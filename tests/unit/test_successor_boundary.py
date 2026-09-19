"""Unit tests for successor workflow boundary validation.

Session 03 Wave 4: test require_successor_spawn boundary enforcement without database.
Session 03 Wave 5: test create_successors contract (no-successor return for non-MULTIPLY).
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from money_machine.domain.enums import ProductLifecycleState
from money_machine.domain.errors import InvalidTransitionError
from money_machine.domain.events import EventName
from money_machine.orchestration.successor_factory import SuccessorFactory
from money_machine.orchestration.transition_guard import (
    ORIGINAL_WORKFLOW_ENTRY_STATE,
    SUCCESSOR_SPAWN_SOURCE_STATE,
    SUCCESSOR_WORKFLOW_ENTRY_STATE,
    require_successor_spawn,
)

PARENT_ID = UUID("00000000-0000-0000-0000-000000000001")
SUCCESSOR_ID = UUID("00000000-0000-0000-0000-000000000002")


class TestSuccessorBoundaryConstants:
    """Test that boundary constants are correctly defined."""

    def test_entry_states_are_distinct(self) -> None:
        """Original and successor workflows start at different states."""
        assert ORIGINAL_WORKFLOW_ENTRY_STATE == ProductLifecycleState.DISCOVERED
        assert SUCCESSOR_WORKFLOW_ENTRY_STATE == ProductLifecycleState.DEDUPE_CHECK
        assert ORIGINAL_WORKFLOW_ENTRY_STATE != SUCCESSOR_WORKFLOW_ENTRY_STATE

    def test_successor_spawn_source_is_successor_spec(self) -> None:
        """Successors spawn from SUCCESSOR_SPEC state."""
        assert SUCCESSOR_SPAWN_SOURCE_STATE == ProductLifecycleState.SUCCESSOR_SPEC


class TestRequireSuccessorSpawn:
    """Test require_successor_spawn boundary validation."""

    def test_accepts_valid_cross_workflow_spawn(self) -> None:
        """Valid: parent in SUCCESSOR_SPEC, distinct workflow IDs."""
        result = require_successor_spawn(
            parent_state=ProductLifecycleState.SUCCESSOR_SPEC,
            parent_workflow_id=PARENT_ID,
            successor_workflow_id=SUCCESSOR_ID,
        )
        assert result == ProductLifecycleState.DEDUPE_CHECK

    def test_rejects_same_workflow_id(self) -> None:
        """Successor workflow must differ from parent workflow."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            require_successor_spawn(
                parent_state=ProductLifecycleState.SUCCESSOR_SPEC,
                parent_workflow_id=PARENT_ID,
                successor_workflow_id=PARENT_ID,  # Same!
            )
        assert "differ from the parent" in str(exc_info.value)

    def test_rejects_wrong_parent_state(self) -> None:
        """Parent must be in SUCCESSOR_SPEC to spawn a successor."""
        # Too early: still in EVALUATING
        with pytest.raises(InvalidTransitionError) as exc_info:
            require_successor_spawn(
                parent_state=ProductLifecycleState.EVALUATING,
                parent_workflow_id=PARENT_ID,
                successor_workflow_id=SUCCESSOR_ID,
            )
        assert "SUCCESSOR_SPEC" in str(exc_info.value)
        assert "EVALUATING" in str(exc_info.value)

        # Too late: already in OBSERVING
        with pytest.raises(InvalidTransitionError) as exc_info:
            require_successor_spawn(
                parent_state=ProductLifecycleState.OBSERVING,
                parent_workflow_id=PARENT_ID,
                successor_workflow_id=SUCCESSOR_ID,
            )
        assert "SUCCESSOR_SPEC" in str(exc_info.value)
        assert "OBSERVING" in str(exc_info.value)

    def test_rejects_building_state(self) -> None:
        """Cannot spawn successor from BUILDING (would create same-workflow loop)."""
        with pytest.raises(InvalidTransitionError):
            require_successor_spawn(
                parent_state=ProductLifecycleState.BUILDING,
                parent_workflow_id=PARENT_ID,
                successor_workflow_id=SUCCESSOR_ID,
            )

    def test_rejects_dedupe_check_state(self) -> None:
        """Cannot spawn successor from DEDUPE_CHECK."""
        with pytest.raises(InvalidTransitionError):
            require_successor_spawn(
                parent_state=ProductLifecycleState.DEDUPE_CHECK,
                parent_workflow_id=PARENT_ID,
                successor_workflow_id=SUCCESSOR_ID,
            )

    def test_rejects_all_non_successor_spec_states(self) -> None:
        """Only SUCCESSOR_SPEC is valid for spawning successors."""
        invalid_states = [
            ProductLifecycleState.DISCOVERED,
            ProductLifecycleState.RESEARCHING,
            ProductLifecycleState.RESEARCH_COMPLETE,
            ProductLifecycleState.QUALIFYING,
            ProductLifecycleState.QUALIFIED,
            ProductLifecycleState.REJECTED,
            ProductLifecycleState.TEARDOWN_PENDING,
            ProductLifecycleState.TEARDOWN_COMPLETE,
            ProductLifecycleState.SPEC_READY,
            ProductLifecycleState.DEDUPE_CHECK,
            ProductLifecycleState.RECONCEPTING,
            ProductLifecycleState.BUILDING,
            ProductLifecycleState.BUILD_QA,
            ProductLifecycleState.BUILD_REPAIR,
            ProductLifecycleState.VARIANT_BUILD,
            ProductLifecycleState.VARIANT_QA,
            ProductLifecycleState.MERCHANDISING,
            ProductLifecycleState.ASSET_BUILD,
            ProductLifecycleState.ASSET_QA,
            ProductLifecycleState.DRAFTING,
            ProductLifecycleState.DRAFT_READY,
            ProductLifecycleState.PREFLIGHT,
            ProductLifecycleState.LISTING_REPAIR,
            ProductLifecycleState.READY_TO_PUBLISH,
            ProductLifecycleState.PUBLISHED,
            ProductLifecycleState.POST_PUBLISH_QA,
            ProductLifecycleState.INCIDENT_REPAIR,
            ProductLifecycleState.OBSERVING,
            ProductLifecycleState.MATURE,
            ProductLifecycleState.EVALUATING,
            ProductLifecycleState.REPAIRING,
            ProductLifecycleState.DEACTIVATING,
            ProductLifecycleState.DEACTIVATED,
        ]

        for state in invalid_states:
            with pytest.raises(InvalidTransitionError):
                require_successor_spawn(
                    parent_state=state,
                    parent_workflow_id=PARENT_ID,
                    successor_workflow_id=SUCCESSOR_ID,
                )


