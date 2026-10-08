# ADR-0002: Paperkist is written in Python, with PySide6 for the window

- **Status:** Accepted
- **Date:** 2026-09-27

## Context

The Qt window was already decided (`docs/brief.md`). Qt can be used from
C++, its own language, or from Python. The owner's other apps — Rolodex
and finbreak — are Python, and Rolodex already builds installers for
Windows, macOS and Linux.

## Decision

Python, chosen by the owner on 2026-09-27, with PySide6 as the Qt binding.

## Consequences

- Faster to build and change. Rolodex's PyInstaller approach carries
  over for Windows and macOS; Linux ships as a Flatpak (`docs/design.md`,
  the stack).
- Python 3.12 is the floor: 3.10's security support ends in October
  2026 and 3.11's in October 2027 (PEPs 619 and 664). The ceiling is
  whatever the pinned PySide6 supports — 6.11.2 requires Python below
  3.15. Package metadata and the CI matrix state both bounds, and move
  the ceiling only when PySide6 is bumped.
- Installers are larger and start-up is slower than a C++ build.
- Python cannot guarantee decrypted data is wiped from memory. Paperkist
  protects the vault at rest, not a machine already compromised while the
  vault is open.
- Rolodex uses GTK, not Qt, so no window code is shared with it.
