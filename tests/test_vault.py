"""docs/specs/DEED-0002-vault-format.md INV-1 to INV-5 and INV-8."""

from __future__ import annotations

import base64
import datetime
import json
import os
import re
from pathlib import Path

import nacl.pwhash.argon2id as argon2id
import pytest

from paperkist.errors import VaultCorrupt, VaultTooNew, WrongPassword
from paperkist.vault import Vault

FAST = {"opslimit": argon2id.OPSLIMIT_MIN, "memlimit": argon2id.MEMLIMIT_MIN}
PIECE_OUT = 65536 + 17  # ciphertext bytes per full secretstream piece


def make_vault(tmp_path: Path) -> tuple[Path, Vault]:
    folder = tmp_path / "vault"
    return folder, Vault.create(folder, "correct horse", **FAST)


def add_bytes(vault: Vault, tmp_path: Path, data: bytes, name: str = "doc.pdf") -> str:
    source = tmp_path / name
    source.write_bytes(data)
    return vault.add(source, "application/pdf")


def snapshot(folder: Path) -> dict:
    """Every file under `folder`: its modification time and bytes."""
    return {
        p.relative_to(folder): (p.stat().st_mtime_ns, p.read_bytes())
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize("size", [0, 1, 65535, 65536, 65537, 200000])
def test_round_trip(tmp_path, size):
    """INV-1, across the piece boundary and the empty final piece."""
    folder, vault = make_vault(tmp_path)
    data = os.urandom(size)
    doc_id = add_bytes(vault, tmp_path, data)
    vault.close()
    assert Vault.open(folder, "correct horse").read(doc_id) == data


def test_wrong_password(tmp_path):
    """INV-2."""
    folder, vault = make_vault(tmp_path)
    add_bytes(vault, tmp_path, b"receipt")
    vault.close()
    before = snapshot(folder)
    with pytest.raises(WrongPassword):
        Vault.open(folder, "wrong horse")
    assert snapshot(folder) == before


def test_nothing_readable(tmp_path):
    """INV-3 (S5)."""
    folder, vault = make_vault(tmp_path)
    add_bytes(vault, tmp_path, b"marker-CONTENT", name="marker-FILENAME.pdf")
    # Closed first: Windows refuses to read the held `lock` file.
    vault.close()
    today = datetime.date.today().isoformat().encode()
    for path, (_, data) in snapshot(folder).items():
        for secret in (b"marker-CONTENT", b"marker-FILENAME", today):
            assert secret not in data, f"{secret!r} readable in {path}"
    names = [p.name for p in (folder / "objects").iterdir()]
    assert names
    assert all(re.fullmatch(r"[0-9a-f]{32}\.(c|m)", n) for n in names), names


@pytest.mark.parametrize(
    "cut",
    [
        "after_stream_header",
        "after_first_piece",
        "into_final_piece",
        "one_byte_appended",
    ],
)
def test_truncation(tmp_path, cut):
    """INV-4. after_first_piece leaves only valid pieces: only the final-tag rule rejects it."""
    folder, vault = make_vault(tmp_path)
    doc_id = add_bytes(vault, tmp_path, os.urandom(200000))
    content = folder / "objects" / f"{doc_id}.c"
    data = content.read_bytes()
    final_piece = 200000 - 3 * 65536 + 17
    damaged = {
        "after_stream_header": data[: 6 + 24],
        "after_first_piece": data[: 6 + 24 + PIECE_OUT],
        "into_final_piece": data[: len(data) - final_piece + 1],
        "one_byte_appended": data + b"\x00",
    }[cut]
    content.write_bytes(damaged)
    with pytest.raises(VaultCorrupt):
        vault.read(doc_id)


def test_binding(tmp_path):
    """INV-5 (id): swapped content files are valid ciphertext; only the id rejects them."""
    folder, vault = make_vault(tmp_path)
    first = add_bytes(vault, tmp_path, b"first document", name="a.pdf")
    second = add_bytes(vault, tmp_path, b"second document", name="b.pdf")
    a, b = (folder / "objects" / f"{i}.c" for i in (first, second))
    a_bytes, b_bytes = a.read_bytes(), b.read_bytes()
    a.write_bytes(b_bytes)
    b.write_bytes(a_bytes)
    for doc_id in (first, second):
        with pytest.raises(VaultCorrupt):
            vault.read(doc_id)


def test_too_new(tmp_path):
    """INV-8: a newer header, key record or file prefix is refused, untouched."""
    folder, vault = make_vault(tmp_path)
    doc_id = add_bytes(vault, tmp_path, b"receipt")
    vault.close()
    header_path = folder / "vault.deedbox"
    original_header = header_path.read_bytes()

    header = json.loads(original_header)
    header["format"] = 2
    header_path.write_text(json.dumps(header))
    before = snapshot(folder)
    with pytest.raises(VaultTooNew):
        Vault.open(folder, "correct horse")
    assert snapshot(folder) == before

    header = json.loads(original_header)
    record = json.loads(base64.b64decode(header["key_record"]))
    record["version"] = 2
    header["key_record"] = base64.b64encode(json.dumps(record).encode()).decode()
    header_path.write_text(json.dumps(header))
    before = snapshot(folder)
    with pytest.raises(VaultTooNew):
        Vault.open(folder, "correct horse")
    assert snapshot(folder) == before

    header_path.write_bytes(original_header)
    content = folder / "objects" / f"{doc_id}.c"
    data = bytearray(content.read_bytes())
    data[4:6] = (2).to_bytes(2, "big")
    content.write_bytes(bytes(data))
    # DEED-0003 § 4.6 step 0 refuses a newer file when the vault opens.
    before = snapshot(folder)
    with pytest.raises(VaultTooNew):
        Vault.open(folder, "correct horse")
    assert snapshot(folder) == before
