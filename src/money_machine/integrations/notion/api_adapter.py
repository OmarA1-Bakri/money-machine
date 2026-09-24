"""API Notion adapter stub — deferred to Wave 2+.

Real implementation will use Notion Official API via notion-client Python SDK.
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


class APINotionAdapter(NotionAdapter):
    """Notion API adapter (DIRECT_API method) — Wave 2+ implementation.

    Will use Notion Official API v1 via notion-client Python SDK for:
    - Connection status
    - Workspace discovery
    - Page/database CRUD
    - Properties, relations, rollups
    - Inspection operations

    NOT suitable for:
    - Formula editing (API read-only)
    - View creation (UI-only)
    - Publishing settings (UI-only)
    """

    async def connection_status(self) -> dict[str, bool]:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def workspace_discovery(self) -> list[NotionWorkspace]:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def create_page(self, title: str, parent_id: str | None = None, parent_type: str = "workspace", icon: str | None = None, cover: str | None = None) -> NotionPage:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def duplicate_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "duplicate_page requires BROWSER method (UI-only, no API). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def rename_page(self, page_id: str, new_title: str) -> NotionPage:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def move_page(self, page_id: str, new_parent_id: str, new_parent_type: str = "workspace") -> NotionPage:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def set_icon(self, page_id: str, icon: str) -> NotionPage:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def set_cover(self, page_id: str, cover_url: str) -> NotionPage:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def add_text_block(self, page_id: str, content: str) -> NotionTextBlock:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def add_callout_block(self, page_id: str, content: str, icon: str = "💡") -> NotionCalloutBlock:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def create_database(self, title: str, parent_id: str | None = None, parent_type: str = "workspace", icon: str | None = None, cover: str | None = None) -> NotionDatabase:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def add_property(self, database_id: str, name: str, property_type: str, config: dict) -> NotionDatabaseProperty:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def create_relation(self, database_id: str, name: str, target_database_id: str, synced_property_name: str | None = None) -> NotionRelation:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def create_rollup(self, database_id: str, name: str, relation_property_id: str, rollup_property_id: str, function: str) -> NotionRollup:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def create_formula(self, database_id: str, name: str, expression: str) -> NotionFormula:
        raise NotImplementedError(
            "create_formula requires BROWSER method (formula editor UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def create_linked_view(self, source_database_id: str, parent_page_id: str, view_type: str = "table") -> NotionLinkedView:
        raise NotImplementedError(
            "create_linked_view requires BROWSER method (UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def add_filter(self, database_id: str, view_id: str, filter_spec: NotionFilter) -> dict:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def add_sort(self, database_id: str, view_id: str, sort_spec: NotionSort) -> dict:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def create_calendar_view(self, database_id: str, name: str, date_property: str) -> NotionView:
        raise NotImplementedError(
            "create_calendar_view requires BROWSER method (UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def create_table_view(self, database_id: str, name: str) -> NotionView:
        raise NotImplementedError(
            "create_table_view requires BROWSER method (UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def create_board_view(self, database_id: str, name: str, group_by_property: str) -> NotionView:
        raise NotImplementedError(
            "create_board_view requires BROWSER method (UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def set_view_title_visibility(self, view_id: str, visible: bool) -> NotionView:
        raise NotImplementedError(
            "set_view_title_visibility requires BROWSER method (UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def add_child_page(self, parent_page_id: str, title: str) -> NotionPage:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def publish_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "publish_page requires BROWSER method (share settings UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def set_duplicate_as_template(self, page_id: str, enabled: bool) -> NotionPage:
        raise NotImplementedError(
            "set_duplicate_as_template requires BROWSER method (UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def set_search_indexing(self, page_id: str, enabled: bool) -> NotionPage:
        raise NotImplementedError(
            "set_search_indexing requires BROWSER method (UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def get_public_url(self, page_id: str) -> str | None:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def unpublish_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "unpublish_page requires BROWSER method (share settings UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def inspect_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def inspect_database(self, database_id: str) -> NotionDatabase:
        raise NotImplementedError(
            "Real API adapter deferred to Session 06 Wave 2+. Use FixtureNotionAdapter for testing."
        )

    async def verify_stranger_access(self, public_url: str) -> bool:
        raise NotImplementedError(
            "verify_stranger_access requires BROWSER method (logged-out browser check). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )
