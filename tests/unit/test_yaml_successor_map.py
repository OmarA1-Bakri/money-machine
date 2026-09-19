"""Unit tests for YAML-driven event successor mapping.

Session 03 Wave 7: test the real YAML map implementation of create_successors.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from money_machine.domain.events import EventName
from money_machine.orchestration.successor_factory import (
    SuccessorFactory,
    load_event_successor_map,
)
from money_machine.persistence.tables import Job


class TestLoadEventSuccessorMap:
    """Test YAML configuration loading."""

    def test_loads_map_from_workflows_yaml(self) -> None:
        """Load event_successor_map from config/workflows.yaml."""
        successor_map = load_event_successor_map()

        assert isinstance(successor_map, dict)
        assert len(successor_map) > 0

        # Verify key mappings from Wave 7
        assert successor_map["DEDUPE_PASSED"] == ["ProductBuildJob"]
        assert successor_map["DEDUPE_FAILED"] == ["ReconceptProductJob"]
        assert successor_map["BUILD_COMPLETED"] == ["ProductQAJob"]

        # Verify parallel successors
        assert set(successor_map["SCREENSHOTS_CAPTURED"]) == {
            "ListingCopyJob",
            "AssetFactoryJob",
            "DeliveryBuildJob",
        }

        # Verify empty successors (handled specially or blocking)
        assert successor_map["WINNER_DETECTED"] == []
        assert successor_map["CREDENTIAL_REQUIRED"] == []

    def test_map_structure_is_valid(self) -> None:
        """All keys are strings, all values are lists of strings."""
        successor_map = load_event_successor_map()

        for event_name, successors in successor_map.items():
            assert isinstance(event_name, str), f"Event name must be string: {event_name}"
            assert isinstance(successors, list), f"Successors must be list: {event_name}"
            for job_type in successors:
                assert isinstance(job_type, str), (
                    f"Job type must be string: {job_type} in {event_name}"
                )

    def test_map_is_cached(self) -> None:
        """load_event_successor_map uses lru_cache (same object returned)."""
        map_1 = load_event_successor_map()
        map_2 = load_event_successor_map()

        assert map_1 is map_2, "Should return cached instance"


class TestYamlDrivenSuccessors:
    """Test create_successors with YAML-driven mapping."""

    async def test_creates_successors_from_yaml_map(self) -> None:
        """create_successors reads event → successor mappings from YAML and creates jobs."""
        mock_uow = MagicMock()
        mock_uow.session = AsyncMock()
        added_jobs: list[Job] = []

        def track_add(obj: Job) -> None:
            added_jobs.append(obj)

        mock_uow.session.add = track_add
        mock_uow.session.flush = AsyncMock()

        factory = SuccessorFactory(mock_uow)

        workflow_id = UUID("00000000-0000-0000-0000-000000000001")
        parent_job_id = UUID("00000000-0000-0000-0000-000000000002")
        occurred_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

        # Test DEDUPE_PASSED → ProductBuildJob (single successor)
        result = await factory.create_successors(
            event_name=EventName.DEDUPE_PASSED,
            workflow_id=workflow_id,
            parent_job_id=parent_job_id,
            payload={},
            occurred_at=occurred_at,
        )

        assert len(result) == 1, "DEDUPE_PASSED should create one successor"
        assert len(added_jobs) == 1, "Should have added one Job to session"
        job = added_jobs[0]
        assert job.job_type == "ProductBuildJob"
        assert job.workflow_id == workflow_id
        assert job.status == "PENDING"

    async def test_creates_multiple_successors_for_parallel_events(self) -> None:
        """Events with multiple successors create all of them."""
        mock_uow = MagicMock()
        mock_uow.session = AsyncMock()
        added_jobs: list[Job] = []

        def track_add(obj: Job) -> None:
            added_jobs.append(obj)

        mock_uow.session.add = track_add
        mock_uow.session.flush = AsyncMock()

        factory = SuccessorFactory(mock_uow)

        workflow_id = UUID("00000000-0000-0000-0000-000000000001")
        parent_job_id = UUID("00000000-0000-0000-0000-000000000002")
        occurred_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

        # SCREENSHOTS_CAPTURED → [ListingCopyJob, AssetFactoryJob, DeliveryBuildJob]
        result = await factory.create_successors(
            event_name=EventName.SCREENSHOTS_CAPTURED,
            workflow_id=workflow_id,
            parent_job_id=parent_job_id,
            occurred_at=occurred_at,
        )

        assert len(result) == 3, "SCREENSHOTS_CAPTURED should create three successors"
        assert len(added_jobs) == 3
        job_types = {job.job_type for job in added_jobs}
        assert job_types == {"ListingCopyJob", "AssetFactoryJob", "DeliveryBuildJob"}

    async def test_dedupe_failed_creates_different_successor(self) -> None:
        """DEDUPE_FAILED creates ReconceptProductJob, not ProductBuildJob."""
        mock_uow = MagicMock()
        mock_uow.session = AsyncMock()
        added_jobs: list[Job] = []

        def track_add(obj: Job) -> None:
            added_jobs.append(obj)

        mock_uow.session.add = track_add
        mock_uow.session.flush = AsyncMock()

        factory = SuccessorFactory(mock_uow)

        result = await factory.create_successors(
            event_name=EventName.DEDUPE_FAILED,
            workflow_id=UUID("00000000-0000-0000-0000-000000000001"),
            parent_job_id=UUID("00000000-0000-0000-0000-000000000002"),
            occurred_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        )

        assert len(result) == 1
        assert added_jobs[0].job_type == "ReconceptProductJob"

    async def test_winner_detected_returns_empty_via_map(self) -> None:
        """WINNER_DETECTED is in map, empty successors (dispatch_decision)."""
        mock_uow = MagicMock()
        mock_uow.session = AsyncMock()

        factory = SuccessorFactory(mock_uow)

        result = await factory.create_successors(
            event_name=EventName.WINNER_DETECTED,
            workflow_id=UUID("00000000-0000-0000-0000-000000000001"),
            parent_job_id=UUID("00000000-0000-0000-0000-000000000002"),
            occurred_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        )

        # WINNER_DETECTED is in the map with empty list, so returns empty tuple
        assert result == ()

    async def test_credential_required_returns_empty_via_map(self) -> None:
        """CREDENTIAL_REQUIRED is in the map with no successors (blocks workflow)."""
        mock_uow = MagicMock()
        mock_uow.session = AsyncMock()

        factory = SuccessorFactory(mock_uow)

        result = await factory.create_successors(
            event_name=EventName.CREDENTIAL_REQUIRED,
            workflow_id=UUID("00000000-0000-0000-0000-000000000001"),
            parent_job_id=UUID("00000000-0000-0000-0000-000000000002"),
            occurred_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        )

        assert result == ()

    async def test_deterministic_job_ids(self) -> None:
        """Successor job IDs are deterministic (no random UUIDs)."""
        mock_uow = MagicMock()
        mock_uow.session = AsyncMock()
        added_jobs_1: list[Job] = []
        added_jobs_2: list[Job] = []

        def track_add_1(obj: Job) -> None:
            added_jobs_1.append(obj)

        def track_add_2(obj: Job) -> None:
            added_jobs_2.append(obj)

        factory = SuccessorFactory(mock_uow)

        workflow_id = UUID("00000000-0000-0000-0000-000000000001")
        parent_job_id = UUID("00000000-0000-0000-0000-000000000002")
        occurred_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

        # First call
        mock_uow.session.add = track_add_1
        result_1 = await factory.create_successors(
            event_name=EventName.BUILD_COMPLETED,
            workflow_id=workflow_id,
            parent_job_id=parent_job_id,
            occurred_at=occurred_at,
        )

        # Second call with same inputs
        mock_uow.session.add = track_add_2
        result_2 = await factory.create_successors(
            event_name=EventName.BUILD_COMPLETED,
            workflow_id=workflow_id,
            parent_job_id=parent_job_id,
            occurred_at=occurred_at,
        )

        # Job IDs should be identical
        assert result_1 == result_2
        assert added_jobs_1[0].id == added_jobs_2[0].id

    async def test_verify_multiply_path_still_works(self) -> None:
        """MULTIPLY path via require_successor_spawn still enforced (existing Wave 4/5 contract)."""
        # This test verifies that the old MULTIPLY path via create_multiply_successor
        # still works as before. WINNER_DETECTED returns empty from create_successors
        # because it's handled by dispatch_decision/create_multiply_successor instead.

        mock_uow = MagicMock()
        mock_uow.session = AsyncMock()

        factory = SuccessorFactory(mock_uow)

        result = await factory.create_successors(
            event_name=EventName.WINNER_DETECTED,
            workflow_id=UUID("00000000-0000-0000-0000-000000000001"),
            parent_job_id=UUID("00000000-0000-0000-0000-000000000002"),
            occurred_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        )

        # No jobs created via create_successors
        assert result == ()

        # The actual MULTIPLY successor creation happens via create_multiply_successor
        # which is tested in test_successor_boundary.py (existing tests remain valid)


class TestFailClosedBehavior:
    """Test that unknown/invalid events fail closed."""

    async def test_fails_closed_on_unmapped_event(self) -> None:
        """Events not in the map raise ValueError with helpful message."""
        # We can't easily create an EventName that's not in the map
        # because we mapped all existing events. This test verifies the
        # fail-closed logic exists and would trigger for future events.

        # Verify the map has all current EventName values
        from money_machine.domain.events import EventName as AllEvents

        successor_map = load_event_successor_map()

        # All EventName enum values should be in the map (Wave 7 requirement)
        for event in AllEvents:
            assert event.value in successor_map, (
                f"Event {event.value} missing from successor map - would fail closed"
            )

        # If a future event is added to EventName but not the map,
        # create_successors will raise ValueError per the implementation

    async def test_unknown_event_raises_value_error(self) -> None:
        """Inject an unknown event to prove fail-closed ValueError."""
        from unittest.mock import MagicMock

        mock_uow = MagicMock()
        mock_uow.session = AsyncMock()
        factory = SuccessorFactory(mock_uow)

        # Create a fake EventName that's not in the map
        fake_event = MagicMock()
        fake_event.value = "UNKNOWN_FUTURE_EVENT"

        workflow_id = UUID("00000000-0000-0000-0000-000000000001")
        parent_job_id = UUID("00000000-0000-0000-0000-000000000002")
        occurred_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

        # Should raise ValueError with helpful message
        with pytest.raises(ValueError) as exc_info:
            await factory.create_successors(
                event_name=fake_event,
                workflow_id=workflow_id,
                parent_job_id=parent_job_id,
                occurred_at=occurred_at,
            )

        error_message = str(exc_info.value)
        assert "UNKNOWN_FUTURE_EVENT" in error_message
        assert "not found in event_successor_map" in error_message
        assert "Known events:" in error_message


class TestYamlLoadFailures:
    """SF-5 Coverage: YAML load failure scenarios.

    AUDIT.md SF-5 Acceptance:
    - Missing workflows.yaml raises FileNotFoundError with helpful message
    - Invalid YAML raises ValueError
    - Cache works (second call returns same dict)
    """

    def test_missing_yaml_raises_file_not_found_error(self) -> None:
        """SF-5.1: Missing workflows.yaml raises FileNotFoundError with helpful message."""
        from unittest.mock import patch

        from money_machine.orchestration.successor_factory import load_workflows_config

        # Clear the cache to ensure fresh load
        load_workflows_config.cache_clear()

        # Mock Path.exists to return False (file missing)
        with patch("money_machine.orchestration.successor_factory.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError) as exc_info:
                load_workflows_config()

            error_message = str(exc_info.value)
            assert "Workflow configuration not found" in error_message
            assert "workflows.yaml" in error_message
            assert "Cannot determine event successors" in error_message

    def test_invalid_yaml_raises_value_error(self) -> None:
        """SF-5.2: Invalid YAML raises ValueError with helpful message."""
        from unittest.mock import patch

        from money_machine.config.loader import ConfigLoadError
        from money_machine.orchestration.successor_factory import load_workflows_config

        # Clear the cache to ensure fresh load
        load_workflows_config.cache_clear()

        # Mock load_yaml_model to raise ConfigLoadError (malformed YAML)
        with (
            patch("money_machine.orchestration.successor_factory.Path.exists", return_value=True),
            patch(
                "money_machine.orchestration.successor_factory.load_yaml_model",
                side_effect=ConfigLoadError("Invalid YAML structure"),
            ),
            pytest.raises(ValueError) as exc_info,
        ):
            load_workflows_config()

        error_message = str(exc_info.value)
        assert "Failed to load workflow configuration" in error_message
        assert "Invalid YAML structure" in error_message

    def test_yaml_cache_works(self) -> None:
        """SF-5.3: Cache works - second call returns same dict.

        Already tested in TestLoadEventSuccessorMap.test_map_is_cached.
        """
        # This is already covered by test_map_is_cached in TestLoadEventSuccessorMap,
        # but we document it here as part of SF-5 acceptance.
        from money_machine.orchestration.successor_factory import load_workflows_config

        # Clear cache to start fresh
        load_workflows_config.cache_clear()

        # First call
        result1 = load_workflows_config()

        # Second call should return cached instance (same object)
        result2 = load_workflows_config()

        assert result1 is result2, "Cache should return same object instance"
        assert id(result1) == id(result2), "Memory addresses should match (cached)"


class TestDispatchIdempotency:
    """Test that idempotent dispatch doesn't re-create successor jobs."""

    async def test_idempotent_dispatch_creates_successors_once(self) -> None:
        """Dispatching same event twice creates successors only on first dispatch."""
        from money_machine.orchestration.event_dispatcher import EventDispatcher
        from money_machine.persistence.repositories.events import EventAppendError

        mock_uow = MagicMock()
        mock_uow.session = AsyncMock()
        mock_uow.events = AsyncMock()

        # Track how many times create_successors is called
        create_successors_calls: list[dict[str, object]] = []

        async def mock_create_successors(**kwargs: object) -> tuple[UUID, ...]:
            create_successors_calls.append(kwargs)
            return (UUID("10000000-0000-0000-0000-000000000001"),)

        dispatcher = EventDispatcher(mock_uow)
        # Replace factory's create_successors with our mock
        dispatcher.factory.create_successors = mock_create_successors

        workflow_id = UUID("00000000-0000-0000-0000-000000000001")
        job_id = UUID("00000000-0000-0000-0000-000000000002")
        aggregate_id = UUID("00000000-0000-0000-0000-000000000003")

        # First dispatch: event is new, successors created
        mock_uow.events.append = AsyncMock()
        result_1 = await dispatcher.dispatch(
            event_name=EventName.DEDUPE_PASSED,
            aggregate_type="product_specs",
            aggregate_id=aggregate_id,
            workflow_id=workflow_id,
            job_id=job_id,
            occurred_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        )

        assert len(create_successors_calls) == 1, "First dispatch should create successors"
        assert result_1 == (UUID("10000000-0000-0000-0000-000000000001"),)

        # Second dispatch: event already exists (EventAppendError)
        # Mock by_dedupe_key to return existing event
        mock_existing_event = MagicMock()
        mock_uow.events.by_dedupe_key = AsyncMock(return_value=mock_existing_event)

        # Mock append to raise EventAppendError (duplicate)
        mock_uow.events.append = AsyncMock(side_effect=EventAppendError("Duplicate"))

        result_2 = await dispatcher.dispatch(
            event_name=EventName.DEDUPE_PASSED,
            aggregate_type="product_specs",
            aggregate_id=aggregate_id,
            workflow_id=workflow_id,
            job_id=job_id,
            occurred_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        )

        # Successors should NOT be created again (still 1 call)
        assert len(create_successors_calls) == 1, (
            "Idempotent dispatch should not create successors again"
        )
        assert result_2 == (), "Idempotent dispatch returns empty tuple"
