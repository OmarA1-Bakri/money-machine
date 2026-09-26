"""Relation and linked-view helpers.

Session 06 prompt heading "### 6. Implement relation and linked-view helpers"
(``prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md``).

One catalogue data type has one canonical database. Hub views link to that
database; they do not create another store. Filters are date, category, or
status, and each filter property must exist on that database. The home
dashboard has a today view, a monthly calendar, and quick notes. The
notification dashboard is one row of relations and rollups over the Tasks,
Events, Finance, and Habits formulas from section 5. A missing database omits
its relation and rollup. The relation must include today's row, and the formula
contributes only today's row, so the rollup sum is today's value. Notion
evaluates now() and formatDate in the viewer's local time zone, API reads
return UTC, and 'today' can differ near midnight.
``client_name``, the configured buyer name, and ``current_date`` are not
relations. This module does not call Notion, the network, or a browser.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import cast

from .errors import SchemaBuilderError
from .formulas import generate_notification_dashboard_formulas, validated_name
from .schema_builder import DATABASE_KINDS, schema_definitions

MAX_FILTERS = 3
VIEW_TYPES: frozenset[str] = frozenset({"table", "calendar", "board"})
FILTER_DIMENSIONS: frozenset[str] = frozenset({"date", "category", "status"})
_DIMENSION_TYPES: dict[str, frozenset[str]] = {
    "date": frozenset({"date"}),
    "status": frozenset({"status", "select"}),
    "category": frozenset({"select"}),
}
_ROLLUP_FUNCTION_TYPES: dict[str, frozenset[str]] = {
    "checked": frozenset({"checkbox"}),
    "sum": frozenset({"number"}),
}
_CATALOGUE_KINDS: frozenset[str] = frozenset(DATABASE_KINDS)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PropertyFacts = tuple[str, tuple[str, ...], bool]

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

    def __post_init__(self) -> None:
        _require_catalogue_data_type(cast(object, self.data_type))


def _is_unknown_data_type(item: str) -> bool:
    if item not in _CATALOGUE_KINDS:  # noqa: SIM103
        return True
    return False


def _require_catalogue_data_type(value: object) -> None:
    if not isinstance(value, str) or _is_unknown_data_type(value):
        raise SchemaBuilderError(f"data type {value!r} is not canonical")


@dataclass(frozen=True, slots=True)
class CanonicalDatabases:
    """Canonical databases copied from the caller sequence."""

    data_types: tuple[str, ...]
    by_type: Mapping[str, CanonicalDatabase]

    def __post_init__(self) -> None:
        data_types = cast(object, self.data_types)
        if isinstance(data_types, str) or not isinstance(data_types, tuple):
            raise SchemaBuilderError("canonical data types must be a tuple")
        seen: set[str] = set()
        for item in data_types:
            _require_catalogue_data_type(item)
            if item in seen:
                raise SchemaBuilderError(f"data type {item!r} is repeated")
            seen.add(item)
        by_type = cast(object, self.by_type)
        if not isinstance(by_type, Mapping):
            raise SchemaBuilderError("canonical databases must be a mapping")
        copied: dict[str, CanonicalDatabase] = {}
        for key, database in by_type.items():
            if not isinstance(key, str) or _is_unknown_data_type(key):
                raise SchemaBuilderError(f"canonical key {key!r} is not canonical")
            if not isinstance(database, CanonicalDatabase):
                raise SchemaBuilderError("canonical entry must be a CanonicalDatabase")
            entry_type = cast(object, database.data_type)
            if not isinstance(entry_type, str) or _is_unknown_data_type(entry_type):
                raise SchemaBuilderError(f"entry data type {entry_type!r} is not canonical")
            if key != database.data_type:
                raise SchemaBuilderError(f"key {key!r} does not match entry {database.data_type!r}")
            copied[key] = database
        if set(copied) != seen:
            raise SchemaBuilderError("canonical database keys must match data types")
        object.__setattr__(self, "by_type", MappingProxyType(dict(copied)))


@dataclass(frozen=True, slots=True)
class ViewFilter:
    """One date, category, or status filter."""

    dimension: str
    property_name: str
    condition: str
    value: str

    def __post_init__(self) -> None:
        dimension = cast(object, self.dimension)
        if not isinstance(dimension, str) or dimension not in FILTER_DIMENSIONS:
            raise SchemaBuilderError(f"filter dimension {dimension!r} is not allowed")
        if self.condition != "equals":
            raise SchemaBuilderError("filter condition must be equals")
        validated_name("property name", self.property_name)
        validated_name("filter value", self.value)
        if dimension == "date":
            _require_date_filter_value(self.value)


def _require_date_filter_value(value: str) -> None:
    if value == "today" or _is_iso_date(value):
        return
    raise SchemaBuilderError(f"date filter value {value!r} must be today or an ISO date")


def _is_iso_date(value: str) -> bool:
    if _ISO_DATE.fullmatch(value) is None:
        return False
    return _is_calendar_date(value)


def _is_calendar_date(value: str) -> bool:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed.isoformat() == value


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
    """A relation from the one-row dashboard to one canonical database.

    The relation must include today's row. ``water_glasses_remaining`` contributes
    only today's row, so the rollup sum is today's value.
    """

    name: str
    data_type: str

    def __post_init__(self) -> None:
        validated_name("relation name", self.name)
        _require_catalogue_data_type(cast(object, self.data_type))


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

    def __post_init__(self) -> None:
        if type(self.row_count) is not int or self.row_count != 1:
            raise SchemaBuilderError("notification dashboard row count must be 1")
        relations = cast(object, self.relations)
        if isinstance(relations, str) or not isinstance(relations, tuple):
            raise SchemaBuilderError("notification dashboard relations must be a tuple")
        linked: list[DashboardRelation] = []
        for relation in relations:
            if not isinstance(relation, DashboardRelation):
                raise SchemaBuilderError(
                    "notification dashboard relation must be a DashboardRelation"
                )
            linked.append(relation)
        rollups = cast(object, self.rollups)
        if not isinstance(rollups, tuple):
            raise SchemaBuilderError("notification dashboard rollups must be a tuple")
        names = {relation.name for relation in linked}
        for rollup in rollups:
            if not isinstance(rollup, DashboardRollup):
                raise SchemaBuilderError("notification dashboard rollup must be a DashboardRollup")
            if rollup.relation_name not in names:
                raise SchemaBuilderError(
                    f"rollup relation {rollup.relation_name!r} does not match a dashboard relation"
                )


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
        if _is_unknown_data_type(item):
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
    return ViewFilter(
        dimension=cast(str, dimension),
        property_name=cast(str, property_name),
        condition=cast(str, condition),
        value=cast(str, value),
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
    copied = _copy_filters(filters)
    _require_view(data_type, view_type, copied)
    return LinkedView(
        hub=hub_name,
        data_type=data_type,
        view_type=view_type,
        name=view_name,
        filters=copied,
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


def build_dashboard_rollup(
    data_type: object,
    name: object,
    property_name: object,
    function: object,
) -> DashboardRollup:
    """Build one rollup whose source exists and whose function fits that type."""
    if not isinstance(data_type, str) or data_type not in DATABASE_KINDS:
        raise SchemaBuilderError(f"data type {data_type!r} is not canonical")
    if not isinstance(function, str):
        raise SchemaBuilderError("rollup function must be a string")
    rollup_name = validated_name("rollup name", name)
    source = validated_name("property name", property_name)
    _require_rollup(data_type, source, function)
    return DashboardRollup(
        name=rollup_name,
        relation_name=data_type,
        property_name=source,
        function=function,
    )


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
        rollups.append(build_dashboard_rollup(data_type, rollup_name, property_name, function))
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


def _catalogue_properties(data_type: str) -> dict[str, _PropertyFacts]:
    """Schema properties plus this data type's own dashboard formulas."""
    definitions = schema_definitions()
    schema = definitions[data_type]
    properties: dict[str, _PropertyFacts] = {
        prop.name: (prop.type, prop.options, False) for prop in schema.properties
    }
    verified = {
        kind: {prop.name: prop.type for prop in definition.properties}
        for kind, definition in definitions.items()
    }
    formulas = generate_notification_dashboard_formulas(verified)
    for key, result_type in formulas.result_types.items():
        if formulas.databases[key] == data_type:
            properties[key] = (result_type, (), True)
    return properties


