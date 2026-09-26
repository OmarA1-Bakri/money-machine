"""Notification-dashboard formula builder from Session 06 prompt section 5.

No network, no Notion, no browser.
"""

from __future__ import annotations

from typing import cast

import pytest

from money_machine.integrations.notion.errors import (
    SchemaBuilderError,
    UnverifiedPropertyNameError,
)
from money_machine.integrations.notion.formulas import (
    compile_formula,
    generate_notification_dashboard_formulas,
)
from money_machine.integrations.notion.schema_builder import build_schema

_VERIFIED = [
    "Buyer Name",
    "Today",
    "Status",
    "Due",
    "Birthday",
    "Amount",
    "Glasses",
    "Goal",
]

_ALLOWED_FORMULA_TYPES = ("text", "number", "checkbox", "date")


def _depth_expr(depth: int) -> str:
    expression = 'prop("Name")'
    for _ in range(depth - 1):
        expression = f"not({expression})"
    return expression


def _length_expr(length: int) -> str:
    base = "now()"
    return base + (" " * (length - len(base)))


def test_dashboard_formulas_use_verified_property_names() -> None:
    generated = generate_notification_dashboard_formulas(_VERIFIED)
    assert list(generated.expressions) == [
        "buyer_name",
        "current_date",
        "open_tasks_due_today",
        "birthday_status",
        "money_spent_today",
        "water_glasses_remaining",
    ]
    assert generated.expressions["buyer_name"] == 'prop("Buyer Name")'
    assert generated.expressions["current_date"] == 'prop("Today")'
    assert generated.expressions["open_tasks_due_today"] == (
        'if(prop("Status"), prop("Due"), prop("Today"))'
    )
    assert generated.expressions["birthday_status"] == 'prop("Birthday")'
    assert generated.expressions["money_spent_today"] == 'prop("Amount")'
    assert generated.expressions["water_glasses_remaining"] == (
        'if(prop("Glasses"), prop("Goal"), prop("Glasses"))'
    )
    assert dict(generated.result_types) == {
        "buyer_name": "text",
        "current_date": "date",
        "open_tasks_due_today": "date",
        "birthday_status": "checkbox",
        "money_spent_today": "number",
        "water_glasses_remaining": "number",
    }
    assert generated.verified_property_names == frozenset(_VERIFIED)


def test_missing_verified_name_is_rejected() -> None:
    names = [name for name in _VERIFIED if name != "Goal"]
    with pytest.raises(UnverifiedPropertyNameError, match="Goal") as raised:
        generate_notification_dashboard_formulas(names)
    assert raised.value.property_name == "Goal"


def test_empty_verified_names_are_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="must not be empty"):
        generate_notification_dashboard_formulas([])


def test_verified_names_reject_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="collection of strings"):
        generate_notification_dashboard_formulas(cast(list[str], "Buyer Name"))


def test_verified_names_reject_a_mapping() -> None:
    with pytest.raises(SchemaBuilderError, match="collection of strings"):
        generate_notification_dashboard_formulas(cast(list[str], {"Buyer Name": "text"}))


def test_verified_names_must_be_strings() -> None:
    with pytest.raises(SchemaBuilderError, match="must be strings"):
        compile_formula('prop("A")', cast(list[str], ["A", 1]), "text")


def test_extra_verified_name_is_not_copied_into_the_expression() -> None:
    generated = generate_notification_dashboard_formulas([*_VERIFIED, "Secret"])
    assert "Secret" in generated.verified_property_names
    for expression in generated.expressions.values():
        assert "Secret" not in expression


def test_caller_verified_names_are_isolated() -> None:
    names = list(_VERIFIED)
    generated = generate_notification_dashboard_formulas(names)
    names.append("Injected")
    names[0] = "Changed"
    assert "Injected" not in generated.verified_property_names
    assert "Buyer Name" in generated.verified_property_names
    assert generated.expressions["buyer_name"] == 'prop("Buyer Name")'


def test_caller_verified_set_is_isolated() -> None:
    names = set(_VERIFIED)
    generated = generate_notification_dashboard_formulas(names)
    names.add("Injected")
    assert "Injected" not in generated.verified_property_names


def test_dashboard_mappings_are_immutable() -> None:
    generated = generate_notification_dashboard_formulas(_VERIFIED)
    with pytest.raises(TypeError):
        cast(dict[str, str], generated.expressions)["buyer_name"] = "nope"
    with pytest.raises(TypeError):
        cast(dict[str, str], generated.result_types)["buyer_name"] = "number"


