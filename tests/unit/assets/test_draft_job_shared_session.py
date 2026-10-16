"""Shared-session rollback, one event, and the worker draft path."""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

import money_machine.assets.draft_listing_successor as successor
from money_machine.domain.errors import InvalidTransitionError
from money_machine.domain.events import EventName
from money_machine.integrations.etsy.draft_client import DraftLedger, EtsyDraftClient
from money_machine.orchestration.event_dispatcher import EventDispatcher
from money_machine.orchestration.successor_factory import SuccessorFactory
from money_machine.persistence.tables import Job
from money_machine.persistence.unit_of_work import UnitOfWork
from tests.unit.assets.test_draft_listing_successor import (
    OPENED_AT,
    OTHER_WORKFLOW,
    WORKFLOW,
    SharedUow,
    draft_jobs,
    open_ready_draft,
)
from tests.unit.assets.test_etsy_draft_ready import chain_evidence
from tests.unit.integrations.test_etsy_draft_client import Store

_ASSET_JOB = UUID("00000000-0000-4000-8000-0000000000a1")
_OTHER_ASSET_JOB = UUID("00000000-0000-4000-8000-0000000000a2")
_SENTINEL = UUID("00000000-0000-4000-8000-0000000000ee")


@pytest.fixture(autouse=True)
def _block_sockets(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("socket")

    def _connect(_self: socket.socket, address: object) -> None:
        _blocked(address)

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _connect)


def _caller_row(source: Job) -> Job:
    return Job(
        id=_SENTINEL,
        workflow_id=source.workflow_id,
        job_type="CallerSentinel",
        object_type=source.object_type,
        object_id=source.object_id,
        owner_agent_id=source.owner_agent_id,
        status="PENDING",
        input={},
        success_contract={},
        scheduled_at=OPENED_AT,
        attempt=0,
        max_attempts=3,
        idempotency_key="caller-sentinel",
        side_effect_class=source.side_effect_class,
        retry_class=source.retry_class,
        allowed_mode=source.allowed_mode,
        version=1,
    )


async def _later_status_keeps_the_session(tmp_path: Path, status: str) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = SharedUow()
    evidence = chain_evidence()
    await open_ready_draft(evidence, client, uow)
    draft = draft_jobs(uow)[0]
    draft.status = status
    uow.session.add(_caller_row(draft))
    await uow.events.append(
        event_name=EventName.SHOP_BOOTSTRAPPED,
        aggregate_type="shops",
        aggregate_id=evidence.product_id,
        workflow_id=WORKFLOW,
        job_id=None,
        dedupe_key=f"caller:{status}",
        occurred_at=OPENED_AT,
    )
    with pytest.raises(InvalidTransitionError, match=f"{status} -> READY"):
        await open_ready_draft(evidence, client, uow, workflow_id=OTHER_WORKFLOW)
    assert [job.status for job in draft_jobs(uow)] == [status]
    assert uow.events.names.count("ASSETS_COMPLETED") == 1
    assert "SHOP_BOOTSTRAPPED" in uow.events.names
    assert any(job.job_type == "CallerSentinel" for job in uow.session.jobs)


async def test_a_later_running_job_keeps_the_callers_session(tmp_path: Path) -> None:
    await _later_status_keeps_the_session(tmp_path, "RUNNING")


async def test_a_later_succeeded_job_keeps_the_callers_session(tmp_path: Path) -> None:
    await _later_status_keeps_the_session(tmp_path, "SUCCEEDED")


async def test_another_workflow_does_not_record_a_second_event(tmp_path: Path) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = SharedUow()
    evidence = chain_evidence()
    await open_ready_draft(evidence, client, uow)
    await open_ready_draft(evidence, client, uow, workflow_id=OTHER_WORKFLOW)
    assert uow.events.names == ["ASSETS_COMPLETED"]
    assert len(draft_jobs(uow)) == 1
    assert draft_jobs(uow)[0].status == "READY"


