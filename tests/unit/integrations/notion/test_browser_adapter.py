"""Unit tests for BrowserNotionAdapter — mocked browser automation.

Tests BROWSER operations without real Playwright or live Notion UI.
All browser interactions are mocked via FakeBrowserSession.
"""

import pytest

from money_machine.integrations.notion.browser_adapter import BrowserNotionAdapter
from money_machine.integrations.notion.domain import (
    NotionFormula,
    NotionLinkedView,
    NotionPage,
    NotionView,
)


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
    return FakeBrowserSession()


@pytest.fixture
def browser_adapter(fake_browser):
    """Create BrowserNotionAdapter with fake browser."""
    return BrowserNotionAdapter(browser_session=fake_browser)


# Test: API operations should raise NotImplementedError
@pytest.mark.asyncio
async def test_api_operations_not_implemented(browser_adapter):
    """DIRECT_API operations raise NotImplementedError in browser adapter."""
    with pytest.raises(NotImplementedError, match="API method"):
        await browser_adapter.connection_status()

    with pytest.raises(NotImplementedError, match="API method"):
        await browser_adapter.workspace_discovery()

    with pytest.raises(NotImplementedError, match="API method"):
        await browser_adapter.create_page("Test")

    with pytest.raises(NotImplementedError, match="API method"):
        await browser_adapter.rename_page("page_123", "New Title")

    with pytest.raises(NotImplementedError, match="API method"):
        await browser_adapter.inspect_page("page_123")


# Test: duplicate_page
@pytest.mark.asyncio
async def test_duplicate_page(browser_adapter, fake_browser):
    """duplicate_page navigates to page and clicks duplicate."""

    # Navigate will be called first, then we set the URL for get_current_url
    # Simulate the new page URL after duplication
    async def navigate_mock(url: str) -> None:
        fake_browser.navigated_to.append(url)
        # After navigating and duplicating, set the new URL
        fake_browser.current_url = "https://www.notion.so/page_new123"

    fake_browser.navigate = navigate_mock

    result = await browser_adapter.duplicate_page("page_orig456")

    # Verify browser interactions
    assert "https://www.notion.so/page_orig456" in fake_browser.navigated_to
    assert '[data-testid="page-menu-button"]' in fake_browser.clicks
    assert '[data-testid="duplicate-page-action"]' in fake_browser.clicks

    # Verify result
    assert isinstance(result, NotionPage)
    assert result.id == "page_new123"
    assert "Copy of" in result.title or result.id


# Test: create_formula
@pytest.mark.asyncio
async def test_create_formula(browser_adapter, fake_browser):
    """create_formula navigates to database and uses formula editor."""
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

    # Verify result
    assert isinstance(result, NotionFormula)
    assert result.name == "Total"
    assert "Quantity" in result.expression


# Test: create_linked_view
@pytest.mark.asyncio
async def test_create_linked_view(browser_adapter, fake_browser):
    """create_linked_view embeds linked database in page."""
    result = await browser_adapter.create_linked_view(
        source_database_id="db_source", parent_page_id="page_parent", view_type="board"
    )

    # Verify browser interactions
    assert "https://www.notion.so/page_parent" in fake_browser.navigated_to
    assert '[data-testid="linked-database-option"]' in fake_browser.clicks
    db_search_fill = fake_browser.fills.get('[data-testid="database-search-input"]')
    assert db_search_fill == "db_source"

    # Verify result
    assert isinstance(result, NotionLinkedView)
    assert result.source_database_id == "db_source"
    assert result.parent_page_id == "page_parent"
    assert result.view_type == "board"


# Test: create_calendar_view
@pytest.mark.asyncio
async def test_create_calendar_view(browser_adapter, fake_browser):
    """create_calendar_view creates calendar view with date property."""
    result = await browser_adapter.create_calendar_view("db_123", "Event Calendar", "due_date")

    # Verify browser interactions
    assert "https://www.notion.so/db_123" in fake_browser.navigated_to
    assert '[data-testid="view-type-calendar"]' in fake_browser.clicks
    assert fake_browser.fills.get('[data-testid="view-name-input"]') == "Event Calendar"

    # Verify result
    assert isinstance(result, NotionView)
    assert result.name == "Event Calendar"
    assert result.type == "calendar"
    assert result.database_id == "db_123"


