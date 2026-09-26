"""Notification-dashboard formula generation.

Session 06 prompt heading "### 5. Implement formula and schema builders"
(``prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md``).

The service emits formula expressions for the notification dashboard. Every
``prop()`` name must belong to the caller-supplied verified set. Expressions
are call-shaped (``prop``, ``if``, ``and``, ``or``, ``not``, ``empty``,
``now``, ``formatDate``). This module does not call Notion, the network, or a
browser, and it does not build relations, rollups, or views.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
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
}
_AT_LEAST_TWO: frozenset[str] = frozenset({"and", "or"})

# key, result type, expression. Property names are checked against the verified set.
_DASHBOARD: tuple[tuple[str, str, str], ...] = (
    ("buyer_name", "text", 'prop("Buyer Name")'),
    ("current_date", "date", 'prop("Today")'),
    (
        "open_tasks_due_today",
        "date",
        'if(prop("Status"), prop("Due"), prop("Today"))',
    ),
    ("birthday_status", "checkbox", 'prop("Birthday")'),
    ("money_spent_today", "number", 'prop("Amount")'),
    (
        "water_glasses_remaining",
        "number",
        'if(prop("Glasses"), prop("Goal"), prop("Glasses"))',
    ),
)


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

    ``verified_property_names`` is a copy taken at generation time.
    """

    expressions: Mapping[str, str]
    result_types: Mapping[str, str]
    verified_property_names: frozenset[str]


def validated_name(label: str, value: object) -> str:
    """Return ``value`` when it is a usable schema or property name."""
    if not isinstance(value, str):
        raise SchemaBuilderError(f"{label} must be a string")
    if value.strip() == "":
        raise SchemaBuilderError(f"{label} must not be empty")
    if value != value.strip():
        raise SchemaBuilderError(f"{label} must not have surrounding whitespace")
    if len(value) > MAX_NAME_LENGTH:
        raise SchemaBuilderError(f"{label} longer than 64 characters is rejected")
    return value


def compile_formula(
    expression: object,
    verified_property_names: object,
    result_type: object,
) -> CompiledFormula:
    """Compile one formula. ``prop()`` names must be in the verified set."""
    if not isinstance(expression, str):
        raise SchemaBuilderError("formula expression must be a string")
    if expression.strip() == "":
        raise SchemaBuilderError("formula expression must not be empty")
    if len(expression) < MIN_FORMULA_LENGTH:
        raise SchemaBuilderError("formula expression shorter than 5 characters is rejected")
    if len(expression) > MAX_FORMULA_LENGTH:
        raise SchemaBuilderError("formula expression longer than 128 characters is rejected")
    if not isinstance(result_type, str) or result_type not in ALLOWED_FORMULA_TYPES:
        raise SchemaBuilderError(f"formula type {result_type!r} is not allowed")
    verified = copy_verified_names(verified_property_names)
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
    return CompiledFormula(
        expression=expression,
        result_type=result_type,
        referenced_property_names=referenced,
        depth=depth,
    )


def generate_notification_dashboard_formulas(
    verified_property_names: object,
) -> NotificationDashboardFormulas:
    """Generate every notification-dashboard formula from verified property names.

    The caller passes the verified set. A name used by an expression and absent
    from that set raises ``UnverifiedPropertyNameError``. An empty set is rejected.
    The stored set is a copy, so later caller mutations do not change it.
    """
    verified = copy_verified_names(verified_property_names)
    if len(verified) < 1:
        raise SchemaBuilderError("verified property names must not be empty")
    expressions: dict[str, str] = {}
    result_types: dict[str, str] = {}
    for key, result_type, expression in _DASHBOARD:
        compiled = compile_formula(expression, verified, result_type)
        expressions[key] = compiled.expression
        result_types[key] = compiled.result_type
    return NotificationDashboardFormulas(
        expressions=MappingProxyType(expressions),
        result_types=MappingProxyType(result_types),
        verified_property_names=verified,
    )


def copy_verified_names(verified_property_names: object) -> frozenset[str]:
    """Copy caller names into a new set. Strings and mappings are rejected."""
    if isinstance(verified_property_names, str | Mapping) or not isinstance(
        verified_property_names, Collection
    ):
        raise SchemaBuilderError("verified property names must be a collection of strings")
    copied: set[str] = set()
    for name in verified_property_names:
        if not isinstance(name, str):
            raise SchemaBuilderError("verified property names must be strings")
        copied.add(name)
    return frozenset(copied)


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
        if char.isdigit():
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
        while self._i < len(self._text) and self._text[self._i].isdigit():
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
