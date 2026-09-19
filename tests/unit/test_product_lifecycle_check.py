"""Unit tests for Workbook Action 2: object-lifecycle check in dependency resolver.

Tests that jobs transition to READY only when the workflow's product lifecycle
is in a valid (non-terminal) state.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.enums import ProductLifecycleState
from money_machine.orchestration.dependency_resolver import (
    check_product_lifecycle_valid,
    evaluate_job_readiness,
)
from money_machine.persistence.tables import Job, WorkflowRun


class TestProductLifecycleCheck:
    """Test product lifecycle validation in dependency resolver."""

    async def test_lifecycle_check_allows_active_states(self, db_session: AsyncSession) -> None:
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
            db_session.add(workflow)
            await db_session.flush()

            result = await check_product_lifecycle_valid(
                db_session,
                workflow_id=workflow.id,
            )

            assert result is True, f"State {valid_state.value} should allow execution"
            await db_session.rollback()

    async def test_lifecycle_check_blocks_terminal_states(self, db_session: AsyncSession) -> None:
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
            db_session.add(workflow)
            await db_session.flush()

            result = await check_product_lifecycle_valid(
                db_session,
                workflow_id=workflow.id,
            )

            assert result is False, f"Terminal state {terminal_state.value} should block execution"
            await db_session.rollback()

    async def test_lifecycle_check_fails_on_missing_workflow(
        self, db_session: AsyncSession
    ) -> None:
        """Missing workflow fails lifecycle check (fail-closed)."""
        nonexistent_id = UUID("00000000-0000-0000-0000-000000000000")

        result = await check_product_lifecycle_valid(
            db_session,
            workflow_id=nonexistent_id,
        )

        assert result is False, "Missing workflow should fail lifecycle check"

    async def test_evaluate_job_readiness_includes_lifecycle_check(
        self, db_session: AsyncSession
    ) -> None:
        """evaluate_job_readiness includes product lifecycle validation."""
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
        db_session.add(workflow)
        await db_session.flush()

        # Create job that would otherwise be ready
        job = Job(
            workflow_id=workflow.id,
            job_type="TestJob",
            status="PENDING",
            scheduled_at=now,
            created_at=now,
            updated_at=now,
        )
        db_session.add(job)
        await db_session.flush()

        # Evaluate readiness
        is_ready, reason = await evaluate_job_readiness(
            db_session,
            job_id=job.id,
            now=now,
        )

        # Should NOT be ready due to terminal lifecycle
        assert is_ready is False
        assert "terminal" in reason.lower() or "REJECTED" in reason or "DEACTIVATED" in reason


@pytest.fixture
async def db_session(monkeypatch: pytest.MonkeyPatch) -> AsyncSession:
    """Provide in-memory database session for tests."""
    from money_machine.persistence.database import create_engine, create_session_factory
    from money_machine.persistence.tables import Base

    monkeypatch.setenv("DB_HOST", "memory")
    monkeypatch.setenv("DB_PORT", "0")
    monkeypatch.setenv("DB_NAME", ":memory:")
    monkeypatch.setenv("DB_USER", "test")
    monkeypatch.setenv("DB_PASSWORD", "test")

    from money_machine.config.settings import DatabaseConfig

    config = DatabaseConfig(
        host="memory",
        port=0,
        name=":memory:",
        user="test",
        password="test",
    )

    engine = create_engine(config)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = create_session_factory(engine)
    async with factory() as session:
        yield session

    await engine.dispose()
