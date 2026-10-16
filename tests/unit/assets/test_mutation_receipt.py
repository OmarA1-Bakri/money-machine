"""In-memory listing mutation receipts reconciled against a recording double."""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Literal

import pytest

from money_machine.assets.mutation_receipt import (
    ListingMutation,
    ReadObservation,
    ReceiptBook,
    ReceiptRejected,
    ReconciliationError,
    WriteTimeout,
    build_receipt,
    commit_listing_mutation,
)

_HASH = "ab" * 32


@pytest.fixture(autouse=True)
def _block_sockets(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("socket")

    def _connect(_self: socket.socket, address: object) -> None:
        _blocked(address)

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _connect)


def _mutation(key: str) -> ListingMutation:
    return ListingMutation(
        operation="etsy.create_draft",
        listing_target="shop:1/listing",
        pre_state="absent",
        expected_post_state="draft",
        idempotency_key=key,
    )


@dataclass
class RecordingListingDouble:
    """Fixture double. Successful creates and observed reads are counted."""

    timeout_first_write: bool = False
    read_mode: Literal["ok", "unknown", "disabled"] = "ok"
    visible: dict[str, str] = field(default_factory=dict)
    creates: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    write_attempts: list[str] = field(default_factory=list)
    _attempted: int = 0

    def create(self, idempotency_key: str) -> str:
        self.write_attempts.append(idempotency_key)
        self._attempted += 1
        if self.timeout_first_write and self._attempted == 1:
            raise WriteTimeout(idempotency_key)
        provider_id = f"listing-{len(self.creates) + 1}"
        self.creates.append(idempotency_key)
        self.visible[idempotency_key] = provider_id
        return provider_id

    def read(self, idempotency_key: str) -> ReadObservation:
        if self.read_mode == "disabled":
            return ReadObservation(observed=False, provider_id=None, unknown=False)
        self.reads.append(idempotency_key)
        if self.read_mode == "unknown":
            return ReadObservation(observed=True, provider_id=None, unknown=True)
        return ReadObservation(
            observed=True,
            provider_id=self.visible.get(idempotency_key),
            unknown=False,
        )


def test_same_idempotency_key_creates_once() -> None:
    book = ReceiptBook()
    double = RecordingListingDouble()
    first = commit_listing_mutation(book, double, _mutation("key-a"))
    second = commit_listing_mutation(book, double, _mutation("key-a"))
    assert double.creates == ["key-a"]
    assert first.provider_id == second.provider_id
    assert first.provider_id == "listing-1"
    assert first.effect_state == "CONFIRMED"
    assert second.effect_state == "CONFIRMED"
    assert first.operation == "etsy.create_draft"
    assert first.listing_target == "shop:1/listing"
    assert first.pre_state == "absent"
    assert first.expected_post_state == "draft"
    assert first.idempotency_key == "key-a"
    assert first.response_hash
    assert first.effect.provider_object_id == first.provider_id
    assert first.effect.idempotency_key == "key-a"


def test_different_idempotency_key_creates_twice() -> None:
    book = ReceiptBook()
    double = RecordingListingDouble()
    first = commit_listing_mutation(book, double, _mutation("key-a"))
    second = commit_listing_mutation(book, double, _mutation("key-b"))
    assert double.creates == ["key-a", "key-b"]
    assert first.provider_id == "listing-1"
    assert second.provider_id == "listing-2"
    assert first.provider_id != second.provider_id


def test_timeout_found_listing_creates_nothing_more() -> None:
    book = ReceiptBook()
    double = RecordingListingDouble(
        timeout_first_write=True,
        visible={"key-a": "listing-found"},
    )
    receipt = commit_listing_mutation(book, double, _mutation("key-a"))
    assert double.write_attempts == ["key-a"]
    assert double.reads == ["key-a"]
    assert double.creates == []
    assert receipt.effect_state == "CONFIRMED"
    assert receipt.provider_id == "listing-found"
    assert receipt.effect.effect_state == "CONFIRMED"
    assert receipt.effect.provider_object_id == "listing-found"


def test_timeout_absent_listing_creates_once() -> None:
    book = ReceiptBook()
    double = RecordingListingDouble(timeout_first_write=True)
    receipt = commit_listing_mutation(book, double, _mutation("key-a"))
    assert double.write_attempts == ["key-a", "key-a"]
    assert double.reads == ["key-a"]
    assert double.creates == ["key-a"]
    assert receipt.effect_state == "CONFIRMED"
    assert receipt.provider_id == "listing-1"


def test_unknown_does_not_create_again() -> None:
    book = ReceiptBook()
    double = RecordingListingDouble(timeout_first_write=True, read_mode="unknown")
    first = commit_listing_mutation(book, double, _mutation("key-a"))
    assert first.effect_state == "UNKNOWN"
    assert first.provider_id is None
    assert first.effect.effect_state == "UNKNOWN"
    assert first.effect.provider_object_id is None
    assert double.creates == []
    second = commit_listing_mutation(book, double, _mutation("key-a"))
    assert second.effect_state == "UNKNOWN"
    assert second.provider_id is None
    assert double.creates == []
    assert double.write_attempts == ["key-a"]


def test_reconciled_status_without_read_fails() -> None:
    book = ReceiptBook()
    double = RecordingListingDouble(timeout_first_write=True, read_mode="disabled")
    with pytest.raises(ReconciliationError, match="read"):
        commit_listing_mutation(book, double, _mutation("key-a"))
    assert double.reads == []
    assert double.creates == []


def test_confirmed_without_provider_id_fails() -> None:
    with pytest.raises(ReceiptRejected, match="provider"):
        build_receipt(
            operation="etsy.create_draft",
            listing_target="shop:1/listing",
            pre_state="absent",
            expected_post_state="draft",
            provider_id=None,
            response_hash=_HASH,
            idempotency_key="key-a",
            effect_state="CONFIRMED",
        )


def test_missing_response_hash_fails() -> None:
    with pytest.raises(ReceiptRejected, match="hash"):
        build_receipt(
            operation="etsy.create_draft",
            listing_target="shop:1/listing",
            pre_state="absent",
            expected_post_state="draft",
            provider_id="listing-1",
            response_hash=None,
            idempotency_key="key-a",
            effect_state="CONFIRMED",
        )


def test_raw_response_body_rejected() -> None:
    with pytest.raises(ReceiptRejected, match="response"):
        build_receipt(
            operation="etsy.create_draft",
            listing_target="shop:1/listing",
            pre_state="absent",
            expected_post_state="draft",
            provider_id="listing-1",
            response_hash=_HASH,
            idempotency_key="key-a",
            effect_state="CONFIRMED",
            response={"listing_id": 1, "title": "raw provider body"},
        )


def test_screenshot_rejected() -> None:
    with pytest.raises(ReceiptRejected, match="screenshot"):
        build_receipt(
            operation="etsy.create_draft",
            listing_target="shop:1/listing",
            pre_state="absent",
            expected_post_state="draft",
            provider_id="listing-1",
            response_hash=_HASH,
            idempotency_key="key-a",
            effect_state="CONFIRMED",
            screenshot=b"\x89PNG-raw",
        )
