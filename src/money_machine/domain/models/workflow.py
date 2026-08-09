"""Durable workflow-run contract."""

from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, model_validator

from money_machine.domain.enums import ProductState
from money_machine.domain.value_objects import FrozenModel, NonEmptyStr


class WorkflowRun(FrozenModel):
    """One replayable first-product workflow run."""

    workflow_run_id: UUID
    workflow_type: NonEmptyStr
    packet_id: NonEmptyStr
    state: ProductState
    idempotency_key: NonEmptyStr
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_timing(self) -> Self:
        """A workflow cannot be updated before it is created."""

        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        return self
