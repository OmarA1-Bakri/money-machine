"""Fixture Etsy draft client. Each guard has its own kill."""

from __future__ import annotations

import os
import socket
import stat
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
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
    FixtureTransport,
    draft_marker,
    fixture_hash,
)

_FIXTURE_PAGE = 25

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
            query = dict(call.query)
            state = query.get("state", "active")
            limit = int(query["limit"]) if "limit" in query else _FIXTURE_PAGE
            offset = int(query["offset"]) if "offset" in query else 0
            matched = [row for row in self.listings if row.get("state") == state]
            return {"count": len(matched), "results": matched[offset : offset + limit]}
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
            return {"count": 0, "results": []}
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


def _client(
    directory: Path, store: Store | None = None
) -> tuple[EtsyDraftClient, Store, DraftLedger]:
    target = Store() if store is None else store
    ledger = DraftLedger(directory)
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


def test_a_missing_or_real_token_never_opens_a_socket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = EtsyDraftClient(None, DraftLedger(tmp_path))
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETSY_SHOP_ID", "999")
    monkeypatch.setenv("ETSY_ACCESS_TOKEN", _LIVE_TOKEN)
    client, store, _ledger = _client(tmp_path)
    receipt = client.create_draft(_spec())
    assert receipt.ready is True
    assert store.calls[0].path == "/v3/application/shops/123456/listings"
    assert "999" not in store.calls[0].path
    posted = next(call for call in store.calls if call.method == "POST")
    assert posted.body is not None
    blob = " ".join(value for _name, value in posted.body)
    assert _LIVE_TOKEN not in blob


