"""Typed Notion operation receipts.

The shape follows Session 06 prompt section 4, "Implement Notion operation
receipts" (workbook heading of the same name). Each mutation record carries
the fields that section lists. This module does not open network connections
and does not write anywhere except a path the caller injects.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class DuplicateReceiptError(ValueError):
    """Raised when an idempotency key was already recorded."""

    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__(f"idempotency key {idempotency_key!r} is already recorded")


def _require_text(field_name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_datetime(value: object) -> None:
    if not isinstance(value, datetime):
        raise ValueError("timestamp must be a datetime")


def _require_mapping(field_name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return value


def _json_payload(receipt: NotionOperationReceipt) -> dict[str, object]:
    pre_state = (
        None
        if receipt.pre_state is None
        else dict(_require_mapping("pre_state", receipt.pre_state))
    )
    payload: dict[str, object] = {
        "job_id": receipt.job_id,
        "operation": receipt.operation,
        "workspace": receipt.workspace,
        "target": receipt.target,
        "pre_state": pre_state,
        "post_state": dict(_require_mapping("post_state", receipt.post_state)),
        "provider_response": dict(_require_mapping("provider_response", receipt.provider_response)),
        "evidence": receipt.evidence,
        "timestamp": receipt.timestamp.isoformat(),
        "idempotency_key": receipt.idempotency_key,
        "status": receipt.status,
    }
    try:
        json.dumps(payload)
    except TypeError as exc:
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
    status: str

    def __post_init__(self) -> None:
        _require_text("job_id", self.job_id)
        _require_text("operation", self.operation)
        _require_text("workspace", self.workspace)
        _require_text("target", self.target)
        _require_text("evidence", self.evidence)
        _require_text("idempotency_key", self.idempotency_key)
        _require_text("status", self.status)
        _require_datetime(self.timestamp)
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
        status=_text_field(payload, "status"),
    )


class NotionOperationReceiptLog:
    """In-memory receipt log. Persists only when ``path`` is injected."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._by_key: dict[str, NotionOperationReceipt] = {}
        if path is not None and path.is_file():
            self._load(path)

    def record(self, receipt: NotionOperationReceipt) -> NotionOperationReceipt:
        """Record one receipt. Rejects a repeated idempotency key."""
        if receipt.idempotency_key in self._by_key:
            raise DuplicateReceiptError(receipt.idempotency_key)
        if self._path is not None:
            self._append(self._path, receipt)
        self._by_key[receipt.idempotency_key] = receipt
        return receipt

    def get(self, idempotency_key: str) -> NotionOperationReceipt | None:
        """Return the receipt stored under ``idempotency_key``, if any."""
        return self._by_key.get(idempotency_key)

    def __len__(self) -> int:
        return len(self._by_key)

    def _load(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} line {line_number} is not a receipt") from exc
            receipt = _receipt_from_payload(payload)
            if receipt.idempotency_key in self._by_key:
                raise DuplicateReceiptError(receipt.idempotency_key)
            self._by_key[receipt.idempotency_key] = receipt

    @staticmethod
    def _append(path: Path, receipt: NotionOperationReceipt) -> None:
        line = json.dumps(_json_payload(receipt), sort_keys=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
