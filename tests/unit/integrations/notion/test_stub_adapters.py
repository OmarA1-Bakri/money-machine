"""Unit tests for stub adapters — verify NotImplementedError behavior."""

import pytest

from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.browser_adapter import BrowserNotionAdapter
from money_machine.integrations.notion.combined_adapter import CombinedNotionAdapter


@pytest.mark.asyncio
async def test_api_adapter_raises_not_implemented():
    """APINotionAdapter raises NotImplementedError for all methods."""
    adapter = APINotionAdapter()

    with pytest.raises(NotImplementedError, match="Real API adapter deferred"):
        await adapter.connection_status()

    with pytest.raises(NotImplementedError, match="Real API adapter deferred"):
        await adapter.workspace_discovery()

    with pytest.raises(NotImplementedError, match="Real API adapter deferred"):
        await adapter.create_page(title="Test")

    with pytest.raises(NotImplementedError, match="Real API adapter deferred"):
        await adapter.inspect_page(page_id="page_123")


@pytest.mark.asyncio
async def test_browser_adapter_raises_not_implemented_for_ui_ops():
    """BrowserNotionAdapter raises NotImplementedError for UI-only operations."""
    adapter = BrowserNotionAdapter()

    with pytest.raises(NotImplementedError, match="Real browser adapter deferred"):
        await adapter.duplicate_page(page_id="page_123")

    with pytest.raises(NotImplementedError, match="Real browser adapter deferred"):
        await adapter.create_formula(database_id="db_123", name="Formula", expression="1+1")

    with pytest.raises(NotImplementedError, match="Real browser adapter deferred"):
        await adapter.create_linked_view(source_database_id="db_123", parent_page_id="page_123")

    with pytest.raises(NotImplementedError, match="Real browser adapter deferred"):
        await adapter.publish_page(page_id="page_123")


@pytest.mark.asyncio
async def test_browser_adapter_rejects_api_operations():
    """BrowserNotionAdapter rejects operations that use API method."""
    adapter = BrowserNotionAdapter()

    with pytest.raises(NotImplementedError, match="uses API method, not BROWSER"):
        await adapter.connection_status()

    with pytest.raises(NotImplementedError, match="uses API method, not BROWSER"):
        await adapter.create_page(title="Test")

    with pytest.raises(NotImplementedError, match="uses API method, not BROWSER"):
        await adapter.inspect_page(page_id="page_123")


@pytest.mark.asyncio
async def test_combined_adapter_raises_not_implemented():
    """CombinedNotionAdapter raises NotImplementedError for all methods."""
    adapter = CombinedNotionAdapter()

    with pytest.raises(NotImplementedError, match="Real combined adapter deferred"):
        await adapter.connection_status()

    with pytest.raises(NotImplementedError, match="Real combined adapter deferred"):
        await adapter.get_public_url(page_id="page_123")

    with pytest.raises(NotImplementedError, match="Real combined adapter deferred"):
        await adapter.verify_stranger_access(public_url="https://example.notion.site/Page-123")


@pytest.mark.asyncio
async def test_api_adapter_browser_ops_indicate_method_mismatch():
    """APINotionAdapter indicates UI-only operations require BROWSER method."""
    adapter = APINotionAdapter()

    with pytest.raises(NotImplementedError, match="requires BROWSER method"):
        await adapter.duplicate_page(page_id="page_123")

    with pytest.raises(NotImplementedError, match="formula editor UI-only"):
        await adapter.create_formula(database_id="db_123", name="Formula", expression="1+1")

    with pytest.raises(NotImplementedError, match="requires BROWSER method"):
        await adapter.publish_page(page_id="page_123")
