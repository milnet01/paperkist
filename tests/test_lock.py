"""docs/specs/DEED-0003-index-and-recovery.md INV-5."""

from __future__ import annotations

import subprocess
import sys

import nacl.pwhash.argon2id as argon2id
import pytest

from paperkist.errors import VaultInUse
from paperkist.vault import Vault

FAST = {"opslimit": argon2id.OPSLIMIT_MIN, "memlimit": argon2id.MEMLIMIT_MIN}

HOLDER = """
import sys
from paperkist.vault import Vault
vault = Vault.open(sys.argv[1], "pw")
print("open", flush=True)
sys.stdin.read()
"""


def test_second_open_refused(tmp_path):
    """INV-5: from another process, and from this one."""
    folder = tmp_path / "vault"
    Vault.create(folder, "pw", **FAST).close()

    holder = subprocess.Popen(  # noqa: S603 — our own interpreter and script
        [sys.executable, "-c", HOLDER, str(folder)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "open"
        with pytest.raises(VaultInUse):
            Vault.open(folder, "pw")
    finally:
        holder.communicate("", timeout=30)
    Vault.open(folder, "pw").close()

    first = Vault.open(folder, "pw")
    with pytest.raises(VaultInUse):
        Vault.open(folder, "pw")
    first.close()
    Vault.open(folder, "pw").close()
