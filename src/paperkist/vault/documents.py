"""Reading and writing a document's two files, `<id>.c` and `<id>.m`.

docs/specs/DEED-0002-vault-format.md § 4.3 and § 4.5.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import BinaryIO

from paperkist import crypto
from paperkist.errors import DocumentMissing, VaultCorrupt
from paperkist.vault import atomic, layout


def write_content(path: Path, key: bytes, src: BinaryIO, doc_id: str) -> None:
    ad = crypto.associated_data("content", layout.FILE_FORMAT["content"], doc_id)
    with atomic.write_stream(path) as out:
        out.write(layout.prefix("content"))
        crypto.encrypt_stream(key, src, out, ad)


def read_content(path: Path, key: bytes, doc_id: str) -> bytes:
    try:
        src = path.open("rb")
    except FileNotFoundError as err:
        raise DocumentMissing(doc_id) from err
    with src:
        fmt = layout.check_prefix(src.read(layout.PREFIX_BYTES), "content")
        out = io.BytesIO()
        crypto.decrypt_stream(
            key, src, out, crypto.associated_data("content", fmt, doc_id)
        )
        return out.getvalue()


def write_metadata(path: Path, key: bytes, metadata: dict, doc_id: str) -> None:
    ad = crypto.associated_data("metadata", layout.FILE_FORMAT["metadata"], doc_id)
    body = json.dumps(metadata).encode("utf-8")
    atomic.write_bytes(path, layout.prefix("metadata") + crypto.seal(key, body, ad))


def read_metadata(path: Path, key: bytes, doc_id: str) -> dict:
    try:
        data = path.read_bytes()
    except FileNotFoundError as err:
        raise DocumentMissing(doc_id) from err
    fmt = layout.check_prefix(data, "metadata")
    ad = crypto.associated_data("metadata", fmt, doc_id)
    plain = crypto.unseal(key, data[layout.PREFIX_BYTES :], ad)
    try:
        metadata = json.loads(plain.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as err:
        raise VaultCorrupt("metadata is not valid JSON") from err
    if not isinstance(metadata, dict):
        raise VaultCorrupt("metadata is not an object")
    return metadata
