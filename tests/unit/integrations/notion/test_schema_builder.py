"""Catalogue schema builders from Session 06 prompt section 5.

No network, no Notion, no browser.
"""

from __future__ import annotations

from typing import cast

import pytest

from money_machine.integrations.notion.errors import SchemaBuilderError
from money_machine.integrations.notion.schema_builder import (
    DATABASE_KINDS,
    build_database_schema,
    build_schema,
    schema_definitions,
)

_CatalogueRow = tuple[str, tuple[tuple[str, str, tuple[str, ...]], ...]]

_CATALOGUE: dict[str, _CatalogueRow] = {
    "Tasks": (
        "personal",
        (
            ("Name", "title", ()),
            ("Status", "select", ("Open", "Done")),
            ("Due", "date", ()),
        ),
    ),
    "Events": (
        "personal",
        (
            ("Name", "title", ()),
            ("Date", "date", ()),
            ("Birthday", "checkbox", ()),
        ),
    ),
    "Habits": (
        "personal",
        (
            ("Name", "title", ()),
            ("Glasses", "number", ()),
            ("Goal", "number", ()),
        ),
    ),
    "Finance": (
        "personal",
        (
            ("Name", "title", ()),
            ("Amount", "number", ()),
            ("Date", "date", ()),
        ),
    ),
    "Meals": (
        "personal",
        (("Name", "title", ()), ("Day", "date", ())),
    ),
    "Notes": (
        "personal",
        (("Name", "title", ()), ("Body", "text", ())),
    ),
    "Clients": (
        "business",
        (("Name", "title", ()), ("Email", "email", ())),
    ),
    "Projects": (
        "business",
        (
            ("Name", "title", ()),
            ("Status", "select", ("Active", "Paused")),
        ),
    ),
    "Content": (
        "business",
        (("Name", "title", ()), ("URL", "url", ())),
    ),
    "Invoices": (
        "business",
        (
            ("Name", "title", ()),
            ("Amount", "number", ()),
            ("Status", "select", ("Draft", "Sent", "Paid")),
        ),
    ),
}

_ALLOWED_PROPERTY_TYPES = (
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
)


def _title(name: str = "Name") -> dict[str, object]:
    return {"name": name, "type": "title"}


def _properties(count: int) -> list[dict[str, object]]:
    properties = [_title()]
    for index in range(count - 1):
        properties.append({"name": f"P{index}", "type": "text"})
    return properties


def _select(option_count: int, *, type_name: str = "select") -> list[dict[str, object]]:
    options = [f"O{index}" for index in range(option_count)]
    return [_title(), {"name": "Status", "type": type_name, "options": options}]


def test_catalogue_kinds_follow_the_heading_order() -> None:
    assert DATABASE_KINDS == (
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


@pytest.mark.parametrize("kind", list(_CATALOGUE))
def test_catalogue_schema(kind: str) -> None:
    family, expected = _CATALOGUE[kind]
    schema = build_database_schema(kind)
    assert schema.family == family
    actual = tuple((prop.name, prop.type, prop.options) for prop in schema.properties)
    assert actual == expected
    assert schema.name == kind


def test_each_database_definition_is_its_own_record() -> None:
    definitions = schema_definitions()
    assert not isinstance(definitions, str)
    assert list(definitions) == list(DATABASE_KINDS)
    names = {schema.name for schema in definitions.values()}
    assert names == set(DATABASE_KINDS)
    for schema in definitions.values():
        property_names = {prop.name for prop in schema.properties}
        assert (names - {schema.name}).isdisjoint(property_names)


def test_unknown_database_kind_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="not a schema builder"):
        build_database_schema("tasks")


def test_empty_database_kind_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="database kind must not be empty"):
        build_database_schema("")


def test_database_kind_length_accepts_64_and_rejects_65() -> None:
    with pytest.raises(SchemaBuilderError, match="longer than 64"):
        build_database_schema("K" * 65)
    with pytest.raises(SchemaBuilderError, match="not a schema builder"):
        build_database_schema("K" * 64)