async def test_worker_assets_completed_does_not_add_a_pending_draft(
    tmp_path: Path,
) -> None:
    uow = SharedUow()
    uow.session.add(_asset_job(_ASSET_JOB))
    await EventDispatcher(cast(UnitOfWork, uow)).dispatch(
        event_name=EventName.ASSETS_COMPLETED,
        aggregate_type="Job",
        aggregate_id=_ASSET_JOB,
        workflow_id=WORKFLOW,
        job_id=_ASSET_JOB,
        payload={},
        occurred_at=OPENED_AT,
    )
    assert draft_jobs(uow) == []
    assert uow.events.names == ["ASSETS_COMPLETED"]
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    await open_ready_draft(chain_evidence(), client, uow)
    await EventDispatcher(cast(UnitOfWork, uow)).dispatch(
        event_name=EventName.ASSETS_COMPLETED,
        aggregate_type="Job",
        aggregate_id=_ASSET_JOB,
        workflow_id=OTHER_WORKFLOW,
        job_id=_ASSET_JOB,
        payload={},
        occurred_at=OPENED_AT,
    )
    assert [job.status for job in draft_jobs(uow)] == ["READY"]


async def test_a_missing_product_id_is_refused() -> None:
    uow = SharedUow()
    with pytest.raises(ValueError, match="product aggregate"):
        await SuccessorFactory(cast(UnitOfWork, uow)).create_successors(
            event_name=EventName.ASSETS_COMPLETED,
            workflow_id=WORKFLOW,
            parent_job_id=None,
            aggregate_id=None,
            occurred_at=OPENED_AT,
        )
    assert draft_jobs(uow) == []


async def test_the_idempotency_key_is_the_product(tmp_path: Path) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = SharedUow()
    evidence = chain_evidence()
    await open_ready_draft(evidence, client, uow)
    assert draft_jobs(uow)[0].idempotency_key == f"DraftListingJob:{evidence.product_id}"


def _asset_job(job_id: UUID) -> Job:
    return Job(
        id=job_id,
        workflow_id=WORKFLOW,
        job_type="AssetFactoryJob",
        object_type="listing_versions",
        object_id=job_id,
        owner_agent_id="A13",
        status="SUCCEEDED",
        input={},
        success_contract={},
        scheduled_at=OPENED_AT,
        attempt=0,
        max_attempts=3,
        idempotency_key=f"asset:{job_id}",
        side_effect_class="EXTERNAL_WRITE",
        retry_class="RECONCILE_FIRST",
        allowed_mode="simulation",
        version=1,
    )


async def _worker_assets(uow: SharedUow, workflow_id: UUID, job_id: UUID) -> None:
    if await uow.session.get(Job, job_id) is None:
        uow.session.add(_asset_job(job_id))
    await EventDispatcher(cast(UnitOfWork, uow)).dispatch(
        event_name=EventName.ASSETS_COMPLETED,
        aggregate_type="Job",
        aggregate_id=job_id,
        workflow_id=workflow_id,
        job_id=job_id,
        payload={},
        occurred_at=OPENED_AT,
    )


async def test_an_existing_pending_job_becomes_ready(tmp_path: Path) -> None:
    evidence = chain_evidence()
    uow = SharedUow()
    await EventDispatcher(cast(UnitOfWork, uow)).dispatch(
        event_name=EventName.ASSETS_COMPLETED,
        aggregate_type="products",
        aggregate_id=evidence.product_id,
        workflow_id=WORKFLOW,
        job_id=None,
        payload={},
        occurred_at=OPENED_AT,
    )
    assert [job.status for job in draft_jobs(uow)] == ["PENDING"]
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    receipt = await open_ready_draft(evidence, client, uow)
    drafts = draft_jobs(uow)
    assert receipt.ready is True
    assert len(drafts) == 1
    assert drafts[0].status == "READY"
    assert drafts[0].attempt == 0
    assert drafts[0].updated_at == OPENED_AT
    assert uow.events.names == ["ASSETS_COMPLETED"]
    assert uow.session.flush_statuses[-1] == ("READY",)
    assert shop.posts == 1


