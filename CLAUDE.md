# Paperkist — instructions for Claude Code

## Where this project is

**State:** 4 — Between items. Roadmap queued (`ROADMAP.md`, 0.1.0 to 1.0.0).
**In flight:** nothing.

> Keep the two lines above true, and keep them to two lines. They are
> the only position this project records. Everything else about where
> work stands is read off things that cannot lie — whether a spec exists,
> whether tests fail, what `git status` says, whether the roadmap bullet
> is 🚧. A recorded step number starts lying the first time a session
> forgets to update it, and still reads as authoritative.
>
> **There is deliberately no `Next:` line.** The next action follows from
> the state — `~/.claude/workflow.md` names what each state leads to —
> and once the roadmap has items, from the roadmap. A hand-kept forward
> pointer is the exact shape the paragraph above rejects, and it goes
> stale first because nothing contradicts it when it does.

## How work is done here

- **`~/.claude/workflow.md`** — the states, the gates, and what "done"
  means. Read in place. This project does not have its own copy.
- **`~/.claude/standards/`** — how to write code, tests, commits,
  documents, releases. Also read in place.

Neither is summarised here. A rule restated in two places is two rules
that will disagree.

## This project's own facts

Everything below is specific to this project, which is why it lives here
rather than in a standard.

### Stack

Python 3.12+, PySide6 (Qt), PyNaCl. `docs/design.md` § The stack owns
the full list and what it rules out.

### Build and test

- The whole gate, as CI runs it: `./scripts/local-ci.sh` (needs `uv`).
- Tests alone: `uv run --locked --group dev pytest -q`.
- Dependencies are pinned in `pyproject.toml` and locked in `uv.lock`.

### Roadmap IDs

`DEED-NNNN`, per `roadmap-format.md` § 3.5.1. Commit subjects
are `<ID>: <description>`, per `commits.md`.

### Overrides

Any place this project deliberately departs from a global standard goes
in `docs/standards/`, with the reason. If that directory is empty, there
are none.
