"""docs/specs/DEED-0004-format-migration.md INV-1 to INV-7.

INV-1 and INV-2 run against the reader DEED-0002/DEED-0003 already built, so
they pass today. INV-3 to INV-7 exercise `layout.FILE_FORMAT`,
`layout.VAULT_FORMAT` and `paperkist.vault.migrate`, which this item creates —
until then they are expected to fail, diagnosably, at the first line that
touches one of those. `paperkist.vault.migrate` is imported inside each such
test (never at module scope) so a missing module fails only that test, not
collection of the whole file.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import struct
from pathlib import Path

import nacl.pwhash.argon2id as argon2id
import pytest

from paperkist import crypto
from paperkist.errors import VaultCorrupt, VaultTooNew
from paperkist.vault import Vault, documents, layout
from fixtures import sample_vault

FAST = {"opslimit": argon2id.OPSLIMIT_MIN, "memlimit": argon2id.MEMLIMIT_MIN}


def make_vault(tmp_path: Path) -> tuple[Path, Vault]:
    folder = tmp_path / "vault"
    return folder, Vault.create(folder, "correct horse", **FAST)


def add_bytes(vault: Vault, tmp_path: Path, data: bytes, name: str) -> str:
    source = tmp_path / name
    source.write_bytes(data)
    return vault.add(source, "application/pdf")


def by_id(entries: list[dict]) -> dict[str, dict]:
    return {e["id"]: e for e in entries}


def raw_format(data: bytes) -> int:
    """The 2-byte format straight out of a file's prefix, no ceiling check.

    `layout.check_prefix` compares against the pre-DEED-0004 global
    `layout.FORMAT`, which these tests never touch (only the new
    `FILE_FORMAT`/`VAULT_FORMAT` are patched), so it cannot be used to read
    a file this item's migration has already brought past format 1.
    """
    return struct.unpack(">H", data[4:6])[0]


def corrupt_last_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[-1] ^= 0xFF
    path.write_bytes(bytes(data))


def reseal_metadata(old_path: Path, out, key: bytes, doc_id: str, new_fmt: int) -> None:
    """A metadata migration step: same JSON, re-sealed under `new_fmt`.

    Raises `VaultCorrupt` by itself when the old file will not decrypt —
    `crypto.unseal` already does that (§ 4.2's "a step that cannot read the
    old file raises VaultCorrupt").
    """
    data = old_path.read_bytes()
    fmt = raw_format(data)
    plain = crypto.unseal(
        key,
        data[layout.PREFIX_BYTES :],
        crypto.associated_data("metadata", fmt, doc_id),
    )
    sealed = crypto.seal(
        key, plain, crypto.associated_data("metadata", new_fmt, doc_id)
    )
    out.write(layout.METADATA_MAGIC + struct.pack(">H", new_fmt) + sealed)


def reseal_content(old_path: Path, out, key: bytes, doc_id: str, new_fmt: int) -> None:
    """A content migration step: decrypt the whole stream, re-encrypt it."""
    data = old_path.read_bytes()
    fmt = raw_format(data)
    plain = io.BytesIO()
    crypto.decrypt_stream(
        key,
        io.BytesIO(data[layout.PREFIX_BYTES :]),
        plain,
        crypto.associated_data("content", fmt, doc_id),
    )
    plain.seek(0)
    out.write(layout.CONTENT_MAGIC + struct.pack(">H", new_fmt))
    crypto.encrypt_stream(
        key, plain, out, crypto.associated_data("content", new_fmt, doc_id)
    )


def reseal_index(old_path: Path, out, key: bytes, doc_id: str, new_fmt: int) -> None:
    data = old_path.read_bytes()
    fmt = raw_format(data)
    plain = crypto.unseal(
        key, data[layout.PREFIX_BYTES :], crypto.associated_data("index", fmt)
    )
    sealed = crypto.seal(key, plain, crypto.associated_data("index", new_fmt))
    out.write(layout.INDEX_MAGIC + struct.pack(">H", new_fmt) + sealed)


def test_sample_vault_opens(tmp_path):
    """INV-1. Breaks when a reader's layout changes without a step, or a
    format number rises without one."""
    folder = tmp_path / "vault"
    shutil.copytree(sample_vault.FIXTURE, folder)
    vault = Vault.open(folder, sample_vault.PASSWORD)
    try:
        entries = {e["filename"]: e for e in vault.documents()}
        assert entries == sample_vault.EXPECTED_METADATA
        for filename, entry in sample_vault.EXPECTED_METADATA.items():
            assert vault.read(entry["id"]) == sample_vault.expected_content(filename)
    finally:
        vault.close()


def test_sample_vault_unchanged(tmp_path):
    """INV-2. Breaks when the fixture is regenerated or edited."""
    recorded = {}
    for line in sample_vault.HASH_LIST.read_text(encoding="utf-8").splitlines():
        digest, rel = line.split("  ", 1)
        recorded[rel] = digest
    actual = {
        p.relative_to(sample_vault.FIXTURE).as_posix(): hashlib.sha256(
            p.read_bytes()
        ).hexdigest()
        for p in sample_vault.FIXTURE.rglob("*")
        if p.is_file()
    }
    # Plain dict equality already fails on an added or a missing file, in
    # either direction.
    assert actual == recorded


def test_migrates_to_current(tmp_path, monkeypatch):
    """INV-3, INV-4."""
    folder, vault = make_vault(tmp_path)
    first = add_bytes(vault, tmp_path, b"first document", name="a.pdf")
    second = add_bytes(vault, tmp_path, b"second document", name="b.pdf")
    before_reads = {first: vault.read(first), second: vault.read(second)}
    before_entries = vault.documents()
    vault.close()

    assert (folder / "index.prev").exists()  # so migration has one to bring up too

    objects_before = {
        p.relative_to(folder): p.read_bytes() for p in (folder / "objects").glob("*")
    }

    from paperkist.vault import (
        migrate,
    )  # does not exist yet: expected ModuleNotFoundError

    calls: list[str] = []

    def index_step(old_path: Path, out, step_key: bytes, doc_id: str) -> None:
        assert doc_id == ""  # index carries no document id (§ 4.2)
        calls.append(old_path.name)
        reseal_index(old_path, out, step_key, doc_id, new_fmt=2)

    monkeypatch.setattr(layout, "FILE_FORMAT", {**layout.FILE_FORMAT, "index": 2})
    monkeypatch.setattr(layout, "VAULT_FORMAT", 2)
    monkeypatch.setitem(migrate.STEPS, ("index", 1), index_step)

    reopened = Vault.open(folder, "correct horse")
    try:
        # Isolates step 2 itself: skipping `index` and relying on the
        # index.prev fallback would still end at a format-2 `index`.
        assert sorted(calls) == ["index", "index.prev"]
        assert by_id(reopened.documents()) == by_id(before_entries)
        assert reopened.read(first) == before_reads[first]
        assert reopened.read(second) == before_reads[second]
    finally:
        reopened.close()

    # INV-4: content and metadata files are untouched — only index's kind changed.
    for name, data in objects_before.items():
        assert (folder / name).read_bytes() == data, name

    for name in ("index", "index.prev"):
        assert raw_format((folder / name).read_bytes()) == 2

    header = json.loads((folder / "vault.deedbox").read_bytes())
    assert header["format"] == 2


def test_interrupted_migration_resumes(tmp_path, monkeypatch):
    """INV-5. Breaks when the header is written before the files, or an
    upgraded file is upgraded again."""
    folder, vault = make_vault(tmp_path)
    first = add_bytes(vault, tmp_path, b"first document", name="a.pdf")
    second = add_bytes(vault, tmp_path, b"second document", name="b.pdf")
    before_reads = {first: vault.read(first), second: vault.read(second)}
    before_entries = vault.documents()
    vault.close()

    from paperkist.vault import (
        migrate,
    )  # does not exist yet: expected ModuleNotFoundError

    def make_step(fail_on_call: int | None):
        state = {"n": 0}

        def step(old_path: Path, out, step_key: bytes, doc_id: str) -> None:
            state["n"] += 1
            fmt = raw_format(old_path.read_bytes())
            # The step refuses a file already at 2: re-migrating an upgraded
            # file must never happen.
            assert fmt < 2, f"{old_path.name} is already format 2"
            if state["n"] == fail_on_call:
                raise OSError("simulated write failure")
            reseal_metadata(old_path, out, step_key, doc_id, new_fmt=2)

        return step

    monkeypatch.setattr(layout, "FILE_FORMAT", {**layout.FILE_FORMAT, "metadata": 2})
    monkeypatch.setattr(layout, "VAULT_FORMAT", 2)
    monkeypatch.setitem(migrate.STEPS, ("metadata", 1), make_step(fail_on_call=2))

    with pytest.raises(OSError):
        Vault.open(folder, "correct horse")

    header = json.loads((folder / "vault.deedbox").read_bytes())
    assert header["format"] == 1

    m_formats = [
        raw_format(layout.metadata_path(folder, doc_id).read_bytes())
        for doc_id in (first, second)
    ]
    assert set(m_formats) <= {1, 2}
    assert 1 in m_formats, "the interrupted file must not have finished"

    monkeypatch.setitem(migrate.STEPS, ("metadata", 1), make_step(fail_on_call=None))
    reopened = Vault.open(folder, "correct horse")
    try:
        assert by_id(reopened.documents()) == by_id(before_entries)
        assert reopened.read(first) == before_reads[first]
        assert reopened.read(second) == before_reads[second]
    finally:
        reopened.close()

    header = json.loads((folder / "vault.deedbox").read_bytes())
    assert header["format"] == 2
    for doc_id in (first, second):
        assert raw_format(layout.metadata_path(folder, doc_id).read_bytes()) == 2


def test_unreadable_file_survives(tmp_path, monkeypatch):
    """INV-6. Breaks when one bad file aborts the upgrade, or a step's
    failure deletes the file."""
    folder, vault = make_vault(tmp_path)
    bystander = add_bytes(vault, tmp_path, b"bystander document", name="bystander.pdf")
    listed_bad_meta = add_bytes(vault, tmp_path, b"listed, bad metadata", name="a.pdf")
    listed_bad_content = add_bytes(
        vault, tmp_path, b"listed, bad content", name="c.pdf"
    )
    key = vault._key
    bystander_bytes = vault.read(bystander)
    listed_bad_content_bytes = vault.read(listed_bad_content)
    vault.close()

    # An unlisted document: its files exist, but no index entry names it.
    unlisted_id = layout.new_id()
    unlisted_meta_path = layout.metadata_path(folder, unlisted_id)
    documents.write_content(
        layout.content_path(folder, unlisted_id),
        key,
        io.BytesIO(b"orphan body"),
        unlisted_id,
    )
    documents.write_metadata(
        unlisted_meta_path,
        key,
        {
            "id": unlisted_id,
            "filename": "orphan.pdf",
            "type": "application/pdf",
            "size": 11,
            "added": "2026-09-28",
            "edit": 1,
            "extraction": "not yet run",
        },
        unlisted_id,
    )

    corrupt_last_byte(layout.metadata_path(folder, listed_bad_meta))
    corrupt_last_byte(unlisted_meta_path)
    corrupt_last_byte(layout.content_path(folder, listed_bad_content))
    unlisted_meta_bytes = unlisted_meta_path.read_bytes()

    from paperkist.vault import (
        migrate,
    )  # does not exist yet: expected ModuleNotFoundError

    def content_step(old_path: Path, out, step_key: bytes, doc_id: str) -> None:
        reseal_content(old_path, out, step_key, doc_id, new_fmt=2)

    def metadata_step(old_path: Path, out, step_key: bytes, doc_id: str) -> None:
        reseal_metadata(old_path, out, step_key, doc_id, new_fmt=2)

    monkeypatch.setattr(
        layout, "FILE_FORMAT", {**layout.FILE_FORMAT, "content": 2, "metadata": 2}
    )
    monkeypatch.setattr(layout, "VAULT_FORMAT", 2)
    monkeypatch.setitem(migrate.STEPS, ("content", 1), content_step)
    monkeypatch.setitem(migrate.STEPS, ("metadata", 1), metadata_step)

    for attempt in range(2):  # the first open upgrades everything it can; the
        # second has nothing left to upgrade and must show the same outcome.
        reopened = Vault.open(folder, "correct horse")
        try:
            damaged = set(reopened.damaged())
            listed = {e["id"] for e in reopened.documents()}

            assert reopened.read(bystander) == bystander_bytes

            assert listed_bad_meta in listed
            assert listed_bad_meta not in damaged
            fixed = reopened.metadata(listed_bad_meta)
            on_disk = documents.read_metadata(
                layout.metadata_path(folder, listed_bad_meta), key, listed_bad_meta
            )
            assert fixed == on_disk
            assert (
                raw_format(layout.metadata_path(folder, listed_bad_meta).read_bytes())
                == 2
            )

            assert unlisted_id not in listed
            assert unlisted_id in damaged
            assert unlisted_meta_path.read_bytes() == unlisted_meta_bytes  # untouched

            assert listed_bad_content in damaged
            with pytest.raises(VaultCorrupt):
                reopened.read(listed_bad_content)
        finally:
            reopened.close()
        assert attempt in (0, 1)

    header = json.loads((folder / "vault.deedbox").read_bytes())
    assert header["format"] == 2
    # listed_bad_content_bytes is kept only to document what the document
    # held before corruption; it can never be read back (INV-6).
    assert listed_bad_content_bytes


def test_newer_kind_refused(tmp_path, monkeypatch):
    """INV-7. Breaks when a check compares against another kind's number."""
    monkeypatch.setattr(layout, "FILE_FORMAT", {**layout.FILE_FORMAT, "index": 2})
    monkeypatch.setattr(layout, "VAULT_FORMAT", 2)

    folder, vault = make_vault(tmp_path)
    doc_id = add_bytes(vault, tmp_path, b"doc", name="a.pdf")
    vault.close()

    assert raw_format((folder / "index").read_bytes()) == 2
    header = json.loads((folder / "vault.deedbox").read_bytes())
    assert header["format"] == 2

    Vault.open(folder, "correct horse").close()  # up to date: opens plainly

    meta_path = layout.metadata_path(folder, doc_id)
    data = bytearray(meta_path.read_bytes())
    data[4:6] = (2).to_bytes(2, "big")  # metadata's own current number is still 1
    meta_path.write_bytes(bytes(data))

    # A leftover step 3 would delete if the open got that far: the refusal
    # must come from step 0, before anything is written (DEED-0003 INV-7),
    # not from a reader raising VaultTooNew later during reconcile.
    (folder / "objects" / "leftover.tmp").write_bytes(b"leftover")
    before = {
        p.relative_to(folder): (p.stat().st_mtime_ns, p.read_bytes())
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }

    with pytest.raises(VaultTooNew):
        Vault.open(folder, "correct horse")
    after = {
        p.relative_to(folder): (p.stat().st_mtime_ns, p.read_bytes())
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }
    assert after == before


def test_deleted_orphan_not_reported(tmp_path, monkeypatch):
    """§ 4.3 with DEED-0003's reconcile: a content file left below its format
    that reconcile then deletes, as an unfinished add, is not reported by
    `damaged()`. Breaks when the stale ids are taken before reconcile and
    never checked against what it deleted."""
    folder, vault = make_vault(tmp_path)
    key = vault._key
    vault.close()

    orphan = layout.new_id()
    documents.write_content(
        layout.content_path(folder, orphan), key, io.BytesIO(b"orphan"), orphan
    )  # format 1, no metadata file, no index entry

    monkeypatch.setattr(layout, "FILE_FORMAT", {**layout.FILE_FORMAT, "content": 2})
    monkeypatch.setattr(layout, "VAULT_FORMAT", 2)
    header_path = folder / "vault.deedbox"
    header_path.write_text(
        json.dumps({**json.loads(header_path.read_text()), "format": 2})
    )

    reopened = Vault.open(folder, "correct horse")
    try:
        assert not layout.content_path(folder, orphan).exists()
        assert orphan not in reopened.damaged()
    finally:
        reopened.close()