async def test_cancellation_rolls_the_savepoint_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = SharedUow()
    evidence = chain_evidence()
    await open_ready_draft(evidence, client, uow)
    draft = draft_jobs(uow)[0]
    draft.status = "RUNNING"
    uow.session.add(_caller_row(draft))
    await uow.events.append(
        event_name=EventName.SHOP_BOOTSTRAPPED,
        aggregate_type="shops",
        aggregate_id=evidence.product_id,
        workflow_id=WORKFLOW,
        job_id=None,
        dedupe_key="caller:cancel",
        occurred_at=OPENED_AT,
    )

    def _cancel(_source: object, _target: object) -> None:
        raise asyncio.CancelledError()

    monkeypatch.setattr(successor, "require_job_transition", _cancel)
    with pytest.raises(asyncio.CancelledError):
        await open_ready_draft(evidence, client, uow, workflow_id=OTHER_WORKFLOW)
    assert [job.status for job in draft_jobs(uow)] == ["RUNNING"]
    assert uow.events.names.count("ASSETS_COMPLETED") == 1
    assert "SHOP_BOOTSTRAPPED" in uow.events.names
    assert any(job.job_type == "CallerSentinel" for job in uow.session.jobs)


async def test_the_savepoint_commit_keeps_the_draft(tmp_path: Path) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = SharedUow()
    await open_ready_draft(chain_evidence(), client, uow)
    await uow.session.boundaries[-1].rollback()
    assert [job.status for job in draft_jobs(uow)] == ["READY"]
    assert uow.events.names == ["ASSETS_COMPLETED"]


async def test_a_second_workflow_does_not_record_another_worker_event() -> None:
    uow = SharedUow()
    await _worker_assets(uow, WORKFLOW, _ASSET_JOB)
    await _worker_assets(uow, OTHER_WORKFLOW, _ASSET_JOB)
    assert uow.events.names == ["ASSETS_COMPLETED"]
    assert draft_jobs(uow) == []


async def test_a_different_worker_job_records_its_own_event() -> None:
    uow = SharedUow()
    await _worker_assets(uow, WORKFLOW, _ASSET_JOB)
    await _worker_assets(uow, WORKFLOW, _OTHER_ASSET_JOB)
    assert uow.events.names == ["ASSETS_COMPLETED", "ASSETS_COMPLETED"]
    assert draft_jobs(uow) == []


def _pending_draft(product_id: UUID) -> Job:
    job_id = SuccessorFactory.derive_product_job_id(product_id, "DraftListingJob")
    return Job(
        id=job_id,
        workflow_id=WORKFLOW,
        job_type="DraftListingJob",
        object_type="listing_versions",
        object_id=product_id,
        owner_agent_id="A13",
        status="PENDING",
        input={},
        success_contract={},
        scheduled_at=OPENED_AT,
        attempt=0,
        max_attempts=3,
        idempotency_key=f"DraftListingJob:{product_id}",
        side_effect_class="EXTERNAL_WRITE",
        retry_class="RECONCILE_FIRST",
        allowed_mode="simulation",
        version=1,
    )


async def test_a_legacy_product_key_beside_a_pending_job_stays_one_event(
    tmp_path: Path,
) -> None:
    evidence = chain_evidence()
    uow = SharedUow()
    legacy_key = f"ASSETS_COMPLETED:{evidence.product_id}:{WORKFLOW}:null"
    product_key = f"ASSETS_COMPLETED:{evidence.product_id}:product"
    await uow.events.append(
        event_name=EventName.ASSETS_COMPLETED,
        aggregate_type="products",
        aggregate_id=evidence.product_id,
        workflow_id=WORKFLOW,
        job_id=None,
        dedupe_key=legacy_key,
        occurred_at=OPENED_AT,
    )
    uow.session.add(_pending_draft(evidence.product_id))
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    receipt = await open_ready_draft(evidence, client, uow)
    assert receipt.ready is True
    assert uow.events.names == ["ASSETS_COMPLETED"]
    assert await uow.events.by_dedupe_key(legacy_key) is not None
    assert await uow.events.by_dedupe_key(product_key) is None
    assert len(draft_jobs(uow)) == 1
    assert draft_jobs(uow)[0].status == "READY"
    assert draft_jobs(uow)[0].updated_at == OPENED_AT
    assert shop.posts == 1