@pytest.mark.parametrize("length", [1, 2, 63, 64])
def test_database_name_length_within_limit(length: int) -> None:
    schema = build_schema("N" * length, [_title()])
    assert schema.name == "N" * length


def test_database_name_one_past_max_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="database name longer than 64"):
        build_schema("N" * 65, [_title()])


def test_empty_database_name_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="database name must not be empty"):
        build_schema("", [_title()])


def test_whitespace_database_name_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="surrounding whitespace"):
        build_schema(" Tasks", [_title()])


def test_database_name_must_be_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="database name must be a string"):
        build_schema(cast(str, 1), [_title()])


@pytest.mark.parametrize("count", [1, 2, 11, 12])
def test_property_count_within_limit(count: int) -> None:
    schema = build_schema("Tasks", _properties(count))
    assert len(schema.properties) == count


def test_empty_properties_are_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="properties must not be empty"):
        build_schema("Tasks", [])


def test_property_count_one_past_max_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="more than 12 properties"):
        build_schema("Tasks", _properties(13))


def test_properties_must_be_a_sequence_of_mappings() -> None:
    with pytest.raises(SchemaBuilderError, match="sequence of mappings"):
        build_schema("Tasks", cast(list[dict[str, object]], "Name"))


def test_property_must_be_a_mapping() -> None:
    with pytest.raises(SchemaBuilderError, match="property must be a mapping"):
        build_schema("Tasks", cast(list[dict[str, object]], ["Name"]))


def test_unknown_property_field_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="prompt"):
        build_schema("Tasks", [{"name": "Name", "type": "title", "prompt": "write a database"}])


@pytest.mark.parametrize("length", [1, 2, 63, 64])
def test_property_name_length_within_limit(length: int) -> None:
    schema = build_schema("Tasks", [_title("N" * length)])
    assert schema.properties[0].name == "N" * length


def test_property_name_one_past_max_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="property name longer than 64"):
        build_schema("Tasks", [_title("N" * 65)])


def test_empty_property_name_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="property name must not be empty"):
        build_schema("Tasks", [_title("   ")])


def test_property_name_whitespace_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="surrounding whitespace"):
        build_schema("Tasks", [_title(" Name")])


def test_property_name_must_be_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="property name must be a string"):
        build_schema("Tasks", [{"name": 1, "type": "title"}])


def test_duplicate_property_name_is_rejected() -> None:
    properties = [_title(), {"name": "Note", "type": "text"}, {"name": "Note", "type": "text"}]
    with pytest.raises(SchemaBuilderError, match="duplicated"):
        build_schema("Tasks", properties)


def test_schema_without_a_title_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="must contain a title property"):
        build_schema("Tasks", [{"name": "Note", "type": "text"}])


def test_schema_with_two_titles_is_rejected() -> None:
    properties = [_title("Name"), _title("Other")]
    with pytest.raises(SchemaBuilderError, match="exactly one title"):
        build_schema("Tasks", properties)


@pytest.mark.parametrize("property_type", _ALLOWED_PROPERTY_TYPES)
def test_allowed_property_type_is_accepted(property_type: str) -> None:
    if property_type == "title":
        schema = build_schema("Tasks", [_title()])
        assert schema.properties[0].type == "title"
        return
    extra: dict[str, object] = {"name": "Extra", "type": property_type}
    if property_type in {"select", "multi_select"}:
        extra["options"] = ["One"]
    if property_type == "formula":
        extra["formula_expression"] = 'prop("Name")'
        extra["formula_result_type"] = "text"
    schema = build_schema("Tasks", [_title(), extra])
    assert schema.properties[1].type == property_type


@pytest.mark.parametrize("property_type", ["relation", "rollup", "Title", ""])
def test_disallowed_property_type_is_rejected(property_type: str) -> None:
    properties = [_title(), {"name": "Extra", "type": property_type}]
    with pytest.raises(SchemaBuilderError, match="is not allowed"):
        build_schema("Tasks", properties)


