from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from money_machine.domain.enums import JobState, ProductState, RetryClass
from money_machine.domain.events import DomainEvent, DomainEventName
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.product_spec import DedupeResult, ProductFact, ProductSpec
from money_machine.domain.models.workflow import WorkflowBlocker, WorkflowRun
from money_machine.domain.value_objects import canonical_sha256
from money_machine.persistence.database import Database
from money_machine.persistence.tables import (
    dedupe_results,
    domain_events,
    job_attempts,
    jobs,
    product_specs,
    workflow_runs,
)
from money_machine.persistence.unit_of_work import UnitOfWork

REPO_ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 8, 9, tzinfo=UTC)


def _product_facts() -> tuple[ProductFact, ...]:
    return (
        ProductFact(
            claim="Configured with 6 hubs",
            category="HUB_INVENTORY",
            evidence_ids=("EV-1",),
        ),
        ProductFact(
            claim="Includes weekly review",
            category="FEATURE",
            evidence_ids=("EV-1",),
        ),
        ProductFact(
            claim="Configured with 3 colour variants",
            category="COLOUR_VARIANTS",
            evidence_ids=("EV-1",),
        ),
        ProductFact(
            claim="People managing students",
            category="BUYER_FIT",
            evidence_ids=("EV-1",),
        ),
        ProductFact(
            claim="A structured planner workspace",
            category="WORKFLOW_OUTCOME",
            evidence_ids=("EV-1",),
        ),
    )


def test_job_completion_advances_workflow_state_and_canonical_payload_atomically() -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
    command.upgrade(config, "head")

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        actual_now = datetime.now(UTC)
        workflow_id = UUID("00000000-0000-0000-0000-000000000221")
        job_id = UUID("00000000-0000-0000-0000-000000000222")
        workflow = WorkflowRun(
            workflow_run_id=workflow_id,
            workflow_type="FIRST_PRODUCT_VERTICAL_SLICE",
            packet_id="RPK-workflow-progress",
            state=ProductState.QUALIFIED,
            idempotency_key="workflow:RPK-workflow-progress",
            created_at=NOW,
            updated_at=NOW,
        )
        job = JobEnvelope(
            job_id=job_id,
            workflow_run_id=workflow_id,
            job_type="CREATE_PRODUCT_SPEC",
            state=JobState.READY,
            idempotency_key="job:workflow-progress",
            input_sha256="9" * 64,
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
                    lease_owner="worker-progress",
                    lease_token="lease-token",
                    leased_at=actual_now,
                    lease_expires_at=actual_now + timedelta(minutes=5),
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
            product_spec_id="PS-workflow-progress",
            candidate_id="candidate-workflow-progress",
            identity_niche="students",
            base_category="planner",
            target_buyer="People managing students",
            promised_outcome="A structured planner workspace",
            hubs=("home", "courses", "tasks", "calendar", "notes", "review"),
            colour_variants=("ink", "sage", "sand"),
            features=("weekly review",),
            product_facts=_product_facts(),
            source_evidence_ids=("EV-1",),
            spec_sha256="8" * 64,
        )
        event_payload = {"product_spec_id": spec.product_spec_id}
        event = DomainEvent(
            event_id=UUID("00000000-0000-0000-0000-000000000223"),
            workflow_run_id=workflow_id,
            job_id=job_id,
            name=DomainEventName.PRODUCT_SPEC_CREATED,
            occurred_at=actual_now,
            payload=event_payload,
            payload_sha256=canonical_sha256(event_payload),
        )

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
            row = (
                await session.execute(
                    select(
                        workflow_runs.c.state,
                        workflow_runs.c.payload,
                        workflow_runs.c.payload_sha256,
                        workflow_runs.c.updated_at,
                    ).where(workflow_runs.c.workflow_run_id == workflow_id)
                )
            ).one()
            persisted = WorkflowRun.model_validate_json(json.dumps(row.payload))
            assert row.state == ProductState.SPECIFIED.value
            assert persisted.state is ProductState.SPECIFIED
            assert persisted.updated_at == event.occurred_at
            assert row.updated_at == event.occurred_at
            assert row.payload_sha256 == canonical_sha256(persisted)
            assert (
                await session.scalar(select(jobs.c.state).where(jobs.c.job_id == job_id))
                == JobState.SUCCEEDED.value
            )
            await session.execute(
                delete(product_specs).where(product_specs.c.product_spec_id == spec.product_spec_id)
            )
            await session.execute(
                delete(workflow_runs).where(workflow_runs.c.workflow_run_id == workflow_id)
            )
            await session.commit()
        await database.dispose()

    asyncio.run(scenario())


