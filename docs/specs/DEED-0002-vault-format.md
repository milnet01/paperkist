# DEED-0002 — Define the vault format and build the vault core

**Status:** accepted (2026-09-27).
**Kind:** implement.
**Source:** ROADMAP DEED-0002 (broken out of `docs/design.md`; the format
`docs/decisions/ADR-0001-crypto-library.md` defers to "the vault-format
spec written for build step 1").
**Blocker for:** DEED-0003.  **Pairs with:** DEED-0004.

**Layman:** This is the locked drawer itself — how Paperkist stores your
files on disk so that only your password opens them, and so that every
future version can still read them.

## 1. Goal

A vault can be created in a folder with a password, reopened with that
password, given a document, and asked for it back byte-for-byte — on
Windows, macOS and Linux. The bytes on disk follow one fixed, versioned
format that every later release must read (S9), that reveals no document
content, name or date (S5), and that a folder copy fully backs up (S6).

## 2. Problem

1. There is no code yet (`src/paperkist/__init__.py` holds only a
   docstring). Build step 1 of `docs/brief.md` is this.
2. `docs/design.md` and ADR-0001 fix the direction — PyNaCl, a random
   vault key wrapped by an Argon2id key, secretstream for content,
   XChaCha20-Poly1305 for small files, associated data binding role,
   format number and document id — and leave the byte layout to this
   spec. Once one vault exists on a stranger's disk, every choice below
   is permanent.
3. The same password can reach the program as different bytes. Checked
   2026-09-27: `unicodedata.normalize("NFC", "café").encode() ==
   unicodedata.normalize("NFD", "café").encode()` is `False`. A vault
   made where the keyboard produces one form would refuse the right
   password where it produces the other.

## 3. Scope decisions (agreed with the user)

- Python and PyNaCl — owner, 2026-09-27 (ADR-0002, ADR-0001).
- File sizes and modification times in the vault folder stay visible —
  owner, 2026-09-27 (`docs/design.md`, What it rules out).
- Every other choice below follows from §2 and from `docs/design.md`.

## 4. Design

### 4.1 Folder layout

```
<vault>/
  vault.deedbox          header (JSON, UTF-8)
  objects/
    <id>.c               a document's content
    <id>.m               a document's metadata
  index                  the index (container defined here, contents: DEED-0003)
  index.prev             the index's previous copy (DEED-0003)
```

- `<id>` is 32 lowercase hex characters from 16 random bytes
  (`secrets.token_hex(16)`). It carries no information about the document.
- `Vault.create` refuses a folder that already holds anything.
- `Vault.open` on a folder without `vault.deedbox` raises `NotAVault`.

### 4.2 The header, and the key record

`vault.deedbox` is the only plaintext file. It and the associated-data
label (§ 4.4) keep the app's old name, Deedbox: existing vaults need them
(DEED-0023). `vault` writes and reads the
outer object; the `key_record` value is `crypto`'s, and `vault` stores it
without reading it (`docs/design.md`, rule 2).

```json
{
  "format": 1,
  "key_record": "<base64 of the key record's bytes>"
}
```

Every base64 value in the header and the key record uses the standard
alphabet with padding (RFC 4648 § 4).

The key record, as `crypto` produces it, is UTF-8 JSON:

```json
{
  "version": 1,
  "kdf": "argon2id13",
  "opslimit": 3,
  "memlimit": 268435456,
  "parallelism": 1,
  "salt": "<base64, 16 bytes>",
  "wrap": "xchacha20poly1305-ietf",
  "nonce": "<base64, 24 bytes>",
  "wrapped_key": "<base64, 32-byte vault key + 16-byte tag>"
}
```

- **Password bytes** are `unicodedata.normalize("NFC", password)` encoded
  as UTF-8, on every system, before any key derivation.
- **Settings for a new vault** are libsodium's `MODERATE` pair
  (`nacl.pwhash.argon2id.OPSLIMIT_MODERATE` = 3,
  `MEMLIMIT_MODERATE` = 268435456 bytes). Measured 2026-09-27 on the
  development machine: 0.27 s per derivation. `parallelism` is recorded
  as 1 because libsodium fixes it there; a replacement library needs the
  value, not the assumption.
- **Opening reads the settings from the record**, never from constants,
  so raising them for new vaults never breaks an old one.
- **`unlock` validates the record before deriving anything**, because the
  folder is untrusted: `version` above 1 raises `VaultTooNew`; any other
  `version`, `kdf` or `wrap` value, `parallelism` other than 1, `opslimit`
  outside 1–20, `memlimit` outside 8192 bytes–4 GiB, or a salt, nonce or
  wrapped key of the wrong length raises `VaultCorrupt`. So a tampered
  record cannot make an open hang or reach libsodium with values it
  rejects, and a failed derivation of a valid record is a memory failure.
- **The vault key** is 32 random bytes. The Argon2id output (32 bytes)
  wraps it with single-message XChaCha20-Poly1305 under the associated
  data for role `key` (§4.4).

### 4.3 Encrypted files

Every encrypted file starts with the same 6-byte prefix:

```
magic   4 bytes   b"DBXC" content · b"DBXM" metadata · b"DBXI" index
format  2 bytes   unsigned, big-endian; 1 for everything this spec defines
```

**Content (`<id>.c`)** — secretstream:

```
prefix            6 bytes
stream header    24 bytes   crypto_secretstream_xchacha20poly1305 header
pieces           each 65536 plaintext bytes → 65553 ciphertext bytes;
                 the last piece is always shorter than 65536 plaintext
                 bytes and tagged TAG_FINAL; it is empty when the length
                 is a multiple of 65536, zero included
```

Every piece is pushed with the file's associated data (§4.4). A reader
rejects the file unless the last piece it reads is tagged `TAG_FINAL`,
no piece before it is, and the file ends exactly there. Secretstream
does not flag a cut-off file by itself (ADR-0001); this check is ours.

A reader checks the prefix before decrypting: the wrong magic raises
`VaultCorrupt`, and a format number above 1 raises `VaultTooNew`.

**Metadata (`<id>.m`) and index (`index`)** — one sealed message:

```
prefix            6 bytes
nonce            24 bytes   random
ciphertext        rest      XChaCha20-Poly1305-IETF over UTF-8 JSON
```

### 4.4 Associated data

```
b"deedbox\x00" + role + b"\x00" + str(format) + b"\x00" + doc_id
```

`role` is ASCII `content`, `metadata`, `index` or `key`. `format` is the
file's format number in ASCII decimal; for `key` it is the key record's
`version` field, read from the record and independent of the header's
`format`, so a header bump never breaks the unwrap. `doc_id` is the
document's hex id for `content` and `metadata`, and empty for `index`
and `key`. No field can contain a NUL byte, so the encoding is
unambiguous. A file moved to another id, given another role, or
relabelled with another format number fails to decrypt (ADR-0001,
Binding).

### 4.5 Metadata written by this item

A metadata file's JSON is an object. This item writes these keys; later
items add keys, and readers keep keys they do not know:

```json
{
  "id": "<the document id>",
  "filename": "<original file name, as given>",
  "type": "<MIME type, e.g. application/pdf>",
  "size": 12345,
  "added": "2026-09-27",
  "edit": 1,
  "extraction": "not yet run"
}
```

### 4.6 Code, and what other parts call

`src/paperkist/errors.py`:

```python
class PaperkistError(Exception): ...
class NotAVault(PaperkistError): ...      # no vault.deedbox in the folder
class VaultExists(PaperkistError): ...    # create() on a non-empty folder
class WrongPassword(PaperkistError): ...  # the key record will not unwrap
class VaultCorrupt(PaperkistError): ...   # any other decrypt or parse failure
class NotEnoughMemory(PaperkistError): ... # Argon2id could not allocate
class VaultTooNew(PaperkistError): ...    # a format number above what we read
class DocumentMissing(PaperkistError): ...
```

`src/paperkist/crypto.py` (the only importer of `nacl`):

```python
def new_key_record(password: str, *, opslimit: int | None = None,
                   memlimit: int | None = None) -> tuple[bytes, bytes]:
    """(key record bytes, vault key). None means MODERATE."""
def unlock(key_record: bytes, password: str) -> bytes:  # the vault key
def seal(key: bytes, plaintext: bytes, ad: bytes) -> bytes:  # nonce + ciphertext
def unseal(key: bytes, blob: bytes, ad: bytes) -> bytes:
def encrypt_stream(key: bytes, src: BinaryIO, dst: BinaryIO, ad: bytes) -> None:
def decrypt_stream(key: bytes, src: BinaryIO, dst: BinaryIO, ad: bytes) -> None:
```

`unlock` raises `WrongPassword` only when the wrapped key fails to
authenticate, and `VaultCorrupt` when the record will not parse. A failed
Argon2id derivation raises `nacl.exceptions.RuntimeError` (checked
2026-09-27 by capping the process's memory below the derivation's), and
`crypto` turns it into `NotEnoughMemory` — never `WrongPassword`. Every
other failure is `VaultCorrupt`; no `nacl` exception leaves `crypto`.

`src/paperkist/vault/vault.py` — the `Vault` object other parts use:

```python
class Vault:
    @classmethod
    def create(cls, folder: Path, password: str, *,
               opslimit: int | None = None,
               memlimit: int | None = None) -> "Vault": ...
    @classmethod
    def open(cls, folder: Path, password: str) -> "Vault": ...
    def add(self, source: Path, mime_type: str) -> str: ...  # the new id
    def read(self, doc_id: str) -> bytes: ...
    def metadata(self, doc_id: str) -> dict: ...
    def close(self) -> None: ...
```

`src/paperkist/vault/layout.py` owns the paths and the file prefixes;
`vault/documents.py` owns reading and writing `<id>.c` and `<id>.m`;
`vault/atomic.py` owns write-new, flush, replace (`os.replace`). This
item creates it with two entry points, `write_bytes(target, data)` and a
`write_stream(target)` context manager that yields a binary file and
replaces the target only on a clean exit. It writes `<target>.tmp` in the
target's own directory, so the replace never crosses a file system. A
leftover `*.tmp` is an interrupted write; DEED-0003's recovery deletes
it. DEED-0003 tests `atomic.py` on all three systems and saves the index
through it.

`create` passes `opslimit` and `memlimit` to `new_key_record`; only
tests pass them, to keep derivation fast. `open` takes none — it reads
the settings from the record (§4.2).

### 4.7 Adding and reading

- `add` streams the source file through `encrypt_stream` into
  `objects/<id>.c`, then seals and writes `objects/<id>.m`, each through
  `atomic.py`. If writing the `.m` fails, `add` deletes the `.c` before
  re-raising. This item writes no `index`; DEED-0003 inserts the index
  write between the two, giving `docs/design.md`'s order (content, then
  index, then metadata file). No decrypted byte is written anywhere.
