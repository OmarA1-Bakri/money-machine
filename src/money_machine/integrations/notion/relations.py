"""Relation and linked-view helpers.

Session 06 prompt heading "### 6. Implement relation and linked-view helpers"
(``prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md``).

One catalogue data type has one canonical database. Hub views link to that
database; they do not create another store. Filters are date, category, or
status. The home dashboard has a today view, a monthly calendar, and quick
notes. The notification dashboard is one row of relations and rollups over
the Tasks, Events, Finance, and Habits formulas from section 5. A missing
database omits its relation and rollup. ``client_name``, the configured buyer
name, and ``current_date`` are not relations. This module does not call
Notion, the network, or a browser.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from .errors import SchemaBuilderError
from .formulas import validated_name
from .schema_builder import DATABASE_KINDS

MAX_FILTERS = 3
VIEW_TYPES: frozenset[str] = frozenset({"table", "calendar", "board"})
FILTER_DIMENSIONS: frozenset[str] = frozenset({"date", "category", "status"})

# data type, rollup name, source property, function.
_DASHBOARD_LINKS: tuple[tuple[str, str, str, str], ...] = (
    ("Tasks", "open_tasks_due_today", "task_open_and_due_today", "checked"),
    ("Events", "birthday_status", "birthday_status", "checked"),
    ("Finance", "money_spent_today", "money_spent_today", "sum"),
    ("Habits", "water_glasses_remaining", "water_glasses_remaining", "sum"),
)


@dataclass(frozen=True, slots=True)
class CanonicalDatabase:
    """The one database for a catalogue data type."""

    data_type: str


@dataclass(frozen=True, slots=True)
class CanonicalDatabases:
    """Canonical databases copied from the caller sequence."""

    data_types: tuple[str, ...]
    by_type: Mapping[str, CanonicalDatabase]


@dataclass(frozen=True, slots=True)
class ViewFilter:
    """One date, category, or status filter."""

    dimension: str
    property_name: str
    condition: str
    value: str


@dataclass(frozen=True, slots=True)
class LinkedView:
    """A hub view whose source is a canonical database."""

    hub: str
    data_type: str
    view_type: str
    name: str
    filters: tuple[ViewFilter, ...]


@dataclass(frozen=True, slots=True)
class DashboardRelation:
    """A relation from the one-row dashboard to one canonical database."""

    name: str
    data_type: str


@dataclass(frozen=True, slots=True)
class DashboardRollup:
    """A rollup over one dashboard relation."""

    name: str
    relation_name: str
    property_name: str
    function: str


@dataclass(frozen=True, slots=True)
class NotificationDashboard:
    """Relations and rollups for the one-row notification dashboard."""

    row_count: int
    relations: tuple[DashboardRelation, ...]
    rollups: tuple[DashboardRollup, ...]


def build_canonical_databases(data_types: object) -> CanonicalDatabases:
    """Register one canonical database per catalogue data type."""
    if isinstance(data_types, str) or not isinstance(data_types, Sequence):
        raise SchemaBuilderError("data types must be a sequence of strings")
    raw = tuple(data_types)
    if len(raw) < 1:
        raise SchemaBuilderError("data types must not be empty")
    ordered: dict[str, CanonicalDatabase] = {}
    names: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise SchemaBuilderError("data type must be a string")
        if item not in DATABASE_KINDS:
            valid = ", ".join(DATABASE_KINDS)
            raise SchemaBuilderError(f"unknown data type {item!r}; valid keys: {valid}")
        if item in ordered:
            raise SchemaBuilderError(f"data type {item!r} is duplicated")
        names.append(item)
        ordered[item] = CanonicalDatabase(data_type=item)
    return CanonicalDatabases(data_types=tuple(names), by_type=MappingProxyType(ordered))


def build_filter(
    dimension: object,
    property_name: object,
    condition: object,
    value: object,
) -> ViewFilter:
    """Build one filter. The condition is ``equals``."""
    if not isinstance(dimension, str) or dimension not in FILTER_DIMENSIONS:
        raise SchemaBuilderError(f"filter dimension {dimension!r} is not allowed")
    if condition != "equals":
        raise SchemaBuilderError("filter condition must be equals")
    return ViewFilter(
        dimension=dimension,
        property_name=validated_name("property name", property_name),
        condition="equals",
        value=validated_name("filter value", value),
    )


def build_linked_view(
    hub: object,
    data_type: object,
    view_type: object,
    name: object,
    filters: object,
    canonical: object,
) -> LinkedView:
    """Link a hub view to a registered canonical database."""
    hub_name = validated_name("hub", hub)
    view_name = validated_name("view name", name)
    if not isinstance(canonical, CanonicalDatabases):
        raise SchemaBuilderError("linked view requires canonical databases")
    if not isinstance(data_type, str) or data_type not in canonical.by_type:
        raise SchemaBuilderError(f"data type {data_type!r} is not canonical")
    if not isinstance(view_type, str) or view_type not in VIEW_TYPES:
        raise SchemaBuilderError(f"view type {view_type!r} is not allowed")
    return LinkedView(
        hub=hub_name,
        data_type=data_type,
        view_type=view_type,
        name=view_name,
        filters=_copy_filters(filters),
    )


def dashboard_today_view(canonical: CanonicalDatabases) -> LinkedView:
    """Today's open tasks, linked to the canonical Tasks database."""
    return build_linked_view(
        "Dashboard",
        "Tasks",
        "table",
        "Today",
        (
            build_filter("date", "Due", "equals", "today"),
            build_filter("status", "Status", "equals", "Open"),
        ),
        canonical,
    )


def monthly_calendar(canonical: CanonicalDatabases) -> LinkedView:
    """A month calendar linked to the canonical Events database."""
    return build_linked_view("Dashboard", "Events", "calendar", "Month", (), canonical)


def quick_notes(canonical: CanonicalDatabases) -> LinkedView:
    """Quick notes linked to the canonical Notes database."""
    return build_linked_view("Dashboard", "Notes", "table", "Quick notes", (), canonical)


def build_notification_dashboard(canonical: object) -> NotificationDashboard:
    """Build the one-row dashboard relations and rollups."""
    if not isinstance(canonical, CanonicalDatabases):
        raise SchemaBuilderError("notification dashboard requires canonical databases")
    relations: list[DashboardRelation] = []
    rollups: list[DashboardRollup] = []
    for data_type, rollup_name, property_name, function in _DASHBOARD_LINKS:
        if data_type not in canonical.by_type:
            continue
        relations.append(DashboardRelation(name=data_type, data_type=data_type))
        rollups.append(
            DashboardRollup(
                name=rollup_name,
                relation_name=data_type,
                property_name=property_name,
                function=function,
            )
        )
    return NotificationDashboard(
        row_count=1,
        relations=tuple(relations),
        rollups=tuple(rollups),
    )


def _copy_filters(filters: object) -> tuple[ViewFilter, ...]:
    if isinstance(filters, str) or not isinstance(filters, Sequence):
        raise SchemaBuilderError("filters must be a sequence")
    raw = tuple(filters)
    if len(raw) > MAX_FILTERS:
        raise SchemaBuilderError("more than 3 filters is rejected")
    seen: set[str] = set()
    copied: list[ViewFilter] = []
    for item in raw:
        if not isinstance(item, ViewFilter):
            raise SchemaBuilderError("filter must be a view filter")
        if item.dimension in seen:
            raise SchemaBuilderError(f"filter dimension {item.dimension!r} is duplicated")
        seen.add(item.dimension)
        copied.append(item)
    return tuple(copied)
