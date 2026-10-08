# Paperkist

**Every important piece of paper you own, in one locked drawer on your own
computer — and a nudge before a warranty runs out.**

> **Status: not started.** This file is a *brief*, not documentation of
> something that exists. It's here so that when you sit down to build this,
> you don't have to re-think the problem from scratch.
>
> **Decided (2026-09-25):** this is a **public app for anyone to use**, not a
> personal tool, and it ships on **Windows, macOS and Linux** from the first
> public release. Sections below were revised for that; see
> [Releasing it to the public](#releasing-it-to-the-public).
>
> **Also decided (2026-09-25), settling the "leaning" notes below:**
> Argon2id key derivation with an authenticated cipher; a Qt desktop window;
> GPL-3.0 licence; reminders shown when the app opens; one vault in v1 without
> hard-coding that there is only one; the project lives next to Rolodex and
> the other apps under `Scripts/Linux/`.
>
> **Named Deedbox (2026-09-25).** "Folio", the working name, is taken; see
> [Prior-art check](#prior-art-check-2026-09-25). A deed box is a lockable
> box for important papers.
>
> **Renamed Paperkist (2026-10-08).** Other software took the name Deedbox
> in 2026 (DEED-0016), so the owner chose a new one (DEED-0023). A kist is
> a chest.

---

## The problem

You've built the private-life-admin set almost completely:

- **Rolodex** — passwords, keys, secret notes.
- **finbreak** — where the money goes.
- **Contact List** — the people.

The missing drawer is **paperwork**. Receipts, appliance manuals, warranties,
insurance policies, vehicle papers, ID documents, medical letters, guarantees
on work done to the house. Right now that lives in a physical folder, a
scattering of PDFs in Downloads, and some photos on a phone.

Two things go wrong. You can't *find* the receipt when the thing breaks. And
you don't find out the warranty expired until after it mattered.

That problem isn't yours alone — almost everyone has it. So Paperkist is built for
the public: someone who has never heard of encryption should be able to
install it, set a password and file their first receipt without help.

## Why not just use an existing tool?

**Paperless-ngx** is the standard answer, and it's genuinely good software.
It's also a Docker stack with a database, a task queue and a web server — a
weekend of setup and a permanently running service, to store your fridge
receipt. If it stops working in two years you have to remember how you built it.

The other options are cloud drives (fine until you want them not to be
someone else's computer) or Evernote-style products with an account and a
subscription.

**The gap is the same one Rolodex fills:** one file, one password, one window,
no server, nothing leaving the machine. Not a small Paperless — a different
product with a much smaller promise.

Do check the current state of Paperless-ngx before you start. If it's grown a
genuinely one-click desktop install since this was written, that changes the
calculation and it's better to know on day one.

### Prior-art check (2026-09-25)

Result: **no free desktop app found that does encrypted storage plus expiry
tracking on Windows, macOS and Linux.** The gap is real.

- **Paperless-ngx** — still Docker-only; no one-click or desktop install.
- **Paperwork** (openpaper.work) — Linux and Windows desktop app; no built-in
  encryption (relies on the operating system's). Its GitHub repository was
  archived in March 2026 and moved to GNOME's GitLab; whether work continues
  there was not checked.
- **Warracker** — open-source warranty tracker with reminders, but a
  self-hosted web app that needs Docker.
- **Sortio** — paid AI file sorter; no encryption or expiry tracking found.
- **Folio** (folio.id), **Paperlock**, **Paper Trail** — encrypted document
  apps with expiry reminders, but **phone-only**. Folio and Paperlock also
  take the two most obvious names for this app.

## What it does (v1)

- **Add a document** — drag in a PDF or photo.
- **File it** — a category, a few tags, a date, a free-text note. Sensible
  suggestions from the filename and the document's own text, always editable.
- **Find it** — search across titles, tags, notes *and the text inside the
  documents* (see OCR below).
- **Track expiry** — a document can carry an expiry or renewal date (warranty
  ends, policy renews, licence expires, guarantee runs out). Paperkist tells you
  what's coming up.
- **Get it back out** — open, export, or print any document, and export the
  whole vault in a plain readable form. No hostage-taking.
- **Lock it** — everything encrypted at rest with one master password. A
  forgotten password means the documents are gone for good; the app must say
  so plainly when the vault is created, in words a non-technical person reads.

### Deliberately not in v1

- **No sync, no cloud, no server.** Backup is "copy the vault folder", and
  that must be genuinely sufficient.
- **No sharing or multi-user.** One person, one machine.
- **No filing rules engine.** Suggestions, not automation. Automation here
  quietly misfiles things, which is worse than not helping.
- **No mobile app.** Getting a photo off a phone is a solved problem elsewhere.
- **No scanner import.** Scanning works completely differently on each of the
  three platforms. People can scan with their phone and drag the file in.

## The two design decisions that matter

### 1. Don't store it the way Rolodex does

Rolodex holds text: the whole vault can be one encrypted blob, decrypted into
memory. **Documents are different** — a few hundred scanned PDFs is easily a
gigabyte, and you can't hold that in memory or rewrite it whole every time you
add a receipt.

So: **each document is its own encrypted file, plus one small encrypted index**
holding the metadata and search text. Adding a document writes one new file
and updates the index. Opening one decrypts one file. The index — small,
fast, always loaded — is what search runs against.

Practical consequences worth writing down before you code:

- The index is the crown jewel. Corrupt it and the documents are unreadable
  noise. Write it atomically (write new, fsync, rename), keep the previous
  version, and provide a rebuild-from-documents path as a last resort.
  "Atomic rename" behaves differently on Windows than on Linux and macOS —
  confirm the recipe on all three, not just the one you develop on.
- Document filenames on disk must not leak anything — random IDs, not
  `medical-results-2026.pdf.enc`.
- **Show documents inside Paperkist's own window, decrypted in memory.** Handing a
  document to an outside PDF viewer means writing a decrypted copy to disk,
  and that copy is the weak point of the whole design. The Linux-only answer
  (the user's runtime directory) has no equivalent on Windows or macOS, so
  avoid the copy instead. Writing plaintext to disk happens only when the
  user explicitly exports.
- **The vault format carries a version number from the first release.**
  Strangers' vaults must keep opening after every update, so every format
  change needs a tested migration path.

### 2. Get the crypto decided on day one

Check what Rolodex uses (its README mentions AES via Fernet with a
PBKDF2-derived key) and make a deliberate choice:

- **Match Rolodex** — one crypto approach across both apps, one thing to
  reason about, code you can share.
- **Or use current best practice for a new app** — Argon2id for the key
  derivation (much more resistant to cracking by GPU than PBKDF2) with an
  authenticated cipher.

Both are defensible. What isn't defensible is deciding by accident and finding
out later, because changing it means migrating everyone's vault. Make the call
explicitly, write down why, and if you pick the newer approach, consider
whether Rolodex should follow.

*Leaning, now that it's public: the newer approach.* Matching Rolodex was
mainly a convenience for one developer. For strangers' ID documents and
medical letters, stronger protection against password cracking matters more.

**Don't invent anything here.** Use a well-known library, follow its documented
recipe, and confirm the recipe is the current one — this is precisely the kind
of code where remembered idioms from a few years ago are subtly wrong.

## OCR — the "text inside the document" part

Search that only covers titles and tags is half a product; you want to find
the receipt by typing the appliance's model number. That needs the text pulled
out of scans, via OCR (software that reads text out of a picture).

Treat it as **an optional extra that degrades cleanly**:

- If the OCR tool is installed, extract text on import, store it in the index,
  and search it.
- If it isn't, everything else works and search covers what you typed.
- OCR runs in the background — importing a document must never block on it.
- Digital PDFs usually already contain their text; take that free path first
  and only OCR what needs it.
- On Windows and macOS, nobody has an OCR tool installed already. For the
  feature to reach most users, the installers must ship one. Check its
  licence allows that.

## Build order

1. **Vault format + crypto**, no UI. *Verify: a script that creates a vault,
   adds a file, closes it, reopens with the password, reads the file back
   byte-identical — and fails cleanly on a wrong password. It runs
   automatically on Windows, macOS and Linux from this step on, not just at
   packaging time.*
2. **The index** — metadata, atomic writes, rebuild path. *Verify: kill the
   process mid-write, reopen, vault still intact.*
3. **The window** — add, list, search, open. *Verify: file twenty real
   documents from your own Downloads folder and use it for a week.*
4. **Expiry tracking** — dates, an "upcoming" view, a notification on launch.
   *Verify: a warranty dated next week shows up; one dated last year is
   flagged, not hidden.*
5. **OCR**, optional and in the background. *Verify: search finds a model
   number that only appears inside a scanned image.*
6. **Packaging** — an installer per platform: Flathub for Linux, and signed
   installers for Windows and macOS. *Verify: on a fresh machine for each
   platform, someone who didn't build it installs it and files a document
   without help.*

Step 3 is the real gate: if it isn't pleasant enough that *you* file documents
into it for a week, no amount of feature work fixes that.

## Releasing it to the public

Things a personal tool never needed:

- **Code signing.** Unsigned apps trigger alarming warnings on macOS (which
  needs a paid Apple developer account) and on Windows. Budget for it.
- **Automated testing on all three platforms.** A public GitHub repository
  gets free build minutes, so this costs nothing.
- **A licence**, chosen before the first public commit. Done: GPL-3.0.
- **A name nobody else is using.** Done: Paperkist, after "Folio" and
  "Deedbox" were taken. No trademark contains "Paperkist" in the US
  register (searched 2026-09-28) or in TMview, which covers the EU, UK
  and many national offices (searched 2026-10-08). The nearest,
  PAPERKISS, has expired (DEED-0023).
- **Help written for non-technical people** — especially setup, backup and
  "what happens if I forget my password".
- **A place to report bugs**, and a security contact for vulnerabilities.
- **An independent security review of the crypto and vault code** before the
  first public release. People will trust it with their passports.

## Open questions to settle at kickoff

- **Qt window or local web app?** Rolodex-style Qt keeps it feeling like a
  private desktop thing; Contact_List-style Flask makes the document viewer
  and search UI much easier (browsers render PDFs for free). *Leaning, now
  that it's public: a Qt window.* A web page served on the user's machine can
  be reached by other programs on that machine, and it is hard to lock
  reliably. Qt can also show PDFs inside its own window, which removes the
  decrypted temporary copy (see design decision 1). Decide before step 3.
- **Should it be a Rolodex feature instead?** Rolodex already has a vault and
  a master password. Attachments-in-Rolodex is a real option and would be less
  work. *Leaning: separate — the storage model genuinely differs (see above),
  and a public Paperkist shouldn't force Rolodex to become public too.*
- **How do reminders reach you when the app isn't open?** A background service
  is a big commitment for one notification, and each platform does it
  differently. *Leaning: check on launch in v1. Optional background reminders
  come later, and only if they work on all three platforms.*
- **Multiple vaults?** (household vs personal, say.) *Leaning: one vault, but
  don't hard-code the assumption that there's only ever one path.*

## Prior art worth a look before starting

- `Rolodex/` — the encrypted-vault pattern, master-password UX, cross-platform
  packaging. The single closest thing you own; read its crypto code before
  writing yours.
- `finbreak/` — document/statement parsing, and the "private by default, one
  opt-in network feature" stance this app should copy exactly.
- `Contact_List/` — the local-web-app shape, if you go that way.
- Paperless-ngx's documentation — not to copy the architecture, but its
  feature list is a good checklist of what people actually need, and a good
  list of what to leave out.

## When you start

Set the project up with `start-project`. It needs an empty folder, so move
this brief aside first and bring it back once the project exists. Do step 1
as a spike before committing to anything else — the storage and crypto decisions are the ones that are
expensive to change later, and everything else is ordinary app work.
