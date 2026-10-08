"""Rebuild the index from the metadata files, when no index will decrypt.

docs/specs/DEED-0003-index-and-recovery.md § 4.6 step 4.
"""

from __future__ import annotations

from pathlib import Path

from paperkist.errors import VaultCorrupt
from paperkist.vault import documents, layout


def rebuild(folder: Path, key: bytes) -> list[dict]:
    """Every readable metadata file's object. Unreadable ones are skipped;
    reconcile reports them."""
    entries = []
    for path in sorted((folder / layout.OBJECTS).glob("*.m")):
        doc_id = path.stem
        if not layout.is_id(doc_id):
            continue
        try:
            entries.append(documents.read_metadata(path, key, doc_id))
        except VaultCorrupt:
            continue
    return entries
