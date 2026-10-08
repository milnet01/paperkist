"""The frozen format-1 sample vault: shared by the generator and the tests.

docs/specs/DEED-0004-format-migration.md § 4.4. The folder this module
generates, `vault-format-1/`, is never regenerated — a later release that
changes a format keeps it and adds a migration step. This module is the one
place its expected content and metadata are written down, so the tests need
no second copy.

Regenerating (only ever done once, to create the checked-in fixture)::

    python -m tests.fixtures.sample_vault
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

FIXTURE = Path(__file__).parent / "vault-format-1"
HASH_LIST = Path(__file__).parent / "vault-format-1.sha256"

PASSWORD = "deedbox-sample-1"  # noqa: S105 — a checked-in fixture's password, not a secret
OPSLIMIT = 1
MEMLIMIT = 8192

# (filename, mime type, byte size), in the order the generator adds them.
# The sizes are the ones docs/specs/DEED-0004-format-migration.md § 4.4 names:
# the empty final piece, a full piece then an empty one, several pieces, a
# non-ASCII name, and one edited document.
DOCUMENTS = [
    ("empty.txt", "text/plain", 0),
    ("boundary.bin", "application/octet-stream", 65536),
    ("scan.pdf", "application/pdf", 150000),
    ("Überweisung Mai.txt", "text/plain", 48),
    ("edited.txt", "text/plain", 48),
]

_SIZE_BY_NAME = {name: size for name, _mime, size in DOCUMENTS}

# The one `update` call the generator makes on edited.txt, which is why its
# `edit` is 2 in EXPECTED_METADATA below while every other document's is 1.
EDITED_UPDATE = {"extraction": "checked"}

# Recorded from the single run that produced the checked-in vault-format-1/
# folder. Never derive this from a fresh run — it names the frozen fixture's
# actual metadata, ids included, which is why INV-1 can compare exact values.
EXPECTED_METADATA = {
    "empty.txt": {
        "filename": "empty.txt",
        "type": "text/plain",
        "size": 0,
        "added": "2026-09-28",
        "edit": 1,
        "extraction": "not yet run",
        "id": "4e05f3ecd0b117cb285c56d6c2feec85",
    },
    "boundary.bin": {
        "filename": "boundary.bin",
        "type": "application/octet-stream",
        "size": 65536,
        "added": "2026-09-28",
        "edit": 1,
        "extraction": "not yet run",
        "id": "4d7cf76927479c6bda7944ba75ede7b3",
    },
    "scan.pdf": {
        "filename": "scan.pdf",
        "type": "application/pdf",
        "size": 150000,
        "added": "2026-09-28",
        "edit": 1,
        "extraction": "not yet run",
        "id": "c9091649f64a7788fc50769869eed971",
    },
    "Überweisung Mai.txt": {
        "filename": "Überweisung Mai.txt",
        "type": "text/plain",
        "size": 48,
        "added": "2026-09-28",
        "edit": 1,
        "extraction": "not yet run",
        "id": "dd60dd482a6f691fbd47e1de3509ea2e",
    },
    "edited.txt": {
        "filename": "edited.txt",
        "type": "text/plain",
        "size": 48,
        "added": "2026-09-28",
        "edit": 2,
        "extraction": "checked",
        "id": "4b657f7d06f256a513df5ab52e27b7d4",
    },
}


def expected_content(filename: str) -> bytes:
    """The deterministic bytes `filename` holds, at the size DOCUMENTS names.

    Derived from `filename` through hashlib, so no second copy of the bytes
    has to be carried anywhere: the expected content is computable from the
    name alone.
    """
    size = _SIZE_BY_NAME[filename]
    out = bytearray()
    block = 0
    while len(out) < size:
        out.extend(hashlib.sha256(f"{filename}#{block}".encode()).digest())
        block += 1
    return bytes(out[:size])


def generate() -> None:
    """Write `vault-format-1/` and `vault-format-1.sha256`. Run once, ever."""
    if FIXTURE.exists():
        raise FileExistsError(
            f"{FIXTURE} already exists; the fixture is generated once and "
            "never overwritten"
        )
    from paperkist.vault import Vault  # local: this module is also imported by tests

    sources = FIXTURE.parent / "_sample_vault_sources.tmp"
    sources.mkdir(parents=True)
    try:
        vault = Vault.create(FIXTURE, PASSWORD, opslimit=OPSLIMIT, memlimit=MEMLIMIT)
        try:
            ids = {}
            for filename, mime_type, _size in DOCUMENTS:
                source = sources / filename
                source.write_bytes(expected_content(filename))
                ids[filename] = vault.add(source, mime_type)
            vault.update(ids["edited.txt"], dict(EDITED_UPDATE))
        finally:
            vault.close()
    finally:
        shutil.rmtree(sources, ignore_errors=True)

    (FIXTURE / "lock").unlink(missing_ok=True)

    lines = []
    for path in sorted(p for p in FIXTURE.rglob("*") if p.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(FIXTURE).as_posix()}")
    HASH_LIST.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate()
