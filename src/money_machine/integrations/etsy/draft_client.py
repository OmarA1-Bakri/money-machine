"""Fixture Etsy draft client. There is no live transport.

Measured from the Etsy Open API v3 Shop Listing document
(``x-generated-from: https://www.etsy.com/openapi/generated/oas/3.0.0.json``,
``x-last-validated: 2026-05-30``):

- ``createDraftListing`` — ``POST /v3/application/shops/{shop_id}/listings``
- ``getListingsByShop`` — ``GET /v3/application/shops/{shop_id}/listings``

``getListingsByShop`` defaults ``state`` to ``active`` and ``limit`` to 25.
This client sends ``state=draft`` and ``limit=100``, and follows ``offset``
until a short page. It then walks every page again. The sorted listing ids
must match, and every id is an exact int. ``count`` is the filtered total. ``updateListing`` is
``PATCH`` on ``/v3/application/shops/{shop_id}/listings/{listing_id}`` and can
set ``state=active``, which publishes the draft. That pair is not in the
allowlist, and this class has no publish or activate method.

Etsy does not take a client idempotency key. The ledger key is the spec
version plus a hash of the fixture fields. The pending file is created with
``O_CREAT|O_EXCL|O_NOFOLLOW`` and fsynced, with the directory, before
``POST``. A pending key with no adopted draft is not posted again. The
description carries one exact line, ``mm-draft:{spec_version}:{fixture_hash}``.
A retry adopts that line and never a title.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
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
PAGE_LIMIT = 100
PAGE_CAP = 10
_GET_KEYS = frozenset({"state", "limit", "offset"})
_BODY_KEYS = frozenset(
    {
        "quantity",
        "title",
        "description",
        "price",
        "who_made",
        "when_made",
        "taxonomy_id",
        "type",
    }
)


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
    """One spec-and-hash row. ``pending`` is written before ``POST``."""

    spec_version: int
    fixture_hash: str
    status: Literal["pending", "recorded"]
    listing_id: int | None


def _fsync_file(fd: int) -> None:
    """Flush one file descriptor. Called before ``POST``."""
    os.fsync(fd)


def _fsync_dir(directory: Path) -> None:
    """Flush the directory so the new name survives a crash."""
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class DraftLedger:
    """Durable idempotency ledger. The directory is injected. There is no default."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def get(self, spec_version: int, fixture_hash: str) -> LedgerEntry | None:
        """Return the row, or refuse an unreadable or corrupt file."""
        path = self._path(spec_version, fixture_hash)
        if not path.is_symlink() and not path.exists():
            return None
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as exc:
            raise EtsyDraftRefused("ledger") from exc
        try:
            payload = os.read(descriptor, 4096)
        except OSError as exc:
            raise EtsyDraftRefused("ledger") from exc
        finally:
            os.close(descriptor)
        text = payload.decode("utf-8", errors="replace")
        if text == "pending\n":
            return LedgerEntry(
                spec_version=spec_version,
                fixture_hash=fixture_hash,
                status="pending",
                listing_id=None,
            )
        if text.startswith("recorded\n"):
            lines = text.split("\n")
            if len(lines) >= 2 and lines[1].isdigit() and int(lines[1]) >= 1:
                return LedgerEntry(
                    spec_version=spec_version,
                    fixture_hash=fixture_hash,
                    status="recorded",
                    listing_id=int(lines[1]),
                )
        raise EtsyDraftRefused("ledger_corrupt")

    def put_pending(self, spec_version: int, fixture_hash: str) -> None:
        """Create the pending file if it is missing. A recorded row stays recorded."""
        current = self.get(spec_version, fixture_hash)
        if current is not None:
            return
        self._create_exclusive(self._path(spec_version, fixture_hash), b"pending\n")

    def record(self, spec_version: int, fixture_hash: str, listing_id: int) -> None:
        """Replace the row with the adopted or created listing."""
        payload = f"recorded\n{listing_id}\n".encode()
        path = self._path(spec_version, fixture_hash)
        temporary = path.with_name(path.name + ".next")
        with suppress(FileNotFoundError):
            os.unlink(temporary)
        self._create_exclusive(temporary, payload)
        os.replace(temporary, path)
        _fsync_dir(self._directory)

    def _path(self, spec_version: int, fixture_hash: str) -> Path:
        return self._directory / f"{spec_version}-{fixture_hash}"

    def _create_exclusive(self, path: Path, payload: bytes) -> None:
        flags = os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY
        descriptor = os.open(path, flags, 0o644)
        try:
            os.write(descriptor, payload)
            _fsync_file(descriptor)
        finally:
            os.close(descriptor)
        _fsync_dir(self._directory)


