"""Test 45: the pre-publish routine gate refuses a browser write until the file is valid."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from money_machine.control.s07_publish_gate import (
    PublishGateError,
    guarded_browser_write,
    validate_publish_routine,
    write_routine_file,
)

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def _document(**overrides: object) -> dict[str, object]:
    created = NOW
    deadline = NOW + timedelta(hours=10)
    document: dict[str, object] = {
        "deadline_routine_id": "deadline-1",
        "deadline_at": deadline.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reminder_routine_id": "reminder-1",
        "reminder_at": (deadline - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "routine_created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "omar_notified_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    document.update(overrides)
    return document


def _write(path: Path, document: dict[str, object] | None = None) -> None:
    write_routine_file(path, _document() if document is None else document, owner_uid=os.getuid())


def _assert_zero_writes(path: Path) -> None:
    writes: list[str] = []
    with pytest.raises(PublishGateError):
        guarded_browser_write(
            path,
            lambda: writes.append("wrote"),
            now=NOW,
            owner_uid=os.getuid(),
            wait_seconds=0,
        )
    assert writes == []


def test_45_missing_stale_deadline_mode_symlink_field_owner_and_valid(tmp_path: Path) -> None:
    """A browser write happens only for a fresh, private, owned, notified routine file."""
    missing = tmp_path / "missing.json"
    _assert_zero_writes(missing)

    stale = tmp_path / "stale.json"
    created = NOW - timedelta(minutes=61)
    _write(
        stale,
        _document(routine_created_at=created.strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    _assert_zero_writes(stale)

    past = tmp_path / "past.json"
    past_deadline = NOW - timedelta(minutes=1)
    _write(
        past,
        _document(
            deadline_at=past_deadline.strftime("%Y-%m-%dT%H:%M:%SZ"),
            reminder_at=(past_deadline - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )
    past_writes: list[str] = []
    with pytest.raises(PublishGateError, match="within the next 23 hours"):
        guarded_browser_write(
            past,
            lambda: past_writes.append("wrote"),
            now=NOW,
            owner_uid=os.getuid(),
            wait_seconds=0,
        )
    assert past_writes == []

    too_far = tmp_path / "far.json"
    far_deadline = NOW + timedelta(hours=23, minutes=1)
    _write(
        too_far,
        _document(
            deadline_at=far_deadline.strftime("%Y-%m-%dT%H:%M:%SZ"),
            reminder_at=(far_deadline - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )
    _assert_zero_writes(too_far)

    wrong_mode = tmp_path / "mode.json"
    _write(wrong_mode)
    os.chmod(wrong_mode, 0o644)
    _assert_zero_writes(wrong_mode)

    target = tmp_path / "target.json"
    _write(target)
    link = tmp_path / "link.json"
    link.symlink_to(target)
    link_writes: list[str] = []
    with pytest.raises(PublishGateError, match="non-symlink"):
        guarded_browser_write(
            link,
            lambda: link_writes.append("wrote"),
            now=NOW,
            owner_uid=os.getuid(),
            wait_seconds=0,
        )
    assert link_writes == []

    missing_field = tmp_path / "fields.json"
    document = _document()
    del document["reminder_routine_id"]
    write_routine_file(missing_field, document, owner_uid=os.getuid())
    _assert_zero_writes(missing_field)

    quiet = tmp_path / "quiet.json"
    _write(quiet, _document(omar_notified_at=""))
    _assert_zero_writes(quiet)

    owned = tmp_path / "owned.json"
    _write(owned)
    writes: list[str] = []
    with pytest.raises(PublishGateError, match="owned by the operator"):
        guarded_browser_write(
            owned,
            lambda: writes.append("wrote"),
            now=NOW,
            owner_uid=os.getuid() + 1,
            wait_seconds=0,
        )
    assert writes == []

    valid = tmp_path / "valid.json"
    _write(valid)
    info = valid.lstat()
    assert info.st_uid == os.getuid()
    assert oct(info.st_mode & 0o777) == "0o600"
    parsed = validate_publish_routine(valid, now=NOW, owner_uid=os.getuid())
    assert parsed["omar_notified_at"] != ""
    guarded_browser_write(
        valid,
        lambda: writes.append("wrote"),
        now=NOW,
        owner_uid=os.getuid(),
        wait_seconds=0,
    )
    assert writes == ["wrote"]
    assert json.loads(valid.read_text(encoding="utf-8"))["deadline_routine_id"] == "deadline-1"
