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

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

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


def translate_browser_exceptions(fn):
    """Decorator to translate Playwright-style exceptions to built-in exceptions.

    Maps:
    - Exceptions named 'TimeoutError' from 'playwright.*' modules -> built-in TimeoutError
    - Exceptions named 'Error' from 'playwright.*' modules containing navigation/connection
      keywords -> ConnectionError
    - All other exceptions propagate unchanged

    Uses FAKE exception matching only — no actual Playwright import.
    """

    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            exc_type = type(e)
            exc_module = exc_type.__module__
            exc_name = exc_type.__name__

            # Check if exception is from a playwright module
            if exc_module and exc_module.startswith("playwright."):
                # Map TimeoutError from playwright to built-in TimeoutError
                if exc_name == "TimeoutError":
                    raise TimeoutError(str(e)) from e

                # Map Error from playwright containing navigation/connection keywords
                # to built-in ConnectionError
                if exc_name == "Error":
                    error_message = str(e).lower()
                    if any(
                        keyword in error_message
                        for keyword in ["navigation", "connection", "net::", "network"]
                    ):
                        raise ConnectionError(str(e)) from e

            # All other exceptions propagate unchanged
            raise

    return wrapper


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

    async def close(self) -> None:
        """Close the browser session."""
        ...


class BrowserNotionAdapter(NotionAdapter):
    """Notion browser adapter (BROWSER method) — Wave 3 implementation.

    Uses browser automation (Playwright in production, fake in tests) for
    UI-only Notion operations that have no API equivalent.
    """

    def __init__(
        self,
        browser_session: BrowserSession,
        anon_session_factory: Callable[[], BrowserSession] | None = None,
    ) -> None:
        """Initialize with injected browser session.

        Args:
            browser_session: Browser abstraction for navigation/interaction.
                            Production: Playwright-backed session (W4+ scope).
                            Tests: Fake session with synthetic responses.
            anon_session_factory: Factory to create anonymous (logged-out) browser sessions.
                                 Required for verify_stranger_access.
                                 Tests can inject a factory returning a separate fake session.
        """
        self._browser = browser_session
        self._anon_session_factory = anon_session_factory

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
        # Validate page_id is not empty
        if not page_id or not page_id.strip():
            raise ValueError("page_id cannot be empty")

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

        # Extract new page ID from URL
        new_url = await self._browser.get_current_url()

        # Parse the ID from the URL
        # Notion URLs can be:
        # - https://www.notion.so/32hexid
        # - https://www.notion.so/Title-32hexid
        # - https://www.notion.so/32-hex-id-with-dashes
        # - https://www.notion.so/Title-32-hex-id-with-dashes
        # Extract the last path segment
        url_path = new_url.split("?")[0]  # Remove query params
        last_segment = url_path.rstrip("/").split("/")[-1]

        # If the segment contains a dash and looks like Title-ID, extract the trailing ID
        if "-" in last_segment:
            # Split by dash and look for the trailing 32-hex ID
            parts = last_segment.split("-")
            # Try to find a 32-character hex string (with or without dashes)
            # Start from the end and reconstruct the ID
            potential_id = ""
            for i in range(len(parts) - 1, -1, -1):
                part = parts[i]
                # Check if this part contains only hex characters
                if all(c in "0123456789abcdefABCDEF" for c in part):
                    potential_id = part + potential_id
                    # Check if we have 32 hex characters
                    if len(potential_id) == 32:
                        break
                else:
                    # If we hit a non-hex part, we've gone past the ID
                    break

            if len(potential_id) == 32:
                new_page_id = potential_id
            else:
                raise RuntimeError(
                    f"Failed to parse page ID from URL {new_url}: "
                    f"expected 32-hex ID, got segment '{last_segment}'"
                )
        else:
            # No dash, expect the whole segment to be a 32-hex ID
            new_page_id = last_segment.replace("-", "")  # Remove any dashes
            if len(new_page_id) != 32 or not all(
                c in "0123456789abcdefABCDEF" for c in new_page_id
            ):
                raise RuntimeError(
                    f"Failed to parse page ID from URL {new_url}: "
                    f"expected 32-hex ID, got '{last_segment}'"
                )

        # Verify new ID differs from source
        source_id_normalized = page_id.replace("-", "")
        if new_page_id == source_id_normalized:
            raise RuntimeError(
                f"Duplicate page ID matches source ID ({page_id}). Duplication may have failed."
            )

        # Read the title from the duplicated page
        title_attr = await self._browser.get_attribute('[data-testid="page-title"]', "textContent")
        if not title_attr:
            raise RuntimeError(f"Failed to read page title after duplicating {page_id}")

        return NotionPage(
            id=new_page_id,
            title=title_attr,
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
            "move_page uses API method, not BROWSER. Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def set_icon(self, page_id: str, icon: str) -> NotionPage:
        raise NotImplementedError(
            "set_icon uses API method, not BROWSER. Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def set_cover(self, page_id: str, cover_url: str) -> NotionPage:
        raise NotImplementedError(
            "set_cover uses API method, not BROWSER. Use APINotionAdapter or FixtureNotionAdapter."
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

    async def create_formula(self, database_id: str, name: str, expression: str) -> NotionFormula:
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

        # Read the property ID from the saved property element
        property_id_attr = await self._browser.get_attribute(
            '[data-testid="property-saved"]', "data-property-id"
        )
        if not property_id_attr:
            raise RuntimeError(
                f"Failed to read property ID after creating formula '{name}' "
                f"in database {database_id}"
            )

        return NotionFormula(
            id=property_id_attr,
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
        await self._browser.fill('[data-testid="database-search-input"]', source_database_id)
        await self._browser.click(f'[data-testid="database-option-{source_database_id}"]')

        # Set view type
        if view_type != "table":
            await self._browser.click('[data-testid="view-type-select"]')
            await self._browser.click(f'[data-testid="view-type-{view_type}"]')

        # Read the view ID from the created linked view element
        view_id_attr = await self._browser.get_attribute(
            '[data-testid="linked-view-created"]', "data-view-id"
        )
        if not view_id_attr:
            raise RuntimeError(
                f"Failed to read view ID after creating linked view "
                f"for database {source_database_id} in page {parent_page_id}"
            )

        return NotionLinkedView(
            id=view_id_attr,
            source_database_id=source_database_id,
            parent_page_id=parent_page_id,
            view_type=view_type,
        )

    async def add_filter(
        self, database_id: str, view_id: str, filter_spec: NotionFilter
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "add_filter uses API method, not BROWSER. Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def add_sort(
        self, database_id: str, view_id: str, sort_spec: NotionSort
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "add_sort uses API method, not BROWSER. Use APINotionAdapter or FixtureNotionAdapter."
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

        # Capture current view ID (if any) before creating new view
        initial_url = await self._browser.get_current_url()
        initial_view_id = None
        if "?v=" in initial_url:
            initial_view_id = initial_url.split("?v=")[1].split("&")[0]

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

        # Read the view ID from the created view
        current_url = await self._browser.get_current_url()
        # View ID is in URL after ?v=
        if "?v=" not in current_url:
            raise RuntimeError(
                f"Failed to read view ID after creating calendar view '{name}' "
                f"in database {database_id}: URL missing ?v= parameter"
            )
        view_id = current_url.split("?v=")[1].split("&")[0]

        # Verify the view ID changed (new view was created)
        if initial_view_id is not None and view_id == initial_view_id:
            raise RuntimeError(
                f"View ID unchanged after creating calendar view '{name}' "
                f"in database {database_id}: still {view_id}"
            )

        return NotionView(
            id=view_id,
            database_id=database_id,
            name=name,
            type="calendar",
            title_visible=True,
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

        # Capture current view ID (if any) before creating new view
        initial_url = await self._browser.get_current_url()
        initial_view_id = None
        if "?v=" in initial_url:
            initial_view_id = initial_url.split("?v=")[1].split("&")[0]

        # Open view menu
        await self._browser.click('[data-testid="add-view-button"]')
        await self._browser.wait_for_selector('[data-testid="view-type-select"]')

        # Select table type
        await self._browser.click('[data-testid="view-type-table"]')

        # Fill view name
        await self._browser.fill('[data-testid="view-name-input"]', name)

        # Create view
        await self._browser.click('[data-testid="create-view-button"]')

        # Read the view ID from the created view
        current_url = await self._browser.get_current_url()
        # View ID is in URL after ?v=
        if "?v=" not in current_url:
            raise RuntimeError(
                f"Failed to read view ID after creating table view '{name}' "
                f"in database {database_id}: URL missing ?v= parameter"
            )
        view_id = current_url.split("?v=")[1].split("&")[0]

        # Verify the view ID changed (new view was created)
        if initial_view_id is not None and view_id == initial_view_id:
            raise RuntimeError(
                f"View ID unchanged after creating table view '{name}' "
                f"in database {database_id}: still {view_id}"
            )

        return NotionView(
            id=view_id,
            database_id=database_id,
            name=name,
            type="table",
            title_visible=True,
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

        # Capture current view ID (if any) before creating new view
        initial_url = await self._browser.get_current_url()
        initial_view_id = None
        if "?v=" in initial_url:
            initial_view_id = initial_url.split("?v=")[1].split("&")[0]

        # Open view menu
        await self._browser.click('[data-testid="add-view-button"]')
        await self._browser.wait_for_selector('[data-testid="view-type-select"]')

        # Select board type
        await self._browser.click('[data-testid="view-type-board"]')

        # Fill view name
        await self._browser.fill('[data-testid="view-name-input"]', name)

        # Select group-by property
        await self._browser.click('[data-testid="board-group-by-select"]')
        await self._browser.click(f'[data-testid="property-option-{group_by_property}"]')

        # Create view
        await self._browser.click('[data-testid="create-view-button"]')

        # Read the view ID from the created view
        current_url = await self._browser.get_current_url()
        # View ID is in URL after ?v=
        if "?v=" not in current_url:
            raise RuntimeError(
                f"Failed to read view ID after creating board view '{name}' "
                f"in database {database_id}: URL missing ?v= parameter"
            )
        view_id = current_url.split("?v=")[1].split("&")[0]

        # Verify the view ID changed (new view was created)
        if initial_view_id is not None and view_id == initial_view_id:
            raise RuntimeError(
                f"View ID unchanged after creating board view '{name}' "
                f"in database {database_id}: still {view_id}"
            )

        return NotionView(
            id=view_id,
            database_id=database_id,
            name=name,
            type="board",
            title_visible=True,
        )

    async def set_view_title_visibility(
        self, database_id: str, view_id: str, visible: bool
    ) -> NotionView:
        """Set view title visibility via UI settings.

        Method: BROWSER (view settings are UI-only)
        Mutates: true
        Idempotent: true
        """
        # Validate database_id (32-hex, with or without dashes)
        # Normalize to undashed form
        normalized_db_id = database_id.replace("-", "")
        if (
            not normalized_db_id
            or len(normalized_db_id) != 32
            or not all(c in "0123456789abcdefABCDEF" for c in normalized_db_id)
        ):
            raise ValueError(f"Invalid database_id: {database_id}")

        # Build view URL directly from database_id
        view_url = f"https://www.notion.so/{normalized_db_id}?v={view_id}"
        await self._browser.navigate(view_url)

        # Open view settings
        await self._browser.click('[data-testid="view-settings-button"]')
        await self._browser.wait_for_selector('[data-testid="view-title-visibility-toggle"]')

        # Check current state and toggle if needed
        is_currently_visible = await self._browser.is_visible('[data-testid="view-title"]')
        if is_currently_visible != visible:
            await self._browser.click('[data-testid="view-title-visibility-toggle"]')

        # Read back view properties where possible
        view_name_attr = await self._browser.get_attribute(
            '[data-testid="view-name"]', "textContent"
        )
        view_name = view_name_attr or ""

        view_type_attr = await self._browser.get_attribute(
            '[data-testid="view-type"]', "data-view-type"
        )
        view_type = view_type_attr or "unknown"

        # Extract database_id from URL
        current_url_after = await self._browser.get_current_url()
        database_id = ""
        if "/" in current_url_after:
            database_id = current_url_after.split("/")[-1].split("?")[0]

        return NotionView(
            id=view_id,
            database_id=database_id,
            name=view_name,
            type=view_type,
            title_visible=visible,
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

        # Check if already published
        is_already_published = await self._browser.is_visible('[data-testid="public-url-display"]')

        # Only toggle if not already published
        if not is_already_published:
            await self._browser.click('[data-testid="share-to-web-toggle"]')
            await self._browser.wait_for_selector('[data-testid="public-url-display"]')

        # Extract public URL
        public_url_attr = await self._browser.get_attribute(
            '[data-testid="public-url-display"]', "value"
        )
        if not public_url_attr:
            raise RuntimeError(f"Failed to read public URL after publishing {page_id}")

        # Close share menu
        await self._browser.click('[data-testid="close-share-menu"]')

        return NotionPage(
            id=page_id,
            title="",  # Unknown from this context
            public_url=public_url_attr,
            is_published=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def set_duplicate_as_template(self, page_id: str, enabled: bool) -> NotionPage:
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

        # Check if currently published and only toggle if it is
        is_published = await self._browser.is_visible('[data-testid="public-url-display"]')
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
        # Validate URL is HTTPS and has allowed host
        # Only allow notion.so, www.notion.so, notion.site, www.notion.site (no other subdomains)
        from urllib.parse import urlparse

        try:
            parsed = urlparse(public_url)
        except Exception as e:
            raise ValueError(f"Invalid URL: {public_url}") from e

        # Must be HTTPS
        if parsed.scheme != "https":
            raise ValueError(f"URL must use HTTPS: {public_url}")

        # Reject userinfo in URL (https://user:pass@host or https://user@host)
        if parsed.username or parsed.password:
            raise ValueError(f"URL must not contain userinfo: {public_url}")

        # Must be exactly notion.so, www.notion.so, notion.site, or www.notion.site
        # (no other subdomains, no lookalikes)
        # Reject:
        # - evil.notion.so
        # - notion.so.evil.com
        # - https://notion.so@evil.com (userinfo trick)
        allowed_hosts = {"notion.so", "www.notion.so", "notion.site", "www.notion.site"}
        if parsed.hostname not in allowed_hosts:
            raise ValueError(
                f"URL host must be notion.so, www.notion.so, notion.site, "
                f"or www.notion.site, got: {parsed.hostname}"
            )

        if self._anon_session_factory is None:
            raise RuntimeError(
                "verify_stranger_access requires an anonymous session factory. "
                "BrowserNotionAdapter must be initialized with anon_session_factory."
            )

        # Create a separate anonymous (logged-out) session
        anon_session = self._anon_session_factory()

        try:
            # Navigate to public URL in anonymous context
            try:
                await anon_session.navigate(public_url)
            except (ConnectionError, TimeoutError, ValueError) as e:
                # Network, navigation, or value failures
                raise RuntimeError(f"Failed to navigate to {public_url}: {e}") from e

            # Check if page content is visible (not login wall)
            try:
                await anon_session.wait_for_selector('[data-testid="page-content"]', timeout=3000)
                return True
            except TimeoutError:
                # Timeout means page content didn't appear (likely login wall)
                return False
        finally:
            # Always close the anonymous session
            await anon_session.close()