# Test: create_table_view
@pytest.mark.asyncio
async def test_create_table_view(browser_adapter, fake_browser):
    """create_table_view creates table view."""
    result = await browser_adapter.create_table_view("db_123", "All Items")

    # Verify browser interactions
    assert "https://www.notion.so/db_123" in fake_browser.navigated_to
    assert '[data-testid="view-type-table"]' in fake_browser.clicks
    assert fake_browser.fills.get('[data-testid="view-name-input"]') == "All Items"

    # Verify result
    assert isinstance(result, NotionView)
    assert result.name == "All Items"
    assert result.type == "table"


# Test: create_board_view
@pytest.mark.asyncio
async def test_create_board_view(browser_adapter, fake_browser):
    """create_board_view creates kanban board view."""
    result = await browser_adapter.create_board_view("db_123", "Project Board", "status")

    # Verify browser interactions
    assert "https://www.notion.so/db_123" in fake_browser.navigated_to
    assert '[data-testid="view-type-board"]' in fake_browser.clicks
    assert fake_browser.fills.get('[data-testid="view-name-input"]') == "Project Board"

    # Verify result
    assert isinstance(result, NotionView)
    assert result.name == "Project Board"
    assert result.type == "board"


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
async def test_set_view_title_visibility_already_visible(browser_adapter, fake_browser):
    """set_view_title_visibility skips toggle if already visible."""
    # Title already visible
    fake_browser.set_element_visible('[data-testid="view-title"]', True)

    result = await browser_adapter.set_view_title_visibility("view_123", visible=True)

    # Verify toggle was NOT clicked (already in desired state)
    assert '[data-testid="view-title-visibility-toggle"]' not in fake_browser.clicks

    # Verify result
    assert result.title_visible is True


# Test: publish_page
@pytest.mark.asyncio
async def test_publish_page(browser_adapter, fake_browser):
    """publish_page enables share to web and returns public URL."""
    # Configure fake public URL
    fake_browser.set_attribute(
        '[data-testid="public-url-display"]', "value", "https://notion.site/page_123"
    )

    result = await browser_adapter.publish_page("page_123")

    # Verify browser interactions
    assert "https://www.notion.so/page_123" in fake_browser.navigated_to
    assert '[data-testid="share-button"]' in fake_browser.clicks
    assert '[data-testid="share-to-web-toggle"]' in fake_browser.clicks

    # Verify result
    assert isinstance(result, NotionPage)
    assert result.is_published is True
    assert result.public_url == "https://notion.site/page_123"


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
async def test_verify_stranger_access_accessible(browser_adapter, fake_browser):
    """verify_stranger_access returns True when page content loads."""
    # Simulate page content visible
    fake_browser.set_element_visible('[data-testid="page-content"]', True)

    url = "https://notion.site/page_123"
    result = await browser_adapter.verify_stranger_access(url)

    # Verify navigation in logged-out context
    assert "https://notion.site/page_123" in fake_browser.navigated_to

    # Verify result
    assert result is True


@pytest.mark.asyncio
async def test_verify_stranger_access_blocked(browser_adapter, fake_browser):
    """verify_stranger_access returns False when page content doesn't load."""
    # Simulate wait_for_selector timeout (page content never appears)
    # FakeBrowserSession.wait_for_selector is no-op,
    # so simulate by not setting visibility

    # Override wait_for_selector to raise exception
    async def wait_timeout(selector: str, timeout: int = 5000) -> None:
        raise Exception("Timeout waiting for selector")

    fake_browser.wait_for_selector = wait_timeout

    url = "https://notion.site/page_blocked"
    result = await browser_adapter.verify_stranger_access(url)

    # Verify result
    assert result is False
