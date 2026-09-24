"""Browser Notion adapter — Playwright-based UI automation for BROWSER operations.

Implements BROWSER-tagged operations from PLATFORM_COMPATIBILITY.md:
- duplicate_page
- create_formula
- create_linked_view
- create_calendar_view, create_table_view, create_board_view
- set_view_title_visibility
- publish_page, unpublish_page
- set_duplicate_as_template, set_search_indexing
- verify_stranger_access

This adapter is injected with a browser session manager for testing flexibility.
Production will use Playwright; tests inject a fake browser.
"""

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from .adapter import NotionAdapter
from .domain import (
    NotionCalloutBlock,
    NotionDatabase,
    NotionDatabaseProperty,
    NotionFilter,
    NotionFormula,
    NotionLinkedView,
    NotionPage,
    NotionRelation,
    NotionRollup,
    NotionSort,
    NotionTextBlock,
    NotionView,
    NotionWorkspace,
)


class BrowserSession(Protocol):
    """Protocol for browser session abstraction.
    
    Allows dependency injection for testing without real Playwright.
    Production implementation will use real Playwright browser.
    """

    async def navigate(self, url: str) -> None:
        """Navigate to URL."""
        ...

    async def click(self, selector: str) -> None:
        """Click element by selector."""
        ...

    async def fill(self, selector: str, value: str) -> None:
        """Fill input field."""
        ...

    async def get_attribute(self, selector: str, attribute: str) -> str | None:
        """Get element attribute."""
        ...

    async def is_visible(self, selector: str) -> bool:
        """Check if element is visible."""
        ...

    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> None:
        """Wait for element to appear."""
        ...

    async def get_current_url(self) -> str:
        """Get current page URL."""
        ...


