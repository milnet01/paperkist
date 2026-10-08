# DEED-0003 — Keep an index, save safely, and recover on open

**Status:** accepted (2026-09-27).
**Kind:** implement.
**Source:** ROADMAP DEED-0003 (build step 2 of `docs/brief.md`; the
recovery rules in `docs/design.md` § Which copy wins and § Opening, in
order).
**Blocked by:** DEED-0002.  **Pairs with:** DEED-0004.

**Layman:** This makes sure a crash or a power cut never loses a filed
document, and that Paperkist always knows what is in the vault.

## 1. Goal

A vault keeps an encrypted index of its documents, saves every change so
that a crash at any moment leaves each file whole, and on opening repairs
whatever an interrupted save left behind — so the vault opens with every
document filed before the crash (S8). Only one copy of Paperkist can have a
vault open at a time.

## 2. Problem

1. DEED-0002 stores documents but nothing lists them: `Vault` in
   `src/paperkist/vault/vault.py` has `add`, `read`, `metadata` and `close`,
   and no way to enumerate what it holds.
2. `docs/design.md` fixes the recovery rules — the index is the truth,
   each metadata file its document's recovery copy, the write orders, and
   the open-time reconciliation — and leaves their mechanics to this spec.
3. `vault/atomic.py` (DEED-0002) writes a temporary file and replaces the
   target, but does not flush the folder after the replace. On Linux and
   macOS a power cut can then lose a replace the program already
   reported as done.
4. Nothing stops two copies of Paperkist opening one vault. Each would save
   its own index over the other's, and a filed document would drop out.

## 3. Scope decisions (agreed with the user)

None beyond `docs/design.md`'s, which the owner agreed on 2026-09-27.
Every choice below follows from §2 and that document.

## 4. Design

### 4.1 Files this item adds

```
<vault>/
  index              the index (DBXI container, DEED-0002 § 4.3)
  index.prev         the index as it was before the last save
  lock               empty; held with an OS lock while the vault is open
```

Both index files are sealed with the associated data for role `index`
(DEED-0002 § 4.4), so either can be decrypted as the other.

### 4.2 The index

The sealed JSON is:

```json
{"documents": [ <one metadata object per document> ]}
```

Each entry is the same object as that document's metadata file
(DEED-0002 § 4.5), including `edit`. The index is kept in memory while
the vault is open and read by `Vault.documents()`.

### 4.3 Saving the index

1. If `index` decrypted when this vault was opened, or has been saved
   since, copy its bytes to `index.prev` through `atomic.write_bytes`.
   Otherwise — after a fallback or a rebuild — skip this step, so a
   corrupt `index` is never copied over `index.prev`.
2. Write the new index to `index` through `atomic.write_bytes`.

A crash between the two leaves `index` and `index.prev` both holding the
old index, which is a valid state.

### 4.4 Atomic writes, completed

`atomic.write_stream` gains one step: after the replace, on Linux and
macOS it opens the target's directory and calls `os.fsync` on it, so on
Linux the replace survives a power cut. On macOS `fsync` does not empty
the drive's own cache; where `fcntl.F_FULLFSYNC` exists, `atomic.py`
uses it on the file before the replace, and the directory flush stays
best effort (unrunnable here, so not asserted). `atomic.py` also gains
`delete(path)`: unlink, then flush the directory the same way, so a
removed file stays removed after a power cut. Windows has no directory
handle to flush, and `os.replace` there is implemented as `MoveFileExW`
with `MOVEFILE_REPLACE_EXISTING` (CPython 3.13 `Modules/posixmodule.c`,
checked 2026-09-27); its behaviour is exercised by CI on Windows, not
asserted here. Windows refuses to replace or delete a file another handle
has open — a refused second opener's step 0, a virus scanner, an indexer.
So on Windows the replace and `delete` retry a `PermissionError` for up
to `atomic.IN_USE_WAIT` seconds, then raise it; elsewhere they raise at
once.

### 4.5 Write orders

The edit counter `edit` starts at 1 and rises by one with every change.

