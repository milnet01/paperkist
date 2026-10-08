# Security policy — Paperkist

## Trust boundaries

- **The vault folder.** Anyone holding it can change its bytes. Every
  encrypted file is authenticated before use; a changed, cut-off or
  swapped one is refused (`docs/specs/DEED-0002-vault-format.md` § 5).
  The one plain file, the header, holds no secret.
- **The password.** It unlocks the vault key through Argon2id; it is
  never stored (`docs/decisions/ADR-0001-crypto-library.md`).
- **Documents you add.** Stored as data and shown in Paperkist's own
  window; never run.
- **The network.** Paperkist makes no network connections. A planned
  updater (DEED-0024), off until you turn it on, will be the one
  exception; this line changes when it ships.

Paperkist protects the vault at rest. It does not protect a computer that
is already compromised while the vault is open.

## Supported versions

Nothing has been released. Reports against the latest code on the main
branch are welcome.

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's private
vulnerability reporting on this repository: the **Security** tab, then
**Report a vulnerability**.
