from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from alembic import command
from alembic.config import Config
from pydantic import AnyHttpUrl
from sqlalchemy import select, update

from money_machine.domain.enums import JobState, ProductState, QualificationDimension, RetryClass
from money_machine.domain.events import DomainEvent, DomainEventName
from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.models.candidate import CandidateShortlist, QualificationScore
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.listing import ListingPackage, PreflightResult
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import DedupeResult, ProductFact, ProductSpec
from money_machine.domain.models.research import (
    EvidenceReference,
    ResearchObservation,
    ResearchPacket,
)
from money_machine.domain.models.workflow import WorkflowRun
from money_machine.domain.value_objects import canonical_sha256
from money_machine.persistence.database import Database
from money_machine.persistence.tables import (
    build_results,
    candidate_shortlists,
    dedupe_results,
    evidence_references,
    jobs,
    listing_packages,
    preflight_results,
    product_qa_results,
    product_specs,
    qualification_scores,
    research_packets,
)
from money_machine.persistence.unit_of_work import UnitOfWork

REPO_ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 8, 9, 8, 0, tzinfo=UTC)
SHA256 = "a" * 64


def _migrate() -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
    command.upgrade(config, "head")


def _evidence(index: int) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=f"evidence-{index}",
        source_url=AnyHttpUrl(f"https://example.test/listing/{index}"),
        observed_at=NOW,
        source_mode="fixture",
        freshness_status="current",
        content_sha256=SHA256,
    )


def _observation(index: int) -> ResearchObservation:
    return ResearchObservation(
        observation_id=f"observation-{index}",
        evidence=_evidence(index),
        marketplace="etsy",
        title=f"Planner {index}",
        category="digital-planners",
        identity_niche="adhd-students",
        base_category="planner",
        price=Decimal("12.00"),
        currency="USD",
        demand_proxies={"reviews": Decimal("10")},
        competition_proxies={"result_count": Decimal("100")},
        qualification_inputs={
            QualificationDimension.DEMAND: Decimal("8"),
            QualificationDimension.DIFFERENTIATION: Decimal("7"),
            QualificationDimension.BUILD_FEASIBILITY: Decimal("9"),
            QualificationDimension.BUYER_VALUE: Decimal("8"),
        },
        listing_quality_notes=("Clear benefit-led title",),
    )


def _score(candidate_id: str, total: int) -> QualificationScore:
    base, remainder = divmod(total, 4)
    dimensions = tuple(base + (1 if index < remainder else 0) for index in range(4))
    return QualificationScore(
        candidate_id=candidate_id,
        demand=dimensions[0],
        differentiation=dimensions[1],
        build_feasibility=dimensions[2],
        buyer_value=dimensions[3],
        evidence_ids=("evidence-0",),
    )


def _spec() -> ProductSpec:
    return ProductSpec(
        product_spec_id="spec-all",
        candidate_id="candidate-31",
        identity_niche="adhd-students",
        base_category="planner",
        target_buyer="People managing adhd-students",
        promised_outcome="A structured planner workspace",
        hubs=("home", "courses", "tasks", "notes", "reviews", "archive"),
        colour_variants=("ink", "sand", "sage"),
        features=("Linked course and task views",),
        product_facts=(
            ProductFact(
                claim="Configured with 6 hubs",
                category="HUB_INVENTORY",
                evidence_ids=("evidence-0",),
            ),
            ProductFact(
                claim="Includes Linked course and task views",
                category="FEATURE",
                evidence_ids=("evidence-0",),
            ),
            ProductFact(
                claim="Configured with 3 colour variants",
                category="COLOUR_VARIANTS",
                evidence_ids=("evidence-0",),
            ),
            ProductFact(
                claim="People managing adhd-students",
                category="BUYER_FIT",
                evidence_ids=("evidence-0",),
            ),
            ProductFact(
                claim="A structured planner workspace",
                category="WORKFLOW_OUTCOME",
                evidence_ids=("evidence-0",),
            ),
        ),
        source_evidence_ids=("evidence-0",),
        spec_sha256=SHA256,
    )


