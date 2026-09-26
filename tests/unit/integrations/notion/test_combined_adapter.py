"""Unit tests for CombinedNotionAdapter delegation and fallback.

Fakes only. No live Notion, no browser, no Playwright.
"""

from __future__ import annotations

from typing import cast

import pytest

from money_machine.integrations.notion.adapter import NotionAdapter
from money_machine.integrations.notion.combined_adapter import (
    API_OPERATIONS,
    BROWSER_OPERATIONS,
    COMBINED_OPERATIONS,
    CombinedNotionAdapter,
    OperationUnsupportedError,
)
from money_machine.integrations.notion.domain import (
    NotionFilter,
    NotionPage,
    NotionSort,
    NotionView,
)

_PAGE = NotionPage(id="page_from_delegate", title="delegated")
_VIEW = NotionView(
    id="view_from_delegate",
    database_id="db_from_delegate",
    name="Titles",
    type="table",
    title_visible=False,
)
_FILTER = NotionFilter(property="Name", condition="equals", value="A")
_SORT = NotionSort(property="Name", direction="ascending")
_PUBLIC_URL = "https://notion.site/Page-abc"

# Expected kwargs are fixed here. A dropped or rewritten argument fails that case.
_EXPECTED_CALLS: dict[str, dict[str, object]] = {
    "connection_status": {},
    "workspace_discovery": {},
    "create_page": {
        "title": "Title-distinct",
        "parent_id": "parent-9",
        "parent_type": "page_id",
        "icon": "📄",
        "cover": "https://example.com/cover-distinct.png",
    },
    "duplicate_page": {"page_id": "page-1"},
    "rename_page": {"page_id": "page-1", "new_title": "Renamed-title"},
    "move_page": {
        "page_id": "page-1",
        "new_parent_id": "parent-2",
        "new_parent_type": "database_id",
    },
    "set_icon": {"page_id": "page-1", "icon": "🔥"},
    "set_cover": {"page_id": "page-1", "cover_url": "https://example.com/cover.png"},
    "add_text_block": {"page_id": "page-1", "content": "hello-block"},
    "add_callout_block": {"page_id": "page-1", "content": "note-body", "icon": "📌"},
    "create_database": {
        "title": "Tasks-distinct",
        "parent_id": "parent-db",
        "parent_type": "page_id",
        "icon": "📁",
        "cover": "https://example.com/db-cover.png",
    },
    "add_property": {
        "database_id": "db-1",
        "name": "Name",
        "property_type": "title",
        "config": {"options": ["A"]},
    },
    "create_relation": {
        "database_id": "db-1",
        "name": "Project",
        "target_database_id": "db-2",
        "synced_property_name": "Backlink",
    },
    "create_rollup": {
        "database_id": "db-1",
        "name": "Total",
        "relation_property_id": "rel-1",
        "rollup_property_id": "prop-1",
        "function": "sum",
    },
    "create_formula": {"database_id": "db-1", "name": "Score", "expression": "1+1"},
    "create_linked_view": {
        "source_database_id": "db-1",
        "parent_page_id": "page-1",
        "view_type": "board",
    },
    "add_filter": {"database_id": "db-1", "view_id": "view-1", "filter_spec": _FILTER},
    "add_sort": {"database_id": "db-1", "view_id": "view-1", "sort_spec": _SORT},
    "create_calendar_view": {"database_id": "db-1", "name": "Calendar", "date_property": "Date"},
    "create_table_view": {"database_id": "db-1", "name": "Table"},
    "create_board_view": {"database_id": "db-1", "name": "Board", "group_by_property": "Status"},
    "set_view_title_visibility": {
        "database_id": "Db-ABC",
        "view_id": "view-specific",
        "visible": False,
    },
    "add_child_page": {"parent_page_id": "page-1", "title": "Child"},
    "publish_page": {"page_id": "page-1"},
    "set_duplicate_as_template": {"page_id": "page-1", "enabled": False},
    "set_search_indexing": {"page_id": "page-1", "enabled": False},
    "get_public_url": {"page_id": "page-specific"},
    "unpublish_page": {"page_id": "page-1"},
    "inspect_page": {"page_id": "page-1"},
    "inspect_database": {"database_id": "db-1"},
    "verify_stranger_access": {"public_url": "https://www.notion.so/page-1"},
}

