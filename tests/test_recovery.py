"""docs/specs/DEED-0003-index-and-recovery.md INV-2, INV-3, INV-4, INV-6, INV-7."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from pathlib import Path

import nacl.pwhash.argon2id as argon2id
import pytest

from paperkist.errors import VaultInUse, VaultTooNew, WrongPassword
from paperkist.vault import Vault, documents, index, layout

FAST = {"opslimit": argon2id.OPSLIMIT_MIN, "memlimit": argon2id.MEMLIMIT_MIN}


def new_vault(tmp_path: Path) -> tuple[Path, Vault]:
    folder = tmp_path / "vault"
    return folder, Vault.create(folder, "pw", **FAST)


def add(vault: Vault, tmp_path: Path, body: bytes) -> str:
    source = tmp_path / "source.pdf"
    source.write_bytes(body)
    return vault.add(source, "application/pdf")


def objects(folder: Path, doc_id: str) -> tuple[Path, Path]:
    return layout.content_path(folder, doc_id), layout.metadata_path(folder, doc_id)


def snapshot(folder: Path) -> dict:
    return {
        p.relative_to(folder): (p.stat().st_mtime_ns, p.read_bytes())
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def assert_whole(folder: Path) -> list[str]:
    """INV-2's outcome: every listed document whole, nothing half there."""
    vault = Vault.open(folder, "pw")
    try:
        listed = [d["id"] for d in vault.documents()]
        for doc_id in listed:
            vault.read(doc_id)
            assert objects(folder, doc_id)[1].exists()
    finally:
        vault.close()
    assert not list(folder.rglob("*.tmp"))
    for c in (folder / "objects").glob("*.c"):
        assert c.stem in listed, f"orphan content {c.name}"
    return listed


def crash_state(tmp_path: Path, state: str) -> tuple[Path, str]:
    """A vault as a crash at `state` would leave it; returns the affected id."""
    folder, vault = new_vault(tmp_path)
    add(vault, tmp_path, b"bystander")
    key = vault._key
    if state == "add: content only":
        doc_id = layout.new_id()
        documents.write_content(
            objects(folder, doc_id)[0], key, io.BytesIO(b"x"), doc_id
        )
    elif state == "add: content and index":
        doc_id = add(vault, tmp_path, b"x")
        objects(folder, doc_id)[1].unlink()
    elif state == "update: index only":
        doc_id = add(vault, tmp_path, b"x")
        old = objects(folder, doc_id)[1].read_bytes()
        vault.update(doc_id, {"title": "new"})
        objects(folder, doc_id)[1].write_bytes(old)
    elif state == "remove: metadata deleted":
        doc_id = add(vault, tmp_path, b"x")
        objects(folder, doc_id)[1].unlink()
    elif state == "remove: index saved":
        doc_id = add(vault, tmp_path, b"x")
        content = objects(folder, doc_id)[0].read_bytes()
        vault.remove(doc_id)
        objects(folder, doc_id)[0].write_bytes(content)
    else:
        raise AssertionError(state)
    (folder / "objects" / f"{doc_id}.m.tmp").write_bytes(b"half written")
    vault.close()
    return folder, doc_id


@pytest.mark.parametrize(
    ("state", "present"),
    [
        ("add: content only", False),
        ("add: content and index", True),
        ("update: index only", True),
        ("remove: metadata deleted", True),
        ("remove: index saved", False),
    ],
)
def test_crash_states(tmp_path, state, present):
    """INV-2. 'add: content only' isolates the deletion row: no metadata and
    no index entry exist, so no other row can remove it."""
    folder, doc_id = crash_state(tmp_path, state)
    listed = assert_whole(folder)
    assert (doc_id in listed) is present
    if state == "update: index only":
        vault = Vault.open(folder, "pw")
        key = vault._key
        assert vault.metadata(doc_id)["title"] == "new"
        on_disk = documents.read_metadata(objects(folder, doc_id)[1], key, doc_id)
        assert on_disk["edit"] == 2
        vault.close()


