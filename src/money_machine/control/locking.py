"""Portable exclusive file locking for control-state transitions."""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


class ControlLockError(OSError):
    """Raised when the control lock cannot be acquired or released safely."""


def _acquire_lock(lock_file: BinaryIO) -> None:
    if sys.platform == "win32":
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
    else:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _release_lock(lock_file: BinaryIO) -> None:
    if sys.platform == "win32":
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def exclusive_control_lock(path: Path) -> Generator[None]:
    """Hold an exclusive lock at ``path`` for the duration of the context."""
    try:
        lock_file = path.open("a+b")
    except OSError as error:
        raise ControlLockError(f"cannot open control lock {path}: {error}") from error

    with lock_file:
        try:
            if lock_file.seek(0, os.SEEK_END) == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            _acquire_lock(lock_file)
        except OSError as error:
            raise ControlLockError(f"cannot acquire control lock {path}: {error}") from error
        try:
            yield
        finally:
            try:
                _release_lock(lock_file)
            except OSError as error:
                raise ControlLockError(f"cannot release control lock {path}: {error}") from error
