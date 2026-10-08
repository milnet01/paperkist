# ADR-0001: PyNaCl (libsodium) does all of Paperkist's encryption

- **Status:** Accepted
- **Date:** 2026-09-27

## Context

`docs/brief.md` fixed the approach: Argon2id to turn the password into a
key, and an authenticated cipher. It also said: use a well-known library,
follow its documented recipe, invent nothing.

Documents can be large scans. Encrypting a whole file in one call means
holding it all in memory twice. Splitting a file into pieces and
encrypting each safely is a known recipe — but only if the library
provides it. Writing our own splitting scheme is exactly the invention
the brief forbids.

Two well-known Python libraries were checked on 2026-09-27, by
installing each and inspecting it:

- **`cryptography`** has Argon2id and authenticated ciphers, but only as
  one-shot calls. A large file would need our own splitting scheme.
- **PyNaCl** wraps libsodium. It has Argon2id and libsodium's
  "secretstream" recipe, which encrypts a file as a sequence of pieces
  and lets the reader detect pieces that were removed, reordered or cut
  off.

## Decision

Use PyNaCl for all encryption. Only `src/paperkist/crypto.py` imports it.

- **Keys.** Argon2id turns the password into a key that wraps a random
  vault key, using the single-message encryption below. The vault key
  encrypts everything else. The Argon2id settings, the salt and the
  wrapped vault key form the header record that `vault` stores without
  reading (`docs/design.md`, rule 2). The settings are chosen in build
  step 1 (`docs/brief.md`, Build order).
- **Document content.** Secretstream encrypts each document's content
  file. The reader must reject a stream whose last piece is not tagged
  final: secretstream does not flag a cut-off file by itself. Checked
  2026-09-27 — with the final piece dropped, the first piece still
  decrypted with no error.
- **Everything small.** XChaCha20-Poly1305 single-message encryption
  (`crypto_aead_xchacha20poly1305_ietf`) protects the wrapped vault key,
  the index and each metadata file.
- **Binding.** Every ciphertext carries, as authenticated associated
  data, its role (content, metadata, index or key), its format number
  and — for a document's two files — the document's random id. A file
  moved to another id, or relabelled, fails to decrypt.
- **Layout.** Secretstream's piece size, each file's byte layout and the
  byte encoding of the associated data are part of the vault format,
  fixed by the vault-format spec written for build step 1.

## Consequences

- Rolodex uses `cryptography` with PBKDF2, so the two apps do not share
  crypto code. Whether Rolodex should follow is its own question.
- Changing the password, or raising the Argon2id settings, rewraps the
  vault key and rewrites only the header. No document is re-encrypted.
- A format change to content files re-encrypts every document it
  touches, because the format number is bound into each ciphertext.
- PyNaCl releases less often than `cryptography`. It is a thin wrapper;
  libsodium underneath does the work. If PyNaCl stops being maintained,
  the replacement must still read that vault format. It uses only
  libsodium's Argon2id, secretstream and XChaCha20-Poly1305, with the
  same parameters.
- libsodium is a compiled library, so every installer must ship it.
  PyNaCl's prebuilt packages include it on all three systems.
- The independent security review before the first public release
  (`docs/brief.md`, Releasing it to the public) reviews this choice too.
