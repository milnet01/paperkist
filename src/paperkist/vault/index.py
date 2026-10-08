"""The index: check, load with fallbacks, save, and reconcile on open.

docs/specs/DEED-0003-index-and-recovery.md § 4.2, § 4.3 and § 4.6.
"""

from __future__ import annotations

import json
from pathlib import Path

from paperkist import crypto
from paperkist.errors import DocumentMissing, VaultCorrupt, VaultTooNew
from paperkist.vault import atomic, documents, layout
from paperkist.vault.rebuild import rebuild

INDEX = "index"
PREVIOUS = "index.prev"


def check_prefixes(folder: Path) -> None:
    """Step 0: refuse any file newer than this release before writing."""
    for path, kind in encrypted_files(folder):
        fmt = layout.file_format(head(path), kind)
        if fmt is not None and fmt > layout.FILE_FORMAT[kind]:
            raise VaultTooNew(f"{path.name} has format {fmt}")


def stale_content(folder: Path) -> list[str]:
    """Ids whose content file migration left below its format (DEED-0004 § 4.3)."""
    return [
        path.stem
        for path, kind in encrypted_files(folder)
        if kind == "content"
        and layout.is_id(path.stem)
        and (fmt := layout.file_format(head(path), kind)) is not None
        and fmt < layout.FILE_FORMAT[kind]
    ]


def encrypted_files(folder: Path) -> list[tuple[Path, str]]:
    """Every file that carries a prefix, with its kind: objects, then the index."""
    files = []
    for path in sorted((folder / layout.OBJECTS).iterdir()):
        if path.suffix == ".c":
            files.append((path, "content"))
        elif path.suffix == ".m":
            files.append((path, "metadata"))
    return [*files, (folder / PREVIOUS, "index"), (folder / INDEX, "index")]


def head(path: Path) -> bytes:
    try:
        with path.open("rb") as f:
            return f.read(layout.PREFIX_BYTES)
    except FileNotFoundError:
        return b""


def delete_leftovers(folder: Path) -> bool:
    """Step 3: every *.tmp is an interrupted write."""
    leftovers = [*folder.glob("*.tmp"), *(folder / layout.OBJECTS).glob("*.tmp")]
    for path in leftovers:
        path.unlink()
    return bool(leftovers)


def load(folder: Path, key: bytes) -> tuple[list[dict], str]:
    """Step 4: the index, its previous copy, or a rebuild — and which."""
    for name in (INDEX, PREVIOUS):
        entries = _try_read(folder / name, key)
        if entries is not None:
            return entries, name
    return rebuild(folder, key), "rebuild"


def read(path: Path, key: bytes) -> list[dict]:
    data = path.read_bytes()
    fmt = layout.check_prefix(data, "index")
    plain = crypto.unseal(
        key, data[layout.PREFIX_BYTES :], crypto.associated_data("index", fmt)
    )
    try:
        body = json.loads(plain.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as err:
        raise VaultCorrupt("index is not valid JSON") from err
    entries = body.get("documents") if isinstance(body, dict) else None
    if not isinstance(entries, list) or not all(
        isinstance(e, dict) and layout.is_id(str(e.get("id"))) for e in entries
    ):
        raise VaultCorrupt("index has no valid document list")
    return entries


def save(folder: Path, key: bytes, entries: list[dict], *, keep_previous: bool) -> None:
    """§ 4.3. `keep_previous` is False after a fallback or rebuild, so a
    corrupt index is never copied over index.prev."""
    current = folder / INDEX
    if keep_previous and current.exists():
        atomic.write_bytes(folder / PREVIOUS, current.read_bytes())
    body = json.dumps({"documents": entries}).encode("utf-8")
    sealed = crypto.seal(
        key, body, crypto.associated_data("index", layout.FILE_FORMAT["index"])
    )
    atomic.write_bytes(current, layout.prefix("index") + sealed)


def reconcile(
    folder: Path, key: bytes, entries: list[dict]
) -> tuple[list[dict], bool, list[str]]:
    """Step 5: the table in § 4.6, first matching row wins.

    Returns the reconciled entries, whether the index changed, and the ids
    for `damaged()`.
    """
    by_id = {e["id"]: e for e in entries}
    on_disk = {
        p.stem
        for p in (folder / layout.OBJECTS).iterdir()
        if p.suffix in (".c", ".m") and layout.is_id(p.stem)
    }
    changed, damaged = False, []
    for doc_id in sorted(on_disk | by_id.keys()):
        content = layout.content_path(folder, doc_id)
        meta_path = layout.metadata_path(folder, doc_id)
        entry = by_id.get(doc_id)
        meta, meta_state = _read_meta(meta_path, key, doc_id)

        if not content.exists():
            if meta_state == "missing":
                if entry is not None:
                    del by_id[doc_id]
                    changed = True
            else:
                damaged.append(doc_id)
            continue
        if entry is not None:
            entry_edit = entry.get("edit", 0)
            if meta_state == "readable" and meta["edit"] > entry_edit:
                by_id[doc_id] = meta
                changed = True
            elif meta_state != "readable" or meta["edit"] < entry_edit:
                documents.write_metadata(meta_path, key, entry, doc_id)
        elif meta_state == "readable":
            by_id[doc_id] = meta
            changed = True
        elif meta_state == "unreadable":
            damaged.append(doc_id)
        else:
            atomic.delete(content)
    return list(by_id.values()), changed, damaged


def _try_read(path: Path, key: bytes) -> list[dict] | None:
    try:
        return read(path, key)
    except (FileNotFoundError, VaultCorrupt):
        return None


def _read_meta(path: Path, key: bytes, doc_id: str) -> tuple[dict | None, str]:
    try:
        meta = documents.read_metadata(path, key, doc_id)
    except DocumentMissing:
        return None, "missing"
    except VaultCorrupt:
        return None, "unreadable"
    if not isinstance(meta.get("edit"), int):
        return None, "unreadable"
    return meta, "readable"
