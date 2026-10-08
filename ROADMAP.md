<!-- ants-roadmap-format: 1 -->
<!-- Generated from the Ants Terminal roadmap store. Edit it with roadmap_log; hand edits are discarded by the next write. -->
# Paperkist — Roadmap

> What is planned, in progress and shipped. [CHANGELOG.md](CHANGELOG.md)
> is the user-facing record of what shipped; released items stay here and
> flip to ✅.
>
> **Format:** `~/.claude/standards/roadmap-format.md`. Theme emojis
> (§ 3.4), priority bands (§ 3.5.2) and the full bullet field set (§ 3.5)
> are defined there and deliberately not restated here.

**Legend**

- ✅ Done · 🚧 In progress · 📋 Planned · 💭 Considered
- 🚫 Dropped (closed, not done)

## 0.1.0 — (first release)

The first public release, on Windows, macOS and Linux. Items follow the
build order in `docs/brief.md` and the parts in `docs/design.md`. Signs
of success are cited by their `docs/discovery.md` labels, S1 to S10.

- ✅ [DEED-0001] **Project tooling: package layout, lint, tests, CI on three systems.**
  `pyproject.toml` with Python 3.12 up to the pinned PySide6's ceiling,
  ruff, pytest, and `scripts/local-ci.sh` called by `ci.yml` on
  Windows, macOS and Linux runners. Includes the import-rule test that
  enforces `docs/design.md` § What may depend on what.
  **Layman:** Sets up the automatic checks that run on Windows, macOS and Linux every time the code changes.
  Kind: chore.
  Lanes: tooling.
  Source: design-2026-09-27.
  Shipped 2026-09-27 (198d608): local gate green on Linux. The Windows
  and macOS CI legs have not run yet — no remote until DEED-0015 — so
  the first push is their first real run.

- ✅ [DEED-0002] **Vault core: create, lock, unlock, add and read a document.**
  Build step 1 of `docs/brief.md`. Needs a spec first — the vault-format
  spec that ADR-0001 and `docs/design.md` defer to (key record, piece
  size, associated-data encoding, file layout). Serves S5 and S6. Done
  when a test creates a vault, adds a file, reopens it and reads it back
  byte-identical on all three systems, and a wrong password fails
  cleanly.
  Overlaps DEED-0003 and DEED-0004: all three edit `src/deedbox/vault/`.
  Run them in order, not together.
  Blocked-by: DEED-0001
  **Layman:** The locked drawer itself: make a vault with a password, put a file in, and get exactly the same file back.
  Kind: implement.
  Lanes: crypto, vault.
  Source: design-2026-09-27.
  Spec accepted 2026-09-27: `docs/specs/DEED-0002-vault-format.md`.
  Shipped 2026-09-27 (cd8e739): round trip, wrong password, nothing
  readable, truncation, binding and too-new all locked by tests, each
  proven red by a deliberate break. Linux only so far; the Windows and
  macOS legs first run when the repository gets a remote (DEED-0015).

- ✅ [DEED-0003] **Index, safe saving and recovery on open.**
  Build step 2. The index, `vault/atomic.py`, the metadata-file recovery
  copies, the open-time order and reconciliation, and rebuild
  (`docs/design.md` § Which copy wins, § Opening, in order). Serves S8.
  Done when a test kills the process mid-write and the vault reopens
  intact.
  Blocked-by: DEED-0002
  **Layman:** Makes sure a power cut or crash never loses a filed document.
  Kind: implement.
  Lanes: vault, index.
  Source: design-2026-09-27.
  Spec accepted 2026-09-27:
  `docs/specs/DEED-0003-index-and-recovery.md`.
  Shipped 2026-09-27 (96513eb): index, recovery on open, lock; INV-1
  to INV-7 locked by tests, each proven red by a deliberate break except
  atomicity, which INV-6 does not isolate (spec § 10). Linux only so far;
  Windows and macOS first run with a remote (DEED-0015).