def test_workflow_and_job_round_trip_is_immutable_ordered_and_current() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        workflow = WorkflowRun(
            workflow_run_id=UUID("00000000-0000-0000-0000-000000000101"),
            workflow_type="FIRST_PRODUCT",
            packet_id="RPK-test",
            state=ProductState.RESEARCHED,
            idempotency_key="workflow:RPK-test",
            created_at=NOW,
            updated_at=NOW,
        )
        job = JobEnvelope(
            job_id=UUID("00000000-0000-0000-0000-000000000102"),
            workflow_run_id=workflow.workflow_run_id,
            job_type="ADMIT_RESEARCH_PACKET",
            state=JobState.READY,
            idempotency_key="job:RPK-test:admit",
            input_sha256=SHA256,
            retry_class=RetryClass.TRANSIENT_INTERNAL,
            max_attempts=3,
        )
        successor = job.model_copy(
            update={
                "job_id": UUID("00000000-0000-0000-0000-000000000103"),
                "job_type": "QUALIFY_CANDIDATES",
                "state": JobState.PENDING,
                "idempotency_key": "job:RPK-test:score",
            }
        )
        async with UnitOfWork(database) as uow:
            await uow.workflows.add(workflow)
            await uow.jobs.add(job, available_at=NOW, created_at=NOW)
            await uow.jobs.add(
                successor,
                available_at=NOW,
                created_at=NOW + timedelta(microseconds=1),
            )
            await uow.jobs.add_dependency(successor.job_id, job.job_id)
        async with UnitOfWork(database) as uow:
            assert await uow.workflows.get(workflow.workflow_run_id) == workflow
            assert await uow.jobs.list_for_workflow(workflow.workflow_run_id) == (job, successor)
            claim = await uow.jobs.claim_next(
                owner="worker-test",
                token="token-test",
                now=NOW,
                expires_at=NOW + timedelta(seconds=30),
            )
            assert claim is not None and claim.job.job_id == job.job_id
        async with UnitOfWork(database) as uow:
            await uow.jobs.mark_running(claim, NOW)
            await uow.jobs.require_live_running(claim, NOW)
            await uow.jobs.heartbeat(claim, NOW, NOW + timedelta(seconds=60))
        async with database.session_factory() as session, session.begin():
            await session.execute(
                update(jobs)
                .where(jobs.c.job_id == job.job_id)
                .values(
                    state="SUCCEEDED",
                    lease_owner=None,
                    lease_token=None,
                    leased_at=None,
                    lease_expires_at=None,
                )
            )
        async with UnitOfWork(database) as uow:
            current = await uow.jobs.get(job.job_id)
            assert current is not None and current.state is JobState.SUCCEEDED
            await uow.jobs.add(job)
            assert (
                await uow.jobs.activate_successor(job.job_id, successor.job_type)
                == successor.job_id
            )
            assert uow.session is not None
            await uow.session.execute(
                update(jobs)
                .where(jobs.c.job_id == successor.job_id)
                .values(state=JobState.CANCELLED.value)
            )
            with pytest.raises(ValueError, match="identity collision"):
                await uow.workflows.add(workflow.model_copy(update={"packet_id": "RPK-conflict"}))
        await database.dispose()

    asyncio.run(scenario())