def test_job_completion_rejects_backward_workflow_event_time_atomically() -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
    command.upgrade(config, "head")

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        actual_now = datetime.now(UTC)
        workflow_id = UUID("00000000-0000-0000-0000-000000000231")
        job_id = UUID("00000000-0000-0000-0000-000000000232")
        workflow = WorkflowRun(
            workflow_run_id=workflow_id,
            workflow_type="FIRST_PRODUCT_VERTICAL_SLICE",
            packet_id="RPK-backward-workflow-clock",
            state=ProductState.QUALIFIED,
            idempotency_key="workflow:RPK-backward-workflow-clock",
            created_at=NOW,
            updated_at=actual_now,
        )
        job = JobEnvelope(
            job_id=job_id,
            workflow_run_id=workflow_id,
            job_type="CREATE_PRODUCT_SPEC",
            state=JobState.READY,
            idempotency_key="job:backward-workflow-clock",
            input_sha256="7" * 64,
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
                    lease_owner="worker-backward-clock",
                    lease_token="lease-token",
                    leased_at=actual_now,
                    lease_expires_at=actual_now + timedelta(minutes=5),
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
            product_spec_id="PS-backward-workflow-clock",
            candidate_id="candidate-backward-workflow-clock",
            identity_niche="students",
            base_category="planner",
            target_buyer="People managing students",
            promised_outcome="A structured planner workspace",
            hubs=("home", "courses", "tasks", "calendar", "notes", "review"),
            colour_variants=("ink", "sage", "sand"),
            features=("weekly review",),
            product_facts=_product_facts(),
            source_evidence_ids=("EV-1",),
            spec_sha256="6" * 64,
        )
        event_payload = {"product_spec_id": spec.product_spec_id}
        event = DomainEvent(
            event_id=UUID("00000000-0000-0000-0000-000000000233"),
            workflow_run_id=workflow_id,
            job_id=job_id,
            name=DomainEventName.PRODUCT_SPEC_CREATED,
            occurred_at=actual_now - timedelta(seconds=1),
            payload=event_payload,
            payload_sha256=canonical_sha256(event_payload),
        )

        with pytest.raises(ValueError, match="workflow event time precedes current update"):
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
            persisted_job = (
                await session.execute(
                    select(jobs.c.state, jobs.c.lease_token).where(jobs.c.job_id == job_id)
                )
            ).one()
            persisted_attempt = (
                await session.execute(
                    select(job_attempts.c.state, job_attempts.c.completed_at).where(
                        job_attempts.c.job_id == job_id,
                        job_attempts.c.attempt_number == 1,
                    )
                )
            ).one()
            persisted_workflow = (
                await session.execute(
                    select(
                        workflow_runs.c.state,
                        workflow_runs.c.payload,
                        workflow_runs.c.payload_sha256,
                    ).where(workflow_runs.c.workflow_run_id == workflow_id)
                )
            ).one()
            assert persisted_job.state == JobState.RUNNING.value
            assert persisted_job.lease_token == "lease-token"
            assert persisted_attempt.state == JobState.RUNNING.value
            assert persisted_attempt.completed_at is None
            assert persisted_workflow.state == ProductState.QUALIFIED.value
            assert persisted_workflow.payload["state"] == ProductState.QUALIFIED.value
            assert persisted_workflow.payload_sha256 == canonical_sha256(workflow)
            assert await session.scalar(select(func.count()).select_from(product_specs)) == 0
            assert await session.scalar(select(func.count()).select_from(domain_events)) == 0
            await session.execute(
                delete(workflow_runs).where(workflow_runs.c.workflow_run_id == workflow_id)
            )
            await session.commit()
        await database.dispose()

    asyncio.run(scenario())


