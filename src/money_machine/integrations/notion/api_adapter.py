"""API Notion adapter — real Notion Official API integration via notion-client.

Implements DIRECT_API operations using the Notion Official API v1. This adapter
handles connection status, workspace discovery, page/database CRUD, properties,
relations, rollups, and inspection operations.

BROWSER and COMBINED operations remain as stubs (Wave 3+).
"""

import os
from datetime import UTC, datetime
from typing import Any

from notion_client import AsyncClient

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
    """Notion API adapter (DIRECT_API method) — Wave 2 implementation.

    Uses Notion Official API v1 via notion-client Python SDK for:
    - Connection status
    - Workspace discovery
    - Page/database CRUD
    - Properties, relations, rollups
    - Block operations (text, callout)
    - Inspection operations

    NOT suitable for:
    - Formula editing (API read-only)
    - View creation (UI-only)
    - Publishing settings (UI-only)
    - Browser-based operations

    Auth: Requires NOTION_API_TOKEN environment variable.
    """

    def __init__(self, api_token: str | None = None) -> None:
        """Initialize API adapter with Notion client.

        Args:
            api_token: Notion integration token. If None, reads from NOTION_API_TOKEN env var.
                      If still None, defers token validation until first method call.

        Note:
            Token can be None at initialization for testing/routing purposes, but actual
            API calls will fail if no token is available.
        """
        token = api_token or os.getenv("NOTION_API_TOKEN")

        # Create client even if token is None to allow router initialization
        # Methods will fail with appropriate error if token is actually needed
        self.client = AsyncClient(auth=token or "")
        self._token_available = bool(token)

    async def connection_status(self) -> dict[str, bool | str | int]:
        """Check API token validity via /v1/users/me endpoint."""
        try:
            me = await self.client.users.me()
            user_id = me.get("id")

            # Try to search workspaces to verify access
            await self.client.search(filter={"property": "object", "value": "page"})
            workspace_count = 1  # At least one workspace if search succeeds

            return {
                "connected": True,
                "user_id": user_id or "",
                "workspace_count": workspace_count,
            }
        except Exception:
            # Catch any error (APIResponseError, HTTPResponseError, etc.)
            return {
                "connected": False,
                "user_id": "",
                "workspace_count": 0,
            }

    async def workspace_discovery(self) -> list[NotionWorkspace]:
        """List accessible workspaces via search endpoint."""
        # Note: Notion API doesn't have a direct "list workspaces" endpoint.
        # We use the bot's user info and create a synthetic workspace entry.
        try:
            me = await self.client.users.me()
            bot_name = me.get("name", "Unknown Bot")

            # Create a synthetic workspace representing the bot's access scope
            workspace = NotionWorkspace(
                id=me.get("id", "unknown"),
                name=f"{bot_name}'s Workspace",
                owner_user_id=me.get("id"),
            )

            return [workspace]
        except Exception as e:
            raise ValueError(f"Failed to discover workspaces: {e}") from e

    async def create_page(
        self,
        title: str,
        parent_id: str | None = None,
        parent_type: str = "workspace",
        icon: str | None = None,
        cover: str | None = None,
    ) -> NotionPage:
        """Create a new page via POST /v1/pages."""
        parent: dict[str, Any]
        if parent_id:
            if parent_type == "page_id":
                parent = {"type": "page_id", "page_id": parent_id}
            elif parent_type == "database_id":
                parent = {"type": "database_id", "database_id": parent_id}
            else:
                parent = {"type": "workspace", "workspace": True}
        else:
            parent = {"type": "workspace", "workspace": True}

        properties: dict[str, Any] = {"title": {"title": [{"text": {"content": title}}]}}

        page_data: dict[str, Any] = {"parent": parent, "properties": properties}

        if icon:
            if icon.startswith("http"):
                page_data["icon"] = {"type": "external", "external": {"url": icon}}
            else:
                page_data["icon"] = {"type": "emoji", "emoji": icon}

        if cover:
            page_data["cover"] = {"type": "external", "external": {"url": cover}}

        result = await self.client.pages.create(**page_data)
        return self._map_page(result)

    def _map_page(self, api_page: dict[str, Any]) -> NotionPage:
        """Map Notion API page response to domain model."""
        page_id = api_page["id"]
        title_prop = api_page.get("properties", {}).get("title", {})
        title_array = title_prop.get("title", [])
        title = title_array[0]["plain_text"] if title_array else "Untitled"

        parent = api_page.get("parent", {})
        parent_type = parent.get("type", "workspace")
        parent_id = parent.get(f"{parent_type}")

        icon_data = api_page.get("icon")
        icon = None
        if icon_data:
            if icon_data.get("type") == "emoji":
                icon = icon_data.get("emoji")
            elif icon_data.get("type") == "external":
                icon = icon_data.get("external", {}).get("url")

        cover_data = api_page.get("cover")
        cover = cover_data.get("external", {}).get("url") if cover_data else None

        created_time = api_page.get("created_time")
        updated_time = api_page.get("last_edited_time")

        return NotionPage(
            id=page_id,
            title=title,
            parent_id=str(parent_id) if parent_id and parent_id is not True else None,
            parent_type=parent_type,
            icon=icon,
            cover=cover,
            public_url=api_page.get("public_url"),
            is_published=bool(api_page.get("public_url")),
            created_at=(
                datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                if created_time
                else datetime.now(UTC)
            ),
            updated_at=(
                datetime.fromisoformat(updated_time.replace("Z", "+00:00"))
                if updated_time
                else datetime.now(UTC)
            ),
            properties=api_page.get("properties", {}),
        )

    async def duplicate_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "duplicate_page requires BROWSER method (UI-only, no API). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def rename_page(self, page_id: str, new_title: str) -> NotionPage:
        """Rename a page via PATCH /v1/pages/{id}."""
        properties = {"title": {"title": [{"text": {"content": new_title}}]}}

        result = await self.client.pages.update(page_id=page_id, properties=properties)
        return self._map_page(result)

    async def move_page(
        self, page_id: str, new_parent_id: str, new_parent_type: str = "workspace"
    ) -> NotionPage:
        """Move a page to a new parent via PATCH /v1/pages/{id}."""
        parent: dict[str, Any]
        if new_parent_type == "page_id":
            parent = {"type": "page_id", "page_id": new_parent_id}
        elif new_parent_type == "database_id":
            parent = {"type": "database_id", "database_id": new_parent_id}
        else:
            parent = {"type": "workspace", "workspace": True}

        result = await self.client.pages.update(page_id=page_id, parent=parent)
        return self._map_page(result)

    async def set_icon(self, page_id: str, icon: str) -> NotionPage:
        """Set page icon via PATCH /v1/pages/{id}."""
        icon_data: dict[str, Any]
        if icon.startswith("http"):
            icon_data = {"type": "external", "external": {"url": icon}}
        else:
            icon_data = {"type": "emoji", "emoji": icon}

        result = await self.client.pages.update(page_id=page_id, icon=icon_data)
        return self._map_page(result)

    async def set_cover(self, page_id: str, cover_url: str) -> NotionPage:
        """Set page cover via PATCH /v1/pages/{id}."""
        cover_data = {"type": "external", "external": {"url": cover_url}}

        result = await self.client.pages.update(page_id=page_id, cover=cover_data)
        return self._map_page(result)

    async def add_text_block(self, page_id: str, content: str) -> NotionTextBlock:
        """Append a text block via PATCH /v1/blocks/{id}/children."""
        block_data = {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": content}}]},
        }

        result = await self.client.blocks.children.append(block_id=page_id, children=[block_data])

        # Extract the created block from results
        if result.get("results"):
            block = result["results"][0]
            return NotionTextBlock(
                id=block["id"],
                type="paragraph",
                parent_id=page_id,
                content=content,
                created_at=datetime.fromisoformat(block["created_time"].replace("Z", "+00:00"))
                if block.get("created_time")
                else datetime.now(UTC),
            )

        # Fallback if results not in expected format
        raise ValueError("Failed to create text block")

    async def add_callout_block(
        self, page_id: str, content: str, icon: str = "💡"
    ) -> NotionCalloutBlock:
        """Append a callout block via PATCH /v1/blocks/{id}/children."""
        block_data = {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"text": {"content": content}}],
                "icon": {"type": "emoji", "emoji": icon},
            },
        }

        result = await self.client.blocks.children.append(block_id=page_id, children=[block_data])

        # Extract the created block from results
        if result.get("results"):
            block = result["results"][0]
            return NotionCalloutBlock(
                id=block["id"],
                type="callout",
                parent_id=page_id,
                content=content,
                icon=icon,
                created_at=datetime.fromisoformat(block["created_time"].replace("Z", "+00:00"))
                if block.get("created_time")
                else datetime.now(UTC),
            )

        raise ValueError("Failed to create callout block")

    async def create_database(
        self,
        title: str,
        parent_id: str | None = None,
        parent_type: str = "workspace",
        icon: str | None = None,
        cover: str | None = None,
    ) -> NotionDatabase:
        """Create a database via POST /v1/databases."""
        parent: dict[str, Any]
        if parent_id:
            if parent_type == "page_id":
                parent = {"type": "page_id", "page_id": parent_id}
            else:
                parent = {"type": "workspace", "workspace": True}
        else:
            parent = {"type": "workspace", "workspace": True}

        # Create with a default Title property
        properties: dict[str, Any] = {"Name": {"title": {}}}

        db_data: dict[str, Any] = {
            "parent": parent,
            "title": [{"text": {"content": title}}],
            "properties": properties,
        }

        if icon:
            if icon.startswith("http"):
                db_data["icon"] = {"type": "external", "external": {"url": icon}}
            else:
                db_data["icon"] = {"type": "emoji", "emoji": icon}

        if cover:
            db_data["cover"] = {"type": "external", "external": {"url": cover}}

        result = await self.client.databases.create(**db_data)
        return self._map_database(result)

    def _map_database(self, api_db: dict[str, Any]) -> NotionDatabase:
        """Map Notion API database response to domain model."""
        db_id = api_db["id"]

        title_array = api_db.get("title", [])
        title = title_array[0]["plain_text"] if title_array else "Untitled"

        parent = api_db.get("parent", {})
        parent_type = parent.get("type", "workspace")
        parent_id = parent.get(f"{parent_type}")

        icon_data = api_db.get("icon")
        icon = None
        if icon_data:
            if icon_data.get("type") == "emoji":
                icon = icon_data.get("emoji")
            elif icon_data.get("type") == "external":
                icon = icon_data.get("external", {}).get("url")

        cover_data = api_db.get("cover")
        cover = cover_data.get("external", {}).get("url") if cover_data else None

        # Map properties
        properties_data = api_db.get("properties", {})
        properties = [
            NotionDatabaseProperty(
                id=prop_id,
                name=name,
                type=prop_data.get("type", "unknown"),
                config=prop_data,
            )
            for name, prop_data in properties_data.items()
            for prop_id in [prop_data.get("id", name)]
        ]

        created_time = api_db.get("created_time")
        updated_time = api_db.get("last_edited_time")

        return NotionDatabase(
            id=db_id,
            title=title,
            parent_id=str(parent_id) if parent_id and parent_id is not True else None,
            parent_type=parent_type,
            icon=icon,
            cover=cover,
            properties=properties,
            created_at=(
                datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                if created_time
                else datetime.now(UTC)
            ),
            updated_at=(
                datetime.fromisoformat(updated_time.replace("Z", "+00:00"))
                if updated_time
                else datetime.now(UTC)
            ),
        )

    async def add_property(
        self, database_id: str, name: str, property_type: str, config: dict[str, Any]
    ) -> NotionDatabaseProperty:
        """Add/update a property via PATCH /v1/databases/{id}."""
        # Build property definition based on type
        prop_def: dict[str, Any] = {property_type: config or {}}

        properties = {name: prop_def}

        result = await self.client.databases.update(database_id=database_id, properties=properties)

        # Find the property we just added/updated
        props_data = result.get("properties", {})
        if name in props_data:
            prop_data = props_data[name]
            return NotionDatabaseProperty(
                id=prop_data.get("id", name),
                name=name,
                type=property_type,
                config=config,
            )

        raise ValueError(f"Failed to add property {name}")

    async def create_relation(
        self,
        database_id: str,
        name: str,
        target_database_id: str,
        synced_property_name: str | None = None,
    ) -> NotionRelation:
        """Create a relation property via PATCH /v1/databases/{id}."""
        relation_config: dict[str, Any] = {
            "database_id": target_database_id,
        }

        if synced_property_name:
            relation_config["synced_property_name"] = synced_property_name

        properties = {name: {"relation": relation_config}}

        result = await self.client.databases.update(database_id=database_id, properties=properties)

        # Extract relation info
        props_data = result.get("properties", {})
        if name in props_data:
            return NotionRelation(
                id=props_data[name].get("id", name),
                name=name,
                database_id=target_database_id,
                synced_property_name=synced_property_name,
            )

        raise ValueError(f"Failed to create relation {name}")

    async def create_rollup(
        self,
        database_id: str,
        name: str,
        relation_property_id: str,
        rollup_property_id: str,
        function: str,
    ) -> NotionRollup:
        """Create a rollup property via PATCH /v1/databases/{id}."""
        rollup_config = {
            "relation_property_name": relation_property_id,
            "rollup_property_name": rollup_property_id,
            "function": function,
        }

        properties = {name: {"rollup": rollup_config}}

        result = await self.client.databases.update(database_id=database_id, properties=properties)

        # Extract rollup info
        props_data = result.get("properties", {})
        if name in props_data:
            return NotionRollup(
                id=props_data[name].get("id", name),
                name=name,
                relation_property_id=relation_property_id,
                rollup_property_id=rollup_property_id,
                function=function,
            )

        raise ValueError(f"Failed to create rollup {name}")

    async def create_formula(self, database_id: str, name: str, expression: str) -> NotionFormula:
        raise NotImplementedError(
            "create_formula requires BROWSER method (formula editor UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def create_linked_view(
        self, source_database_id: str, parent_page_id: str, view_type: str = "table"
    ) -> NotionLinkedView:
        raise NotImplementedError(
            "create_linked_view requires BROWSER method (UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def add_filter(
        self, database_id: str, view_id: str, filter_spec: NotionFilter
    ) -> dict[str, Any]:
        """Add a filter to a database query (part of query API)."""
        # Note: Filters are part of query parameters, not persistent view config
        # Return a representation of the filter that can be used in queries
        return {
            "view_id": view_id,
            "filter": {
                "property": filter_spec.property,
                filter_spec.condition: filter_spec.value,
            },
        }

    async def add_sort(
        self, database_id: str, view_id: str, sort_spec: NotionSort
    ) -> dict[str, Any]:
        """Add a sort to a database query (part of query API)."""
        # Note: Sorts are part of query parameters, not persistent view config
        # Return a representation of the sort that can be used in queries
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
        raise NotImplementedError(
            "create_calendar_view requires BROWSER method (UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def create_table_view(self, database_id: str, name: str) -> NotionView:
        raise NotImplementedError(
            "create_table_view requires BROWSER method (UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def create_board_view(
        self, database_id: str, name: str, group_by_property: str
    ) -> NotionView:
        raise NotImplementedError(
            "create_board_view requires BROWSER method (UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def set_view_title_visibility(
        self, database_id: str, view_id: str, visible: bool
    ) -> NotionView:
        raise NotImplementedError(
            "set_view_title_visibility requires BROWSER method (UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def add_child_page(self, parent_page_id: str, title: str) -> NotionPage:
        """Add a child page via POST /v1/pages with parent page_id."""
        return await self.create_page(title=title, parent_id=parent_page_id, parent_type="page_id")

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
        """Get public URL via GET /v1/pages/{id} (COMBINED method placeholder)."""
        # API can return public_url if page is published
        # Browser verification deferred to Wave 3+
        result = await self.client.pages.retrieve(page_id=page_id)
        return result.get("public_url")

    async def unpublish_page(self, page_id: str) -> NotionPage:
        raise NotImplementedError(
            "unpublish_page requires BROWSER method (share settings UI-only). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )

    async def inspect_page(self, page_id: str) -> NotionPage:
        """Inspect a page via GET /v1/pages/{id}."""
        result = await self.client.pages.retrieve(page_id=page_id)
        return self._map_page(result)

    async def inspect_database(self, database_id: str) -> NotionDatabase:
        """Inspect a database via GET /v1/databases/{id}."""
        result = await self.client.databases.retrieve(database_id=database_id)
        return self._map_database(result)

    async def verify_stranger_access(self, public_url: str) -> bool:
        raise NotImplementedError(
            "verify_stranger_access requires BROWSER method (logged-out browser check). "
            "Deferred to Session 06 Wave 3+. Use FixtureNotionAdapter for testing."
        )
