"""docs/specs/DEED-0003-index-and-recovery.md INV-1."""

from __future__ import annotations

import nacl.pwhash.argon2id as argon2id

from paperkist.vault import Vault

FAST = {"opslimit": argon2id.OPSLIMIT_MIN, "memlimit": argon2id.MEMLIMIT_MIN}


def test_changes_survive_reopen(tmp_path):
    """INV-1: add, update and remove all reach the index."""
    folder = tmp_path / "vault"
    vault = Vault.create(folder, "pw", **FAST)
    ids = []
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        source = tmp_path / name
        source.write_bytes(name.encode())
        ids.append(vault.add(source, "application/pdf"))
    vault.update(ids[0], {"title": "Fridge receipt"})
    vault.remove(ids[1])
    vault.close()

    reopened = Vault.open(folder, "pw")
    listed = {d["id"]: d for d in reopened.documents()}
    assert set(listed) == {ids[0], ids[2]}
    assert listed[ids[0]]["title"] == "Fridge receipt"
    assert listed[ids[0]]["edit"] == 2
    assert reopened.read(ids[2]) == b"c.pdf"