def test_patch_state_active_never_reaches_the_transport(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.exchange(
            "PATCH",
            "/v3/application/shops/123456/listings",
            (),
            (("state", "active"),),
        )
    assert caught.value.code == "off_list"
    assert store.calls == []


def test_a_state_field_on_create_is_refused_before_the_transport(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.exchange(
            "POST",
            "/v3/application/shops/123456/listings",
            (),
            (("state", "active"),),
        )
    assert caught.value.code == "body_extra"
    assert store.calls == []


def test_lookup_state_must_be_draft(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.exchange(
            "GET",
            "/v3/application/shops/123456/listings",
            (("state", "active"),),
            None,
        )
    assert caught.value.code == "lookup_state"
    assert store.calls == []


def test_the_create_body_has_no_state_field(tmp_path: Path) -> None:
    spec = _spec()
    client, store, _ledger = _client(tmp_path)
    receipt = client.create_draft(spec)
    assert isinstance(receipt, DraftReceipt)
    assert receipt.state == "draft"
    assert receipt.ready is True
    gets = [call for call in store.calls if call.method == "GET"]
    posts = [call for call in store.calls if call.method == "POST"]
    assert len(gets) == 2
    assert len(posts) == 1
    assert all(
        call.query == (("state", "draft"), ("limit", "100"), ("offset", "0")) for call in gets
    )
    post_call = posts[0]
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
    tmp_path: Path,
    field: str,
    value: object,
    code: str,
) -> None:
    client, store, _ledger = _client(tmp_path)
    spec = replace(_spec(), **{field: value})
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == code
    assert store.calls == []


def test_a_boolean_shop_id_is_refused(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    spec = replace(_spec(), shop_id=True)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "shop_id"
    assert store.calls == []


def test_pending_is_written_before_the_call(tmp_path: Path) -> None:
    spec = _spec()
    store = Store()
    ledger = DraftLedger(tmp_path)
    seen: list[str | None] = []

    class _Watch:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            entry = ledger.get(spec.spec_version, fixture_hash(spec))
            seen.append(None if entry is None else entry.status)
            if call.method == "POST":
                assert entry is not None
                assert entry.status == "pending"
                assert any(tmp_path.iterdir())
            return store.exchange(call)

    receipt = EtsyDraftClient(_Watch(), ledger).create_draft(spec)
    assert seen == [None, None, "pending"]
    assert receipt.listing_id == 5001
    recorded = ledger.get(spec.spec_version, fixture_hash(spec))
    assert recorded is not None
    assert recorded.status == "recorded"


def test_a_plain_retry_creates_no_second_listing(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    spec = _spec()
    first = client.create_draft(spec)
    calls = len(store.calls)
    second = client.create_draft(spec)
    assert second.listing_id == first.listing_id
    assert store.posts == 1
    assert len(store.calls) == calls


def test_a_crash_after_create_adopts_the_existing_draft(tmp_path: Path) -> None:
    spec = _spec()
    store = Store()
    ledger = DraftLedger(tmp_path)
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
def test_a_same_title_decoy_is_not_adopted(tmp_path: Path, description: str) -> None:
    spec = _spec()
    decoy: dict[str, object] = {
        "listing_id": 9,
        "title": spec.title,
        "description": description,
        "state": "draft",
    }
    client, store, _ledger = _client(tmp_path, Store([decoy]))
    receipt = client.create_draft(spec)
    assert receipt.listing_id == 5001
    assert store.posts == 1
    assert store.listings[0]["listing_id"] == 9


def test_a_marker_inside_a_longer_line_is_not_adopted(tmp_path: Path) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    decoy: dict[str, object] = {
        "listing_id": 9,
        "title": "Different title",
        "description": f"A fixture description.\nx{marker}",
        "state": "draft",
    }
    client, store, _ledger = _client(tmp_path, Store([decoy]))
    receipt = client.create_draft(spec)
    assert receipt.listing_id != 9
    assert store.posts == 1


def test_an_active_create_response_is_not_recorded(tmp_path: Path) -> None:
    spec = _spec()
    ledger = DraftLedger(tmp_path)
    client = EtsyDraftClient(_ActivePost(), ledger)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "active"
    entry = ledger.get(spec.spec_version, fixture_hash(spec))
    assert entry is None or entry.listing_id is None


def test_an_active_listing_with_the_marker_is_not_adopted(tmp_path: Path) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    decoy: dict[str, object] = {
        "listing_id": 9,
        "title": spec.title,
        "description": f"{spec.description}\n{marker}",
        "state": "active",
    }

    class _Visible:
        def __init__(self) -> None:
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "GET":
                return {"count": 1, "results": [decoy]}
            self.posts += 1
            return {"listing_id": 5, "state": "draft", "description": "x"}

    visible = _Visible()
    ledger = DraftLedger(tmp_path)
    client = EtsyDraftClient(visible, ledger)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "active"
    assert visible.posts == 0
    entry = ledger.get(spec.spec_version, fixture_hash(spec))
    assert entry is None or entry.listing_id is None


def test_two_listings_with_the_same_marker_are_refused(tmp_path: Path) -> None:
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
    client, store, _ledger = _client(tmp_path, Store(rows))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "duplicate_marker"
    assert store.posts == 0


def test_a_listing_id_path_is_off_list(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.exchange(
            "GET",
            "/v3/application/shops/123456/listings/9",
            (("state", "draft"),),
            None,
        )
    assert caught.value.code == "off_list"
    assert store.calls == []


def test_a_recorded_row_is_not_replaced_by_pending(tmp_path: Path) -> None:
    ledger = DraftLedger(tmp_path)
    digest = "ab" * 32
    ledger.record(2, digest, 5001)
    ledger.put_pending(2, digest)
    entry = ledger.get(2, digest)
    assert entry is not None
    assert entry.status == "recorded"
    assert entry.listing_id == 5001


def test_a_decoy_without_a_description_is_not_adopted(tmp_path: Path) -> None:
    spec = _spec()
    decoy: dict[str, object] = {
        "listing_id": 9,
        "title": "Different title",
        "description": None,
        "state": "draft",
    }
    client, store, _ledger = _client(tmp_path, Store([decoy]))
    receipt = client.create_draft(spec)
    assert receipt.listing_id == 5001
    assert store.posts == 1


def test_a_non_dict_result_is_malformed(tmp_path: Path) -> None:
    class _Row:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            del call
            return {"count": 1, "results": ["nope"]}

    client = EtsyDraftClient(_Row(), DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "malformed"


def test_a_create_response_without_the_marker_is_refused(tmp_path: Path) -> None:
    spec = _spec()
    ledger = DraftLedger(tmp_path)

    class _NoMarker:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "GET":
                return {"count": 0, "results": []}
            return {"listing_id": 5, "state": "draft", "description": "no marker"}

    client = EtsyDraftClient(_NoMarker(), ledger)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "marker"
    entry = ledger.get(spec.spec_version, fixture_hash(spec))
    assert entry is None or entry.listing_id is None


@pytest.mark.parametrize("listing_id", [0, "5"])
def test_a_create_response_listing_id_must_be_a_positive_int(
    tmp_path: Path, listing_id: object
) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))

    class _BadId:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "GET":
                return {"count": 0, "results": []}
            return {
                "listing_id": listing_id,
                "state": "draft",
                "description": f"{spec.description}\n{marker}",
            }

    ledger = DraftLedger(tmp_path)
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
def test_the_marker_is_its_own_line(tmp_path: Path, description: str, expected: str | None) -> None:
    spec = replace(_spec(), description=description)
    client, store, _ledger = _client(tmp_path)
    client.create_draft(spec)
    posted = next(call for call in store.calls if call.method == "POST")
    assert posted.body is not None
    fields = dict(posted.body)
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    if expected is None:
        assert fields["description"] == marker
    elif expected == "separate-line":
        assert fields["description"] == description + "\n" + marker
    else:
        assert fields["description"] == description + marker


def test_a_lookup_without_results_is_malformed(tmp_path: Path) -> None:
    class _Bare:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            del call
            return {}

    client = EtsyDraftClient(_Bare(), DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "malformed"


_LISTINGS = "/v3/application/shops/123456/listings"
_BODY = (
    ("quantity", "999"),
    ("title", "Fixture planner"),
    ("description", "A fixture description."),
    ("price", "11.00"),
    ("who_made", "i_did"),
    ("when_made", "2020_2026"),
    ("taxonomy_id", "1"),
    ("type", "download"),
)


def _draft_row(listing_id: int, description: str = "decoy") -> dict[str, object]:
    return {
        "listing_id": listing_id,
        "title": f"decoy {listing_id}",
        "description": description,
        "state": "draft",
    }


def _orphan_rows(spec: DraftSpec) -> list[dict[str, object]]:
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    rows = [_draft_row(1000 + index) for index in range(100)]
    rows.append(
        {
            "listing_id": 42,
            "title": "not the fixture title",
            "description": f"{spec.description}\n{marker}",
            "state": "draft",
        }
    )
    return rows


def _refuse(
    client: EtsyDraftClient,
    method: str,
    query: tuple[tuple[str, str], ...],
    body: tuple[tuple[str, str], ...] | None,
) -> str:
    with pytest.raises(EtsyDraftRefused) as caught:
        client.exchange(method, _LISTINGS, query, body)
    return caught.value.code


def test_the_ledger_directory_is_required() -> None:
    with pytest.raises(TypeError):
        DraftLedger()  # pyright: ignore[reportCallIssue]


def test_an_empty_ledger_adopts_the_page_two_orphan_without_a_post(tmp_path: Path) -> None:
    spec = _spec()
    store = Store(_orphan_rows(spec))
    client, _same, ledger = _client(tmp_path, store)
    receipt = client.create_draft(spec)
    assert receipt.listing_id == 42
    assert store.posts == 0
    recorded = ledger.get(spec.spec_version, fixture_hash(spec))
    assert recorded is not None
    assert recorded.status == "recorded"
    assert recorded.listing_id == 42


def test_a_pending_restart_adopts_when_lookup_finds_the_draft(tmp_path: Path) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    DraftLedger(tmp_path).put_pending(spec.spec_version, fixture_hash(spec))
    row: dict[str, object] = {
        "listing_id": 42,
        "title": "other",
        "description": f"{spec.description}\n{marker}",
        "state": "draft",
    }
    transport, posts = _show(row)
    receipt = EtsyDraftClient(transport, DraftLedger(tmp_path)).create_draft(spec)
    assert receipt.listing_id == 42
    assert posts == []


def test_a_restart_adopts_the_page_two_orphan_without_a_post(tmp_path: Path) -> None:
    spec = _spec()
    digest = fixture_hash(spec)
    DraftLedger(tmp_path).put_pending(spec.spec_version, digest)
    store = Store(_orphan_rows(spec))
    client = EtsyDraftClient(store, DraftLedger(tmp_path))
    receipt = client.create_draft(spec)
    assert receipt.listing_id == 42
    assert store.posts == 0
    recorded = DraftLedger(tmp_path).get(spec.spec_version, digest)
    assert recorded is not None
    assert recorded.listing_id == 42


def test_a_pending_key_with_no_draft_does_not_post(tmp_path: Path) -> None:
    spec = _spec()
    DraftLedger(tmp_path).put_pending(spec.spec_version, fixture_hash(spec))
    store = Store()
    client = EtsyDraftClient(store, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "pending"
    assert store.posts == 0


def test_a_broken_pending_symlink_refuses_to_post(tmp_path: Path) -> None:
    spec = _spec()
    digest = fixture_hash(spec)
    (tmp_path / f"{spec.spec_version}-{digest}").symlink_to(tmp_path / "missing")
    store = Store()
    client = EtsyDraftClient(store, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "ledger"
    assert store.posts == 0


def test_an_unreadable_pending_file_refuses_to_post(tmp_path: Path) -> None:
    spec = _spec()
    digest = fixture_hash(spec)
    target = tmp_path / "readable-pending"
    target.write_bytes(b"pending\n")
    (tmp_path / f"{spec.spec_version}-{digest}").symlink_to(target)
    store = Store()
    client = EtsyDraftClient(store, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "ledger"
    assert store.posts == 0


def test_a_corrupt_pending_file_refuses_to_post(tmp_path: Path) -> None:
    spec = _spec()
    digest = fixture_hash(spec)
    (tmp_path / f"{spec.spec_version}-{digest}").write_bytes(b"nope\n")
    store = Store()
    client = EtsyDraftClient(store, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "ledger_corrupt"
    assert store.posts == 0


def test_the_ledger_create_is_exclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    digest = "ab" * 32
    path = tmp_path / f"2-{digest}.next"
    path.write_bytes(b"already\n")
    seen: list[int] = []
    real_open = os.open

    def _spy(opened: object, flags: int, mode: int = 0o777) -> int:
        seen.append(flags)
        return real_open(opened, flags, mode)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "open", _spy)
    DraftLedger(tmp_path).record(2, digest, 7)
    assert not path.exists()
    entry = DraftLedger(tmp_path).get(2, digest)
    assert entry is not None
    assert entry.listing_id == 7
    assert any(item & os.O_EXCL for item in seen)


def test_the_ledger_create_does_not_follow_a_symlink(tmp_path: Path) -> None:
    digest = "cd" * 32
    target = tmp_path / "stolen"
    target.write_bytes(b"safe")
    (tmp_path / f"2-{digest}.next").symlink_to(target)
    DraftLedger(tmp_path).record(2, digest, 7)
    assert target.read_bytes() == b"safe"
    entry = DraftLedger(tmp_path).get(2, digest)
    assert entry is not None
    assert entry.listing_id == 7


def _create_open_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[int]:
    seen: list[int] = []
    real_open = os.open

    def _spy(path: object, flags: int, mode: int = 0o777) -> int:
        seen.append(flags)
        return real_open(path, flags, mode)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "open", _spy)
    with suppress(OSError):
        DraftLedger(tmp_path).put_pending(2, "ef" * 32)
    return seen


def test_the_pending_create_uses_nofollow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flags = _create_open_flags(tmp_path, monkeypatch)
    assert any(item & os.O_NOFOLLOW for item in flags)


def test_the_pending_create_uses_exclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flags = _create_open_flags(tmp_path, monkeypatch)
    assert any(item & os.O_EXCL for item in flags)


def test_the_pending_create_uses_create(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flags = _create_open_flags(tmp_path, monkeypatch)
    assert any(item & os.O_CREAT for item in flags)


def _fsync_kinds(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    kinds: list[str] = []
    real = os.fsync

    def _spy(fd: int) -> None:
        mode = os.fstat(fd).st_mode
        if stat.S_ISREG(mode):
            kinds.append("file")
        elif stat.S_ISDIR(mode):
            kinds.append("dir")
        real(fd)

    monkeypatch.setattr(os, "fsync", _spy)
    return kinds


def test_put_pending_fsyncs_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kinds = _fsync_kinds(monkeypatch)
    DraftLedger(tmp_path).put_pending(2, "ab" * 32)
    assert kinds[0] == "file"


def test_put_pending_fsyncs_the_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kinds = _fsync_kinds(monkeypatch)
    DraftLedger(tmp_path).put_pending(2, "cd" * 32)
    assert "dir" in kinds


def test_fsync_happens_before_the_post(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    events = _fsync_kinds(monkeypatch)
    store = Store()

    class _Watch:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                events.append("post")
            return store.exchange(call)

    EtsyDraftClient(_Watch(), DraftLedger(tmp_path)).create_draft(_spec())
    posted = events.index("post")
    assert events.index("file") < posted
    assert events.index("dir") < posted


def test_a_full_page_cap_refuses_to_post(tmp_path: Path) -> None:
    class _Endless:
        def __init__(self) -> None:
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return {"listing_id": 5, "state": "draft", "description": "x"}
            self.gets += 1
            if self.gets > 15:
                return {"count": 0, "results": []}
            start = (self.gets - 1) * 100
            results = [_draft_row(start + index + 1) for index in range(100)]
            return {"count": 99999, "results": results}

    endless = _Endless()
    client = EtsyDraftClient(endless, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "page_cap"
    assert endless.posts == 0


def test_a_count_that_changes_between_pages_refuses_to_post(tmp_path: Path) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    marked = {
        "listing_id": 9000,
        "title": "other",
        "description": f"{spec.description}\n{marker}",
        "state": "draft",
    }

    class _Grow:
        def __init__(self) -> None:
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return {"listing_id": 5, "state": "draft", "description": "x"}
            self.gets += 1
            if self.gets == 1:
                results = [_draft_row(index + 1) for index in range(100)]
                return {"count": 101, "results": results}
            return {"count": 102, "results": [marked]}

    grow = _Grow()
    client = EtsyDraftClient(grow, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused):
        client.create_draft(spec)
    assert grow.posts == 0


def test_a_short_page_whose_count_does_not_match_refuses_to_post(tmp_path: Path) -> None:
    class _Short:
        def __init__(self) -> None:
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return {"listing_id": 5, "state": "draft", "description": "x"}
            return {"count": 5, "results": []}

    short = _Short()
    client = EtsyDraftClient(short, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "count"
    assert short.posts == 0


def test_a_repeated_listing_id_refuses_to_post(tmp_path: Path) -> None:
    class _Dup:
        def __init__(self) -> None:
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return {"listing_id": 5, "state": "draft", "description": "x"}
            self.gets += 1
            if self.gets == 1:
                results = [_draft_row(index + 1) for index in range(100)]
                return {"count": 101, "results": results}
            return {"count": 101, "results": [_draft_row(1)]}

    dup = _Dup()
    client = EtsyDraftClient(dup, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused):
        client.create_draft(_spec())
    assert dup.posts == 0


def test_a_page_longer_than_the_limit_is_malformed(tmp_path: Path) -> None:
    class _Long:
        def __init__(self) -> None:
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return {"listing_id": 5, "state": "draft", "description": "x"}
            return {"count": 101, "results": [_draft_row(index + 1) for index in range(101)]}

    long_page = _Long()
    client = EtsyDraftClient(long_page, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "malformed"
    assert long_page.posts == 0


def test_a_lookup_transport_error_refuses_to_post(tmp_path: Path) -> None:
    class _Down:
        def __init__(self) -> None:
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "GET":
                raise RuntimeError("down")
            self.posts += 1
            return {"listing_id": 5, "state": "draft", "description": "x"}

    down = _Down()
    client = EtsyDraftClient(down, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "transport"
    assert down.posts == 0


def test_a_lookup_refusal_is_not_relabelled_as_transport(tmp_path: Path) -> None:
    class _Already:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            del call
            raise EtsyDraftRefused("from_transport")

    client = EtsyDraftClient(_Already(), DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "from_transport"


def test_an_insert_and_delete_with_a_pending_key_does_not_post(tmp_path: Path) -> None:
    spec = _spec()
    DraftLedger(tmp_path).put_pending(spec.spec_version, fixture_hash(spec))

    class _Shift:
        def __init__(self) -> None:
            self.rows = [_draft_row(index + 1) for index in range(101)]
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return {"listing_id": 5, "state": "draft", "description": "x"}
            self.gets += 1
            if self.gets == 2:
                self.rows.pop(0)
                self.rows.append(_draft_row(9000))
            query = dict(call.query)
            offset = int(query["offset"])
            limit = int(query["limit"])
            return {"count": len(self.rows), "results": self.rows[offset : offset + limit]}

    shift = _Shift()
    client = EtsyDraftClient(shift, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "count"
    assert shift.posts == 0


def test_an_unknown_query_key_is_refused_before_the_transport(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    code = _refuse(
        client,
        "GET",
        (("state", "draft"), ("limit", "100"), ("offset", "0"), ("sort_on", "created")),
        None,
    )
    assert code == "query_key"
    assert store.calls == []


def test_a_get_with_a_body_is_refused_before_the_transport(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    code = _refuse(client, "GET", (("state", "draft"),), (("quantity", "1"),))
    assert code == "query_key"
    assert store.calls == []


def test_a_query_key_that_changes_case_is_refused(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    assert _refuse(client, "GET", (("State", "draft"),), None) == "query_case"
    assert store.calls == []


def test_a_query_key_with_whitespace_is_refused(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    assert _refuse(client, "GET", (("state ", "draft"),), None) == "query_space"
    assert store.calls == []


def test_a_duplicated_query_key_is_refused(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    code = _refuse(client, "GET", (("state", "draft"), ("state", "draft")), None)
    assert code == "query_duplicate"
    assert store.calls == []


def test_a_lookup_without_state_is_refused(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.exchange("GET", _LISTINGS, (("limit", "25"), ("offset", "0")), None)
    assert caught.value.code == "lookup_state"
    assert store.calls == []


def test_a_page_zero_reread_count_change_refuses_to_post(tmp_path: Path) -> None:
    class _GrowAfter:
        def __init__(self) -> None:
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return {"listing_id": 5, "state": "draft", "description": "x"}
            self.gets += 1
            if self.gets == 1:
                return {"count": 1, "results": [_draft_row(1)]}
            return {"count": 2, "results": [_draft_row(1), _draft_row(2)]}

    race = _GrowAfter()
    client = EtsyDraftClient(race, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "count"
    assert race.posts == 0


def _post_body() -> dict[str, object]:
    return {"listing_id": 5, "state": "draft", "description": "x"}


@pytest.mark.parametrize("bad", [True, 1.0, "1", None])
def test_a_reread_count_must_be_an_exact_int(tmp_path: Path, bad: object) -> None:
    class _BadCount:
        def __init__(self) -> None:
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return _post_body()
            self.gets += 1
            row = [_draft_row(1)]
            if self.gets == 1:
                return {"count": 1, "results": row}
            return {"count": bad, "results": row}

    race = _BadCount()
    client = EtsyDraftClient(race, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "malformed"
    assert race.posts == 0


def test_a_reread_transport_error_refuses_to_post(tmp_path: Path) -> None:
    class _Down:
        def __init__(self) -> None:
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return _post_body()
            self.gets += 1
            if self.gets > 1:
                raise RuntimeError("down")
            return {"count": 1, "results": [_draft_row(1)]}

    down = _Down()
    client = EtsyDraftClient(down, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "transport"
    assert down.posts == 0


def test_a_reread_without_results_is_malformed(tmp_path: Path) -> None:
    class _Missing:
        def __init__(self) -> None:
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return _post_body()
            self.gets += 1
            if self.gets == 1:
                return {"count": 1, "results": [_draft_row(1)]}
            return {"count": 1}

    missing = _Missing()
    client = EtsyDraftClient(missing, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "malformed"
    assert missing.posts == 0


def test_a_true_listing_id_on_the_first_read_is_malformed(tmp_path: Path) -> None:
    class _TrueId:
        def __init__(self) -> None:
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return _post_body()
            row = _draft_row(1)
            row["listing_id"] = True
            return {"count": 1, "results": [row]}

    bad = _TrueId()
    client = EtsyDraftClient(bad, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "malformed"
    assert bad.posts == 0


def test_a_true_listing_id_on_the_reread_is_malformed(tmp_path: Path) -> None:
    class _TrueId:
        def __init__(self) -> None:
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return _post_body()
            self.gets += 1
            row = _draft_row(1)
            if self.gets > 1:
                row["listing_id"] = True
            return {"count": 1, "results": [row]}

    bad = _TrueId()
    client = EtsyDraftClient(bad, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "malformed"
    assert bad.posts == 0


def test_a_duplicate_listing_id_on_the_first_read_refuses_to_post(tmp_path: Path) -> None:
    class _Dup:
        def __init__(self) -> None:
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return _post_body()
            return {"count": 2, "results": [_draft_row(1), _draft_row(1)]}

    dup = _Dup()
    client = EtsyDraftClient(dup, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "count"
    assert dup.posts == 0


def test_a_duplicate_listing_id_on_the_reread_refuses_to_post(tmp_path: Path) -> None:
    class _Dup:
        def __init__(self) -> None:
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return _post_body()
            self.gets += 1
            if self.gets == 1:
                return {"count": 2, "results": [_draft_row(1), _draft_row(2)]}
            return {"count": 2, "results": [_draft_row(1), _draft_row(1)]}

    dup = _Dup()
    client = EtsyDraftClient(dup, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(_spec())
    assert caught.value.code == "count"
    assert dup.posts == 0


def test_an_equal_count_swap_onto_page_one_refuses_to_post(tmp_path: Path) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    rows = [_draft_row(index + 1) for index in range(101)]
    rows[100] = _draft_row(9001, f"{spec.description}\n{marker}")

    class _Swap:
        def __init__(self) -> None:
            self.posts = 0
            self.shifted = False

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return _post_body()
            query = dict(call.query)
            if query["offset"] == "100" and not self.shifted:
                rows.pop(0)
                rows.append(_draft_row(9002))
                self.shifted = True
            offset = int(query["offset"])
            return {"count": len(rows), "results": rows[offset : offset + 100]}

    swap = _Swap()
    client = EtsyDraftClient(swap, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "count"
    assert swap.posts == 0


def test_a_marker_swap_between_existing_ids_refuses_to_post(tmp_path: Path) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    marked = f"{spec.description}\n{marker}"
    decoy = "decoy"
    first = [_draft_row(1, marked), _draft_row(2, decoy)]
    second = [_draft_row(1, decoy), _draft_row(2, marked)]
    race = _TwoWalks(first, second)
    ledger = DraftLedger(tmp_path)
    client = EtsyDraftClient(race, ledger)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "count"
    assert race.posts == 0
    assert ledger.get(spec.spec_version, fixture_hash(spec)) is None


def test_a_reordered_description_still_posts(tmp_path: Path) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    first = [_draft_row(1, "alpha"), _draft_row(2, "beta")]
    second = [_draft_row(2, "beta"), _draft_row(1, "alpha")]

    class _Reorder:
        def __init__(self) -> None:
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return {
                    "listing_id": 5,
                    "state": "draft",
                    "description": f"{spec.description}\n{marker}",
                }
            rows = first if self.gets == 0 else second
            self.gets += 1
            return {"count": len(rows), "results": rows}

    race = _Reorder()
    client = EtsyDraftClient(race, DraftLedger(tmp_path))
    receipt = client.create_draft(spec)
    assert receipt.ready is True
    assert race.posts == 1


def test_an_empty_description_and_a_missing_one_still_post(tmp_path: Path) -> None:
    """A blank description and a row with no description field compare equal."""
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    empty = {
        "listing_id": 1,
        "title": "decoy 1",
        "description": "",
        "state": "draft",
    }
    missing = {"listing_id": 1, "title": "decoy 1", "state": "draft"}

    class _Blank:
        def __init__(self) -> None:
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return {
                    "listing_id": 5,
                    "state": "draft",
                    "description": f"{spec.description}\n{marker}",
                }
            rows = [empty] if self.gets == 0 else [missing]
            self.gets += 1
            return {"count": len(rows), "results": rows}

    race = _Blank()
    client = EtsyDraftClient(race, DraftLedger(tmp_path))
    receipt = client.create_draft(spec)
    assert receipt.ready is True
    assert race.posts == 1


def test_an_existing_description_change_refuses_to_post(tmp_path: Path) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    marked = f"{spec.description}\n{marker}"
    edited = f"{spec.description} Edited.\n{marker}"
    race = _TwoWalks([_draft_row(1, marked)], [_draft_row(1, edited)])
    ledger = DraftLedger(tmp_path)
    client = EtsyDraftClient(race, ledger)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "count"
    assert race.posts == 0
    assert ledger.get(spec.spec_version, fixture_hash(spec)) is None


class _TwoWalks:
    def __init__(self, first: list[dict[str, object]], second: list[dict[str, object]]) -> None:
        self._walks = (first, second)
        self.gets = 0
        self.posts = 0

    def exchange(self, call: FixtureCall) -> Mapping[str, object]:
        if call.method == "POST":
            self.posts += 1
            return _post_body()
        rows = self._walks[0 if self.gets == 0 else 1]
        self.gets += 1
        return {"count": len(rows), "results": rows}


def test_a_later_page_swap_with_the_ledger_lost_refuses_to_post(tmp_path: Path) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    rows = [_draft_row(index + 1) for index in range(270)]
    rows[100] = _draft_row(9001, f"{spec.description}\n{marker}")

    class _Later:
        def __init__(self) -> None:
            self.gets = 0
            self.posts = 0

        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "POST":
                self.posts += 1
                return _post_body()
            self.gets += 1
            if self.gets == 4:
                rows.pop(260)
                rows.append(_draft_row(9002))
            query = dict(call.query)
            offset = int(query["offset"])
            return {"count": len(rows), "results": rows[offset : offset + 100]}

    later = _Later()
    client = EtsyDraftClient(later, DraftLedger(tmp_path))
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "count"
    assert later.posts == 0


@pytest.mark.parametrize("limit", ["0", "101", "01", "x"])
def test_a_bad_limit_is_refused(tmp_path: Path, limit: str) -> None:
    client, store, _ledger = _client(tmp_path)
    code = _refuse(client, "GET", (("state", "draft"), ("limit", limit)), None)
    assert code == "query_limit"
    assert store.calls == []


@pytest.mark.parametrize("offset", ["-1", "01"])
def test_a_bad_offset_is_refused(tmp_path: Path, offset: str) -> None:
    client, store, _ledger = _client(tmp_path)
    code = _refuse(client, "GET", (("state", "draft"), ("offset", offset)), None)
    assert code == "query_offset"
    assert store.calls == []


def test_a_post_query_is_refused_before_the_transport(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    assert _refuse(client, "POST", (("state", "active"),), _BODY) == "post_query"
    assert store.calls == []


def test_a_post_query_key_that_changes_case_is_refused(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    assert _refuse(client, "POST", (("State", "active"),), _BODY) == "query_case"
    assert store.calls == []


def test_a_post_query_key_with_whitespace_is_refused(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    assert _refuse(client, "POST", (("state ", "active"),), _BODY) == "query_space"
    assert store.calls == []


def test_a_body_key_that_changes_case_is_refused(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    body = (("Quantity", "999"), *_BODY[1:])
    assert _refuse(client, "POST", (), body) == "body_case"
    assert store.calls == []


def test_a_body_key_with_whitespace_is_refused(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    body = (("quantity ", "999"), *_BODY[1:])
    assert _refuse(client, "POST", (), body) == "body_space"
    assert store.calls == []


def test_a_duplicated_body_key_is_refused(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    body = (*_BODY, ("quantity", "1"))
    assert _refuse(client, "POST", (), body) == "body_duplicate"
    assert store.calls == []


def test_a_missing_body_key_is_refused(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    body = tuple(pair for pair in _BODY if pair[0] != "price")
    assert _refuse(client, "POST", (), body) == "body_missing"
    assert store.calls == []


def test_a_missing_body_is_refused(tmp_path: Path) -> None:
    client, store, _ledger = _client(tmp_path)
    assert _refuse(client, "POST", (), None) == "body_missing"
    assert store.calls == []


def test_the_fixture_store_defaults_to_active_and_twenty_five() -> None:
    drafts = [_draft_row(index + 1) for index in range(30)]
    actives: list[dict[str, object]] = [
        {
            "listing_id": 7000 + index,
            "title": "active",
            "description": "active",
            "state": "active",
        }
        for index in range(30)
    ]
    store = Store([*drafts, *actives])
    payload = store.exchange(FixtureCall("GET", _LISTINGS, (), None))
    assert payload["count"] == 30
    results = payload["results"]
    assert isinstance(results, list)
    assert len(results) == _FIXTURE_PAGE
    assert all(isinstance(row, dict) and row.get("state") == "active" for row in results)


def _show(row: dict[str, object]) -> tuple[FixtureTransport, list[int]]:
    posts: list[int] = []

    class _Show:
        def exchange(self, call: FixtureCall) -> Mapping[str, object]:
            if call.method == "GET":
                return {"count": 1, "results": [row]}
            posts.append(1)
            return {"listing_id": 5, "state": "draft", "description": "x"}

    return _Show(), posts


def test_a_crlf_marker_line_is_adopted(tmp_path: Path) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    row: dict[str, object] = {
        "listing_id": 42,
        "title": "other",
        "description": f"A fixture description.\r\n{marker}\r\n",
        "state": "draft",
    }
    transport, posts = _show(row)
    receipt = EtsyDraftClient(transport, DraftLedger(tmp_path)).create_draft(spec)
    assert receipt.listing_id == 42
    assert posts == []


def test_a_trailing_space_on_the_marker_line_is_adopted(tmp_path: Path) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    row: dict[str, object] = {
        "listing_id": 42,
        "title": "other",
        "description": f"A fixture description.\n{marker} \t",
        "state": "draft",
    }
    transport, posts = _show(row)
    receipt = EtsyDraftClient(transport, DraftLedger(tmp_path)).create_draft(spec)
    assert receipt.listing_id == 42
    assert posts == []


def test_an_injected_marker_line_is_refused_before_the_transport(tmp_path: Path) -> None:
    spec = replace(_spec(), description="Hello\nmm-draft:2:" + ("a" * 64))
    client, store, _ledger = _client(tmp_path)
    with pytest.raises(EtsyDraftRefused) as caught:
        client.create_draft(spec)
    assert caught.value.code == "marker_injection"
    assert store.calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("description", "Other description."),
        ("spec_version", 3),
        ("title", "Other title"),
        ("price", "12.00"),
        ("shop_id", 99),
        ("quantity", 5),
        ("who_made", "collective"),
        ("when_made", "made_to_order"),
        ("taxonomy_id", 9),
        ("product_id", UUID("00000000-0000-4000-8000-0000000000b9")),
    ],
)
def test_a_changed_field_changes_the_fixture_hash(field: str, value: object) -> None:
    assert fixture_hash(_spec()) != fixture_hash(replace(_spec(), **{field: value}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("description", "Other description."),
        ("spec_version", 3),
        ("title", "Other title"),
    ],
)
def test_a_different_spec_does_not_adopt_the_other_draft(
    tmp_path: Path, field: str, value: object
) -> None:
    spec = _spec()
    marker = draft_marker(spec.spec_version, fixture_hash(spec))
    row: dict[str, object] = {
        "listing_id": 42,
        "title": spec.title,
        "description": f"{spec.description}\n{marker}",
        "state": "draft",
    }
    other = replace(spec, **{field: value})
    client, store, _ledger = _client(tmp_path, Store([row]))
    receipt = client.create_draft(other)
    assert receipt.listing_id != 42
    assert store.posts == 1


def test_the_marker_embeds_the_fixture_hash() -> None:
    spec = _spec()
    digest = fixture_hash(spec)
    assert draft_marker(spec.spec_version, digest) == f"mm-draft:{spec.spec_version}:{digest}"
    assert draft_marker(2, "a" * 64) != draft_marker(2, "b" * 64)
