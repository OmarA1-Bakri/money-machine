"""NotionAdapter interface — abstract protocol for Notion operations.

Defines the contract for interacting with Notion via different methods:
DIRECT_API, COMPOSIO, BROWSER, COMBINED, or FIXTURE (for testing).

All operations are async. Mutating operations must document idempotency and
reconciliation requirements. See docs/architecture/PLATFORM_COMPATIBILITY.md
for per-operation method selection and contracts.
"""

from abc import ABC, abstractmethod

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


class NotionAdapter(ABC):
    """Abstract interface for Notion operations.

    Implementations: FixtureNotionAdapter (W1), APINotionAdapter (W2+),
    BrowserNotionAdapter (W2+), CombinedNotionAdapter (W3+).
    """

    @abstractmethod
    async def connection_status(self) -> dict[str, bool]:
        """Check API token validity and workspace access.

        Method: DIRECT_API
        Mutates: false
        Requires Auth: true
        Idempotent: true
        Reconcilable: N/A

        Returns:
            dict with keys:
                - connected: bool
                - user_id: str | None
                - workspace_count: int
        """

    @abstractmethod
    async def workspace_discovery(self) -> list[NotionWorkspace]:
        """List accessible workspaces.

        Method: DIRECT_API
        Mutates: false
        Requires Auth: true
        Idempotent: true
        Reconcilable: N/A
        """

    @abstractmethod
    async def create_page(
        self,
        title: str,
        parent_id: str | None = None,
        parent_type: str = "workspace",
        icon: str | None = None,
        cover: str | None = None,
    ) -> NotionPage:
        """Create a new page.

        Method: DIRECT_API
        Mutates: true
        Requires Auth: true
        Idempotent: false (use external_id or title+parent check for retry)
        Reconcilable: true (inspect post-state)

        Args:
            title: Page title
            parent_id: Parent workspace/page/database ID (None = workspace root)
            parent_type: "workspace" | "page_id" | "database_id"
            icon: Emoji or external URL
            cover: External URL

        Returns:
            Created NotionPage with assigned ID
        """

    @abstractmethod
    async def duplicate_page(self, page_id: str) -> NotionPage:
        """Duplicate an existing page.

        Method: BROWSER (UI-only, no API equivalent)
        Mutates: true
        Requires Auth: true
        Idempotent: false (always creates new page)
        Reconcilable: true (check new page exists)

        Args:
            page_id: Source page to duplicate

        Returns:
            Duplicated NotionPage with new ID
        """

    @abstractmethod
    async def rename_page(self, page_id: str, new_title: str) -> NotionPage:
        """Rename a page.

        Method: DIRECT_API
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            page_id: Page to rename
            new_title: New title

        Returns:
            Updated NotionPage
        """

    @abstractmethod
    async def move_page(
        self, page_id: str, new_parent_id: str, new_parent_type: str = "workspace"
    ) -> NotionPage:
        """Move a page to a new parent.

        Method: DIRECT_API
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            page_id: Page to move
            new_parent_id: New parent workspace/page ID
            new_parent_type: "workspace" | "page_id"

        Returns:
            Updated NotionPage
        """

    @abstractmethod
    async def set_icon(self, page_id: str, icon: str) -> NotionPage:
        """Set page icon (emoji or external URL).

        Method: DIRECT_API
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            page_id: Page to update
            icon: Emoji or external URL

        Returns:
            Updated NotionPage
        """

    @abstractmethod
    async def set_cover(self, page_id: str, cover_url: str) -> NotionPage:
        """Set page cover image.

        Method: DIRECT_API
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            page_id: Page to update
            cover_url: External image URL

        Returns:
            Updated NotionPage
        """

    @abstractmethod
    async def add_text_block(self, page_id: str, content: str) -> NotionTextBlock:
        """Append a text (paragraph) block to a page.

        Method: DIRECT_API
        Mutates: true
        Requires Auth: true
        Idempotent: false (appends every time)
        Reconcilable: true (inspect post-state blocks)

        Args:
            page_id: Parent page
            content: Text content

        Returns:
            Created NotionTextBlock
        """

    @abstractmethod
    async def add_callout_block(
        self, page_id: str, content: str, icon: str = "💡"
    ) -> NotionCalloutBlock:
        """Append a callout block to a page.

        Method: DIRECT_API
        Mutates: true
        Requires Auth: true
        Idempotent: false (appends every time)
        Reconcilable: true (inspect post-state blocks)

        Args:
            page_id: Parent page
            content: Callout text
            icon: Callout icon emoji

        Returns:
            Created NotionCalloutBlock
        """

    @abstractmethod
    async def create_database(
        self,
        title: str,
        parent_id: str | None = None,
        parent_type: str = "workspace",
        icon: str | None = None,
        cover: str | None = None,
    ) -> NotionDatabase:
        """Create a new database.

        Method: DIRECT_API
        Mutates: true
        Requires Auth: true
        Idempotent: false (check title+parent before retry)
        Reconcilable: true (inspect post-state)

        Args:
            title: Database title
            parent_id: Parent workspace/page ID (None = workspace root)
            parent_type: "workspace" | "page_id"
            icon: Emoji or external URL
            cover: External URL

        Returns:
            Created NotionDatabase with assigned ID
        """

    @abstractmethod
    async def add_property(
        self, database_id: str, name: str, property_type: str, config: dict
    ) -> NotionDatabaseProperty:
        """Add a property (column) to a database.

        Method: DIRECT_API
        Mutates: true
        Requires Auth: true
        Idempotent: true (adding same-name property updates it)
        Reconcilable: true

        Args:
            database_id: Target database
            name: Property name
            property_type: title | text | number | select | date | etc.
            config: Type-specific configuration

        Returns:
            Created/updated NotionDatabaseProperty
        """

    @abstractmethod
    async def create_relation(
        self,
        database_id: str,
        name: str,
        target_database_id: str,
        synced_property_name: str | None = None,
    ) -> NotionRelation:
        """Create a relation property.

        Method: DIRECT_API
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            database_id: Source database
            name: Relation property name
            target_database_id: Target database
            synced_property_name: Two-way relation name (optional)

        Returns:
            Created NotionRelation
        """

    @abstractmethod
    async def create_rollup(
        self,
        database_id: str,
        name: str,
        relation_property_id: str,
        rollup_property_id: str,
        function: str,
    ) -> NotionRollup:
        """Create a rollup property.

        Method: DIRECT_API
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            database_id: Target database
            name: Rollup property name
            relation_property_id: Relation to follow
            rollup_property_id: Property to aggregate
            function: count | sum | average | min | max | etc.

        Returns:
            Created NotionRollup
        """

    @abstractmethod
    async def create_formula(self, database_id: str, name: str, expression: str) -> NotionFormula:
        """Create a formula property.

        Method: BROWSER (formula editor is UI-only; API read-only)
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            database_id: Target database
            name: Formula property name
            expression: Notion formula expression

        Returns:
            Created NotionFormula
        """

    @abstractmethod
    async def create_linked_view(
        self,
        source_database_id: str,
        parent_page_id: str,
        view_type: str = "table",
    ) -> NotionLinkedView:
        """Create a linked database view.

        Method: BROWSER (UI-only, no API equivalent)
        Mutates: true
        Requires Auth: true
        Idempotent: false
        Reconcilable: true

        Args:
            source_database_id: Canonical database to link
            parent_page_id: Page to embed view in
            view_type: table | board | calendar

        Returns:
            Created NotionLinkedView
        """

    @abstractmethod
    async def add_filter(self, database_id: str, view_id: str, filter_spec: NotionFilter) -> dict:
        """Add a filter to a database view.

        Method: DIRECT_API (part of database query)
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            database_id: Target database
            view_id: Target view
            filter_spec: Filter specification

        Returns:
            Updated view config
        """

    @abstractmethod
    async def add_sort(self, database_id: str, view_id: str, sort_spec: NotionSort) -> dict:
        """Add a sort to a database view.

        Method: DIRECT_API (part of database query)
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            database_id: Target database
            view_id: Target view
            sort_spec: Sort specification

        Returns:
            Updated view config
        """

    @abstractmethod
    async def create_calendar_view(
        self, database_id: str, name: str, date_property: str
    ) -> NotionView:
        """Create a calendar view.

        Method: BROWSER (view creation is UI-only)
        Mutates: true
        Requires Auth: true
        Idempotent: false
        Reconcilable: true

        Args:
            database_id: Target database
            name: View name
            date_property: Property to use for calendar dates

        Returns:
            Created NotionView
        """

    @abstractmethod
    async def create_table_view(self, database_id: str, name: str) -> NotionView:
        """Create a table view.

        Method: BROWSER (view creation is UI-only)
        Mutates: true
        Requires Auth: true
        Idempotent: false
        Reconcilable: true

        Args:
            database_id: Target database
            name: View name

        Returns:
            Created NotionView
        """

    @abstractmethod
    async def create_board_view(
        self, database_id: str, name: str, group_by_property: str
    ) -> NotionView:
        """Create a board (kanban) view.

        Method: BROWSER (view creation is UI-only)
        Mutates: true
        Requires Auth: true
        Idempotent: false
        Reconcilable: true

        Args:
            database_id: Target database
            name: View name
            group_by_property: Property to group cards by

        Returns:
            Created NotionView
        """

    @abstractmethod
    async def set_view_title_visibility(self, view_id: str, visible: bool) -> NotionView:
        """Set whether view title is visible.

        Method: BROWSER (view settings UI-only)
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            view_id: Target view
            visible: Show or hide title

        Returns:
            Updated NotionView
        """

    @abstractmethod
    async def add_child_page(self, parent_page_id: str, title: str) -> NotionPage:
        """Add a child page to a parent page.

        Method: DIRECT_API (POST /v1/pages with parent page_id)
        Mutates: true
        Requires Auth: true
        Idempotent: false (check existing children before retry)
        Reconcilable: true

        Args:
            parent_page_id: Parent page
            title: Child page title

        Returns:
            Created NotionPage
        """

    @abstractmethod
    async def publish_page(self, page_id: str) -> NotionPage:
        """Publish page to web (share to web).

        Method: BROWSER (share settings UI, no API)
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            page_id: Page to publish

        Returns:
            Updated NotionPage with public_url
        """

    @abstractmethod
    async def set_duplicate_as_template(self, page_id: str, enabled: bool) -> NotionPage:
        """Set "Duplicate as template" page setting.

        Method: BROWSER (page settings UI, no API)
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            page_id: Page to update
            enabled: Enable or disable

        Returns:
            Updated NotionPage
        """

    @abstractmethod
    async def set_search_indexing(self, page_id: str, enabled: bool) -> NotionPage:
        """Set "Allow search engines to index" page setting.

        Method: BROWSER (page settings UI, no API)
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            page_id: Page to update
            enabled: Enable or disable search indexing

        Returns:
            Updated NotionPage
        """

    @abstractmethod
    async def get_public_url(self, page_id: str) -> str | None:
        """Get public URL if page is published.

        Method: COMBINED (API returns URL; browser verifies stranger access)
        Mutates: false
        Requires Auth: true (for API query)
        Idempotent: true
        Reconcilable: N/A

        Args:
            page_id: Page to check

        Returns:
            Public URL if published, None if not published
        """

    @abstractmethod
    async def unpublish_page(self, page_id: str) -> NotionPage:
        """Unpublish page (disable share to web).

        Method: BROWSER (share settings UI, no API)
        Mutates: true
        Requires Auth: true
        Idempotent: true
        Reconcilable: true

        Args:
            page_id: Page to unpublish

        Returns:
            Updated NotionPage with public_url=None
        """

    @abstractmethod
    async def inspect_page(self, page_id: str) -> NotionPage:
        """Get page metadata and content.

        Method: DIRECT_API
        Mutates: false
        Requires Auth: true
        Idempotent: true
        Reconcilable: N/A

        Args:
            page_id: Page to inspect

        Returns:
            NotionPage with metadata + properties
        """

    @abstractmethod
    async def inspect_database(self, database_id: str) -> NotionDatabase:
        """Get database schema.

        Method: DIRECT_API
        Mutates: false
        Requires Auth: true
        Idempotent: true
        Reconcilable: N/A

        Args:
            database_id: Database to inspect

        Returns:
            NotionDatabase with schema (properties)
        """

    @abstractmethod
    async def verify_stranger_access(self, public_url: str) -> bool:
        """Verify public URL is accessible to strangers (logged-out users).

        Method: BROWSER (logged-out browser)
        Mutates: false
        Requires Auth: false
        Idempotent: true
        Reconcilable: N/A

        Args:
            public_url: Public URL to verify

        Returns:
            True if accessible (200), False otherwise
        """
