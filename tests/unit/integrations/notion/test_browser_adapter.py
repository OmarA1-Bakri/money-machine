"""Unit tests for BrowserNotionAdapter — mocked browser automation.

Tests BROWSER operations without real Playwright or live Notion UI.
All browser interactions are mocked via FakeBrowserSession.
"""

import re
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

from money_machine.integrations.notion.adapter import NotionAdapter
from money_machine.integrations.notion.browser_adapter import BrowserNotionAdapter
from money_machine.integrations.notion.domain import (
    NotionFilter,
    NotionFormula,
    NotionLinkedView,
    NotionPage,
    NotionSort,
    NotionView,
)


def _parse_platform_compatibility() -> tuple[set[str], set[str]]:
    """Parse PLATFORM_COMPATIBILITY.md to extract DIRECT_API and COMBINED operations.

    Returns:
        Tuple of (direct_api_ops, combined_ops) operation name sets.
    """
    compat_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "docs"
        / "architecture"
        / "PLATFORM_COMPATIBILITY.md"
    )
    if not compat_path.exists():
        raise FileNotFoundError(f"PLATFORM_COMPATIBILITY.md not found at {compat_path}")

    direct_api_ops = set()
    combined_ops = set()

    with open(compat_path) as f:
        for line in f:
            # Match table rows: | `operation_name` | METHOD | ...
            match = re.match(r"^\|\s*`(\w+)`\s*\|\s*(\w+)\s*\|", line)
            if match:
                op_name = match.group(1)
                method = match.group(2)
                if method == "DIRECT_API":
                    direct_api_ops.add(op_name)
                elif method == "COMBINED":
                    combined_ops.add(op_name)

    return direct_api_ops, combined_ops


# Parse capability matrix to derive expected operation sets
EXPECTED_DIRECT_API_OPS, EXPECTED_COMBINED_OPS = _parse_platform_compatibility()


class FakeBrowserSession:
    """Fake browser session for testing without Playwright.

    Simulates browser interactions with synthetic responses.
    Tests inject this instead of real Playwright to avoid
    browser launches and actual UI automation.
    """

    def __init__(self) -> None:
        self.current_url = "https://www.notion.so/workspace"
        self.navigated_to: list[str] = []
        self.clicks: list[str] = []
        self.fills: dict[str, str] = {}
        self._element_visibility: dict[str, bool] = {}
        self._element_attributes: dict[tuple[str, str], str] = {}

    async def navigate(self, url: str) -> None:
        """Record navigation."""
        self.current_url = url
        self.navigated_to.append(url)

    async def click(self, selector: str) -> None:
        """Record click."""
        self.clicks.append(selector)

    async def fill(self, selector: str, value: str) -> None:
        """Record fill."""
        self.fills[selector] = value

    async def get_attribute(self, selector: str, attribute: str) -> str | None:
        """Return fake attribute value."""
        return self._element_attributes.get((selector, attribute))

    async def is_visible(self, selector: str) -> bool:
        """Return fake visibility state."""
        return self._element_visibility.get(selector, False)

    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> None:
        """No-op for fake session."""
        pass

    async def get_current_url(self) -> str:
        """Return current URL."""
        return self.current_url

    def set_element_visible(self, selector: str, visible: bool) -> None:
        """Configure element visibility for test."""
        self._element_visibility[selector] = visible

    def set_attribute(self, selector: str, attribute: str, value: str) -> None:
        """Configure element attribute for test."""
        self._element_attributes[(selector, attribute)] = value


@pytest.fixture
def fake_browser():
    """Create fake browser session."""
    session = FakeBrowserSession()
    # Set up deterministic IDs for property/view creation tests
    session.set_attribute('[data-testid="property-saved"]', "data-property-id", "prop_abc123")
    session.set_attribute('[data-testid="linked-view-created"]', "data-view-id", "view_def456")
    return session


@pytest.fixture
def fake_anon_browser():
    """Create fake anonymous browser session for verify_stranger_access tests."""
    return FakeBrowserSession()


@pytest.fixture
def browser_adapter(fake_browser, fake_anon_browser):
    """Create BrowserNotionAdapter with fake browser and anon session factory."""
    return BrowserNotionAdapter(
        browser_session=fake_browser,
        anon_session_factory=lambda: fake_anon_browser,  # type: ignore[reportUnknownLambdaType]
    )


