"""Unit tests for APINotionAdapter — mocked Notion API calls.

Tests DIRECT_API operations without live Notion API calls. All HTTP requests
are mocked using respx to avoid network calls and credentials in tests.
"""

import pytest
import respx
from httpx import Response

from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.domain import (
    NotionCalloutBlock,
    NotionDatabase,
    NotionDatabaseProperty,
    NotionPage,
    NotionRelation,
    NotionRollup,
    NotionTextBlock,
    NotionWorkspace,
)


@pytest.fixture
def api_adapter():
    """Create APINotionAdapter with test token."""
    return APINotionAdapter(api_token="test_secret_token")


@pytest.mark.asyncio
@respx.mock
async def test_connection_status_success(api_adapter):
    """connection_status returns connected=True when API responds."""
    # Mock GET /v1/users/me
    respx.get("https://api.notion.com/v1/users/me").mock(
        return_value=Response(200, json={"id": "user_123", "name": "Test Bot"})
    )

    # Mock POST /v1/search (for workspace count)
    respx.post("https://api.notion.com/v1/search").mock(
        return_value=Response(200, json={"results": []})
    )

    result = await api_adapter.connection_status()

    assert result["connected"] is True
    assert result["user_id"] == "user_123"
    assert result["workspace_count"] == 1


@pytest.mark.asyncio
@respx.mock
async def test_connection_status_failure(api_adapter):
    """connection_status returns connected=False on API error."""
    # Mock API failure
    respx.get("https://api.notion.com/v1/users/me").mock(
        return_value=Response(401, json={"message": "Unauthorized"})
    )

    result = await api_adapter.connection_status()

    assert result["connected"] is False
    assert result["user_id"] == ""
    assert result["workspace_count"] == 0


@pytest.mark.asyncio
@respx.mock
async def test_workspace_discovery(api_adapter):
    """workspace_discovery returns workspace list."""
    respx.get("https://api.notion.com/v1/users/me").mock(
        return_value=Response(200, json={"id": "user_123", "name": "Test Bot"})
    )

    workspaces = await api_adapter.workspace_discovery()

    assert len(workspaces) == 1
    assert isinstance(workspaces[0], NotionWorkspace)
    assert workspaces[0].owner_user_id == "user_123"


@pytest.mark.asyncio
@respx.mock
async def test_create_page(api_adapter):
    """create_page creates a new page via API."""
    mock_response = {
        "id": "page_123",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:00:00.000Z",
        "parent": {"type": "workspace", "workspace": True},
        "properties": {"title": {"title": [{"plain_text": "Test Page"}]}},
    }

    respx.post("https://api.notion.com/v1/pages").mock(
        return_value=Response(200, json=mock_response)
    )

    page = await api_adapter.create_page(title="Test Page")

    assert isinstance(page, NotionPage)
    assert page.id == "page_123"
    assert page.title == "Test Page"


@pytest.mark.asyncio
@respx.mock
async def test_rename_page(api_adapter):
    """rename_page updates page title via API."""
    mock_response = {
        "id": "page_123",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:01:00.000Z",
        "parent": {"type": "workspace", "workspace": True},
        "properties": {"title": {"title": [{"plain_text": "New Title"}]}},
    }

    respx.patch("https://api.notion.com/v1/pages/page_123").mock(
        return_value=Response(200, json=mock_response)
    )

    page = await api_adapter.rename_page(page_id="page_123", new_title="New Title")

    assert page.title == "New Title"


@pytest.mark.asyncio
@respx.mock
async def test_move_page(api_adapter):
    """move_page updates page parent via API."""
    mock_response = {
        "id": "page_123",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:01:00.000Z",
        "parent": {"type": "page_id", "page_id": "parent_456"},
        "properties": {"title": {"title": [{"plain_text": "Test Page"}]}},
    }

    respx.patch("https://api.notion.com/v1/pages/page_123").mock(
        return_value=Response(200, json=mock_response)
    )

    page = await api_adapter.move_page(
        page_id="page_123", new_parent_id="parent_456", new_parent_type="page_id"
    )

    assert page.parent_id == "parent_456"
    assert page.parent_type == "page_id"


@pytest.mark.asyncio
@respx.mock
async def test_set_icon(api_adapter):
    """set_icon updates page icon via API."""
    mock_response = {
        "id": "page_123",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:01:00.000Z",
        "parent": {"type": "workspace", "workspace": True},
        "properties": {"title": {"title": [{"plain_text": "Test Page"}]}},
        "icon": {"type": "emoji", "emoji": "🚀"},
    }

    respx.patch("https://api.notion.com/v1/pages/page_123").mock(
        return_value=Response(200, json=mock_response)
    )

    page = await api_adapter.set_icon(page_id="page_123", icon="🚀")

    assert page.icon == "🚀"


