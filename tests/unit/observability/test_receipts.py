"""Unit tests for the Notion operation receipt stub.

No network and no writes except the path a test injects.
"""

from __future__ import annotations

import gc
import json
import os
import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from types import MappingProxyType
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


def test_nested_list_and_mapping_are_frozen() -> None:
    """A mapping nested through a list and a tuple cannot be mutated at any depth."""
    inner = {"title": "old"}
    receipt = _receipt(post_state={"level": [{"wrap": (inner,)}]})
    log = NotionOperationReceiptLog()
    log.record(receipt)
    inner["title"] = "NEW"

    stored = log.get(receipt.idempotency_key)
    assert stored is not None
    level = stored.post_state["level"]
    assert isinstance(level, tuple)
    wrap = level[0]["wrap"]
    assert isinstance(wrap, tuple)
    nested = wrap[0]
    assert isinstance(nested, MappingProxyType)
    assert nested["title"] == "old"
    assignment = cast(dict[str, object], nested)
    with pytest.raises(TypeError):
        assignment["title"] = "NEW"


def test_tuple_nested_mapping_is_frozen() -> None:
    """A mapping inside a tuple is copied and cannot be mutated in place."""
    inner = {"title": "old"}
    receipt = _receipt(post_state={"items": (inner,)})
    log = NotionOperationReceiptLog()
    log.record(receipt)
    inner["title"] = "NEW"

    stored = log.get(receipt.idempotency_key)
    assert stored is not None
    items = stored.post_state["items"]
    assert isinstance(items, tuple)
    nested = items[0]
    assert isinstance(nested, MappingProxyType)
    assert nested["title"] == "old"
    assignment = cast(dict[str, object], nested)
    with pytest.raises(TypeError):
        assignment["title"] = "NEW"


def test_non_string_mapping_keys_are_rejected() -> None:
    """A mapping whose keys are not strings is rejected before store."""
    ambiguous = cast(dict[str, object], {1: "int", "1": "str"})
    with pytest.raises(ValueError, match="keys must be strings"):
        _receipt(post_state=ambiguous)


def test_nested_non_string_mapping_keys_are_rejected() -> None:
    """A non-string key inside a nested mapping or tuple is rejected."""
    nested = cast(dict[str, object], {"items": ({1: "int"},)})
    with pytest.raises(ValueError, match="keys must be strings"):
        _receipt(post_state=nested)


def test_complete_json_tail_without_newline_is_kept(tmp_path: Path) -> None:
    """A complete receipt that lacks a trailing newline is still loaded."""
    path = tmp_path / "receipts.jsonl"
    NotionOperationReceiptLog(path).record(_receipt())
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")

    reloaded = NotionOperationReceiptLog(path)
    stored = reloaded.get("create_page:job_1")
    assert stored is not None
    assert stored.target == "page_1"


def _record_three(path: Path) -> tuple[bytes, tuple[str, ...]]:
    """Write three valid receipts and return their exact on-disk prefix."""
    keys = ("key-1", "key-2", "key-3")
    log = NotionOperationReceiptLog(path)
    for index, key in enumerate(keys, start=1):
        log.record(_receipt(idempotency_key=key, target=f"page_{index}"))
    prefix = path.read_bytes()
    assert prefix.endswith(b"\n")
    assert _stored_keys(prefix) == keys
    return prefix, keys


def _assert_loaded_keys(log: NotionOperationReceiptLog, keys: tuple[str, ...]) -> None:
    assert len(log) == len(keys)
    for index, key in enumerate(keys, start=1):
        stored = log.get(key)
        assert stored is not None
        assert stored.target == f"page_{index}"