# Capability matrix refusal: DIRECT_API + COMBINED operations
# Derived programmatically from docs/architecture/PLATFORM_COMPATIBILITY.md
# via _parse_platform_compatibility()
DIRECT_API_OPERATIONS: list[tuple[str, Callable[[NotionAdapter], Awaitable[object]]]] = [
    ("connection_status", lambda adapter: adapter.connection_status()),
    ("workspace_discovery", lambda adapter: adapter.workspace_discovery()),
    ("create_page", lambda adapter: adapter.create_page("Test")),
    ("rename_page", lambda adapter: adapter.rename_page("page_123", "New Title")),
    ("move_page", lambda adapter: adapter.move_page("page_123", "page_parent")),
    ("set_icon", lambda adapter: adapter.set_icon("page_123", "📄")),
    ("set_cover", lambda adapter: adapter.set_cover("page_123", "https://example.com/cover.jpg")),
    ("add_text_block", lambda adapter: adapter.add_text_block("page_123", "Text content")),
    ("add_callout_block", lambda adapter: adapter.add_callout_block("page_123", "Callout", "info")),
    ("create_database", lambda adapter: adapter.create_database("DB", "page_parent")),
    ("add_property", lambda adapter: adapter.add_property("db_123", "Prop", "text", {})),  # type: ignore[reportUnknownLambdaType]
    ("create_relation", lambda adapter: adapter.create_relation("db_123", "Rel", "db_target")),
    (
        "create_rollup",
        lambda adapter: adapter.create_rollup("db_123", "Roll", "rel_prop", "rollup_prop", "count"),
    ),  # type: ignore[reportUnknownLambdaType]
    (
        "add_filter",
        lambda adapter: adapter.add_filter(
            "db_123", "view_123", NotionFilter(property="prop", condition="equals", value="value")
        ),
    ),
    (
        "add_sort",
        lambda adapter: adapter.add_sort(
            "db_123", "view_123", NotionSort(property="prop", direction="ascending")
        ),
    ),
    ("add_child_page", lambda adapter: adapter.add_child_page("page_parent", "Child")),
    ("inspect_page", lambda adapter: adapter.inspect_page("page_123")),
    ("inspect_database", lambda adapter: adapter.inspect_database("db_123")),
]

COMBINED_OPERATIONS: list[tuple[str, Callable[[NotionAdapter], Awaitable[object]]]] = [
    ("get_public_url", lambda adapter: adapter.get_public_url("page_123")),
]

# Verify operation lists match parsed capability matrix (drift detection)
_test_direct_api_names = {name for name, _ in DIRECT_API_OPERATIONS}
_test_combined_names = {name for name, _ in COMBINED_OPERATIONS}
assert _test_direct_api_names == EXPECTED_DIRECT_API_OPS, (
    f"DIRECT_API test operations drift from PLATFORM_COMPATIBILITY.md. "
    f"Expected: {EXPECTED_DIRECT_API_OPS}, got: {_test_direct_api_names}, "
    f"missing: {EXPECTED_DIRECT_API_OPS - _test_direct_api_names}, "
    f"extra: {_test_direct_api_names - EXPECTED_DIRECT_API_OPS}"
)
assert _test_combined_names == EXPECTED_COMBINED_OPS, (
    f"COMBINED test operations drift from PLATFORM_COMPATIBILITY.md. "
    f"Expected: {EXPECTED_COMBINED_OPS}, got: {_test_combined_names}"
)

ALL_NON_BROWSER_OPERATIONS = DIRECT_API_OPERATIONS + COMBINED_OPERATIONS


@pytest.mark.parametrize("operation_name,call_fn", ALL_NON_BROWSER_OPERATIONS)
@pytest.mark.asyncio
async def test_non_browser_operations_raise_not_implemented(
    browser_adapter, operation_name, call_fn
):
    """BrowserAdapter raises NotImplementedError for all DIRECT_API and COMBINED operations.

    Parametrized over 18 DIRECT_API + 1 COMBINED operations from capability matrix.
    BrowserAdapter only implements BROWSER-tagged operations.
    """
    with pytest.raises(NotImplementedError, match=r"(API method|COMBINED)"):
        await call_fn(browser_adapter)


