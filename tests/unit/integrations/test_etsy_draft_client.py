"""Fixture Etsy draft client. Each guard has its own kill."""

from __future__ import annotations

import socket
from collections.abc import Mapping
from dataclasses import replace
from uuid import UUID

import pytest

from money_machine.integrations.etsy.draft_client import (
    MEASURED_ALLOWLIST,
    DraftLedger,
    DraftReceipt,
    DraftSpec,
    EtsyDraftClient,
    EtsyDraftRefused,
    FixtureCall,
    draft_marker,
    fixture_hash,
)

_PRODUCT = UUID("00000000-0000-4000-8000-0000000000a8")
_ETSY_ENV = (
    "ETSY_API_KEY",
    "ETSY_SHARED_SECRET",
    "ETSY_ACCESS_TOKEN",
    "ETSY_REFRESH_TOKEN",
    "ETSY_SHOP_ID",
)
_LIVE_TOKEN = "eyJlive-" + ("a" * 40)


def _spec() -> DraftSpec:
    return DraftSpec(
        product_id=_PRODUCT,
        spec_version=2,
        shop_id=123456,
        title="Fixture planner",
        description="A fixture description.",
        price="11.00",
        quantity=999,
        who_made="i_did",
        when_made="2020_2026",
        taxonomy_id=1,
    )


class Store:
    """Fixture shop. It records calls and does not open a socket."""

    def __init__(self, listings: list[dict[str, object]] | None = None) -> None:
        self.listings: list[dict[str, object]] = [] if listings is None else list(listings)
        self.calls: list[FixtureCall] = []
        self.posts = 0

    def exchange(self, call: FixtureCall) -> Mapping[str, object]:
        self.calls.append(call)
        if call.method == "GET":
            return {"results": list(self.listings)}
        if call.method == "POST":
            assert call.body is not None
            fields = dict(call.body)
            self.posts += 1
            row: dict[str, object] = {
                "listing_id": 5000 + self.posts,
                "title": fields["title"],
                "description": fields["description"],
                "state": "draft",
            }
            self.listings.append(row)
            return row
        raise AssertionError(call.method)


class _CrashAfterPost:
    def __init__(self, store: Store) -> None:
        self._store = store
        self.armed = True

    def exchange(self, call: FixtureCall) -> Mapping[str, object]:
        if call.method == "POST" and self.armed:
            saved = self._store.exchange(call)
            self.armed = False
            del saved
            raise RuntimeError("crash before record")
        return self._store.exchange(call)


class _ActivePost:
    def exchange(self, call: FixtureCall) -> Mapping[str, object]:
        if call.method == "GET":
            return {"results": []}
        assert call.body is not None
        fields = dict(call.body)
        return {
            "listing_id": 5,
            "state": "active",
            "title": fields["title"],
            "description": fields["description"],
        }


@pytest.fixture(autouse=True)
def _block_sockets(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("socket")

    def _connect(_self: socket.socket, address: object) -> None:
        _blocked(address)

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _connect)


def _client(store: Store | None = None) -> tuple[EtsyDraftClient, Store, DraftLedger]:
    target = Store() if store is None else store
    ledger = DraftLedger()
    return EtsyDraftClient(target, ledger), target, ledger


def test_the_measured_allowlist_is_the_draft_pair() -> None:
    assert (
        frozenset(
            {
                ("GET", "/v3/application/shops/{shop_id}/listings"),
                ("POST", "/v3/application/shops/{shop_id}/listings"),
            }
        )
        == MEASURED_ALLOWLIST
    )


def test_publish_and_activate_are_not_methods() -> None:
    public = {name for name in dir(EtsyDraftClient) if not name.startswith("_")}
    assert "publish" not in public
    assert "activate" not in public
    assert "update_listing" not in public
    assert "create_draft" in public
    assert "exchange" in public


def test_a_missing_or_real_token_never_opens_a_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EtsyDraftClient(None, DraftLedger())
    for present in (False, True):
        for name in _ETSY_ENV:
            if present:
                monkeypatch.setenv(name, _LIVE_TOKEN)
            else:
                monkeypatch.delenv(name, raising=False)
        with pytest.raises(EtsyDraftRefused) as caught:
            client.create_draft(_spec())
        assert caught.value.code == "fixture_transport"


def test_the_shop_id_comes_from_the_fixture_not_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ETSY_SHOP_ID", "999")
    monkeypatch.setenv("ETSY_ACCESS_TOKEN", _LIVE_TOKEN)
    client, store, _ledger = _client()
    receipt = client.create_draft(_spec())
    assert receipt.ready is True
    assert store.calls[0].path == "/v3/application/shops/123456/listings"
    assert "999" not in store.calls[0].path
    posted = store.calls[1]
    assert posted.body is not None
    blob = " ".join(value for _name, value in posted.body)
    assert _LIVE_TOKEN not in blob