class EtsyDraftClient:
    """Create one draft through a fixture transport, or refuse."""

    def __init__(self, transport: FixtureTransport | None, ledger: DraftLedger) -> None:
        self._transport = transport
        self._ledger = ledger

    def create_draft(self, spec: DraftSpec) -> DraftReceipt:
        """Return the ready draft. A pending key with no adopted draft is not posted."""
        _require_spec(spec)
        digest = fixture_hash(spec)
        marker = draft_marker(spec.spec_version, digest)
        existing = self._ledger.get(spec.spec_version, digest)
        if existing is not None and existing.status == "recorded":
            listing_id = existing.listing_id
            assert listing_id is not None
            return _receipt(spec, digest, marker, listing_id)
        adopted = self._adopt(spec, marker)
        if adopted is not None:
            self._ledger.record(spec.spec_version, digest, adopted)
            return _receipt(spec, digest, marker, adopted)
        if existing is not None and existing.status == "pending":
            raise EtsyDraftRefused("pending")
        self._ledger.put_pending(spec.spec_version, digest)
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
        """Send one call. Off-list pairs and bad keys are refused before the transport."""
        if self._transport is None:
            raise EtsyDraftRefused("fixture_transport")
        pair = _measured_pair(method, path)
        if pair not in MEASURED_ALLOWLIST:
            raise EtsyDraftRefused("off_list")
        if method == "GET":
            _refuse_get(query, body)
        elif method == "POST":
            _refuse_post(query, body)
        return self._transport.exchange(FixtureCall(method, path, query, body))

    def _adopt(self, spec: DraftSpec, marker: str) -> int | None:
        found, ids, texts = self._read_pages(spec, marker)
        confirm_found, confirm_ids, confirm_texts = self._read_pages(spec, marker)
        if ids != confirm_ids or found != confirm_found or texts != confirm_texts:
            raise EtsyDraftRefused("count")
        return found

    def _read_pages(self, spec: DraftSpec, marker: str) -> tuple[int | None, list[int], list[str]]:
        found: int | None = None
        seen = 0
        ids: list[int] = []
        texts: list[str] = []
        seen_ids: set[int] = set()
        expected: int | None = None
        offset = 0
        for _page in range(PAGE_CAP):
            try:
                payload = self.exchange(
                    "GET",
                    _listings_path(spec.shop_id),
                    _draft_query(offset),
                    None,
                )
            except EtsyDraftRefused:
                raise
            except Exception as exc:
                raise EtsyDraftRefused("transport") from exc
            results = payload.get("results")
            count = payload.get("count")
            if not isinstance(results, list) or type(count) is not int or count < 0:
                raise EtsyDraftRefused("malformed")
            if expected is None:
                expected = count
            elif count != expected:
                raise EtsyDraftRefused("count")
            if len(results) > PAGE_LIMIT:
                raise EtsyDraftRefused("malformed")
            for row in results:
                if not isinstance(row, dict):
                    raise EtsyDraftRefused("malformed")
                listing_raw = row.get("listing_id")
                if type(listing_raw) is not int:
                    raise EtsyDraftRefused("malformed")
                if listing_raw in seen_ids:
                    raise EtsyDraftRefused("count")
                seen_ids.add(listing_raw)
                ids.append(listing_raw)
                texts.append(_row_text(row.get("description")))
                if not _line_marker(row.get("description"), marker):
                    continue
                listing_id = _draft_listing_id(row)
                if found is not None:
                    raise EtsyDraftRefused("duplicate_marker")
                found = listing_id
            seen += len(results)
            if len(results) < PAGE_LIMIT:
                if seen != expected:
                    raise EtsyDraftRefused("count")
                ids.sort()
                texts.sort()
                return found, ids, texts
            offset += PAGE_LIMIT
        raise EtsyDraftRefused("page_cap")

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
    if any(line.startswith("mm-draft:") for line in _description_lines(spec.description)):
        raise EtsyDraftRefused("marker_injection")


