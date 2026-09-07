"""Repository behaviour and the database constraints behind it."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.enums import JobStatus, ProductLifecycleState
from money_machine.domain.events import EventName
from money_machine.persistence.repositories._base import (
    MAX_PAGE_SIZE,
    ConcurrentModificationError,
)
from money_machine.persistence.repositories.agents import (
    AgentDefinitionRepository,
    AgentRunRepository,
    PromptVersionRepository,
)
from money_machine.persistence.repositories.events import (
    EventAppendError,
    EventRepository,
    IdempotencyRepository,
)
from money_machine.persistence.repositories.jobs import JobRepository
from money_machine.persistence.repositories.shops import ShopRepository
from money_machine.persistence.repositories.workflows import WorkflowRunRepository
from money_machine.persistence.tables import Job
from tests.integration.factories import NOW, make_agent_run, make_job, make_shop, make_workflow


async def test_shop_round_trip_and_soft_deactivation(session: AsyncSession) -> None:
    """A shop is fetched by name and deactivated rather than deleted."""
    repository = ShopRepository(session)
    shop = await make_shop(session)

    assert await repository.by_name("test-shop") == shop
    assert shop in await repository.active()

    shop.active = False
    shop.deactivated_at = NOW
    await session.flush()

    assert shop not in await repository.active()
    assert await repository.get(shop.id) is not None


async def test_duplicate_shop_name_is_rejected_by_the_database(session: AsyncSession) -> None:
    """Uniqueness is enforced by the database, not by application checks alone."""
    await make_shop(session, "unique-shop")

    with pytest.raises(IntegrityError):
        await make_shop(session, "unique-shop")


async def test_job_idempotency_key_is_unique(session: AsyncSession) -> None:
    """Two jobs cannot share an idempotency key."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    await make_job(session, workflow, idempotency_key="ETSY_PUBLISH:1")

    with pytest.raises(IntegrityError):
        await make_job(session, workflow, idempotency_key="ETSY_PUBLISH:1")


async def test_job_attempt_budget_is_enforced(session: AsyncSession) -> None:
    """A job cannot record more attempts than its budget allows."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)

    with pytest.raises(IntegrityError):
        await make_job(session, workflow, attempt=4, max_attempts=3)


async def test_ready_due_query_reads_without_claiming(session: AsyncSession) -> None:
    """Reading ready work leaves the row untouched: claiming is Session 03."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    due = await make_job(session, workflow, status=JobStatus.READY.value, scheduled_at=NOW)
    await make_job(
        session,
        workflow,
        status=JobStatus.READY.value,
        scheduled_at=NOW + timedelta(hours=1),
    )
    await make_job(session, workflow, status=JobStatus.PENDING.value, scheduled_at=NOW)

    found = await JobRepository(session).ready_due(NOW)

    assert [row.id for row in found] == [due.id]
    assert due.status == JobStatus.READY.value
    assert due.lease_owner is None
    assert due.version == 1


async def test_pagination_is_bounded_and_reports_totals(session: AsyncSession) -> None:
    """No repository returns an unbounded result set."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    for _ in range(5):
        await make_job(session, workflow)
    repository = JobRepository(session)

    first = await repository.page(limit=2, offset=0)
    second = await repository.page(limit=2, offset=2)

    assert len(first.items) == 2
    assert first.total == 5
    assert first.has_more
    assert {row.id for row in first.items}.isdisjoint({row.id for row in second.items})
    with pytest.raises(ValueError, match="limit must be between"):
        await repository.page(limit=MAX_PAGE_SIZE + 1)
    with pytest.raises(ValueError, match="offset must not be negative"):
        await repository.page(offset=-1)


async def test_optimistic_versioning_rejects_a_stale_writer(session: AsyncSession) -> None:
    """A second writer holding an old version loses rather than overwriting."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    repository = WorkflowRunRepository(session)

    await repository.update_versioned(
        workflow,
        expected_version=1,
        product_state=ProductLifecycleState.RESEARCHING.value,
    )

    assert workflow.version == 2
    assert workflow.product_state == ProductLifecycleState.RESEARCHING.value
    with pytest.raises(ConcurrentModificationError):
        await repository.update_versioned(
            workflow,
            expected_version=1,
            product_state=ProductLifecycleState.RESEARCH_COMPLETE.value,
        )


