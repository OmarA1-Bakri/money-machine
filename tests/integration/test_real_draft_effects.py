from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from money_machine.application.real_draft_authority import DraftRunAuthority, DraftRunRefused
from money_machine.application.real_draft_effects import DraftEffectUncertain, SqlDraftEffects
from money_machine.persistence.tables import IdempotencyRecord, Job, Receipt, Shop, WorkflowRun


async def prepare(factory):
    now = datetime.now(UTC)
    product = uuid4()
    job_id = uuid4()
    parent = uuid4()
    authority = DraftRunAuthority(
        run_id="real-effect-test", product_id=product, verified_notion_parent_id=parent
    )
    async with factory() as s, s.begin():
        shop = Shop(name="QuietlyBuiltStudio", connection_state="CONNECTED", timezone="UTC")
        s.add(shop)
        await s.flush()
        workflow = WorkflowRun(
            shop_id=shop.id, workflow_type="RealProductDraft", workflow_version=1
        )
        s.add(workflow)
        await s.flush()
        s.add(
            Job(
                id=job_id,
                workflow_id=workflow.id,
                job_type="RealProductBuild",
                object_type="Product",
                object_id=product,
                owner_agent_id="A07",
                status="RUNNING",
                input={"run_id": authority.run_id},
                scheduled_at=now,
                idempotency_key=str(job_id),
                side_effect_class="EXTERNAL_WRITE",
                retry_class="RECONCILE_FIRST",
                allowed_mode="draft",
                lease_owner="test-owner",
                lease_expires_at=now + timedelta(minutes=10),
            )
        )
    return SqlDraftEffects(factory, authority, job_id, lease_owner="test-owner"), parent


@pytest.mark.asyncio
async def test_accepted_write_lost_response_reconciles_one_object(session_factory):
    effects, parent = await prepare(session_factory)
    objects = []
    writes = 0

    async def create():
        nonlocal writes
        writes += 1
        objects.append({"id": str(uuid4())})
        raise TimeoutError("response lost")

    async def read(object_id):
        return objects[0] if objects else None

    with pytest.raises(DraftEffectUncertain):
        await effects.execute(
            "root",
            provider="notion",
            operation="notion.private_product.write",
            create=create,
            reconcile=read,
            notion_parent_id=parent,
        )
    observed = await effects.execute(
        "root",
        provider="notion",
        operation="notion.private_product.write",
        create=create,
        reconcile=read,
        notion_parent_id=parent,
    )
    assert observed == objects[0] and writes == 1
    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(Receipt)) == 1
        assert await s.scalar(select(func.count()).select_from(IdempotencyRecord)) == 1


@pytest.mark.asyncio
async def test_pending_absence_does_not_repost(session_factory):
    effects, parent = await prepare(session_factory)
    writes = 0

    async def create():
        nonlocal writes
        writes += 1
        raise TimeoutError()

    async def read(object_id):
        return None

    for _ in range(2):
        with pytest.raises(DraftEffectUncertain):
            await effects.execute(
                "root",
                provider="notion",
                operation="notion.private_product.write",
                create=create,
                reconcile=read,
                notion_parent_id=parent,
            )
    assert writes == 1


@pytest.mark.asyncio
async def test_repeat_rechecks_provider_and_keeps_one_receipt(session_factory):
    effects, parent = await prepare(session_factory)
    objects = []
    writes = 0
    reads = 0

    async def create():
        nonlocal writes
        writes += 1
        obj = {"id": str(uuid4())}
        objects.append(obj)
        return obj

    async def read(object_id):
        nonlocal reads
        reads += 1
        return objects[0] if objects else None

    for _ in range(2):
        await effects.execute(
            "root",
            provider="notion",
            operation="notion.private_product.write",
            create=create,
            reconcile=read,
            notion_parent_id=parent,
        )
    assert writes == 1 and reads == 3
    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(Receipt)) == 1


@pytest.mark.asyncio
async def test_publication_refused_before_callbacks(session_factory):
    effects, parent = await prepare(session_factory)

    async def impossible(*args):
        raise AssertionError("provider callback must not run")

    with pytest.raises(DraftRunRefused):
        await effects.execute(
            "publish",
            provider="etsy",
            operation="etsy.publish",
            create=impossible,
            reconcile=impossible,
            notion_parent_id=parent,
        )


@pytest.mark.asyncio
async def test_wrong_lease_refused_before_callbacks(session_factory):
    effects, parent = await prepare(session_factory)
    effects.lease_owner = "different-owner"

    async def impossible(*args):
        raise AssertionError("provider callback must not run")

    with pytest.raises(DraftRunRefused, match="lease"):
        await effects.execute(
            "root",
            provider="notion",
            operation="notion.private_product.write",
            create=impossible,
            reconcile=impossible,
            notion_parent_id=parent,
        )