def test_referenced_names_are_the_prop_names_only() -> None:
    compiled = compile_formula('prop("A")', ["A", "B"], "text")
    assert compiled.referenced_property_names == frozenset({"A"})
    assert compiled.expression == 'prop("A")'


@pytest.mark.parametrize("result_type", _ALLOWED_FORMULA_TYPES)
def test_allowed_formula_type_is_accepted(result_type: str) -> None:
    compiled = compile_formula('prop("Name")', ["Name"], result_type)
    assert compiled.result_type == result_type


@pytest.mark.parametrize("result_type", ["select", "rollup", "Text", ""])
def test_disallowed_formula_type_is_rejected(result_type: str) -> None:
    with pytest.raises(SchemaBuilderError, match="is not allowed"):
        compile_formula('prop("Name")', ["Name"], result_type)


def test_formula_expression_must_be_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="formula expression must be a string"):
        compile_formula(cast(str, 1), ["Name"], "text")


def test_empty_formula_expression_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="must not be empty"):
        compile_formula("   ", [], "text")


@pytest.mark.parametrize("length", [5, 6, 127, 128])
def test_formula_length_within_limit(length: int) -> None:
    compiled = compile_formula(_length_expr(length), [], "date")
    assert len(compiled.expression) == length
    assert compiled.depth == 1


def test_formula_length_one_under_min_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="shorter than 5"):
        compile_formula("now(", [], "date")


def test_formula_length_one_past_max_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="longer than 128"):
        compile_formula(_length_expr(129), [], "date")


def test_formula_literal_depth_zero_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="function call"):
        compile_formula('"hello"', [], "text")


@pytest.mark.parametrize("depth", [1, 2, 3, 4])
def test_formula_depth_within_limit(depth: int) -> None:
    compiled = compile_formula(_depth_expr(depth), ["Name"], "text")
    assert compiled.depth == depth


def test_formula_depth_one_past_limit_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="deeper than 4"):
        compile_formula(_depth_expr(5), ["Name"], "text")


def test_now_call_is_accepted_at_depth_one() -> None:
    compiled = compile_formula("now()", [], "date")
    assert compiled.depth == 1
    assert compiled.referenced_property_names == frozenset()


def test_prop_name_length_accepts_64_and_rejects_65() -> None:
    accepted = "N" * 64
    compiled = compile_formula(f'prop("{accepted}")', [accepted], "text")
    assert compiled.referenced_property_names == frozenset({accepted})
    rejected = "N" * 65
    with pytest.raises(SchemaBuilderError, match="property name longer than 64"):
        compile_formula(f'prop("{rejected}")', [rejected], "text")


def test_empty_prop_name_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="property name must not be empty"):
        compile_formula('prop("")', [""], "text")


def test_prop_name_whitespace_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="surrounding whitespace"):
        compile_formula('prop(" Name")', [" Name"], "text")


def test_unverified_prop_name_is_rejected() -> None:
    with pytest.raises(UnverifiedPropertyNameError, match="Missing") as raised:
        compile_formula('prop("Missing")', ["Other"], "text")
    assert raised.value.property_name == "Missing"


def test_prop_rejects_two_arguments() -> None:
    with pytest.raises(SchemaBuilderError, match=r"prop\(\) requires 1 arguments"):
        compile_formula('prop("A", "B")', ["A", "B"], "text")


def test_prop_requires_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="string property name"):
        compile_formula("prop(1)", ["1"], "text")


def test_if_rejects_two_arguments() -> None:
    with pytest.raises(SchemaBuilderError, match=r"if\(\) requires 3 arguments"):
        compile_formula('if(prop("A"), prop("B"))', ["A", "B"], "text")


def test_and_rejects_one_argument() -> None:
    with pytest.raises(SchemaBuilderError, match=r"and\(\) requires at least 2"):
        compile_formula('and(prop("A"))', ["A"], "checkbox")


def test_now_rejects_an_argument() -> None:
    with pytest.raises(SchemaBuilderError, match=r"now\(\) requires 0 arguments"):
        compile_formula("now(1)", [], "date")


def test_unknown_function_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="not allowed"):
        compile_formula("foo()", [], "text")


def test_trailing_input_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="trailing input"):
        compile_formula("now() x", [], "date")