- `read` decrypts `<id>.c` into memory and returns it. A missing file
  raises `DocumentMissing`; any failed piece, missing final tag or
  trailing byte raises `VaultCorrupt`, never a shortened result.
- `close` drops the vault key. The object is unusable afterwards.

## 5. Invariants

Tests below run against code this item creates, so none can be run yet.
Each names the rule its fixture isolates.

- **INV-1** — A document added to a vault reads back byte-identical after
  the vault is closed and reopened with the same password.
  *Test:* `tests/test_vault.py::test_round_trip` — sizes 0, 1, 65535,
  65536, 65537 and 200000 bytes (isolates the piece boundary and the
  empty final piece).
  *Breaks when:* the reader drops or duplicates a piece, or mishandles an
  empty final piece.

- **INV-2** — Opening with any other password raises `WrongPassword` and
  writes nothing to the vault folder.
  *Test:* `tests/test_vault.py::test_wrong_password` — compares the
  folder's file list and modification times before and after.
  *Breaks when:* a wrong key is not detected, or `open` writes before
  unlocking.

- **INV-3** — Nothing in the vault folder contains a document's content,
  file name or date in readable form, and no name in it is derived from
  the document (S5).
  *Test:* `tests/test_vault.py::test_nothing_readable` — adds a file
  named `marker-FILENAME.pdf` whose content is `marker-CONTENT`, then
  scans every byte of every file in the folder for both markers and for
  today's ISO date, and checks every name under `objects/` against
  `^[0-9a-f]{32}\.(c|m)$`.
  *Breaks when:* any part of a document or its metadata is written
  unencrypted, or a file name reuses the original.

