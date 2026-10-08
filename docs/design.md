# Paperkist — Design

> **Purpose — so the shape is decided once, and anyone can tell where a
> new piece of work belongs and what it is allowed to touch.**

**This document is a gate.** Work is not broken into items until it is
agreed — `~/.claude/workflow.md` § 2. It passes when someone can take any
item off the queue and say which part it belongs in and what it may
touch.

**Status:** agreed; the packaging part and rules 10–11 reviewed
2026-09-28. Built from `docs/discovery.md`; its sign labels (S1–S10)
are cited below.

## The parts

All code lives in the Python package `src/paperkist/`. Tests mirror it under
`tests/`.

| Part | Responsible for | Files |
|---|---|---|
| **crypto** | Turning a password into a key; encrypting document content as a stream (secretstream) and the index and metadata files as single messages. The only code that touches the encryption library. | `src/paperkist/crypto.py` |
| **vault** | The vault on disk: its folder layout, format version and header, the encrypted document files, and the one atomic-write helper. Opening, closing, adding, reading, removing. | `src/paperkist/vault/layout.py`, `vault/documents.py`, `vault/atomic.py`, `vault/lock.py`, `vault/vault.py` |
| **index** | The encrypted catalogue: each document's metadata and extracted text, saving it safely with the previous copy kept, and rebuilding it from the documents' metadata files. | `src/paperkist/vault/index.py`, `vault/rebuild.py` |
| **migrate** | Upgrading a vault written by an older release to the current format (S9). | `src/paperkist/vault/migrate.py` |
| **search** | Answering a query from the loaded index (S3). | `src/paperkist/search.py` |
| **expiry** | Deciding what is upcoming and what has already expired (S4). Pure date logic. | `src/paperkist/expiry.py` |
| **extract** | Getting text out of a document: the free path for PDFs that already contain text, and OCR for scans (S3), rendering scanned PDF pages to images in memory first. Plain and synchronous; `ui` runs it in a worker thread. | `src/paperkist/extract/pdftext.py`, `extract/ocr.py` |
| **suggest** | Proposing a title, category and date from a filename and extracted text. Suggests only; never files. | `src/paperkist/suggest.py` |
| **export** | The only code that writes readable plaintext to disk: one document, or the whole vault (S7). | `src/paperkist/export.py` |
| **update** | On Windows and macOS: checking for, downloading and installing a new release (DEED-0024). The only code that opens a network connection. Asks `crypto` to check each download's signature before installing it. Also tells `ui` how Paperkist was installed. The Linux Flatpak cannot replace its own files; there `ui` asks Flatpak's update service, through Qt, to install the new version from the store it came from. | `src/paperkist/update/`; the network code in `update/fetch.py` alone |
| **errors** | The shared error types every part raises. | `src/paperkist/errors.py` |
| **ui** | Every window, dialog and the in-window document viewer, and the worker threads for extraction. Runs the expiry check when the main window opens. Owns the translation files. | `src/paperkist/ui/` — one file per window or dialog; translation sources in `ui/translations/` |
| **app** | Start-up: builds the Qt application, loads the compiled translation for the system's language from `ui/translations/`, and opens the first window. | `src/paperkist/__main__.py` |
| **packaging** | Building the installers: PyInstaller for Windows and macOS, the Flatpak for Linux, each bundling Tesseract (S1) and the compiled translations. Imports nothing from Paperkist; it packages the tree. | `packaging/` |

**`vault` in the rules below means the whole `src/paperkist/vault/`
package** — vault, index and migrate. They share the atomic-write helper
and the key, and change whenever the format does. Nothing outside the
package reads the index's file layout.

## What may depend on what

The rules, strongest first. A test can check the import half of each
by reading imports; a condition a rule attaches needs a behaviour test.

1. **Only `ui` and `app` import Qt.** Everything else runs and is tested
   without a display. This keeps the vault logic checkable on all three
   systems in plain automated tests.
2. **Only `crypto` imports the encryption library and interprets its
   settings.** `crypto` hands `vault` a key-derivation record — the
   Argon2id settings, salt and wrapped vault key as one byte string —
   and `vault` stores it in the header without reading it.
3. **Only `vault` and `update` call `crypto`** — `update` only to check a
   download's signature — and only `vault` reads or writes files
   inside the vault folder. Every other part gets documents and the index
   through the `Vault` object in `vault/vault.py`.
4. **Only `export` writes decrypted content to disk**, and only when the
   user asked for an export, and never to a place inside the vault
   folder. No part writes a decrypted temporary file,
   ever — not for viewing, not for OCR, not for printing. `update` may
   hold a downloaded release in a temporary file; a release carries no
   document content.