# Test: duplicate_page
@pytest.mark.asyncio
async def test_duplicate_page(browser_adapter, fake_browser):
    """duplicate_page navigates to page, clicks duplicate, reads new ID and title."""

    # Simulate the new page URL after duplication
    async def navigate_mock(url: str) -> None:
        fake_browser.navigated_to.append(url)
        # After navigating and duplicating, set the new URL
        fake_browser.current_url = "https://www.notion.so/page_new123"

    fake_browser.navigate = navigate_mock

    # Set up the page title attribute
    fake_browser.set_attribute('[data-testid="page-title"]', "textContent", "Copy of Original Page")

    result = await browser_adapter.duplicate_page("page_orig456")

    # Verify browser interactions
    assert "https://www.notion.so/page_orig456" in fake_browser.navigated_to
    assert '[data-testid="page-menu-button"]' in fake_browser.clicks
    assert '[data-testid="duplicate-page-action"]' in fake_browser.clicks

    # Verify result
    assert isinstance(result, NotionPage)
    assert result.id == "page_new123"
    assert result.id != "page_orig456"  # New ID must differ from source
    assert result.title == "Copy of Original Page"


@pytest.mark.asyncio
async def test_duplicate_page_reads_real_id(browser_adapter, fake_browser):
    """duplicate_page reads real ID from URL after duplication."""

    async def navigate_mock(url: str) -> None:
        fake_browser.navigated_to.append(url)
        fake_browser.current_url = "https://www.notion.so/page_newid789"

    fake_browser.navigate = navigate_mock
    fake_browser.set_attribute('[data-testid="page-title"]', "textContent", "Duplicated Page")

    result = await browser_adapter.duplicate_page("page_source")

    assert result.id == "page_newid789"
    assert result.id != "page_source"


@pytest.mark.asyncio
async def test_duplicate_page_fails_if_title_cannot_be_read(browser_adapter, fake_browser):
    """duplicate_page raises RuntimeError if page title cannot be read."""

    async def navigate_mock(url: str) -> None:
        fake_browser.navigated_to.append(url)
        fake_browser.current_url = "https://www.notion.so/page_newid999"

    fake_browser.navigate = navigate_mock
    # Simulate title attribute not being available
    fake_browser.set_attribute('[data-testid="page-title"]', "textContent", None)

    with pytest.raises(RuntimeError, match="Failed to read page title after duplicating"):
        await browser_adapter.duplicate_page("page_source")


@pytest.mark.asyncio
async def test_duplicate_page_fails_if_id_matches_source(browser_adapter, fake_browser):
    """duplicate_page raises if new ID equals source ID (duplication failed)."""

    # Simulate duplication failure: URL doesn't change
    async def navigate_mock(url: str) -> None:
        fake_browser.navigated_to.append(url)
        # URL stays the same (duplication failed)
        fake_browser.current_url = "https://www.notion.so/page_same123"

    fake_browser.navigate = navigate_mock

    with pytest.raises(RuntimeError, match="Duplicate page ID matches source ID"):
        await browser_adapter.duplicate_page("page_same123")


# Test: create_formula
@pytest.mark.asyncio
async def test_create_formula(browser_adapter, fake_browser):
    """create_formula navigates to database, uses formula editor, and reads property ID."""
    result = await browser_adapter.create_formula(
        "db_123", "Total", "prop('Quantity') * prop('Price')"
    )

    # Verify browser interactions
    assert "https://www.notion.so/db_123" in fake_browser.navigated_to
    assert '[data-testid="add-property-button"]' in fake_browser.clicks
    assert '[data-testid="property-type-formula"]' in fake_browser.clicks
    assert fake_browser.fills.get('[data-testid="property-name-input"]') == "Total"
    formula_input = fake_browser.fills.get('[data-testid="formula-expression-input"]', "")
    assert "Quantity" in formula_input

    # Verify result: ID read from fake browser attribute (prop_abc123)
    assert isinstance(result, NotionFormula)
    assert result.id == "prop_abc123"
    assert result.name == "Total"
    assert "Quantity" in result.expression


@pytest.mark.asyncio
async def test_create_formula_fails_if_id_cannot_be_read(fake_browser, fake_anon_browser):
    """create_formula raises if property ID cannot be read."""
    # Create adapter with browser that won't return property ID
    fake_browser_no_id = FakeBrowserSession()
    adapter = BrowserNotionAdapter(
        browser_session=fake_browser_no_id,
        anon_session_factory=lambda: fake_anon_browser,  # type: ignore[reportUnknownLambdaType]
    )

    with pytest.raises(RuntimeError, match="Failed to read property ID"):
        await adapter.create_formula("db_123", "BadFormula", "1 + 1")