# Channels are fixed here so a source-map swap fails these cases.
_EXPECTED_API = (
    "add_callout_block",
    "add_child_page",
    "add_filter",
    "add_property",
    "add_sort",
    "add_text_block",
    "connection_status",
    "create_database",
    "create_page",
    "create_relation",
    "create_rollup",
    "inspect_database",
    "inspect_page",
    "move_page",
    "rename_page",
    "set_cover",
    "set_icon",
    "workspace_discovery",
)
_EXPECTED_BROWSER = (
    "create_board_view",
    "create_calendar_view",
    "create_formula",
    "create_linked_view",
    "create_table_view",
    "duplicate_page",
    "publish_page",
    "set_duplicate_as_template",
    "set_search_indexing",
    "set_view_title_visibility",
    "unpublish_page",
    "verify_stranger_access",
)
_EXPECTED_COMBINED = ("get_public_url",)
_DELEGATED = _EXPECTED_API + _EXPECTED_BROWSER


class _FakeAdapter:
    """Records calls and returns a canned result or raises a canned error."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.results: dict[str, object] = {}
        self.errors: dict[str, BaseException] = {}
        self.unsupported: set[str] = set()

    def reports_unsupported(self, operation: str) -> bool:
        return operation in self.unsupported

    def __getattr__(self, name: str) -> object:
        if name.startswith("_"):
            raise AttributeError(name)

        async def _call(*args: object, **kwargs: object) -> object:
            self.calls.append((name, args, dict(kwargs)))
            if name in self.errors:
                raise self.errors[name]
            if name not in self.results:
                raise AssertionError(f"unexpected call {name}")
            return self.results[name]

        return _call


def _adapters() -> tuple[_FakeAdapter, _FakeAdapter, CombinedNotionAdapter]:
    api = _FakeAdapter()
    browser = _FakeAdapter()
    combined = CombinedNotionAdapter(cast(NotionAdapter, api), cast(NotionAdapter, browser))
    return api, browser, combined


def _seed(adapter: _FakeAdapter, operation: str, result: object) -> None:
    adapter.results[operation] = result


async def _invoke(combined: CombinedNotionAdapter, operation: str) -> object:
    return await getattr(combined, operation)(**_EXPECTED_CALLS[operation])


def test_operation_channels_partition_the_adapter_interface() -> None:
    """Every NotionAdapter operation has exactly one preferred channel."""
    assert API_OPERATIONS.isdisjoint(BROWSER_OPERATIONS)
    assert COMBINED_OPERATIONS.isdisjoint(API_OPERATIONS | BROWSER_OPERATIONS)
    assert set(NotionAdapter.__abstractmethods__) == (
        API_OPERATIONS | BROWSER_OPERATIONS | COMBINED_OPERATIONS
    )
    assert set(_EXPECTED_API) == API_OPERATIONS
    assert set(_EXPECTED_BROWSER) == BROWSER_OPERATIONS
    assert set(_EXPECTED_COMBINED) == COMBINED_OPERATIONS


@pytest.mark.parametrize("operation", _EXPECTED_API)
async def test_operation_uses_api_adapter(operation: str) -> None:
    """DIRECT_API operations call the API delegate only."""
    api, browser, combined = _adapters()
    api_result = object()
    _seed(api, operation, api_result)
    _seed(browser, operation, object())

    result = await _invoke(combined, operation)

    assert result is api_result
    assert [call[0] for call in api.calls] == [operation]
    assert browser.calls == []


@pytest.mark.parametrize("operation", _EXPECTED_BROWSER)
async def test_operation_uses_browser_adapter(operation: str) -> None:
    """BROWSER operations call the browser delegate only."""
    api, browser, combined = _adapters()
    browser_result = object()
    _seed(api, operation, object())
    _seed(browser, operation, browser_result)

    result = await _invoke(combined, operation)

    assert result is browser_result
    assert [call[0] for call in browser.calls] == [operation]
    assert api.calls == []


@pytest.mark.parametrize("operation", _DELEGATED)
async def test_operation_forwards_every_argument(operation: str) -> None:
    """Each delegated operation passes its arguments through unchanged."""
    api, browser, combined = _adapters()
    preferred = api if operation in _EXPECTED_API else browser
    _seed(preferred, operation, object())

    await _invoke(combined, operation)

    assert preferred.calls == [(operation, (), _EXPECTED_CALLS[operation])]


class _WriteFailure(Exception):
    """A custom write failure. It is not an unsupported signal."""


@pytest.mark.parametrize(
    "error_type",
    [
        RuntimeError,
        ValueError,
        ConnectionError,
        KeyError,
        AttributeError,
        NotImplementedError,
        _WriteFailure,
    ],
)
async def test_write_error_is_not_retried_on_the_other_adapter(
    error_type: type[Exception],
) -> None:
    """A write that raises is not run again on the other adapter."""
    api, browser, combined = _adapters()
    error = error_type("create_page failed")
    api.errors["create_page"] = error
    _seed(browser, "create_page", _PAGE)

    with pytest.raises(error_type) as caught:
        await _invoke(combined, "create_page")

    assert caught.value is error
    assert len(api.calls) == 1
    assert browser.calls == []


async def test_type_error_propagates_unchanged() -> None:
    """A TypeError from the preferred adapter is not swallowed or retried."""
    api, browser, combined = _adapters()
    error = TypeError("bad page id")
    api.errors["inspect_page"] = error
    _seed(browser, "inspect_page", _PAGE)

    with pytest.raises(TypeError) as caught:
        await _invoke(combined, "inspect_page")

    assert caught.value is error
    assert browser.calls == []


async def test_auth_error_propagates_unchanged() -> None:
    """An authentication failure from the preferred adapter is not retried."""
    api, browser, combined = _adapters()
    error = PermissionError("401 unauthorized")
    api.errors["inspect_page"] = error
    _seed(browser, "inspect_page", _PAGE)

    with pytest.raises(PermissionError) as caught:
        await _invoke(combined, "inspect_page")

    assert caught.value is error
    assert browser.calls == []


async def test_operation_unsupported_error_triggers_fallback() -> None:
    """OperationUnsupportedError is the unsupported signal and falls back once."""
    api, browser, combined = _adapters()
    api.errors["create_page"] = OperationUnsupportedError("api refuses create_page")
    _seed(browser, "create_page", _PAGE)

    result = await _invoke(combined, "create_page")

    assert result is _PAGE
    assert len(api.calls) == 1
    assert browser.calls == [("create_page", (), _EXPECTED_CALLS["create_page"])]


async def test_browser_preferred_write_error_is_not_retried() -> None:
    """A browser-preferred write that raises is not run on the API adapter."""
    api, browser, combined = _adapters()
    error = RuntimeError("duplicate_page failed")
    browser.errors["duplicate_page"] = error
    _seed(api, "duplicate_page", _PAGE)

    with pytest.raises(RuntimeError) as caught:
        await _invoke(combined, "duplicate_page")

    assert caught.value is error
    assert len(browser.calls) == 1
    assert api.calls == []


@pytest.mark.parametrize(
    ("operation", "preferred_channel"),
    [("create_page", "api"), ("publish_page", "browser")],
)
async def test_fallback_when_preferred_reports_unsupported(
    operation: str, preferred_channel: str
) -> None:
    """reports_unsupported skips the preferred call and forwards every argument."""
    api, browser, combined = _adapters()
    fallback_result = object()
    preferred = api if preferred_channel == "api" else browser
    fallback = browser if preferred_channel == "api" else api
    preferred.unsupported.add(operation)
    _seed(preferred, operation, object())
    _seed(fallback, operation, fallback_result)

    result = await _invoke(combined, operation)

    assert result is fallback_result
    assert preferred.calls == []
    assert fallback.calls == [(operation, (), _EXPECTED_CALLS[operation])]


@pytest.mark.parametrize(
    "signal",
    ["operation_unsupported", "reports_unsupported"],
)
async def test_unsupported_fallback_error_is_chained_from_the_first_error(signal: str) -> None:
    """When the fallback also fails, its error's __cause__ is the first refusal."""
    api, browser, combined = _adapters()
    browser.errors["create_page"] = RuntimeError("browser down")
    first: Exception | None = None
    if signal == "operation_unsupported":
        first = OperationUnsupportedError("api refuses create_page")
        api.errors["create_page"] = first
    else:
        api.unsupported.add("create_page")

    with pytest.raises(RuntimeError, match="browser down") as caught:
        await _invoke(combined, "create_page")

    cause = caught.value.__cause__
    assert cause is not None
    if signal == "operation_unsupported":
        assert cause is first
    else:
        assert isinstance(cause, OperationUnsupportedError)


