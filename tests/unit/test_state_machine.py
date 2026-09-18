"""Tests for job state machine transitions.

These tests verify the canonical JobStatus state machine using deterministic
test data. No live database or agent execution required.
"""

from datetime import datetime
from uuid import UUID

import pytest

from money_machine.domain.enums import JobStatus
from money_machine.domain.errors import InvalidTransitionError
from money_machine.orchestration.state_machine import JobStateMachine


@pytest.fixture
def state_machine() -> JobStateMachine:
    """Provide a fresh state machine for each test."""
    return JobStateMachine()


@pytest.fixture
def test_job_id() -> UUID:
    """Deterministic test job ID."""
    return UUID("00000000-0000-0000-0000-000000000001")


class TestBasicTransitions:
    """Test the core PENDING → BLOCKED → READY → RUNNING flow."""

    def test_pending_to_ready_is_valid(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id, JobStatus.PENDING, JobStatus.READY, reason="dependencies satisfied"
        )
        assert transition.source_status == JobStatus.PENDING
        assert transition.target_status == JobStatus.READY
        assert transition.job_id == test_job_id
        assert transition.reason == "dependencies satisfied"
        assert isinstance(transition.timestamp, datetime)

    def test_pending_to_blocked_is_valid(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id, JobStatus.PENDING, JobStatus.BLOCKED, reason="credential required"
        )
        assert transition.source_status == JobStatus.PENDING
        assert transition.target_status == JobStatus.BLOCKED

    def test_blocked_to_ready_is_valid(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id, JobStatus.BLOCKED, JobStatus.READY, reason="credentials provided"
        )
        assert transition.source_status == JobStatus.BLOCKED
        assert transition.target_status == JobStatus.READY

    def test_ready_to_running_is_valid(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id, JobStatus.READY, JobStatus.RUNNING, reason="claimed by worker"
        )
        assert transition.source_status == JobStatus.READY
        assert transition.target_status == JobStatus.RUNNING

    def test_running_to_succeeded_is_valid(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id, JobStatus.RUNNING, JobStatus.SUCCEEDED, reason="agent completed"
        )
        assert transition.source_status == JobStatus.RUNNING
        assert transition.target_status == JobStatus.SUCCEEDED


class TestFailurePaths:
    """Test failure and retry transitions."""

    def test_running_to_failed_is_valid(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id, JobStatus.RUNNING, JobStatus.FAILED, reason="agent returned failure"
        )
        assert transition.source_status == JobStatus.RUNNING
        assert transition.target_status == JobStatus.FAILED

    def test_failed_to_ready_allows_retry(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id, JobStatus.FAILED, JobStatus.READY, reason="retry scheduled"
        )
        assert transition.source_status == JobStatus.FAILED
        assert transition.target_status == JobStatus.READY

    def test_failed_to_terminal_failure_ends_retry(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id,
            JobStatus.FAILED,
            JobStatus.TERMINAL_FAILURE,
            reason="max attempts reached",
        )
        assert transition.source_status == JobStatus.FAILED
        assert transition.target_status == JobStatus.TERMINAL_FAILURE


class TestUncertainExternalEffect:
    """Test uncertain external effect reconciliation paths."""

    def test_running_to_uncertain_external_effect(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id,
            JobStatus.RUNNING,
            JobStatus.UNCERTAIN_EXTERNAL_EFFECT,
            reason="timeout during external write",
        )
        assert transition.target_status == JobStatus.UNCERTAIN_EXTERNAL_EFFECT

    def test_uncertain_to_succeeded_after_reconciliation(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id,
            JobStatus.UNCERTAIN_EXTERNAL_EFFECT,
            JobStatus.SUCCEEDED,
            reason="effect confirmed",
        )
        assert transition.source_status == JobStatus.UNCERTAIN_EXTERNAL_EFFECT
        assert transition.target_status == JobStatus.SUCCEEDED

    def test_uncertain_to_failed_after_reconciliation(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id,
            JobStatus.UNCERTAIN_EXTERNAL_EFFECT,
            JobStatus.FAILED,
            reason="effect absent",
        )
        assert transition.source_status == JobStatus.UNCERTAIN_EXTERNAL_EFFECT
        assert transition.target_status == JobStatus.FAILED

    def test_uncertain_to_blocked_after_reconciliation_failure(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id,
            JobStatus.UNCERTAIN_EXTERNAL_EFFECT,
            JobStatus.BLOCKED,
            reason="reconciliation budget exhausted",
        )
        assert transition.source_status == JobStatus.UNCERTAIN_EXTERNAL_EFFECT
        assert transition.target_status == JobStatus.BLOCKED