# Test: create_linked_view
@pytest.mark.asyncio
async def test_create_linked_view(browser_adapter, fake_browser):
    """create_linked_view embeds linked database in page and reads view ID."""
    result = await browser_adapter.create_linked_view(
        source_database_id="db_source", parent_page_id="page_parent", view_type="board"
    )

    # Verify browser interactions
    assert "https://www.notion.so/page_parent" in fake_browser.navigated_to
    assert '[data-testid="linked-database-option"]' in fake_browser.clicks
    db_search_fill = fake_browser.fills.get('[data-testid="database-search-input"]')
    assert db_search_fill == "db_source"

    # Verify result: ID read from fake browser attribute (view_def456)
    assert isinstance(result, NotionLinkedView)
    assert result.id == "view_def456"
    assert result.source_database_id == "db_source"
    assert result.parent_page_id == "page_parent"
    assert result.view_type == "board"


@pytest.mark.asyncio
async def test_create_linked_view_fails_if_id_cannot_be_read(fake_browser, fake_anon_browser):
    """create_linked_view raises if view ID cannot be read."""
    fake_browser_no_id = FakeBrowserSession()
    adapter = BrowserNotionAdapter(
        browser_session=fake_browser_no_id,
        anon_session_factory=lambda: fake_anon_browser,  # type: ignore[reportUnknownLambdaType]
    )

    with pytest.raises(RuntimeError, match="Failed to read view ID"):
        await adapter.create_linked_view("db_source", "page_parent")


# Test: create_calendar_view
@pytest.mark.asyncio
async def test_create_calendar_view(browser_adapter, fake_browser):
    """create_calendar_view creates calendar view and reads view ID from URL."""

    # Simulate URL change after view creation
    async def original_navigate(url: str) -> None:
        fake_browser.navigated_to.append(url)
        fake_browser.current_url = url

    fake_browser.navigate = original_navigate

    # After creating view, URL includes ?v=view_id
    async def click_with_url_update(selector: str) -> None:
        fake_browser.clicks.append(selector)
        if selector == '[data-testid="create-view-button"]':
            fake_browser.current_url = "https://www.notion.so/db_123?v=view_cal456"

    fake_browser.click = click_with_url_update

    result = await browser_adapter.create_calendar_view("db_123", "Event Calendar", "due_date")

    # Verify browser interactions
    assert "https://www.notion.so/db_123" in fake_browser.navigated_to
    assert '[data-testid="view-type-calendar"]' in fake_browser.clicks
    assert fake_browser.fills.get('[data-testid="view-name-input"]') == "Event Calendar"

    # Verify result: ID read from URL
    assert isinstance(result, NotionView)
    assert result.id == "view_cal456"
    assert result.name == "Event Calendar"
    assert result.type == "calendar"
    assert result.database_id == "db_123"


@pytest.mark.asyncio
async def test_create_calendar_view_fails_if_id_cannot_be_read(fake_browser, fake_anon_browser):
    """create_calendar_view raises if view ID cannot be read from URL."""
    # Browser that doesn't update URL with ?v=
    fake_browser_no_url = FakeBrowserSession()
    adapter = BrowserNotionAdapter(
        browser_session=fake_browser_no_url,
        anon_session_factory=lambda: fake_anon_browser,  # type: ignore[reportUnknownLambdaType]
    )

    with pytest.raises(RuntimeError, match="Failed to read view ID"):
        await adapter.create_calendar_view("db_123", "BadCalendar", "date")


@pytest.mark.asyncio
async def test_create_calendar_view_fails_if_id_unchanged(fake_browser, fake_anon_browser):
    """create_calendar_view raises if view ID unchanged after creation."""

    async def navigate_with_initial_view(url: str) -> None:
        fake_browser.navigated_to.append(url)
        # Start with an existing view
        fake_browser.current_url = "https://www.notion.so/db_123?v=view_existing"

    fake_browser.navigate = navigate_with_initial_view

    async def click_no_change(selector: str) -> None:
        fake_browser.clicks.append(selector)
        # Simulate view ID not changing (create failed or clicked wrong button)
        if selector == '[data-testid="create-view-button"]':
            fake_browser.current_url = "https://www.notion.so/db_123?v=view_existing"

    fake_browser.click = click_no_change

    adapter = BrowserNotionAdapter(
        browser_session=fake_browser,
        anon_session_factory=lambda: fake_anon_browser,  # type: ignore[reportUnknownLambdaType]
    )

    with pytest.raises(RuntimeError, match="View ID unchanged"):
        await adapter.create_calendar_view("db_123", "Calendar", "date")