async def test_set_view_title_visibility_returns_delegate_view() -> None:
    """The browser delegate's NotionView is returned unchanged."""
    _api, browser, combined = _adapters()
    _seed(browser, "set_view_title_visibility", _VIEW)

    result = await _invoke(combined, "set_view_title_visibility")

    assert result is _VIEW


async def test_get_public_url_returns_api_url_only_when_stranger_access_succeeds() -> None:
    """COMBINED: API supplies the URL, browser verifies it, both arguments pass through."""
    api, browser, combined = _adapters()
    _seed(api, "get_public_url", _PUBLIC_URL)
    _seed(browser, "verify_stranger_access", True)

    result = await combined.get_public_url("page-specific")

    assert result == _PUBLIC_URL
    assert api.calls == [("get_public_url", (), {"page_id": "page-specific"})]
    assert browser.calls == [("verify_stranger_access", (), {"public_url": _PUBLIC_URL})]


async def test_get_public_url_skips_browser_when_unpublished() -> None:
    """None from the API means unpublished, so stranger access is not checked."""
    api, browser, combined = _adapters()
    _seed(api, "get_public_url", None)

    result = await combined.get_public_url("page-specific")

    assert result is None
    assert api.calls == [("get_public_url", (), {"page_id": "page-specific"})]
    assert browser.calls == []


