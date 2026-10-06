"""Shared fixture helpers for a named linked view.

Dashboard and hub phases both attach a planned view to a page. The fixture
call and the filter triple live here so the two phases do not keep copies.
"""

from __future__ import annotations

from money_machine.integrations.notion.domain import NotionLinkedView
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from money_machine.integrations.notion.relations import LinkedView


def filter_pairs(view: LinkedView) -> tuple[tuple[str, str, str], ...]:
    """Property, condition, and value for each filter, in view order."""
    return tuple((item.property_name, item.condition, item.value) for item in view.filters)


async def create_named_linked_view(
    probe: FixtureNotionAdapter,
    page_id: str,
    source_id: str,
    view: LinkedView,
) -> NotionLinkedView:
    """Create one linked view and store its planned name and filters."""
    created = await probe.create_linked_view(source_id, page_id, view.view_type)
    created.name = view.name
    created.filters = filter_pairs(view)
    return created
