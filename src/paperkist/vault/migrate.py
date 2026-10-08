"""Bring an older vault's files to this release's formats, header last.

docs/specs/DEED-0004-format-migration.md § 4.2 and § 4.3.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from paperkist.errors import VaultCorrupt
from paperkist.vault import atomic, index, layout

# (kind, n) turns a file of that kind at format n into one at n + 1: it gets
# the old file's path, an output stream, the vault key and the document id
# ("" for the index), and writes the whole new file. A step that cannot read
# the old file raises VaultCorrupt.
Step = Callable[[Path, BinaryIO, bytes, str], None]
# ("header", n) takes the header object at vault format n and returns the next.
HeaderStep = Callable[[dict], dict]
STEPS: dict[tuple[str, int], Step | HeaderStep] = {}


def run(folder: Path, key: bytes, header_format: int) -> None:
    """Step 2 of opening (DEED-0003 § 4.6).

    The header is written only after every file has been tried, so a run cut
    off anywhere is resumed by the next open.
    """
    if header_format == layout.VAULT_FORMAT:
        return
    for path, kind in index.encrypted_files(folder):
        if kind == "index":
            _upgrade(path, kind, key, "")
        elif layout.is_id(path.stem):  # reconcile ignores any other name too
            _upgrade(path, kind, key, path.stem)
    header_path = folder / layout.HEADER
    header = json.loads(header_path.read_bytes().decode("utf-8"))
    for n in range(header_format, layout.VAULT_FORMAT):
        step = STEPS.get(("header", n))
        if step is not None:
            header = step(header)
    header["format"] = layout.VAULT_FORMAT
    atomic.write_bytes(header_path, json.dumps(header).encode("utf-8"))


def _upgrade(path: Path, kind: str, key: bytes, doc_id: str) -> None:
    """One file, one atomic replace per step; an unreadable file is left."""
    fmt = layout.file_format(index.head(path), kind)
    if fmt is None or fmt < 1:
        return
    for n in range(fmt, layout.FILE_FORMAT[kind]):
        step = STEPS[(kind, n)]
        try:
            with atomic.write_stream(path) as out:
                step(path, out, key, doc_id)
        except VaultCorrupt:
            return