5. **`search`, `expiry` and `suggest` are pure.** They take data in and
   return answers. No disk, no network, no Qt, no clock of their own —
   today's date is passed in.
6. **`extract` takes document bytes and returns text.** It never opens a
   vault file and holds no thread or Qt signal. Scanned PDF pages become
   images in memory; OCR hands those image bytes to the OCR tool through
   a pipe.
7. **Only `update/fetch.py` opens a network connection.** `ui` runs
   `update`'s check only after the user turned updates on or asked for
   one. On the Flatpak, `ui` starts the update service's watch only
   while updates are on; the service has no one-off check. No check
   sends anything about the user's documents. No other file
   imports a network library (discovery: documents never leave the
   machine). This grant is per file, not per part; the dependency test
   gains `update` and its exceptions in the change that builds it
   (DEED-0024).
8. **`ui` may call** `vault`, `search`, `expiry`, `suggest`, `extract`,
   `export` and `update`. **It may not call** `crypto`, and it may not build a path
   inside the vault folder.
9. **Nothing depends on `ui` or `app`.** Every part may import `errors`.
10. **`app` may call only `ui`**, **`export` may call only `vault`**, and
    **`update` may call only `crypto`** (besides `errors`). These were arrows in the diagram below; the
    diagram renders the rules and does not add to them.
11. **`packaging` is not imported by anything and imports nothing from
    `src/paperkist/`.** It builds installers from the tree and the
    dependency lock; no Paperkist code may assume it runs installed. Only
    `update` asks how Paperkist was installed, and it does nothing when it
    cannot tell. Flatpak's update service installs a release only if it
    asks for no more sandbox permissions than the installed one; a
    Flatpak release that widens them reaches users only through their
    software centre.

```
app ─► ui ─► vault ─► crypto
        │      └────► errors
        ├─► search, expiry, suggest   (pure)
        ├─► extract
        ├─► export ─► vault
        └─► update ─► crypto
```

## What every part does the same way

- **Errors.** Every expected failure is one of the types in
  `errors.py`, which is the full list; a new expected failure adds a type
  there. `ui` turns each into one plain-language message. Nothing catches
  an error and carries on silently: documents found damaged while
  opening are listed by `Vault.damaged()`, and `ui` shows that list when
  the vault opens.
- **Text on screen.** Inside the app, only `ui` writes text the user
  reads, and every such string goes through Qt's translation mechanism.
  Every window lays out correctly when mirrored for right-to-left
  languages (DEED-0035).
  Dates are shown in the user's locale format.
- **Categories.** A built-in category is stored as a fixed key that `ui`
  shows translated; one the user added is stored as typed. The metadata
  records which of the two it is, so a user's category spelt like a key
  stays the user's. `suggest` defines the built-in keys and `ui` imports
  them for its labels. `suggest` returns a key or the user's own text,
  never a translated name.
- **State.** An open vault is one `Vault` object. The key exists only in
  that object's memory while the vault is open, and is dropped on close.
  Decrypted documents live in memory only while shown.
- **Saving.** Every write into the vault folder goes through
  `vault/atomic.py`: write to a new file, flush it to disk, then replace
  the old one in one step (S8). The one exception is the empty `lock`
  file, which `vault/lock.py` holds so only one copy of the app opens a
  vault; a second open is refused with `VaultInUse`. The index keeps its previous copy. The
  recipe is tested on Windows, macOS and Linux, because replacing a file
  behaves differently on Windows.
- **Which copy wins.** The index is the truth; each metadata file is its
  document's recovery copy, carrying an edit counter the index also
  records. Adding writes content, then index, then metadata file.
  Editing writes index, then metadata file. Removing deletes the metadata
  file, then writes the index, then deletes the content file.
- **Opening, in order.** Read the header and check the password;
  nothing is written before both pass. Take the `lock`. Run `migrate`.
  Load the index; if it will not decrypt, load its previous copy; if
  neither will, rebuild from the metadata files. Then reconcile against the files on disk:
  - a metadata file ahead of the index, or not listed in it, updates the
    index;
  - an index entry whose metadata file is behind or missing has that file
    rewritten from the index;
  - a content file with neither an index entry nor a metadata file is
    left from an unfinished add or remove, and is deleted;
  - an index entry whose content and metadata files are both gone is
    dropped;
  - a missing content file beside a metadata file, or an unreadable
    metadata file with no index entry, marks the document damaged: it
    stays on disk and is listed by `Vault.damaged()`.
