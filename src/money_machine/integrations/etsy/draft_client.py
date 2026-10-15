"""Fixture Etsy draft client. There is no live transport.

Measured from the Etsy Open API v3 Shop Listing document
(``x-generated-from: https://www.etsy.com/openapi/generated/oas/3.0.0.json``,
``x-last-validated: 2026-05-30``):

- ``createDraftListing`` — ``POST /v3/application/shops/{shop_id}/listings``
- ``getListingsByShop`` — ``GET /v3/application/shops/{shop_id}/listings``

``getListingsByShop`` defaults ``state`` to ``active``. This client sends
``state=draft``. ``updateListing`` is ``PATCH`` on
``/v3/application/shops/{shop_id}/listings/{listing_id}`` and can set
``state=active``, which publishes the draft. That pair is not in the
allowlist, and this class has no publish or activate method.

Etsy does not take a client idempotency key. The ledger key is the spec
version plus a hash of the fixture fields. The description carries one exact
line, ``mm-draft:{spec_version}:{fixture_hash}``. A retry adopts that line
and never a title.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

_LISTINGS_PATH = "/v3/application/shops/{shop_id}/listings"
MEASURED_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", _LISTINGS_PATH),
        ("POST", _LISTINGS_PATH),
    }
)
_LISTINGS_RE = re.compile(r"^/v3/application/shops/([1-9][0-9]*)/listings$")


class EtsyDraftRefused(Exception):
    """The draft was not created. ``code`` names the guard that fired."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DraftSpec:
    """Fields hashed into the ledger key and sent on ``createDraftListing``."""

    product_id: UUID
    spec_version: int
    shop_id: int
    title: str
    description: str
    price: str
    quantity: int
    who_made: str
    when_made: str
    taxonomy_id: int


@dataclass(frozen=True, slots=True)
class DraftReceipt:
    """A fixture draft that is ready. ``state`` is ``draft`` and never ``active``."""

    listing_id: int
    spec_version: int
    fixture_hash: str
    marker: str
    state: Literal["draft"]
    ready: Literal[True]


@dataclass(frozen=True, slots=True)
class FixtureCall:
    """One request the fixture transport is allowed to see."""

    method: str
    path: str
    query: tuple[tuple[str, str], ...]
    body: tuple[tuple[str, str], ...] | None