- **INV-4** — A content file cut short at any point, or with bytes
  appended, raises `VaultCorrupt` on `read`, never returns data.
  *Test:* `tests/test_vault.py::test_truncation` — a 200000-byte
  document; truncate after the stream header, after the first piece
  exactly, one byte into the final piece, and append one byte. The
  second case isolates the final-tag check: every remaining piece
  decrypts cleanly, so only the missing `TAG_FINAL` can reject it.
  *Breaks when:* the reader stops at end of file without requiring
  `TAG_FINAL`.

- **INV-5** — A file moved to another document's id, or given another
  role, fails with `VaultCorrupt`.
  *Test:* `tests/test_vault.py::test_binding` — swap the `.c` files of
  two documents: same magic, same format, valid ciphertext under the right
  key, so only the id in the associated data can reject them.
  `tests/test_crypto.py::test_role_binding` — `seal` under the `metadata`
  associated data and `unseal` under the `content` associated data, same
  id and format, so the two differ only in the role. A role swap between
  whole files is rejected by the magic first, so the role is tested where
  nothing else can reject it.
  *Breaks when:* the associated data omits the id or the role.

- **INV-6** — A password entered in decomposed form (NFD) opens a vault
  created with the composed form (NFC), and the reverse.
  *Test:* `tests/test_crypto.py::test_password_normalisation` —
  `"café"` in both forms.
  *Breaks when:* the password is encoded without NFC normalisation.

