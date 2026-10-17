"""The operator console read model stays in memory."""

from __future__ import annotations

import pytest

from money_machine.assets.operator_console import ConsoleReadModel, ConsoleRefusal, WorkflowView
from money_machine.assets.operator_views import render_console


def test_an_empty_store_returns_empty_pages() -> None:
    model = ConsoleReadModel()
    page = model.workflow_page(limit=1)
    assert model.current_shop() is None
    assert page.items == ()
    assert page.next_cursor is None
    assert model.system_health().action_required is False
    assert model.autonomy_settings().posthog == "offline"


def test_pages_continue_from_the_cursor() -> None:
    model = ConsoleReadModel(
        workflows=tuple(
            WorkflowView(
                workflow_id=f"w-{index}",
                name=f"Workflow {index}",
                stage="build",
                owning_agent="fixture",
                elapsed_seconds=0,
                next_transition="review",
                blocked_dependency=None,
            )
            for index in (1, 2, 3)
        )
    )
    first = model.workflow_page(limit=2)
    second = model.workflow_page(cursor=first.next_cursor, limit=2)
    assert tuple(item.workflow_id for item in first.items) == ("w-1", "w-2")
    assert tuple(item.workflow_id for item in second.items) == ("w-3",)


def test_an_empty_model_renders_empty_views() -> None:
    views = render_console(ConsoleReadModel())
    assert views.now.status == "empty"
    assert views.pipeline.status == "empty"
    assert views.shop.status == "empty"
    assert views.blocked.status == "empty"
    assert views.decisions.status == "empty"
    assert views.incidents.status == "empty"
    assert views.settings.status == "empty"
    assert views.settings.posthog == "offline"


def test_a_missing_cursor_is_an_error_view() -> None:
    views = render_console(ConsoleReadModel(), cursor="missing")
    assert views.now.status == "error"
    assert views.now.error == "cursor"
    assert views.settings.mode == ""


def test_a_status_word_is_not_a_job_status() -> None:
    with pytest.raises(ConsoleRefusal, match="status"):
        ConsoleReadModel().job_page(status="connected")