def test_unclosed_string_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="string is not closed"):
        compile_formula('prop("ABC)', ["ABC"], "text")


def test_unclosed_call_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="call is not closed"):
        compile_formula('prop("ABC"', ["ABC"], "text")


def test_formula_string_escape_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="escapes"):
        compile_formula('prop("A\\\\")', ["A"], "text")


def test_format_date_and_empty_are_accepted() -> None:
    expression = 'empty(formatDate(prop("Due"), "YYYY-MM-DD"))'
    compiled = compile_formula(expression, ["Due"], "checkbox")
    assert compiled.depth == 3
    assert compiled.referenced_property_names == frozenset({"Due"})


def test_or_accepts_two_arguments() -> None:
    compiled = compile_formula('or(prop("A"), prop("B"))', ["A", "B"], "checkbox")
    assert compiled.depth == 2


def _title() -> dict[str, object]:
    return {"name": "Name", "type": "title"}


def test_formula_property_uses_sibling_names() -> None:
    properties = [
        _title(),
        {
            "name": "Soon",
            "type": "formula",
            "formula_expression": 'prop("Name")',
            "formula_result_type": "text",
        },
    ]
    schema = build_schema("Tasks", properties)
    soon = schema.properties[1]
    assert soon.formula_expression == 'prop("Name")'
    assert soon.formula_result_type == "text"


def test_formula_property_rejects_an_unverified_name() -> None:
    properties = [
        _title(),
        {
            "name": "Flag",
            "type": "formula",
            "formula_expression": 'prop("Missing")',
            "formula_result_type": "checkbox",
        },
    ]
    with pytest.raises(UnverifiedPropertyNameError, match="Missing") as raised:
        build_schema("Tasks", properties)
    assert raised.value.property_name == "Missing"
    assert isinstance(raised.value, SchemaBuilderError)


def test_formula_property_rejects_its_own_name() -> None:
    properties = [
        _title(),
        {
            "name": "Flag",
            "type": "formula",
            "formula_expression": 'prop("Flag")',
            "formula_result_type": "checkbox",
        },
    ]
    with pytest.raises(UnverifiedPropertyNameError, match="Flag"):
        build_schema("Tasks", properties)


def test_formula_property_requires_an_expression() -> None:
    properties = [
        _title(),
        {"name": "Flag", "type": "formula", "formula_result_type": "text"},
    ]
    with pytest.raises(SchemaBuilderError, match="requires an expression"):
        build_schema("Tasks", properties)


def test_formula_property_requires_a_result_type() -> None:
    properties = [
        _title(),
        {"name": "Flag", "type": "formula", "formula_expression": 'prop("Name")'},
    ]
    with pytest.raises(SchemaBuilderError, match="requires a result type"):
        build_schema("Tasks", properties)


def test_schema_empty_formula_expression_is_rejected() -> None:
    properties = [
        _title(),
        {
            "name": "Flag",
            "type": "formula",
            "formula_expression": "   ",
            "formula_result_type": "text",
        },
    ]
    with pytest.raises(SchemaBuilderError, match="must not be empty"):
        build_schema("Tasks", properties)


def test_formula_expression_on_text_is_rejected() -> None:
    properties = [
        _title(),
        {"name": "Note", "type": "text", "formula_expression": 'prop("Name")'},
    ]
    with pytest.raises(SchemaBuilderError, match="only allowed on formula"):
        build_schema("Tasks", properties)


def test_formula_result_type_on_text_is_rejected() -> None:
    properties = [_title(), {"name": "Note", "type": "text", "formula_result_type": "text"}]
    with pytest.raises(SchemaBuilderError, match="result type is only allowed"):
        build_schema("Tasks", properties)


def test_schema_formula_expression_must_be_a_string() -> None:
    properties = [
        _title(),
        {
            "name": "Flag",
            "type": "formula",
            "formula_expression": 1,
            "formula_result_type": "text",
        },
    ]
    with pytest.raises(SchemaBuilderError, match="formula expression must be a string"):
        build_schema("Tasks", properties)


def test_formula_result_type_must_be_a_string() -> None:
    properties = [
        _title(),
        {
            "name": "Flag",
            "type": "formula",
            "formula_expression": 'prop("Name")',
            "formula_result_type": 1,
        },
    ]
    with pytest.raises(SchemaBuilderError, match="formula result type must be a string"):
        build_schema("Tasks", properties)