- **INV-7** — Opening uses the Argon2id settings stored in the key
  record, not the current defaults.
  *Test:* `tests/test_crypto.py::test_settings_come_from_record` — a
  record made with `OPSLIMIT_MIN`/`MEMLIMIT_MIN` unlocks; tampering its
  stored `opslimit` to 2 makes it fail with `WrongPassword` (isolates
  that the stored value, not a constant, reaches the derivation).
  *Breaks when:* `unlock` derives with constants.

- **INV-8** — A header, or any encrypted file, whose format number is
  above 1 raises `VaultTooNew` and changes nothing on disk.
  *Test:* `tests/test_vault.py::test_too_new` — a header with `format`
  2, a key record whose `version` is 2, and a `.c` whose prefix format
  is 2 (its ciphertext is otherwise valid, so only the prefix check can
  raise `VaultTooNew` rather than `VaultCorrupt`). Each compares the
  folder's file list, modification times and bytes before and after, as
  INV-2 does.
  *Breaks when:* a newer vault is opened, guessed at, or rewritten.

- **INV-9** — Only `crypto` imports `nacl` (`docs/design.md`, rule 2),
  and no module imports `tempfile` (rule 4).
  *Test:* `uv run --locked --group dev pytest -q tests/test_dependency_rules.py`
  → `12 passed`.
  *Breaks when:* any other module imports `nacl` or `tempfile`.

INV-9 is the one clause runnable today; it passed as written on
2026-09-27, and adding `import nacl.secret` to a scratch `vault/vault.py`
fails it (the rule-2 breach case in that file).

**Trust boundary.** The vault folder is untrusted input: anyone with the
folder can change its bytes. INV-4, INV-5 and INV-8 are the defences, and
`crypto`'s rule of raising only Paperkist errors keeps a malformed file
from surfacing as an unhandled library exception.

## 6. Failure modes

- **Wrong password** → `WrongPassword`; nothing written (INV-2).
- **Header not JSON, a field missing, or base64 invalid** → `VaultCorrupt`.
- **Header from a newer release** → `VaultTooNew` (INV-8).
- **A damaged, cut-off or swapped document file** → `VaultCorrupt` for
  that document only; other documents still read.
- **Disk full or permission denied while adding** → the `OSError`
  propagates; the half-written temporary file is removed, and a `.c`
  whose `.m` failed is deleted, so no document half-exists. Recovery of
  an add interrupted by a crash is DEED-0003's.