@pytest.mark.asyncio
async def test_foreign_shop_workflow_refused_before_callbacks(session_factory):
    effects, parent = await prepare(session_factory)
    async with session_factory() as s, s.begin():
        shop = await s.scalar(select(Shop))
        shop.name = "UnrelatedShop"

    async def impossible(*args):
        raise AssertionError("provider callback must not run")

    with pytest.raises(DraftRunRefused, match="shop"):
        await effects.execute(
            "root",
            provider="notion",
            operation="notion.private_product.write",
            create=impossible,
            reconcile=impossible,
            notion_parent_id=parent,
        )


@pytest.mark.asyncio
async def test_concurrent_calls_cannot_duplicate_provider_create(session_factory):
    effects, parent = await prepare(session_factory)
    objects = []
    writes = 0

    async def create():
        nonlocal writes
        writes += 1
        await asyncio.sleep(0.05)
        obj = {"id": str(uuid4())}
        objects.append(obj)
        return obj

    async def read(object_id):
        return objects[0] if objects else None

    results = await asyncio.gather(
        *[
            effects.execute(
                "root",
                provider="notion",
                operation="notion.private_product.write",
                create=create,
                reconcile=read,
                notion_parent_id=parent,
            )
            for _ in range(2)
        ],
        return_exceptions=True,
    )
    assert writes == 1
    assert any(isinstance(r, dict) for r in results)
    assert all(isinstance(r, (dict, DraftEffectUncertain)) for r in results)
    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(Receipt)) == 1


@pytest.mark.asyncio
async def test_read_failure_before_first_mutation_does_not_poison_reservation(session_factory):
    effects, parent = await prepare(session_factory)
    writes = 0
    objects = []
    fail = True

    async def create():
        nonlocal writes
        writes += 1
        obj = {"id": str(uuid4())}
        objects.append(obj)
        return obj

    async def read(object_id):
        if fail:
            raise ConnectionError("read unavailable before create")
        return objects[0] if objects else None

    with pytest.raises(DraftEffectUncertain):
        await effects.execute(
            "root",
            provider="notion",
            operation="notion.private_product.write",
            create=create,
            reconcile=read,
            notion_parent_id=parent,
        )
    assert writes == 0
    fail = False
    assert (
        await effects.execute(
            "root",
            provider="notion",
            operation="notion.private_product.write",
            create=create,
            reconcile=read,
            notion_parent_id=parent,
        )
    )["id"] == objects[0]["id"]
    assert writes == 1


@pytest.mark.asyncio
async def test_explicit_provider_refusal_does_not_become_unknown_effect(session_factory):
    effects, parent = await prepare(session_factory)
    objects = []
    reject = True

    async def create():
        if reject:
            raise DraftRunRefused("notion_provider_refused_400")
        obj = {"id": str(uuid4())}
        objects.append(obj)
        return obj

    async def read(object_id):
        return objects[0] if objects else None

    with pytest.raises(DraftRunRefused, match="400"):
        await effects.execute(
            "root",
            provider="notion",
            operation="notion.private_product.write",
            create=create,
            reconcile=read,
            notion_parent_id=parent,
        )
    reject = False
    await effects.execute(
        "root",
        provider="notion",
        operation="notion.private_product.write",
        create=create,
        reconcile=read,
        notion_parent_id=parent,
    )
    assert len(objects) == 1


@pytest.mark.asyncio
async def test_job_cancelled_during_reconcile_never_creates_provider_object(session_factory):
    effects, parent = await prepare(session_factory)
    writes = 0

    async def read(object_id):
        async with session_factory() as s, s.begin():
            job = await s.get(Job, effects.job_id)
            job.status = "CANCELLED"
        return None

    async def create():
        nonlocal writes
        writes += 1
        return {"id": str(uuid4())}

    with pytest.raises(DraftRunRefused):
        await effects.execute(
            "root",
            provider="notion",
            operation="notion.private_product.write",
            create=create,
            reconcile=read,
            notion_parent_id=parent,
        )
    assert writes == 0


@pytest.mark.asyncio
async def test_concurrent_absent_retries_claim_one_provider_write(session_factory):
    effects, parent = await prepare(session_factory)
    objects = []
    writes = 0
    reject = True

    async def create():
        nonlocal writes
        if reject:
            raise DraftRunRefused("notion_provider_refused_400")
        writes += 1
        await asyncio.sleep(0.05)
        obj = {"id": str(uuid4())}
        objects.append(obj)
        return obj

    async def read(object_id):
        return objects[0] if objects else None

    with pytest.raises(DraftRunRefused):
        await effects.execute(
            "root",
            provider="notion",
            operation="notion.private_product.write",
            create=create,
            reconcile=read,
            notion_parent_id=parent,
        )
    reject = False
    results = await asyncio.gather(
        *[
            effects.execute(
                "root",
                provider="notion",
                operation="notion.private_product.write",
                create=create,
                reconcile=read,
                notion_parent_id=parent,
            )
            for _ in range(2)
        ],
        return_exceptions=True,
    )
    assert writes == 1
    assert any(isinstance(r, dict) for r in results)
    assert all(isinstance(r, (dict, DraftEffectUncertain)) for r in results)
    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(Receipt)) == 1


