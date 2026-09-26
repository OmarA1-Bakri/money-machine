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
    CombinedNotionAdapter,
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


class _FakeAdapter:
    """Records calls and returns a canned result or raises a canned error."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.results: dict[str, object] = {}
        self.errors: dict[str, Exception] = {}
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


async def _call(adapter: CombinedNotionAdapter, operation: str) -> object:
    if operation == "connection_status":
        return await adapter.connection_status()
    if operation == "workspace_discovery":
        return await adapter.workspace_discovery()
    if operation == "create_page":
        return await adapter.create_page("Title", parent_id="parent", icon="📄")
    if operation == "duplicate_page":
        return await adapter.duplicate_page("page_1")
    if operation == "rename_page":
        return await adapter.rename_page("page_1", "Renamed")
    if operation == "move_page":
        return await adapter.move_page("page_1", "parent_2", "page_id")
    if operation == "set_icon":
        return await adapter.set_icon("page_1", "🔥")
    if operation == "set_cover":
        return await adapter.set_cover("page_1", "https://example.com/cover.png")
    if operation == "add_text_block":
        return await adapter.add_text_block("page_1", "hello")
    if operation == "add_callout_block":
        return await adapter.add_callout_block("page_1", "note", "💡")
    if operation == "create_database":
        return await adapter.create_database("Tasks")
    if operation == "add_property":
        return await adapter.add_property("db_1", "Name", "title", {})
    if operation == "create_relation":
        return await adapter.create_relation("db_1", "Project", "db_2")
    if operation == "create_rollup":
        return await adapter.create_rollup("db_1", "Total", "rel", "prop", "sum")
    if operation == "create_formula":
        return await adapter.create_formula("db_1", "Score", "1+1")
    if operation == "create_linked_view":
        return await adapter.create_linked_view("db_1", "page_1", "table")
    if operation == "add_filter":
        return await adapter.add_filter("db_1", "view_1", NotionFilter("Name", "equals", "A"))
    if operation == "add_sort":
        return await adapter.add_sort("db_1", "view_1", NotionSort("Name", "ascending"))
    if operation == "create_calendar_view":
        return await adapter.create_calendar_view("db_1", "Calendar", "Date")
    if operation == "create_table_view":
        return await adapter.create_table_view("db_1", "Table")
    if operation == "create_board_view":
        return await adapter.create_board_view("db_1", "Board", "Status")
    if operation == "set_view_title_visibility":
        return await adapter.set_view_title_visibility("db_1", "view_1", True)
    if operation == "add_child_page":
        return await adapter.add_child_page("page_1", "Child")
    if operation == "publish_page":
        return await adapter.publish_page("page_1")
    if operation == "set_duplicate_as_template":
        return await adapter.set_duplicate_as_template("page_1", True)
    if operation == "set_search_indexing":
        return await adapter.set_search_indexing("page_1", False)
    if operation == "get_public_url":
        return await adapter.get_public_url("page_1")
    if operation == "unpublish_page":
        return await adapter.unpublish_page("page_1")
    if operation == "inspect_page":
        return await adapter.inspect_page("page_1")
    if operation == "inspect_database":
        return await adapter.inspect_database("db_1")
    if operation == "verify_stranger_access":
        return await adapter.verify_stranger_access("https://www.notion.so/page_1")
    raise AssertionError(operation)


# Expected channels are fixed here so a source-map swap fails these cases.
# They are the method column in docs/architecture/PLATFORM_COMPATIBILITY.md.
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
    "get_public_url",
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


def test_operation_channels_partition_the_adapter_interface() -> None:
    """Every NotionAdapter operation has exactly one preferred channel."""
    assert API_OPERATIONS.isdisjoint(BROWSER_OPERATIONS)
    assert set(NotionAdapter.__abstractmethods__) == API_OPERATIONS | BROWSER_OPERATIONS
    assert set(_EXPECTED_API) == API_OPERATIONS
    assert set(_EXPECTED_BROWSER) == BROWSER_OPERATIONS


@pytest.mark.parametrize("operation", _EXPECTED_API)
async def test_operation_uses_api_adapter(operation: str) -> None:
    """DIRECT_API and COMBINED operations call the API delegate only."""
    api, browser, combined = _adapters()
    api_result = object()
    _seed(api, operation, api_result)
    _seed(browser, operation, object())

    result = await _call(combined, operation)

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

    result = await _call(combined, operation)

    assert result is browser_result
    assert [call[0] for call in browser.calls] == [operation]
    assert api.calls == []


@pytest.mark.parametrize(
    ("operation", "preferred_channel"),
    [("create_page", "api"), ("duplicate_page", "browser")],
)
async def test_fallback_when_preferred_raises(operation: str, preferred_channel: str) -> None:
    """A preferred delegate that raises is skipped and the other delegate's result is returned."""
    api, browser, combined = _adapters()
    fallback_result = object()
    preferred = api if preferred_channel == "api" else browser
    fallback = browser if preferred_channel == "api" else api
    preferred.errors[operation] = RuntimeError("preferred failed")
    _seed(fallback, operation, fallback_result)

    result = await _call(combined, operation)

    assert result is fallback_result
    assert [call[0] for call in preferred.calls] == [operation]
    assert [call[0] for call in fallback.calls] == [operation]


