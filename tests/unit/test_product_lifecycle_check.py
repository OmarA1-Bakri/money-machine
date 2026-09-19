"""Unit tests for Workbook Action 2: object-lifecycle check in dependency resolver.

Tests that jobs transition to READY only when the workflow's product lifecycle
is in a valid (non-terminal) state.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

from money_machine.domain.enums import ProductLifecycleState
from money_machine.orchestration.dependency_resolver import (
    check_product_lifecycle_valid,
    evaluate_job_readiness,
)
from money_machine.persistence.tables import Job, WorkflowRun


class TestProductLifecycleCheck:
    """Test product lifecycle validation in dependency resolver."""

    async def test_lifecycle_check_allows_active_states(self) -> None:
        """Product in QUALIFIED, BUILDING, PUBLISHED states allows job execution."""
        shop_id = UUID("10000000-0000-0000-0000-000000000001")

        for valid_state in [
            ProductLifecycleState.QUALIFIED,
            ProductLifecycleState.BUILDING,
            ProductLifecycleState.PUBLISHED,
        ]:
            workflow = WorkflowRun(
                workflow_type="ProductLifecycleWorkflow",
                workflow_version=1,
                product_state=valid_state.value,
                shop_id=shop_id,
                started_at=datetime.now(UTC),
            )
            workflow.id = UUID("10000000-0000-0000-0000-000000000001")

            mock_session = AsyncMock()
            mock_session.get.return_value = workflow

            result = await check_product_lifecycle_valid(
                mock_session,
                workflow_id=workflow.id,
            )

            assert result is True, f"State {valid_state.value} should allow execution"

    async def test_lifecycle_check_blocks_terminal_states(self) -> None:
        """Product in REJECTED or DEACTIVATED (terminal) blocks job execution."""
        shop_id = UUID("10000000-0000-0000-0000-000000000001")

        for terminal_state in [ProductLifecycleState.REJECTED, ProductLifecycleState.DEACTIVATED]:
            workflow = WorkflowRun(
                workflow_type="ProductLifecycleWorkflow",
                workflow_version=1,
                product_state=terminal_state.value,
                shop_id=shop_id,
                started_at=datetime.now(UTC),
            )
            workflow.id = UUID("10000000-0000-0000-0000-000000000001")

            mock_session = AsyncMock()
            mock_session.get.return_value = workflow

            result = await check_product_lifecycle_valid(
                mock_session,
                workflow_id=workflow.id,
            )

            assert result is False, f"Terminal state {terminal_state.value} should block execution"

    async def test_lifecycle_check_fails_on_missing_workflow(self) -> None:
        """Missing workflow fails lifecycle check (fail-closed)."""
        nonexistent_id = UUID("00000000-0000-0000-0000-000000000000")

        mock_session = AsyncMock()
        mock_session.get.return_value = None

        result = await check_product_lifecycle_valid(
            mock_session,
            workflow_id=nonexistent_id,
        )

        assert result is False, "Missing workflow should fail lifecycle check"

    async def test_evaluate_job_readiness_includes_lifecycle_check(self) -> None:
        """evaluate_job_readiness includes product lifecycle validation."""
        from unittest.mock import patch

        shop_id = UUID("10000000-0000-0000-0000-000000000001")
        now = datetime.now(UTC)

        # Create workflow in terminal state (REJECTED)
        workflow = WorkflowRun(
            workflow_type="ProductLifecycleWorkflow",
            workflow_version=1,
            product_state=ProductLifecycleState.REJECTED.value,
            shop_id=shop_id,
            started_at=now,
        )
        workflow.id = UUID("10000000-0000-0000-0000-000000000001")

        # Create job that would otherwise be ready
        job = Job(
            workflow_id=workflow.id,
            job_type="TestJob",
            status="PENDING",
            scheduled_at=now,
            created_at=now,
            updated_at=now,
        )
        job.id = UUID("20000000-0000-0000-0000-000000000001")

        mock_session = AsyncMock()

        async def mock_get(table_class: type, id: UUID) -> Job | WorkflowRun | None:
            if table_class == Job:
                return job
            if table_class == WorkflowRun:
                return workflow
            return None

        mock_session.get.side_effect = mock_get
        mock_session.scalar.return_value = False  # No unsatisfied dependencies

        # Mock the intermediate checks to pass so we get to the lifecycle check
        with (
            patch(
                "money_machine.orchestration.dependency_resolver.check_dependencies_satisfied",
                return_value=True,
            ),
            patch(
                "money_machine.orchestration.dependency_resolver.check_workflow_active",
                return_value=True,
            ),
            patch(
                "money_machine.orchestration.dependency_resolver.check_idempotency_collision",
                return_value=False,
            ),
        ):
            # Evaluate readiness
            is_ready, reason = await evaluate_job_readiness(
                mock_session,
                job_id=job.id,
                now=now,
            )

        # Should NOT be ready due to terminal lifecycle
        assert is_ready is False
        assert "terminal" in reason.lower() or "REJECTED" in reason or "DEACTIVATED" in reason
