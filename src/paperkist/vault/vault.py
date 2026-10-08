"""The `Vault` object: the only way other parts reach a vault's files.

docs/specs/DEED-0002-vault-format.md § 4.2, § 4.6 and § 4.7;
docs/specs/DEED-0003-index-and-recovery.md § 4.5 to § 4.7;
docs/specs/DEED-0004-format-migration.md § 4.3.
"""

from __future__ import annotations

import base64
import binascii
import copy
import datetime
import json
from pathlib import Path

from paperkist import crypto
from paperkist.errors import (
    DocumentMissing,
    NotAVault,
    VaultCorrupt,
    VaultExists,
    VaultTooNew,
)
from paperkist.vault import atomic, documents, index, layout, migrate
from paperkist.vault.lock import VaultLock

LOCK = "lock"


class Vault:
    """An open vault. Holds the vault key and the lock until `close`."""

    def __init__(
        self,
        folder: Path,
        key: bytes,
        lock: VaultLock,
        entries: list[dict],
        *,
        keep_previous: bool,
        damaged: list[str] | None = None,
    ) -> None:
        self._folder = folder
        self._key: bytes | None = key
        self._lock = lock
        self._entries = entries
        self._keep_previous = keep_previous
        self._damaged = damaged or []

    @classmethod
    def create(
        cls,
        folder: Path,
        password: str,
        *,
        opslimit: int | None = None,
        memlimit: int | None = None,
    ) -> Vault:
        """A new, empty vault in `folder`, which must be empty or absent.

        `opslimit` and `memlimit` are for tests; every other caller omits them.
        """
        folder = Path(folder)
        if folder.exists() and any(folder.iterdir()):
            raise VaultExists(str(folder))
        record, key = crypto.new_key_record(
            password, opslimit=opslimit, memlimit=memlimit
        )
        (folder / layout.OBJECTS).mkdir(parents=True, exist_ok=True)
        lock = VaultLock(folder / LOCK)
        try:
            header = {
                "format": layout.VAULT_FORMAT,
                "key_record": base64.b64encode(record).decode("ascii"),
            }
            atomic.write_bytes(
                folder / layout.HEADER, json.dumps(header).encode("utf-8")
            )
            index.save(folder, key, [], keep_previous=False)
        except BaseException:
            lock.release()
            raise
        return cls(folder, key, lock, [], keep_previous=True)

    @classmethod
    def open(cls, folder: Path, password: str) -> Vault:
        """The vault in `folder`, unlocked and recovered (DEED-0003 § 4.6).

        A wrong password or a newer format is refused before anything is
        written.
        """
        folder = Path(folder)
        record, header_format = cls._read_header(folder)
        key = crypto.unlock(record, password)
        index.check_prefixes(folder)
        lock = VaultLock(folder / LOCK)
        try:
            migrate.run(folder, key, header_format)
            stale = index.stale_content(folder)
            cleaned = index.delete_leftovers(folder)
            entries, source = index.load(folder, key)
            entries, changed, damaged = index.reconcile(folder, key, entries)
            # Reconcile may have deleted a stale content file as an unfinished add.
            damaged += [
                doc_id
                for doc_id in stale
                if doc_id not in damaged
                and layout.content_path(folder, doc_id).exists()
            ]
            keep_previous = source == index.INDEX
            if source != index.INDEX or cleaned or changed:
                index.save(folder, key, entries, keep_previous=keep_previous)
                keep_previous = True
        except BaseException:
            lock.release()
            raise
        return cls(
            folder, key, lock, entries, keep_previous=keep_previous, damaged=damaged
        )

    def documents(self) -> list[dict]:
        """Every document's metadata, from the index. A copy."""
        self._require_key()
        return copy.deepcopy(self._entries)

    def damaged(self) -> list[str]:
        """Ids reconcile found damaged when this vault was opened."""
        return list(self._damaged)

    def add(self, source: Path, mime_type: str) -> str:
        """Encrypt the file at `source` into the vault. Returns its new id.

        Order: content, index, metadata file (DEED-0003 § 4.5). Once the index
        is saved the document exists, even if the metadata write then fails.
        """
        key = self._require_key()
        source = Path(source)
        doc_id = layout.new_id()
        content = layout.content_path(self._folder, doc_id)
        entry = {
            "id": doc_id,
            "filename": source.name,
            "type": mime_type,
            "size": source.stat().st_size,
            "added": datetime.date.today().isoformat(),
            "edit": 1,
            "extraction": "not yet run",
        }
        try:
            with source.open("rb") as src:
                documents.write_content(content, key, src, doc_id)
            self._save([*self._entries, entry])
        except BaseException:
            content.unlink(missing_ok=True)
            raise
        documents.write_metadata(
            layout.metadata_path(self._folder, doc_id), key, entry, doc_id
        )
        return doc_id

    def update(self, doc_id: str, changes: dict) -> None:
        """Merge `changes` into a document's metadata: index, then file."""
        key = self._require_key()
        if "id" in changes or "edit" in changes:
            raise ValueError("id and edit cannot be changed")
        entry = self._entry(doc_id)
        updated = {**entry, **changes, "edit": entry["edit"] + 1}
        self._save([updated if e is entry else e for e in self._entries])
        documents.write_metadata(
            layout.metadata_path(self._folder, doc_id), key, updated, doc_id
        )

    def remove(self, doc_id: str) -> None:
        """Metadata file, then index, then content (DEED-0003 § 4.5)."""
        self._require_key()
        entry = self._entry(doc_id)
        atomic.delete(layout.metadata_path(self._folder, doc_id))
        self._save([e for e in self._entries if e is not entry])
        atomic.delete(layout.content_path(self._folder, doc_id))

    def read(self, doc_id: str) -> bytes:
        """The document's original bytes, decrypted in memory."""
        key = self._require_key()
        self._entry(doc_id)
        return documents.read_content(
            layout.content_path(self._folder, doc_id), key, doc_id
        )

    def metadata(self, doc_id: str) -> dict:
        self._require_key()
        return copy.deepcopy(self._entry(doc_id))

    def close(self) -> None:
        """Drop the vault key and the lock. The object cannot be used afterwards."""
        self._key = None
        self._lock.release()

    def _save(self, entries: list[dict]) -> None:
        index.save(
            self._folder,
            self._require_key(),
            entries,
            keep_previous=self._keep_previous,
        )
        self._entries = entries
        self._keep_previous = True

    def _entry(self, doc_id: str) -> dict:
        # An id is also a file name, so only a listed one is ever used.
        for entry in self._entries:
            if entry["id"] == doc_id:
                return entry
        raise DocumentMissing(doc_id)

    def _require_key(self) -> bytes:
        if self._key is None:
            raise ValueError("the vault is closed")
        return self._key

    @staticmethod
    def _read_header(folder: Path) -> tuple[bytes, int]:
        """The key record and the header's format, once it is one this release reads."""
        try:
            raw = (folder / layout.HEADER).read_bytes()
        except FileNotFoundError as err:
            raise NotAVault(str(folder)) from err
        try:
            header = json.loads(raw.decode("utf-8"))
            fmt = header["format"]
            record = base64.b64decode(header["key_record"], validate=True)
        except (
            UnicodeDecodeError,
            ValueError,
            KeyError,
            TypeError,
            binascii.Error,
        ) as err:
            raise VaultCorrupt("the vault header is malformed") from err
        if not isinstance(fmt, int) or isinstance(fmt, bool):
            raise VaultCorrupt("the vault header's format is not a number")
        if fmt > layout.VAULT_FORMAT:
            raise VaultTooNew(f"vault format {fmt}")
        if fmt < 1:
            raise VaultCorrupt(f"vault format {fmt}")
        return record, fmt
