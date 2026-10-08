# Paperkist — Discovery

> **Purpose — so that later, anyone can tell whether the thing being
> built is still the thing that was wanted.**

Not a kick-off document. This is what everything is checked against for
the life of the project, which is why the signs of success below have to
be things you could actually observe.

**This document is a gate.** Design does not start until it is agreed —
`~/.claude/workflow.md` § 2. It passes when a stranger could read it and
say whether a given feature serves it.

**Status:** agreed by the owner, 2026-09-27.
Drawn from `docs/brief.md`; decisions recorded there are not reopened here.

## The problem

Personal paperwork has no safe, findable home. Receipts, warranties,
insurance policies, vehicle papers, ID and medical letters sit in a paper
folder, loose PDFs in Downloads, and photos on a phone.

Two things go wrong:

- **You can't find it.** The appliance breaks and the receipt is nowhere.
- **Dates pass unnoticed.** You learn the warranty ended after it mattered.

The existing answers ask too much. Paperless-ngx needs a Docker server.
Cloud drives put ID documents on someone else's computer. The encrypted
apps with expiry reminders are phone-only (`docs/brief.md`, Prior-art check).

## Who it is for

- **A person who keeps important papers in three half-places** — a folder,
  a Downloads directory, a phone — and can't lay hands on the right one
  when it's needed.
- **A person who has never heard of encryption and won't run a server**,
  but wants their passport scan and medical letters private, on their own
  computer, on Windows, macOS or Linux.
- **The owner.** Rolodex, finbreak and Contact List cover passwords, money
  and people. Paperwork is the missing drawer.

## Signs it is working

- **S1** — Someone who didn't build it installs Paperkist on Windows, macOS
  or Linux, creates a vault and files a first document without help.
- **S2** — Before a vault is created, the app says in plain words that a
  forgotten password means the documents are gone for good.
- **S3** — You find a document by typing something you remember about it —
  a word from its title, tag or note, or a model number printed inside a
  scan — not by browsing. On Windows and macOS this means the installers
  bundle the text-reading (OCR) tool.
- **S4** — Open the app and anything expiring soon is already on screen.
  Something that already expired is marked expired, not hidden.
- **S5** — With the app closed, nothing in the vault folder is readable:
  file names, contents and the documents' own dates are all opaque.
  File sizes and save times on disk stay visible.
- **S6** — Copy the vault folder to another computer, open it with the
  password, and every document is there. That copy is the whole backup.
- **S7** — Any document comes back out as the original file, one at a time
  or the whole vault at once, and opens without Paperkist.
- **S8** — Pull the power mid-filing, and the vault still opens with every
  document filed before that moment.
- **S9** — A vault made with an older release opens in the newest one.
- **S10** — The owner is still filing their own real paperwork into it a
  week after first using it, instead of going back to the Downloads folder.

## What it deliberately does not do

- **No cloud, no sync, no server — ever, not just in the first release.**
  Your documents never leave the machine. The one network use is the
  self-updater, which is off until you turn it on and sends nothing
  about your documents (DEED-0024).
- **No sharing and no multiple users.** One person, one computer.
- **No automatic filing rules.** It suggests; it never files on its own.
  A silent misfile is worse than no help.
- **No phone app.**
- **No scanner import.** Scan with a phone and drag the file in.
- **No reminders while the app is closed**, in the first release. Upcoming
  dates show when the app opens.
- **Not a small Paperless.** Paperless-ngx's feature list is a checklist of
  what people need, not a target to match.
