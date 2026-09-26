"""Unit tests for the Notion operation receipt stub.

No network and no writes except the path a test injects.
"""

from __future__ import annotations

import gc
import threading
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from typing import cast

import pytest

from money_machine.observability import receipts as receipts_module
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
        "status": "Success",
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
    assert receipt.status == "Success"


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


def test_reloaded_receipt_round_trips_every_field(tmp_path: Path) -> None:
    """Every section-4 field survives a write and a reload."""
    path = tmp_path / "receipts.jsonl"
    when = datetime(2026, 9, 26, 4, 5, 6, tzinfo=UTC)
    original = _receipt(
        job_id="job-field",
        operation="rename_page",
        workspace="ws-field",
        target="target-field",
        pre_state={"before": "pre"},
        post_state={"after": "post"},
        provider_response={"provider": "ok"},
        evidence="evidence-field",
        timestamp=when,
        idempotency_key="key-field",
        status="Unknown",
    )
    NotionOperationReceiptLog(path).record(original)
    stored = NotionOperationReceiptLog(path).get("key-field")

    assert stored is not None
    assert stored.job_id == "job-field"
    assert stored.operation == "rename_page"
    assert stored.workspace == "ws-field"
    assert stored.target == "target-field"
    assert stored.pre_state == {"before": "pre"}
    assert stored.post_state == {"after": "post"}
    assert stored.provider_response == {"provider": "ok"}
    assert stored.evidence == "evidence-field"
    assert stored.timestamp == when
    assert stored.idempotency_key == "key-field"
    assert stored.status == "Unknown"


class _NullOffset(tzinfo):
    """A tzinfo whose utcoffset is None. That timestamp is not aware."""

    def utcoffset(self, dt: datetime | None) -> timedelta | None:
        return None

    def tzname(self, dt: datetime | None) -> str | None:
        return None

    def dst(self, dt: datetime | None) -> timedelta | None:
        return None


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _receipt(timestamp=datetime(2026, 9, 26, 1, 2, 3))


def test_timestamp_with_null_utcoffset_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _receipt(timestamp=datetime(2026, 9, 26, 1, 2, 3, tzinfo=_NullOffset()))


def test_timestamp_must_be_a_datetime() -> None:
    with pytest.raises(ValueError, match="timestamp must be a datetime"):
        _receipt(timestamp="2026-09-26T01:02:03+00:00")


def test_status_rejects_values_outside_the_enum() -> None:
    with pytest.raises(ValueError, match="status must be Success, Unknown, or Failure"):
        _receipt(status="CONFIRMED")


def test_lowercase_success_status_is_rejected() -> None:
    with pytest.raises(ValueError, match="status must be Success, Unknown, or Failure"):
        _receipt(status="success")


def test_post_state_must_be_a_mapping() -> None:
    with pytest.raises(ValueError, match="post_state"):
        _receipt(post_state="not-a-mapping")


