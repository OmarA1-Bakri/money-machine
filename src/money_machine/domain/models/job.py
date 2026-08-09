"""Durable job and attempt contracts."""

from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from money_machine.domain.enums import JobState, RetryClass
from money_machine.domain.value_objects import FrozenModel, NonEmptyStr, Sha256


class JobEnvelope(FrozenModel):
    """The immutable business inputs and retry policy for one durable job."""

    job_id: UUID
    workflow_run_id: UUID
    job_type: NonEmptyStr
    state: JobState
    idempotency_key: NonEmptyStr
    input_sha256: Sha256
    retry_class: RetryClass
    max_attempts: int = Field(ge=1, le=5)


class JobAttempt(FrozenModel):
    """Append-only record of one job execution attempt."""

    attempt_id: UUID
    job_id: UUID
    attempt_number: int = Field(ge=1, le=5)
    state: JobState
    started_at: AwareDatetime
    completed_at: AwareDatetime | None
    error_code: str | None = None
    error_detail: str | None = None

    @model_validator(mode="after")
    def validate_timing(self) -> Self:
        """Reject attempts whose completion precedes their start."""

        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        return self
