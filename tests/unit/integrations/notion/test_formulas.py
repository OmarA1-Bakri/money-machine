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

_VERIFIED: dict[str, dict[str, str]] = {
    "Clients": {"Name": "title"},
    "Tasks": {"Name": "title", "Status": "select", "Due": "date"},
    "Events": {"Name": "title", "Date": "date", "Birthday": "checkbox"},
    "Finance": {"Name": "title", "Amount": "number", "Date": "date"},
    "Habits": {"Name": "title", "Glasses": "number", "Goal": "number"},
}

_ALLOWED_FORMULA_TYPES = ("text", "number", "checkbox", "date")
_TYPE_CASES = {
    "text": ('prop("Name")', {"Name": "text"}),
    "number": ('prop("Amount")', {"Amount": "number"}),
    "checkbox": ('prop("Flag")', {"Flag": "checkbox"}),
    "date": ("now()", {}),
}


def _verified_copy() -> dict[str, dict[str, str]]:
    return {database: dict(properties) for database, properties in _VERIFIED.items()}


def _depth_expr(depth: int) -> str:
    expression = 'prop("Flag")'
    for _ in range(depth - 1):
        expression = f"not({expression})"
    return expression


def _length_expr(length: int) -> tuple[str, dict[str, str], str]:
    if length == 5:
        return "now()", {}, "date"
    prefix = 'formatDate(now(), "'
    suffix = '")'
    return prefix + ("Y" * (length - len(prefix) - len(suffix))) + suffix, {}, "text"


def test_dashboard_formulas_use_verified_property_names() -> None:
    generated = generate_notification_dashboard_formulas(_VERIFIED)
    assert list(generated.expressions) == [
        "client_name",
        "current_date",
        "task_open_and_due_today",
        "birthday_status",
        "money_spent_today",
        "water_glasses_remaining",
    ]
    assert generated.expressions["client_name"] == 'prop("Name")'
    assert generated.expressions["current_date"] == "now()"
    assert generated.expressions["task_open_and_due_today"] == (
        'and(equal(prop("Status"), "Open"), equal(prop("Due"), now()))'
    )
    assert generated.expressions["birthday_status"] == (
        'and(prop("Birthday"), equal(prop("Date"), now()))'
    )
    assert generated.expressions["money_spent_today"] == (
        'if(equal(prop("Date"), now()), prop("Amount"), 0)'
    )
    assert (
        generated.expressions["water_glasses_remaining"]
        == 'subtract(prop("Goal"), prop("Glasses"))'
    )
    assert dict(generated.result_types) == {
        "client_name": "text",
        "current_date": "date",
        "task_open_and_due_today": "checkbox",
        "birthday_status": "checkbox",
        "money_spent_today": "number",
        "water_glasses_remaining": "number",
    }
    assert dict(generated.databases) == {
        "client_name": "Clients",
        "current_date": "Tasks",
        "task_open_and_due_today": "Tasks",
        "birthday_status": "Events",
        "money_spent_today": "Finance",
        "water_glasses_remaining": "Habits",
    }
    assert generated.verified_properties["Clients"]["Name"] == "title"
    assert generated.verified_properties["Habits"]["Goal"] == "number"


def test_missing_verified_name_is_rejected() -> None:
    names = _verified_copy()
    del names["Habits"]["Goal"]
    with pytest.raises(UnverifiedPropertyNameError, match="Goal") as raised:
        generate_notification_dashboard_formulas(names)
    assert raised.value.property_name == "Goal"


def test_cross_database_property_is_rejected() -> None:
    names = _verified_copy()
    names["Finance"]["Due"] = names["Tasks"].pop("Due")
    with pytest.raises(UnverifiedPropertyNameError, match="Due") as raised:
        generate_notification_dashboard_formulas(names)
    assert raised.value.property_name == "Due"


def test_dashboard_property_type_must_match_the_catalogue() -> None:
    names = _verified_copy()
    names["Tasks"]["Status"] = "text"
    with pytest.raises(SchemaBuilderError, match="Status"):
        generate_notification_dashboard_formulas(names)


def test_empty_verified_names_are_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="must not be empty"):
        generate_notification_dashboard_formulas({})


def test_verified_names_reject_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="mapping of names to types"):
        generate_notification_dashboard_formulas(cast(dict[str, dict[str, str]], "Buyer Name"))


def test_verified_properties_reject_a_list() -> None:
    listed = list(_VERIFIED.items())
    with pytest.raises(SchemaBuilderError, match="mapping of names to types"):
        generate_notification_dashboard_formulas(cast(dict[str, dict[str, str]], listed))


