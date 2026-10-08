# Changelog

All notable changes to Paperkist are documented in this file.

The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). The format
contract is `~/.claude/standards/changelog-format.md` § 4.

The `[Unreleased]` block stays at the top, always, even when empty.

## [Unreleased]

### Added

- **An encrypted vault for documents** (DEED-0002)
  Documents are stored encrypted in a vault folder, unlocked by one
  password. With the app closed, nothing in the folder is readable:
  not the names, the contents or the documents' own dates.

- **A vault survives a crash or power cut** (DEED-0003)
  Paperkist keeps a catalogue of the vault and repairs whatever an
  interrupted save left behind the next time the vault opens, so every
  document filed before a crash is still there. Only one copy of the
  app can have a vault open at a time.

- **Vaults made by an older release open in a newer one** (DEED-0004)
  A newer Paperkist upgrades an older vault the first time it opens it,
  rewriting only the kinds of file whose format changed. An upgrade cut
  off by a crash or power cut carries on at the next open.

### Changed

- **The app is now called Paperkist** (DEED-0023)
  Its old name, Deedbox, was taken by other software. Vaults made
  under the old name still open.
