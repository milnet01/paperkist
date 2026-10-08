# Paperkist

> An encrypted vault on your own computer for receipts, warranties,
> policies and ID — with search, and reminders before things expire.

## Status

Early development. Not ready for use: there is no window yet, and no
installer. The encrypted storage and crash recovery are built and
tested on Linux.

## Install

Not yet installable.

## Documentation

| | |
|---|---|
| [ROADMAP.md](ROADMAP.md) | What is planned, in progress and shipped |
| [CHANGELOG.md](CHANGELOG.md) | What shipped, when |
| [docs/discovery.md](docs/discovery.md) | What this is for, and how we would know it works |
| [docs/design.md](docs/design.md) | The shape — the parts, and what may touch what |
| [docs/decisions/](docs/decisions/) | Why a close call went the way it did |
| [docs/specs/](docs/specs/) | The contract for one feature, where one was needed |
| [SECURITY.md](SECURITY.md) | How to report a security problem |

Paths starting `~/.claude/` point at the author's own workflow standards.
They live on the author's machine and are not published; you can skip them.

## Developing

Needs [uv](https://docs.astral.sh/uv/). `./scripts/local-ci.sh` runs
every check CI runs.

## License

[GPL-3.0](LICENSE) — GNU General Public License, version 3.
