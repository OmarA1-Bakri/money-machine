"""In-memory listing mutation receipt and fixture reconciliation.

The receipt stores a redacted response hash. It does not store a raw provider
body or a screenshot. A timeout reads the fixture before any further create.
``UNKNOWN`` does not create again.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from money_machine.domain.models.common import EffectReference

EffectState = Literal["CONFIRMED", "ABSENT", "UNKNOWN"]
_OBSERVED_AT = datetime(2026, 10, 16, tzinfo=UTC)
_RAW_BODY_FIELDS = frozenset(
    {
        "body",
        "provider_response",
        "raw_body",
        "raw_response",
        "response",
        "response_body",
    }
)


class ReceiptRejected(Exception):
    """A receipt field is missing or would store a forbidden payload."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ReconciliationError(Exception):
    """Fixture reconciliation refused to invent a resolved status."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class WriteTimeout(Exception):
    """The fixture write did not return a provider id."""

    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__(idempotency_key)


@dataclass(frozen=True, slots=True)
class ReadObservation:
    """One fixture read. ``observed`` is false when no read happened."""

    observed: bool
    provider_id: str | None
    unknown: bool


@dataclass(frozen=True, slots=True)
class ListingMutation:
    """The listing write the receipt describes. No provider payload."""

    operation: str
    listing_target: str
    pre_state: str
    expected_post_state: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class MutationReceipt:
    """Redacted record of one listing mutation."""

    operation: str
    listing_target: str
    pre_state: str
    expected_post_state: str
    provider_id: str | None
    response_hash: str
    idempotency_key: str
    effect_state: EffectState
    effect: EffectReference


class ListingFixture(Protocol):
    """Recording double surface used by fixture reconciliation.

    ``create`` returns a provider id or raises ``WriteTimeout``.
    ``read`` returns an observation. A disabled read leaves ``observed`` false.
    """

    def create(self, idempotency_key: str) -> str: ...

    def read(self, idempotency_key: str) -> ReadObservation: ...


class ReceiptBook:
    """In-memory receipts keyed by the idempotency key they name."""

    def __init__(self) -> None:
        self._by_key: dict[str, MutationReceipt] = {}

    def get(self, idempotency_key: str) -> MutationReceipt | None:
        """Return the receipt for this key. A different key is not a match."""
        for receipt in self._by_key.values():
            if receipt.idempotency_key != idempotency_key:
                continue  # pin: distinct-key
            return receipt
        return None

    def put(self, receipt: MutationReceipt) -> None:
        """Store one receipt under its own idempotency key."""
        self._by_key[receipt.idempotency_key] = receipt


def build_receipt(
    *,
    operation: str,
    listing_target: str,
    pre_state: str,
    expected_post_state: str,
    provider_id: str | None,
    response_hash: str | None,
    idempotency_key: str,
    effect_state: EffectState,
    **forbidden: object,
) -> MutationReceipt:
    """Build one redacted receipt. Reuses ``EffectReference`` for the effect."""
    _reject_forbidden(forbidden)
    if response_hash is None or response_hash.strip() == "":
        raise ReceiptRejected("response hash is required")  # pin: response-hash
    if effect_state == "CONFIRMED" and provider_id is None:
        raise ReceiptRejected(
            "confirmed effect requires a provider id"
        )  # pin: confirmed-provider-id
    effect = EffectReference(
        idempotency_key=idempotency_key,
        provider="etsy",
        operation=operation,
        provider_object_id=provider_id,
        effect_state=effect_state,
        observed_at=_OBSERVED_AT,
    )
    return MutationReceipt(
        operation=operation,
        listing_target=listing_target,
        pre_state=pre_state,
        expected_post_state=expected_post_state,
        provider_id=effect.provider_object_id,
        response_hash=response_hash,
        idempotency_key=effect.idempotency_key,
        effect_state=effect.effect_state,
        effect=effect,
    )


def commit_listing_mutation(
    book: ReceiptBook,
    fixture: ListingFixture,
    mutation: ListingMutation,
) -> MutationReceipt:
    """Create once per key. A timeout reads the fixture before another create."""
    existing = book.get(mutation.idempotency_key)
    if existing is not None and existing.effect_state == "UNKNOWN":
        return existing  # pin: unknown-again
    if existing is not None and existing.effect_state == "CONFIRMED":
        return existing  # pin: same-key
    try:
        provider_id = fixture.create(mutation.idempotency_key)
    except WriteTimeout:
        return _reconcile_timeout(book, fixture, mutation)
    return _remember(book, mutation, provider_id=provider_id, effect_state="CONFIRMED")


def _reject_forbidden(forbidden: dict[str, object]) -> None:
    for key in forbidden:
        if key in _RAW_BODY_FIELDS:
            raise ReceiptRejected("raw response body")  # pin: raw-body
        if "screenshot" in key:
            raise ReceiptRejected("screenshot")  # pin: screenshot


def _reconcile_timeout(
    book: ReceiptBook,
    fixture: ListingFixture,
    mutation: ListingMutation,
) -> MutationReceipt:
    observation = fixture.read(mutation.idempotency_key)
    if not observation.observed:
        raise ReconciliationError("reconciled status requires a read")  # pin: no-read
    if observation.unknown:
        return _remember(
            book, mutation, provider_id=None, effect_state="UNKNOWN"
        )  # pin: unknown-read
    if observation.provider_id is not None:
        return _remember(  # pin: timeout-found
            book,
            mutation,
            provider_id=observation.provider_id,
            effect_state="CONFIRMED",
        )
    provider_id = fixture.create(mutation.idempotency_key)  # pin: timeout-absent
    return _remember(book, mutation, provider_id=provider_id, effect_state="CONFIRMED")


def _remember(
    book: ReceiptBook,
    mutation: ListingMutation,
    *,
    provider_id: str | None,
    effect_state: EffectState,
) -> MutationReceipt:
    receipt = build_receipt(
        operation=mutation.operation,
        listing_target=mutation.listing_target,
        pre_state=mutation.pre_state,
        expected_post_state=mutation.expected_post_state,
        provider_id=provider_id,
        response_hash=_redacted_hash(mutation, provider_id, effect_state),
        idempotency_key=mutation.idempotency_key,
        effect_state=effect_state,
    )
    book.put(receipt)
    return receipt


def _redacted_hash(
    mutation: ListingMutation,
    provider_id: str | None,
    effect_state: str,
) -> str:
    material = "|".join(
        (
            mutation.operation,
            mutation.listing_target,
            mutation.pre_state,
            mutation.expected_post_state,
            mutation.idempotency_key,
            effect_state,
            provider_id or "",
        )
    )
    return hashlib.sha256(material.encode()).hexdigest()
