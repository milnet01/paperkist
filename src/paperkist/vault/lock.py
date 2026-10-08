"""One open copy of a vault at a time, by an OS lock the OS drops on exit.

docs/specs/DEED-0003-index-and-recovery.md § 4.6 step 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

from paperkist.errors import VaultInUse

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


class VaultLock:
    """Held from construction until `release`."""

    def __init__(self, path: Path) -> None:
        self._file = path.open("a+b")
        try:
            if sys.platform == "win32":
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as err:
            self._file.close()
            raise VaultInUse(str(path.parent)) from err

    def release(self) -> None:
        if self._file.closed:
            return
        if sys.platform == "win32":
            self._file.seek(0)
            msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        self._file.close()
