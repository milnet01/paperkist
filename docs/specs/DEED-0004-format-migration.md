# DEED-0004 — Format versions and the migration framework

**Status:** accepted (2026-09-28).
**Kind:** implement.
**Source:** ROADMAP DEED-0004 (`docs/design.md` § The parts, the
`migrate` row, and § What every part does the same way, *Format
version*).
**Blocked by:** DEED-0002.  **Pairs with:** DEED-0003.

**Layman:** This makes sure a vault made with an older version of
Paperkist always opens in a newer one, and that an upgrade cut off halfway
simply carries on next time.

## 1. Goal

A vault written by any earlier release opens in the current one (S9).
Opening upgrades it in place, one file at a time, rewriting only the
kinds of file whose format changed, so a cut-off upgrade resumes on the
next open. A sample vault from the first format is checked in, and every
later release must open it.

## 2. Problem

1. Every file carries a format number (DEED-0002 § 4.3), but one
   constant, `layout.FORMAT`, stands for all of them. Changing the
   index's layout would force every document to be re-encrypted, because
   a content file's associated data includes its format number
   (DEED-0002 § 4.4).
2. `Vault._read_header` refuses any header format other than the
   current one, so today an older vault cannot open at all.
3. `Vault.open` has an empty step 2 (DEED-0003 § 4.6: *"Migrate.
   DEED-0004's step"*).
4. Nothing proves a later release still reads what this one wrote. A
   reader change passes every test that builds its vault fresh.

## 3. Scope decisions (agreed with the user)

- **Each kind of file has its own format number** (owner, 2026-09-28).
  A change to one kind rewrites only files of that kind; the rest are
  left byte for byte. Rejected: one number for the whole vault, where
  any change re-encrypts every document.

## 4. Design

### 4.1 Format numbers

`src/paperkist/vault/layout.py` replaces `FORMAT` with:

```python
VAULT_FORMAT = 1                       # the header's "format"
FILE_FORMAT = {"content": 1, "metadata": 1, "index": 1}
```

- A file's prefix carries its **kind's** number: `content` for `.c`,
  `metadata` for `.m`, `index` for `index` and `index.prev`. Writers use
  `FILE_FORMAT[kind]`, in the prefix and in the associated data.
- `VAULT_FORMAT` rises by one whenever any entry of `FILE_FORMAT` does,
  or the header's own shape changes. It records that every file in the
  vault has been brought to the numbers of that release.
- The header's `format` and `key_record` fields keep their names and
  meaning in every format, so any release can read an older header far
  enough to unlock it and see how old it is.
- The key record keeps its own `version` (DEED-0002 § 4.2); nothing here
  touches it.

Each check reads the number for the file's own kind:

| Found | Result |
|---|---|
| above the current number | `VaultTooNew` (step 0 at open; a reader too) |
| the current number | read normally |
| below the current number, before step 2 has run | left for step 2 |
| below the current number, after step 2 | `VaultCorrupt` — a file step 2 could not upgrade |
| below 1 | `VaultCorrupt` |

Readers after step 2 read only the current number of each kind; no
reader keeps an older layout. `migrate` is the only code that reads an
older file.

`_read_header` accepts a header `format` from 1 to `VAULT_FORMAT` and
returns it with the key record; above raises `VaultTooNew`, below 1 or
not a number raises `VaultCorrupt`.

### 4.2 Steps

`src/paperkist/vault/migrate.py` holds one registry:

```python
Step = Callable[[Path, BinaryIO, bytes, str], None]
STEPS: dict[tuple[str, int], Step] = {}
```

- `STEPS[(kind, n)]` turns a file of that kind at format `n` into one at
  `n + 1`. It is called with the old file's path, an output stream, the
  vault key and the document id (empty for `index`), and writes the
  whole new file, prefix included, to the stream.
- A step changes how a file is stored, never what it holds: the same
  document bytes, the same metadata object (its `edit` included), the
  same index entries.
- A step that cannot read the old file raises `VaultCorrupt`.
- The header is kind `header`, keyed by `VAULT_FORMAT`: `STEPS[("header",
  n)]` takes the header object and returns the next one. Its `Step`
  signature differs and is declared beside the registry. Most bumps
  change no header field, so a missing header step leaves the object as
  it is.
- A file at a number from 1 up to below its kind's, with no step for
  that number, is a release that raised a number without shipping the
  step: `run` raises `KeyError` and the open fails.
- No step exists in this item; there is only format 1.

### 4.3 Opening, step 2

`Vault.open` passes the header's format to `migrate.run(folder, key,
header_format)` at DEED-0003 § 4.6 step 2 — after the lock, before
leftovers are deleted.

1. If `header_format` equals `VAULT_FORMAT`, return. This is every open
   of an up-to-date vault.
2. For each `.c`, `.m`, `index.prev` and `index` whose prefix number is
   below its kind's current one: apply `STEPS[(kind, n)]` for each `n`
   from the file's number up, each through `atomic.write_stream` onto
   the same path. Each application is its own atomic replace, so the
   file on disk is always at some whole format.
3. A step raising `VaultCorrupt`, or a prefix number below 1, leaves
   that file as it is and moves to the next file. Any other exception
   propagates, and the open fails.
4. Last, apply the header steps and write the header with `format` set
   to `VAULT_FORMAT` through `atomic.write_bytes`.

A file with the wrong magic is skipped, as DEED-0003 § 4.6 step 0 skips
it. `*.tmp` files are not walked; step 3 deletes them next.

**Why it resumes.** The header is written only after every file has
been tried, so a run cut off anywhere leaves the header old, and the
next open runs step 2 again. A file already upgraded now carries the
current number and is skipped.

**What a skipped file becomes.** A file left at an old number is
unreadable to the rest of the open (§ 4.1), and DEED-0003 § 4.6 handles
it as it handles any unreadable file: an index copy is passed over for
the other, and a metadata file is rewritten from the index where the
index lists it, or its id goes to `damaged()` where it does not. A
content file left behind cannot be recovered from anything, and the
header no longer sends later opens back through step 2. So every open,
right after step 2, reads each `.c` prefix and collects those whose
number is below its kind's or below 1 (`index.stale_content`), and
`Vault.open` adds those ids to `damaged()`. Reading one raises
`VaultCorrupt`. Collecting at step 0 instead would list every content
file an upgrade in the same open is about to bring up.

### 4.4 The sample vault

`tests/fixtures/vault-format-1/` holds a vault this release wrote, with
the password `deedbox-sample-1` and the smallest Argon2id settings the
key record allows (`opslimit` 1, `memlimit` 8192), so opening it is fast.
It holds:

| Document | Content | Why |
|---|---|---|
| `empty.txt` | 0 bytes | the empty final piece |
| `boundary.bin` | exactly 65536 bytes | a full piece then an empty final one |
| `scan.pdf` | 150000 bytes | several pieces |
| `Überweisung Mai.txt` | short UTF-8 text | a non-ASCII name |
| `edited.txt` | short text, then one `update` | `edit` 2 |

Content bytes are generated from each filename by
`tests/fixtures/sample_vault.py::expected_content`, so the expected
bytes need no second copy. That module also holds the generator, which
refuses to write into an existing folder.
`tests/fixtures/vault-format-1.sha256`, beside the folder, lists the hash
of every file in it. The generator deletes `lock` after closing the
vault. `.gitattributes` marks the folder and the hash list `-text`, so
a Windows checkout does not rewrite `vault.deedbox`'s line endings.

The fixture is never regenerated. A later release that changes a format
keeps this folder and adds a step.

## 5. Invariants

Tests below run against code this item creates. Each names the rule its
fixture isolates.

- **INV-1** — The sample vault opens in this release, lists its five
  documents with the metadata recorded in `sample_vault.py`, and reads
  each one back byte for byte.
  *Test:* `tests/test_migrate.py::test_sample_vault_opens` — copies the
  fixture to a temporary folder and opens the copy.
  *Breaks when:* a reader's layout changes without a step, or a format
  number rises without one.

- **INV-2** — The sample vault's files are the bytes first checked in.
  *Test:* `tests/test_migrate.py::test_sample_vault_unchanged` — hashes
  every file under the fixture folder and compares with
  `vault-format-1.sha256`, both ways, so an added or missing file fails
  too.
  *Breaks when:* the fixture is regenerated or edited.

- **INV-3** — Opening a vault whose header is behind brings every file
  of a changed kind, and the header, to the current numbers; every
  document reads as before.
  *Test:* `tests/test_migrate.py::test_migrates_to_current` — patches
  `FILE_FORMAT["index"]` and `VAULT_FORMAT` to 2 and registers an index
  step 1→2 that re-seals under format 2 and records each path it is
  called with, then opens a format-1 vault holding documents, so it has
  an `index.prev`. The step was called for
  exactly `index` and `index.prev`; afterwards both and the header carry
  2, and `documents()` and every `read` match the values before. The
  record is what isolates step 2: skipping `index` alone still ends with
  a format-2 `index`, because the open falls back to `index.prev` and
  saves a fresh one.
  *Breaks when:* a file of the changed kind is skipped, or the header
  is not written.

- **INV-4** — A file whose kind's number did not change is not
  rewritten.
  *Test:* part of `test_migrates_to_current` — every `.c` and `.m` is
  byte-identical before and after that open.
  *Breaks when:* migration rewrites every file (one number for the
  vault, the rejected design).

- **INV-5** — A migration cut off part-way resumes on the next open and
  ends with every document intact.
  *Test:* `tests/test_migrate.py::test_interrupted_migration_resumes` —
  with `metadata` and `VAULT_FORMAT` raised to 2, the registered metadata
  step raises `OSError` on its second call. The open fails; the header
  is still 1, and each `.m` is at 1 or 2. A second open with the step
  healthy succeeds, and every document reads as before. The step
  refuses a file already at 2, so re-migrating an upgraded file fails
  the test.
  *Breaks when:* the header is written before the files, or an
  upgraded file is upgraded again.

- **INV-6** — A file a step cannot read does not stop the upgrade: the
  open succeeds, and the file is then handled as any unreadable file.
  *Test:* `tests/test_migrate.py::test_unreadable_file_survives` — with
  `content`, `metadata` and `VAULT_FORMAT` raised to 2, three documents
  each get one byte flipped: a listed document's `.m`; the `.m` of a
  document whose `.c` and `.m` are written directly, so the index does
  not list it; and a third, listed document's `.c`. The open succeeds
  and the header is 2. The first document's metadata file is rewritten
  from the index at format 2, its metadata matches the index, and its
  id is not in `damaged()`. The second's `.m` is byte-identical and its
  id is in `damaged()`. The third's id is in `damaged()` and its `read`
  raises `VaultCorrupt`. Every other document reads. A second open,
  with nothing left to upgrade, still lists the second and third ids.
  *Breaks when:* one bad file aborts the upgrade, or a step's failure
  deletes the file.

- **INV-7** — A file above its own kind's number is refused, whatever
  the other kinds' numbers are.
  *Test:* `tests/test_migrate.py::test_newer_kind_refused` — with
  `FILE_FORMAT["index"]` and `VAULT_FORMAT` patched to 2, a vault
  created under the patch opens, its `index` at 2. Then one `.m`'s
  prefix is set to 2, a leftover `.tmp` is placed in the vault folder,
  and the open raises `VaultTooNew` with the folder unchanged. A check
  against the metadata number refuses the `index`. One against the
  highest number of any kind passes the `.m` at step 0; the metadata
  reader then refuses it, but only after step 3 has deleted the `.tmp`,
  and that is what the unchanged folder catches.
  *Breaks when:* a check compares against another kind's number.

## 6. Failure modes

- **Disk full or a write error mid-upgrade** → the error propagates and
  the open fails; the header is still old, so the next open resumes.
- **A power cut mid-upgrade** → each file is whole at one format
  (atomic replace); the next open resumes.
- **A file a step cannot decrypt** → left in place, then handled as
  § 4.3 says.
- **A vault from a newer release** → refused before anything is written
  (DEED-0003 § 4.6 step 0, and `_read_header`).
- **Older Paperkist opening an upgraded vault** → refused as too new. A
  downgrade path is not offered.

## 7. Tests

| Test | Locks |
|---|---|
| `tests/test_migrate.py::test_sample_vault_opens` | INV-1 |
| `tests/test_migrate.py::test_sample_vault_unchanged` | INV-2 |
| `tests/test_migrate.py::test_migrates_to_current` | INV-3, INV-4 |
| `tests/test_migrate.py::test_interrupted_migration_resumes` | INV-5 |
| `tests/test_migrate.py::test_unreadable_file_survives` | INV-6 |
| `tests/test_migrate.py::test_newer_kind_refused` | INV-7 |

The tests from INV-3 on patch `layout.FILE_FORMAT`, `layout.VAULT_FORMAT`
and `migrate.STEPS`, so every reader and writer looks those up when
called, never copies them at import. Each test must be seen failing once
against a deliberately broken implementation before it counts. The
existing refusal tests (`tests/test_vault.py::test_too_new`,
`tests/test_recovery.py::test_refusals_write_nothing`) keep passing.

## 8. Alternatives considered (and rejected)

- **One format number for the whole vault** — rejected by the owner
  (§ 3): any change would re-encrypt every document.
- **Upgrade a copy of the vault, then swap folders** — rejected: it
  doubles the disk space, and swapping a folder is not one atomic step
  on every system. Per-file atomic replace already makes each step safe.
- **Upgrade lazily, when a file is next read** — rejected: every reader
  would keep every old layout forever, and a vault could stay mixed
  indefinitely.
- **Record progress in a separate file** — rejected: each file's own
  prefix already says whether it is done.

## 9. Out of scope

- Any real format change — none exists yet.
- Changing the password or the Argon2id settings of an existing vault —
  DEED-0019.
- Opening an upgraded vault in an older release.

## 10. What checks this

| Rule | What catches a breach |
|------|----------------------|
| INV-1 | `tests/test_migrate.py::test_sample_vault_opens` |
| INV-2 | `tests/test_migrate.py::test_sample_vault_unchanged` |
| INV-3 | `tests/test_migrate.py::test_migrates_to_current` |
| INV-4 | `tests/test_migrate.py::test_migrates_to_current` |
| INV-5 | `tests/test_migrate.py::test_interrupted_migration_resumes` |
| INV-6 | `tests/test_migrate.py::test_unreadable_file_survives` |
| INV-7 | `tests/test_migrate.py::test_newer_kind_refused` |
| A step preserves what a file holds (§ 4.2) | **`Partial:`** INV-3 and INV-5 for the test steps; nothing for a future real step until its own test |
| Readers keep no older layout (§ 4.1) | **nothing** — checked by reading the readers |

## 11. Cross-doc impact

- DEED-0002 § 4.3 says a format number above 1 raises `VaultTooNew`;
  that now means above the file's kind's number. With every number at 1
  the behaviour is the same.
- DEED-0003 § 4.6 step 2 names this item; its text still holds. Its
  open gains one duty from § 4.3, right after step 2: it collects each
  `.c` below its kind's number for `damaged()`. DEED-0003 § 4.6 is
  amended to say so when this item is built.
- `docs/design.md` § Format version already states the order (files one
  at a time, header last); no change.

## 12. Cold-eyes loop log

Rows live in `../reviews/DEED-0004-format-migration-loop-log.md`.

## 13. Resource cost

An up-to-date vault costs step 2 one comparison. An upgrade reads and
writes each file of a changed kind once per step; a content step
streams, so its memory stays at one piece.