class TestCreateSuccessorsContract:
    """Test create_successors contract (Wave 4: no-op for non-MULTIPLY events)."""

    async def test_create_successors_contract_no_jobs(self) -> None:
        """create_successors returns empty tuple for all events (MULTIPLY via dispatch_decision).

        This explicit contract test proves the current no-successor behavior is
        intentional, not a silent stub. Wave 4 routes MULTIPLY through
        dispatch_decision/create_multiply_successor. Future waves will load
        event → successor mappings from config/workflows.yaml.
        """
        # Mock UnitOfWork
        mock_uow = MagicMock()
        mock_uow.events = AsyncMock()
        mock_uow.session = AsyncMock()

        factory = SuccessorFactory(mock_uow)

        # Test various non-MULTIPLY events
        test_events: list[EventName] = [
            EventName.WINNER_DETECTED,
            EventName.PRODUCT_REJECTED,
            EventName.LISTING_CULLED,
            EventName.SUCCESSOR_CREATED,
        ]

        workflow_id = UUID("00000000-0000-0000-0000-000000000001")
        job_id = UUID("00000000-0000-0000-0000-000000000002")
        occurred_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

        for event_name in test_events:
            result = await factory.create_successors(
                event_name=event_name,
                workflow_id=workflow_id,
                parent_job_id=job_id,
                payload={},
                occurred_at=occurred_at,
            )
            # Contract: no successors for non-MULTIPLY events in Wave 4
            assert result == (), f"{event_name} should return empty tuple per contract"

    async def test_create_successors_winner_detected_no_jobs(self) -> None:
        """WINNER_DETECTED also returns empty (routed via dispatch_decision separately)."""
        mock_uow = MagicMock()
        mock_uow.events = AsyncMock()
        mock_uow.session = AsyncMock()

        factory = SuccessorFactory(mock_uow)

        workflow_id = UUID("00000000-0000-0000-0000-000000000001")
        job_id = UUID("00000000-0000-0000-0000-000000000002")
        occurred_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

        result = await factory.create_successors(
            event_name=EventName.WINNER_DETECTED,
            workflow_id=workflow_id,
            parent_job_id=job_id,
            payload={},
            occurred_at=occurred_at,
        )

        # WINNER_DETECTED is handled by dispatch_decision, not create_successors
        assert result == ()