# Test: create_table_view
@pytest.mark.asyncio
async def test_create_table_view(browser_adapter, fake_browser):
    """create_table_view creates table view and reads view ID from URL."""

    async def original_navigate(url: str) -> None:
        fake_browser.navigated_to.append(url)
        fake_browser.current_url = url

    fake_browser.navigate = original_navigate

    async def click_with_url_update(selector: str) -> None:
        fake_browser.clicks.append(selector)
        if selector == '[data-testid="create-view-button"]':
            fake_browser.current_url = "https://www.notion.so/db_123?v=view_table789"

    fake_browser.click = click_with_url_update

    result = await browser_adapter.create_table_view("db_123", "All Items")

    # Verify browser interactions
    assert "https://www.notion.so/db_123" in fake_browser.navigated_to
    assert '[data-testid="view-type-table"]' in fake_browser.clicks
    assert fake_browser.fills.get('[data-testid="view-name-input"]') == "All Items"

    # Verify result: ID read from URL
    assert isinstance(result, NotionView)
    assert result.id == "view_table789"
    assert result.name == "All Items"
    assert result.type == "table"


@pytest.mark.asyncio
async def test_create_table_view_fails_if_id_cannot_be_read(fake_browser, fake_anon_browser):
    """create_table_view raises if view ID cannot be read from URL."""
    fake_browser_no_url = FakeBrowserSession()
    adapter = BrowserNotionAdapter(
        browser_session=fake_browser_no_url,
        anon_session_factory=lambda: fake_anon_browser,  # type: ignore[reportUnknownLambdaType]
    )

    with pytest.raises(RuntimeError, match="Failed to read view ID"):
        await adapter.create_table_view("db_123", "BadTable")


@pytest.mark.asyncio
async def test_create_table_view_fails_if_id_unchanged(fake_browser, fake_anon_browser):
    """create_table_view raises if view ID unchanged after creation."""

    async def navigate_with_initial_view(url: str) -> None:
        fake_browser.navigated_to.append(url)
        fake_browser.current_url = "https://www.notion.so/db_123?v=view_existing"

    fake_browser.navigate = navigate_with_initial_view

    async def click_no_change(selector: str) -> None:
        fake_browser.clicks.append(selector)
        if selector == '[data-testid="create-view-button"]':
            fake_browser.current_url = "https://www.notion.so/db_123?v=view_existing"

    fake_browser.click = click_no_change

    adapter = BrowserNotionAdapter(
        browser_session=fake_browser,
        anon_session_factory=lambda: fake_anon_browser,  # type: ignore[reportUnknownLambdaType]
    )

    with pytest.raises(RuntimeError, match="View ID unchanged"):
        await adapter.create_table_view("db_123", "Table")


# Test: create_board_view
@pytest.mark.asyncio
async def test_create_board_view(browser_adapter, fake_browser):
    """create_board_view creates kanban board view and reads view ID from URL."""

    async def original_navigate(url: str) -> None:
        fake_browser.navigated_to.append(url)
        fake_browser.current_url = url

    fake_browser.navigate = original_navigate

    async def click_with_url_update(selector: str) -> None:
        fake_browser.clicks.append(selector)
        if selector == '[data-testid="create-view-button"]':
            fake_browser.current_url = "https://www.notion.so/db_123?v=view_board999"

    fake_browser.click = click_with_url_update

    result = await browser_adapter.create_board_view("db_123", "Project Board", "status")

    # Verify browser interactions
    assert "https://www.notion.so/db_123" in fake_browser.navigated_to
    assert '[data-testid="view-type-board"]' in fake_browser.clicks
    assert fake_browser.fills.get('[data-testid="view-name-input"]') == "Project Board"

    # Verify result: ID read from URL
    assert isinstance(result, NotionView)
    assert result.id == "view_board999"
    assert result.name == "Project Board"
    assert result.type == "board"