- ✅ [DEED-0004] **Format versions and the migration framework.**
  Per-file format numbers, a resumable `migrate`, refusal of a vault
  newer than the app, and a checked-in sample vault from the first
  format that every later release must open. Serves S9.
  Blocked-by: DEED-0002
  **Layman:** Makes sure a vault made with an older version always opens in a newer one.
  Kind: implement.
  Lanes: vault, migrate.
  Source: design-2026-09-27.
  Spec accepted 2026-09-28: docs/specs/DEED-0004-format-migration.md.
  Shipped 2026-09-28 (9bc3470, 13cf543): per-kind format numbers,
  resumable upgrade on open, frozen sample vault
  tests/fixtures/vault-format-1/. 50 tests green on Linux and Windows.

- ✅ [DEED-0005] **Main window: create or unlock a vault, add, list and view documents.**
  Build step 3. Vault creation says in plain words that a forgotten
  password loses everything (S2). Drag-in adding, a document list, and
  the in-window PDF and image viewer with no decrypted temporary file.
  Blocked-by: DEED-0003
  **Layman:** The window you use: set a password, drag files in, see them listed and open them without leaving the app.
  Kind: implement.
  Lanes: ui, app.
  Source: design-2026-09-27.
  Decided (2026-09-28, owner): Create stays disabled until the owner ticks
  "I understand my documents cannot be recovered without this password"
  (S2). A new password needs 12+ characters, typed twice, no other rules.
  A new vault defaults to a Paperkist-named folder in Documents, and any
  folder can be chosen.
  Shipped 2026-10-08: start, create and main windows in src/paperkist/ui/,
  start-up in src/paperkist/__main__.py. Tests: tests/test_ui_dialogs.py,
  test_ui_main_window.py. Linux and the Windows test box 78/78. Not yet:
  the expiry check on opening (no expiry part yet); unlocking runs in the
  window's thread behind a busy cursor.

- 📋 [DEED-0006] **Filing: category, tags, dates, note, with suggestions.**
  Editing a document's metadata, and `suggest` proposing a title,
  category and date from the filename and text. Suggests only; never
  files on its own.
  Overlaps DEED-0007 and DEED-0008 in the main window's files.
  Blocked-by: DEED-0005
  **Layman:** Lets you label each document, with sensible guesses you can always change.
  Kind: implement.
  Source: design-2026-09-27.
  Lanes: ui, suggest.

- 📋 [DEED-0007] **Search, including text already inside PDFs.**
  `search` over titles, tags, notes and extracted text; `extract`'s free
  path for PDFs that already contain text (pypdf), run in `ui`'s worker
  thread. Serves S3 for typed fields and digital PDFs.
  Blocked-by: DEED-0006
  **Layman:** Find a document by typing anything you remember about it.
  Kind: implement.
  Source: design-2026-09-27.
  Lanes: search, extract, ui.

- 📋 [DEED-0008] **Expiry tracking and the upcoming view.**
  Build step 4. Expiry and renewal dates, an upcoming view, the check
  when the main window opens, and already-expired items marked, not
  hidden. Serves S4. Done when a warranty dated next week shows up and
  one dated last year is flagged.
  Blocked-by: DEED-0006
  Note (2026-10-08): DEED-0005 left the expiry check on opening to this
  item. The design says `ui` runs it when the main window opens; the hook
  is MainWindow.__init__ in src/paperkist/ui/main_window.py.
  **Layman:** Shows what is about to run out as soon as you open the app.
  Kind: implement.
  Source: design-2026-09-27.
  Lanes: expiry, ui.

- 📋 [DEED-0009] **OCR for scans, in the background.**
  Build step 5. First confirm Tesseract reads images from a pipe with no
  temporary file; if not, this goes back to design (`docs/design.md`,
  the stack). pypdfium2 renders scanned pages in memory; extraction
  status is saved and unfinished work resumes on open. Serves S3. Done
  when search finds a model number that only appears inside a scan.
  Blocked-by: DEED-0007
  **Layman:** Lets search find words printed inside scanned documents and photos.
  Kind: implement.
  Source: design-2026-09-27.
  Lanes: extract, ui.