def test_successor_activation_requires_every_declared_dependency_to_succeed() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        workflow = WorkflowRun(
            workflow_run_id=UUID("00000000-0000-0000-0000-000000000121"),
            workflow_type="FIRST_PRODUCT",
            packet_id="RPK-all-dependencies",
            state=ProductState.RESEARCHED,
            idempotency_key="workflow:all-dependencies",
            created_at=NOW,
            updated_at=NOW,
        )
        parent = JobEnvelope(
            job_id=UUID("00000000-0000-0000-0000-000000000122"),
            workflow_run_id=workflow.workflow_run_id,
            job_type="ADMIT_RESEARCH_PACKET",
            state=JobState.SUCCEEDED,
            idempotency_key="job:all-dependencies:parent",
            input_sha256=SHA256,
            retry_class=RetryClass.NEVER,
            max_attempts=1,
        )
        unsatisfied_parent = parent.model_copy(
            update={
                "job_id": UUID("00000000-0000-0000-0000-000000000123"),
                "job_type": "QUALIFY_CANDIDATES",
                "state": JobState.PENDING,
                "idempotency_key": "job:all-dependencies:unsatisfied-parent",
            }
        )
        successor = parent.model_copy(
            update={
                "job_id": UUID("00000000-0000-0000-0000-000000000124"),
                "job_type": "CREATE_PRODUCT_SPEC",
                "state": JobState.PENDING,
                "idempotency_key": "job:all-dependencies:successor",
            }
        )
        async with UnitOfWork(database) as uow:
            await uow.workflows.add(workflow)
            for job in (parent, unsatisfied_parent, successor):
                await uow.jobs.add(job, available_at=NOW, created_at=NOW)
            await uow.jobs.add_dependency(successor.job_id, parent.job_id)
            await uow.jobs.add_dependency(successor.job_id, unsatisfied_parent.job_id)

        with pytest.raises(ValueError, match="unsatisfied dependencies"):
            async with UnitOfWork(database) as uow:
                await uow.jobs.activate_successor(parent.job_id, successor.job_type)

        async with UnitOfWork(database) as uow:
            stored_successor = await uow.jobs.get(successor.job_id)
            assert stored_successor is not None
            assert stored_successor.state is JobState.PENDING
        await database.dispose()

    asyncio.run(scenario())


def test_claim_next_skips_ready_jobs_with_unsatisfied_dependencies() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        workflow = WorkflowRun(
            workflow_run_id=UUID("00000000-0000-0000-0000-000000000131"),
            workflow_type="FIRST_PRODUCT",
            packet_id="RPK-claim-dependencies",
            state=ProductState.RESEARCHED,
            idempotency_key="workflow:claim-dependencies",
            created_at=NOW,
            updated_at=NOW,
        )
        parent = JobEnvelope(
            job_id=UUID("00000000-0000-0000-0000-000000000132"),
            workflow_run_id=workflow.workflow_run_id,
            job_type="ADMIT_RESEARCH_PACKET",
            state=JobState.PENDING,
            idempotency_key="job:claim-dependencies:parent",
            input_sha256=SHA256,
            retry_class=RetryClass.NEVER,
            max_attempts=1,
        )
        successor = parent.model_copy(
            update={
                "job_id": UUID("00000000-0000-0000-0000-000000000133"),
                "job_type": "QUALIFY_CANDIDATES",
                "state": JobState.READY,
                "idempotency_key": "job:claim-dependencies:successor",
            }
        )
        async with UnitOfWork(database) as uow:
            await uow.workflows.add(workflow)
            await uow.jobs.add(parent, available_at=NOW, created_at=NOW)
            await uow.jobs.add(successor, available_at=NOW, created_at=NOW)
            await uow.jobs.add_dependency(successor.job_id, parent.job_id)

        async with UnitOfWork(database) as uow:
            claim = await uow.jobs.claim_next(
                owner="worker-dependencies",
                token="token-dependencies",
                now=NOW,
                expires_at=NOW + timedelta(seconds=30),
            )
            assert claim is None
        await database.dispose()

    asyncio.run(scenario())


