"""Reusable Notion database schema builders.

Session 06 prompt heading "### 5. Implement formula and schema builders"
(``prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md``).

Each catalogue kind has its own typed definition: Tasks, Events, Habits,
Finance, Meals, Notes, and the business alternatives Clients, Projects,
Content, and Invoices. Definitions are separate records, not one agent prompt.
``build_schema`` is the reusable builder those records go through. It copies
caller input before validation. This module does not call Notion, the network,
or a browser.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from .errors import SchemaBuilderError
from .formulas import compile_formula, validated_name

MIN_PROPERTY_COUNT = 1
MAX_PROPERTY_COUNT = 12
MIN_OPTION_COUNT = 1
MAX_OPTION_COUNT = 8

ALLOWED_PROPERTY_TYPES: frozenset[str] = frozenset(
    {
        "title",
        "text",
        "number",
        "select",
        "multi_select",
        "date",
        "checkbox",
        "formula",
        "url",
        "email",
    }
)

DATABASE_KINDS: tuple[str, ...] = (
    "Tasks",
    "Events",
    "Habits",
    "Finance",
    "Meals",
    "Notes",
    "Clients",
    "Projects",
    "Content",
    "Invoices",
)

_OPTION_TYPES: frozenset[str] = frozenset({"select", "multi_select"})
_BUSINESS: frozenset[str] = frozenset({"Clients", "Projects", "Content", "Invoices"})
_PROPERTY_FIELDS: frozenset[str] = frozenset(
    {"name", "type", "options", "formula_expression", "formula_result_type"}
)
_FAMILIES: frozenset[str] = frozenset({"personal", "business"})


@dataclass(frozen=True, slots=True)
class SchemaProperty:
    """One database property. ``options`` is a copy, not the caller's list."""

    name: str
    type: str
    options: tuple[str, ...] = ()
    formula_expression: str | None = None
    formula_result_type: str | None = None


@dataclass(frozen=True, slots=True)
class DatabaseSchema:
    """A database schema produced by the builder."""

    name: str
    family: Literal["personal", "business"]
    properties: tuple[SchemaProperty, ...]


@dataclass(frozen=True, slots=True)
class _Draft:
    name: object
    type: object
    options: tuple[object, ...]
    formula_expression: object
    formula_result_type: object


def _field(
    name: str,
    type_name: str,
    options: tuple[str, ...] = (),
) -> Mapping[str, object]:
    return MappingProxyType({"name": name, "type": type_name, "options": options})


def _tasks() -> tuple[Mapping[str, object], ...]:
    return (
        _field("Name", "title"),
        _field("Status", "select", ("Open", "Done")),
        _field("Due", "date"),
    )


def _events() -> tuple[Mapping[str, object], ...]:
    return (
        _field("Name", "title"),
        _field("Date", "date"),
        _field("Birthday", "checkbox"),
    )


def _habits() -> tuple[Mapping[str, object], ...]:
    return (
        _field("Name", "title"),
        _field("Glasses", "number"),
        _field("Goal", "number"),
    )


def _finance() -> tuple[Mapping[str, object], ...]:
    return (
        _field("Name", "title"),
        _field("Amount", "number"),
        _field("Date", "date"),
    )


def _meals() -> tuple[Mapping[str, object], ...]:
    return (
        _field("Name", "title"),
        _field("Day", "date"),
    )


def _notes() -> tuple[Mapping[str, object], ...]:
    return (
        _field("Name", "title"),
        _field("Body", "text"),
    )


def _clients() -> tuple[Mapping[str, object], ...]:
    return (
        _field("Name", "title"),
        _field("Email", "email"),
    )


def _projects() -> tuple[Mapping[str, object], ...]:
    return (
        _field("Name", "title"),
        _field("Status", "select", ("Active", "Paused")),
    )


def _content() -> tuple[Mapping[str, object], ...]:
    return (
        _field("Name", "title"),
        _field("URL", "url"),
    )