def test_property_type_must_be_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="property type must be a string"):
        build_schema("Tasks", [{"name": "Name", "type": 1}])


@pytest.mark.parametrize("option_count", [1, 2, 7, 8])
def test_option_count_within_limit(option_count: int) -> None:
    schema = build_schema("Tasks", _select(option_count))
    assert schema.properties[1].options == tuple(f"O{index}" for index in range(option_count))


def test_empty_select_options_are_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="select options must not be empty"):
        build_schema("Tasks", _select(0))


def test_option_count_one_past_max_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="more than 8 options"):
        build_schema("Tasks", _select(9))


def test_multi_select_accepts_options() -> None:
    schema = build_schema("Tasks", _select(2, type_name="multi_select"))
    assert schema.properties[1].type == "multi_select"
    assert schema.properties[1].options == ("O0", "O1")


def test_options_on_a_non_select_are_rejected() -> None:
    properties = [_title(), {"name": "Amount", "type": "number", "options": ["One"]}]
    with pytest.raises(SchemaBuilderError, match="only allowed on select"):
        build_schema("Tasks", properties)


def test_duplicate_option_is_rejected() -> None:
    properties = [_title(), {"name": "Status", "type": "select", "options": ["Open", "Open"]}]
    with pytest.raises(SchemaBuilderError, match="unique"):
        build_schema("Tasks", properties)


def test_empty_option_name_is_rejected() -> None:
    properties = [_title(), {"name": "Status", "type": "select", "options": [""]}]
    with pytest.raises(SchemaBuilderError, match="option name must not be empty"):
        build_schema("Tasks", properties)


@pytest.mark.parametrize("length", [1, 2, 63, 64])
def test_option_name_length_within_limit(length: int) -> None:
    option = "O" * length
    properties = [_title(), {"name": "Status", "type": "select", "options": [option]}]
    schema = build_schema("Tasks", properties)
    assert schema.properties[1].options == (option,)


def test_option_name_one_past_max_is_rejected() -> None:
    properties = [_title(), {"name": "Status", "type": "select", "options": ["O" * 65]}]
    with pytest.raises(SchemaBuilderError, match="option name longer than 64"):
        build_schema("Tasks", properties)


def test_option_name_whitespace_is_rejected() -> None:
    properties = [_title(), {"name": "Status", "type": "select", "options": [" Open"]}]
    with pytest.raises(SchemaBuilderError, match="surrounding whitespace"):
        build_schema("Tasks", properties)


def test_options_must_be_a_sequence() -> None:
    properties = [_title(), {"name": "Status", "type": "select", "options": "Open"}]
    with pytest.raises(SchemaBuilderError, match="options must be a sequence"):
        build_schema("Tasks", properties)


def test_option_name_must_be_a_string() -> None:
    properties = [_title(), {"name": "Status", "type": "select", "options": [1]}]
    with pytest.raises(SchemaBuilderError, match="option name must be a string"):
        build_schema("Tasks", properties)


def test_schema_family_must_be_personal_or_business() -> None:
    with pytest.raises(SchemaBuilderError, match="schema family"):
        build_schema("Tasks", [_title()], family=cast("str", "other"))  # type: ignore[arg-type]


def test_caller_property_mutation_does_not_change_the_schema() -> None:
    status: dict[str, object] = {"name": "Status", "type": "select", "options": ["Open", "Done"]}
    properties = [_title(), status]
    schema = build_schema("Tasks", properties)
    status["name"] = "Nope"
    properties.append({"name": "Later", "type": "text"})
    assert [prop.name for prop in schema.properties] == ["Name", "Status"]
    assert schema.properties[1].options == ("Open", "Done")


def test_caller_option_list_mutation_does_not_change_the_schema() -> None:
    options = ["Open", "Done"]
    properties = [_title(), {"name": "Status", "type": "select", "options": options}]
    schema = build_schema("Tasks", properties)
    options.append("Later")
    assert schema.properties[1].options == ("Open", "Done")
