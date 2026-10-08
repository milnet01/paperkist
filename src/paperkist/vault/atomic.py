"""Write-new, flush, replace: a file is either the old one or the new one.

docs/specs/DEED-0002-vault-format.md § 4.6 and
docs/specs/DEED-0003-index-and-recovery.md § 4.4.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

# How long Windows may keep refusing a replace or delete because another
# handle has the file open: a refused second opener, a virus scanner or an
# indexer, each holding it for a moment (DEED-0003 § 4.4).
IN_USE_WAIT = 2.0


def write_bytes(target: Path, data: bytes) -> None:
    with write_stream(target) as out:
        out.write(data)


@contextmanager
def write_stream(target: Path) -> Iterator[BinaryIO]:
    """Yield a file whose contents replace `target` only on a clean exit.

    The temporary file sits beside the target, so the replace never crosses
    a file system. Any failure removes it and re-raises.
    """
    tmp = target.with_name(target.name + ".tmp")
    try:
        with tmp.open("wb") as out:
            yield out
            out.flush()
            _flush_file(out.fileno())
        _while_in_use(lambda: tmp.replace(target))
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _flush_directory(target.parent)


def delete(path: Path) -> None:
    """Remove `path` so that the removal survives a power cut."""
    _while_in_use(lambda: path.unlink(missing_ok=True))
    _flush_directory(path.parent)


def _while_in_use(operation: Callable[[], object]) -> None:
    # Windows refuses to replace or delete a file another handle has open.
    # Elsewhere a PermissionError is a real refusal and is raised at once.
    deadline = time.monotonic() + IN_USE_WAIT
    while True:
        try:
            operation()
            return
        except PermissionError:
            if os.name != "nt" or time.monotonic() > deadline:
                raise
            time.sleep(0.05)


def _flush_file(fd: int) -> None:
    # macOS fsync leaves data in the drive's own cache; F_FULLFSYNC empties it.
    if fcntl is not None and hasattr(fcntl, "F_FULLFSYNC"):
        fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
    else:
        os.fsync(fd)


def _flush_directory(directory: Path) -> None:
    # Windows has no directory handle to flush.
    if os.name == "nt":
        return
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