def _invoices() -> tuple[Mapping[str, object], ...]:
    return (
        _field("Name", "title"),
        _field("Amount", "number"),
        _field("Status", "select", ("Draft", "Sent", "Paid")),
    )


_PRESETS: dict[str, Callable[[], tuple[Mapping[str, object], ...]]] = {
    "Tasks": _tasks,
    "Events": _events,
    "Habits": _habits,
    "Finance": _finance,
    "Meals": _meals,
    "Notes": _notes,
    "Clients": _clients,
    "Projects": _projects,
    "Content": _content,
    "Invoices": _invoices,
}


def build_schema(
    name: str,
    properties: Sequence[Mapping[str, object]],
    *,
    family: Literal["personal", "business"] = "personal",
) -> DatabaseSchema:
    """Build one database schema from caller-supplied property mappings.

    The property sequence and each options sequence are copied before checks.
    """
    schema_name = validated_name("database name", name)
    if family not in _FAMILIES:
        raise SchemaBuilderError(f"schema family {family!r} is not allowed")
    drafts = _copy_properties(properties)
    if len(drafts) < MIN_PROPERTY_COUNT:
        raise SchemaBuilderError("properties must not be empty")
    if len(drafts) > MAX_PROPERTY_COUNT:
        raise SchemaBuilderError("more than 12 properties is rejected")
    built = tuple(_build_property(draft) for draft in drafts)
    _require_unique_names(built)
    _require_one_title(built)
    compiled = _compile_formulas(built)
    return DatabaseSchema(name=schema_name, family=family, properties=compiled)


def build_database_schema(kind: str) -> DatabaseSchema:
    """Build the typed schema for one catalogue kind from the heading list."""
    validated_name("database kind", kind)
    factory = _PRESETS.get(kind)
    if factory is None:
        raise SchemaBuilderError(f"database kind {kind!r} is not a schema builder")
    family: Literal["personal", "business"] = "business" if kind in _BUSINESS else "personal"
    return build_schema(kind, factory(), family=family)


def schema_definitions() -> Mapping[str, DatabaseSchema]:
    """Return each catalogue kind as its own schema, not one agent prompt."""
    return MappingProxyType({kind: build_database_schema(kind) for kind in DATABASE_KINDS})


def _copy_properties(properties: object) -> tuple[_Draft, ...]:
    if isinstance(properties, str) or not isinstance(properties, Sequence):
        raise SchemaBuilderError("properties must be a sequence of mappings")
    drafts: list[_Draft] = []
    for item in properties:
        if not isinstance(item, Mapping):
            raise SchemaBuilderError("property must be a mapping")
        unknown = set(item) - _PROPERTY_FIELDS
        if unknown:
            field_name = sorted(unknown)[0]
            raise SchemaBuilderError(f"property field {field_name!r} is not allowed")
        drafts.append(
            _Draft(
                name=item.get("name"),
                type=item.get("type"),
                options=_copy_options(item.get("options", ())),
                formula_expression=item.get("formula_expression"),
                formula_result_type=item.get("formula_result_type"),
            )
        )
    return tuple(drafts)


def _copy_options(raw: object) -> tuple[object, ...]:
    if isinstance(raw, str) or not isinstance(raw, Sequence):
        raise SchemaBuilderError("options must be a sequence of strings")
    return tuple(raw)


def _build_property(draft: _Draft) -> SchemaProperty:
    name = validated_name("property name", draft.name)
    if not isinstance(draft.type, str):
        raise SchemaBuilderError("property type must be a string")
    property_type = draft.type
    if property_type not in ALLOWED_PROPERTY_TYPES:
        raise SchemaBuilderError(f"property type {property_type!r} is not allowed")
    options = _validate_options(property_type, draft.options)
    expression, result_type = _formula_fields(property_type, draft)
    return SchemaProperty(
        name=name,
        type=property_type,
        options=options,
        formula_expression=expression,
        formula_result_type=result_type,
    )


