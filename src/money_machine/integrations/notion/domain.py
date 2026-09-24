"""Domain models for Notion integration.

These models represent Notion entities (pages, databases, properties, views, blocks)
as returned by NotionAdapter operations. They are fixture-friendly: simple dataclasses
with minimal validation, suitable for in-memory testing and later API/browser mapping.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class NotionWorkspace:
    """A Notion workspace."""

    id: str
    name: str
    owner_user_id: str | None = None
    icon: str | None = None


@dataclass
class NotionPage:
    """A Notion page."""

    id: str
    title: str
    parent_id: str | None = None
    parent_type: str = "workspace"  # workspace | page_id | database_id
    icon: str | None = None
    cover: str | None = None
    public_url: str | None = None
    is_published: bool = False
    duplicate_as_template: bool = False
    search_indexing: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotionBlock:
    """Base class for Notion blocks."""

    id: str
    parent_id: str
    type: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class NotionTextBlock(NotionBlock):
    """A Notion paragraph (text) block."""

    type: str = "paragraph"
    content: str = ""


@dataclass
class NotionCalloutBlock(NotionBlock):
    """A Notion callout block."""

    type: str = "callout"
    content: str = ""
    icon: str = "💡"


@dataclass
class NotionDatabaseProperty:
    """A Notion database property (column)."""

    id: str
    name: str
    type: str  # title | text | number | select | multi_select | date | person | checkbox
    # | url | email | phone | formula | relation | rollup | created_time
    # | created_by | last_edited_time | last_edited_by
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotionRelation:
    """A Notion relation property."""

    id: str
    name: str
    database_id: str
    synced_property_name: str | None = None  # For two-way relations


@dataclass
class NotionRollup:
    """A Notion rollup property."""

    id: str
    name: str
    relation_property_id: str
    rollup_property_id: str
    function: str  # count | count_values | empty | not_empty | unique | show_unique
    # | percent_empty | percent_not_empty | sum | average | median | min | max
    # | range | earliest_date | latest_date | date_range | checked | unchecked
    # | percent_checked | percent_unchecked


@dataclass
class NotionFormula:
    """A Notion formula property."""

    id: str
    name: str
    expression: str


@dataclass
class NotionDatabase:
    """A Notion database."""

    id: str
    title: str
    parent_id: str | None = None
    parent_type: str = "workspace"  # workspace | page_id
    icon: str | None = None
    cover: str | None = None
    properties: list[NotionDatabaseProperty] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class NotionView:
    """A Notion database view."""

    id: str
    database_id: str
    name: str
    type: str  # table | board | calendar | list | gallery | timeline
    title_visible: bool = True


@dataclass
class NotionLinkedView:
    """A Notion linked database view (references canonical database)."""

    id: str
    source_database_id: str
    parent_page_id: str
    view_type: str = "table"  # table | board | calendar


@dataclass
class NotionFilter:
    """A Notion database filter."""

    property: str
    condition: str  # equals | does_not_equal | contains | does_not_contain
    # | is_empty | is_not_empty | greater_than | less_than | etc.
    value: Any


@dataclass
class NotionSort:
    """A Notion database sort."""

    property: str
    direction: str  # ascending | descending
