from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError

from money_machine.domain.enums import JobState, ProductState, RetryClass
from money_machine.domain.events import DomainEvent, DomainEventName
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.models.workflow import WorkflowRun
from money_machine.domain.value_objects import canonical_sha256
from money_machine.persistence.database import Database
from money_machine.persistence.tables import domain_events, job_attempts, jobs, product_specs
from money_machine.persistence.unit_of_work import UnitOfWork

REPO_ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 8, 9, tzinfo=UTC)


def test_job_completion_rolls_back_result_event_parent_and_successor() -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
    command.upgrade(config, "head")

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        actual_now = datetime.now(UTC)
        workflow_id = UUID("00000000-0000-0000-0000-000000000201")
        parent_id = UUID("00000000-0000-0000-0000-000000000202")
        workflow = WorkflowRun(
            workflow_run_id=workflow_id,
            workflow_type="FIRST_PRODUCT",
            packet_id="RPK-atomic",
            state=ProductState.RESEARCHED,
            idempotency_key="workflow:RPK-atomic",
            created_at=NOW,
            updated_at=NOW,
        )
        parent = JobEnvelope(
            job_id=parent_id,
            workflow_run_id=workflow_id,
            job_type="CREATE_PRODUCT_SPEC",
            state=JobState.READY,
            idempotency_key="job:parent",
            input_sha256="a" * 64,
            retry_class=RetryClass.NEVER,
            max_attempts=1,
        )
        occupied = JobEnvelope(
            job_id=UUID("00000000-0000-0000-0000-000000000203"),
            workflow_run_id=workflow_id,
            job_type="RUN_DEDUPE",
            state=JobState.PENDING,
            idempotency_key="job:duplicate-successor",
            input_sha256="b" * 64,
            retry_class=RetryClass.NEVER,
            max_attempts=1,
        )
        async with UnitOfWork(database) as uow:
            await uow.workflows.add(workflow)
            await uow.jobs.add(parent)
            await uow.jobs.add(occupied)
            assert uow.session is not None
            await uow.session.execute(
                update(jobs)
                .where(jobs.c.job_id == parent_id)
                .values(
                    state="RUNNING",
                    attempt_count=1,
                    lease_owner="worker-atomic",
                    lease_token="lease-token",
                    leased_at=actual_now,
                    lease_expires_at=actual_now + timedelta(minutes=5),
                )
            )
            await uow.session.execute(
                insert(job_attempts).values(
                    job_id=parent_id,
                    attempt_number=1,
                    state="RUNNING",
                    lease_token="lease-token",
                    started_at=actual_now,
                )
            )

        spec = ProductSpec(
            product_spec_id="PS-atomic",
            candidate_id="candidate-atomic",
            identity_niche="students",
            base_category="planner",
            target_buyer="students",
            promised_outcome="organise coursework",
            hubs=("home", "courses", "tasks", "calendar", "notes", "review"),
            colour_variants=("ink", "sage", "sand"),
            features=("weekly review",),
            product_facts=("contains six hubs",),
            source_evidence_ids=("EV-1",),
            spec_sha256="c" * 64,
        )
        event_payload = {"product_spec_id": spec.product_spec_id}
        event = DomainEvent(
            event_id=UUID("00000000-0000-0000-0000-000000000204"),
            workflow_run_id=workflow_id,
            job_id=parent_id,
            name=DomainEventName.PRODUCT_SPEC_CREATED,
            occurred_at=actual_now,
            payload=event_payload,
            payload_sha256=canonical_sha256(event_payload),
        )
        conflicting_successor = occupied.model_copy(
            update={"job_id": UUID("00000000-0000-0000-0000-000000000205")}
        )

        with pytest.raises(IntegrityError):
            async with UnitOfWork(database) as uow:
                await uow.commit_job_success(
                    parent_id,
                    "lease-token",
                    1,
                    "product_specs",
                    spec,
                    event,
                    conflicting_successor,
                )

        async with database.session_factory() as session:
            assert (
                await session.scalar(select(jobs.c.state).where(jobs.c.job_id == parent_id))
                == "RUNNING"
            )
            attempt = (
                await session.execute(
                    select(job_attempts.c.state, job_attempts.c.completed_at).where(
                        job_attempts.c.job_id == parent_id,
                        job_attempts.c.attempt_number == 1,
                    )
                )
            ).one()
            assert attempt.state == "RUNNING"
            assert attempt.completed_at is None
            assert await session.scalar(select(func.count()).select_from(product_specs)) == 0
            assert await session.scalar(select(func.count()).select_from(domain_events)) == 0
            assert await session.scalar(select(func.count()).select_from(jobs)) == 2
        await database.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("suffix", "job_state", "lease_expiry_delta", "event_delta", "attempt_state"),
    [
        ("leased", "LEASED", timedelta(minutes=5), timedelta(0), "LEASED"),
        ("expired", "RUNNING", -timedelta(seconds=1), timedelta(0), "RUNNING"),
        (
            "forged-event-time",
            "RUNNING",
            -timedelta(seconds=1),
            -timedelta(seconds=2),
            "RUNNING",
        ),
    ],
)
def test_job_completion_rejects_invalid_or_expired_running_lease_atomically(
    suffix: str,
    job_state: str,
    lease_expiry_delta: timedelta,
    event_delta: timedelta,
    attempt_state: str,
) -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
    command.upgrade(config, "head")

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        actual_now = datetime.now(UTC)
        workflow_id = uuid5(NAMESPACE_URL, f"workflow-{suffix}")
        job_id = uuid5(NAMESPACE_URL, f"job-{suffix}")
        workflow = WorkflowRun(
            workflow_run_id=workflow_id,
            workflow_type="FIRST_PRODUCT",
            packet_id=f"RPK-{suffix}",
            state=ProductState.RESEARCHED,
            idempotency_key=f"workflow:{suffix}",
            created_at=NOW,
            updated_at=NOW,
        )
        job = JobEnvelope(
            job_id=job_id,
            workflow_run_id=workflow_id,
            job_type="CREATE_PRODUCT_SPEC",
            state=JobState.READY,
            idempotency_key=f"job:{suffix}",
            input_sha256="d" * 64,
            retry_class=RetryClass.NEVER,
            max_attempts=1,
        )
        async with UnitOfWork(database) as uow:
            await uow.workflows.add(workflow)
            await uow.jobs.add(job)
            assert uow.session is not None
            await uow.session.execute(
                update(jobs)
                .where(jobs.c.job_id == job_id)
                .values(
                    state=job_state,
                    attempt_count=1,
                    lease_owner="worker-test",
                    lease_token="lease-token",
                    leased_at=actual_now - timedelta(minutes=1),
                    lease_expires_at=actual_now + lease_expiry_delta,
                )
            )
            await uow.session.execute(
                insert(job_attempts).values(
                    job_id=job_id,
                    attempt_number=1,
                    state=attempt_state,
                    lease_token="lease-token",
                    started_at=actual_now - timedelta(minutes=1),
                )
            )

        spec = ProductSpec(
            product_spec_id=f"PS-{suffix}",
            candidate_id=f"candidate-{suffix}",
            identity_niche="students",
            base_category="planner",
            target_buyer="students",
            promised_outcome="organise coursework",
            hubs=("home", "courses", "tasks", "calendar", "notes", "review"),
            colour_variants=("ink", "sage", "sand"),
            features=("weekly review",),
            product_facts=("contains six hubs",),
            source_evidence_ids=("EV-1",),
            spec_sha256="e" * 64,
        )
        event_payload = {"product_spec_id": spec.product_spec_id}
        event = DomainEvent(
            event_id=uuid5(NAMESPACE_URL, f"event-{suffix}"),
            workflow_run_id=workflow_id,
            job_id=job_id,
            name=DomainEventName.PRODUCT_SPEC_CREATED,
            occurred_at=actual_now + event_delta,
            payload=event_payload,
            payload_sha256=canonical_sha256(event_payload),
        )

        with pytest.raises(ValueError, match="job completion lease mismatch"):
            async with UnitOfWork(database) as uow:
                await uow.commit_job_success(
                    job_id,
                    "lease-token",
                    1,
                    "product_specs",
                    spec,
                    event,
                    None,
                )

        async with database.session_factory() as session:
            assert (
                await session.scalar(select(jobs.c.state).where(jobs.c.job_id == job_id))
                == job_state
            )
            assert await session.scalar(select(func.count()).select_from(product_specs)) == 0
            assert await session.scalar(select(func.count()).select_from(domain_events)) == 0
        await database.dispose()

    asyncio.run(scenario())


