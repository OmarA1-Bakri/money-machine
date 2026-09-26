"""Relation and linked-view helpers from Session 06 prompt section 6.

No network, no Notion, no browser.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest

from money_machine.integrations.notion.errors import SchemaBuilderError
from money_machine.integrations.notion.relations import (
    MAX_FILTERS,
    VIEW_TYPES,
    CanonicalDatabase,
    CanonicalDatabases,
    DashboardRelation,
    DashboardRollup,
    ViewFilter,
    build_canonical_databases,
    build_dashboard_rollup,
    build_filter,
    build_linked_view,
    build_notification_dashboard,
    dashboard_today_view,
    monthly_calendar,
    quick_notes,
)
from money_machine.integrations.notion.schema_builder import DATABASE_KINDS

_ROLLUPS: dict[str, tuple[str, str, str]] = {
    "Tasks": ("open_tasks_due_today", "task_open_and_due_today", "checked"),
    "Events": ("birthday_status", "birthday_status", "checked"),
    "Finance": ("money_spent_today", "money_spent_today", "sum"),
    "Habits": ("water_glasses_remaining", "water_glasses_remaining", "sum"),
}


def test_each_catalogue_kind_is_its_own_canonical_database() -> None:
    canonical = build_canonical_databases(list(DATABASE_KINDS))
    assert canonical.data_types == DATABASE_KINDS
    assert tuple(canonical.by_type) == DATABASE_KINDS
    assert len(canonical.by_type) == len(DATABASE_KINDS)
    for kind in DATABASE_KINDS:
        assert canonical.by_type[kind].data_type == kind


def test_caller_data_type_list_is_copied() -> None:
    kinds = ["Notes", "Tasks"]
    canonical = build_canonical_databases(kinds)
    kinds.append("Events")
    kinds[0] = "Meals"
    assert canonical.data_types == ("Notes", "Tasks")


def test_canonical_mapping_is_immutable() -> None:
    canonical = build_canonical_databases(["Tasks"])
    with pytest.raises(TypeError):
        canonical.by_type["Notes"] = CanonicalDatabase("Notes")  # type: ignore[index]


def test_hand_built_canonical_databases_are_rejected() -> None:
    made_up = ("Widgets",)
    registry = {"Widgets": _database_with_data_type("Widgets")}
    with pytest.raises(SchemaBuilderError):
        CanonicalDatabases(data_types=made_up, by_type=registry)
    with pytest.raises(SchemaBuilderError):
        build_linked_view(
            "Home",
            "Widgets",
            "table",
            "Open",
            (),
            CanonicalDatabases(data_types=made_up, by_type=registry),
        )
    with pytest.raises(SchemaBuilderError):
        CanonicalDatabases(data_types=cast(tuple[str, ...], ([],)), by_type={})


def test_data_types_reject_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="sequence"):
        build_canonical_databases("Tasks")


def test_data_types_reject_a_non_sequence() -> None:
    with pytest.raises(SchemaBuilderError, match="sequence"):
        build_canonical_databases(None)


def test_empty_data_types_are_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="empty"):
        build_canonical_databases([])


def test_data_type_must_be_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="string"):
        build_canonical_databases([None])


def test_unknown_data_type_is_rejected() -> None:
    pattern = r"unknown data type 'Widgets'; valid keys: .*Tasks"
    with pytest.raises(SchemaBuilderError, match=pattern):
        build_canonical_databases(["Widgets"])


def test_data_type_case_must_match() -> None:
    with pytest.raises(SchemaBuilderError, match="'tasks'"):
        build_canonical_databases(["tasks"])


def test_duplicate_data_type_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="duplicated"):
        build_canonical_databases(["Tasks", "Notes", "Tasks"])


@pytest.mark.parametrize("dimension", ["date", "category", "status"])
def test_filter_dimension_is_accepted(dimension: str) -> None:
    filt = build_filter(dimension, "Field", "equals", "Value")
    assert filt.dimension == dimension
    assert filt.condition == "equals"


def test_other_filter_dimension_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="dimension"):
        build_filter("title", "Name", "equals", "Value")


def test_filter_condition_must_be_equals() -> None:
    with pytest.raises(SchemaBuilderError, match="equals"):
        build_filter("status", "Status", "greater_than", "Open")


def test_filter_property_name_must_be_present() -> None:
    with pytest.raises(SchemaBuilderError, match="property name"):
        build_filter("status", "", "equals", "Open")


def test_filter_value_must_be_present() -> None:
    with pytest.raises(SchemaBuilderError, match="filter value"):
        build_filter("status", "Status", "equals", "")


def test_hand_built_view_filter_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError):
        ViewFilter("priority", " x ", "contains", "")
    canonical = build_canonical_databases(["Tasks"])
    with pytest.raises(SchemaBuilderError):
        build_linked_view(
            "Home",
            "Tasks",
            "table",
            "Open",
            (ViewFilter("priority", " x ", "contains", ""),),
            canonical,
        )


def test_unhashable_filter_dimension_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError):
        build_filter([], "Due", "equals", "today")


def test_unhashable_data_type_is_rejected() -> None:
    canonical = build_canonical_databases(["Tasks"])
    with pytest.raises(SchemaBuilderError):
        build_linked_view("Home", [], "table", "Open", (), canonical)


def test_unhashable_view_type_is_rejected() -> None:
    canonical = build_canonical_databases(["Tasks"])
    with pytest.raises(SchemaBuilderError):
        build_linked_view("Home", "Tasks", [], "Open", (), canonical)


def test_two_hubs_link_to_one_canonical_database() -> None:
    canonical = build_canonical_databases(["Tasks"])
    home = build_linked_view("Home", "Tasks", "table", "Open", (), canonical)
    work = build_linked_view("Work", "Tasks", "board", "Done", (), canonical)
    assert home.data_type == work.data_type == "Tasks"
    assert len(canonical.by_type) == 1
    assert canonical.by_type["Tasks"].data_type == "Tasks"


def test_linked_view_rejects_a_database_that_is_not_canonical() -> None:
    canonical = build_canonical_databases(["Notes"])
    with pytest.raises(SchemaBuilderError, match="not canonical"):
        build_linked_view("Home", "Tasks", "table", "Today", (), canonical)


def test_linked_view_requires_the_canonical_registry() -> None:
    with pytest.raises(SchemaBuilderError, match="canonical databases"):
        build_linked_view("Home", "Tasks", "table", "Open", (), {"Tasks": "Tasks"})


def test_disallowed_view_type_is_rejected() -> None:
    canonical = build_canonical_databases(["Tasks"])
    with pytest.raises(SchemaBuilderError, match="view type"):
        build_linked_view("Home", "Tasks", "gallery", "Open", (), canonical)


def test_linked_view_rejects_an_empty_hub() -> None:
    canonical = build_canonical_databases(["Notes"])
    with pytest.raises(SchemaBuilderError, match="hub"):
        build_linked_view("", "Notes", "table", "Notes", (), canonical)


def test_linked_view_rejects_an_empty_name() -> None:
    canonical = build_canonical_databases(["Notes"])
    with pytest.raises(SchemaBuilderError, match="view name"):
        build_linked_view("Home", "Notes", "table", "", (), canonical)


def test_three_filter_dimensions_are_accepted() -> None:
    canonical = build_canonical_databases(["Tasks"])
    filters = [
        build_filter("date", "Due", "equals", "today"),
        build_filter("category", "Status", "equals", "Done"),
        build_filter("status", "Status", "equals", "Open"),
    ]
    view = build_linked_view("Home", "Tasks", "table", "Open", filters, canonical)
    assert len(view.filters) == MAX_FILTERS
    assert view.view_type in VIEW_TYPES


def test_four_filters_are_rejected() -> None:
    canonical = build_canonical_databases(["Tasks"])
    filters = [build_filter("status", "Status", "equals", "Open") for _ in range(4)]
    with pytest.raises(SchemaBuilderError, match="more than 3 filters"):
        build_linked_view("Home", "Tasks", "table", "Open", filters, canonical)


def test_duplicate_filter_dimension_is_rejected() -> None:
    canonical = build_canonical_databases(["Tasks"])
    filters = [
        build_filter("status", "Status", "equals", "Open"),
        build_filter("status", "Status", "equals", "Done"),
    ]
    with pytest.raises(SchemaBuilderError, match="duplicated"):
        build_linked_view("Home", "Tasks", "table", "Open", filters, canonical)


def test_filter_must_be_a_view_filter() -> None:
    canonical = build_canonical_databases(["Tasks"])
    with pytest.raises(SchemaBuilderError, match="view filter"):
        build_linked_view("Home", "Tasks", "table", "Open", ["nope"], canonical)


def test_caller_filter_list_is_copied() -> None:
    canonical = build_canonical_databases(["Tasks"])
    filters = [build_filter("status", "Status", "equals", "Open")]
    view = build_linked_view("Home", "Tasks", "table", "Open", filters, canonical)
    filters.append(build_filter("date", "Due", "equals", "today"))
    assert view.filters == (build_filter("status", "Status", "equals", "Open"),)


def test_filters_must_be_a_sequence() -> None:
    canonical = build_canonical_databases(["Tasks"])
    with pytest.raises(SchemaBuilderError, match="sequence"):
        build_linked_view("Home", "Tasks", "table", "Open", None, canonical)


def test_filters_reject_a_string() -> None:
    canonical = build_canonical_databases(["Tasks"])
    with pytest.raises(SchemaBuilderError, match="sequence"):
        build_linked_view("Home", "Tasks", "table", "Open", "", canonical)


def test_filters_reject_a_non_empty_string() -> None:
    canonical = build_canonical_databases(["Tasks"])
    with pytest.raises(SchemaBuilderError, match="sequence"):
        build_linked_view("Home", "Tasks", "table", "Open", "ab", canonical)


def test_filter_order_is_preserved() -> None:
    canonical = build_canonical_databases(["Tasks"])
    filters = (
        build_filter("status", "Status", "equals", "Open"),
        build_filter("date", "Due", "equals", "today"),
    )
    view = build_linked_view("Home", "Tasks", "table", "Open", filters, canonical)
    assert [item.dimension for item in view.filters] == ["status", "date"]


def test_filter_on_a_missing_property_is_rejected() -> None:
    canonical = build_canonical_databases(["Tasks"])
    filters = (build_filter("date", "Missing", "equals", "today"),)
    with pytest.raises(SchemaBuilderError, match="not on Tasks"):
        build_linked_view("Home", "Tasks", "table", "Open", filters, canonical)


def test_date_filter_on_a_select_property_is_rejected() -> None:
    canonical = build_canonical_databases(["Tasks"])
    filters = (build_filter("date", "Status", "equals", "today"),)
    with pytest.raises(SchemaBuilderError, match="does not fit"):
        build_linked_view("Home", "Tasks", "table", "Open", filters, canonical)


def test_category_filter_on_a_date_property_is_rejected() -> None:
    canonical = build_canonical_databases(["Tasks"])
    filters = (build_filter("category", "Due", "equals", "today"),)
    with pytest.raises(SchemaBuilderError, match="does not fit"):
        build_linked_view("Home", "Tasks", "table", "Open", filters, canonical)


def test_invalid_status_value_is_rejected() -> None:
    canonical = build_canonical_databases(["Tasks"])
    filters = (build_filter("status", "Status", "equals", "Later"),)
    with pytest.raises(SchemaBuilderError, match="status value"):
        build_linked_view("Home", "Tasks", "table", "Open", filters, canonical)


def test_invalid_category_value_is_rejected() -> None:
    canonical = build_canonical_databases(["Tasks"])
    filters = (build_filter("category", "Status", "equals", "Work"),)
    with pytest.raises(SchemaBuilderError, match="category value"):
        build_linked_view("Home", "Tasks", "table", "Open", filters, canonical)


def test_date_filter_on_current_date_formula_is_rejected() -> None:
    canonical = build_canonical_databases(["Tasks"])
    filters = (build_filter("date", "current_date", "equals", "today"),)
    with pytest.raises(SchemaBuilderError, match="formula"):
        build_linked_view("Home", "Tasks", "table", "Open", filters, canonical)


def test_calendar_view_requires_a_date_property() -> None:
    canonical = build_canonical_databases(["Notes"])
    with pytest.raises(SchemaBuilderError, match="date property"):
        build_linked_view("Home", "Notes", "calendar", "Month", (), canonical)


def test_missing_rollup_source_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="not on Tasks"):
        build_dashboard_rollup("Tasks", "open_tasks_due_today", "Missing", "checked")


def test_mismatched_rollup_function_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="does not fit"):
        build_dashboard_rollup("Tasks", "open_tasks_due_today", "task_open_and_due_today", "sum")


def test_unknown_rollup_function_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="does not fit"):
        build_dashboard_rollup("Finance", "spent", "Amount", "average")


def test_unknown_rollup_data_type_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="not canonical"):
        build_dashboard_rollup("Bogus", "spent", "Amount", "sum")


def test_unhashable_rollup_function_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="rollup function"):
        build_dashboard_rollup("Finance", "spent", "Amount", ["average"])


def test_rollup_name_must_be_present() -> None:
    with pytest.raises(SchemaBuilderError, match="rollup name"):
        build_dashboard_rollup("Finance", "", "Amount", "sum")


def test_rollup_source_name_must_be_present() -> None:
    with pytest.raises(SchemaBuilderError, match="property name"):
        build_dashboard_rollup("Finance", "spent", " ", "sum")


def test_finance_formula_rollup_is_rejected_on_tasks() -> None:
    with pytest.raises(SchemaBuilderError, match="not on Tasks"):
        build_dashboard_rollup("Tasks", "spent", "money_spent_today", "sum")


def test_dashboard_today_view() -> None:
    canonical = build_canonical_databases(["Tasks", "Events", "Notes"])
    view = dashboard_today_view(canonical)
    assert view.hub == "Dashboard"
    assert view.data_type == "Tasks"
    assert view.view_type == "table"
    assert view.name == "Today"
    observed = [
        (item.dimension, item.property_name, item.condition, item.value) for item in view.filters
    ]
    assert observed == [
        ("date", "Due", "equals", "today"),
        ("status", "Status", "equals", "Open"),
    ]
    assert len(canonical.by_type) == 3


def test_today_view_requires_the_canonical_tasks_database() -> None:
    canonical = build_canonical_databases(["Notes"])
    with pytest.raises(SchemaBuilderError, match="not canonical"):
        dashboard_today_view(canonical)


def test_monthly_calendar() -> None:
    canonical = build_canonical_databases(["Events"])
    view = monthly_calendar(canonical)
    assert view.hub == "Dashboard"
    assert view.data_type == "Events"
    assert view.view_type == "calendar"
    assert view.name == "Month"
    assert view.filters == ()
    assert len(canonical.by_type) == 1


def test_monthly_calendar_requires_the_canonical_events_database() -> None:
    canonical = build_canonical_databases(["Tasks"])
    with pytest.raises(SchemaBuilderError, match="not canonical"):
        monthly_calendar(canonical)


def test_quick_notes() -> None:
    canonical = build_canonical_databases(["Notes"])
    view = quick_notes(canonical)
    assert view.hub == "Dashboard"
    assert view.data_type == "Notes"
    assert view.view_type == "table"
    assert view.name == "Quick notes"
    assert view.filters == ()


def test_quick_notes_requires_the_canonical_notes_database() -> None:
    canonical = build_canonical_databases(["Tasks"])
    with pytest.raises(SchemaBuilderError, match="not canonical"):
        quick_notes(canonical)


def test_notification_dashboard_is_one_row() -> None:
    canonical = build_canonical_databases(list(DATABASE_KINDS))
    dashboard = build_notification_dashboard(canonical)
    assert dashboard.row_count == 1
    assert isinstance(dashboard.relations, tuple)
    assert isinstance(dashboard.rollups, tuple)
    assert [item.name for item in dashboard.relations] == [
        "Tasks",
        "Events",
        "Finance",
        "Habits",
    ]
    assert [item.data_type for item in dashboard.relations] == [
        "Tasks",
        "Events",
        "Finance",
        "Habits",
    ]
    expected = [
        DashboardRollup(
            name=name,
            relation_name=kind,
            property_name=prop,
            function=function,
        )
        for kind, (name, prop, function) in _ROLLUPS.items()
    ]
    assert list(dashboard.rollups) == expected


def test_dashboard_does_not_emit_client_name_or_current_date() -> None:
    canonical = build_canonical_databases(list(DATABASE_KINDS))
    dashboard = build_notification_dashboard(canonical)
    names = [item.name for item in dashboard.relations]
    names.extend(item.name for item in dashboard.rollups)
    assert "client_name" not in names
    assert "buyer_name" not in names
    assert "current_date" not in names


@pytest.mark.parametrize("kind", ["Tasks", "Events", "Finance", "Habits"])
def test_each_dashboard_database_adds_its_rollup(kind: str) -> None:
    dashboard = build_notification_dashboard(build_canonical_databases([kind]))
    name, prop, function = _ROLLUPS[kind]
    assert [item.name for item in dashboard.relations] == [kind]
    assert [item.data_type for item in dashboard.relations] == [kind]
    assert dashboard.rollups == (
        DashboardRollup(
            name=name,
            relation_name=kind,
            property_name=prop,
            function=function,
        ),
    )
    assert dashboard.row_count == 1


def test_habits_relation_links_only_todays_row() -> None:
    dashboard = build_notification_dashboard(build_canonical_databases(["Tasks", "Habits"]))
    by_type = {item.data_type: item for item in dashboard.relations}
    today = ViewFilter(dimension="date", property_name="Date", condition="equals", value="today")
    assert by_type["Habits"].filters == (today,)
    assert by_type["Habits"].linked_rows is None
    assert by_type["Tasks"].filters == ()
    assert by_type["Tasks"].linked_rows is None
    habits = [item for item in dashboard.rollups if item.relation_name == "Habits"]
    assert habits == [
        DashboardRollup(
            name="water_glasses_remaining",
            relation_name="Habits",
            property_name="water_glasses_remaining",
            function="sum",
        )
    ]


def test_water_glasses_rollup_is_omitted_when_habits_is_absent() -> None:
    canonical = build_canonical_databases(["Tasks", "Events", "Finance"])
    dashboard = build_notification_dashboard(canonical)
    assert [item.name for item in dashboard.rollups] == [
        "open_tasks_due_today",
        "birthday_status",
        "money_spent_today",
    ]
    assert "water_glasses_remaining" not in [item.name for item in dashboard.rollups]


def test_notes_does_not_add_a_dashboard_relation() -> None:
    dashboard = build_notification_dashboard(build_canonical_databases(["Notes"]))
    assert dashboard.row_count == 1
    assert dashboard.relations == ()
    assert dashboard.rollups == ()


def test_notification_dashboard_requires_the_canonical_registry() -> None:
    with pytest.raises(SchemaBuilderError, match="canonical databases"):
        build_notification_dashboard({"Tasks": "Tasks"})


def _database_with_data_type(data_type: str) -> CanonicalDatabase:
    entry = object.__new__(CanonicalDatabase)
    object.__setattr__(entry, "data_type", data_type)
    return entry


def test_canonical_database_rejects_an_unknown_data_type() -> None:
    with pytest.raises(SchemaBuilderError, match="is not canonical"):
        CanonicalDatabase(data_type="Bogus")


def test_catalogue_data_type_must_be_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="is not canonical"):
        CanonicalDatabase(data_type=cast(str, ["Bogus"]))


def test_canonical_key_must_be_catalogue() -> None:
    with pytest.raises(SchemaBuilderError, match="canonical key"):
        CanonicalDatabases(
            data_types=("Tasks",),
            by_type={"Bogus": CanonicalDatabase("Tasks")},
        )


def test_canonical_entry_data_type_must_be_catalogue() -> None:
    with pytest.raises(SchemaBuilderError, match="entry data type"):
        CanonicalDatabases(
            data_types=("Tasks",),
            by_type={"Tasks": _database_with_data_type("Bogus")},
        )


def test_canonical_key_must_match_entry_data_type() -> None:
    with pytest.raises(SchemaBuilderError, match="does not match"):
        CanonicalDatabases(
            data_types=("Tasks",),
            by_type={"Tasks": CanonicalDatabase("Events")},
        )


def test_canonical_data_types_must_not_repeat() -> None:
    with pytest.raises(SchemaBuilderError, match="repeated"):
        CanonicalDatabases(
            data_types=("Tasks", "Tasks"),
            by_type={"Tasks": CanonicalDatabase("Tasks")},
        )


def test_canonical_keys_must_match_data_types() -> None:
    with pytest.raises(SchemaBuilderError, match="must match data types"):
        CanonicalDatabases(data_types=("Tasks",), by_type={})


def test_unhashable_canonical_data_type_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="is not canonical"):
        CanonicalDatabases(
            data_types=cast(tuple[str, ...], (["Tasks"],)),
            by_type={},
        )


def test_canonical_data_types_must_be_a_tuple() -> None:
    with pytest.raises(SchemaBuilderError, match="must be a tuple"):
        CanonicalDatabases(
            data_types=cast(tuple[str, ...], ["Tasks"]),
            by_type={"Tasks": CanonicalDatabase("Tasks")},
        )


def test_canonical_by_type_must_be_a_mapping() -> None:
    with pytest.raises(SchemaBuilderError, match="must be a mapping"):
        CanonicalDatabases(
            data_types=("Tasks",),
            by_type=cast(Mapping[str, CanonicalDatabase], []),
        )


def test_canonical_entry_must_be_a_database() -> None:
    with pytest.raises(SchemaBuilderError, match="CanonicalDatabase"):
        CanonicalDatabases(
            data_types=("Tasks",),
            by_type=cast(Mapping[str, CanonicalDatabase], {"Tasks": "Tasks"}),
        )


def test_caller_by_type_mutation_has_no_effect() -> None:
    original: dict[str, CanonicalDatabase] = {"Tasks": CanonicalDatabase("Tasks")}
    registry = CanonicalDatabases(data_types=("Tasks",), by_type=original)
    original["Events"] = CanonicalDatabase("Events")
    assert tuple(registry.by_type) == ("Tasks",)


def test_linked_rows_yesterday_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="yesterday is not allowed"):
        DashboardRelation(name="Habits", data_type="Habits", linked_rows="yesterday")


def test_linked_rows_must_not_be_empty() -> None:
    with pytest.raises(SchemaBuilderError, match="must not be empty"):
        DashboardRelation(name="Habits", data_type="Habits", linked_rows="")


def test_linked_rows_must_be_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="must be a string"):
        DashboardRelation(name="Habits", data_type="Habits", linked_rows=cast(str, 123))


def test_relation_data_type_must_be_canonical() -> None:
    with pytest.raises(SchemaBuilderError, match="not canonical"):
        DashboardRelation(name="Habits", data_type="Bogus")


def test_rollup_names_the_canonical_database() -> None:
    canonical = build_canonical_databases(["Tasks"])
    dashboard = build_notification_dashboard(canonical)
    assert dashboard.relations[0].data_type == canonical.by_type["Tasks"].data_type
    assert len(canonical.by_type) == 1