def _stored_keys(blob: bytes) -> tuple[str, ...]:
    keys: list[str] = []
    for line in blob.decode("utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        key = payload["idempotency_key"]
        if not isinstance(key, str):
            raise AssertionError("idempotency_key")
        keys.append(key)
    return tuple(keys)


def _reject_later_duplicate(path: Path, before: bytes) -> None:
    with pytest.raises(ValueError, match="key-3") as caught:
        NotionOperationReceiptLog(path).record(_receipt(idempotency_key="key-3", target="other"))
    assert type(caught.value) is DuplicateReceiptError
    assert path.read_bytes() == before


def test_record_after_torn_tail_round_trips(tmp_path: Path) -> None:
    """Appending after a torn fragment keeps every earlier line."""
    path = tmp_path / "receipts.jsonl"
    prefix, keys = _record_three(path)
    path.write_bytes(prefix + b'{"idem')

    reloaded = NotionOperationReceiptLog(path)
    _assert_loaded_keys(reloaded, keys)
    _reject_later_duplicate(path, prefix + b'{"idem')

    reloaded.record(_receipt(idempotency_key="key-4", target="page_4"))
    raw = path.read_bytes()
    assert raw.startswith(prefix)
    assert b'{"idem' not in raw
    assert _stored_keys(raw) == (*keys, "key-4")
    again = NotionOperationReceiptLog(path)
    _assert_loaded_keys(again, (*keys, "key-4"))


def test_incomplete_utf8_tail_is_skipped(tmp_path: Path) -> None:
    """An incomplete UTF-8 tail is skipped on load and truncated before append."""
    path = tmp_path / "receipts.jsonl"
    prefix, keys = _record_three(path)
    torn = prefix + b"\xc3"
    path.write_bytes(torn)

    reloaded = NotionOperationReceiptLog(path)
    _assert_loaded_keys(reloaded, keys)
    _reject_later_duplicate(path, torn)

    reloaded.record(_receipt(idempotency_key="key-4", target="page_4"))
    raw = path.read_bytes()
    assert raw.startswith(prefix)
    assert b"\xc3" not in raw
    assert _stored_keys(raw) == (*keys, "key-4")
    again = NotionOperationReceiptLog(path)
    _assert_loaded_keys(again, (*keys, "key-4"))


def test_deeply_nested_torn_tail_is_skipped(tmp_path: Path) -> None:
    """A torn tail of nested brackets is skipped, not a RecursionError."""
    path = tmp_path / "receipts.jsonl"
    prefix, keys = _record_three(path)
    path.write_bytes(prefix + b"[" * 10000)

    reloaded = NotionOperationReceiptLog(path)
    _assert_loaded_keys(reloaded, keys)
    reloaded.record(_receipt(idempotency_key="key-4", target="page_4"))
    raw = path.read_bytes()
    assert raw.startswith(prefix)
    assert _stored_keys(raw) == (*keys, "key-4")
    again = NotionOperationReceiptLog(path)
    _assert_loaded_keys(again, (*keys, "key-4"))


def test_recorded_lines_are_ascii(tmp_path: Path) -> None:
    """record() writes pure ASCII even when the receipt contains non-ASCII text."""
    path = tmp_path / "receipts.jsonl"
    receipt = _receipt(
        target="café",
        evidence="💡",
        post_state={"title": "café", "icon": "💡"},
    )
    NotionOperationReceiptLog(path).record(receipt)

    raw = path.read_bytes()
    assert raw.isascii()
    stored = NotionOperationReceiptLog(path).get(receipt.idempotency_key)
    assert stored is not None
    assert stored.target == "café"
    assert stored.evidence == "💡"
    assert stored.post_state == {"title": "café", "icon": "💡"}


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


def test_replace_keeps_nested_state_frozen() -> None:
    """Replacing status keeps nested pre-state, post-state, and provider response."""
    receipt = _receipt(
        status="Unknown",
        pre_state={"items": [{"title": "before"}]},
        post_state={"items": [{"title": "after"}]},
        provider_response={"blocks": [{"type": "text"}]},
    )
    replaced = replace(receipt, status="Failure")
    round_trip = replace(replaced, status="Unknown")

    assert replaced.status == "Failure"
    assert round_trip.status == "Unknown"
    assert replaced.pre_state == receipt.pre_state
    assert replaced.post_state == receipt.post_state
    assert replaced.provider_response == receipt.provider_response
    assert round_trip.pre_state == receipt.pre_state
    assert round_trip.post_state == receipt.post_state
    assert round_trip.provider_response == receipt.provider_response
    assert replaced.pre_state is not None
    pre_items = replaced.pre_state["items"]
    post_items = replaced.post_state["items"]
    blocks = replaced.provider_response["blocks"]
    assert isinstance(pre_items, tuple)
    assert isinstance(post_items, tuple)
    assert isinstance(blocks, tuple)
    pre_nested = pre_items[0]
    post_nested = post_items[0]
    block = blocks[0]
    assert isinstance(pre_nested, MappingProxyType)
    assert isinstance(post_nested, MappingProxyType)
    assert isinstance(block, MappingProxyType)
    assert pre_nested["title"] == "before"
    assert post_nested["title"] == "after"
    assert block["type"] == "text"
    assignment = cast(dict[str, object], post_nested)
    with pytest.raises(TypeError):
        assignment["title"] = "changed"
    assert post_nested["title"] == "after"


def test_caller_nested_dict_and_list_stay_outside_the_receipt() -> None:
    """Mutating the caller's nested dict and list leaves the receipt unchanged."""
    inner = {"title": "old"}
    items = [inner]
    post_state: dict[str, object] = {"items": items}
    receipt = _receipt(post_state=post_state)
    inner["title"] = "NEW"
    items.append({"title": "extra"})
    post_state["extra"] = True

    assert receipt.post_state == {"items": ({"title": "old"},)}
    stored_items = receipt.post_state["items"]
    assert isinstance(stored_items, tuple)
    assert stored_items is not items
    stored_inner = stored_items[0]
    assert isinstance(stored_inner, MappingProxyType)
    assert stored_inner is not inner
    assert receipt.post_state is not post_state


def test_caller_mapping_proxy_list_mutation_does_not_change_the_receipt() -> None:
    """A caller proxy is copied, including a proxy nested inside another mapping."""
    inner = [1]
    top = MappingProxyType({"a": inner})
    receipt = _receipt(post_state=top)
    inner.append(2)

    assert receipt.post_state == {"a": (1,)}
    assert receipt.post_state is not top
    stored = receipt.post_state["a"]
    assert isinstance(stored, tuple)
    assert stored is not inner

    nested_list = [1]
    nested = MappingProxyType({"b": nested_list})
    wrapped: dict[str, object] = {"a": nested}
    nested_receipt = _receipt(idempotency_key="create_page:job_2", post_state=wrapped)
    nested_list.append(2)

    assert nested_receipt.post_state == {"a": {"b": (1,)}}
    stored_nested = nested_receipt.post_state["a"]
    assert isinstance(stored_nested, MappingProxyType)
    assert stored_nested is not nested
    stored_list = stored_nested["b"]
    assert isinstance(stored_list, tuple)
    assert stored_list is not nested_list


def test_shared_subcontainers_round_trip(tmp_path: Path) -> None:
    """The same sub-dict or list used twice is copied, not treated as a cycle."""
    shared = {"x": 1}
    shared_list = [1]
    receipt = _receipt(post_state={"a": shared, "b": shared, "c": shared_list, "d": shared_list})
    path = tmp_path / "receipts.jsonl"
    NotionOperationReceiptLog(path).record(receipt)
    shared["x"] = 9
    shared_list.append(2)

    stored = NotionOperationReceiptLog(path).get(receipt.idempotency_key)
    assert stored is not None
    assert stored.post_state == {"a": {"x": 1}, "b": {"x": 1}, "c": (1,), "d": (1,)}
    stored_a = stored.post_state["a"]
    stored_b = stored.post_state["b"]
    assert isinstance(stored_a, MappingProxyType)
    assert isinstance(stored_b, MappingProxyType)
    assert stored_a is not stored_b
    assert stored_a is not shared
    stored_c = stored.post_state["c"]
    stored_d = stored.post_state["d"]
    assert isinstance(stored_c, tuple)
    assert isinstance(stored_d, tuple)
    assert stored_c is not stored_d
    assert stored_c is not shared_list


def _nested_mappings(count: int) -> dict[str, object]:
    """count includes the receipt field mapping as container 1 (level 0)."""
    node: dict[str, object] = {"leaf": 1}
    for _ in range(count - 1):
        node = {"child": node}
    return node


def _nested_lists(count: int) -> dict[str, object]:
    """count includes the receipt field mapping, then count-1 lists."""
    node: object = 1
    for _ in range(count - 1):
        node = [node]
    return {"items": node}


def test_nesting_accepts_33_containers_and_rejects_34() -> None:
    """More than 32 levels below the field mapping is rejected.

    33 nested containers are accepted, counting the field mapping as level 0;
    34 are rejected.
    """
    accepted = _receipt(post_state=_nested_mappings(33))
    current: object = accepted.post_state
    for _ in range(32):
        assert isinstance(current, MappingProxyType)
        current = current["child"]
    assert isinstance(current, MappingProxyType)
    assert current["leaf"] == 1

    with pytest.raises(ValueError, match="more than 32 levels below the field mapping") as caught:
        _receipt(idempotency_key="create_page:job_34", post_state=_nested_mappings(34))
    assert type(caught.value) is ValueError

    listed = _receipt(idempotency_key="create_page:job_lists", post_state=_nested_lists(33))
    listed_current: object = listed.post_state["items"]
    for _ in range(32):
        assert isinstance(listed_current, tuple)
        assert len(listed_current) == 1
        listed_current = listed_current[0]
    assert listed_current == 1

    with pytest.raises(
        ValueError, match="more than 32 levels below the field mapping"
    ) as listed_caught:
        _receipt(idempotency_key="create_page:job_lists_34", post_state=_nested_lists(34))
    assert type(listed_caught.value) is ValueError


def test_deep_list_nest_raises_value_error() -> None:
    """A list-only nest well past the limit raises ValueError, not RecursionError."""
    node: object = 1
    for _ in range(200):
        node = [node]
    with pytest.raises(ValueError, match="more than 32 levels below the field mapping") as caught:
        _receipt(post_state={"items": node})
    assert type(caught.value) is ValueError


def test_deeply_nested_json_line_raises_value_error(tmp_path: Path) -> None:
    """A load line that makes json.loads recurse raises ValueError."""
    path = tmp_path / "receipts.jsonl"
    depth = 10000
    path.write_text("[" * depth + "1" + "]" * depth + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="is not a receipt") as caught:
        NotionOperationReceiptLog(path)
    assert type(caught.value) is ValueError
    assert isinstance(caught.value.__cause__, RecursionError)


def test_cycles_and_deep_nesting_raise_value_error() -> None:
    """A reference cycle or an excessive nest raises ValueError, not RecursionError."""
    cycle: dict[str, object] = {}
    cycle["self"] = cycle
    with pytest.raises(ValueError, match="JSON-serializable") as caught:
        _receipt(post_state=cycle)
    assert type(caught.value) is ValueError

    node: object = {"leaf": 1}
    for _ in range(40):
        node = {"child": node}
    with pytest.raises(ValueError, match="more than 32 levels below the field mapping") as deep:
        _receipt(post_state=node)
    assert type(deep.value) is ValueError


def test_reloaded_post_state_seeds_a_new_receipt(tmp_path: Path) -> None:
    """A reloaded post_state can be stored again as pre_state and post_state."""
    path = tmp_path / "receipts.jsonl"
    NotionOperationReceiptLog(path).record(_receipt(post_state={"items": [{"title": "kept"}]}))
    reloaded = NotionOperationReceiptLog(path).get("create_page:job_1")
    assert reloaded is not None

    follow = _receipt(
        idempotency_key="create_page:job_2",
        pre_state=reloaded.post_state,
        post_state=reloaded.post_state,
        status="Failure",
    )
    NotionOperationReceiptLog(path).record(follow)
    stored = NotionOperationReceiptLog(path).get("create_page:job_2")
    assert stored is not None
    assert stored.pre_state == reloaded.post_state
    assert stored.post_state == reloaded.post_state
    assert stored.status == "Failure"


def test_lock_inside_state_raises_value_error() -> None:
    """A lock inside state is rejected as non-serializable, not as TypeError."""
    with pytest.raises(ValueError, match="JSON-serializable") as caught:
        _receipt(post_state={"lock": threading.Lock()})
    assert type(caught.value) is ValueError


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match="JSON-serializable"):
        _receipt(post_state={"n": bad})