def test_load_rejects_duplicate_idempotency_key(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    log = NotionOperationReceiptLog(path)
    log.record(_receipt())
    line = path.read_text(encoding="utf-8")
    path.write_text(line + line, encoding="utf-8")

    with pytest.raises(DuplicateReceiptError, match="create_page:job_1"):
        NotionOperationReceiptLog(path)


def test_torn_trailing_line_is_skipped(tmp_path: Path) -> None:
    """A crash fragment without a newline is skipped; the prior receipt reloads."""
    path = tmp_path / "receipts.jsonl"
    NotionOperationReceiptLog(path).record(_receipt())
    path.write_text(path.read_text(encoding="utf-8") + '{"idem', encoding="utf-8")

    reloaded = NotionOperationReceiptLog(path)
    assert len(reloaded) == 1
    assert reloaded.get("create_page:job_1") is not None


def test_two_logs_reject_a_duplicate_key_without_corrupting_the_file(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    first = NotionOperationReceiptLog(path)
    second = NotionOperationReceiptLog(path)
    first.record(_receipt())

    with pytest.raises(DuplicateReceiptError, match="create_page:job_1"):
        second.record(_receipt(target="page_2"))

    assert path.read_text(encoding="utf-8").count("\n") == 1
    reloaded = NotionOperationReceiptLog(path)
    assert len(reloaded) == 1
    stored = reloaded.get("create_page:job_1")
    assert stored is not None
    assert stored.target == "page_1"


def test_pre_state_snapshot_is_independent_of_the_caller() -> None:
    """A later mutation of the caller's pre_state does not change the receipt."""
    inner = {"n": 1}
    pre_state = {"items": (inner,)}
    receipt = _receipt(pre_state=pre_state)
    log = NotionOperationReceiptLog()
    log.record(receipt)
    inner["n"] = 9

    stored = log.get(receipt.idempotency_key)
    assert stored is not None
    assert stored.pre_state == {"items": ({"n": 1},)}


def test_complete_json_tail_without_newline_is_kept(tmp_path: Path) -> None:
    """A complete receipt that lacks a trailing newline is still loaded."""
    path = tmp_path / "receipts.jsonl"
    NotionOperationReceiptLog(path).record(_receipt())
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")

    reloaded = NotionOperationReceiptLog(path)
    stored = reloaded.get("create_page:job_1")
    assert stored is not None
    assert stored.target == "page_1"


def test_record_after_torn_tail_round_trips(tmp_path: Path) -> None:
    """Appending after a torn fragment does not glue the next receipt onto it."""
    path = tmp_path / "receipts.jsonl"
    NotionOperationReceiptLog(path).record(_receipt())
    path.write_text(path.read_text(encoding="utf-8") + '{"idem', encoding="utf-8")

    NotionOperationReceiptLog(path).record(_receipt(idempotency_key="key-2", target="page_2"))
    reloaded = NotionOperationReceiptLog(path)
    assert reloaded.get("create_page:job_1") is not None
    stored = reloaded.get("key-2")
    assert stored is not None
    assert stored.target == "page_2"


def test_record_after_complete_line_without_newline_round_trips(tmp_path: Path) -> None:
    """Appending after a complete line with no newline keeps both receipts."""
    path = tmp_path / "receipts.jsonl"
    NotionOperationReceiptLog(path).record(_receipt())
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")

    NotionOperationReceiptLog(path).record(_receipt(idempotency_key="key-2", target="page_2"))
    reloaded = NotionOperationReceiptLog(path)
    first = reloaded.get("create_page:job_1")
    second = reloaded.get("key-2")
    assert first is not None
    assert first.target == "page_1"
    assert second is not None
    assert second.target == "page_2"


def test_caller_dict_mutation_does_not_change_the_stored_receipt() -> None:
    post_state = {"title": "Hello", "nested": {"n": 1}}
    provider_response = {"id": "page_1"}
    receipt = _receipt(post_state=post_state, provider_response=provider_response)
    log = NotionOperationReceiptLog()
    log.record(receipt)
    post_state["title"] = "changed"
    nested = post_state["nested"]
    assert isinstance(nested, dict)
    nested["n"] = 9
    provider_response["id"] = "other"

    stored = log.get(receipt.idempotency_key)
    assert stored is not None
    assert stored.post_state == {"title": "Hello", "nested": {"n": 1}}
    assert stored.provider_response == {"id": "page_1"}


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match="JSON-serializable"):
        _receipt(post_state={"n": bad})


def test_record_waits_for_the_path_lock(tmp_path: Path) -> None:
    """record() holds the path lock, so a second record waits until it is released."""
    path = tmp_path / "receipts.jsonl"
    log = NotionOperationReceiptLog(path)
    lock = log._lock  # pyright: ignore[reportPrivateUsage]
    assert lock is not None
    assert lock.acquire(blocking=False)
    finished = threading.Event()

    def _record() -> None:
        log.record(_receipt(idempotency_key="key-wait"))
        finished.set()

    thread = threading.Thread(target=_record)
    thread.start()
    assert finished.wait(timeout=0.2) is False
    lock.release()
    thread.join(timeout=2)
    assert finished.is_set()
    assert log.get("key-wait") is not None


def test_discarded_log_drops_its_path_lock(tmp_path: Path) -> None:
    """A log that is no longer referenced leaves the path lock registry."""
    path = tmp_path / "receipts.jsonl"
    log: NotionOperationReceiptLog | None = NotionOperationReceiptLog(path)
    key = str(path.resolve())
    registry = receipts_module._PATH_LOCKS  # pyright: ignore[reportPrivateUsage]
    assert key in registry
    del log
    gc.collect()
    assert key not in registry


def test_missing_parent_directory_is_rejected(tmp_path: Path) -> None:
    """A path whose parent directory does not exist is rejected."""
    path = tmp_path / "missing" / "receipts.jsonl"
    with pytest.raises(ValueError, match="parent"):
        NotionOperationReceiptLog(path)


def test_string_path_is_rejected() -> None:
    """A str path is rejected. The log does not create directories for it."""
    with pytest.raises(TypeError, match=r"pathlib\.Path"):
        NotionOperationReceiptLog(cast(Path, "receipts.jsonl"))
