"""docs/specs/DEED-0002-vault-format.md INV-5 (role), INV-6 and INV-7."""

from __future__ import annotations

import json
import unicodedata

import nacl.pwhash.argon2id as argon2id
import nacl.utils
import pytest

from paperkist import crypto
from paperkist.errors import VaultCorrupt, WrongPassword

FAST = {"opslimit": argon2id.OPSLIMIT_MIN, "memlimit": argon2id.MEMLIMIT_MIN}


def test_role_binding():
    """INV-5: metadata and content associated data differ only in the role."""
    key = nacl.utils.random(32)
    doc_id = "0" * 32
    as_metadata = crypto.associated_data("metadata", 1, doc_id)
    as_content = crypto.associated_data("content", 1, doc_id)
    blob = crypto.seal(key, b"body", as_metadata)
    assert crypto.unseal(key, blob, as_metadata) == b"body"
    with pytest.raises(VaultCorrupt):
        crypto.unseal(key, blob, as_content)


@pytest.mark.parametrize("made_as", ["NFC", "NFD"])
def test_password_normalisation(made_as):
    """INV-6: the same password in either Unicode form opens the vault."""
    other = "NFD" if made_as == "NFC" else "NFC"
    made = unicodedata.normalize(made_as, "café")
    typed = unicodedata.normalize(other, "café")
    assert made.encode() != typed.encode()
    record, key = crypto.new_key_record(made, **FAST)
    assert crypto.unlock(record, typed) == key


def test_settings_come_from_record():
    """INV-7: unlock derives with the record's settings, not the defaults."""
    record, key = crypto.new_key_record("pw", **FAST)
    assert crypto.unlock(record, "pw") == key
    tampered = json.loads(record)
    tampered["opslimit"] = 2
    with pytest.raises(WrongPassword):
        crypto.unlock(json.dumps(tampered).encode(), "pw")