async def test_get_public_url_returns_none_when_stranger_access_fails() -> None:
    """A URL the stranger check rejects is not returned."""
    api, browser, combined = _adapters()
    _seed(api, "get_public_url", _PUBLIC_URL)
    _seed(browser, "verify_stranger_access", False)

    result = await combined.get_public_url("page-specific")

    assert result is None
    assert browser.calls == [("verify_stranger_access", (), {"public_url": _PUBLIC_URL})]


async def test_get_public_url_does_not_hide_stranger_access_errors() -> None:
    """A stranger-check error is not turned into None."""
    api, browser, combined = _adapters()
    error = RuntimeError("stranger check failed")
    _seed(api, "get_public_url", _PUBLIC_URL)
    browser.errors["verify_stranger_access"] = error

    with pytest.raises(RuntimeError) as caught:
        await combined.get_public_url("page-specific")

    assert caught.value is error


async def test_get_public_url_rejects_a_non_bool_stranger_check() -> None:
    """verify_stranger_access must return bool."""
    api, browser, combined = _adapters()
    _seed(api, "get_public_url", _PUBLIC_URL)
    _seed(browser, "verify_stranger_access", "yes")

    with pytest.raises(TypeError, match="bool"):
        await combined.get_public_url("page-specific")


async def test_get_public_url_does_not_hide_api_errors() -> None:
    """An API error is not turned into a browser get_public_url call."""
    api, browser, combined = _adapters()
    error = TimeoutError("api timed out")
    api.errors["get_public_url"] = error
    _seed(browser, "get_public_url", _PUBLIC_URL)

    with pytest.raises(TimeoutError) as caught:
        await combined.get_public_url("page-specific")

    assert caught.value is error
    assert browser.calls == []