| Operation | Order |
|---|---|
| `add` | content file → index → metadata file |
| `update` | index → metadata file |
| `remove` | delete metadata file (`atomic.delete`) → index → delete content file |

This inserts the index step DEED-0002 § 4.7 left for this item. `add`
deletes its content file only if a failure comes before the index is
saved. Once the index is saved the document exists: if the metadata
write then fails, the content file stays and the next open rewrites the
metadata file from the index.

### 4.6 Opening, in order

After `crypto.unlock` succeeds (so a wrong password still writes
nothing — DEED-0002 INV-2):

0. **Check every prefix.** Read the first 6 bytes of `index`,
   `index.prev` and every `.c` and `.m` in `objects/`. A format number
   above what this release reads raises `VaultTooNew` here, before
   anything is written. A wrong magic is not refused here: step 4
   treats such an index file as unreadable, step 5 such a `.m`, and a
   `.c` with one fails when it is read.
1. **Lock.** Take an exclusive, non-blocking OS lock on `lock`
   (`fcntl.flock` on Linux and macOS, `msvcrt.locking` on Windows). If
   another process or another `Vault` in this process holds it, raise
   `VaultInUse`. `create` takes the same lock. The lock is released by
   `close`, and by the OS if the process dies.
2. **Migrate** (DEED-0004 § 4.3). Then each `.c` still below its
   format is listed by `damaged()`.
3. **Delete leftovers.** Every `*.tmp` in the vault folder and in
   `objects/` is an interrupted write (DEED-0002 § 4.6) and is deleted.
4. **Load the index.** Decrypt `index`; if it is missing or will not
   decrypt, decrypt `index.prev`; if neither will, rebuild: the index
   becomes the readable metadata files, in no particular order.
5. **Reconcile** against `objects/`, one document id at a time:

| On disk | Index | Action |
|---|---|---|
| no `.c`, no `.m` | entry | entry dropped — nothing of the document is left |
| no `.c`, `.m` present | either | files left in place; id reported by `damaged()` |
| `.m` readable, `edit` above the index's | entry | index takes the metadata file's object |
| `.m` readable, `edit` below the index's | entry | metadata file rewritten from the index |
| `.m` missing or unreadable | entry | metadata file rewritten from the index |
| `.m` readable | no entry | index gains the metadata file's object |
| `.m` unreadable | no entry | left in place; id reported by `damaged()` |
| `.m` missing | no entry | `.c` deleted — an unfinished add or remove |
| `.m` readable, same `edit` | entry | nothing |

6. **Save** the index (§4.3) if step 4 fell back or rebuilt, or steps 3
   and 5 changed anything. After a fallback this replaces the corrupt
   `index`, and §4.3 step 1 leaves `index.prev` untouched.

The rows are applied top to bottom and the first match wins; every row
after the first two has a `.c` present. "Readable"
means it decrypts and parses. Step 0 has already refused any newer
file, so nothing in steps 1–6 meets one.

### 4.7 What other parts call

`src/paperkist/errors.py` gains:

```python
class VaultInUse(PaperkistError): ...  # another process has it open
```

`Vault` in `src/paperkist/vault/vault.py` gains:

```python
def documents(self) -> list[dict]: ...           # every index entry, copied
def update(self, doc_id: str, changes: dict) -> None: ...
def remove(self, doc_id: str) -> None: ...
def damaged(self) -> list[str]: ...               # ids found by reconcile
```

`update` merges `changes` into the entry, raises `ValueError` if
`changes` holds `id` or `edit`, raises `edit` by one, and writes index
then metadata file. `remove` of an unknown id raises `DocumentMissing`.
The index code lives in `src/paperkist/vault/index.py` (load, save,
reconcile) and
`src/paperkist/vault/rebuild.py` (rebuild from metadata files), as
`docs/design.md` names them.

## 5. Invariants

Tests below run against code this item creates. Each names the rule its
fixture isolates.

- **INV-1** — Every add, update and remove is visible in `documents()`
  after the vault is closed and reopened.
  *Test:* `tests/test_index.py::test_changes_survive_reopen`.
  *Breaks when:* a change is written to the metadata file but not the
  index, or the index is not saved.