def test_verified_names_must_be_strings() -> None:
    with pytest.raises(SchemaBuilderError, match="must be strings"):
        compile_formula('prop("A")', {"A": 1}, "text")


def test_extra_verified_name_is_not_copied_into_the_expression() -> None:
    names = _verified_copy()
    names["Habits"]["Secret"] = "text"
    generated = generate_notification_dashboard_formulas(names)
    assert generated.verified_properties["Habits"]["Secret"] == "text"
    for expression in generated.expressions.values():
        assert "Secret" not in expression


def test_caller_verified_names_are_isolated() -> None:
    names = _verified_copy()
    generated = generate_notification_dashboard_formulas(names)
    names["Habits"]["Injected"] = "text"
    names["Clients"]["Name"] = "text"
    assert "Injected" not in generated.verified_properties["Habits"]
    assert generated.verified_properties["Clients"]["Name"] == "title"
    assert generated.expressions["client_name"] == 'prop("Name")'


def test_caller_verified_set_is_isolated() -> None:
    names = _verified_copy()
    generated = generate_notification_dashboard_formulas(names)
    names["Notes"] = {"Body": "text"}
    assert "Notes" not in generated.verified_properties


def test_dashboard_mappings_are_immutable() -> None:
    generated = generate_notification_dashboard_formulas(_VERIFIED)
    with pytest.raises(TypeError):
        cast(dict[str, str], generated.expressions)["client_name"] = "nope"
    with pytest.raises(TypeError):
        cast(dict[str, str], generated.result_types)["client_name"] = "number"
    with pytest.raises(TypeError):
        cast(dict[str, str], generated.databases)["client_name"] = "Tasks"
    with pytest.raises(TypeError):
        cast(dict[str, str], generated.verified_properties["Clients"])["Name"] = "text"


def test_referenced_names_are_the_prop_names_only() -> None:
    compiled = compile_formula('prop("A")', {"A": "text", "B": "text"}, "text")
    assert compiled.referenced_property_names == frozenset({"A"})
    assert compiled.expression == 'prop("A")'


def test_result_type_must_match_the_expression() -> None:
    with pytest.raises(SchemaBuilderError, match="does not match expression type 'text'"):
        compile_formula('prop("Name")', {"Name": "title"}, "number")


def test_prop_uses_the_verified_type() -> None:
    compiled = compile_formula('prop("Amount")', {"Amount": "number"}, "number")
    assert compiled.result_type == "number"


def test_if_condition_must_be_checkbox() -> None:
    with pytest.raises(SchemaBuilderError, match="if\\(\\) condition"):
        compile_formula(
            'if(prop("Status"), prop("Due"), prop("Due"))',
            {"Status": "select", "Due": "date"},
            "date",
        )


def test_if_branches_must_have_the_same_type() -> None:
    with pytest.raises(SchemaBuilderError, match="branches must have the same type"):
        compile_formula(
            'if(prop("Flag"), prop("Amount"), prop("Name"))',
            {"Flag": "checkbox", "Amount": "number", "Name": "text"},
            "number",
        )


def test_equal_rejects_different_types() -> None:
    with pytest.raises(SchemaBuilderError, match="equal\\(\\) arguments"):
        compile_formula('equal(prop("Status"), 1)', {"Status": "select"}, "checkbox")


def test_subtract_rejects_a_non_number() -> None:
    with pytest.raises(SchemaBuilderError, match="subtract\\(\\)"):
        compile_formula(
            'subtract(prop("Name"), prop("Glasses"))',
            {"Name": "title", "Glasses": "number"},
            "number",
        )


@pytest.mark.parametrize("result_type", _ALLOWED_FORMULA_TYPES)
def test_allowed_formula_type_is_accepted(result_type: str) -> None:
    expression, verified = _TYPE_CASES[result_type]
    compiled = compile_formula(expression, verified, result_type)
    assert compiled.result_type == result_type


@pytest.mark.parametrize("result_type", ["select", "rollup", "Text", ""])
def test_disallowed_formula_type_is_rejected(result_type: str) -> None:
    with pytest.raises(SchemaBuilderError, match="is not allowed"):
        compile_formula('prop("Name")', {"Name": "text"}, result_type)


def test_formula_expression_must_be_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="formula expression must be a string"):
        compile_formula(cast(str, 1), {"Name": "text"}, "text")


def test_empty_formula_expression_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="must not be empty"):
        compile_formula("   ", {}, "text")


def test_formula_surrounding_whitespace_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="surrounding whitespace"):
        compile_formula("now() ", {}, "date")
    with pytest.raises(SchemaBuilderError, match="surrounding whitespace"):
        compile_formula(" now()", {}, "date")


