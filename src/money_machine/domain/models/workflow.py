"""Durable workflow-run contract."""

from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, model_validator

from money_machine.domain.enums import ProductState
from money_machine.domain.value_objects import FrozenModel, NonEmptyStr, Sha256

_ADVERSE_TERMINAL_STATES = frozenset(
    {
        ProductState.INSUFFICIENT_EVIDENCE,
        ProductState.REJECTED,
        ProductState.FAILED,
    }
)


class WorkflowBlocker(FrozenModel):
    """Exact durable reason and optional step-result identity for an adverse terminal."""

    blocker_id: NonEmptyStr
    job_id: UUID
    terminal_state: ProductState
    code: NonEmptyStr
    message: NonEmptyStr
    result_type: NonEmptyStr | None = None
    result_id: NonEmptyStr | None = None
    result_sha256: Sha256 | None = None
    occurred_at: AwareDatetime

    @model_validator(mode="after")
    def validate_terminal_identity(self) -> Self:
        if self.terminal_state not in _ADVERSE_TERMINAL_STATES:
            raise ValueError("blocker requires an adverse terminal state")
        result_identity = (self.result_type, self.result_id, self.result_sha256)
        if any(value is None for value in result_identity) and any(
            value is not None for value in result_identity
        ):
            raise ValueError("blocker result identity fields must be all present or all absent")
        return self


def workflow_blocker_payload(blocker: WorkflowBlocker) -> dict[str, object]:
    """Return the exact event payload bound to a terminal blocker."""

    return {
        "blocker_id": blocker.blocker_id,
        "terminal_state": blocker.terminal_state.value,
        "code": blocker.code,
        "message": blocker.message,
        "result_type": blocker.result_type,
        "result_id": blocker.result_id,
        "result_sha256": blocker.result_sha256,
    }


class WorkflowRun(FrozenModel):
    """One replayable first-product workflow run."""

    workflow_run_id: UUID
    workflow_type: NonEmptyStr
    packet_id: NonEmptyStr
    state: ProductState
    idempotency_key: NonEmptyStr
    created_at: AwareDatetime
    updated_at: AwareDatetime
    terminal_blocker: WorkflowBlocker | None = None

    @model_validator(mode="after")
    def validate_timing(self) -> Self:
        """A workflow cannot be updated before it is created."""

        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        if self.terminal_blocker is not None:
            WorkflowBlocker(**self.terminal_blocker.model_dump(mode="python"))
        if self.state in _ADVERSE_TERMINAL_STATES:
            if self.terminal_blocker is None:
                raise ValueError("adverse terminal workflow requires terminal_blocker")
            if self.terminal_blocker.terminal_state is not self.state:
                raise ValueError("terminal_blocker state must match workflow state")
        elif self.terminal_blocker is not None:
            raise ValueError("terminal_blocker is only valid for an adverse terminal state")
        return self
