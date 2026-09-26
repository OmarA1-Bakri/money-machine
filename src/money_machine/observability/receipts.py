"""Typed Notion operation receipts.

The shape follows Session 06 prompt section 4, "Implement Notion operation
receipts" (workbook heading of the same name). Each record carries the fields
that section lists. Status is Success, Unknown, or Failure. Timestamps are
timezone-aware. This module does not open network connections and does not
write anywhere except a path the caller injects.

A trailing partial line that is not valid JSON and is not newline-terminated
is a torn write from a crash. Load skips that tail, and the next append
truncates it before writing. A complete JSON line that lacks a trailing
newline is kept on load, and a newline is added before the next append.
A newline-terminated line that is not JSON is rejected.

Writers of one path in this process share a lock and re-read the file before
appending, so two log instances cannot record the same idempotency key. The
stub does not coordinate writers in other processes.
"""

from __future__ import annotations

import copy
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Literal

ReceiptStatus = Literal["Success", "Unknown", "Failure"]
_STATUSES: frozenset[str] = frozenset({"Success", "Unknown", "Failure"})

_PATH_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


class DuplicateReceiptError(ValueError):
    """Raised when an idempotency key was already recorded."""

    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__(f"idempotency key {idempotency_key!r} is already recorded")


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


def _freeze_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    return value


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    frozen = {key: _freeze_value(item) for key, item in value.items()}
    return MappingProxyType(frozen)


def _snapshot_mapping(field_name: str, value: object) -> Mapping[str, object]:
    mapping = _require_mapping(field_name, value)
    return _freeze_mapping(copy.deepcopy(dict(mapping)))


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
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
    """Truncate a torn fragment, or terminate a complete last line, before append."""
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if not text or text.endswith("\n"):
        return
    lines = text.splitlines()
    if _complete_json(lines[-1]):
        path.write_text(text + "\n", encoding="utf-8")
        return
    kept = "\n".join(lines[:-1])
    if kept:
        kept += "\n"
    path.write_text(kept, encoding="utf-8")


class NotionOperationReceiptLog:
    """In-memory receipt log. Persists only when ``path`` is injected.

    A torn trailing line (not valid JSON, and not newline-terminated) is
    skipped on load and truncated before the next append. A complete JSON line
    with no trailing newline is kept, and a newline is written before the next
    append. Complete corrupt lines are rejected. Instances that share a path
    in this process lock that path and re-read it before appending.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._by_key: dict[str, NotionOperationReceipt] = {}
        if path is not None and path.is_file():
            with _path_lock(path):
                self._load(path)

    def record(self, receipt: NotionOperationReceipt) -> NotionOperationReceipt:
        """Record one receipt. Rejects a repeated idempotency key."""
        if self._path is None:
            return self._store(receipt)
        with _path_lock(self._path):
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
        text = path.read_text(encoding="utf-8")
        seen_in_file: set[str] = set()
        for line_number, line in enumerate(_logical_lines(text), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
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
        line = json.dumps(_json_payload(receipt), sort_keys=True, allow_nan=False)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