def test_every_slice_result_round_trips_with_canonical_hash_and_collision_rejection() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        workflow = WorkflowRun(
            workflow_run_id=UUID("00000000-0000-0000-0000-000000000501"),
            workflow_type="FIRST_PRODUCT",
            packet_id="packet-25",
            state=ProductState.RESEARCHED,
            idempotency_key="workflow:packet-25",
            created_at=NOW,
            updated_at=NOW,
        )
        job = JobEnvelope(
            job_id=UUID("00000000-0000-0000-0000-000000000502"),
            workflow_run_id=workflow.workflow_run_id,
            job_type="ADMIT_RESEARCH_PACKET",
            state=JobState.READY,
            idempotency_key="job:packet-25:admit",
            input_sha256=SHA256,
            retry_class=RetryClass.NEVER,
            max_attempts=1,
        )
        packet = ResearchPacket(
            packet_id="packet-25",
            imported_at=NOW,
            observations=tuple(_observation(index) for index in range(25)),
            packet_sha256=SHA256,
        )
        score_30 = _score("candidate-30", 30)
        score_31 = _score("candidate-31", 31)
        shortlist = CandidateShortlist(
            shortlist_id="shortlist-all",
            packet_id=packet.packet_id,
            candidates=(score_30, score_31),
            selected_candidate_id=score_31.candidate_id,
            backup_candidate_id=score_30.candidate_id,
            shortlist_sha256=SHA256,
        )
        spec = _spec()
        dedupe = DedupeResult(
            dedupe_result_id="dedupe-all",
            product_spec_id=spec.product_spec_id,
            passed=True,
            matched_product_spec_ids=(),
            reasons=(),
            result_sha256=SHA256,
        )
        artifact = ArtifactReference(
            artifact_id="artifact-all",
            relative_path=Path("products/spec-all/index.html"),
            media_type="text/html",
            byte_count=1,
            content_sha256=SHA256,
        )
        build = BuildResult(
            build_id="build-all",
            product_spec_id=spec.product_spec_id,
            root_artifact_path="products/spec-all",
            artifacts=(artifact,),
            manifest_sha256=SHA256,
            renderer_version="1",
        )
        qa = ProductQAResult(
            qa_result_id="qa-all",
            build_id=build.build_id,
            passed=True,
            findings=(),
            checked_at=NOW,
            result_sha256=SHA256,
        )
        listing = ListingPackage(
            listing_package_id="listing-all",
            product_spec_id=spec.product_spec_id,
            build_id=build.build_id,
            title="Planner",
            description="A useful planner",
            tags=tuple(f"tag-{index}" for index in range(13)),
            feature_statements=(),
            buyer_fit_statements=(),
            package_sha256=SHA256,
        )
        preflight = PreflightResult(
            preflight_result_id="preflight-all",
            listing_package_id=listing.listing_package_id,
            passed=True,
            findings=(),
            checked_at=NOW,
            external_effect_mode="simulation",
            incremental_spend=Decimal("0.00"),
            publication_receipt_present=False,
            result_sha256=SHA256,
        )
        event_payload = {"packet_id": packet.packet_id}
        event = DomainEvent(
            event_id=UUID("00000000-0000-0000-0000-000000000503"),
            workflow_run_id=workflow.workflow_run_id,
            job_id=job.job_id,
            name=DomainEventName.RESEARCH_PACKET_ADMITTED,
            occurred_at=NOW,
            payload=event_payload,
            payload_sha256=canonical_sha256(event_payload),
        )

        async with UnitOfWork(database) as uow:
            await uow.workflows.add(workflow)
            await uow.jobs.add(job)
            await uow.research.add_packet(packet)
            await uow.research.add_score(packet.packet_id, score_30)
            await uow.research.add_score(packet.packet_id, score_31)
            await uow.research.add_shortlist(shortlist)
            await uow.products.add_spec(spec)
            await uow.products.add_dedupe(dedupe)
            await uow.artifacts.add(artifact, workflow_run_id=workflow.workflow_run_id)
            await uow.products.add_build(build)
            await uow.products.add_qa(qa)
            await uow.listings.add_package(listing)
            await uow.listings.add_preflight(preflight)
            await uow.events.add(event)

        async with UnitOfWork(database) as uow:
            assert await uow.research.get_packet(packet.packet_id) == packet
            assert await uow.research.get_evidence("evidence-0") == packet.observations[0].evidence
            assert await uow.research.list_scores(packet.packet_id) == (score_30, score_31)
            assert await uow.research.get_shortlist(shortlist.shortlist_id) == shortlist
            assert await uow.products.get_spec(spec.product_spec_id) == spec
            assert await uow.products.get_dedupe(dedupe.dedupe_result_id) == dedupe
            assert await uow.products.get_build(build.build_id) == build
            assert await uow.products.get_qa(qa.qa_result_id) == qa
            assert await uow.listings.get_package(listing.listing_package_id) == listing
            assert await uow.listings.get_preflight(preflight.preflight_result_id) == preflight
            assert await uow.artifacts.get(artifact.artifact_id) == artifact
            assert await uow.events.get(event.event_id) == event
            with pytest.raises(ValueError, match="identity collision"):
                await uow.products.add_spec(
                    spec.model_copy(update={"promised_outcome": "conflict"})
                )

        expected_hashes = {
            research_packets: (research_packets.c.packet_id, packet.packet_id, packet),
            evidence_references: (
                evidence_references.c.evidence_id,
                "evidence-0",
                packet.observations[0].evidence,
            ),
            qualification_scores: (
                qualification_scores.c.qualification_score_id,
                score_30.candidate_id,
                score_30,
            ),
            candidate_shortlists: (
                candidate_shortlists.c.shortlist_id,
                shortlist.shortlist_id,
                shortlist,
            ),
            product_specs: (product_specs.c.product_spec_id, spec.product_spec_id, spec),
            dedupe_results: (dedupe_results.c.dedupe_result_id, dedupe.dedupe_result_id, dedupe),
            build_results: (build_results.c.build_id, build.build_id, build),
            product_qa_results: (
                product_qa_results.c.product_qa_result_id,
                qa.qa_result_id,
                qa,
            ),
            listing_packages: (
                listing_packages.c.listing_package_id,
                listing.listing_package_id,
                listing,
            ),
            preflight_results: (
                preflight_results.c.preflight_result_id,
                preflight.preflight_result_id,
                preflight,
            ),
        }
        async with database.session_factory() as session:
            for table, (identity_column, identity, model) in expected_hashes.items():
                stored_hash = await session.scalar(
                    select(table.c.payload_sha256).where(identity_column == identity)
                )
                assert stored_hash == canonical_sha256(model)
        await database.dispose()

    asyncio.run(scenario())


