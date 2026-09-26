"""Notification-dashboard formula generation.

Session 06 prompt heading "### 5. Implement formula and schema builders"
(``prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md``).

The service emits one formula per dashboard value. Each formula is attached to
a single catalogue database and may name only properties of that database.
Expressions are call-shaped (``prop``, ``if``, ``and``, ``or``, ``not``,
``empty``, ``now``, ``formatDate``, ``equal``, ``subtract``). ``equal`` and
``subtract`` are the only additions, and only the dashboard formulas use them.

A cross-row count or a rollup is out of scope. Session 07 section 4 names a
configured buyer name and does not name ``client_name``. That buyer name is
deferred to Session 07 and is not emitted here, and ``client_name`` is not
emitted either, so a verified map with no Clients database is valid.
``current_date`` is ``now()`` on Tasks. Notion evaluates now() and formatDate in the
viewer's local time zone, API reads return UTC, and 'today' can differ near
midnight. ``task_open_and_due_today`` is this Tasks row, not a count
of tasks, and it compares the Due calendar day to today. That per-row name is a justified
correction: a formula evaluates per row, and the count belongs in a section 6
rollup. ``birthday_status`` compares month and day so the Events row recurs
yearly. A February 29 birthday matches only when today is February 29, so
``Recurs yearly`` fires only in leap years. The expression does not special-case
that date. ``money_spent_today`` is this Finance row's amount when its calendar
date is today, otherwise 0, not a sum. A date property is never compared to
``now()`` directly. ``water_glasses_remaining`` is Goal minus Glasses on Habits
when that row's calendar date is today, otherwise 0, and is omitted when Habits
is not verified (water glasses only where relevant).
Any dashboard formula is omitted when its database is not in the verified map,
so each personal preset can be used alone. A key that is not in
``schema_definitions()`` is rejected. A known database that is simply absent
is still skipped, and an empty formula result is not an error.

Surrounding whitespace is rejected, so it does not count toward the 128
character limit. Characters inside the expression, including spaces between
arguments, do count. This module does not call Notion, the network, or a
browser, and it does not build relations, rollups, or views.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from .errors import SchemaBuilderError, UnverifiedPropertyNameError

MIN_FORMULA_LENGTH = 5
MAX_FORMULA_LENGTH = 128
MAX_FORMULA_DEPTH = 4
MAX_NAME_LENGTH = 64

ALLOWED_FORMULA_TYPES: frozenset[str] = frozenset({"text", "number", "checkbox", "date"})

_EXACT_ARITY: dict[str, int] = {
    "prop": 1,
    "now": 0,
    "not": 1,
    "empty": 1,
    "if": 3,
    "formatDate": 2,
    "equal": 2,
    "subtract": 2,
}
_AT_LEAST_TWO: frozenset[str] = frozenset({"and", "or"})
_PROPERTY_VALUE_TYPES: dict[str, str] = {
    "title": "text",
    "text": "text",
    "select": "text",
    "multi_select": "text",
    "url": "text",
    "email": "text",
    "number": "number",
    "date": "date",
    "checkbox": "checkbox",
}

# key, database, result type, expression.
_DASHBOARD: tuple[tuple[str, str, str, str], ...] = (
    ("current_date", "Tasks", "date", "now()"),
    (
        "task_open_and_due_today",
        "Tasks",
        "checkbox",
        'and(equal(prop("Status"), "Open"), '
        'equal(formatDate(prop("Due"), "YYYY-MM-DD"), formatDate(now(), "YYYY-MM-DD")))',
    ),
    (
        "birthday_status",
        "Events",
        "checkbox",
        'and(prop("Birthday"), '
        'equal(formatDate(prop("Date"), "MM-DD"), formatDate(now(), "MM-DD")))',
    ),
    (
        "money_spent_today",
        "Finance",
        "number",
        'if(equal(formatDate(prop("Date"), "YYYY-MM-DD"), formatDate(now(), "YYYY-MM-DD")), '
        'prop("Amount"), 0)',
    ),
    (
        "water_glasses_remaining",
        "Habits",
        "number",
        'if(equal(formatDate(prop("Date"), "YYYY-MM-DD"), formatDate(now(), "YYYY-MM-DD")), '
        'subtract(prop("Goal"), prop("Glasses")), 0)',
    ),
)
_EXPECTED_TYPES: dict[str, dict[str, str]] = {
    "Tasks": {"Status": "select", "Due": "date"},
    "Events": {"Birthday": "checkbox", "Date": "date"},
    "Finance": {"Date": "date", "Amount": "number"},
    "Habits": {"Date": "date", "Goal": "number", "Glasses": "number"},
}


@dataclass(frozen=True, slots=True)
class _Call:
    name: str
    args: tuple[_Node, ...]


@dataclass(frozen=True, slots=True)
class _Literal:
    text: str
    kind: Literal["string", "number"]


_Node = _Call | _Literal


@dataclass(frozen=True, slots=True)
class CompiledFormula:
    """One formula expression that passed the builder limits."""

    expression: str
    result_type: str
    referenced_property_names: frozenset[str]
    depth: int


@dataclass(frozen=True, slots=True)
class NotificationDashboardFormulas:
    """Formula expressions for the notification dashboard.

    ``verified_properties`` is a copy of the caller's per-database types.
    ``databases`` records the one database each formula is attached to.
    """

    expressions: Mapping[str, str]
    result_types: Mapping[str, str]
    databases: Mapping[str, str]
    verified_properties: Mapping[str, Mapping[str, str]]


_INVISIBLE_NAME_CHARACTERS = ("\u200b", "\ufeff", "\u200c", "\u200d", "\u2060", "\u00ad")


def _is_ascii_digit(char: str) -> bool:
    return "0" <= char <= "9"


def validated_name(label: str, value: object) -> str:
    """Return ``value`` when it is a usable schema or property name."""
    if not isinstance(value, str):
        raise SchemaBuilderError(f"{label} must be a string")
    if any(char in value for char in _INVISIBLE_NAME_CHARACTERS):
        raise SchemaBuilderError(f"{label} must not contain an invisible character")
    if value.strip() == "":
        raise SchemaBuilderError(f"{label} must not be empty")
    if value != value.strip():
        raise SchemaBuilderError(f"{label} must not have surrounding whitespace")
    if len(value) > MAX_NAME_LENGTH:
        raise SchemaBuilderError(f"{label} longer than 64 characters is rejected")
    return value


def formula_value_type(property_type: str) -> str:
    """Return the formula value type for a property type or formula result type."""
    mapped = _PROPERTY_VALUE_TYPES.get(property_type)
    if mapped is not None:
        return mapped
    if property_type in ALLOWED_FORMULA_TYPES:
        return property_type
    raise SchemaBuilderError(f"property type {property_type!r} has no formula value")


def compile_formula(
    expression: object,
    verified_properties: object,
    result_type: object,
) -> CompiledFormula:
    """Compile one formula. ``prop()`` names and types must be verified."""
    if not isinstance(expression, str):
        raise SchemaBuilderError("formula expression must be a string")
    if expression.strip() == "":
        raise SchemaBuilderError("formula expression must not be empty")
    if expression != expression.strip():
        raise SchemaBuilderError("formula expression must not have surrounding whitespace")
    if len(expression) < MIN_FORMULA_LENGTH:
        raise SchemaBuilderError("formula expression shorter than 5 characters is rejected")
    if len(expression) > MAX_FORMULA_LENGTH:
        raise SchemaBuilderError("formula expression longer than 128 characters is rejected")
    if not isinstance(result_type, str) or result_type not in ALLOWED_FORMULA_TYPES:
        raise SchemaBuilderError(f"formula type {result_type!r} is not allowed")
    verified = copy_verified_properties(verified_properties)
    node = _Parser(expression).parse()
    depth = _call_depth(node)
    if depth < 1:
        raise SchemaBuilderError("formula must be a function call")
    if depth > MAX_FORMULA_DEPTH:
        raise SchemaBuilderError("formula nesting deeper than 4 is rejected")
    referenced = _referenced_names(node)
    for name in sorted(referenced):
        if name not in verified:
            raise UnverifiedPropertyNameError(name)
    inferred = _infer_type(node, verified)
    if inferred != result_type:
        raise SchemaBuilderError(
            f"formula result type {result_type!r} does not match expression type {inferred!r}"
        )
    return CompiledFormula(
        expression=expression,
        result_type=result_type,
        referenced_property_names=referenced,
        depth=depth,
    )


def generate_notification_dashboard_formulas(
    verified_properties: object,
) -> NotificationDashboardFormulas:
    """Generate each dashboard formula from the properties of its own database.

    ``verified_properties`` maps a database kind to that database's property
    names and types. A property verified only on another database does not
    satisfy a formula. The stored mapping is a copy.
    """
    verified = copy_verified_databases(verified_properties)
    if len(verified) < 1:
        raise SchemaBuilderError("verified property names must not be empty")
    _require_known_databases(verified)
    expressions: dict[str, str] = {}
    result_types: dict[str, str] = {}
    databases: dict[str, str] = {}
    for key, database, result_type, expression in _DASHBOARD:
        if database not in verified:
            continue
        properties = verified[database]
        compiled = compile_formula(expression, properties, result_type)
        _require_catalogue_types(database, properties, compiled.referenced_property_names)
        expressions[key] = compiled.expression
        result_types[key] = compiled.result_type
        databases[key] = database
    frozen = {
        database: MappingProxyType(dict(properties)) for database, properties in verified.items()
    }
    return NotificationDashboardFormulas(
        expressions=MappingProxyType(expressions),
        result_types=MappingProxyType(result_types),
        databases=MappingProxyType(databases),
        verified_properties=MappingProxyType(frozen),
    )


def _require_known_databases(verified: Mapping[str, Mapping[str, str]]) -> None:
    """Reject a database key that is not a catalogue kind.

    ``schema_builder`` imports this module, so the catalogue is imported here.
    """
    from .schema_builder import schema_definitions

    known = tuple(schema_definitions())
    unknown = sorted(name for name in verified if name not in known)
    if not unknown:
        return
    listed = ", ".join(repr(name) for name in unknown)
    valid = ", ".join(known)
    raise SchemaBuilderError(f"unknown database {listed}; valid keys: {valid}")


def copy_verified_properties(verified_properties: object) -> dict[str, str]:
    """Copy one database's name-to-type mapping. Strings and sequences are rejected."""
    if isinstance(verified_properties, str) or not isinstance(verified_properties, Mapping):
        raise SchemaBuilderError("verified properties must be a mapping of names to types")
    copied: dict[str, str] = {}
    for name, type_name in verified_properties.items():
        if not isinstance(name, str) or not isinstance(type_name, str):
            raise SchemaBuilderError("verified properties must be strings")
        copied[name] = type_name
    return copied