async def test_a_pending_job_beside_another_workflows_event_records_one(
    tmp_path: Path,
) -> None:
    evidence = chain_evidence()
    uow = SharedUow()
    await EventDispatcher(cast(UnitOfWork, uow)).dispatch(
        event_name=EventName.ASSETS_COMPLETED,
        aggregate_type="products",
        aggregate_id=evidence.product_id,
        workflow_id=OTHER_WORKFLOW,
        job_id=None,
        payload={},
        occurred_at=OPENED_AT,
    )
    assert [job.status for job in draft_jobs(uow)] == ["PENDING"]
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    receipt = await open_ready_draft(evidence, client, uow)
    assert receipt.ready is True
    assert [job.status for job in draft_jobs(uow)] == ["READY"]
    assert len(draft_jobs(uow)) == 1
    assert uow.events.names == ["ASSETS_COMPLETED"]


async def test_a_worker_assets_event_without_a_job_row_is_refused() -> None:
    uow = SharedUow()
    with pytest.raises(ValueError, match="requires a job"):
        await EventDispatcher(cast(UnitOfWork, uow)).dispatch(
            event_name=EventName.ASSETS_COMPLETED,
            aggregate_type="Job",
            aggregate_id=_ASSET_JOB,
            workflow_id=WORKFLOW,
            job_id=_ASSET_JOB,
            payload={},
            occurred_at=OPENED_AT,
        )
    assert uow.events.names == []
    assert draft_jobs(uow) == []


async def test_a_worker_assets_event_without_a_job_id_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uow = SharedUow()
    original = uow.session.get

    async def _get(_entity: object, ident: UUID | None) -> Job | None:
        if ident is None:
            raise AssertionError("null job id")
        return await original(_entity, ident)

    monkeypatch.setattr(uow.session, "get", _get)
    with pytest.raises(ValueError, match="requires a job"):
        await EventDispatcher(cast(UnitOfWork, uow)).dispatch(
            event_name=EventName.ASSETS_COMPLETED,
            aggregate_type="Job",
            aggregate_id=_ASSET_JOB,
            workflow_id=WORKFLOW,
            job_id=None,
            payload={},
            occurred_at=OPENED_AT,
        )
    assert uow.events.names == []
    assert draft_jobs(uow) == []


async def test_two_job_ids_on_one_worker_aggregate_record_two_events() -> None:
    uow = SharedUow()
    uow.session.add(_asset_job(_ASSET_JOB))
    uow.session.add(_asset_job(_OTHER_ASSET_JOB))
    dispatcher = EventDispatcher(cast(UnitOfWork, uow))
    await dispatcher.dispatch(
        event_name=EventName.ASSETS_COMPLETED,
        aggregate_type="Job",
        aggregate_id=_ASSET_JOB,
        workflow_id=WORKFLOW,
        job_id=_ASSET_JOB,
        payload={},
        occurred_at=OPENED_AT,
    )
    await dispatcher.dispatch(
        event_name=EventName.ASSETS_COMPLETED,
        aggregate_type="Job",
        aggregate_id=_ASSET_JOB,
        workflow_id=OTHER_WORKFLOW,
        job_id=_OTHER_ASSET_JOB,
        payload={},
        occurred_at=OPENED_AT,
    )
    assert uow.events.names == ["ASSETS_COMPLETED", "ASSETS_COMPLETED"]
    assert draft_jobs(uow) == []