- **Argon2id cannot allocate 256 MiB** → `NotEnoughMemory` on create or
  open, never `WrongPassword`.

## 7. Tests

| Test | Locks |
|---|---|
| `tests/test_vault.py::test_round_trip` | INV-1 |
| `tests/test_vault.py::test_wrong_password` | INV-2 |
| `tests/test_vault.py::test_nothing_readable` | INV-3 |
| `tests/test_vault.py::test_truncation` | INV-4 |
| `tests/test_vault.py::test_binding` | INV-5 (id) |
| `tests/test_crypto.py::test_role_binding` | INV-5 (role) |
| `tests/test_crypto.py::test_password_normalisation` | INV-6 |
| `tests/test_crypto.py::test_settings_come_from_record` | INV-7 |
| `tests/test_vault.py::test_too_new` | INV-8 |
| `tests/test_dependency_rules.py` | INV-9 |

All tests use `OPSLIMIT_MIN`/`MEMLIMIT_MIN`. Each must be seen failing once
against a deliberately broken implementation before it counts. CI runs
them on Windows, macOS and Linux.

## 8. Alternatives considered (and rejected)

- **Length-prefixed pieces instead of a fixed piece size** — rejected:
  a fixed size needs no framing field to parse or validate, and the
  final-tag rule already marks the end.
- **Binary header instead of JSON** — rejected: the header holds no
  secret, JSON is readable when diagnosing a user's vault, and a format
  number plus named fields migrate more simply than offsets.
- **Deriving document keys straight from the password** — rejected in
  ADR-0001 (a password change would re-encrypt every document).
- **`INTERACTIVE` Argon2id settings (64 MiB)** — rejected: `MODERATE`
  measured 0.27 s here, which is acceptable once per unlock, and gives
  four times the memory cost to an attacker.
- **Using the vault's id as the index and key's associated-data id** —
  rejected: different vaults already use different keys, so it binds
  nothing extra and adds a field.

## 9. Out of scope

- The index's contents, atomic saving tested on three systems, and
  recovery on open — tracked by DEED-0003.
- Format versions beyond 1 and the migration framework — tracked by
  DEED-0004.
- Changing the password or raising the Argon2id settings on an existing
  vault — deferred; not yet queued.

## 10. What checks this

| Rule | What catches a breach |
|------|----------------------|
| INV-1 | `tests/test_vault.py::test_round_trip` |
| INV-2 | `tests/test_vault.py::test_wrong_password` |
| INV-3 | `tests/test_vault.py::test_nothing_readable` |
| INV-4 | `tests/test_vault.py::test_truncation` |
| INV-5 | `tests/test_vault.py::test_binding`, `tests/test_crypto.py::test_role_binding` |
| INV-6 | `tests/test_crypto.py::test_password_normalisation` |
| INV-7 | `tests/test_crypto.py::test_settings_come_from_record` |
| INV-8 | `tests/test_vault.py::test_too_new` |
| INV-9 | `tests/test_dependency_rules.py` |
| The byte layout in §4.1–§4.4 | **`Partial:`** INV-1, INV-4 and INV-5 exercise it; nothing checks it against an independent reader — DEED-0004's checked-in sample vault is the first |
| No decrypted temporary file (rule 4) | **`Partial:`** INV-9 forbids `tempfile`; nothing stops a hand-made temporary path |
| Keys dropped on `close` | **nothing** — Python cannot prove memory was cleared (`docs/design.md`, What it rules out) |

## 11. Cross-doc impact

None beyond the roadmap item. `docs/design.md` and ADR-0001 already point
here for the byte layout.

## 12. Cold-eyes loop log

Rows live in `../reviews/DEED-0002-vault-format-loop-log.md`.

## 13. Resource cost

- Argon2id holds 256 MiB for about a quarter of a second per create or
  open.
- `add` streams: memory is one 64 KiB piece. `read` holds the whole
  document in memory, as the in-window viewer needs it there anyway.
- New dependency: `PyNaCl` 1.6.2 (ADR-0001), pinned in
  `pyproject.toml`.
