"""Browser Notion adapter stub — deferred to Wave 2+.

Real implementation will use Playwright for UI-only Notion operations.
Wave 1 raises NotImplementedError to mark deferred boundary.
"""

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


class BrowserNotionAdapter(NotionAdapter):
    """Notion browser adapter (BROWSER method) — Wave 2+ implementation.

    Will use Playwright for UI-only Notion operations:
    - Page duplication
    - Formula editing
    - View creation (calendar, table, board)
    - Publishing settings
    - Linked database views
    - Stranger access verification (logged-out browser)
    """

    async def connection_status(self) -> dict[str, bool]:
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

    async def duplicate_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "Real browser adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
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
        self, database_id: str, name: str, property_type: str, config: dict
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
        raise NotImplementedError(
            "Real browser adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def create_linked_view(
        self,
        source_database_id: str,
        parent_page_id: str,
        view_type: str = "table",
    ) -> NotionLinkedView:
        raise NotImplementedError(
            "Real browser adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def add_filter(self, database_id: str, view_id: str, filter_spec: NotionFilter) -> dict:
        raise NotImplementedError(
            "add_filter uses API method, not BROWSER. Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def add_sort(self, database_id: str, view_id: str, sort_spec: NotionSort) -> dict:
        raise NotImplementedError(
            "add_sort uses API method, not BROWSER. Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def create_calendar_view(
        self, database_id: str, name: str, date_property: str
    ) -> NotionView:
        raise NotImplementedError(
            "Real browser adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def create_table_view(self, database_id: str, name: str) -> NotionView:
        raise NotImplementedError(
            "Real browser adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def create_board_view(
        self, database_id: str, name: str, group_by_property: str
    ) -> NotionView:
        raise NotImplementedError(
            "Real browser adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def set_view_title_visibility(self, view_id: str, visible: bool) -> NotionView:
        raise NotImplementedError(
            "Real browser adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def add_child_page(self, parent_page_id: str, title: str) -> NotionPage:
        raise NotImplementedError(
            "add_child_page uses API method, not BROWSER. "
            "Use APINotionAdapter or FixtureNotionAdapter."
        )

    async def publish_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "Real browser adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def set_duplicate_as_template(self, page_id: str, enabled: bool) -> NotionPage:
        raise NotImplementedError(
            "Real browser adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def set_search_indexing(self, page_id: str, enabled: bool) -> NotionPage:
        raise NotImplementedError(
            "Real browser adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def get_public_url(self, page_id: str) -> str | None:
        raise NotImplementedError(
            "get_public_url uses COMBINED method (API + browser). "
            "Use CombinedNotionAdapter or FixtureNotionAdapter."
        )

    async def unpublish_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "Real browser adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
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
        raise NotImplementedError(
            "Real browser adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )
