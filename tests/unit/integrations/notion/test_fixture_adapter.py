"""Unit tests for FixtureNotionAdapter — in-memory CRUD stubs."""

import pytest

from money_machine.integrations.notion.domain import (
    NotionDatabase,
    NotionFilter,
    NotionPage,
    NotionSort,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter


@pytest.fixture
def adapter():
    """Create a fresh FixtureNotionAdapter for each test."""
    return FixtureNotionAdapter()


@pytest.mark.asyncio
async def test_fixture_connection_status_always_connected(adapter):
    """Fixture adapter reports connected status."""
    status = await adapter.connection_status()

    assert status["connected"] is True
    assert status["user_id"] == "user_fixture"
    assert status["workspace_count"] == 1  # Default workspace seeded


@pytest.mark.asyncio
async def test_fixture_workspace_discovery_returns_seeded_workspace(adapter):
    """Fixture adapter has one default workspace."""
    workspaces = await adapter.workspace_discovery()

    assert len(workspaces) == 1
    assert workspaces[0].id == "ws_default"
    assert workspaces[0].name == "Fixture Workspace"


@pytest.mark.asyncio
async def test_fixture_create_page_returns_typed_page(adapter):
    """Fixture create_page returns NotionPage with generated ID."""
    page = await adapter.create_page(
        title="Test Page", icon="📄", cover="https://example.com/cover.jpg"
    )

    assert isinstance(page, NotionPage)
    assert page.id.startswith("page_")
    assert page.title == "Test Page"
    assert page.icon == "📄"
    assert page.cover == "https://example.com/cover.jpg"
    assert page.parent_id == "ws_default"  # Default workspace
    assert page.parent_type == "workspace"


@pytest.mark.asyncio
async def test_fixture_duplicate_page_creates_copy_with_new_id(adapter):
    """Fixture duplicate_page returns new page with distinct ID."""
    original = await adapter.create_page(title="Original Page", icon="🔵")

    duplicate = await adapter.duplicate_page(original.id)

    assert isinstance(duplicate, NotionPage)
    assert duplicate.id != original.id  # Different ID
    assert duplicate.id.startswith("page_")
    assert duplicate.title == "Original Page (Copy)"
    assert duplicate.icon == "🔵"
    assert duplicate.is_published is False  # Duplicates unpublished


@pytest.mark.asyncio
async def test_fixture_duplicate_page_raises_on_nonexistent_page(adapter):
    """Fixture duplicate_page raises ValueError for nonexistent page."""
    with pytest.raises(ValueError, match="Page nonexistent_id not found"):
        await adapter.duplicate_page("nonexistent_id")


@pytest.mark.asyncio
async def test_fixture_rename_page_updates_title(adapter):
    """Fixture rename_page updates title idempotently."""
    page = await adapter.create_page(title="Old Title")

    renamed = await adapter.rename_page(page.id, "New Title")

    assert renamed.id == page.id
    assert renamed.title == "New Title"


@pytest.mark.asyncio
async def test_fixture_move_page_updates_parent(adapter):
    """Fixture move_page updates parent idempotently."""
    parent1 = await adapter.create_page(title="Parent 1")
    parent2 = await adapter.create_page(title="Parent 2")
    child = await adapter.create_page(title="Child", parent_id=parent1.id, parent_type="page_id")

    moved = await adapter.move_page(child.id, parent2.id, "page_id")

    assert moved.id == child.id
    assert moved.parent_id == parent2.id
    assert moved.parent_type == "page_id"


@pytest.mark.asyncio
async def test_fixture_set_icon_updates_icon(adapter):
    """Fixture set_icon updates icon idempotently."""
    page = await adapter.create_page(title="Page", icon="🔵")

    updated = await adapter.set_icon(page.id, "🔴")

    assert updated.id == page.id
    assert updated.icon == "🔴"


@pytest.mark.asyncio
async def test_fixture_set_cover_updates_cover(adapter):
    """Fixture set_cover updates cover idempotently."""
    page = await adapter.create_page(title="Page")

    updated = await adapter.set_cover(page.id, "https://example.com/new-cover.jpg")

    assert updated.id == page.id
    assert updated.cover == "https://example.com/new-cover.jpg"


@pytest.mark.asyncio
async def test_fixture_add_text_block_appends_block(adapter):
    """Fixture add_text_block appends text block to page."""
    page = await adapter.create_page(title="Page")

    block = await adapter.add_text_block(page.id, "This is a paragraph.")

    assert block.id.startswith("block_")
    assert block.type == "paragraph"
    assert block.parent_id == page.id
    assert block.content == "This is a paragraph."


@pytest.mark.asyncio
async def test_fixture_add_callout_block_appends_callout(adapter):
    """Fixture add_callout_block appends callout block to page."""
    page = await adapter.create_page(title="Page")

    block = await adapter.add_callout_block(page.id, "Important note", icon="⚠️")

    assert block.id.startswith("block_")
    assert block.type == "callout"
    assert block.parent_id == page.id
    assert block.content == "Important note"
    assert block.icon == "⚠️"


@pytest.mark.asyncio
async def test_fixture_create_database_returns_typed_database(adapter):
    """Fixture create_database returns NotionDatabase with generated ID."""
    database = await adapter.create_database(title="Test DB", icon="🗂️")

    assert isinstance(database, NotionDatabase)
    assert database.id.startswith("db_")
    assert database.title == "Test DB"
    assert database.icon == "🗂️"
    assert database.properties == []  # Empty schema initially


@pytest.mark.asyncio
async def test_fixture_add_property_creates_property(adapter):
    """Fixture add_property adds property to database."""
    database = await adapter.create_database(title="DB")

    prop = await adapter.add_property(database.id, "Name", "title", {})

    assert prop.id.startswith("prop_")
    assert prop.name == "Name"
    assert prop.type == "title"
    assert len(database.properties) == 1


@pytest.mark.asyncio
async def test_fixture_add_property_is_idempotent(adapter):
    """Fixture add_property updates existing property with same name."""
    database = await adapter.create_database(title="DB")

    prop1 = await adapter.add_property(database.id, "Status", "select", {})
    prop2 = await adapter.add_property(database.id, "Status", "multi_select", {})

    assert prop1.id == prop2.id  # Same property ID
    assert prop2.type == "multi_select"  # Type updated
    assert len(database.properties) == 1  # Only one property


@pytest.mark.asyncio
async def test_fixture_create_relation_creates_relation(adapter):
    """Fixture create_relation creates relation property."""
    db1 = await adapter.create_database(title="Tasks")
    db2 = await adapter.create_database(title="Projects")

    relation = await adapter.create_relation(db1.id, "Project", db2.id)

    assert relation.id.startswith("rel_")
    assert relation.name == "Project"
    assert relation.database_id == db2.id
    assert len(db1.properties) == 1  # Added to db1


@pytest.mark.asyncio
async def test_fixture_create_rollup_creates_rollup(adapter):
    """Fixture create_rollup creates rollup property."""
    database = await adapter.create_database(title="DB")
    relation_prop = await adapter.add_property(database.id, "Related", "relation", {})

    rollup = await adapter.create_rollup(
        database.id, "Count", relation_prop.id, "some_prop", "count"
    )

    assert rollup.id.startswith("rollup_")
    assert rollup.name == "Count"
    assert rollup.function == "count"


@pytest.mark.asyncio
async def test_fixture_create_formula_creates_formula(adapter):
    """Fixture create_formula creates formula property."""
    database = await adapter.create_database(title="DB")

    formula = await adapter.create_formula(database.id, "Calculation", "prop('A') + prop('B')")

    assert formula.id.startswith("formula_")
    assert formula.name == "Calculation"
    assert formula.expression == "prop('A') + prop('B')"


@pytest.mark.asyncio
async def test_fixture_create_linked_view_creates_linked_view(adapter):
    """Fixture create_linked_view creates linked database view."""
    database = await adapter.create_database(title="Canonical DB")
    page = await adapter.create_page(title="Dashboard")

    linked_view = await adapter.create_linked_view(database.id, page.id, "table")

    assert linked_view.id.startswith("linked_view_")
    assert linked_view.source_database_id == database.id
    assert linked_view.parent_page_id == page.id
    assert linked_view.view_type == "table"


@pytest.mark.asyncio
async def test_fixture_add_filter_returns_stub_config(adapter):
    """Fixture add_filter returns stub filter config."""
    database = await adapter.create_database(title="DB")
    filter_spec = NotionFilter(property="Status", condition="equals", value="Done")

    config = await adapter.add_filter(database.id, "view_123", filter_spec)

    assert config["view_id"] == "view_123"
    assert config["filter"]["property"] == "Status"
    assert config["filter"]["condition"] == "equals"
    assert config["filter"]["value"] == "Done"


@pytest.mark.asyncio
async def test_fixture_add_sort_returns_stub_config(adapter):
    """Fixture add_sort returns stub sort config."""
    database = await adapter.create_database(title="DB")
    sort_spec = NotionSort(property="Created", direction="descending")

    config = await adapter.add_sort(database.id, "view_123", sort_spec)

    assert config["view_id"] == "view_123"
    assert config["sort"]["property"] == "Created"
    assert config["sort"]["direction"] == "descending"


@pytest.mark.asyncio
async def test_fixture_create_calendar_view_creates_view(adapter):
    """Fixture create_calendar_view creates calendar view."""
    database = await adapter.create_database(title="DB")

    view = await adapter.create_calendar_view(database.id, "Calendar", "Date")

    assert view.id.startswith("view_")
    assert view.database_id == database.id
    assert view.name == "Calendar"
    assert view.type == "calendar"


@pytest.mark.asyncio
async def test_fixture_create_table_view_creates_view(adapter):
    """Fixture create_table_view creates table view."""
    database = await adapter.create_database(title="DB")

    view = await adapter.create_table_view(database.id, "All Items")

    assert view.id.startswith("view_")
    assert view.type == "table"


@pytest.mark.asyncio
async def test_fixture_create_board_view_creates_view(adapter):
    """Fixture create_board_view creates board view."""
    database = await adapter.create_database(title="DB")

    view = await adapter.create_board_view(database.id, "Board", "Status")

    assert view.id.startswith("view_")
    assert view.type == "board"


@pytest.mark.asyncio
async def test_fixture_set_view_title_visibility_updates_visibility(adapter):
    """Fixture set_view_title_visibility updates title visibility."""
    database = await adapter.create_database(title="DB")
    view = await adapter.create_table_view(database.id, "View")

    updated = await adapter.set_view_title_visibility(view.id, False)

    assert updated.id == view.id
    assert updated.title_visible is False


@pytest.mark.asyncio
async def test_fixture_add_child_page_creates_child(adapter):
    """Fixture add_child_page creates child page with parent reference."""
    parent = await adapter.create_page(title="Parent")

    child = await adapter.add_child_page(parent.id, "Child")

    assert child.id.startswith("page_")
    assert child.title == "Child"
    assert child.parent_id == parent.id
    assert child.parent_type == "page_id"


@pytest.mark.asyncio
async def test_fixture_publish_page_sets_published_and_url(adapter):
    """Fixture publish_page marks page as published with public URL."""
    page = await adapter.create_page(title="Page")

    published = await adapter.publish_page(page.id)

    assert published.id == page.id
    assert published.is_published is True
    assert published.public_url is not None
    assert "notion.site" in published.public_url


@pytest.mark.asyncio
async def test_fixture_set_duplicate_as_template_updates_setting(adapter):
    """Fixture set_duplicate_as_template updates template setting."""
    page = await adapter.create_page(title="Page")

    updated = await adapter.set_duplicate_as_template(page.id, True)

    assert updated.id == page.id
    assert updated.duplicate_as_template is True


@pytest.mark.asyncio
async def test_fixture_set_search_indexing_updates_setting(adapter):
    """Fixture set_search_indexing updates search indexing setting."""
    page = await adapter.create_page(title="Page")

    updated = await adapter.set_search_indexing(page.id, False)

    assert updated.id == page.id
    assert updated.search_indexing is False


@pytest.mark.asyncio
async def test_fixture_get_public_url_returns_url_if_published(adapter):
    """Fixture get_public_url returns URL if page is published."""
    page = await adapter.create_page(title="Page")
    await adapter.publish_page(page.id)

    url = await adapter.get_public_url(page.id)

    assert url is not None
    assert "notion.site" in url


@pytest.mark.asyncio
async def test_fixture_get_public_url_returns_none_if_unpublished(adapter):
    """Fixture get_public_url returns None if page is unpublished."""
    page = await adapter.create_page(title="Page")

    url = await adapter.get_public_url(page.id)

    assert url is None


@pytest.mark.asyncio
async def test_fixture_unpublish_page_clears_published_and_url(adapter):
    """Fixture unpublish_page marks page as unpublished and clears URL."""
    page = await adapter.create_page(title="Page")
    await adapter.publish_page(page.id)

    unpublished = await adapter.unpublish_page(page.id)

    assert unpublished.id == page.id
    assert unpublished.is_published is False
    assert unpublished.public_url is None


@pytest.mark.asyncio
async def test_fixture_inspect_page_returns_page(adapter):
    """Fixture inspect_page returns existing page."""
    page = await adapter.create_page(title="Page", icon="📄")

    inspected = await adapter.inspect_page(page.id)

    assert inspected.id == page.id
    assert inspected.title == "Page"
    assert inspected.icon == "📄"


@pytest.mark.asyncio
async def test_fixture_inspect_database_returns_database(adapter):
    """Fixture inspect_database returns existing database with schema."""
    database = await adapter.create_database(title="DB")
    await adapter.add_property(database.id, "Name", "title", {})

    inspected = await adapter.inspect_database(database.id)

    assert inspected.id == database.id
    assert inspected.title == "DB"
    assert len(inspected.properties) == 1


@pytest.mark.asyncio
async def test_fixture_verify_stranger_access_returns_true_for_valid_url(adapter):
    """Fixture verify_stranger_access returns True for valid public URLs."""
    accessible = await adapter.verify_stranger_access("https://example.notion.site/Page-123")

    assert accessible is True


@pytest.mark.asyncio
async def test_fixture_verify_stranger_access_returns_false_for_invalid_url(adapter):
    """Fixture verify_stranger_access returns False for non-Notion URLs."""
    accessible = await adapter.verify_stranger_access("https://example.com/page")

    assert accessible is False