def test_business_terminal_persists_result_blocker_event_and_workflow_atomically() -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
    command.upgrade(config, "head")

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        actual_now = datetime.now(UTC)
        workflow_id = UUID("00000000-0000-0000-0000-000000000241")
        job_id = UUID("00000000-0000-0000-0000-000000000242")
        workflow = WorkflowRun(
            workflow_run_id=workflow_id,
            workflow_type="FIRST_PRODUCT_VERTICAL_SLICE",
            packet_id="RPK-terminal-dedupe",
            state=ProductState.SPECIFIED,
            idempotency_key="workflow:RPK-terminal-dedupe",
            created_at=NOW,
            updated_at=NOW,
        )
        job = JobEnvelope(
            job_id=job_id,
            workflow_run_id=workflow_id,
            job_type="CHECK_CATALOGUE_DEDUPE",
            state=JobState.READY,
            idempotency_key="job:terminal-dedupe",
            input_sha256="5" * 64,
            retry_class=RetryClass.NEVER,
            max_attempts=1,
        )
        product_spec = ProductSpec(
            product_spec_id="PS-terminal-dedupe",
            candidate_id="candidate-terminal-dedupe",
            identity_niche="students",
            base_category="planner",
            target_buyer="People managing students",
            promised_outcome="A structured planner workspace",
            hubs=("home", "courses", "tasks", "calendar", "notes", "review"),
            colour_variants=("ink", "sage", "sand"),
            features=("weekly review",),
            product_facts=_product_facts(),
            source_evidence_ids=("EV-1",),
            spec_sha256="3" * 64,
        )
        async with UnitOfWork(database) as uow:
            await uow.workflows.add(workflow)
            await uow.jobs.add(job)
            await uow.products.add_spec(product_spec)
            assert uow.session is not None
            await uow.session.execute(
                update(jobs)
                .where(jobs.c.job_id == job_id)
                .values(
                    state="RUNNING",
                    attempt_count=1,
                    lease_owner="worker-terminal-dedupe",
                    lease_token="lease-token",
                    leased_at=actual_now,
                    lease_expires_at=actual_now + timedelta(minutes=5),
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

        result = DedupeResult(
            dedupe_result_id="DDR-terminal-dedupe",
            product_spec_id="PS-terminal-dedupe",
            passed=False,
            matched_product_spec_ids=("PS-existing",),
            reasons=("TITLE_TOKEN_OVERLAP_AT_OR_ABOVE_0.700",),
            result_sha256="4" * 64,
        )
        result_hash = canonical_sha256(result)
        blocker = WorkflowBlocker(
            blocker_id="BLK-terminal-dedupe",
            job_id=job_id,
            terminal_state=ProductState.REJECTED,
            code="CATALOGUE_DUPLICATE",
            message="The product specification matches an existing catalogue item.",
            result_type="dedupe_results",
            result_id=result.dedupe_result_id,
            result_sha256=result_hash,
            occurred_at=actual_now,
        )
        event_payload = {
            "blocker_id": blocker.blocker_id,
            "terminal_state": blocker.terminal_state.value,
            "code": blocker.code,
            "message": blocker.message,
            "result_type": blocker.result_type,
            "result_id": blocker.result_id,
            "result_sha256": blocker.result_sha256,
        }
        event = DomainEvent(
            event_id=UUID("00000000-0000-0000-0000-000000000243"),
            workflow_run_id=workflow_id,
            job_id=job_id,
            name=DomainEventName.WORKFLOW_REJECTED,
            occurred_at=actual_now,
            payload=event_payload,
            payload_sha256=canonical_sha256(event_payload),
        )

        async def assert_terminal_rollback() -> None:
            async with database.session_factory() as session:
                persisted_job = (
                    await session.execute(
                        select(jobs.c.state, jobs.c.lease_token).where(jobs.c.job_id == job_id)
                    )
                ).one()
                persisted_attempt = (
                    await session.execute(
                        select(job_attempts.c.state, job_attempts.c.completed_at).where(
                            job_attempts.c.job_id == job_id,
                            job_attempts.c.attempt_number == 1,
                        )
                    )
                ).one()
                persisted_workflow = (
                    await session.execute(
                        select(
                            workflow_runs.c.state,
                            workflow_runs.c.payload,
                            workflow_runs.c.payload_sha256,
                        ).where(workflow_runs.c.workflow_run_id == workflow_id)
                    )
                ).one()
                assert persisted_job.state == JobState.RUNNING.value
                assert persisted_job.lease_token == "lease-token"
                assert persisted_attempt.state == JobState.RUNNING.value
                assert persisted_attempt.completed_at is None
                assert persisted_workflow.state == ProductState.SPECIFIED.value
                assert persisted_workflow.payload["terminal_blocker"] is None
                assert persisted_workflow.payload_sha256 == canonical_sha256(workflow)
                assert await session.scalar(select(func.count()).select_from(product_specs)) == 1
                assert await session.scalar(select(func.count()).select_from(dedupe_results)) == 0
                assert await session.scalar(select(func.count()).select_from(domain_events)) == 0

        wrong_result = product_spec.model_copy(
            update={
                "product_spec_id": "PS-wrong-terminal-result",
                "spec_sha256": "8" * 64,
            }
        )
        wrong_result_hash = canonical_sha256(wrong_result)
        wrong_blocker = blocker.model_copy(
            update={
                "blocker_id": "BLK-wrong-terminal-result",
                "result_type": "product_specs",
                "result_id": wrong_result.product_spec_id,
                "result_sha256": wrong_result_hash,
            }
        )
        wrong_event_payload = {
            "blocker_id": wrong_blocker.blocker_id,
            "terminal_state": wrong_blocker.terminal_state.value,
            "code": wrong_blocker.code,
            "message": wrong_blocker.message,
            "result_type": wrong_blocker.result_type,
            "result_id": wrong_blocker.result_id,
            "result_sha256": wrong_blocker.result_sha256,
        }
        wrong_event = event.model_copy(
            update={
                "event_id": UUID("00000000-0000-0000-0000-000000000244"),
                "payload": wrong_event_payload,
                "payload_sha256": canonical_sha256(wrong_event_payload),
            }
        )
        with pytest.raises(ValueError, match="terminal result contract mismatch"):
            async with UnitOfWork(database) as uow:
                await uow.commit_job_terminal(
                    job_id,
                    "lease-token",
                    1,
                    wrong_blocker,
                    wrong_event,
                    result_type="product_specs",
                    result_payload=wrong_result,
                )
        await assert_terminal_rollback()

        forged_result = result.model_copy(update={"passed": True})
        forged_result_hash = canonical_sha256(forged_result)
        forged_blocker = blocker.model_copy(
            update={
                "blocker_id": "BLK-forged-terminal-result",
                "result_sha256": forged_result_hash,
            }
        )
        forged_event_payload = {
            "blocker_id": forged_blocker.blocker_id,
            "terminal_state": forged_blocker.terminal_state.value,
            "code": forged_blocker.code,
            "message": forged_blocker.message,
            "result_type": forged_blocker.result_type,
            "result_id": forged_blocker.result_id,
            "result_sha256": forged_blocker.result_sha256,
        }
        forged_event = event.model_copy(
            update={
                "event_id": UUID("00000000-0000-0000-0000-000000000245"),
                "payload": forged_event_payload,
                "payload_sha256": canonical_sha256(forged_event_payload),
            }
        )
        with pytest.raises(ValueError, match="terminal result model invalid"):
            async with UnitOfWork(database) as uow:
                await uow.commit_job_terminal(
                    job_id,
                    "lease-token",
                    1,
                    forged_blocker,
                    forged_event,
                    result_type="dedupe_results",
                    result_payload=forged_result,
                )
        await assert_terminal_rollback()

        async with UnitOfWork(database) as uow:
            await uow.commit_job_terminal(
                job_id,
                "lease-token",
                1,
                blocker,
                event,
                result_type="dedupe_results",
                result_payload=result,
            )

        with pytest.raises(ValueError, match="job terminal lease mismatch"):
            async with UnitOfWork(database) as uow:
                await uow.commit_job_terminal(
                    job_id,
                    "lease-token",
                    1,
                    blocker,
                    event,
                    result_type="dedupe_results",
                    result_payload=result,
                )

        async with database.session_factory() as session:
            persisted_job = (
                await session.execute(
                    select(jobs.c.state, jobs.c.lease_token).where(jobs.c.job_id == job_id)
                )
            ).one()
            persisted_attempt = (
                await session.execute(
                    select(job_attempts.c.state, job_attempts.c.completed_at).where(
                        job_attempts.c.job_id == job_id,
                        job_attempts.c.attempt_number == 1,
                    )
                )
            ).one()
            persisted_workflow = (
                await session.execute(
                    select(
                        workflow_runs.c.state,
                        workflow_runs.c.payload,
                        workflow_runs.c.payload_sha256,
                    ).where(workflow_runs.c.workflow_run_id == workflow_id)
                )
            ).one()
            reloaded = WorkflowRun.model_validate_json(json.dumps(persisted_workflow.payload))
            assert persisted_job.state == JobState.SUCCEEDED.value
            assert persisted_job.lease_token is None
            assert persisted_attempt.state == JobState.SUCCEEDED.value
            assert persisted_attempt.completed_at == actual_now
            assert persisted_workflow.state == ProductState.REJECTED.value
            assert reloaded.state is ProductState.REJECTED
            assert reloaded.terminal_blocker == blocker
            assert persisted_workflow.payload_sha256 == canonical_sha256(reloaded)
            assert await session.scalar(select(func.count()).select_from(dedupe_results)) == 1
            assert await session.scalar(select(func.count()).select_from(domain_events)) == 1
            await session.execute(
                delete(dedupe_results).where(
                    dedupe_results.c.dedupe_result_id == result.dedupe_result_id
                )
            )
            await session.execute(
                delete(product_specs).where(
                    product_specs.c.product_spec_id == product_spec.product_spec_id
                )
            )
            await session.execute(
                delete(workflow_runs).where(workflow_runs.c.workflow_run_id == workflow_id)
            )
            await session.commit()
        await database.dispose()

    asyncio.run(scenario())


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
            state=ProductState.QUALIFIED,
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
            job_type="CHECK_CATALOGUE_DEDUPE",
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
            target_buyer="People managing students",
            promised_outcome="A structured planner workspace",
            hubs=("home", "courses", "tasks", "calendar", "notes", "review"),
            colour_variants=("ink", "sage", "sand"),
            features=("weekly review",),
            product_facts=_product_facts(),
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
            persisted_workflow = (
                await session.execute(
                    select(workflow_runs.c.state, workflow_runs.c.payload).where(
                        workflow_runs.c.workflow_run_id == workflow_id
                    )
                )
            ).one()
            assert persisted_workflow.state == ProductState.QUALIFIED.value
            assert persisted_workflow.payload["state"] == ProductState.QUALIFIED.value
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
            target_buyer="People managing students",
            promised_outcome="A structured planner workspace",
            hubs=("home", "courses", "tasks", "calendar", "notes", "review"),
            colour_variants=("ink", "sage", "sand"),
            features=("weekly review",),
            product_facts=_product_facts(),
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
            target_buyer="People managing students",
            promised_outcome="A structured planner workspace",
            hubs=("home", "courses", "tasks", "calendar", "notes", "review"),
            colour_variants=("ink", "sage", "sand"),
            features=("weekly review",),
            product_facts=_product_facts(),
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


def test_job_failure_rejects_lease_that_expires_after_caller_timestamp() -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
    command.upgrade(config, "head")

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        actual_now = datetime.now(UTC)
        workflow_id = UUID("00000000-0000-0000-0000-000000000221")
        job_id = UUID("00000000-0000-0000-0000-000000000222")
        workflow = WorkflowRun(
            workflow_run_id=workflow_id,
            workflow_type="FIRST_PRODUCT",
            packet_id="RPK-failure-statement-clock",
            state=ProductState.RESEARCHED,
            idempotency_key="workflow:failure-statement-clock",
            created_at=NOW,
            updated_at=NOW,
        )
        job = JobEnvelope(
            job_id=job_id,
            workflow_run_id=workflow_id,
            job_type="ADMIT_RESEARCH_PACKET",
            state=JobState.READY,
            idempotency_key="job:failure-statement-clock",
            input_sha256="9" * 64,
            retry_class=RetryClass.TRANSIENT_INTERNAL,
            max_attempts=3,
        )
        async with UnitOfWork(database) as uow:
            await uow.workflows.add(workflow)
            await uow.jobs.add(job, available_at=actual_now, created_at=actual_now)

        async with UnitOfWork(database) as uow:
            claim = await uow.jobs.claim_next(
                owner="worker-failure-statement-clock",
                token="lease-token",
                now=actual_now,
                expires_at=actual_now + timedelta(milliseconds=300),
            )
            assert claim is not None
            await uow.jobs.mark_running(claim, actual_now)

        async with UnitOfWork(database) as uow:
            assert uow.session is not None
            sampled_at = await uow.session.scalar(select(func.clock_timestamp()))
            assert sampled_at is not None
            await asyncio.sleep(0.6)
            with pytest.raises(ValueError, match="job failure lease mismatch"):
                await uow.jobs.fail_running(
                    claim,
                    now=sampled_at,
                    retry_at=sampled_at + timedelta(seconds=1),
                    error_code="TRANSIENT",
                )

        async with database.session_factory() as session:
            row = (
                await session.execute(
                    select(
                        jobs.c.state,
                        jobs.c.lease_owner,
                        jobs.c.lease_token,
                        jobs.c.lease_expires_at,
                    ).where(jobs.c.job_id == job_id)
                )
            ).one()
            assert row.state == JobState.RUNNING.value
            assert row.lease_owner == "worker-failure-statement-clock"
            assert row.lease_token == "lease-token"
            assert row.lease_expires_at is not None
            attempt = (
                await session.execute(
                    select(job_attempts.c.state, job_attempts.c.completed_at).where(
                        job_attempts.c.job_id == job_id,
                        job_attempts.c.attempt_number == 1,
                    )
                )
            ).one()
            assert attempt.state == JobState.RUNNING.value
            assert attempt.completed_at is None
        await database.dispose()

    asyncio.run(scenario())
