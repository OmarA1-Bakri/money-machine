"""Test 46: one lock per run id. Trap and finally run the action once."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from money_machine.control.s07_run_lock import RunLockError, begin_run, exec_path, lock_path


def test_46_trap_and_finally_run_once_and_a_stale_lock_is_refused(tmp_path: Path) -> None:
    """The live twin does not act. A leftover lock without exec.json refuses a new start."""
    root = tmp_path / "gu"
    acted: list[str] = []

    def second() -> None:
        acted.append("finally")

    def first() -> None:
        acted.append("trap")
        assert begin_run(root, "run-1", second) is False

    assert begin_run(root, "run-1", first) is True
    assert acted == ["trap"]
    assert lock_path(root, "run-1").is_file()
    assert exec_path(root, "run-1").is_file()

    again: list[str] = []
    assert begin_run(root, "run-1", lambda: again.append("again")) is True
    assert again == ["again"]

    other: list[str] = []
    assert begin_run(root, "run-2", lambda: other.append("other")) is True
    assert other == ["other"]
    assert lock_path(root, "run-2") != lock_path(root, "run-1")

    stale = tmp_path / "stale"
    stale.mkdir()
    descriptor = os.open(lock_path(stale, "run-old"), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    with pytest.raises(RunLockError, match=r"old lock without a completed exec\.json"):
        begin_run(stale, "run-old", lambda: acted.append("stale"))
    assert "stale" not in acted
    assert "finally" not in acted