def _listings_path(shop_id: int) -> str:
    return f"/v3/application/shops/{shop_id}/listings"


def _draft_query(offset: int) -> tuple[tuple[str, str], ...]:
    return (
        ("state", "draft"),
        ("limit", str(PAGE_LIMIT)),
        ("offset", str(offset)),
    )


def _measured_pair(method: str, path: str) -> tuple[str, str]:
    """Return the measured pair, or refuse a path outside that template."""
    if _LISTINGS_RE.fullmatch(path) is None:
        raise EtsyDraftRefused("off_list")
    return (method, _LISTINGS_PATH)


def _query_keys(pairs: tuple[tuple[str, str], ...]) -> dict[str, str]:
    """Case-fold and trim lookup keys. A key that changes, or collides, is refused."""
    normalized: dict[str, str] = {}
    for raw, value in pairs:
        if raw != raw.casefold():
            raise EtsyDraftRefused("query_case")
        folded = raw.casefold()
        if folded != folded.strip():
            raise EtsyDraftRefused("query_space")
        key = folded.strip()
        if key in normalized:
            raise EtsyDraftRefused("query_duplicate")
        normalized[key] = value
    return normalized


def _body_keys(pairs: tuple[tuple[str, str], ...]) -> dict[str, str]:
    """Case-fold and trim create-body keys. A key that changes, or collides, is refused."""
    normalized: dict[str, str] = {}
    for raw, value in pairs:
        if raw != raw.casefold():
            raise EtsyDraftRefused("body_case")
        folded = raw.casefold()
        if folded != folded.strip():
            raise EtsyDraftRefused("body_space")
        key = folded.strip()
        if key in normalized:
            raise EtsyDraftRefused("body_duplicate")
        normalized[key] = value
    return normalized


def _canonical_int(value: str, *, low: int, high: int | None) -> bool:
    if not value.isdigit():
        return False
    if value != "0" and value.startswith("0"):
        return False
    number = int(value)
    if number < low:
        return False
    return high is None or number <= high


def _refuse_get(
    query: tuple[tuple[str, str], ...],
    body: tuple[tuple[str, str], ...] | None,
) -> None:
    if body is not None:
        raise EtsyDraftRefused("query_key")
    fields = _query_keys(query)
    if set(fields) - _GET_KEYS:
        raise EtsyDraftRefused("query_key")
    if "state" not in fields:
        raise EtsyDraftRefused("lookup_state")
    if fields["state"] != "draft":
        raise EtsyDraftRefused("lookup_state")
    if "limit" in fields and not _canonical_int(fields["limit"], low=1, high=PAGE_LIMIT):
        raise EtsyDraftRefused("query_limit")
    if "offset" in fields and not _canonical_int(fields["offset"], low=0, high=None):
        raise EtsyDraftRefused("query_offset")


def _refuse_post(
    query: tuple[tuple[str, str], ...],
    body: tuple[tuple[str, str], ...] | None,
) -> None:
    _query_keys(query)
    if query:
        raise EtsyDraftRefused("post_query")
    if body is None:
        raise EtsyDraftRefused("body_missing")
    fields = _body_keys(body)
    if set(fields) - _BODY_KEYS:
        raise EtsyDraftRefused("body_extra")
    if _BODY_KEYS - set(fields):
        raise EtsyDraftRefused("body_missing")


def _row_text(description: object) -> str:
    """The description compared across the two walks. A non-string is empty."""
    if isinstance(description, str):
        return description
    return ""


def _description_lines(description: str) -> tuple[str, ...]:
    text = description.replace("\r\n", "\n")
    return tuple(line.rstrip(" \t") for line in text.split("\n"))


def _line_marker(description: object, marker: str) -> bool:
    """True only when a whole normalized line equals the marker."""
    if not isinstance(description, str):
        return False
    return any(line == marker for line in _description_lines(description))


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