def test_identical_concurrent_inserts_are_idempotent() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        spec = _spec().model_copy(update={"product_spec_id": "spec-concurrent"})

        async def insert_once() -> None:
            async with UnitOfWork(database) as uow:
                await uow.products.add_spec(spec)

        await asyncio.gather(insert_once(), insert_once())
        async with UnitOfWork(database) as uow:
            assert await uow.products.get_spec(spec.product_spec_id) == spec
        await database.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("repository_name", ["events", "artifacts"])
def test_identical_concurrent_event_and_artifact_inserts_are_idempotent(
    repository_name: str,
) -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        workflow = WorkflowRun(
            workflow_run_id=uuid5(NAMESPACE_URL, f"workflow-concurrent-{repository_name}"),
            workflow_type="FIRST_PRODUCT",
            packet_id=f"RPK-concurrent-{repository_name}",
            state=ProductState.RESEARCHED,
            idempotency_key=f"workflow:concurrent:{repository_name}",
            created_at=NOW,
            updated_at=NOW,
        )
        job = JobEnvelope(
            job_id=uuid5(NAMESPACE_URL, f"job-concurrent-{repository_name}"),
            workflow_run_id=workflow.workflow_run_id,
            job_type="ADMIT_RESEARCH_PACKET",
            state=JobState.READY,
            idempotency_key=f"job:concurrent:{repository_name}",
            input_sha256=SHA256,
            retry_class=RetryClass.NEVER,
            max_attempts=1,
        )
        event_payload = {"repository": repository_name}
        event = DomainEvent(
            event_id=uuid5(NAMESPACE_URL, f"event-concurrent-{repository_name}"),
            workflow_run_id=workflow.workflow_run_id,
            job_id=job.job_id,
            name=DomainEventName.RESEARCH_PACKET_ADMITTED,
            occurred_at=NOW,
            payload=event_payload,
            payload_sha256=canonical_sha256(event_payload),
        )
        artifact = ArtifactReference(
            artifact_id=f"artifact-concurrent-{repository_name}",
            relative_path=Path(f"products/concurrent/{repository_name}.txt"),
            media_type="text/plain",
            byte_count=1,
            content_sha256=SHA256,
        )
        async with UnitOfWork(database) as uow:
            await uow.workflows.add(workflow)
            await uow.jobs.add(job)

        async def insert_once() -> None:
            async with UnitOfWork(database) as uow:
                if repository_name == "events":
                    await uow.events.add(event)
                else:
                    await uow.artifacts.add(
                        artifact,
                        workflow_run_id=workflow.workflow_run_id,
                    )

        await asyncio.gather(insert_once(), insert_once())
        async with UnitOfWork(database) as uow:
            if repository_name == "events":
                assert await uow.events.get(event.event_id) == event
            else:
                assert await uow.artifacts.get(artifact.artifact_id) == artifact
        await database.dispose()

    asyncio.run(scenario())


