"""Unit tests for the Notion operation receipt stub.

No network and no writes except the path a test injects.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from money_machine.observability.receipts import (
    DuplicateReceiptError,
    NotionOperationReceipt,
    NotionOperationReceiptLog,
)

_WHEN = datetime(2026, 9, 26, 1, 2, 3, tzinfo=UTC)


def _receipt(**overrides: object) -> NotionOperationReceipt:
    fields: dict[str, object] = {
        "job_id": "job_1",
        "operation": "create_page",
        "workspace": "ws_1",
        "target": "page_1",
        "pre_state": None,
        "post_state": {"title": "Hello"},
        "provider_response": {"id": "page_1"},
        "evidence": "evidence/page_1",
        "timestamp": _WHEN,
        "idempotency_key": "create_page:job_1",
        "status": "CONFIRMED",
    }
    fields.update(overrides)
    return NotionOperationReceipt(**fields)  # type: ignore[arg-type]


def test_receipt_keeps_section_4_fields() -> None:
    """The typed receipt stores every field from Session 06 prompt section 4."""
    receipt = _receipt(pre_state={"title": None})

    assert receipt.job_id == "job_1"
    assert receipt.operation == "create_page"
    assert receipt.workspace == "ws_1"
    assert receipt.target == "page_1"
    assert receipt.pre_state == {"title": None}
    assert receipt.post_state == {"title": "Hello"}
    assert receipt.provider_response == {"id": "page_1"}
    assert receipt.evidence == "evidence/page_1"
    assert receipt.timestamp == _WHEN
    assert receipt.idempotency_key == "create_page:job_1"
    assert receipt.status == "CONFIRMED"


def test_pre_state_may_be_absent() -> None:
    """Pre-state is optional, matching 'when available' in section 4."""
    receipt = _receipt(pre_state=None)
    assert receipt.pre_state is None


@pytest.mark.parametrize(
    "field_name",
    [
        "job_id",
        "operation",
        "workspace",
        "target",
        "evidence",
        "idempotency_key",
        "status",
    ],
)
def test_required_text_fields_reject_blank(field_name: str) -> None:
    with pytest.raises(ValueError, match=field_name):
        _receipt(**{field_name: "  "})


def test_non_json_payload_is_rejected() -> None:
    with pytest.raises(ValueError, match="JSON-serializable"):
        _receipt(post_state={"when": _WHEN})


def test_record_returns_the_same_receipt_without_a_path(tmp_path: Path) -> None:
    """With no injected path the log keeps the receipt and writes no file."""
    log = NotionOperationReceiptLog()
    receipt = _receipt()

    recorded = log.record(receipt)

    assert recorded is receipt
    assert log.get(receipt.idempotency_key) is receipt
    assert list(tmp_path.iterdir()) == []


def test_duplicate_idempotency_key_is_rejected_and_not_appended(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    log = NotionOperationReceiptLog(path)
    first = _receipt()
    log.record(first)

    with pytest.raises(DuplicateReceiptError, match="create_page:job_1"):
        log.record(_receipt(target="page_2"))

    assert len(log) == 1
    assert path.read_text(encoding="utf-8").count("\n") == 1
    reloaded = NotionOperationReceiptLog(path)
    assert len(reloaded) == 1
    stored = reloaded.get(first.idempotency_key)
    assert stored is not None
    assert stored.target == "page_1"
    assert stored.timestamp == _WHEN
    assert stored.pre_state is None
    assert stored.post_state == {"title": "Hello"}


def test_injected_path_is_the_only_file_written(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "receipts.jsonl"
    path.parent.mkdir()
    log = NotionOperationReceiptLog(path)
    log.record(_receipt(pre_state={"before": True}))

    assert [
        item.relative_to(tmp_path).as_posix() for item in tmp_path.rglob("*") if item.is_file()
    ] == ["nested/receipts.jsonl"]
    reloaded = NotionOperationReceiptLog(path).get("create_page:job_1")
    assert reloaded is not None
    assert reloaded.pre_state == {"before": True}


def test_corrupt_receipt_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not a receipt"):
        NotionOperationReceiptLog(path)