def test_patch_state_active_never_reaches_the_transport() -> None:
    client, store, _ledger = _client()
    with pytest.raises(EtsyDraftRefused) as caught:
        client.exchange(
            "PATCH",
            "/v3/application/shops/123456/listings",
            (),
            (("state", "active"),),
        )
    assert caught.value.code == "off_list"
    assert store.calls == []


def test_a_state_field_on_create_is_refused_before_the_transport() -> None:
    client, store, _ledger = _client()
    with pytest.raises(EtsyDraftRefused) as caught:
        client.exchange(
            "POST",
            "/v3/application/shops/123456/listings",
            (),
            (("state", "active"),),
        )
    assert caught.value.code == "state_field"
    assert store.calls == []


def test_lookup_state_must_be_draft() -> None:
    client, store, _ledger = _client()
    with pytest.raises(EtsyDraftRefused) as caught:
        client.exchange(
            "GET",
            "/v3/application/shops/123456/listings",
            (("state", "active"),),
            None,
        )
    assert caught.value.code == "lookup_state"
    assert store.calls == []


def test_the_create_body_has_no_state_field() -> None:
    spec = _spec()
    client, store, _ledger = _client()
    receipt = client.create_draft(spec)
    assert isinstance(receipt, DraftReceipt)
    assert receipt.state == "draft"
    assert receipt.ready is True
    get_call, post_call = store.calls
    assert get_call.method == "GET"
    assert get_call.query == (("state", "draft"),)
    assert post_call.body is not None
    names = tuple(name for name, _value in post_call.body)
    assert names == (
        "quantity",
        "title",
        "description",
        "price",
        "who_made",
        "when_made",
        "taxonomy_id",
        "type",
    )
    fields = dict(post_call.body)
    assert "state" not in fields
    assert fields["type"] == "download"
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    assert fields["description"].split("\n")[-1] == marker
    assert receipt.marker == marker


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("spec_version", 0, "spec_version"),
        ("shop_id", 0, "shop_id"),
        ("quantity", 0, "quantity"),
        ("taxonomy_id", 0, "taxonomy_id"),
        ("spec_version", True, "spec_version"),
        ("quantity", True, "quantity"),
        ("taxonomy_id", True, "taxonomy_id"),
        ("title", "", "title"),
        ("title", "two\nlines", "title"),
        ("title", "two\rlines", "title"),
        ("price", "", "price"),
    ],
)
def test_a_bad_draft_field_is_refused_before_the_transport(
    field: str,
    value: object,
    code: str,
) -> None:
    client, store, _ledger = _client()
    spec = replace(_spec(), **{field: value})
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == code
    assert store.calls == []


def test_a_boolean_shop_id_is_refused() -> None:
    client, store, _ledger = _client()
    spec = replace(_spec(), shop_id=True)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "shop_id"
    assert store.calls == []


def test_pending_is_written_before_the_call() -> None:
    spec = _spec()
    store = Store()
    ledger = DraftLedger()
    seen: list[str] = []

    class _Watch:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            entry = ledger.get(spec.spec_version, fixture_hash(spec))
            assert entry is not None
            seen.append(entry.status)
            return store.exchange(call)

    receipt = EtsyDraftClient(_Watch(), ledger).create_draft(spec)
    assert seen == ["pending", "pending"]
    assert receipt.listing_id == 5001
    assert ledger.get(spec.spec_version, fixture_hash(spec)) is not None
    recorded = ledger.get(spec.spec_version, fixture_hash(spec))
    assert recorded is not None
    assert recorded.status == "recorded"


def test_a_plain_retry_creates_no_second_listing() -> None:
    client, store, _ledger = _client()
    spec = _spec()
    first = client.create_draft(spec)
    calls = len(store.calls)
    second = client.create_draft(spec)
    assert second.listing_id == first.listing_id
    assert store.posts == 1
    assert len(store.calls) == calls


def test_a_crash_after_create_adopts_the_existing_draft() -> None:
    spec = _spec()
    store = Store()
    ledger = DraftLedger()
    client = EtsyDraftClient(_CrashAfterPost(store), ledger)
    with pytest.raises(RuntimeError, match="crash before record"):
        client.create_draft(spec)
    receipt = client.create_draft(spec)
    assert store.posts == 1
    assert receipt.listing_id == 5001
    assert receipt.ready is True
    assert receipt.state == "draft"
    recorded = ledger.get(spec.spec_version, fixture_hash(spec))
    assert recorded is not None
    assert recorded.status == "recorded"
    assert recorded.listing_id == 5001


@pytest.mark.parametrize(
    "description",
    [
        "A fixture description.",
        "A fixture description.\nmm-draft:2:" + ("0" * 64),
    ],
)
def test_a_same_title_decoy_is_not_adopted(description: str) -> None:
    spec = _spec()
    decoy: dict[str, object] = {
        "listing_id": 9,
        "title": spec.title,
        "description": description,
        "state": "draft",
    }
    client, store, _ledger = _client(Store([decoy]))
    receipt = client.create_draft(spec)
    assert receipt.listing_id == 5001
    assert store.posts == 1
    assert store.listings[0]["listing_id"] == 9


