"""Named operator actions fail closed and write nothing."""

from __future__ import annotations

import pytest

from money_machine.assets.operator_actions import (
    OPERATOR_ACTIONS,
    OperatorActionRefusal,
    refuse_operator_action,
)


def test_every_named_action_is_closed() -> None:
    assert len(OPERATOR_ACTIONS) == 9
    for action in OPERATOR_ACTIONS:
        with pytest.raises(OperatorActionRefusal, match="closed"):
            refuse_operator_action(action)


@pytest.mark.parametrize(
    "action",
    ["edit_database", "pause/resume workflow", "trigger safe schedule run"],
)
def test_a_mutation_phrase_is_closed(action: str) -> None:
    with pytest.raises(OperatorActionRefusal, match="closed"):
        refuse_operator_action(action)


def test_a_status_word_is_not_an_action() -> None:
    with pytest.raises(OperatorActionRefusal, match="unknown"):
        refuse_operator_action("connected")