- **INV-2** — For every point at which a crash can interrupt an add,
  update or remove, reopening yields a vault where each document is
  either fully present or fully absent, with no `.tmp` file and no
  content file without an index entry.
  *Test:* `tests/test_recovery.py::test_crash_states` — builds each
  post-crash state directly on disk, one per step boundary in §4.5's
  table, then opens and checks. The "content file only" state isolates
  the deletion row: its metadata and index are absent, so no other row
  can remove it.
  *Breaks when:* a reconcile row is missing or applied in the wrong order.

- **INV-3** — A vault whose `index` will not decrypt opens from
  `index.prev`; one where neither will opens by rebuilding from metadata
  files; in both, every document with a readable metadata file is listed.
  *Test:* `tests/test_recovery.py::test_index_fallbacks` — corrupt one
  byte of `index`; then of both. A document added after the last save
  of `index.prev` is present only in metadata, so only the "no entry"
  row can list it. After the first case's open, `index.prev` must still
  decrypt to the index it held before.
  *Breaks when:* the fallback stops at the first failure, or a rebuild
  drops documents.

- **INV-4** — A metadata file whose `edit` is ahead of the index wins; one
  behind is rewritten.
  *Test:* `tests/test_recovery.py::test_edit_counter` — craft each case
  by writing an older or newer metadata file for one document.
  *Breaks when:* reconcile compares anything other than `edit`, or
  prefers the index unconditionally.

- **INV-5** — A second `Vault.open` of a vault already open raises
  `VaultInUse`, from another process as well as from the same one.
  *Test:* `tests/test_lock.py::test_second_open_refused` — a child
  process opens the vault and waits, and the parent's open must raise;
  then, in one process, a second `Vault.open` while the first is open
  must raise, and succeed after the first is closed.
  *Breaks when:* no lock is taken, or it is released before `close`.

- **INV-6** — Killing the process during a run of adds and updates never
  leaves a vault that fails to open or loses a document whose add had
  returned.
  *Test:* `tests/test_recovery.py::test_kill_during_writes` — a child
  adds and updates in a loop, printing each id once `add` returns; the
  parent kills it with `SIGKILL` (Linux and macOS; `TerminateProcess` on
  Windows) a short, varying delay after it has printed N ids, for many
  values of N, then reopens and reads every printed id. A kill at once
  lands just after `add` returned often enough that every run can miss
  the writes, so the delays spread from none to a few milliseconds.
  Across the runs, at least one must have left a `.tmp` file or an
  orphan `.c` behind, or the test fails: that is the evidence a kill
  landed mid-write. Runs continue past the planned set until one does,
  up to a cap. Windows drops a killed process's lock some time after it
  exits, so the reopen retries `VaultInUse` for a bounded time.
  *Breaks when:* the write order or a reconcile row is wrong, so a
  killed run leaves a vault that will not open or has lost a returned
  document. It does not isolate atomicity: with in-place writes the
  reconcile rows still recovered every run, so `atomic.py`'s replace
  is checked by reading it, as § 10 records.

- **INV-7** — Opening with a wrong password, or a too-new format, writes
  nothing — the recovery steps run only after a successful unlock.
  *Test:* `tests/test_recovery.py::test_refusals_write_nothing` — a
  vault holding a leftover `.tmp` and an orphan content file, which a
  premature recovery would delete, opened with a wrong password, then
  with a too-new header, then with one too-new `.m`. Each compares the
  folder before and after, and the `.m` case isolates step 0: the
  header is current, so only the per-file prefix check can refuse it.
  *Breaks when:* recovery runs before `unlock` or before step 0.

## 6. Failure modes

- **Both index files and some metadata files unreadable** → rebuild
  from the readable ones; the rest are listed by `damaged()`, left on
  disk, and never deleted.
- **Another process holds the lock** → `VaultInUse`; nothing written.
- **Disk full while saving the index** → the `OSError` propagates; the
  previous `index` is untouched (atomic replace), and the change's
  metadata file is not yet written, so the next open sees the old state
  or, for an add, deletes the lone content file.