def _require_view(data_type: str, view_type: str, filters: tuple[ViewFilter, ...]) -> None:
    properties = _catalogue_properties(data_type)
    if view_type == "calendar" and not any(
        type_name == "date" and not from_formula
        for type_name, _options, from_formula in properties.values()
    ):
        raise SchemaBuilderError(f"{data_type} has no date property for a calendar")
    for item in filters:
        _require_filter(data_type, item, properties)


def _require_filter(
    data_type: str,
    item: ViewFilter,
    properties: Mapping[str, _PropertyFacts],
) -> None:
    if item.property_name not in properties:
        raise SchemaBuilderError(f"property {item.property_name!r} is not on {data_type}")
    type_name, options, from_formula = properties[item.property_name]
    if type_name not in _DIMENSION_TYPES[item.dimension]:
        raise SchemaBuilderError(
            f"filter dimension {item.dimension!r} does not fit property type {type_name!r}"
        )
    if item.dimension == "date" and from_formula:
        raise SchemaBuilderError(f"date filter on formula {item.property_name!r} is not allowed")
    if item.dimension == "status" and item.value not in options:
        raise SchemaBuilderError(
            f"status value {item.value!r} is not an option of {item.property_name}"
        )
    if item.dimension == "category" and item.value not in options:
        raise SchemaBuilderError(
            f"category value {item.value!r} is not an option of {item.property_name}"
        )


def _require_rollup(data_type: str, property_name: str, function: str) -> None:
    properties = _catalogue_properties(data_type)
    if property_name not in properties:
        raise SchemaBuilderError(f"rollup property {property_name!r} is not on {data_type}")
    type_name, _options, _from_formula = properties[property_name]
    allowed = _ROLLUP_FUNCTION_TYPES.get(function)
    if allowed is None or type_name not in allowed:
        raise SchemaBuilderError(
            f"rollup function {function!r} does not fit property type {type_name!r}"
        )