async def test_event_append_is_immutable_and_deduplicated(session: AsyncSession) -> None:
    """The event log appends; it never rewrites and never duplicates a semantic key."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(session, workflow)
    repository = EventRepository(session)

    event = await repository.append(
        event_name=EventName.RESEARCH_COMPLETED,
        aggregate_type="workflow_runs",
        aggregate_id=workflow.id,
        dedupe_key=f"RESEARCH_COMPLETED:{workflow.id}",
        occurred_at=NOW,
        workflow_id=workflow.id,
        job_id=job.id,
        payload={"rows": 30},
    )

    assert (await repository.for_aggregate(workflow.id)) == (event,)
    with pytest.raises(EventAppendError, match="already recorded"):
        await repository.append(
            event_name=EventName.RESEARCH_COMPLETED,
            aggregate_type="workflow_runs",
            aggregate_id=workflow.id,
            dedupe_key=f"RESEARCH_COMPLETED:{workflow.id}",
            occurred_at=NOW,
        )


async def test_idempotency_reservation_is_unique(session: AsyncSession) -> None:
    """A reservation happens once, so an external effect cannot run twice."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(session, workflow)
    repository = IdempotencyRepository(session)

    await repository.reserve(
        idempotency_key="ETSY_PUBLISH:listing-1",
        job_id=job.id,
        operation="ETSY_PUBLISH",
        side_effect_class="EXTERNAL_WRITE",
    )

    assert await repository.by_key("ETSY_PUBLISH:listing-1") is not None
    with pytest.raises(IntegrityError):
        await repository.reserve(
            idempotency_key="ETSY_PUBLISH:listing-1",
            job_id=job.id,
            operation="ETSY_PUBLISH",
            side_effect_class="EXTERNAL_WRITE",
        )


async def test_agent_run_carries_the_full_lineage_chain(session: AsyncSession) -> None:
    """A run names its agent version and the exact prompt hash that produced it."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(session, workflow)

    run = await make_agent_run(session, job)

    assert await AgentRunRepository(session).for_job(job.id) == (run,)
    definition = await AgentDefinitionRepository(session).by_agent_id("A03")
    assert definition is not None
    assert definition.commissioning_state == "DESIGNED"
    prompt = await PromptVersionRepository(session).by_sha256(run.prompt_sha256)
    assert prompt is not None
    assert run.prompt_version_id == prompt.id
    assert run.agent_definition_version == 1


async def test_commissioned_state_requires_evidence(session: AsyncSession) -> None:
    """A commissioning claim without evidence is refused by the database."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(session, workflow)
    run = await make_agent_run(session, job)
    definition = await AgentDefinitionRepository(session).get(run.agent_definition_id)
    assert definition is not None

    definition.commissioning_state = "COMMISSIONED"

    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("status", "NOT_A_STATUS"),
        ("side_effect_class", "EXTERNAL_TELEPATHY"),
        ("retry_class", "MAYBE"),
        ("allowed_mode", "yolo"),
        ("owner_agent_id", "A99"),
    ],
)
async def test_state_taxonomies_are_enforced_by_the_database(
    session: AsyncSession,
    column: str,
    value: str,
) -> None:
    """An invalid state cannot be written even if application validation is bypassed."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(session, workflow)

    setattr(job, column, value)

    with pytest.raises((IntegrityError, DBAPIError)):
        await session.flush()


async def test_successor_workflow_cannot_be_its_own_parent(session: AsyncSession) -> None:
    """The MULTIPLY boundary is a database rule, not only a code rule (D-0017)."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)

    workflow.parent_workflow_id = workflow.id

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_repository_require_refuses_a_missing_row(session: AsyncSession) -> None:
    """A required read fails loudly rather than returning None."""
    with pytest.raises(LookupError, match="does not exist"):
        await JobRepository(session).require(uuid4())


async def test_job_repository_exposes_no_claim_method() -> None:
    """Session 02 must not ship a claim path (corrective addendum 1)."""
    surface = {name for name in dir(JobRepository) if not name.startswith("_")}

    assert not {"claim", "claim_next", "lease", "acquire", "transition"} & surface
    assert "ready_due" in surface
    assert Job.__table__.c["lease_owner"] is not None