- 📋 [DEED-0010] **Export one document or the whole vault.**
  Original filenames and types, readable without Paperkist, never written
  inside the vault folder. Serves S7.
  Blocked-by: DEED-0005
  **Layman:** Get any document back out as a normal file, or everything at once.
  Kind: implement.
  Source: design-2026-09-27.
  Lanes: export, ui.

- 📋 [DEED-0011] **Owner files real paperwork for a week.**
  Twenty real documents from Downloads, used for a week (`docs/brief.md`,
  build step 3's check). Serves S10. Anything that makes it unpleasant
  becomes an item before packaging.
  Blocked-by: DEED-0005, DEED-0006, DEED-0007, DEED-0008, DEED-0010
  **Layman:** The real test: you use it for your own papers for a week and it earns its place.
  Kind: test.
  Source: design-2026-09-27.
  Lanes: ui.

- 📋 [DEED-0012] **Independent security review of the crypto and vault code.**
  Required before the first public release (`docs/brief.md`, Releasing
  it to the public). Covers ADR-0001's choices and the vault code.
  Blocked-by: DEED-0002, DEED-0003, DEED-0004
  **Layman:** Someone outside checks the lock before strangers trust it with their passports.
  Kind: security.
  Lanes: crypto, vault.
  Source: design-2026-09-27.
  Decided (2026-09-28, owner): seek a free or funded audit.
  Apply to programmes that fund audits of open-source security
  tools, and invite volunteer reviewers on the public repo.

- 📋 [DEED-0013] **Help written for non-technical people.**
  Setup, backup by copying the vault folder, the forgotten-password
  warning, what stays visible on disk, and the memory limit
  (`docs/design.md`, What it rules out). Serves S1, S2 and S6.
  Blocked-by: DEED-0005
  **Layman:** Plain-English help on setting up, backing up, and what a forgotten password means.
  Kind: doc.
  Source: design-2026-09-27.
  Lanes: ui, docs.

- 📋 [DEED-0014] **Installers: Windows and macOS builds (unsigned at first), Flatpak for Linux.**
  Build step 6. PyInstaller for Windows and macOS, Flatpak for Linux,
  Tesseract bundled in all three, unsigned at first. Serves S1.
  Done when someone who did not build it installs it on a fresh
  machine per system and files a document without help.
  Blocked-by: DEED-0009, DEED-0013
  **Layman:** Makes Paperkist installable by anyone on any of the three systems.
  Kind: package.
  Lanes: packaging.
  Source: design-2026-09-27.
  Decided (2026-09-28, owner): ship unsigned at first. The
  help explains the system warning and how to get past it. Signing
  can come in a later release.

- ✅ [DEED-0015] **Public repository, bug tracker and security contact.**
  Needs the owner's say on where the repository lives. `SECURITY.md`
  already exists and needs a real contact.
  **Layman:** A public home for the code, a place to report problems, and a private way to report security holes.
  Kind: chore.
  Lanes: repo.
  Source: design-2026-09-27.
  Shipped 2026-09-27: public at https://github.com/milnet01/deedbox
  (owner's choice), issues on, private vulnerability reporting on,
  SECURITY.md names it. The first three-OS CI run is GitHub Actions run
  36312128466; its result had not been seen when this was written.

- ✅ [DEED-0016] **Trademark check on the name Deedbox.**
  `docs/brief.md` records only a web search. Decide before the first
  public release.
  **Layman:** Makes sure nobody else owns the name before it goes public.
  Kind: investigate.
  Lanes: repo.
  Source: design-2026-09-27.
  Decided (2026-09-28, owner): Claude searches the public
  trademark databases and app stores and writes up what it finds;
  the owner decides. Not legal advice.
  Search done 2026-09-28 (not legal advice). No registered or pending
  DEEDBOX mark in USPTO or TMview (EU, UK, WIPO and others). But three
  software products took the name in 2026, none registered: deedbox.io
  (Kontroll Solutions Ltd, UK encrypted document handover for
  conveyancers), an iOS landlord app by Vibesoft LLC, and
  deedbox-maintainers/deedbox-app (AGPL law-firm software with document
  management). deedbox.com and deedbox.app are parked. "Deed box" is also
  a common phrase for a document box. Awaiting the owner's decision.
  Decided (2026-09-28, owner): rename before the first release. The new
  name is the owner's pick from a screened shortlist; the rename itself
  is DEED-0023.

- ✅ [DEED-0022] **The local gate's documentation step checks something.**
  `scripts/local-ci.sh`'s `documentation` step holds only the template's
  example comments, so `--docs` prints "passed" having run nothing. The
  same file says a check that did not run must not look like one that
  passed. Wire in a real link and path check.
  **Layman:** The pre-push check says the docs passed without looking at them; make it actually check links and paths.
  Kind: chore.
  Lanes: repo.
  Source: in-session-2026-09-28.
  Shipped 2026-09-28: scripts/check_docs.py checks every relative link
  in the tracked Markdown files resolves, in both gate modes. Anchors
  are not checked, only files. tests/test_check_docs.py locks it.

- ✅ [DEED-0023] **Rename the app before the first release.**
  The owner chose to rename (DEED-0016's search, 2026-09-28). Covers the
  product name in text, the Python package, the repository and the
  default vault folder name. The on-disk markers inside vault files
  (`DBX*` prefixes, the associated-data label) stay as they are: users
  never see them, and changing them would break the frozen format-1
  sample vault.
  Blocked-by: DEED-0016
  **Layman:** Gives the app a name nobody else's software is already using.
  Kind: chore.
  Lanes: repo.
  Source: owner-decision-2026-09-28.
  Shortlist screened 2026-09-28 (USPTO, PyPI, GitHub, App Store,
  Flathub, domains; EU/UK/WIPO registers NOT reached). Best first:
  Paperkist (nothing found anywhere; .com unregistered), Keepleaf
  (keepleaf.com is a household-goods shop), Paperwell (a dormant 2012
  legal-templates startup used it), Sheafkeep (a Taiwanese magnet shop
  owns the .com), Almery (near Almerys, a French health-insurance app).
  Rejected: Scrinia, Lockleaf, Quirebox, Cofferly, Kistly. Awaiting the
  owner's pick; then check EU/UK registers for that one name before
  renaming.
  Decided (2026-09-28, owner): Paperkist. Same day: a web search for
  the exact word "Paperkist" found no use (nearest: Paperkast, Paper
  Kiss). EU/UK registers still not reached: TMview's API returned an
  empty body to curl, and the browser extension was not connected.
  Shipped 2026-10-08: renamed Paperkist. A TMview search (EU, UK and many
  national offices), run by Claude in the owner's browser on 2026-10-08,
  found no mark containing "Paperkist"; the nearest, PAPERKISS, expired
  (Australia 2019, New Zealand 2020). Corrects an earlier note that said
  the owner had checked. Package src/paperkist/,
  repository milnet01/paperkist. vault.deedbox, the DBX* prefixes, the
  associated-data label and the sample password keep the old name.

- 📋 [DEED-0024] **Opt-in self-updater on Windows, macOS and Linux (Flatpak).**
  The one network use Paperkist has. Off until the user turns it on;
  a manual "Check for updates" also runs. Modelled on finbreak's
  updater (its FIBR-0054 and FIBR-0131 specs): GitHub releases over
  HTTPS only, the download's signature checked before it replaces
  the app. Needs a spec (write-spec) before it is built.
  Blocked-by: DEED-0014
  Decided (2026-09-28, owner): all three systems, the Flatpak
  included; the signature check lives in `crypto`.
  Build note (2026-09-28): tests/test_dependency_rules.py keeps its
  own copy of the design's parts. Building this adds an `update` part
  there, lets it call `crypto`, and lets `update/fetch.py` alone import
  a network library, per docs/design.md rules 3, 7, 10 and 11.
  Decided (2026-09-28, owner, from the design review): the Linux
  Flatpak updates through Flatpak's update portal, which `ui` asks
  through QtDBus; Paperkist downloads nothing there. `update` downloads
  and verifies on Windows and macOS only. The dependency test must also
  let `update` use `tempfile` for a downloaded release (design rule 4),
  and the "updates on" setting is `ui`'s (design § Settings).
  Build note (2026-09-28): the dependency test's ALLOWED_PARTS for
  `ui` must also gain `update` (design rule 8). On the Flatpak, `ui`
  starts the update service only when updates are on or the user asked
  (design rule 7); the service refuses a release that widens sandbox
  permissions (design rule 11).
  For the spec (from the design review, 2026-09-28): name who signs
  each release and in what format, since `update` checks a signature
  nothing yet produces. On the Flatpak there is no one-off check —
  the portal only watches while a monitor is open (measured in
  org.freedesktop.portal.Flatpak.xml) — so say what the "Check for
  updates" menu item does there.
  For the spec (design review of DEED-0035, 2026-09-28): the design's
  update row opens "On Windows and macOS", yet `ui` needs `update`'s
  install detection on Linux too, to know it is a Flatpak. Say the
  detection half runs on all three systems and only fetch/install is
  Windows and macOS.
  **Layman:** Paperkist can fetch and install its own new versions, but only if you switch that on.
  Kind: feature.
  Source: user-request-2026-09-28.
  Lanes: update, crypto, ui, packaging.

- 📋 [DEED-0025] **Design: name the input shape of search, expiry and suggest.**
  docs/design.md rule 3 says "Every other part gets documents and the
  index through the `Vault` object", but tests/test_dependency_rules.py
  lets `search`, `expiry` and `suggest` import only `errors`, so they
  cannot take a `Vault` or import its entry type. The design does not
  say what they receive — plain values `ui` extracts, or a shared type
  every part may import. Narrow rule 3's "every other part" to `ui` and
  `export`, and name the shape. Found by one cold lane; pre-existing,
  outside the DEED-0024 gate, so filed rather than fixed in that run.
  **Layman:** Settles how the search and date-checking code receive document details, before either is built.
  Kind: doc-fix.
  Source: review-contract design.md loop 5, 2026-09-28.
  Lanes: design, search, vault.

- 📋 [DEED-0026] **Design: check the damaged-document list against Vault.open's stale-content case.**
  `Vault.open` in src/paperkist/vault/vault.py also marks as damaged
  any document from `index.stale_content` whose content file still
  exists after reconcile. docs/design.md § Opening, in order lists the
  damaged cases and does not name this one. Both cold lanes raised it
  as an open question; neither could see `stale_content`. Read it, then
  either add the case to the design or confirm an existing line covers
  it. Pre-existing, outside the DEED-0024 gate, filed at its cap.
  Also from the 2026-09-28 DEED-0035 design review: Vault.open runs
  index.check_prefixes before the lock and index.delete_leftovers before
  loading the index; § Opening, in order names neither. Settle together
  with the stale-content case.
  **Layman:** Makes sure the design lists every way a stored document can be flagged as damaged.
  Kind: doc-fix.
  Source: review-contract design.md loop 7, 2026-09-28.
  Lanes: design, vault.

- ✅ [DEED-0035] **Translation-ready from the first window.**
  Owner's decision (2026-09-28): all user-facing text goes through
  Qt's translation mechanism and every window lays out correctly
  mirrored for right-to-left, from the first window. The translations
  themselves are DEED-0027 (0.3.0). Needs a design rule, gated before
  DEED-0005's windows are built.
  Shipped 2026-10-08: every ui string goes through Qt translation, layouts
  mirror right-to-left, start-up installs ui/translations/paperkist_<lang>.qm.
  Tests: tests/test_ui_text.py, tests/test_app.py.
  **Layman:** Every piece of on-screen text can be translated, and windows work right-to-left, so languages can be added later without rebuilding the windows.
  Kind: feature.
  Source: user-request-2026-09-28.
  Lanes: ui, design.

- 📋 [DEED-0036] **Design: an extraction status for failed or impossible extraction, and the no-OCR wording.**
  Two pre-existing gaps both cold lanes raised, outside the DEED-0035
  gate. (1) docs/design.md § Names on disk stores an extraction status
  of "not yet run, done, or no OCR tool", with no value for a failed
  extraction (a malformed PDF, an OCR crash) or a file that cannot be
  extracted (a stored type that is neither PDF nor image). `ui` queues
  every document whose extraction "has not run", so without a terminal
  status such documents re-queue on every open; and the status is on
  disk, so adding one later is a format change. (2) The stack table's
  Tesseract row says "Missing → search covers typed fields only", but
  text PDFs are extracted by pypdf without Tesseract. Should read:
  scanned documents are searchable by typed fields only.
  Blocks DEED-0009, which builds extraction.
  Also from loop 10 (2026-09-28): no part is given the job of finding
  the bundled Tesseract. `packaging` puts it somewhere and `extract` must
  find it there, while rule 11 forbids code assuming it runs installed.
  Name the lookup contract (for example: packaging puts it on PATH;
  extract looks only on PATH).
  **Layman:** Settles what Paperkist records when it cannot read the text in a document, before the reading code is built.
  Kind: doc-fix.
  Source: review-contract design.md loop 9, 2026-09-28.
  Lanes: design, extract, vault.

- 📋 [DEED-0037] **Unlock and create without freezing the window.**
  DEED-0005 runs Vault.create and Vault.open in the window's own thread
  behind a busy cursor; the real key settings take about a second, and
  a slower machine longer. Move them to a worker thread that `ui` owns
  (design § Background work).
  **Layman:** The window stays responsive while your password is being checked.
  Kind: ux.
  Source: in-session-2026-10-08.
  Lanes: ui.

## 0.2.0

The release after 0.1.0. Its items were moved here from "Later" by the owner on 2026-09-28.

- 📋 [DEED-0017] **Reminders while the app is closed.**
  `docs/discovery.md` rules it out for the first release only;
  `docs/brief.md` wants it only if it works on all three systems.
  Planned for 0.2.0 by the owner, 2026-09-28.
  **Layman:** Paperkist could warn you about an expiring passport even when it isn't open.
  Kind: feature.
  Source: discovery-2026-09-27.
  Lanes: ui.

- 📋 [DEED-0018] **Signed Windows and macOS installers.**
  DEED-0014 ships unsigned at first, by the owner's decision.
  macOS needs a paid Apple developer account.
  Planned for 0.2.0 by the owner, 2026-09-28.
  **Layman:** Stops Windows and Mac warning that the app comes from an unknown developer.
  Kind: package.
  Source: owner-decision-2026-09-28.
  Lanes: packaging.

- 📋 [DEED-0019] **Change the password, and strengthen an existing vault's password protection.**
  Deferred in `docs/specs/DEED-0002-vault-format.md` § 9.
  Planned for 0.2.0 by the owner, 2026-09-28.
  **Layman:** Lets you pick a new password, and makes an old vault as hard to crack as a new one.
  Kind: feature.
  Source: DEED-0002 spec § 9.
  Lanes: crypto, vault.

- 📋 [DEED-0020] **Read-only vaults, and vaults on a network drive.**
  Deferred in `docs/specs/DEED-0003-index-and-recovery.md` § 9.
  A network share's file locks may not work.
  Planned for 0.2.0 by the owner, 2026-09-28.
  **Layman:** Opening a vault from a locked-down folder or a shared drive.
  Kind: feature.
  Source: DEED-0003 spec § 9.
  Lanes: vault.

- 📋 [DEED-0021] **More than one vault.**
  `docs/brief.md` leans to one vault, without hard-coding a
  single path.
  Planned for 0.2.0 by the owner, 2026-09-28.
  **Layman:** Separate vaults, for example one for the household and one personal.
  Kind: feature.
  Source: brief-2026-09-27.
  Lanes: ui, vault.

## 0.3.0

Everyone can use it: languages, accessibility and themes. Set by the owner on
2026-09-28.

- 📋 [DEED-0027] **Translations: Afrikaans, right-to-left languages, and common European languages with their American variants.**
  Owner's list (2026-09-28): Afrikaans; right-to-left languages;
  common European languages, including their variants in the Americas
  (for example es-419 and pt-BR beside es-ES and pt-PT). Needs every
  user-facing string translatable and layouts that mirror for
  right-to-left, which is cheapest to decide before the windows are
  built; the path to 1.0.0 proposal settles when.
  **Layman:** Use Paperkist in your own language, including Afrikaans, Arabic or Hebrew, and Spanish or Portuguese as spoken in the Americas.
  Kind: feature.
  Source: user-request-2026-09-28.
  Lanes: ui, packaging.

- 📋 [DEED-0028] **Themes.**
  **Layman:** Choose how Paperkist looks, such as light or dark.
  Kind: feature.
  Source: user-request-2026-09-28.
  Lanes: ui.

- 📋 [DEED-0029] **Accessibility.**
  **Layman:** Make Paperkist usable with a keyboard alone, a screen reader, large text and high contrast.
  Kind: accessibility.
  Source: user-request-2026-09-28.
  Lanes: ui.

## 1.0.0

The promise: safe to trust with your passports for years. Set by the owner on
2026-09-28.

- 📋 [DEED-0030] **Freeze the vault format as a written commitment.**
  State that format 1.0 is supported by every later release, and
  how a future format change is handled (migrate, never refuse).
  Builds on S9 and docs/specs/DEED-0004-format-migration.md.
  **Layman:** A written promise that every future Paperkist opens a vault made with 1.0.
  Kind: doc.
  Source: user-request-2026-09-28.
  Lanes: vault, docs.

- 📋 [DEED-0031] **Every finding from the outside security audit fixed.**
  Closes what DEED-0012's audit reports. Blocked-by: DEED-0012
  **Layman:** Anything the outside security check finds gets fixed before 1.0.
  Kind: security.
  Source: user-request-2026-09-28.
  Lanes: crypto, vault.

- 📋 [DEED-0032] **Tested by non-technical people on all three systems.**
  Beyond the owner's week (DEED-0011): strangers on each system,
  against S1, S2 and S3. What trips them up is filed and fixed.
  **Layman:** People who have never seen Paperkist install and use it on Windows, macOS and Linux, and we fix what trips them up.
  Kind: test.
  Source: user-request-2026-09-28.
  Lanes: ui, packaging.

- 📋 [DEED-0033] **A support policy: which versions get security fixes, and for how long.**
  Replaces SECURITY.md's "Nothing has been released" under
  § Supported versions.
  **Layman:** Says clearly which versions still get security fixes.
  Kind: doc.
  Source: user-request-2026-09-28.
  Lanes: docs.

- 📋 [DEED-0034] **Stays quick with thousands of documents.**
  No success sign covers vault size yet. Set a size and a bar
  (for example, opening and searching a vault of several thousand
  documents on a modest laptop), measure it, and fix what misses.
  **Layman:** Years of paperwork in one vault still opens and searches quickly.
  Kind: perf.
  Source: user-request-2026-09-28.
  Lanes: vault, search, ui.
