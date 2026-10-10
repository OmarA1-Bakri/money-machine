"""One unpublish lock per run id.

An old lock without a completed exec file refuses a new start. A completed exec
file does not. Trap and finally share the exclusive lock, so exactly one of them
runs the action. A live holder is detected with ``flock``; a lock file left
behind after a crash is not a live holder.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import cast


class RunLockError(RuntimeError):
    """A run cannot start because its lock is already held."""


def lock_path(root: Path, run_id: str) -> Path:
    """Lock file for one run id. This is not a fixed ``gu/run.lock``."""
    return root / f"{run_id}.lock"


def exec_path(root: Path, run_id: str) -> Path:
    """Completion record for one run id."""
    return root / f"{run_id}.exec.json"


def _exec_completed(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(decoded, dict):
        return False
    return cast(dict[str, object], decoded).get("status") == "completed"


def begin_run(root: Path, run_id: str, action: Callable[[], None]) -> bool:
    """Run ``action`` once under this run id's lock. Return whether this caller acted."""
    root.mkdir(parents=True, exist_ok=True)
    held = lock_path(root, run_id)
    finished = exec_path(root, run_id)
    if held.exists() and _exec_completed(finished):
        held.unlink()
    try:
        descriptor = os.open(held, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return _refuse_existing_lock(held, finished)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        action()
        finished.write_text(
            json.dumps({"status": "completed", "run_id": run_id}) + "\n",
            encoding="utf-8",
        )
    finally:
        os.close(descriptor)
    return True


def _refuse_existing_lock(held: Path, finished: Path) -> bool:
    """Return false when a live owner holds the lock. A dead lock without exec raises."""
    probe = os.open(held, os.O_RDWR)
    try:
        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    finally:
        os.close(probe)
    if not _exec_completed(finished):
        raise RunLockError("old lock without a completed exec.json")
    return False
