"""Combined Notion adapter stub — deferred to Wave 3+.

Real implementation will combine API + browser for create-verify patterns.
Wave 1 raises NotImplementedError to mark deferred boundary.
"""

from typing import Any

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


class CombinedNotionAdapter(NotionAdapter):
    """Notion combined adapter (API + browser) — Wave 3+ implementation.

    Will combine API and browser for:
    - get_public_url: API returns URL, browser verifies stranger access
    - Future: API create + browser verify patterns
    """

    async def connection_status(self) -> dict[str, bool | str | int]:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def workspace_discovery(self) -> list[NotionWorkspace]:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
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
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def duplicate_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def rename_page(self, page_id: str, new_title: str) -> NotionPage:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def move_page(
        self, page_id: str, new_parent_id: str, new_parent_type: str = "workspace"
    ) -> NotionPage:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def set_icon(self, page_id: str, icon: str) -> NotionPage:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def set_cover(self, page_id: str, cover_url: str) -> NotionPage:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def add_text_block(self, page_id: str, content: str) -> NotionTextBlock:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def add_callout_block(
        self, page_id: str, content: str, icon: str = "💡"
    ) -> NotionCalloutBlock:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
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
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def add_property(
        self, database_id: str, name: str, property_type: str, config: dict[str, Any]
    ) -> NotionDatabaseProperty:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def create_relation(
        self,
        database_id: str,
        name: str,
        target_database_id: str,
        synced_property_name: str | None = None,
    ) -> NotionRelation:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
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
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def create_formula(self, database_id: str, name: str, expression: str) -> NotionFormula:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def create_linked_view(
        self,
        source_database_id: str,
        parent_page_id: str,
        view_type: str = "table",
    ) -> NotionLinkedView:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def add_filter(
        self, database_id: str, view_id: str, filter_spec: NotionFilter
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def add_sort(
        self, database_id: str, view_id: str, sort_spec: NotionSort
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def create_calendar_view(
        self, database_id: str, name: str, date_property: str
    ) -> NotionView:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def create_table_view(self, database_id: str, name: str) -> NotionView:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def create_board_view(
        self, database_id: str, name: str, group_by_property: str
    ) -> NotionView:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def set_view_title_visibility(self, view_id: str, visible: bool) -> NotionView:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def add_child_page(self, parent_page_id: str, title: str) -> NotionPage:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def publish_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def set_duplicate_as_template(self, page_id: str, enabled: bool) -> NotionPage:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def set_search_indexing(self, page_id: str, enabled: bool) -> NotionPage:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def get_public_url(self, page_id: str) -> str | None:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def unpublish_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def inspect_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def inspect_database(self, database_id: str) -> NotionDatabase:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )

    async def verify_stranger_access(self, public_url: str) -> bool:
        raise NotImplementedError(
            "Real combined adapter deferred to Session 06 Wave 3+. "
            "Use FixtureNotionAdapter for testing."
        )