def test_a_marker_inside_a_longer_line_is_not_adopted() -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    decoy: dict[str, object] = {
        "listing_id": 9,
        "title": "Different title",
        "description": f"A fixture description.\nx{marker}",
        "state": "draft",
    }
    client, store, _ledger = _client(Store([decoy]))
    receipt = client.create_draft(spec)
    assert receipt.listing_id != 9
    assert store.posts == 1


def test_an_active_create_response_is_not_recorded() -> None:
    spec = _spec()
    ledger = DraftLedger()
    client = EtsyDraftClient(_ActivePost(), ledger)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "active"
    entry = ledger.get(spec.spec_version, fixture_hash(spec))
    assert entry is None or entry.listing_id is None


def test_an_active_listing_with_the_marker_is_not_adopted() -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    decoy: dict[str, object] = {
        "listing_id": 9,
        "title": spec.title,
        "description": f"{spec.description}\n{marker}",
        "state": "active",
    }
    client, store, ledger = _client(Store([decoy]))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "active"
    assert store.posts == 0
    entry = ledger.get(spec.spec_version, fixture_hash(spec))
    assert entry is None or entry.listing_id is None


def test_two_listings_with_the_same_marker_are_refused() -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    description = f"{spec.description}\n{marker}"
    rows: list[dict[str, object]] = [
        {
            "listing_id": listing_id,
            "title": "other",
            "description": description,
            "state": "draft",
        }
        for listing_id in (1, 2)
    ]
    client, store, _ledger = _client(Store(rows))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "duplicate_marker"
    assert store.posts == 0


def test_a_listing_id_path_is_off_list() -> None:
    client, store, _ledger = _client()
    with pytest.raises(EtsyDraftRefused) as caught:
        client.exchange(
            "GET",
            "/v3/application/shops/123456/listings/9",
            (("state", "draft"),),
            None,
        )
    assert caught.value.code == "off_list"
    assert store.calls == []


def test_a_recorded_row_is_not_replaced_by_pending() -> None:
    ledger = DraftLedger()
    digest = "ab" * 32
    ledger.record(2, digest, 5001)
    ledger.put_pending(2, digest)
    entry = ledger.get(2, digest)
    assert entry is not None
    assert entry.status == "recorded"
    assert entry.listing_id == 5001


def test_a_decoy_without_a_description_is_not_adopted() -> None:
    spec = _spec()
    decoy: dict[str, object] = {
        "listing_id": 9,
        "title": "Different title",
        "description": None,
        "state": "draft",
    }
    client, store, _ledger = _client(Store([decoy]))
    receipt = client.create_draft(spec)
    assert receipt.listing_id == 5001
    assert store.posts == 1


def test_a_non_dict_result_is_malformed() -> None:
    class _Row:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            del call
            return {"results": ["nope"]}

    client = EtsyDraftClient(_Row(), DraftLedger())
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "malformed"


def test_a_create_response_without_the_marker_is_refused() -> None:
    spec = _spec()
    ledger = DraftLedger()

    class _NoMarker:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "GET":
                return {"results": []}
            return {"listing_id": 5, "state": "draft", "description": "no marker"}

    client = EtsyDraftClient(_NoMarker(), ledger)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "marker"
    entry = ledger.get(spec.spec_version, fixture_hash(spec))
    assert entry is None or entry.listing_id is None


@pytest.mark.parametrize("listing_id", [0, "5"])
def test_a_create_response_listing_id_must_be_a_positive_int(listing_id: object) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))

    class _BadId:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "GET":
                return {"results": []}
            return {
                "listing_id": listing_id,
                "state": "draft",
                "description": f"{spec.description}\n{marker}",
            }

    ledger = DraftLedger()
    refused = EtsyDraftClient(_BadId(), ledger)
    with pytest.raises(EtsyDraftRefused) as caught:
        refused.create_draft(spec)
    assert caught.value.code == "malformed"
    entry = ledger.get(spec.spec_version, fixture_hash(spec))
    assert entry is None or entry.listing_id is None


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("", None),
        ("A fixture description.", "separate-line"),
        ("A fixture description.\n", "keep-newline"),
    ],
)
def test_the_marker_is_its_own_line(description: str, expected: str | None) -> None:
    spec = replace(_spec(), description=description)
    client, store, _ledger = _client()
    client.create_draft(spec)
    posted = store.calls[1]
    assert posted.body is not None
    fields = dict(posted.body)
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    if expected is None:
        assert fields["description"] == marker
    elif expected == "separate-line":
        assert fields["description"] == description + "\n" + marker
    else:
        assert fields["description"] == description + marker


def test_a_lookup_without_results_is_malformed() -> None:
    class _Bare:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            del call
            return {}

    client = EtsyDraftClient(_Bare(), DraftLedger())
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "malformed"