class TestCancellation:
    """Test job cancellation from various states."""

    def test_pending_to_cancelled(self, state_machine: JobStateMachine, test_job_id: UUID) -> None:
        transition = state_machine.validate_transition(
            test_job_id, JobStatus.PENDING, JobStatus.CANCELLED, reason="user requested"
        )
        assert transition.target_status == JobStatus.CANCELLED

    def test_blocked_to_cancelled(self, state_machine: JobStateMachine, test_job_id: UUID) -> None:
        transition = state_machine.validate_transition(
            test_job_id, JobStatus.BLOCKED, JobStatus.CANCELLED, reason="user requested"
        )
        assert transition.target_status == JobStatus.CANCELLED

    def test_ready_to_cancelled(self, state_machine: JobStateMachine, test_job_id: UUID) -> None:
        transition = state_machine.validate_transition(
            test_job_id, JobStatus.READY, JobStatus.CANCELLED, reason="user requested"
        )
        assert transition.target_status == JobStatus.CANCELLED


class TestInvalidTransitions:
    """Test that invalid transitions are properly rejected."""

    def test_pending_to_running_is_invalid(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        with pytest.raises(InvalidTransitionError, match=r"PENDING.*RUNNING"):
            state_machine.validate_transition(test_job_id, JobStatus.PENDING, JobStatus.RUNNING)

    def test_succeeded_to_running_is_invalid(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        with pytest.raises(InvalidTransitionError, match=r"SUCCEEDED.*RUNNING"):
            state_machine.validate_transition(test_job_id, JobStatus.SUCCEEDED, JobStatus.RUNNING)

    def test_terminal_failure_to_ready_is_invalid(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        with pytest.raises(InvalidTransitionError, match=r"TERMINAL_FAILURE.*READY"):
            state_machine.validate_transition(
                test_job_id, JobStatus.TERMINAL_FAILURE, JobStatus.READY
            )

    def test_cancelled_to_running_is_invalid(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        with pytest.raises(InvalidTransitionError, match=r"CANCELLED.*RUNNING"):
            state_machine.validate_transition(test_job_id, JobStatus.CANCELLED, JobStatus.RUNNING)

    def test_uncertain_to_ready_is_invalid(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        # UNCERTAIN_EXTERNAL_EFFECT can only go to SUCCEEDED, FAILED, or BLOCKED
        with pytest.raises(InvalidTransitionError, match=r"UNCERTAIN_EXTERNAL_EFFECT.*READY"):
            state_machine.validate_transition(
                test_job_id, JobStatus.UNCERTAIN_EXTERNAL_EFFECT, JobStatus.READY
            )

    def test_running_to_blocked_is_valid(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        # Note: RUNNING → BLOCKED is actually valid per the transition table
        # (e.g., when a credential expires during execution)
        transition = state_machine.validate_transition(
            test_job_id, JobStatus.RUNNING, JobStatus.BLOCKED, reason="credential expired"
        )
        assert transition.target_status == JobStatus.BLOCKED


class TestCanTransition:
    """Test the non-raising transition check method."""

    def test_can_transition_returns_true_for_valid(self, state_machine: JobStateMachine) -> None:
        assert state_machine.can_transition(JobStatus.PENDING, JobStatus.READY)
        assert state_machine.can_transition(JobStatus.READY, JobStatus.RUNNING)
        assert state_machine.can_transition(JobStatus.RUNNING, JobStatus.SUCCEEDED)

    def test_can_transition_returns_false_for_invalid(self, state_machine: JobStateMachine) -> None:
        assert not state_machine.can_transition(JobStatus.PENDING, JobStatus.RUNNING)
        assert not state_machine.can_transition(JobStatus.SUCCEEDED, JobStatus.RUNNING)
        assert not state_machine.can_transition(JobStatus.TERMINAL_FAILURE, JobStatus.READY)


class TestGetAllowedTransitions:
    """Test retrieval of all allowed transitions from a given state."""

    def test_pending_allowed_transitions(self, state_machine: JobStateMachine) -> None:
        allowed = state_machine.get_allowed_transitions(JobStatus.PENDING)
        assert allowed == frozenset({JobStatus.BLOCKED, JobStatus.READY, JobStatus.CANCELLED})

    def test_running_allowed_transitions(self, state_machine: JobStateMachine) -> None:
        allowed = state_machine.get_allowed_transitions(JobStatus.RUNNING)
        assert allowed == frozenset(
            {
                JobStatus.SUCCEEDED,
                JobStatus.FAILED,
                JobStatus.BLOCKED,
                JobStatus.UNCERTAIN_EXTERNAL_EFFECT,
            }
        )

    def test_terminal_states_have_no_allowed_transitions(
        self, state_machine: JobStateMachine
    ) -> None:
        assert state_machine.get_allowed_transitions(JobStatus.SUCCEEDED) == frozenset()
        assert state_machine.get_allowed_transitions(JobStatus.TERMINAL_FAILURE) == frozenset()
        assert state_machine.get_allowed_transitions(JobStatus.CANCELLED) == frozenset()


class TestIsTerminal:
    """Test terminal state detection."""

    def test_succeeded_is_terminal(self, state_machine: JobStateMachine) -> None:
        assert state_machine.is_terminal(JobStatus.SUCCEEDED)

    def test_terminal_failure_is_terminal(self, state_machine: JobStateMachine) -> None:
        assert state_machine.is_terminal(JobStatus.TERMINAL_FAILURE)

    def test_cancelled_is_terminal(self, state_machine: JobStateMachine) -> None:
        assert state_machine.is_terminal(JobStatus.CANCELLED)

    def test_non_terminal_states(self, state_machine: JobStateMachine) -> None:
        assert not state_machine.is_terminal(JobStatus.PENDING)
        assert not state_machine.is_terminal(JobStatus.BLOCKED)
        assert not state_machine.is_terminal(JobStatus.READY)
        assert not state_machine.is_terminal(JobStatus.RUNNING)
        assert not state_machine.is_terminal(JobStatus.FAILED)
        assert not state_machine.is_terminal(JobStatus.UNCERTAIN_EXTERNAL_EFFECT)


class TestTransitionSequences:
    """Test complete transition sequences through the state machine."""

    def test_happy_path_pending_to_succeeded(self, state_machine: JobStateMachine) -> None:
        """Test a successful job flow: PENDING → READY → RUNNING → SUCCEEDED."""
        job_id = UUID("00000000-0000-0000-0000-000000000010")

        # PENDING → READY
        t1 = state_machine.validate_transition(job_id, JobStatus.PENDING, JobStatus.READY)
        assert t1.source_status == JobStatus.PENDING
        assert t1.target_status == JobStatus.READY

        # READY → RUNNING
        t2 = state_machine.validate_transition(job_id, JobStatus.READY, JobStatus.RUNNING)
        assert t2.source_status == JobStatus.READY
        assert t2.target_status == JobStatus.RUNNING

        # RUNNING → SUCCEEDED
        t3 = state_machine.validate_transition(job_id, JobStatus.RUNNING, JobStatus.SUCCEEDED)
        assert t3.source_status == JobStatus.RUNNING
        assert t3.target_status == JobStatus.SUCCEEDED

    def test_blocked_then_ready_path(self, state_machine: JobStateMachine) -> None:
        """Test: PENDING → BLOCKED → READY → RUNNING → SUCCEEDED."""
        job_id = UUID("00000000-0000-0000-0000-000000000011")

        state_machine.validate_transition(job_id, JobStatus.PENDING, JobStatus.BLOCKED)
        state_machine.validate_transition(job_id, JobStatus.BLOCKED, JobStatus.READY)
        state_machine.validate_transition(job_id, JobStatus.READY, JobStatus.RUNNING)
        final = state_machine.validate_transition(job_id, JobStatus.RUNNING, JobStatus.SUCCEEDED)
        assert final.target_status == JobStatus.SUCCEEDED

    def test_retry_path(self, state_machine: JobStateMachine) -> None:
        """Test: RUNNING → FAILED → READY → RUNNING → SUCCEEDED."""
        job_id = UUID("00000000-0000-0000-0000-000000000012")

        state_machine.validate_transition(job_id, JobStatus.RUNNING, JobStatus.FAILED)
        state_machine.validate_transition(job_id, JobStatus.FAILED, JobStatus.READY)
        state_machine.validate_transition(job_id, JobStatus.READY, JobStatus.RUNNING)
        final = state_machine.validate_transition(job_id, JobStatus.RUNNING, JobStatus.SUCCEEDED)
        assert final.target_status == JobStatus.SUCCEEDED

    def test_max_retries_path(self, state_machine: JobStateMachine) -> None:
        """Test: RUNNING → FAILED → TERMINAL_FAILURE."""
        job_id = UUID("00000000-0000-0000-0000-000000000013")

        state_machine.validate_transition(job_id, JobStatus.RUNNING, JobStatus.FAILED)
        final = state_machine.validate_transition(
            job_id, JobStatus.FAILED, JobStatus.TERMINAL_FAILURE
        )
        assert final.target_status == JobStatus.TERMINAL_FAILURE

    def test_uncertain_effect_reconciled_to_success(self, state_machine: JobStateMachine) -> None:
        """Test: RUNNING → UNCERTAIN_EXTERNAL_EFFECT → SUCCEEDED."""
        job_id = UUID("00000000-0000-0000-0000-000000000014")

        state_machine.validate_transition(
            job_id, JobStatus.RUNNING, JobStatus.UNCERTAIN_EXTERNAL_EFFECT
        )
        final = state_machine.validate_transition(
            job_id, JobStatus.UNCERTAIN_EXTERNAL_EFFECT, JobStatus.SUCCEEDED
        )
        assert final.target_status == JobStatus.SUCCEEDED

    def test_uncertain_effect_reconciled_to_failed_then_retry(
        self, state_machine: JobStateMachine
    ) -> None:
        """Test: RUNNING → UNCERTAIN_EXTERNAL_EFFECT → FAILED → READY → RUNNING → SUCCEEDED."""
        job_id = UUID("00000000-0000-0000-0000-000000000015")

        state_machine.validate_transition(
            job_id, JobStatus.RUNNING, JobStatus.UNCERTAIN_EXTERNAL_EFFECT
        )
        state_machine.validate_transition(
            job_id, JobStatus.UNCERTAIN_EXTERNAL_EFFECT, JobStatus.FAILED
        )
        state_machine.validate_transition(job_id, JobStatus.FAILED, JobStatus.READY)
        state_machine.validate_transition(job_id, JobStatus.READY, JobStatus.RUNNING)
        final = state_machine.validate_transition(job_id, JobStatus.RUNNING, JobStatus.SUCCEEDED)
        assert final.target_status == JobStatus.SUCCEEDED


class TestStateTransitionImmutability:
    """Test that StateTransition objects are immutable."""

    def test_state_transition_is_frozen(
        self, state_machine: JobStateMachine, test_job_id: UUID
    ) -> None:
        transition = state_machine.validate_transition(
            test_job_id, JobStatus.PENDING, JobStatus.READY
        )

        with pytest.raises((AttributeError, TypeError)):
            transition.target_status = JobStatus.RUNNING  # type: ignore[misc]

        with pytest.raises((AttributeError, TypeError)):
            transition.reason = "changed"  # type: ignore[misc]