@pytest.mark.asyncio
async def test_adapter_guard_requires_active_reserved_callback(session_factory):
    effects, _ = await prepare(session_factory)
    with pytest.raises(DraftRunRefused, match="active_effect_reservation_required"):
        await effects.assert_lease()


@pytest.mark.asyncio
async def test_provider_callback_observes_committed_active_reservation(session_factory):
    effects, parent = await prepare(session_factory)
    objects = []

    async def create():
        await effects.assert_lease()
        obj = {"id": str(uuid4())}
        objects.append(obj)
        return obj

    async def read(object_id):
        return objects[0] if objects else None

    result = await effects.execute(
        "root",
        provider="notion",
        operation="notion.private_product.write",
        create=create,
        reconcile=read,
        notion_parent_id=parent,
    )
    assert result == objects[0]
    with pytest.raises(DraftRunRefused, match="active_effect_reservation_required"):
        await effects.assert_lease()


@pytest.mark.asyncio
@pytest.mark.parametrize("refusal", ["notion_read_failed", "database_schema_readback_mismatch"])
async def test_accepted_create_followed_by_refused_read_retains_id_and_never_reposts(
    session_factory, refusal
):
    from money_machine.persistence.tables import EffectAttempt

    effects, parent = await prepare(session_factory)
    objects = []
    writes = 0
    phase = "first"

    async def create():
        nonlocal writes
        writes += 1
        obj = {"id": str(uuid4())}
        objects.append(obj)
        return obj

    async def read(object_id):
        if phase == "first":
            if objects:
                raise DraftRunRefused(refusal)
            return None
        if phase == "invisible":
            return None
        assert object_id == objects[0]["id"]
        return objects[0]

    async def execute():
        return await effects.execute(
            "post-read",
            provider="notion",
            operation="notion.private_product.write",
            create=create,
            reconcile=read,
            notion_parent_id=parent,
        )

    with pytest.raises(DraftRunRefused, match=refusal):
        await execute()
    async with session_factory() as session:
        latest = await session.scalar(
            select(EffectAttempt)
            .order_by(EffectAttempt.reconciliation_attempt.desc(), EffectAttempt.recorded_at.desc())
            .limit(1)
        )
        assert latest is not None and latest.effect_state == "UNKNOWN"
        assert latest.provider_object_id == objects[0]["id"]
    phase = "invisible"
    with pytest.raises(DraftEffectUncertain):
        await execute()
    assert writes == 1
    phase = "readable"
    assert await execute() == objects[0]
    assert writes == 1
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Receipt)) == 1


@pytest.mark.asyncio
async def test_concurrent_replay_confirmation_is_never_regressed_by_delayed_create_response(
    session_factory,
):
    from money_machine.persistence.tables import EffectAttempt

    effects, parent = await prepare(session_factory)
    accepted, response = asyncio.Event(), asyncio.Event()
    objects = []
    writes = 0
    fail_reads = False

    async def create():
        nonlocal writes
        writes += 1
        obj = {"id": str(uuid4())}
        objects.append(obj)
        accepted.set()
        await response.wait()
        return obj

    async def read(object_id):
        if fail_reads:
            raise DraftRunRefused("temporary_read_failure")
        return objects[0] if objects else None

    async def execute():
        return await effects.execute(
            "delayed-response",
            provider="notion",
            operation="notion.private_product.write",
            create=create,
            reconcile=read,
            notion_parent_id=parent,
        )

    first = asyncio.create_task(execute())
    try:
        await asyncio.wait_for(accepted.wait(), timeout=5)
        assert await execute() == objects[0]
        fail_reads = True
        response.set()
        with pytest.raises(DraftRunRefused, match="temporary_read_failure"):
            await first
    finally:
        response.set()
        if not first.done():
            first.cancel()
            await asyncio.gather(first, return_exceptions=True)
    async with session_factory() as session:
        latest = await session.scalar(
            select(EffectAttempt).order_by(EffectAttempt.reconciliation_attempt.desc()).limit(1)
        )
        assert latest is not None and latest.effect_state == "CONFIRMED"
        assert latest.provider_object_id == objects[0]["id"] and writes == 1
        record = await session.scalar(select(IdempotencyRecord))
        assert record is not None and record.completed_at is not None
        assert await session.scalar(select(func.count()).select_from(Receipt)) == 1