def test_job_repository_persists_failure_retry_and_expiry_transitions() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        actual_now = datetime.now(UTC)
        workflow = WorkflowRun(
            workflow_run_id=UUID("00000000-0000-0000-0000-000000000401"),
            workflow_type="FIRST_PRODUCT",
            packet_id="RPK-retry",
            state=ProductState.RESEARCHED,
            idempotency_key="workflow:RPK-retry",
            created_at=NOW,
            updated_at=NOW,
        )
        retry_job = JobEnvelope(
            job_id=UUID("00000000-0000-0000-0000-000000000402"),
            workflow_run_id=workflow.workflow_run_id,
            job_type="ADMIT_RESEARCH_PACKET",
            state=JobState.READY,
            idempotency_key="job:RPK-retry:admit",
            input_sha256=SHA256,
            retry_class=RetryClass.TRANSIENT_INTERNAL,
            max_attempts=3,
        )
        expired_job = retry_job.model_copy(
            update={
                "job_id": UUID("00000000-0000-0000-0000-000000000403"),
                "idempotency_key": "job:RPK-expired:admit",
                "retry_class": RetryClass.NEVER,
                "max_attempts": 1,
            }
        )
        async with UnitOfWork(database) as uow:
            await uow.workflows.add(workflow)
            await uow.jobs.add(retry_job, available_at=NOW, created_at=NOW)
            await uow.jobs.add(
                expired_job,
                available_at=NOW,
                created_at=NOW + timedelta(microseconds=1),
            )

        async with UnitOfWork(database) as uow:
            retry_claim = await uow.jobs.claim_next(
                owner="worker-retry",
                token="token-retry",
                now=NOW,
                expires_at=actual_now + timedelta(seconds=30),
            )
            assert retry_claim is not None and retry_claim.job.job_id == retry_job.job_id
            await uow.jobs.mark_running(retry_claim, NOW)
            await uow.jobs.fail_running(
                retry_claim,
                now=NOW + timedelta(seconds=1),
                retry_at=NOW + timedelta(seconds=10),
                error_code="TRANSIENT",
            )
        async with UnitOfWork(database) as uow:
            current = await uow.jobs.get(retry_job.job_id)
            assert current is not None and current.state is JobState.RETRY_WAIT
            assert await uow.jobs.enqueue_due_retries(NOW + timedelta(seconds=9)) == 0
            assert await uow.jobs.enqueue_due_retries(NOW + timedelta(seconds=10)) == 1

        async with UnitOfWork(database) as uow:
            final_claim = await uow.jobs.claim_next(
                owner="worker-retry-final",
                token="token-retry-final",
                now=NOW + timedelta(seconds=10),
                expires_at=actual_now + timedelta(seconds=30),
            )
            assert final_claim is not None and final_claim.job.job_id == retry_job.job_id
            await uow.jobs.mark_running(final_claim, NOW + timedelta(seconds=10))
            await uow.jobs.fail_running(
                final_claim,
                now=NOW + timedelta(seconds=11),
                retry_at=None,
                error_code="EXHAUSTED",
            )

        async with UnitOfWork(database) as uow:
            expired_claim = await uow.jobs.claim_next(
                owner="worker-expired",
                token="token-expired",
                now=NOW + timedelta(seconds=10),
                expires_at=actual_now + timedelta(seconds=1),
            )
            assert expired_claim is not None and expired_claim.job.job_id == expired_job.job_id
        async with UnitOfWork(database) as uow:
            expired = await uow.jobs.list_expired(actual_now + timedelta(seconds=12))
            assert expired_claim in expired
            await uow.jobs.recover_expired(
                expired_claim,
                now=actual_now + timedelta(seconds=12),
                retry_at=None,
            )
        async with UnitOfWork(database) as uow:
            current = await uow.jobs.get(expired_job.job_id)
            assert current is not None and current.state is JobState.FAILED
        await database.dispose()

    asyncio.run(scenario())