def test_job_completion_rejects_lease_that_expires_after_transaction_start() -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
    command.upgrade(config, "head")

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        actual_now = datetime.now(UTC)
        workflow_id = UUID("00000000-0000-0000-0000-000000000211")
        job_id = UUID("00000000-0000-0000-0000-000000000212")
        workflow = WorkflowRun(
            workflow_run_id=workflow_id,
            workflow_type="FIRST_PRODUCT",
            packet_id="RPK-transaction-expiry",
            state=ProductState.RESEARCHED,
            idempotency_key="workflow:transaction-expiry",
            created_at=NOW,
            updated_at=NOW,
        )
        job = JobEnvelope(
            job_id=job_id,
            workflow_run_id=workflow_id,
            job_type="CREATE_PRODUCT_SPEC",
            state=JobState.READY,
            idempotency_key="job:transaction-expiry",
            input_sha256="f" * 64,
            retry_class=RetryClass.NEVER,
            max_attempts=1,
        )
        async with UnitOfWork(database) as uow:
            await uow.workflows.add(workflow)
            await uow.jobs.add(job)
            assert uow.session is not None
            await uow.session.execute(
                update(jobs)
                .where(jobs.c.job_id == job_id)
                .values(
                    state="RUNNING",
                    attempt_count=1,
                    lease_owner="worker-transaction-expiry",
                    lease_token="lease-token",
                    leased_at=actual_now,
                    lease_expires_at=actual_now + timedelta(milliseconds=500),
                )
            )
            await uow.session.execute(
                insert(job_attempts).values(
                    job_id=job_id,
                    attempt_number=1,
                    state="RUNNING",
                    lease_token="lease-token",
                    started_at=actual_now,
                )
            )

        spec = ProductSpec(
            product_spec_id="PS-transaction-expiry",
            candidate_id="candidate-transaction-expiry",
            identity_niche="students",
            base_category="planner",
            target_buyer="students",
            promised_outcome="organise coursework",
            hubs=("home", "courses", "tasks", "calendar", "notes", "review"),
            colour_variants=("ink", "sage", "sand"),
            features=("weekly review",),
            product_facts=("contains six hubs",),
            source_evidence_ids=("EV-1",),
            spec_sha256="1" * 64,
        )
        event_payload = {"product_spec_id": spec.product_spec_id}
        event = DomainEvent(
            event_id=UUID("00000000-0000-0000-0000-000000000213"),
            workflow_run_id=workflow_id,
            job_id=job_id,
            name=DomainEventName.PRODUCT_SPEC_CREATED,
            occurred_at=actual_now,
            payload=event_payload,
            payload_sha256=canonical_sha256(event_payload),
        )

        with pytest.raises(ValueError, match="job completion lease mismatch"):
            async with UnitOfWork(database) as uow:
                assert uow.session is not None
                await uow.session.scalar(select(func.now()))
                await asyncio.sleep(1)
                await uow.commit_job_success(
                    job_id,
                    "lease-token",
                    1,
                    "product_specs",
                    spec,
                    event,
                    None,
                )

        async with database.session_factory() as session:
            assert (
                await session.scalar(select(jobs.c.state).where(jobs.c.job_id == job_id))
                == "RUNNING"
            )
            assert await session.scalar(select(func.count()).select_from(product_specs)) == 0
            assert await session.scalar(select(func.count()).select_from(domain_events)) == 0
        await database.dispose()

    asyncio.run(scenario())
