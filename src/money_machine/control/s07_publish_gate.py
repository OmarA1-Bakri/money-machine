"""Pre-publish routine gate for the Session 07 unpublish deadline.

"Omar notified" means ``omar_notified_at`` is a non-empty string. This gate does
not verify that a message was delivered. Navigate wiring is a later phase; this
module only decides whether a browser write may proceed.
"""

from __future__ import annotations

import json
import os
import stat
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

ROUTINE_FIELDS = (
    "deadline_routine_id",
    "deadline_at",
    "reminder_routine_id",
    "reminder_at",
    "routine_created_at",
    "omar_notified_at",
)


class PublishGateError(ValueError):
    """The routine file does not authorise a browser write."""


def _parse_time(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise PublishGateError(f"{field} must be an RFC3339 timestamp")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise PublishGateError(f"{field} must be an RFC3339 timestamp") from error
    if parsed.tzinfo is None:
        raise PublishGateError(f"{field} must be timezone-aware")
    return parsed


def validate_publish_routine(path: Path, *, now: datetime, owner_uid: int) -> dict[str, object]:
    """Refuse unless the routine file is fresh, private, owned, and notified."""
    if path.is_symlink() or not path.is_file():
        raise PublishGateError("routine file must be a regular non-symlink file")
    info = path.lstat()
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise PublishGateError("routine file mode must be 0600")
    if info.st_uid != owner_uid:
        raise PublishGateError("routine file must be owned by the operator")
    try:
        decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PublishGateError(f"routine file is not JSON: {error}") from error
    if not isinstance(decoded, dict):
        raise PublishGateError("routine file must be an object")
    document = cast(dict[str, object], decoded)
    if set(document) != set(ROUTINE_FIELDS):
        raise PublishGateError("routine file fields must match the frozen set")
    notified = document["omar_notified_at"]
    if not isinstance(notified, str) or notified == "":
        raise PublishGateError("omar_notified_at must be set")
    for field in ("deadline_routine_id", "reminder_routine_id"):
        if not isinstance(document[field], str) or document[field] == "":
            raise PublishGateError(f"{field} must be set")
    created = _parse_time(document["routine_created_at"], "routine_created_at")
    deadline = _parse_time(document["deadline_at"], "deadline_at")
    reminder = _parse_time(document["reminder_at"], "reminder_at")
    if not created <= now <= created + timedelta(minutes=60):
        raise PublishGateError("routine file is not fresh")
    if not now < deadline <= now + timedelta(hours=23):
        raise PublishGateError("deadline must be within the next 23 hours")
    if reminder > deadline - timedelta(hours=3):
        raise PublishGateError("reminder must be at least 3 hours before the deadline")
    return document


def guarded_browser_write(
    path: Path,
    write: Callable[[], None],
    *,
    now: datetime,
    owner_uid: int,
    wait_seconds: float = 0,
) -> None:
    """Call ``write`` only after the routine file validates. ``wait_seconds`` is the poll cap."""
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            validate_publish_routine(path, now=now, owner_uid=owner_uid)
            break
        except PublishGateError:
            if time.monotonic() >= deadline:
                raise
            remaining = deadline - time.monotonic()
            time.sleep(min(0.05, remaining))
    write()


def write_routine_file(
    path: Path, document: dict[str, object], *, owner_uid: int | None = None
) -> None:
    """Write a routine file at mode 0600. Tests use this; production runners do too."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(document, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)
    if owner_uid is not None and hasattr(os, "chown"):
        os.chown(path, owner_uid, path.stat().st_gid)