class FixtureTransport(Protocol):
    """Injected stand-in for the Etsy HTTP client. It is not a socket."""

    def exchange(self, call: FixtureCall) -> Mapping[str, object]:
        """Return the fixture JSON for one allowlisted call."""
        ...


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One spec-and-hash row. ``pending`` is written before the transport call."""

    spec_version: int
    fixture_hash: str
    status: Literal["pending", "recorded"]
    listing_id: int | None


class DraftLedger:
    """In-memory idempotency ledger. The key is not an Etsy field."""

    def __init__(self) -> None:
        self._rows: dict[tuple[int, str], LedgerEntry] = {}

    def get(self, spec_version: int, fixture_hash: str) -> LedgerEntry | None:
        return self._rows.get((spec_version, fixture_hash))

    def put_pending(self, spec_version: int, fixture_hash: str) -> None:
        key = (spec_version, fixture_hash)
        current = self._rows.get(key)
        if current is not None and current.status == "recorded":
            return
        self._rows[key] = LedgerEntry(
            spec_version=spec_version,
            fixture_hash=fixture_hash,
            status="pending",
            listing_id=None,
        )

    def record(self, spec_version: int, fixture_hash: str, listing_id: int) -> None:
        self._rows[(spec_version, fixture_hash)] = LedgerEntry(
            spec_version=spec_version,
            fixture_hash=fixture_hash,
            status="recorded",
            listing_id=listing_id,
        )


class EtsyDraftClient:
    """Create one draft through a fixture transport, or refuse."""

    def __init__(self, transport: FixtureTransport | None, ledger: DraftLedger) -> None:
        self._transport = transport
        self._ledger = ledger

    def create_draft(self, spec: DraftSpec) -> DraftReceipt:
        """Return the ready draft. A missing transport never opens a socket."""
        _require_spec(spec)
        digest = fixture_hash(spec)
        marker = draft_marker(spec.spec_version, digest)
        recorded = self._ledger.get(spec.spec_version, digest)
        if recorded is not None and recorded.status == "recorded":
            listing_id = recorded.listing_id
            assert listing_id is not None
            return _receipt(spec, digest, marker, listing_id)
        self._ledger.put_pending(spec.spec_version, digest)
        adopted = self._adopt(spec, marker)
        if adopted is not None:
            self._ledger.record(spec.spec_version, digest, adopted)
            return _receipt(spec, digest, marker, adopted)
        created = self._create(spec, marker)
        self._ledger.record(spec.spec_version, digest, created)
        return _receipt(spec, digest, marker, created)

    def exchange(
        self,
        method: str,
        path: str,
        query: tuple[tuple[str, str], ...],
        body: tuple[tuple[str, str], ...] | None,
    ) -> Mapping[str, object]:
        """Send one call. Off-list pairs are refused before the transport."""
        if self._transport is None:
            raise EtsyDraftRefused("fixture_transport")
        pair = _measured_pair(method, path)
        if pair not in MEASURED_ALLOWLIST:
            raise EtsyDraftRefused("off_list")
        if method == "GET" and query != (("state", "draft"),):
            raise EtsyDraftRefused("lookup_state")
        if body is not None and any(name == "state" for name, _value in body):
            raise EtsyDraftRefused("state_field")
        return self._transport.exchange(FixtureCall(method, path, query, body))

    def _adopt(self, spec: DraftSpec, marker: str) -> int | None:
        payload = self.exchange(
            "GET",
            _listings_path(spec.shop_id),
            (("state", "draft"),),
            None,
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise EtsyDraftRefused("malformed")
        found: int | None = None
        for row in results:
            if not isinstance(row, dict):
                raise EtsyDraftRefused("malformed")
            if not _line_marker(row.get("description"), marker):
                continue
            listing_id = _draft_listing_id(row)
            if found is not None:
                raise EtsyDraftRefused("duplicate_marker")
            found = listing_id
        return found

    def _create(self, spec: DraftSpec, marker: str) -> int:
        description = _with_marker(spec.description, marker)
        body = (
            ("quantity", str(spec.quantity)),
            ("title", spec.title),
            ("description", description),
            ("price", spec.price),
            ("who_made", spec.who_made),
            ("when_made", spec.when_made),
            ("taxonomy_id", str(spec.taxonomy_id)),
            ("type", "download"),
        )
        payload = self.exchange("POST", _listings_path(spec.shop_id), (), body)
        return _draft_listing_id(payload, marker=marker)


def fixture_hash(spec: DraftSpec) -> str:
    """Hash the fixture fields. The shop environment is not an input."""
    lines = (
        f"product_id={spec.product_id}",
        f"spec_version={spec.spec_version}",
        f"shop_id={spec.shop_id}",
        f"title={spec.title}",
        f"description={spec.description}",
        f"price={spec.price}",
        f"quantity={spec.quantity}",
        f"who_made={spec.who_made}",
        f"when_made={spec.when_made}",
        f"taxonomy_id={spec.taxonomy_id}",
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def draft_marker(spec_version: int, fixture_hash_hex: str) -> str:
    """The exact description line a retry looks up. It is not a title."""
    return f"mm-draft:{spec_version}:{fixture_hash_hex}"


def _require_spec(spec: DraftSpec) -> None:
    if type(spec.spec_version) is not int or spec.spec_version < 1:
        raise EtsyDraftRefused("spec_version")
    if type(spec.shop_id) is not int or spec.shop_id < 1:
        raise EtsyDraftRefused("shop_id")
    if type(spec.quantity) is not int or spec.quantity < 1:
        raise EtsyDraftRefused("quantity")
    if type(spec.taxonomy_id) is not int or spec.taxonomy_id < 1:
        raise EtsyDraftRefused("taxonomy_id")
    if spec.title == "" or "\n" in spec.title or "\r" in spec.title:
        raise EtsyDraftRefused("title")
    if spec.price == "":
        raise EtsyDraftRefused("price")


def _listings_path(shop_id: int) -> str:
    return f"/v3/application/shops/{shop_id}/listings"


def _measured_pair(method: str, path: str) -> tuple[str, str]:
    """Return the measured pair, or refuse a path outside that template."""
    if _LISTINGS_RE.fullmatch(path) is None:
        raise EtsyDraftRefused("off_list")
    return (method, _LISTINGS_PATH)


def _line_marker(description: object, marker: str) -> bool:
    """True only when a whole line equals the marker."""
    if not isinstance(description, str):
        return False
    return any(line == marker for line in description.split("\n"))


def _with_marker(description: str, marker: str) -> str:
    if description == "":
        return marker
    if description.endswith("\n"):
        return description + marker
    return description + "\n" + marker


def _draft_listing_id(row: Mapping[str, object], *, marker: str | None = None) -> int:
    if row.get("state") != "draft":
        raise EtsyDraftRefused("active")
    if marker is not None and not _line_marker(row.get("description"), marker):
        raise EtsyDraftRefused("marker")
    listing_id = row.get("listing_id")
    if type(listing_id) is not int or listing_id < 1:
        raise EtsyDraftRefused("malformed")
    return listing_id


def _receipt(spec: DraftSpec, digest: str, marker: str, listing_id: int) -> DraftReceipt:
    return DraftReceipt(
        listing_id=listing_id,
        spec_version=spec.spec_version,
        fixture_hash=digest,
        marker=marker,
        state="draft",
        ready=True,
    )