@pytest.mark.asyncio
async def test_create_board_view_fails_if_id_cannot_be_read(fake_browser, fake_anon_browser):
    """create_board_view raises if view ID cannot be read from URL."""
    fake_browser_no_url = FakeBrowserSession()
    adapter = BrowserNotionAdapter(
        browser_session=fake_browser_no_url,
        anon_session_factory=lambda: fake_anon_browser,  # type: ignore[reportUnknownLambdaType]
    )

    with pytest.raises(RuntimeError, match="Failed to read view ID"):
        await adapter.create_board_view("db_123", "BadBoard", "status")


@pytest.mark.asyncio
async def test_create_board_view_fails_if_id_unchanged(fake_browser, fake_anon_browser):
    """create_board_view raises if view ID unchanged after creation."""

    async def navigate_with_initial_view(url: str) -> None:
        fake_browser.navigated_to.append(url)
        fake_browser.current_url = "https://www.notion.so/db_123?v=view_existing"

    fake_browser.navigate = navigate_with_initial_view

    async def click_no_change(selector: str) -> None:
        fake_browser.clicks.append(selector)
        if selector == '[data-testid="create-view-button"]':
            fake_browser.current_url = "https://www.notion.so/db_123?v=view_existing"

    fake_browser.click = click_no_change

    adapter = BrowserNotionAdapter(
        browser_session=fake_browser,
        anon_session_factory=lambda: fake_anon_browser,  # type: ignore[reportUnknownLambdaType]
    )

    with pytest.raises(RuntimeError, match="View ID unchanged"):
        await adapter.create_board_view("db_123", "Board", "status")


# Test: set_view_title_visibility
@pytest.mark.asyncio
async def test_set_view_title_visibility_show(browser_adapter, fake_browser):
    """set_view_title_visibility shows title when toggling on."""
    # Title currently hidden
    fake_browser.set_element_visible('[data-testid="view-title"]', False)

    result = await browser_adapter.set_view_title_visibility("view_123", visible=True)

    # Verify toggle was clicked (since current state ≠ desired)
    assert '[data-testid="view-title-visibility-toggle"]' in fake_browser.clicks

    # Verify result
    assert isinstance(result, NotionView)
    assert result.title_visible is True


@pytest.mark.asyncio
async def test_set_view_title_visibility_hide(browser_adapter, fake_browser):
    """set_view_title_visibility hides title when toggling off."""
    # Title currently visible
    fake_browser.set_element_visible('[data-testid="view-title"]', True)

    result = await browser_adapter.set_view_title_visibility("view_456", visible=False)

    # Verify toggle was clicked (since current state ≠ desired)
    assert '[data-testid="view-title-visibility-toggle"]' in fake_browser.clicks

    # Verify result
    assert isinstance(result, NotionView)
    assert result.title_visible is False


@pytest.mark.asyncio
async def test_set_view_title_visibility_already_visible(browser_adapter, fake_browser):
    """set_view_title_visibility skips toggle if already visible."""
    # Title already visible
    fake_browser.set_element_visible('[data-testid="view-title"]', True)

    result = await browser_adapter.set_view_title_visibility("view_123", visible=True)

    # Verify toggle was NOT clicked (already in desired state)
    assert '[data-testid="view-title-visibility-toggle"]' not in fake_browser.clicks

    # Verify result
    assert result.title_visible is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_url,expected_match",
    [
        ("https://example.com/page", r"not notion\.so"),
        ("https://www.notion.so", r"no database/page ID"),
        ("https://www.notion.so/", r"no database/page ID"),
        ("https://notion.so.evil.com/abc", r"not notion\.so"),
        ("https://evilnotion.so/abc", r"not notion\.so"),
    ],
)
async def test_set_view_title_visibility_rejects_invalid_urls(
    fake_browser, fake_anon_browser, invalid_url, expected_match
):
    """set_view_title_visibility raises for invalid URLs (non-notion.so, bare domain, malicious)."""

    async def navigate_to_invalid(url: str) -> None:
        fake_browser.navigated_to.append(url)
        fake_browser.current_url = invalid_url

    fake_browser.navigate = navigate_to_invalid
    fake_browser.current_url = invalid_url

    adapter = BrowserNotionAdapter(
        browser_session=fake_browser,
        anon_session_factory=lambda: fake_anon_browser,  # type: ignore[reportUnknownLambdaType]
    )

    with pytest.raises(RuntimeError, match=expected_match):
        await adapter.set_view_title_visibility("view_123", visible=True)