def test_same_resolved_path_shares_one_lock(tmp_path: Path) -> None:
    """The same resolved path always gets the same lock object."""
    path = tmp_path / "receipts.jsonl"
    first = NotionOperationReceiptLog(path)
    second = NotionOperationReceiptLog(path)
    relative = NotionOperationReceiptLog(Path(os.path.relpath(path)))
    other = NotionOperationReceiptLog(tmp_path / "other.jsonl")
    first_lock = first._lock  # pyright: ignore[reportPrivateUsage]
    second_lock = second._lock  # pyright: ignore[reportPrivateUsage]
    relative_lock = relative._lock  # pyright: ignore[reportPrivateUsage]
    other_lock = other._lock  # pyright: ignore[reportPrivateUsage]
    assert first_lock is second_lock
    assert first_lock is relative_lock
    assert first_lock is not other_lock


def test_record_waits_for_the_path_lock(tmp_path: Path) -> None:
    """A second log on the same path blocks while the first holds the lock."""
    path = tmp_path / "receipts.jsonl"
    first = NotionOperationReceiptLog(path)
    second = NotionOperationReceiptLog(path)
    lock = first._lock  # pyright: ignore[reportPrivateUsage]
    assert lock is not None
    assert lock is second._lock  # pyright: ignore[reportPrivateUsage]
    assert lock.acquire(blocking=False)
    finished = threading.Event()

    def _record() -> None:
        second.record(_receipt(idempotency_key="key-wait"))
        finished.set()

    thread = threading.Thread(target=_record)
    thread.start()
    assert finished.wait(timeout=0.2) is False
    lock.release()
    thread.join(timeout=2)
    assert finished.is_set()
    assert second.get("key-wait") is not None


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