def copy_verified_databases(verified_properties: object) -> dict[str, dict[str, str]]:
    """Copy a database-to-properties mapping."""
    if isinstance(verified_properties, str) or not isinstance(verified_properties, Mapping):
        raise SchemaBuilderError("verified properties must be a mapping of names to types")
    copied: dict[str, dict[str, str]] = {}
    for database, properties in verified_properties.items():
        if not isinstance(database, str):
            raise SchemaBuilderError("verified properties must be strings")
        copied[database] = copy_verified_properties(properties)
    return copied


def _require_catalogue_types(
    database: str,
    properties: Mapping[str, str],
    referenced: frozenset[str],
) -> None:
    expected = _EXPECTED_TYPES[database]
    for name in sorted(referenced):
        actual = properties[name]
        if actual != expected[name]:
            raise SchemaBuilderError(f"property {name!r} on {database} has type {actual!r}")


def _expect(actual: str, expected: str, label: str) -> None:
    if actual != expected:
        raise SchemaBuilderError(f"{label} requires {expected}, not {actual}")


def _infer_type(node: _Node, types: Mapping[str, str]) -> str:
    if isinstance(node, _Literal):
        if node.kind == "string":
            return "text"
        return "number"
    return _infer_call(node, types)


def _infer_call(node: _Call, types: Mapping[str, str]) -> str:
    name = node.name
    arg_types = tuple(_infer_type(arg, types) for arg in node.args)
    if name == "prop":
        argument = node.args[0]
        if not isinstance(argument, _Literal):
            raise SchemaBuilderError("prop() requires a string property name")
        return formula_value_type(types[argument.text])
    if name == "now":
        return "date"
    if name == "formatDate":
        _expect(arg_types[0], "date", "formatDate()")
        _expect(arg_types[1], "text", "formatDate()")
        return "text"
    if name == "not":
        _expect(arg_types[0], "checkbox", "not()")
        return "checkbox"
    if name == "empty":
        return "checkbox"
    if name in {"and", "or"}:
        for arg_type in arg_types:
            _expect(arg_type, "checkbox", f"{name}()")
        return "checkbox"
    if name == "if":
        _expect(arg_types[0], "checkbox", "if() condition")
        if arg_types[1] != arg_types[2]:
            raise SchemaBuilderError("if() branches must have the same type")
        return arg_types[1]
    if name == "equal":
        if arg_types[0] != arg_types[1]:
            raise SchemaBuilderError("equal() arguments must have the same type")
        return "checkbox"
    if name == "subtract":
        _expect(arg_types[0], "number", "subtract()")
        _expect(arg_types[1], "number", "subtract()")
        return "number"
    raise SchemaBuilderError(f"formula function {name!r} is not allowed")