# Test: publish_page
@pytest.mark.asyncio
async def test_publish_page_not_yet_published(browser_adapter, fake_browser):
    """publish_page enables share to web when page is not yet published."""
    # Page not yet published
    fake_browser.set_element_visible('[data-testid="public-url-display"]', False)

    # Configure fake public URL
    fake_browser.set_attribute(
        '[data-testid="public-url-display"]', "value", "https://notion.site/page_123"
    )

    result = await browser_adapter.publish_page("page_123")

    # Verify browser interactions
    assert "https://www.notion.so/page_123" in fake_browser.navigated_to
    assert '[data-testid="share-button"]' in fake_browser.clicks
    # Toggle WAS clicked because page was not published
    assert '[data-testid="share-to-web-toggle"]' in fake_browser.clicks

    # Verify result
    assert isinstance(result, NotionPage)
    assert result.is_published is True
    assert result.public_url == "https://notion.site/page_123"


@pytest.mark.asyncio
async def test_publish_page_already_published(browser_adapter, fake_browser):
    """publish_page skips toggle when page is already published (idempotent)."""
    # Page already published
    fake_browser.set_element_visible('[data-testid="public-url-display"]', True)
    fake_browser.set_attribute(
        '[data-testid="public-url-display"]', "value", "https://notion.site/page_456"
    )

    result = await browser_adapter.publish_page("page_456")

    # Verify toggle was NOT clicked (already published)
    assert '[data-testid="share-to-web-toggle"]' not in fake_browser.clicks

    # Verify result
    assert result.is_published is True
    assert result.public_url == "https://notion.site/page_456"


# Test: unpublish_page
@pytest.mark.asyncio
async def test_unpublish_page_currently_published(browser_adapter, fake_browser):
    """unpublish_page disables share to web when currently published."""
    # Page currently published
    fake_browser.set_element_visible('[data-testid="public-url-display"]', True)

    result = await browser_adapter.unpublish_page("page_123")

    # Verify toggle was clicked
    assert '[data-testid="share-to-web-toggle"]' in fake_browser.clicks

    # Verify result
    assert isinstance(result, NotionPage)
    assert result.is_published is False
    assert result.public_url is None


@pytest.mark.asyncio
async def test_unpublish_page_already_unpublished(browser_adapter, fake_browser):
    """unpublish_page skips toggle if already unpublished."""
    # Page not published
    fake_browser.set_element_visible('[data-testid="public-url-display"]', False)

    result = await browser_adapter.unpublish_page("page_123")

    # Verify toggle was NOT clicked (already unpublished)
    assert '[data-testid="share-to-web-toggle"]' not in fake_browser.clicks

    # Verify result
    assert result.is_published is False


# Test: set_duplicate_as_template
@pytest.mark.asyncio
async def test_set_duplicate_as_template_enable(browser_adapter, fake_browser):
    """set_duplicate_as_template enables template mode."""
    # Currently disabled
    fake_browser.set_element_visible('[data-testid="duplicate-as-template-enabled"]', False)

    result = await browser_adapter.set_duplicate_as_template("page_123", enabled=True)

    # Verify toggle was clicked
    assert '[data-testid="duplicate-as-template-toggle"]' in fake_browser.clicks

    # Verify result
    assert isinstance(result, NotionPage)
    assert result.duplicate_as_template is True


@pytest.mark.asyncio
async def test_set_duplicate_as_template_already_enabled(browser_adapter, fake_browser):
    """set_duplicate_as_template skips toggle if already enabled."""
    # Already enabled
    fake_browser.set_element_visible('[data-testid="duplicate-as-template-enabled"]', True)

    await browser_adapter.set_duplicate_as_template("page_123", enabled=True)

    # Verify toggle was NOT clicked
    assert '[data-testid="duplicate-as-template-toggle"]' not in fake_browser.clicks