def _validate_options(property_type: str, raw_options: tuple[object, ...]) -> tuple[str, ...]:
    if property_type in _OPTION_TYPES:
        if len(raw_options) < MIN_OPTION_COUNT:
            raise SchemaBuilderError("select options must not be empty")
        if len(raw_options) > MAX_OPTION_COUNT:
            raise SchemaBuilderError("more than 8 options is rejected")
        for option in raw_options:
            validated_name("option name", option)
        if len(set(raw_options)) != len(raw_options):
            raise SchemaBuilderError("select options must be unique")
        # Return the copied tuple from _copy_options. Rebuilding it would hide
        # a missing copy of the caller's list.
        return raw_options  # type: ignore[return-value]
    if len(raw_options) > 0:
        raise SchemaBuilderError("options are only allowed on select and multi_select")
    return ()


def _formula_fields(property_type: str, draft: _Draft) -> tuple[str | None, str | None]:
    if property_type == "formula":
        return (
            _optional_text("formula expression", draft.formula_expression),
            _optional_text("formula result type", draft.formula_result_type),
        )
    if draft.formula_expression is not None:
        raise SchemaBuilderError("formula expression is only allowed on formula properties")
    if draft.formula_result_type is not None:
        raise SchemaBuilderError("formula result type is only allowed on formula properties")
    return None, None


def _optional_text(label: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SchemaBuilderError(f"{label} must be a string")
    return value


def _require_unique_names(properties: tuple[SchemaProperty, ...]) -> None:
    seen: set[str] = set()
    for prop in properties:
        if prop.name in seen:
            raise SchemaBuilderError(f"property name {prop.name!r} is duplicated")
        seen.add(prop.name)


def _require_one_title(properties: tuple[SchemaProperty, ...]) -> None:
    titles = [prop for prop in properties if prop.type == "title"]
    if len(titles) < 1:
        raise SchemaBuilderError("schema must contain a title property")
    if len(titles) > 1:
        raise SchemaBuilderError("schema must contain exactly one title property")


def _compile_formulas(properties: tuple[SchemaProperty, ...]) -> tuple[SchemaProperty, ...]:
    raw_types = {prop.name: _raw_type(prop) for prop in properties}
    formula_refs: dict[str, frozenset[str]] = {}
    compiled: list[SchemaProperty] = []
    for prop in properties:
        if prop.type != "formula":
            compiled.append(prop)
            continue
        expression = prop.formula_expression
        result_type = prop.formula_result_type
        if expression is None:
            raise SchemaBuilderError("formula property requires an expression")
        if result_type is None:
            raise SchemaBuilderError("formula property requires a result type")
        # Own name stays visible so prop("A") on A is a cycle, not an unverified name.
        siblings = dict(raw_types)
        formula = compile_formula(expression, siblings, result_type)
        formula_refs[prop.name] = formula.referenced_property_names
        compiled.append(
            SchemaProperty(
                name=prop.name,
                type=prop.type,
                options=prop.options,
                formula_expression=formula.expression,
                formula_result_type=formula.result_type,
            )
        )
    _require_acyclic_formulas(formula_refs)
    return tuple(compiled)


def _raw_type(prop: SchemaProperty) -> str:
    if prop.type == "formula":
        return prop.formula_result_type or ""
    return prop.type


def _require_acyclic_formulas(refs: Mapping[str, frozenset[str]]) -> None:
    done: set[str] = set()

    def visit(name: str, path: tuple[str, ...]) -> None:
        if name in path:
            joined = " -> ".join((*path, name))
            raise SchemaBuilderError(f"formula cycle {joined}")
        if name in done or name not in refs:
            return
        extended = (*path, name)
        for target in sorted(refs[name]):
            visit(target, extended)
        done.add(name)

    for name in refs:
        visit(name, ())
