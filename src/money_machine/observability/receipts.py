"""Typed Notion operation receipts.

The shape follows Session 06 prompt section 4, "Implement Notion operation
receipts" (workbook heading of the same name). Each record carries the fields
that section lists. Status is Success, Unknown, or Failure. Timestamps are
timezone-aware. This module does not open network connections and does not
write anywhere except a path the caller injects.

A trailing partial line that is not valid JSON and is not newline-terminated
is a torn write from a crash. Load skips that tail. Before the next append,
and while the path lock is held, that fragment is truncated in place and a
complete JSON line that lacks a newline gets one. The valid prefix is not
rewritten. A newline-terminated line that is not JSON is rejected.

Writers of one resolved path in this process share one lock object and re-read
the file before appending, so two log instances cannot record the same
idempotency key. A different path gets a different lock. The lock registry
holds those locks weakly. Each log keeps a strong reference for its lifetime,
and a discarded path leaves the registry. The stub does not coordinate writers
in other processes. The path must be a ``pathlib.Path`` whose parent directory
already exists. Nested mappings, lists, and tuples are frozen before store.
More than 32 levels below the field mapping is rejected. That is 33 nested
containers accepted, counting the field mapping as level 0, and 34 rejected.
Mapping keys must be strings at every level. Recorded lines are pure ASCII.
"""

from __future__ import annotations

import json
import os
import threading
import weakref
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Literal

ReceiptStatus = Literal["Success", "Unknown", "Failure"]
_STATUSES: frozenset[str] = frozenset({"Success", "Unknown", "Failure"})

_PATH_LOCKS: weakref.WeakValueDictionary[str, threading.Lock] = weakref.WeakValueDictionary()
_LOCKS_GUARD = threading.Lock()
_MAX_RECEIPT_DEPTH = 32


class DuplicateReceiptError(ValueError):
    """Raised when an idempotency key was already recorded."""

    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__(f"idempotency key {idempotency_key!r} is already recorded")


def _require_path(path: object) -> Path:
    if not isinstance(path, Path):
        raise TypeError("receipt path must be a pathlib.Path")
    if not path.parent.is_dir():
        raise ValueError(f"receipt path parent is not a directory: {path.parent}")
    return path


def _path_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PATH_LOCKS[key] = lock
        return lock


