"""Idempotency and event uniqueness must hold under genuinely concurrent writers.

A unique index is not proved by two serial inserts in one session: the interesting case is
two connections racing. These tests open separate sessions and commit them concurrently.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from money_machine.domain.events import EventName
from money_machine.persistence.tables import Event, IdempotencyRecord
from tests.integration.factories import NOW, make_job, make_shop, make_workflow

CONCURRENCY = 5


async def test_concurrent_idempotency_reservations_yield_exactly_one_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Five writers racing on one key produce one row and four failures."""
    async with session_factory() as setup:
        shop = await make_shop(setup)
        workflow = await make_workflow(setup, shop)
        job = await make_job(setup, workflow)
        job_id = job.id
        await setup.commit()

    key = f"ETSY_PUBLISH:{uuid4()}"

    async def attempt() -> bool:
        async with session_factory() as session:
            session.add(
                IdempotencyRecord(
                    idempotency_key=key,
                    job_id=job_id,
                    operation="ETSY_PUBLISH",
                    side_effect_class="EXTERNAL_WRITE",
                )
            )
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False

    results = await asyncio.gather(*(attempt() for _ in range(CONCURRENCY)))

    assert sum(results) == 1, results
    async with session_factory() as check:
        total = (
            await check.execute(
                select(func.count())
                .select_from(IdempotencyRecord)
                .where(IdempotencyRecord.idempotency_key == key)
            )
        ).scalar_one()
    assert total == 1


async def test_concurrent_event_appends_deduplicate_on_the_semantic_key(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The same domain event emitted twice at once is recorded once."""
    async with session_factory() as setup:
        shop = await make_shop(setup)
        workflow = await make_workflow(setup, shop)
        workflow_id = workflow.id
        await setup.commit()

    dedupe_key = f"RESEARCH_COMPLETED:{workflow_id}"

    async def attempt() -> bool:
        async with session_factory() as session:
            session.add(
                Event(
                    event_name=EventName.RESEARCH_COMPLETED.value,
                    aggregate_type="workflow_runs",
                    aggregate_id=workflow_id,
                    workflow_id=workflow_id,
                    dedupe_key=dedupe_key,
                    payload={},
                    occurred_at=NOW,
                )
            )
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False

    results = await asyncio.gather(*(attempt() for _ in range(CONCURRENCY)))

    assert sum(results) == 1, results
    async with session_factory() as check:
        total = (
            await check.execute(
                select(func.count()).select_from(Event).where(Event.dedupe_key == dedupe_key)
            )
        ).scalar_one()
    assert total == 1


async def test_a_failed_transaction_leaves_no_partial_state(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A unit of work either commits everything or nothing."""
    from money_machine.persistence.unit_of_work import unit_of_work

    async with session_factory() as setup:
        shop = await make_shop(setup)
        workflow = await make_workflow(setup, shop)
        await setup.commit()
        shop_id = shop.id
        workflow_id = workflow.id

    key = f"ETSY_DRAFT_WRITE:{uuid4()}"
    try:
        async with unit_of_work(session_factory) as work:
            job = await make_job(work.session, await work.workflows.require(workflow_id))
            await work.idempotency.reserve(
                idempotency_key=key,
                job_id=job.id,
                operation="ETSY_DRAFT_WRITE",
                side_effect_class="EXTERNAL_WRITE",
            )
            raise RuntimeError("the effect failed after the reservation")
    except RuntimeError:
        pass

    async with session_factory() as check:
        reservations = (
            await check.execute(
                select(func.count())
                .select_from(IdempotencyRecord)
                .where(IdempotencyRecord.idempotency_key == key)
            )
        ).scalar_one()
        assert reservations == 0
        assert await check.get(type(shop), shop_id) is not None
