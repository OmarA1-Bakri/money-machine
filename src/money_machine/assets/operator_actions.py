"""Name the operator actions and fail every one closed."""

from __future__ import annotations

OPERATOR_ACTIONS = (
    "inspect",
    "retry_eligible_failed_job",
    "reconcile_uncertain_effect",
    "supply_credential_status",
    "pause_workflow",
    "resume_workflow",
    "change_standing_authority",
    "create_customer_issue",
    "trigger_schedule_run",
)
_CLOSED = frozenset(OPERATOR_ACTIONS) | {
    "change_standing_authority_settings",
    "edit_database",
    "manually_create_customer_issue",
    "pause_resume_workflow",
    "trigger_safe_schedule_run",
}


class OperatorActionRefusal(ValueError):
    """An operator action is named and closed. Nothing is written."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def refuse_operator_action(action: str) -> None:
    """Refuse one named action. An unknown name is not an action."""
    folded = action.strip().casefold().replace("-", "_").replace("/", "_").replace(" ", "_")
    if folded not in _CLOSED:
        raise OperatorActionRefusal("unknown")
    raise OperatorActionRefusal("closed")