@pytest.mark.asyncio
@respx.mock
async def test_set_cover(api_adapter):
    """set_cover updates page cover via API."""
    mock_response = {
        "id": "page_123",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:01:00.000Z",
        "parent": {"type": "workspace", "workspace": True},
        "properties": {"title": {"title": [{"plain_text": "Test Page"}]}},
        "cover": {"type": "external", "external": {"url": "https://example.com/cover.jpg"}},
    }

    respx.patch("https://api.notion.com/v1/pages/page_123").mock(
        return_value=Response(200, json=mock_response)
    )

    page = await api_adapter.set_cover(
        page_id="page_123", cover_url="https://example.com/cover.jpg"
    )

    assert page.cover == "https://example.com/cover.jpg"


@pytest.mark.asyncio
@respx.mock
async def test_add_text_block(api_adapter):
    """add_text_block appends paragraph block via API."""
    mock_response = {
        "results": [
            {
                "id": "block_123",
                "type": "paragraph",
                "created_time": "2026-09-24T12:00:00.000Z",
                "paragraph": {"rich_text": [{"text": {"content": "Hello"}}]},
            }
        ]
    }

    respx.patch("https://api.notion.com/v1/blocks/page_123/children").mock(
        return_value=Response(200, json=mock_response)
    )

    block = await api_adapter.add_text_block(page_id="page_123", content="Hello")

    assert isinstance(block, NotionTextBlock)
    assert block.id == "block_123"
    assert block.content == "Hello"


@pytest.mark.asyncio
@respx.mock
async def test_add_callout_block(api_adapter):
    """add_callout_block appends callout block via API."""
    mock_response = {
        "results": [
            {
                "id": "block_456",
                "type": "callout",
                "created_time": "2026-09-24T12:00:00.000Z",
                "callout": {
                    "rich_text": [{"text": {"content": "Note"}}],
                    "icon": {"type": "emoji", "emoji": "💡"},
                },
            }
        ]
    }

    respx.patch("https://api.notion.com/v1/blocks/page_123/children").mock(
        return_value=Response(200, json=mock_response)
    )

    block = await api_adapter.add_callout_block(page_id="page_123", content="Note", icon="💡")

    assert isinstance(block, NotionCalloutBlock)
    assert block.id == "block_456"
    assert block.content == "Note"
    assert block.icon == "💡"


@pytest.mark.asyncio
@respx.mock
async def test_create_database(api_adapter):
    """create_database creates a new database via API."""
    mock_response = {
        "id": "db_123",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:00:00.000Z",
        "title": [{"plain_text": "Test DB"}],
        "parent": {"type": "workspace", "workspace": True},
        "properties": {"Name": {"id": "title", "type": "title", "title": {}}},
    }

    respx.post("https://api.notion.com/v1/databases").mock(
        return_value=Response(200, json=mock_response)
    )

    database = await api_adapter.create_database(title="Test DB")

    assert isinstance(database, NotionDatabase)
    assert database.id == "db_123"
    assert database.title == "Test DB"


@pytest.mark.asyncio
@respx.mock
async def test_add_property(api_adapter):
    """add_property adds a property to a database via API."""
    mock_response = {
        "id": "db_123",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:01:00.000Z",
        "title": [{"plain_text": "Test DB"}],
        "parent": {"type": "workspace", "workspace": True},
        "properties": {
            "Name": {"id": "title", "type": "title", "title": {}},
            "Status": {"id": "prop_123", "type": "select", "select": {"options": []}},
        },
    }

    respx.patch("https://api.notion.com/v1/databases/db_123").mock(
        return_value=Response(200, json=mock_response)
    )

    prop = await api_adapter.add_property(
        database_id="db_123", name="Status", property_type="select", config={"options": []}
    )

    assert isinstance(prop, NotionDatabaseProperty)
    assert prop.name == "Status"
    assert prop.type == "select"


@pytest.mark.asyncio
@respx.mock
async def test_create_relation(api_adapter):
    """create_relation creates a relation property via API."""
    mock_response = {
        "id": "db_123",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:01:00.000Z",
        "title": [{"plain_text": "Test DB"}],
        "parent": {"type": "workspace", "workspace": True},
        "properties": {
            "Name": {"id": "title", "type": "title", "title": {}},
            "Related": {
                "id": "rel_123",
                "type": "relation",
                "relation": {"database_id": "db_456"},
            },
        },
    }

    respx.patch("https://api.notion.com/v1/databases/db_123").mock(
        return_value=Response(200, json=mock_response)
    )

    relation = await api_adapter.create_relation(
        database_id="db_123", name="Related", target_database_id="db_456"
    )

    assert isinstance(relation, NotionRelation)
    assert relation.name == "Related"
    assert relation.database_id == "db_456"


@pytest.mark.asyncio
@respx.mock
async def test_create_rollup(api_adapter):
    """create_rollup creates a rollup property via API."""
    mock_response = {
        "id": "db_123",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:01:00.000Z",
        "title": [{"plain_text": "Test DB"}],
        "parent": {"type": "workspace", "workspace": True},
        "properties": {
            "Name": {"id": "title", "type": "title", "title": {}},
            "Count": {
                "id": "rollup_123",
                "type": "rollup",
                "rollup": {
                    "relation_property_name": "rel_prop",
                    "rollup_property_name": "target_prop",
                    "function": "count",
                },
            },
        },
    }

    respx.patch("https://api.notion.com/v1/databases/db_123").mock(
        return_value=Response(200, json=mock_response)
    )

    rollup = await api_adapter.create_rollup(
        database_id="db_123",
        name="Count",
        relation_property_id="rel_prop",
        rollup_property_id="target_prop",
        function="count",
    )

    assert isinstance(rollup, NotionRollup)
    assert rollup.name == "Count"
    assert rollup.function == "count"