def _call_depth(node: _Node) -> int:
    if isinstance(node, _Literal):
        return 0
    if not node.args:
        return 1
    return 1 + max(_call_depth(arg) for arg in node.args)


def _referenced_names(node: _Node) -> frozenset[str]:
    if isinstance(node, _Literal):
        return frozenset()
    names: set[str] = set()
    if node.name == "prop":
        argument = node.args[0]
        if not isinstance(argument, _Literal) or argument.kind != "string":
            raise SchemaBuilderError("prop() requires a string property name")
        names.add(validated_name("property name", argument.text))
    for argument in node.args:
        names.update(_referenced_names(argument))
    return frozenset(names)


class _Parser:
    def __init__(self, text: str) -> None:
        self._text = text
        self._i = 0

    def parse(self) -> _Node:
        node = self._parse_expr()
        self._skip()
        if self._i != len(self._text):
            raise SchemaBuilderError("formula has trailing input")
        return node

    def _skip(self) -> None:
        while self._i < len(self._text) and self._text[self._i].isspace():
            self._i += 1

    def _peek(self) -> str:
        self._skip()
        if self._i >= len(self._text):
            return ""
        return self._text[self._i]

    def _parse_expr(self) -> _Node:
        self._skip()
        if self._i >= len(self._text):
            raise SchemaBuilderError("formula expression ended early")
        char = self._text[self._i]
        if char == '"':
            return self._parse_string()
        if _is_ascii_digit(char):
            return self._parse_number()
        if char.isalpha() or char == "_":
            return self._parse_call()
        raise SchemaBuilderError("formula expression has an unexpected character")

    def _parse_string(self) -> _Literal:
        self._i += 1
        start = self._i
        while self._i < len(self._text) and self._text[self._i] != '"':
            if self._text[self._i] == "\\":
                raise SchemaBuilderError("formula strings cannot contain escapes")
            self._i += 1
        if self._i >= len(self._text):
            raise SchemaBuilderError("formula string is not closed")
        text = self._text[start : self._i]
        self._i += 1
        return _Literal(text=text, kind="string")

    def _parse_number(self) -> _Literal:
        start = self._i
        while self._i < len(self._text) and _is_ascii_digit(self._text[self._i]):
            self._i += 1
        return _Literal(text=self._text[start : self._i], kind="number")

    def _parse_call(self) -> _Call:
        start = self._i
        while self._i < len(self._text) and (
            self._text[self._i].isalnum() or self._text[self._i] == "_"
        ):
            self._i += 1
        name = self._text[start : self._i]
        if self._peek() != "(":
            raise SchemaBuilderError("formula must be a function call")
        self._i += 1
        args: list[_Node] = []
        if self._peek() != ")":
            while True:
                args.append(self._parse_expr())
                if self._peek() == ",":
                    self._i += 1
                    continue
                break
        if self._peek() != ")":
            raise SchemaBuilderError("formula call is not closed")
        self._i += 1
        _check_arity(name, len(args))
        return _Call(name=name, args=tuple(args))


def _check_arity(name: str, count: int) -> None:
    if name in _AT_LEAST_TWO:
        if count < 2:
            raise SchemaBuilderError(f"{name}() requires at least 2 arguments")
        return
    if name not in _EXACT_ARITY:
        raise SchemaBuilderError(f"formula function {name!r} is not allowed")
    expected = _EXACT_ARITY[name]
    if count != expected:
        raise SchemaBuilderError(f"{name}() requires {expected} arguments")