# Test: set_search_indexing
@pytest.mark.asyncio
async def test_set_search_indexing_disable(browser_adapter, fake_browser):
    """set_search_indexing disables search engine indexing."""
    # Currently enabled
    fake_browser.set_element_visible('[data-testid="search-indexing-enabled"]', True)

    result = await browser_adapter.set_search_indexing("page_123", enabled=False)

    # Verify toggle was clicked
    assert '[data-testid="search-indexing-toggle"]' in fake_browser.clicks

    # Verify result
    assert isinstance(result, NotionPage)
    assert result.search_indexing is False


@pytest.mark.asyncio
async def test_set_search_indexing_already_disabled(browser_adapter, fake_browser):
    """set_search_indexing skips toggle if already disabled."""
    # Already disabled
    fake_browser.set_element_visible('[data-testid="search-indexing-enabled"]', False)

    await browser_adapter.set_search_indexing("page_123", enabled=False)

    # Verify toggle was NOT clicked
    assert '[data-testid="search-indexing-toggle"]' not in fake_browser.clicks


# Test: verify_stranger_access
@pytest.mark.asyncio
async def test_verify_stranger_access_accessible(browser_adapter, fake_anon_browser):
    """verify_stranger_access returns True when page content loads in anonymous session."""
    # Simulate page content visible in anon session
    fake_anon_browser.set_element_visible('[data-testid="page-content"]', True)

    url = "https://notion.site/page_123"
    result = await browser_adapter.verify_stranger_access(url)

    # Verify navigation happened in anonymous session (not the main browser)
    assert url in fake_anon_browser.navigated_to

    # Verify result
    assert result is True


@pytest.mark.asyncio
async def test_verify_stranger_access_blocked(fake_browser, fake_anon_browser):
    """verify_stranger_access returns False when page content doesn't load (login wall)."""
    adapter = BrowserNotionAdapter(
        browser_session=fake_browser,
        anon_session_factory=lambda: fake_anon_browser,  # type: ignore[reportUnknownLambdaType]
    )

    # Override wait_for_selector to raise TimeoutError
    async def wait_timeout(selector: str, timeout: int = 5000) -> None:
        raise TimeoutError("Timeout waiting for selector")

    fake_anon_browser.wait_for_selector = wait_timeout

    url = "https://notion.site/page_blocked"
    result = await adapter.verify_stranger_access(url)

    # Verify result
    assert result is False


@pytest.mark.asyncio
async def test_verify_stranger_access_uses_separate_session(
    browser_adapter, fake_browser, fake_anon_browser
):
    """verify_stranger_access uses anonymous session, not the logged-in session."""
    fake_anon_browser.set_element_visible('[data-testid="page-content"]', True)

    url = "https://notion.site/page_xyz"
    await browser_adapter.verify_stranger_access(url)

    # Main browser session was NOT used
    assert url not in fake_browser.navigated_to

    # Anonymous session was used
    assert url in fake_anon_browser.navigated_to


@pytest.mark.asyncio
async def test_verify_stranger_access_propagates_unexpected_errors(fake_browser):
    """verify_stranger_access propagates unexpected errors (not TimeoutError)."""

    # Create anon session that raises unexpected error
    class BadSession:
        async def navigate(self, url: str) -> None:
            raise ValueError("Unexpected navigation error")

        async def click(self, selector: str) -> None:
            pass

        async def fill(self, selector: str, value: str) -> None:
            pass

        async def get_attribute(self, selector: str, attribute: str) -> str | None:
            return None

        async def is_visible(self, selector: str) -> bool:
            return False

        async def wait_for_selector(self, selector: str, timeout: int = 5000) -> None:
            pass

        async def get_current_url(self) -> str:
            return "https://example.com"

    adapter = BrowserNotionAdapter(
        browser_session=fake_browser,
        anon_session_factory=lambda: BadSession(),  # type: ignore[reportUnknownLambdaType]
    )

    # Unexpected error should propagate
    with pytest.raises(RuntimeError, match="Failed to navigate"):
        await adapter.verify_stranger_access("https://notion.site/page_bad")


@pytest.mark.asyncio
async def test_verify_stranger_access_requires_anon_session_factory(fake_browser):
    """verify_stranger_access raises if no anonymous session factory provided."""
    # Create adapter without anon session factory
    adapter = BrowserNotionAdapter(browser_session=fake_browser, anon_session_factory=None)

    with pytest.raises(RuntimeError, match="requires an anonymous session factory"):
        await adapter.verify_stranger_access("https://notion.site/page")