@pytest.mark.asyncio
async def test_add_filter(api_adapter):
    """add_filter returns filter spec (query parameter, not persistent)."""
    from money_machine.integrations.notion.domain import NotionFilter

    filter_spec = NotionFilter(property="Status", condition="equals", value="Done")

    result = await api_adapter.add_filter(
        database_id="db_123", view_id="view_456", filter_spec=filter_spec
    )

    assert result["view_id"] == "view_456"
    assert result["filter"]["property"] == "Status"
    assert "equals" in result["filter"]


@pytest.mark.asyncio
async def test_add_sort(api_adapter):
    """add_sort returns sort spec (query parameter, not persistent)."""
    from money_machine.integrations.notion.domain import NotionSort

    sort_spec = NotionSort(property="Created", direction="descending")

    result = await api_adapter.add_sort(
        database_id="db_123", view_id="view_456", sort_spec=sort_spec
    )

    assert result["view_id"] == "view_456"
    assert result["sort"]["property"] == "Created"
    assert result["sort"]["direction"] == "descending"


@pytest.mark.asyncio
@respx.mock
async def test_add_child_page(api_adapter):
    """add_child_page creates a child page via API."""
    mock_response = {
        "id": "page_child",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:00:00.000Z",
        "parent": {"type": "page_id", "page_id": "page_parent"},
        "properties": {"title": {"title": [{"plain_text": "Child Page"}]}},
    }

    respx.post("https://api.notion.com/v1/pages").mock(
        return_value=Response(200, json=mock_response)
    )

    page = await api_adapter.add_child_page(parent_page_id="page_parent", title="Child Page")

    assert page.id == "page_child"
    assert page.parent_id == "page_parent"
    assert page.parent_type == "page_id"


@pytest.mark.asyncio
@respx.mock
async def test_inspect_page(api_adapter):
    """inspect_page retrieves page metadata via API."""
    mock_response = {
        "id": "page_123",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:00:00.000Z",
        "parent": {"type": "workspace", "workspace": True},
        "properties": {"title": {"title": [{"plain_text": "Test Page"}]}},
    }

    respx.get("https://api.notion.com/v1/pages/page_123").mock(
        return_value=Response(200, json=mock_response)
    )

    page = await api_adapter.inspect_page(page_id="page_123")

    assert page.id == "page_123"
    assert page.title == "Test Page"


@pytest.mark.asyncio
@respx.mock
async def test_inspect_database(api_adapter):
    """inspect_database retrieves database schema via API."""
    mock_response = {
        "id": "db_123",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:00:00.000Z",
        "title": [{"plain_text": "Test DB"}],
        "parent": {"type": "workspace", "workspace": True},
        "properties": {"Name": {"id": "title", "type": "title", "title": {}}},
    }

    respx.get("https://api.notion.com/v1/databases/db_123").mock(
        return_value=Response(200, json=mock_response)
    )

    database = await api_adapter.inspect_database(database_id="db_123")

    assert database.id == "db_123"
    assert database.title == "Test DB"


@pytest.mark.asyncio
@respx.mock
async def test_get_public_url(api_adapter):
    """get_public_url retrieves public URL via API."""
    mock_response = {
        "id": "page_123",
        "created_time": "2026-09-24T12:00:00.000Z",
        "last_edited_time": "2026-09-24T12:00:00.000Z",
        "parent": {"type": "workspace", "workspace": True},
        "properties": {"title": {"title": [{"plain_text": "Test Page"}]}},
        "public_url": "https://example.notion.site/Test-Page-123",
    }

    respx.get("https://api.notion.com/v1/pages/page_123").mock(
        return_value=Response(200, json=mock_response)
    )

    url = await api_adapter.get_public_url(page_id="page_123")

    assert url == "https://example.notion.site/Test-Page-123"


@pytest.mark.asyncio
async def test_browser_operations_raise_not_implemented(api_adapter):
    """BROWSER-only operations raise NotImplementedError."""
    with pytest.raises(NotImplementedError, match="requires BROWSER method"):
        await api_adapter.duplicate_page(page_id="page_123")

    with pytest.raises(NotImplementedError, match="formula editor UI-only"):
        await api_adapter.create_formula(database_id="db_123", name="Formula", expression="1+1")

    with pytest.raises(NotImplementedError, match="requires BROWSER method"):
        await api_adapter.publish_page(page_id="page_123")

    with pytest.raises(NotImplementedError, match="requires BROWSER method"):
        await api_adapter.verify_stranger_access(public_url="https://example.notion.site/Page-123")