- **Names on disk.** Each document is two encrypted files sharing one
  random id: its content, and a small metadata file holding its title,
  category, tags, note, dates, original filename, file type, extracted
  text and extraction status (not yet run, done, or no OCR tool).
  Editing metadata rewrites only the small file and the index.
  Rebuilding the index reads the metadata files alone; nothing is
  re-extracted. No title, date, category or original filename appears
  in any name (S5).
- **Format version.** The vault header and every file in the vault
  except `lock` carry a format number from the first release. Opening a
  vault runs `migrate` before loading the index. It rewrites one file at a time through
  `vault/atomic.py` and updates the header's number last, so an
  interrupted migration resumes on the next open. A vault or file newer
  than the app is refused with a clear message, never guessed at (S9).
- **Logging.** Python's standard `logging`, to a file in the user's
  app-data folder — never inside the vault folder. A log
  line never contains a document's content, title, tags, note, extracted
  text, search query or the password.
- **Settings.** Choices kept between runs, such as whether updates are
  on, live in one file in the user's app-data folder — never inside the
  vault folder. `ui` owns them through Qt's settings store in INI
  format and passes other parts what they need.
- **Dates.** Calendar dates without times, stored as ISO text
  (`2026-09-27`). Compared in the user's local day.
- **Background work.** OCR and text extraction run in worker threads
  that `ui` owns, and report back through Qt signals. When a vault opens,
  `ui` queues every document whose extraction has not run, and those
  marked no OCR tool once the tool is present. Filing a document never waits
  for them.

## The stack, and what it rules out

| Choice | Why | Runner-up |
|---|---|---|
| **Python 3.12 up to the newest the pinned PySide6 supports** | Chosen in ADR-0002; shared with Rolodex and finbreak. 3.10 leaves security support in October 2026. [ADR-0002](decisions/ADR-0002-python.md) | C++ |
| **PySide6** (Qt for Python) | Qt's official Python binding. `QtPdf` shows a PDF from memory with no temporary file — checked 2026-09-27 by loading a PDF from an in-memory buffer. LGPL, compatible with GPL-3.0. | PyQt6 |
| **PyNaCl** (libsodium) | Argon2id key derivation and a documented recipe for encrypting large files in pieces, from one well-known library. [ADR-0001](decisions/ADR-0001-crypto-library.md) | `cryptography` |
| **pypdf** | Reads the text already inside digital PDFs without Qt, so `extract` stays testable headless. | Qt's own PDF text extraction |
| **pypdfium2** + **Pillow** | Render a scanned PDF page to image bytes in memory, without Qt — checked 2026-09-27 by rendering a page from bytes to PNG bytes. BSD-3-Clause / Apache-2.0, and MIT-CMU. | pypdf's embedded-image extraction |
| **Tesseract** for OCR | The standard free OCR engine; Apache-2.0. All three installers bundle it — the Flatpak too, because a sandboxed app cannot run a copy installed on the computer. Missing → search covers typed fields only. Reading images from a pipe is confirmed at the OCR step, before OCR is built; not checked here. If it needs a temporary file, OCR goes back to design rather than breaking rule 4. | none considered |
| **pytest** + **ruff** | The Python standard's tooling. | — |
| **PyInstaller** for Windows and macOS, **Flatpak** for Linux | Rolodex already builds with PyInstaller on all three systems; Flathub is Linux's app store. | Briefcase |
| **GitHub Actions** on Windows, macOS and Linux | Every push runs the tests on all three. | — |

**What it rules out:**

- **No web interface and no local server.** Nothing listens on a port.
- **No outside PDF viewer.** Viewing happens in Paperkist's window.
- **No reliable wiping of memory.** Python cannot guarantee a decrypted
  document is erased from memory after use. The protection is for the
  vault at rest (S5), not against someone already running code on the
  unlocked machine. Help text will say so plainly.
- **No hiding of sizes and times.** Anyone holding the vault folder can see
  roughly how many documents it holds, how large each is, and when each
  was last written. S5's opaque dates are the documents' own dates, which
  live only inside encrypted files.
- **A large installer.** Python plus Qt makes a bigger download than a
  C++ app.
- **Formats Qt cannot show.** v1 shows PDFs and common image types only;
  anything else can be stored and exported but not previewed.

## Close calls

- [ADR-0001 — PyNaCl for the encryption](decisions/ADR-0001-crypto-library.md)
- [ADR-0002 — Python, not C++](decisions/ADR-0002-python.md)

## Cold-eyes loop log

Rows live in [`reviews/design-loop-log.md`](reviews/design-loop-log.md).
