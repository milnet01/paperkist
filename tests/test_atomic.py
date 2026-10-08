"""docs/specs/DEED-0003-index-and-recovery.md § 4.4: on Windows a refused
second opener, a virus scanner or an indexer may hold a vault file open
briefly, and Python's `open()` there does not grant delete-sharing, so a
replace or delete over that file fails with `PermissionError` until the
handle closes. `atomic.py` retries for a short bounded time.

On Linux both operations succeed over an open file, so a green run there
proves nothing; the Windows CI runner is what exercises these tests.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from paperkist.vault import atomic

HOLD_DELAY = 0.2  # generous margin: the operations' own work takes microseconds


@contextmanager
def held_open_briefly(path: Path) -> Iterator[None]:
    """Another handle holds `path` open, and closes it HOLD_DELAY later."""
    opened = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with path.open("rb"):
            opened.set()
            release.wait(timeout=5)

    def release_after_delay() -> None:
        time.sleep(HOLD_DELAY)
        release.set()

    holder = threading.Thread(target=hold)
    releaser = threading.Thread(target=release_after_delay)
    holder.start()
    assert opened.wait(timeout=5), "holder never reported the file open"
    releaser.start()
    try:
        yield
    finally:
        release.set()
        holder.join(timeout=5)
        releaser.join(timeout=5)


def test_write_bytes_succeeds_while_target_briefly_open(tmp_path: Path) -> None:
    target = tmp_path / "index"
    target.write_bytes(b"old")

    with held_open_briefly(target):
        atomic.write_bytes(target, b"new")

    assert target.read_bytes() == b"new"
    assert not target.with_name(target.name + ".tmp").exists()


def test_delete_succeeds_while_target_briefly_open(tmp_path: Path) -> None:
    target = tmp_path / "doc.m"
    target.write_bytes(b"old")

    with held_open_briefly(target):
        atomic.delete(target)

    assert not target.exists()
