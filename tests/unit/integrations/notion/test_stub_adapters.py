"""Unit tests for stub adapters — verify NotImplementedError behavior."""

import pytest

from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.combined_adapter import CombinedNotionAdapter


# Note: BrowserNotionAdapter tests removed - W3 implements real browser adapter
# with dependency injection. See test_browser_adapter.py for full coverage.


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
    adapter = APINotionAdapter(api_token="test_token")

    with pytest.raises(NotImplementedError, match="requires BROWSER method"):
        await adapter.duplicate_page(page_id="page_123")

    with pytest.raises(NotImplementedError, match="formula editor UI-only"):
        await adapter.create_formula(database_id="db_123", name="Formula", expression="1+1")

    with pytest.raises(NotImplementedError, match="requires BROWSER method"):
        await adapter.publish_page(page_id="page_123")