- **The lock file cannot be created** (read-only folder) → the `OSError`
  propagates; a read-only vault is not supported in this item.
- **A power cut on Windows between replace and its flush to disk** →
  outside what the program can control there; noted in §4.4.

## 7. Tests

| Test | Locks |
|---|---|
| `tests/test_index.py::test_changes_survive_reopen` | INV-1 |
| `tests/test_recovery.py::test_crash_states` | INV-2 |
| `tests/test_recovery.py::test_index_fallbacks` | INV-3 |
| `tests/test_recovery.py::test_edit_counter` | INV-4 |
| `tests/test_lock.py::test_second_open_refused` | INV-5 |
| `tests/test_recovery.py::test_kill_during_writes` | INV-6 |
| `tests/test_recovery.py::test_refusals_write_nothing` | INV-7 |

Each must be seen failing once against a deliberately broken
implementation before it counts. CI runs them on Windows, macOS and
Linux; the Windows run is the first evidence for §4.4's Windows half.

## 8. Alternatives considered (and rejected)

- **A write-ahead journal instead of ordered writes and reconcile** —
  rejected: the design already makes every metadata file a recovery copy,
  so a journal would be a second recovery mechanism to keep consistent.
- **Timestamps instead of an edit counter** — rejected: clocks move
  backwards and differ between machines a vault is copied to.
- **Rebuilding from metadata files on every open, with no index** —
  rejected: the index is what records an update whose metadata write a
  crash interrupted (§4.5), so without it that update is lost.
- **A lock taken by creating a file exclusively** — rejected: a crash
  leaves the file behind and the vault locked; an OS lock ends with the
  process.

## 9. Out of scope

- Format migration — tracked by DEED-0004.
- Reporting `damaged()` ids to the user — tracked by DEED-0005.
- Read-only vaults, and a vault on a network share whose locks do not
  work — deferred; not yet queued.

## 10. What checks this

| Rule | What catches a breach |
|------|----------------------|
| INV-1 | `tests/test_index.py::test_changes_survive_reopen` |
| INV-2 | `tests/test_recovery.py::test_crash_states` |
| INV-3 | `tests/test_recovery.py::test_index_fallbacks` |
| INV-4 | `tests/test_recovery.py::test_edit_counter` |
| INV-5 | `tests/test_lock.py::test_second_open_refused` |
| INV-6 | `tests/test_recovery.py::test_kill_during_writes` |
| INV-7 | `tests/test_recovery.py::test_refusals_write_nothing` |
| Directory flush after replace (§4.4) | **nothing** — no test can pull the power; the call is visible in `atomic.py` only |
| Atomic replace itself (§4.4) | **nothing** — INV-6 passes against in-place writes too (see INV-6); checked by reading `atomic.py` |
| Windows replace behaviour | **`Partial:`** INV-6 on the Windows CI runner; not asserted locally |
| Windows retry while a file is in use (§4.4) | **`Partial:`** `tests/test_atomic.py` on the Windows CI runner; green on Linux proves nothing |

## 11. Cross-doc impact

`docs/design.md` already states these rules, and DEED-0002's spec
already hands the index write and `*.tmp` clean-up to this item. One
test moves: step 0 refuses a too-new `.c` at open, so the file case in
DEED-0002's `tests/test_vault.py::test_too_new` expects `VaultTooNew`
from `Vault.open` rather than from `read`. DEED-0002 INV-8 names no step,
so its text still holds.

## 12. Cold-eyes loop log

Rows live in `../reviews/DEED-0003-index-and-recovery-loop-log.md`.

## 13. Resource cost

The index holds every document's metadata, including extracted text, in
memory while the vault is open. At the owner's scale (hundreds of
documents) that is small; no cap is set here. Opening decrypts every
metadata file once to reconcile.

## 14. Migration / compatibility

A vault written by DEED-0002's code has no `index`, `index.prev` or
`lock`. Step 4 finds no index and rebuilds from its metadata files, step 6
saves the rebuilt index, and step 1 creates `lock`, so those vaults open
and are upgraded on first open.
