"""Correlation identifiers shared across logs, metrics, and telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """Safe identifiers that tie one agent execution to its workflow context."""

    job_id: UUID
    agent_id: str
    workflow_id: UUID | None = None
    agent_run_id: UUID | None = None
    job_type: str | None = None
    attempt: int | None = None

    def as_log_fields(self) -> dict[str, Any]:
        """Return only populated correlation fields for structured logging."""
        fields: dict[str, Any] = {
            "job_id": str(self.job_id),
            "agent_id": self.agent_id,
        }
        if self.workflow_id is not None:
            fields["workflow_id"] = str(self.workflow_id)
        if self.agent_run_id is not None:
            fields["agent_run_id"] = str(self.agent_run_id)
        if self.job_type is not None:
            fields["job_type"] = self.job_type
        if self.attempt is not None:
            fields["attempt"] = self.attempt
        return fields
