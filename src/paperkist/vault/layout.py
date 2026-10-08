"""Where everything lives in a vault folder, and each encrypted file's prefix.

docs/specs/DEED-0002-vault-format.md § 4.1 and § 4.3;
docs/specs/DEED-0004-format-migration.md § 4.1.
"""

from __future__ import annotations

import re
import secrets
import struct
from pathlib import Path

from paperkist.errors import VaultCorrupt, VaultTooNew

# Read when called, never copied at import: tests raise them to exercise
# migration (DEED-0004 § 7).
VAULT_FORMAT = 1
FILE_FORMAT = {"content": 1, "metadata": 1, "index": 1}
# The app's old name, kept: existing vaults need it (DEED-0023).
HEADER = "vault.deedbox"
OBJECTS = "objects"

CONTENT_MAGIC = b"DBXC"
METADATA_MAGIC = b"DBXM"
INDEX_MAGIC = b"DBXI"
MAGIC = {"content": CONTENT_MAGIC, "metadata": METADATA_MAGIC, "index": INDEX_MAGIC}
PREFIX_BYTES = 6

_ID = re.compile(r"[0-9a-f]{32}")


def new_id() -> str:
    return secrets.token_hex(16)


def is_id(value: str) -> bool:
    return _ID.fullmatch(value) is not None


def content_path(folder: Path, doc_id: str) -> Path:
    return folder / OBJECTS / f"{doc_id}.c"


def metadata_path(folder: Path, doc_id: str) -> Path:
    return folder / OBJECTS / f"{doc_id}.m"


def prefix(kind: str) -> bytes:
    return MAGIC[kind] + struct.pack(">H", FILE_FORMAT[kind])


def file_format(head: bytes, kind: str) -> int | None:
    """The format number in a file's first bytes, or None if not that kind."""
    if len(head) < PREFIX_BYTES or head[:4] != MAGIC[kind]:
        return None
    (fmt,) = struct.unpack(">H", head[4:PREFIX_BYTES])
    return fmt


def check_prefix(data: bytes, kind: str) -> int:
    """The file's format number, once it is the current one for its kind.

    An older file is one migration could not upgrade (DEED-0004 § 4.1).
    """
    fmt = file_format(data, kind)
    if fmt is None:
        raise VaultCorrupt("not the file type expected here")
    if fmt > FILE_FORMAT[kind]:
        raise VaultTooNew(f"file format {fmt}")
    if fmt != FILE_FORMAT[kind]:
        raise VaultCorrupt(f"file format {fmt}")
    return fmt