async def test_fallback_when_preferred_reports_not_implemented() -> None:
    """NotImplementedError from the preferred delegate is an unsupported report and falls back."""
    api, browser, combined = _adapters()
    browser_page = NotionPage(id="from_browser", title="browser")
    api.errors["create_page"] = NotImplementedError("requires BROWSER method")
    _seed(browser, "create_page", browser_page)

    result = await combined.create_page("Title")

    assert result is browser_page


@pytest.mark.parametrize(
    ("operation", "preferred_channel"),
    [("create_page", "api"), ("publish_page", "browser")],
)
async def test_fallback_when_preferred_reports_unsupported(
    operation: str, preferred_channel: str
) -> None:
    """reports_unsupported skips the preferred call and returns the other delegate's result."""
    api, browser, combined = _adapters()
    fallback_result = object()
    preferred = api if preferred_channel == "api" else browser
    fallback = browser if preferred_channel == "api" else api
    preferred.unsupported.add(operation)
    _seed(preferred, operation, object())
    _seed(fallback, operation, fallback_result)

    result = await _call(combined, operation)

    assert result is fallback_result
    assert preferred.calls == []
    assert [call[0] for call in fallback.calls] == [operation]


async def test_fallback_error_propagates() -> None:
    """When the fallback delegate also raises, that exception propagates."""
    api, browser, combined = _adapters()
    api.errors["create_page"] = RuntimeError("api down")
    browser.errors["create_page"] = RuntimeError("browser down")

    with pytest.raises(RuntimeError, match="browser down"):
        await combined.create_page("Title")


async def test_set_view_title_visibility_passes_arguments_and_returns_delegate_view() -> None:
    """database_id, view_id, and visible are passed through; the delegate's view is returned."""
    _api, browser, combined = _adapters()
    _seed(browser, "set_view_title_visibility", _VIEW)

    result = await combined.set_view_title_visibility(
        "Db-ABC",
        "view-specific",
        False,
    )

    assert result is _VIEW
    assert browser.calls == [
        (
            "set_view_title_visibility",
            (),
            {"database_id": "Db-ABC", "view_id": "view-specific", "visible": False},
        )
    ]


async def test_set_view_title_visibility_falls_back_to_api_with_same_arguments() -> None:
    """A browser failure still forwards database_id, view_id, and visible to the API delegate."""
    api, browser, combined = _adapters()
    browser.errors["set_view_title_visibility"] = RuntimeError("ui missing")
    _seed(api, "set_view_title_visibility", _VIEW)

    result = await combined.set_view_title_visibility("db_1", "view_9", True)

    assert result is _VIEW
    assert api.calls == [
        (
            "set_view_title_visibility",
            (),
            {"database_id": "db_1", "view_id": "view_9", "visible": True},
        )
    ]