def corrupt(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[-1] ^= 0xFF
    path.write_bytes(bytes(data))


def test_index_fallbacks(tmp_path):
    """INV-3. The second document is only in `index` and metadata, never in
    `index.prev`, so only the 'no entry' row can list it after a fallback."""
    folder, vault = new_vault(tmp_path)
    first = add(vault, tmp_path, b"first")
    second = add(vault, tmp_path, b"second")
    key = vault._key
    vault.close()
    previous = index.read(folder / "index.prev", key)
    assert [e["id"] for e in previous] == [first]

    corrupt(folder / "index")
    assert set(assert_whole(folder)) == {first, second}
    assert index.read(folder / "index.prev", key) == previous

    corrupt(folder / "index")
    corrupt(folder / "index.prev")
    assert set(assert_whole(folder)) == {first, second}


def test_edit_counter(tmp_path):
    """INV-4: ahead wins, behind is rewritten."""
    folder, vault = new_vault(tmp_path)
    doc_id = add(vault, tmp_path, b"doc")
    vault.update(doc_id, {"title": "two"})
    key = vault._key
    entry = vault.metadata(doc_id)
    vault.close()
    meta_path = objects(folder, doc_id)[1]

    documents.write_metadata(
        meta_path, key, {**entry, "title": "three", "edit": 3}, doc_id
    )
    reopened = Vault.open(folder, "pw")
    assert reopened.metadata(doc_id)["title"] == "three"
    reopened.close()

    documents.write_metadata(
        meta_path, key, {**entry, "title": "one", "edit": 1}, doc_id
    )
    reopened = Vault.open(folder, "pw")
    assert reopened.metadata(doc_id)["title"] == "three"
    assert documents.read_metadata(meta_path, key, doc_id)["edit"] == 3
    reopened.close()


WRITER = """
import os, sys
from pathlib import Path
from paperkist.vault import Vault
vault = Vault.open(sys.argv[1], "pw")
source = Path(sys.argv[2])
n = 0
while True:
    source.write_bytes(os.urandom(70000))
    doc_id = vault.add(source, "application/pdf")
    print(doc_id, flush=True)
    vault.update(doc_id, {"n": n})
    n += 1
"""


KILL_AFTER = (1, 2, 3, 4, 5, 6, 8, 10, 12, 15)
# Seconds between the Nth id and the kill. Killing at once lands just after
# `add` returned, before the next write starts, often enough that ten runs on
# a fast machine can all miss; a spread of delays reaches into the writes.
KILL_DELAY = (0, 0.0005, 0.001, 0.002, 0.004, 0.008, 0.016)


def assert_whole_after_kill(folder: Path) -> list[str]:
    """Windows drops a killed process's lock some time after it exits."""
    deadline = time.monotonic() + 10
    while True:
        try:
            return assert_whole(folder)
        except VaultInUse:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.05)


def test_kill_during_writes(tmp_path):
    """INV-6. Killed shortly after N ids are printed, for many N and delays;
    at least one run must leave a mid-write state, or the kills proved
    nothing. Runs past the ten until one does, up to a cap."""
    folder = tmp_path / "vault"
    Vault.create(folder, "pw", **FAST).close()
    returned, caught_mid_write = [], 0
    for run in range(60):
        if run >= len(KILL_AFTER) and caught_mid_write:
            break
        n = KILL_AFTER[run % len(KILL_AFTER)]
        child = subprocess.Popen(  # noqa: S603 — our own interpreter and script
            [sys.executable, "-c", WRITER, str(folder), str(tmp_path / "src.pdf")],
            stdout=subprocess.PIPE,
            text=True,
        )
        for _ in range(n):
            returned.append(child.stdout.readline().strip())
        time.sleep(KILL_DELAY[run % len(KILL_DELAY)])
        child.kill()
        child.wait()
        leftovers = list(folder.rglob("*.tmp"))
        orphans = [
            c
            for c in (folder / "objects").glob("*.c")
            if not c.with_suffix(".m").exists()
        ]
        caught_mid_write += bool(leftovers or orphans)
        listed = assert_whole_after_kill(folder)
        assert set(returned) <= set(listed)
    assert caught_mid_write, "no kill landed mid-write; the test proved nothing"


def test_refusals_write_nothing(tmp_path):
    """INV-7. The too-new `.m` case isolates step 0: the header is current."""
    folder, vault = new_vault(tmp_path)
    doc_id = add(vault, tmp_path, b"doc")
    key = vault._key
    vault.close()
    orphan = layout.new_id()
    documents.write_content(objects(folder, orphan)[0], key, io.BytesIO(b"o"), orphan)
    (folder / "objects" / "leftover.tmp").write_bytes(b"x")

    before = snapshot(folder)
    with pytest.raises(WrongPassword):
        Vault.open(folder, "wrong")
    assert snapshot(folder) == before

    header_path = folder / "vault.deedbox"
    original = header_path.read_bytes()
    header_path.write_text(json.dumps({**json.loads(original), "format": 2}))
    before = snapshot(folder)
    with pytest.raises(VaultTooNew):
        Vault.open(folder, "pw")
    assert snapshot(folder) == before
    header_path.write_bytes(original)

    meta_path = objects(folder, doc_id)[1]
    data = bytearray(meta_path.read_bytes())
    data[4:6] = (2).to_bytes(2, "big")
    meta_path.write_bytes(bytes(data))
    before = snapshot(folder)
    with pytest.raises(VaultTooNew):
        Vault.open(folder, "pw")
    assert snapshot(folder) == before
