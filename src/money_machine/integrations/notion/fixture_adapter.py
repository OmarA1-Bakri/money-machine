"""Fixture Notion adapter — in-memory stub for testing.

Provides a testable NotionAdapter implementation that maintains ephemeral state
in memory. Suitable for unit tests and Session 07 E2E test scaffolding.

NOT suitable for production or live Notion integration.
"""

import uuid
from datetime import UTC, datetime
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


class FixtureNotionAdapter(NotionAdapter):
    """In-memory Notion adapter for testing.

    State is ephemeral and resets between test runs. Operations return typed
    domain objects with generated IDs. Suitable for unit tests; does not persist
    to database or call live Notion APIs.
    """

    def __init__(self) -> None:
        """Initialize empty in-memory state."""
        self.workspaces: dict[str, NotionWorkspace] = {}
        self.pages: dict[str, NotionPage] = {}
        self.databases: dict[str, NotionDatabase] = {}
        self.blocks: dict[str, NotionTextBlock | NotionCalloutBlock] = {}
        self.views: dict[str, NotionView] = {}
        self.linked_views: dict[str, NotionLinkedView] = {}

        # Seed one default workspace for convenience
        default_workspace = NotionWorkspace(
            id="ws_default",
            name="Fixture Workspace",
            owner_user_id="user_fixture",
            icon="🏠",
        )
        self.workspaces[default_workspace.id] = default_workspace

    def _generate_id(self, prefix: str = "obj") -> str:
        """Generate a unique object ID."""
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    async def connection_status(self) -> dict[str, bool | str | int]:
        """Check connection status (always connected in fixture)."""
        return {
            "connected": True,
            "user_id": "user_fixture",
            "workspace_count": len(self.workspaces),
        }

    async def workspace_discovery(self) -> list[NotionWorkspace]:
        """List accessible workspaces."""
        return list(self.workspaces.values())

    async def create_page(
        self,
        title: str,
        parent_id: str | None = None,
        parent_type: str = "workspace",
        icon: str | None = None,
        cover: str | None = None,
    ) -> NotionPage:
        """Create a new page."""
        page_id = self._generate_id("page")
        now = datetime.now(UTC)

        page = NotionPage(
            id=page_id,
            title=title,
            parent_id=parent_id or "ws_default",
            parent_type=parent_type,
            icon=icon,
            cover=cover,
            created_at=now,
            updated_at=now,
        )
        self.pages[page_id] = page
        return page

    async def duplicate_page(self, page_id: str) -> NotionPage:
        """Duplicate an existing page."""
        source = self.pages.get(page_id)
        if not source:
            raise ValueError(f"Page {page_id} not found")

        new_id = self._generate_id("page")
        now = datetime.now(UTC)

        duplicate = NotionPage(
            id=new_id,
            title=f"{source.title} (Copy)",
            parent_id=source.parent_id,
            parent_type=source.parent_type,
            icon=source.icon,
            cover=source.cover,
            is_published=False,  # Duplicates are unpublished by default
            duplicate_as_template=source.duplicate_as_template,
            search_indexing=source.search_indexing,
            created_at=now,
            updated_at=now,
            properties=dict(source.properties),  # Shallow copy
        )
        self.pages[new_id] = duplicate
        return duplicate

    async def rename_page(self, page_id: str, new_title: str) -> NotionPage:
        """Rename a page."""
        page = self.pages.get(page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")

        page.title = new_title
        page.updated_at = datetime.now(UTC)
        return page

    async def move_page(
        self, page_id: str, new_parent_id: str, new_parent_type: str = "workspace"
    ) -> NotionPage:
        """Move a page to a new parent."""
        page = self.pages.get(page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")

        page.parent_id = new_parent_id
        page.parent_type = new_parent_type
        page.updated_at = datetime.now(UTC)
        return page

    async def set_icon(self, page_id: str, icon: str) -> NotionPage:
        """Set page icon."""
        page = self.pages.get(page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")

        page.icon = icon
        page.updated_at = datetime.now(UTC)
        return page

    async def set_cover(self, page_id: str, cover_url: str) -> NotionPage:
        """Set page cover image."""
        page = self.pages.get(page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")

        page.cover = cover_url
        page.updated_at = datetime.now(UTC)
        return page

    async def add_text_block(self, page_id: str, content: str) -> NotionTextBlock:
        """Append a text block to a page."""
        if page_id not in self.pages:
            raise ValueError(f"Page {page_id} not found")

        block_id = self._generate_id("block")
        block = NotionTextBlock(
            id=block_id,
            type="paragraph",
            parent_id=page_id,
            content=content,
            created_at=datetime.now(UTC),
        )
        self.blocks[block_id] = block
        return block

    async def add_callout_block(
        self, page_id: str, content: str, icon: str = "💡"
    ) -> NotionCalloutBlock:
        """Append a callout block to a page."""
        if page_id not in self.pages:
            raise ValueError(f"Page {page_id} not found")

        block_id = self._generate_id("block")
        block = NotionCalloutBlock(
            id=block_id,
            type="callout",
            parent_id=page_id,
            content=content,
            icon=icon,
            created_at=datetime.now(UTC),
        )
        self.blocks[block_id] = block
        return block

    async def create_database(
        self,
        title: str,
        parent_id: str | None = None,
        parent_type: str = "workspace",
        icon: str | None = None,
        cover: str | None = None,
    ) -> NotionDatabase:
        """Create a new database."""
        db_id = self._generate_id("db")
        now = datetime.now(UTC)

        database = NotionDatabase(
            id=db_id,
            title=title,
            parent_id=parent_id or "ws_default",
            parent_type=parent_type,
            icon=icon,
            cover=cover,
            properties=[],  # Empty schema initially
            created_at=now,
            updated_at=now,
        )
        self.databases[db_id] = database
        return database

    async def add_property(
        self, database_id: str, name: str, property_type: str, config: dict[str, Any]
    ) -> NotionDatabaseProperty:
        """Add a property to a database."""
        database = self.databases.get(database_id)
        if not database:
            raise ValueError(f"Database {database_id} not found")

        # Check if property already exists (idempotent update)
        existing = next((p for p in database.properties if p.name == name), None)
        if existing:
            existing.type = property_type
            existing.config = config
            database.updated_at = datetime.now(UTC)
            return existing

        # Create new property
        prop_id = self._generate_id("prop")
        prop = NotionDatabaseProperty(id=prop_id, name=name, type=property_type, config=config)
        database.properties.append(prop)
        database.updated_at = datetime.now(UTC)
        return prop

    async def create_relation(
        self,
        database_id: str,
        name: str,
        target_database_id: str,
        synced_property_name: str | None = None,
    ) -> NotionRelation:
        """Create a relation property."""
        database = self.databases.get(database_id)
        if not database:
            raise ValueError(f"Database {database_id} not found")

        if target_database_id not in self.databases:
            raise ValueError(f"Target database {target_database_id} not found")

        relation_id = self._generate_id("rel")
        relation = NotionRelation(
            id=relation_id,
            name=name,
            database_id=target_database_id,
            synced_property_name=synced_property_name,
        )

        # Add as property to database
        prop = NotionDatabaseProperty(
            id=relation_id, name=name, type="relation", config={"relation": relation}
        )
        database.properties.append(prop)
        database.updated_at = datetime.now(UTC)

        return relation

    async def create_rollup(
        self,
        database_id: str,
        name: str,
        relation_property_id: str,
        rollup_property_id: str,
        function: str,
    ) -> NotionRollup:
        """Create a rollup property."""
        database = self.databases.get(database_id)
        if not database:
            raise ValueError(f"Database {database_id} not found")

        rollup_id = self._generate_id("rollup")
        rollup = NotionRollup(
            id=rollup_id,
            name=name,
            relation_property_id=relation_property_id,
            rollup_property_id=rollup_property_id,
            function=function,
        )

        # Add as property to database
        prop = NotionDatabaseProperty(
            id=rollup_id, name=name, type="rollup", config={"rollup": rollup}
        )
        database.properties.append(prop)
        database.updated_at = datetime.now(UTC)

        return rollup

    async def create_formula(self, database_id: str, name: str, expression: str) -> NotionFormula:
        """Create a formula property."""
        database = self.databases.get(database_id)
        if not database:
            raise ValueError(f"Database {database_id} not found")

        formula_id = self._generate_id("formula")
        formula = NotionFormula(id=formula_id, name=name, expression=expression)

        # Add as property to database
        prop = NotionDatabaseProperty(
            id=formula_id, name=name, type="formula", config={"formula": formula}
        )
        database.properties.append(prop)
        database.updated_at = datetime.now(UTC)

        return formula

    async def create_linked_view(
        self,
        source_database_id: str,
        parent_page_id: str,
        view_type: str = "table",
    ) -> NotionLinkedView:
        """Create a linked database view."""
        if source_database_id not in self.databases:
            raise ValueError(f"Source database {source_database_id} not found")

        if parent_page_id not in self.pages:
            raise ValueError(f"Parent page {parent_page_id} not found")

        linked_view_id = self._generate_id("linked_view")
        linked_view = NotionLinkedView(
            id=linked_view_id,
            source_database_id=source_database_id,
            parent_page_id=parent_page_id,
            view_type=view_type,
        )
        self.linked_views[linked_view_id] = linked_view
        return linked_view

    async def add_filter(
        self, database_id: str, view_id: str, filter_spec: NotionFilter
    ) -> dict[str, Any]:
        """Add a filter to a view."""
        if database_id not in self.databases:
            raise ValueError(f"Database {database_id} not found")

        # Fixture returns stub config
        return {
            "view_id": view_id,
            "filter": {
                "property": filter_spec.property,
                "condition": filter_spec.condition,
                "value": filter_spec.value,
            },
        }

    async def add_sort(
        self, database_id: str, view_id: str, sort_spec: NotionSort
    ) -> dict[str, Any]:
        """Add a sort to a view."""
        if database_id not in self.databases:
            raise ValueError(f"Database {database_id} not found")

        # Fixture returns stub config
        return {
            "view_id": view_id,
            "sort": {
                "property": sort_spec.property,
                "direction": sort_spec.direction,
            },
        }

    async def create_calendar_view(
        self, database_id: str, name: str, date_property: str
    ) -> NotionView:
        """Create a calendar view."""
        if database_id not in self.databases:
            raise ValueError(f"Database {database_id} not found")

        view_id = self._generate_id("view")
        view = NotionView(id=view_id, database_id=database_id, name=name, type="calendar")
        self.views[view_id] = view
        return view

    async def create_table_view(self, database_id: str, name: str) -> NotionView:
        """Create a table view."""
        if database_id not in self.databases:
            raise ValueError(f"Database {database_id} not found")

        view_id = self._generate_id("view")
        view = NotionView(id=view_id, database_id=database_id, name=name, type="table")
        self.views[view_id] = view
        return view

    async def create_board_view(
        self, database_id: str, name: str, group_by_property: str
    ) -> NotionView:
        """Create a board view."""
        if database_id not in self.databases:
            raise ValueError(f"Database {database_id} not found")

        view_id = self._generate_id("view")
        view = NotionView(id=view_id, database_id=database_id, name=name, type="board")
        self.views[view_id] = view
        return view

    async def set_view_title_visibility(
        self, database_id: str, view_id: str, visible: bool
    ) -> NotionView:
        """Set view title visibility."""
        # Fixture adapter uses short IDs (12 hex) with prefixes
        # Real IDs are 32 hex (with or without dashes, with or without prefix)
        # Validate that the database_id is at least hex after normalization

        # Normalize ID: strip prefix, dashes, lowercase
        normalized_input = database_id.removeprefix("db_").replace("-", "").lower()

        # Validate it's not empty and contains only hex characters
        if not normalized_input or not all(c in "0123456789abcdef" for c in normalized_input):
            raise ValueError(f"Invalid database_id: {database_id}")

        view = self.views.get(view_id)
        if not view:
            raise ValueError(f"View {view_id} not found")

        # Normalize view's database_id for comparison
        normalized_view_db = view.database_id.removeprefix("db_").replace("-", "").lower()

        # Validate that the view belongs to the given database
        if normalized_view_db != normalized_input:
            raise ValueError(f"View {view_id} does not belong to database {database_id}")

        view.title_visible = visible
        return view

    async def add_child_page(self, parent_page_id: str, title: str) -> NotionPage:
        """Add a child page."""
        if parent_page_id not in self.pages:
            raise ValueError(f"Parent page {parent_page_id} not found")

        return await self.create_page(title=title, parent_id=parent_page_id, parent_type="page_id")

    async def publish_page(self, page_id: str) -> NotionPage:
        """Publish page to web."""
        page = self.pages.get(page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")

        page.is_published = True
        page.public_url = f"https://fixture.notion.site/{page_id}"
        page.updated_at = datetime.now(UTC)
        return page

    async def set_duplicate_as_template(self, page_id: str, enabled: bool) -> NotionPage:
        """Set duplicate-as-template setting."""
        page = self.pages.get(page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")

        page.duplicate_as_template = enabled
        page.updated_at = datetime.now(UTC)
        return page

    async def set_search_indexing(self, page_id: str, enabled: bool) -> NotionPage:
        """Set search indexing setting."""
        page = self.pages.get(page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")

        page.search_indexing = enabled
        page.updated_at = datetime.now(UTC)
        return page

    async def get_public_url(self, page_id: str) -> str | None:
        """Get public URL if published."""
        page = self.pages.get(page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")

        return page.public_url if page.is_published else None

    async def unpublish_page(self, page_id: str) -> NotionPage:
        """Unpublish page."""
        page = self.pages.get(page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")

        page.is_published = False
        page.public_url = None
        page.updated_at = datetime.now(UTC)
        return page

    async def inspect_page(self, page_id: str) -> NotionPage:
        """Get page metadata."""
        page = self.pages.get(page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")

        return page

    async def inspect_database(self, database_id: str) -> NotionDatabase:
        """Get database schema."""
        database = self.databases.get(database_id)
        if not database:
            raise ValueError(f"Database {database_id} not found")

        return database

    async def verify_stranger_access(self, public_url: str) -> bool:
        """Verify public URL is accessible.

        Fixture always returns True for URLs matching pattern.
        """
        return public_url.startswith("https://") and "notion.site" in public_url
