"""The operator console read model stays in memory."""

from __future__ import annotations

import pytest

from money_machine.assets.operator_console import ConsoleReadModel, ConsoleRefusal, WorkflowView


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


def test_a_status_word_is_not_a_job_status() -> None:
    with pytest.raises(ConsoleRefusal, match="status"):
        ConsoleReadModel().job_page(status="connected")