@pytest.mark.parametrize("length", [5, 127, 128])
def test_formula_length_within_limit(length: int) -> None:
    expression, verified, result_type = _length_expr(length)
    compiled = compile_formula(expression, verified, result_type)
    assert len(compiled.expression) == length
    assert " " * 8 not in compiled.expression


def test_formula_length_one_under_min_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="shorter than 5"):
        compile_formula("now(", {}, "date")


def test_formula_length_one_past_max_is_rejected() -> None:
    expression, verified, result_type = _length_expr(129)
    with pytest.raises(SchemaBuilderError, match="longer than 128"):
        compile_formula(expression, verified, result_type)


def test_formula_literal_depth_zero_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="function call"):
        compile_formula('"hello"', {}, "text")


@pytest.mark.parametrize("depth", [1, 2, 3, 4])
def test_formula_depth_within_limit(depth: int) -> None:
    compiled = compile_formula(_depth_expr(depth), {"Flag": "checkbox"}, "checkbox")
    assert compiled.depth == depth


def test_formula_depth_one_past_limit_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="deeper than 4"):
        compile_formula(_depth_expr(5), {"Flag": "checkbox"}, "checkbox")


def test_now_call_is_accepted_at_depth_one() -> None:
    compiled = compile_formula("now()", {}, "date")
    assert compiled.depth == 1
    assert compiled.referenced_property_names == frozenset()


def test_prop_name_length_accepts_64_and_rejects_65() -> None:
    accepted = "N" * 64
    compiled = compile_formula(f'prop("{accepted}")', {accepted: "text"}, "text")
    assert compiled.referenced_property_names == frozenset({accepted})
    rejected = "N" * 65
    with pytest.raises(SchemaBuilderError, match="property name longer than 64"):
        compile_formula(f'prop("{rejected}")', {rejected: "text"}, "text")


def test_empty_prop_name_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="property name must not be empty"):
        compile_formula('prop("")', {"": "text"}, "text")


def test_prop_name_whitespace_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="surrounding whitespace"):
        compile_formula('prop(" Name")', {" Name": "text"}, "text")


def test_unverified_prop_name_is_rejected() -> None:
    with pytest.raises(UnverifiedPropertyNameError, match="Missing") as raised:
        compile_formula('prop("Missing")', {"Other": "text"}, "text")
    assert raised.value.property_name == "Missing"


def test_prop_rejects_two_arguments() -> None:
    with pytest.raises(SchemaBuilderError, match=r"prop\(\) requires 1 arguments"):
        compile_formula('prop("A", "B")', {"A": "text", "B": "text"}, "text")


def test_prop_requires_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="string property name"):
        compile_formula("prop(1)", {"1": "text"}, "text")


def test_if_rejects_two_arguments() -> None:
    with pytest.raises(SchemaBuilderError, match=r"if\(\) requires 3 arguments"):
        compile_formula('if(prop("A"), prop("B"))', {"A": "checkbox", "B": "text"}, "text")


def test_and_rejects_one_argument() -> None:
    with pytest.raises(SchemaBuilderError, match=r"and\(\) requires at least 2"):
        compile_formula('and(prop("A"))', {"A": "checkbox"}, "checkbox")


def test_now_rejects_an_argument() -> None:
    with pytest.raises(SchemaBuilderError, match=r"now\(\) requires 0 arguments"):
        compile_formula("now(1)", {}, "date")


def test_unknown_function_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="not allowed"):
        compile_formula("foo()", {}, "text")


def test_trailing_input_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="trailing input"):
        compile_formula("now() x", {}, "date")


def test_unclosed_string_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="string is not closed"):
        compile_formula('prop("ABC)', {"ABC": "text"}, "text")


def test_unclosed_call_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="call is not closed"):
        compile_formula('prop("ABC"', {"ABC": "text"}, "text")


def test_formula_string_escape_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="escapes"):
        compile_formula('prop("A\\\\")', {"A": "text"}, "text")


def test_format_date_and_empty_are_accepted() -> None:
    expression = 'empty(formatDate(prop("Due"), "YYYY-MM-DD"))'
    compiled = compile_formula(expression, {"Due": "date"}, "checkbox")
    assert compiled.depth == 3
    assert compiled.referenced_property_names == frozenset({"Due"})


def test_or_accepts_two_arguments() -> None:
    compiled = compile_formula(
        'or(prop("A"), prop("B"))',
        {"A": "checkbox", "B": "checkbox"},
        "checkbox",
    )
    assert compiled.depth == 2


def _title() -> dict[str, object]:
    return {"name": "Name", "type": "title"}


def test_schema_formula_expression_must_be_a_string() -> None:
    properties = [
        _title(),
        {"name": "Flag", "type": "formula", "formula_expression": 1, "formula_result_type": "text"},
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