class BrowserNotionAdapter(NotionAdapter):
    """Notion browser adapter (BROWSER method) — Wave 3 implementation.

    Uses browser automation (Playwright in production, fake in tests) for 
    UI-only Notion operations that have no API equivalent.
    """

    def __init__(self, browser_session: BrowserSession) -> None:
        """Initialize with injected browser session.
        
        Args:
            browser_session: Browser abstraction for navigation/interaction.
                            Production: Playwright-backed session (W4+ scope).
                            Tests: Fake session with synthetic responses.
        """
        self._browser = browser_session

    # DIRECT_API operations — not implemented in browser adapter
    async def connection_status(self) -> dict[str, bool | str | int]:
        raise NotImplementedError(
            "connection_status uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def workspace_discovery(self) -> list[NotionWorkspace]:
        raise NotImplementedError(
            "workspace_discovery uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def create_page(
        self,
        title: str,
        parent_id: str | None = None,
        parent_type: str = "workspace",
        icon: str | None = None,
        cover: str | None = None,
    ) -> NotionPage:
        raise NotImplementedError(
            "create_page uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    # BROWSER operations — implemented in Wave 3
    async def duplicate_page(self, page_id: str) -> NotionPage:
        """Duplicate page via UI interaction.
        
        Method: BROWSER
        Mutates: true
        Idempotent: false (always creates new page)
        """
        # Navigate to page
        page_url = f"https://www.notion.so/{page_id}"
        await self._browser.navigate(page_url)
        
        # Click page menu (three dots)
        await self._browser.click('[data-testid="page-menu-button"]')
        await self._browser.wait_for_selector('[data-testid="duplicate-page-action"]')
        
        # Click duplicate
        await self._browser.click('[data-testid="duplicate-page-action"]')
        await self._browser.wait_for_selector(
            '[data-testid="page-duplicated-toast"]', timeout=10000
        )

        # Extract new page ID from URL or duplicate result
        new_url = await self._browser.get_current_url()
        if "/" in new_url:
            new_page_id = new_url.split("/")[-1].split("?")[0]
        else:
            new_page_id = f"page_{uuid4().hex[:12]}"
        
        return NotionPage(
            id=new_page_id,
            title=f"Copy of page_{page_id}",
            parent_id=None,
            parent_type="workspace",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def rename_page(self, page_id: str, new_title: str) -> NotionPage:
        raise NotImplementedError(
            "rename_page uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def move_page(
        self, page_id: str, new_parent_id: str, new_parent_type: str = "workspace"
    ) -> NotionPage:
        raise NotImplementedError(
            "move_page uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def set_icon(self, page_id: str, icon: str) -> NotionPage:
        raise NotImplementedError(
            "set_icon uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def set_cover(self, page_id: str, cover_url: str) -> NotionPage:
        raise NotImplementedError(
            "set_cover uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def add_text_block(self, page_id: str, content: str) -> NotionTextBlock:
        raise NotImplementedError(
            "add_text_block uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def add_callout_block(
        self, page_id: str, content: str, icon: str = "💡"
    ) -> NotionCalloutBlock:
        raise NotImplementedError(
            "add_callout_block uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def create_database(
        self,
        title: str,
        parent_id: str | None = None,
        parent_type: str = "workspace",
        icon: str | None = None,
        cover: str | None = None,
    ) -> NotionDatabase:
        raise NotImplementedError(
            "create_database uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def add_property(
        self, database_id: str, name: str, property_type: str, config: dict[str, Any]
    ) -> NotionDatabaseProperty:
        raise NotImplementedError(
            "add_property uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def create_relation(
        self,
        database_id: str,
        name: str,
        target_database_id: str,
        synced_property_name: str | None = None,
    ) -> NotionRelation:
        raise NotImplementedError(
            "create_relation uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def create_rollup(
        self,
        database_id: str,
        name: str,
        relation_property_id: str,
        rollup_property_id: str,
        function: str,
    ) -> NotionRollup:
        raise NotImplementedError(
            "create_rollup uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def create_formula(
        self, database_id: str, name: str, expression: str
    ) -> NotionFormula:
        """Create formula property via UI formula editor.
        
        Method: BROWSER (formula editor is UI-only; API read-only)
        Mutates: true
        Idempotent: true (updating same formula)
        """
        # Navigate to database
        db_url = f"https://www.notion.so/{database_id}"
        await self._browser.navigate(db_url)
        
        # Open property menu
        await self._browser.click('[data-testid="add-property-button"]')
        await self._browser.wait_for_selector('[data-testid="property-type-select"]')
        
        # Select formula type
        await self._browser.click('[data-testid="property-type-select"]')
        await self._browser.click('[data-testid="property-type-formula"]')
        
        # Fill property name
        await self._browser.fill('[data-testid="property-name-input"]', name)
        
        # Fill formula expression in editor
        await self._browser.click('[data-testid="formula-editor"]')
        await self._browser.fill('[data-testid="formula-expression-input"]', expression)
        
        # Save property
        await self._browser.click('[data-testid="save-property-button"]')
        
        return NotionFormula(
            id=f"prop_{uuid4().hex[:12]}",
            name=name,
            expression=expression,
        )

    async def create_linked_view(
        self,
        source_database_id: str,
        parent_page_id: str,
        view_type: str = "table",
    ) -> NotionLinkedView:
        """Create linked database view via UI.
        
        Method: BROWSER (linked database creation is UI-only)
        Mutates: true
        Idempotent: false
        """
        # Navigate to parent page
        page_url = f"https://www.notion.so/{parent_page_id}"
        await self._browser.navigate(page_url)
        
        # Click slash command menu
        await self._browser.click('[data-testid="page-content"]')
        await self._browser.fill('[data-testid="slash-command-input"]', "/linked")
        await self._browser.wait_for_selector('[data-testid="linked-database-option"]')
        
        # Select linked database
        await self._browser.click('[data-testid="linked-database-option"]')
        
        # Search for source database
        await self._browser.fill(
            '[data-testid="database-search-input"]', source_database_id
        )
        await self._browser.click(
            f'[data-testid="database-option-{source_database_id}"]'
        )
        
        # Set view type
        if view_type != "table":
            await self._browser.click('[data-testid="view-type-select"]')
            await self._browser.click(f'[data-testid="view-type-{view_type}"]')
        
        return NotionLinkedView(
            id=f"view_{uuid4().hex[:12]}",
            source_database_id=source_database_id,
            parent_page_id=parent_page_id,
            view_type=view_type,
        )

    async def add_filter(
        self, database_id: str, view_id: str, filter_spec: NotionFilter
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "add_filter uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def add_sort(
        self, database_id: str, view_id: str, sort_spec: NotionSort
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "add_sort uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def create_calendar_view(
        self, database_id: str, name: str, date_property: str
    ) -> NotionView:
        """Create calendar view via UI.
        
        Method: BROWSER (view creation is UI-only)
        Mutates: true
        Idempotent: false
        """
        # Navigate to database
        db_url = f"https://www.notion.so/{database_id}"
        await self._browser.navigate(db_url)
        
        # Open view menu
        await self._browser.click('[data-testid="add-view-button"]')
        await self._browser.wait_for_selector('[data-testid="view-type-select"]')
        
        # Select calendar type
        await self._browser.click('[data-testid="view-type-calendar"]')
        
        # Fill view name
        await self._browser.fill('[data-testid="view-name-input"]', name)
        
        # Select date property
        await self._browser.click('[data-testid="calendar-date-property-select"]')
        await self._browser.click(f'[data-testid="property-option-{date_property}"]')
        
        # Create view
        await self._browser.click('[data-testid="create-view-button"]')
        
        return NotionView(
            id=f"view_{uuid4().hex[:12]}",
            database_id=database_id,
            name=name,
            type="calendar",
            show_title=True,
        )

    async def create_table_view(self, database_id: str, name: str) -> NotionView:
        """Create table view via UI.
        
        Method: BROWSER (view creation is UI-only)
        Mutates: true
        Idempotent: false
        """
        # Navigate to database
        db_url = f"https://www.notion.so/{database_id}"
        await self._browser.navigate(db_url)
        
        # Open view menu
        await self._browser.click('[data-testid="add-view-button"]')
        await self._browser.wait_for_selector('[data-testid="view-type-select"]')
        
        # Select table type
        await self._browser.click('[data-testid="view-type-table"]')
        
        # Fill view name
        await self._browser.fill('[data-testid="view-name-input"]', name)
        
        # Create view
        await self._browser.click('[data-testid="create-view-button"]')
        
        return NotionView(
            id=f"view_{uuid4().hex[:12]}",
            database_id=database_id,
            name=name,
            type="table",
            show_title=True,
        )

    async def create_board_view(
        self, database_id: str, name: str, group_by_property: str
    ) -> NotionView:
        """Create board (kanban) view via UI.
        
        Method: BROWSER (view creation is UI-only)
        Mutates: true
        Idempotent: false
        """
        # Navigate to database
        db_url = f"https://www.notion.so/{database_id}"
        await self._browser.navigate(db_url)
        
        # Open view menu
        await self._browser.click('[data-testid="add-view-button"]')
        await self._browser.wait_for_selector('[data-testid="view-type-select"]')
        
        # Select board type
        await self._browser.click('[data-testid="view-type-board"]')
        
        # Fill view name
        await self._browser.fill('[data-testid="view-name-input"]', name)
        
        # Select group-by property
        await self._browser.click('[data-testid="board-group-by-select"]')
        await self._browser.click(
            f'[data-testid="property-option-{group_by_property}"]'
        )
        
        # Create view
        await self._browser.click('[data-testid="create-view-button"]')
        
        return NotionView(
            id=f"view_{uuid4().hex[:12]}",
            database_id=database_id,
            name=name,
            type="board",
            show_title=True,
        )

    async def set_view_title_visibility(
        self, view_id: str, visible: bool
    ) -> NotionView:
        """Set view title visibility via UI settings.

        Method: BROWSER (view settings are UI-only)
        Mutates: true
        Idempotent: true
        """
        # Navigate to view (URL pattern may vary)
        view_url = f"https://www.notion.so/view/{view_id}"
        await self._browser.navigate(view_url)

        # Open view settings
        await self._browser.click('[data-testid="view-settings-button"]')
        await self._browser.wait_for_selector(
            '[data-testid="view-title-visibility-toggle"]'
        )

        # Check current state and toggle if needed
        is_currently_visible = await self._browser.is_visible(
            '[data-testid="view-title"]'
        )
        if is_currently_visible != visible:
            await self._browser.click('[data-testid="view-title-visibility-toggle"]')
        
        return NotionView(
            id=view_id,
            database_id="",  # Unknown from this context
            name="",  # Unknown from this context
            type="unknown",
            show_title=visible,
        )

    async def add_child_page(self, parent_page_id: str, title: str) -> NotionPage:
        raise NotImplementedError(
            "add_child_page uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def publish_page(self, page_id: str) -> NotionPage:
        """Publish page to web via UI share settings.
        
        Method: BROWSER (share to web is UI-only)
        Mutates: true
        Idempotent: true
        """
        # Navigate to page
        page_url = f"https://www.notion.so/{page_id}"
        await self._browser.navigate(page_url)
        
        # Open share menu
        await self._browser.click('[data-testid="share-button"]')
        await self._browser.wait_for_selector('[data-testid="share-menu"]')
        
        # Enable "Share to web"
        await self._browser.click('[data-testid="share-to-web-toggle"]')
        await self._browser.wait_for_selector('[data-testid="public-url-display"]')
        
        # Extract public URL
        public_url_attr = await self._browser.get_attribute(
            '[data-testid="public-url-display"]', 
            "value"
        )
        public_url = public_url_attr or f"https://www.notion.so/{page_id}"
        
        # Close share menu
        await self._browser.click('[data-testid="close-share-menu"]')
        
        return NotionPage(
            id=page_id,
            title="",  # Unknown from this context
            public_url=public_url,
            is_published=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def set_duplicate_as_template(
        self, page_id: str, enabled: bool
    ) -> NotionPage:
        """Set "Duplicate as template" page setting via UI.
        
        Method: BROWSER (page settings are UI-only)
        Mutates: true
        Idempotent: true
        """
        # Navigate to page
        page_url = f"https://www.notion.so/{page_id}"
        await self._browser.navigate(page_url)
        
        # Open page settings menu
        await self._browser.click('[data-testid="page-menu-button"]')
        await self._browser.wait_for_selector('[data-testid="page-settings"]')
        await self._browser.click('[data-testid="page-settings"]')
        
        # Toggle "Duplicate as template"
        is_currently_enabled = await self._browser.is_visible(
            '[data-testid="duplicate-as-template-enabled"]'
        )
        if is_currently_enabled != enabled:
            await self._browser.click('[data-testid="duplicate-as-template-toggle"]')
        
        # Close settings
        await self._browser.click('[data-testid="close-settings"]')
        
        return NotionPage(
            id=page_id,
            title="",  # Unknown from this context
            duplicate_as_template=enabled,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def set_search_indexing(self, page_id: str, enabled: bool) -> NotionPage:
        """Set "Allow search engines to index" page setting via UI.
        
        Method: BROWSER (page settings are UI-only)
        Mutates: true
        Idempotent: true
        """
        # Navigate to page
        page_url = f"https://www.notion.so/{page_id}"
        await self._browser.navigate(page_url)
        
        # Open page settings menu
        await self._browser.click('[data-testid="page-menu-button"]')
        await self._browser.wait_for_selector('[data-testid="page-settings"]')
        await self._browser.click('[data-testid="page-settings"]')
        
        # Toggle "Allow search engines to index"
        is_currently_enabled = await self._browser.is_visible(
            '[data-testid="search-indexing-enabled"]'
        )
        if is_currently_enabled != enabled:
            await self._browser.click('[data-testid="search-indexing-toggle"]')
        
        # Close settings
        await self._browser.click('[data-testid="close-settings"]')
        
        return NotionPage(
            id=page_id,
            title="",  # Unknown from this context
            search_indexing=enabled,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def get_public_url(self, page_id: str) -> str | None:
        raise NotImplementedError(
            "get_public_url uses COMBINED method (API + browser). "
            "Use CombinedNotionAdapter or FixtureNotionAdapter."
        )

    async def unpublish_page(self, page_id: str) -> NotionPage:
        """Unpublish page (disable share to web) via UI.
        
        Method: BROWSER (share settings are UI-only)
        Mutates: true
        Idempotent: true
        """
        # Navigate to page
        page_url = f"https://www.notion.so/{page_id}"
        await self._browser.navigate(page_url)
        
        # Open share menu
        await self._browser.click('[data-testid="share-button"]')
        await self._browser.wait_for_selector('[data-testid="share-menu"]')
        
        # Check if currently published and toggle off if needed
        is_published = await self._browser.is_visible(
            '[data-testid="public-url-display"]'
        )
        if is_published:
            await self._browser.click('[data-testid="share-to-web-toggle"]')
        
        # Close share menu
        await self._browser.click('[data-testid="close-share-menu"]')
        
        return NotionPage(
            id=page_id,
            title="",  # Unknown from this context
            public_url=None,
            is_published=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def inspect_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "inspect_page uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def inspect_database(self, database_id: str) -> NotionDatabase:
        raise NotImplementedError(
            "inspect_database uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def verify_stranger_access(self, public_url: str) -> bool:
        """Verify public URL is accessible to logged-out users.
        
        Method: BROWSER (requires logged-out browser session)
        Mutates: false
        Idempotent: true
        """
        # Navigate to public URL (in logged-out context)
        await self._browser.navigate(public_url)
        
        # Check if page content is visible (not login wall)
        try:
            await self._browser.wait_for_selector(
                '[data-testid="page-content"]', timeout=3000
            )
            return True
        except Exception:
            # Login wall or error page
            return False
