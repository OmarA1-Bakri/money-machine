"""Job state machine implementation with transition validation.

This module implements the durable job state transitions defined in the canonical
transition table. All state changes validate against the allowed edges and enforce
the documented lifecycle flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from money_machine.domain.enums import JobStatus
from money_machine.orchestration.transition_guard import require_job_transition


@dataclass(frozen=True)
class StateTransition:
    """A validated state transition request."""

    job_id: UUID
    source_status: JobStatus
    target_status: JobStatus
    timestamp: datetime
    reason: str | None = None


class JobStateMachine:
    """Validates and applies job state transitions.

    This class enforces the canonical JobStatus state machine defined in
    transition_guard.JOB_TRANSITIONS. All transitions must pass through
    validate_transition before being applied to the database.
    """

    def validate_transition(
        self,
        job_id: UUID,
        source: JobStatus,
        target: JobStatus,
        *,
        reason: str | None = None,
    ) -> StateTransition:
        """Validate a proposed state transition against the canonical table.

        Args:
            job_id: The job being transitioned
            source: Current job status
            target: Desired job status
            reason: Optional explanation for the transition

        Returns:
            A validated StateTransition ready to be persisted

        Raises:
            InvalidTransitionError: If the transition is not allowed
        """
        require_job_transition(source, target)
        return StateTransition(
            job_id=job_id,
            source_status=source,
            target_status=target,
            timestamp=datetime.now(UTC),
            reason=reason,
        )

    def can_transition(self, source: JobStatus, target: JobStatus) -> bool:
        """Check if a transition is allowed without raising an exception.

        Args:
            source: Current job status
            target: Desired job status

        Returns:
            True if the transition is allowed, False otherwise
        """
        try:
            require_job_transition(source, target)
            return True
        except Exception:
            return False

    def get_allowed_transitions(self, source: JobStatus) -> frozenset[JobStatus]:
        """Get all allowed target states from the given source state.

        Args:
            source: Current job status

        Returns:
            Set of allowed target states
        """
        from money_machine.orchestration.transition_guard import JOB_TRANSITIONS

        return JOB_TRANSITIONS[source]

    def is_terminal(self, status: JobStatus) -> bool:
        """Check if a status is terminal (no outgoing transitions).

        Args:
            status: Job status to check

        Returns:
            True if the status is terminal
        """
        from money_machine.orchestration.transition_guard import JOB_TRANSITIONS

        return len(JOB_TRANSITIONS[status]) == 0