def _require_text(field_name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_datetime(value: object) -> None:
    if not isinstance(value, datetime):
        raise ValueError("timestamp must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("timestamp must be timezone-aware")


def _require_status(value: object) -> None:
    if value not in _STATUSES:
        raise ValueError("status must be Success, Unknown, or Failure")


def _require_mapping(field_name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return value


def _freeze_value(value: object, *, depth: int, seen: set[int]) -> object:
    if isinstance(value, Mapping):
        return _freeze_mapping(value, depth=depth, seen=seen)
    if isinstance(value, list | tuple):
        return _freeze_sequence(value, depth=depth, seen=seen)
    return value


def _reject_reentry(marker: int, seen: set[int]) -> None:
    if marker in seen:
        raise ValueError("receipt fields must be JSON-serializable")
    seen.add(marker)


def _freeze_sequence(
    value: list[object] | tuple[object, ...],
    *,
    depth: int,
    seen: set[int],
) -> tuple[object, ...]:
    if depth > _MAX_RECEIPT_DEPTH:
        raise ValueError("more than 32 levels below the field mapping is rejected")
    marker = id(value)
    _reject_reentry(marker, seen)
    try:
        return tuple(_freeze_value(item, depth=depth + 1, seen=seen) for item in value)
    finally:
        seen.remove(marker)


def _freeze_mapping[MappingKey](
    value: Mapping[MappingKey, object],
    *,
    depth: int,
    seen: set[int],
) -> Mapping[str, object]:
    if depth > _MAX_RECEIPT_DEPTH:
        raise ValueError("more than 32 levels below the field mapping is rejected")
    marker = id(value)
    _reject_reentry(marker, seen)
    try:
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("receipt mapping keys must be strings")
            frozen[key] = _freeze_value(item, depth=depth + 1, seen=seen)
        return MappingProxyType(frozen)
    finally:
        seen.remove(marker)


def _snapshot_mapping(field_name: str, value: object) -> Mapping[str, object]:
    mapping = _require_mapping(field_name, value)
    return _freeze_mapping(mapping, depth=0, seen=set())


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _json_payload(receipt: NotionOperationReceipt) -> dict[str, object]:
    pre_state = None if receipt.pre_state is None else _plain(receipt.pre_state)
    payload: dict[str, object] = {
        "job_id": receipt.job_id,
        "operation": receipt.operation,
        "workspace": receipt.workspace,
        "target": receipt.target,
        "pre_state": pre_state,
        "post_state": _plain(receipt.post_state),
        "provider_response": _plain(receipt.provider_response),
        "evidence": receipt.evidence,
        "timestamp": receipt.timestamp.isoformat(),
        "idempotency_key": receipt.idempotency_key,
        "status": receipt.status,
    }
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("receipt fields must be JSON-serializable") from exc
    return payload


@dataclass(frozen=True, slots=True)
class NotionOperationReceipt:
    """One Notion mutation receipt. Fields match Session 06 prompt section 4."""

    job_id: str
    operation: str
    workspace: str
    target: str
    pre_state: Mapping[str, object] | None
    post_state: Mapping[str, object]
    provider_response: Mapping[str, object]
    evidence: str
    timestamp: datetime
    idempotency_key: str
    status: ReceiptStatus

    def __post_init__(self) -> None:
        _require_text("job_id", self.job_id)
        _require_text("operation", self.operation)
        _require_text("workspace", self.workspace)
        _require_text("target", self.target)
        _require_text("evidence", self.evidence)
        _require_text("idempotency_key", self.idempotency_key)
        _require_status(self.status)
        _require_datetime(self.timestamp)
        pre_state = (
            None if self.pre_state is None else _snapshot_mapping("pre_state", self.pre_state)
        )
        object.__setattr__(self, "pre_state", pre_state)
        object.__setattr__(self, "post_state", _snapshot_mapping("post_state", self.post_state))
        object.__setattr__(
            self,
            "provider_response",
            _snapshot_mapping("provider_response", self.provider_response),
        )
        _json_payload(self)


def _text_field(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _mapping_field(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    return value


def _status_field(payload: dict[str, object]) -> ReceiptStatus:
    status = _text_field(payload, "status")
    if status == "Success":
        return "Success"
    if status == "Unknown":
        return "Unknown"
    if status == "Failure":
        return "Failure"
    raise ValueError("status must be Success, Unknown, or Failure")


def _receipt_from_payload(payload: object) -> NotionOperationReceipt:
    if not isinstance(payload, dict):
        raise ValueError("receipt record must be a JSON object")
    timestamp = payload.get("timestamp")
    if not isinstance(timestamp, str):
        raise ValueError("receipt timestamp must be a string")
    pre_state = payload.get("pre_state")
    if pre_state is not None and not isinstance(pre_state, dict):
        raise ValueError("pre_state must be a JSON object or null")
    return NotionOperationReceipt(
        job_id=_text_field(payload, "job_id"),
        operation=_text_field(payload, "operation"),
        workspace=_text_field(payload, "workspace"),
        target=_text_field(payload, "target"),
        pre_state=pre_state,
        post_state=_mapping_field(payload, "post_state"),
        provider_response=_mapping_field(payload, "provider_response"),
        evidence=_text_field(payload, "evidence"),
        timestamp=datetime.fromisoformat(timestamp),
        idempotency_key=_text_field(payload, "idempotency_key"),
        status=_status_field(payload),
    )


def _complete_json(line: str) -> bool:
    try:
        json.loads(line)
    except json.JSONDecodeError:
        return False
    return True


def _log_text(data: bytes) -> str:
    """Decode a receipt log, skipping a torn tail that is not valid UTF-8."""
    if data.endswith(b"\n"):
        return data.decode("utf-8")
    newline = data.rfind(b"\n")
    prefix = data[: newline + 1]
    tail = data[newline + 1 :]
    try:
        tail_text = tail.decode("utf-8")
    except UnicodeDecodeError:
        return prefix.decode("utf-8")
    return prefix.decode("utf-8") + tail_text


def _logical_lines(text: str) -> list[str]:
    """Receipt lines. A torn tail is skipped; a complete JSON tail is kept."""
    if not text:
        return []
    lines = text.splitlines()
    if text.endswith("\n") or not lines:
        return lines
    if _complete_json(lines[-1]):
        return lines
    return lines[:-1]


def _repair_tail(path: Path) -> None:
    """Prepare a file for append without rewriting its valid prefix.

    A complete last line that lacks a newline gets one appended. A torn
    fragment is truncated in place. The bytes before that fragment stay put.
    """
    if not path.is_file():
        return
    with path.open("rb+") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        if size == 0:
            return
        handle.seek(size - 1)
        if handle.read(1) == b"\n":
            return
        handle.seek(0)
        data = handle.read()
        newline = data.rfind(b"\n")
        tail = data[newline + 1 :]
        try:
            json.loads(tail.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            handle.truncate(newline + 1)
            return
        handle.seek(0, os.SEEK_END)
        handle.write(b"\n")


class NotionOperationReceiptLog:
    """In-memory receipt log. Persists only when ``path`` is injected.

    A torn trailing line (not valid JSON, and not newline-terminated) is
    skipped on load and truncated before the next append. An incomplete UTF-8
    tail is skipped the same way. A complete JSON line
    with no trailing newline is kept, and a newline is written before the next
    append. Complete corrupt lines are rejected.     Instances that share a path
    in this process lock that path and re-read it before appending. The log
    keeps that lock alive; discarding the log drops the path from the registry.
    ``path`` must be a ``pathlib.Path`` whose parent directory already exists.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._by_key: dict[str, NotionOperationReceipt] = {}
        if path is None:
            self._path: Path | None = None
            self._lock: threading.Lock | None = None
            return
        checked = _require_path(path)
        self._path = checked
        self._lock = _path_lock(checked)
        if checked.is_file():
            with self._lock:
                self._load(checked)

    def record(self, receipt: NotionOperationReceipt) -> NotionOperationReceipt:
        """Record one receipt. Rejects a repeated idempotency key."""
        if self._path is None or self._lock is None:
            return self._store(receipt)
        with self._lock:
            self._load_new_keys(self._path)
            return self._store(receipt)

    def get(self, idempotency_key: str) -> NotionOperationReceipt | None:
        """Return the receipt stored under ``idempotency_key``, if any."""
        return self._by_key.get(idempotency_key)

    def __len__(self) -> int:
        return len(self._by_key)

    def _store(self, receipt: NotionOperationReceipt) -> NotionOperationReceipt:
        if receipt.idempotency_key in self._by_key:
            raise DuplicateReceiptError(receipt.idempotency_key)
        if self._path is not None:
            self._append(self._path, receipt)
        self._by_key[receipt.idempotency_key] = receipt
        return receipt

    def _load(self, path: Path) -> None:
        self._by_key.clear()
        self._load_new_keys(path)

    def _load_new_keys(self, path: Path) -> None:
        if not path.is_file():
            return
        text = _log_text(path.read_bytes())
        seen_in_file: set[str] = set()
        for line_number, line in enumerate(_logical_lines(text), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except (json.JSONDecodeError, RecursionError) as exc:
                raise ValueError(f"{path} line {line_number} is not a receipt") from exc
            receipt = _receipt_from_payload(payload)
            key = receipt.idempotency_key
            if key in seen_in_file:
                raise DuplicateReceiptError(key)
            seen_in_file.add(key)
            if key not in self._by_key:
                self._by_key[key] = receipt

    @staticmethod
    def _append(path: Path, receipt: NotionOperationReceipt) -> None:
        _repair_tail(path)
        line = json.dumps(
            _json_payload(receipt),
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
        )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
