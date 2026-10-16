"""A passed asset chain creates one ready DraftListingJob and does not run it."""

from __future__ import annotations

import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

import money_machine.assets.draft_listing_successor as successor
import money_machine.orchestration.worker as worker
from money_machine.agents.contracts.merchandising import IMAGE_ROLES
from money_machine.assets.draft_listing_successor import create_ready_draft_listing_job
from money_machine.assets.etsy_draft import DraftEvidence, DraftGateError
from money_machine.domain.errors import InvalidTransitionError
from money_machine.domain.events import EventName
from money_machine.integrations.etsy.draft_client import (
    DraftLedger,
    DraftReceipt,
    EtsyDraftClient,
)
from money_machine.orchestration.event_dispatcher import EventDispatcher
from money_machine.orchestration.successor_factory import load_workflows_config
from money_machine.persistence.repositories.events import EventAppendError
from money_machine.persistence.tables import Job
from money_machine.persistence.unit_of_work import UnitOfWork
from tests.unit.assets.test_etsy_draft_ready import chain_assets, chain_evidence
from tests.unit.integrations.test_etsy_draft_client import Store

_WORKFLOW = UUID("00000000-0000-4000-8000-0000000000d1")
_OTHER_WORKFLOW = UUID("00000000-0000-4000-8000-0000000000d2")
_COPY_JOB = UUID("00000000-0000-4000-8000-0000000000c1")
_PRICE_JOB = UUID("00000000-0000-4000-8000-0000000000c2")
_NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


class _Events:
    def __init__(self) -> None:
        self.names: list[str] = []
        self._keys: set[str] = set()

    async def append(
        self,
        *,
        event_name: EventName,
        aggregate_type: str,
        aggregate_id: UUID,
        workflow_id: UUID | None,
        job_id: UUID | None,
        payload: dict[str, object] | None = None,
        dedupe_key: str,
        occurred_at: datetime,
    ) -> None:
        del aggregate_type, aggregate_id, workflow_id, job_id, payload, occurred_at
        if dedupe_key in self._keys:
            raise EventAppendError(dedupe_key)
        self._keys.add(dedupe_key)
        self.names.append(event_name.value)

    def clear(self) -> None:
        self.names.clear()
        self._keys.clear()

    def snapshot(self) -> tuple[tuple[str, ...], frozenset[str]]:
        return tuple(self.names), frozenset(self._keys)

    def restore(self, names: tuple[str, ...], keys: frozenset[str]) -> None:
        self.names[:] = names
        self._keys.clear()
        self._keys.update(keys)

    async def by_dedupe_key(self, dedupe_key: str) -> object | None:
        if dedupe_key not in self._keys:
            return None
        return object()


class _Session:
    def __init__(self) -> None:
        self.jobs: list[Job] = []
        self._by_id: dict[UUID, Job] = {}
        self.flush_statuses: list[tuple[str, ...]] = []
        self.events: _Events | None = None

    def add(self, instance: object) -> None:
        if isinstance(instance, Job):
            self.jobs.append(instance)
            self._by_id[instance.id] = instance

    async def flush(self) -> None:
        self.flush_statuses.append(tuple(job.status for job in self.jobs))

    def clear(self) -> None:
        self.jobs.clear()
        self._by_id.clear()

    async def get(self, _entity: object, ident: UUID) -> Job | None:
        return self._by_id.get(ident)

    def begin_nested(self) -> _Boundary:
        return _Boundary(self)

    def snapshot(
        self,
    ) -> tuple[
        list[Job],
        dict[UUID, Job],
        dict[UUID, tuple[str, datetime]],
        list[tuple[str, ...]],
    ]:
        fields = {job.id: (job.status, job.updated_at) for job in self.jobs}
        return list(self.jobs), dict(self._by_id), fields, list(self.flush_statuses)

    def restore(
        self,
        jobs: list[Job],
        by_id: dict[UUID, Job],
        fields: dict[UUID, tuple[str, datetime]],
        flushes: list[tuple[str, ...]],
    ) -> None:
        self.jobs[:] = jobs
        self._by_id.clear()
        self._by_id.update(by_id)
        for job in jobs:
            status, updated_at = fields[job.id]
            job.status = status
            job.updated_at = updated_at
        self.flush_statuses[:] = flushes


class _Boundary:
    """Savepoint. Rollback restores this session and does not clear an outer row."""

    def __init__(self, session: _Session) -> None:
        self._session = session
        self._events: tuple[tuple[str, ...], frozenset[str]] | None = None
        self._rows: (
            tuple[
                list[Job],
                dict[UUID, Job],
                dict[UUID, tuple[str, datetime]],
                list[tuple[str, ...]],
            ]
            | None
        ) = None

    async def start(self) -> _Boundary:
        events = self._session.events
        if events is None:
            raise RuntimeError("session has no events")
        self._events = events.snapshot()
        self._rows = self._session.snapshot()
        return self

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        events = self._session.events
        if events is None or self._events is None or self._rows is None:
            raise RuntimeError("nested transaction has not started")
        names, keys = self._events
        events.restore(names, keys)
        jobs, by_id, fields, flushes = self._rows
        self._session.restore(jobs, by_id, fields, flushes)


class _MissingJob(_Session):
    async def get(self, _entity: object, ident: UUID) -> Job | None:
        assert isinstance(ident, UUID)
        return None


class _CancelledJob(_Session):
    async def get(self, _entity: object, ident: UUID) -> Job | None:
        job = self._by_id.get(ident)
        if job is not None:
            job.status = "CANCELLED"
        return job


class _Uow:
    def __init__(self, session: _Session | None = None) -> None:
        self.events = _Events()
        self.session = session if session is not None else _Session()
        self.session.events = self.events

    async def rollback(self) -> None:
        self.events.clear()
        self.session.clear()


@pytest.fixture(autouse=True)
def _block_sockets(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("socket")

    def _connect(_self: socket.socket, address: object) -> None:
        _blocked(address)

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _connect)


async def _open(
    evidence: DraftEvidence,
    client: EtsyDraftClient,
    uow: _Uow,
    *,
    workflow_id: UUID = _WORKFLOW,
) -> DraftReceipt:
    return await create_ready_draft_listing_job(
        evidence,
        client,
        cast(UnitOfWork, uow),
        workflow_id=workflow_id,
        occurred_at=_NOW,
    )


def _drafts(uow: _Uow) -> list[Job]:
    return [job for job in uow.session.jobs if job.job_type == "DraftListingJob"]


WORKFLOW = _WORKFLOW
OTHER_WORKFLOW = _OTHER_WORKFLOW
OPENED_AT = _NOW
SharedUow = _Uow
open_ready_draft = _open
draft_jobs = _drafts


async def _dispatch(
    uow: _Uow,
    event_name: EventName,
    product_id: UUID,
    *,
    job_id: UUID,
    aggregate_type: str = "products",
    aggregate_id: UUID | None = None,
) -> None:
    await EventDispatcher(cast(UnitOfWork, uow)).dispatch(
        event_name=event_name,
        aggregate_type=aggregate_type,
        aggregate_id=product_id if aggregate_id is None else aggregate_id,
        workflow_id=_WORKFLOW,
        job_id=job_id,
        payload={},
        occurred_at=_NOW,
    )


def test_assets_completed_still_names_only_draft_listing_job() -> None:
    successor_map, config = load_workflows_config()
    assert successor_map["ASSETS_COMPLETED"] == ["DraftListingJob"]
    assert successor_map["LISTING_COPY_COMPLETED"] == ["PricingJob"]
    assert successor_map["PRICING_COMPLETED"] == []
    workflow = next(
        item for item in config.workflows if item.workflow_type == "ProductLifecycleWorkflow"
    )
    jobs = {job.job_type: tuple(job.successor_job_types) for job in workflow.jobs}
    assert jobs["ListingCopyJob"] == ("PricingJob",)
    assert jobs["PricingJob"] == ()
    assert jobs["AssetFactoryJob"] == ("DraftListingJob",)
    assert "ASSET_QA_PASSED" not in successor_map
    assert "CREATE_ETSY_DRAFT" not in successor_map


async def test_passed_chain_creates_exactly_one_draft_listing_job(tmp_path: Path) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = _Uow()
    receipt = await _open(chain_evidence(), client, uow)
    assert receipt.ready is True
    assert len(uow.session.jobs) == 1
    assert uow.session.jobs[0].job_type == "DraftListingJob"
    assert uow.session.jobs[0].owner_agent_id == "A13"
    assert uow.events.names == ["ASSETS_COMPLETED"]
    assert shop.posts == 1


@pytest.mark.parametrize(
    ("changes", "gate"),
    [
        ({"product_qa": "failed"}, "product_qa"),
        ({"claims_passed": False}, "claims"),
        ({"assets": chain_assets(shots=0)}, "screenshots"),
        ({"assets": chain_assets(images=len(IMAGE_ROLES) - 1)}, "listing_images"),
        ({"assets": chain_assets(images=len(IMAGE_ROLES) + 1)}, "listing_images"),
        ({"assets": chain_assets(videos=0)}, "video"),
        ({"assets": chain_assets(videos=2)}, "video"),
        ({"assets": chain_assets(pdfs=1), "pdf_roles": ("readme",)}, "delivery_pdfs"),
        ({"pdf_roles": ("free_gift", "free_gift")}, "delivery_pdfs"),
        ({"assets": chain_assets(pdfs=3)}, "delivery_pdfs"),
        ({"links_passed": False}, "links"),
        ({"assets": chain_assets(stale_image=True)}, "asset_qa"),
    ],
)
async def test_each_failing_gate_creates_no_successor(
    tmp_path: Path,
    changes: dict[str, object],
    gate: str,
) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = _Uow()
    with pytest.raises(DraftGateError) as caught:
        await _open(chain_evidence(**changes), client, uow)
    assert caught.value.gate == gate
    assert uow.session.jobs == []
    assert uow.events.names == []
    assert shop.calls == []


async def test_redispatch_does_not_duplicate_the_job(tmp_path: Path) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = _Uow()
    first = await _open(chain_evidence(), client, uow)
    second = await _open(chain_evidence(), client, uow)
    assert first.ready is True
    assert second.ready is True
    assert len(uow.session.jobs) == 1
    assert len(uow.events.names) == 1
    assert shop.posts == 1


async def test_draft_listing_job_is_ready_and_not_executed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []

    async def _executed(*_args: object, **_kwargs: object) -> None:
        called.append("executed")
        raise AssertionError("executed")

    monkeypatch.setattr(worker, "claim_ready_job", _executed)
    monkeypatch.setattr(worker, "_execute_job_with_runner", _executed)
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = _Uow()
    await _open(chain_evidence(), client, uow)
    job = uow.session.jobs[0]
    assert job.status == "READY"
    assert job.attempt == 0
    assert job.lease_owner is None
    assert job.lease_expires_at is None
    assert job.heartbeat_at is None
    assert "DRAFT_CREATED" not in uow.events.names
    assert called == []


async def test_copy_and_pricing_routes_do_not_add_a_second_draft_job(tmp_path: Path) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = _Uow()
    evidence = chain_evidence()
    await _dispatch(uow, EventName.LISTING_COPY_COMPLETED, evidence.product_id, job_id=_COPY_JOB)
    await _dispatch(uow, EventName.PRICING_COMPLETED, evidence.product_id, job_id=_PRICE_JOB)
    await _open(evidence, client, uow)
    drafts = _drafts(uow)
    assert len(drafts) == 1
    assert drafts[0].status == "READY"
    assert len([job for job in uow.session.jobs if job.job_type == "PricingJob"]) == 1
    assert shop.posts == 1


async def test_worker_shaped_copy_and_pricing_do_not_add_a_second_draft_job(
    tmp_path: Path,
) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = _Uow()
    evidence = chain_evidence()
    await _dispatch(
        uow,
        EventName.LISTING_COPY_COMPLETED,
        evidence.product_id,
        job_id=_COPY_JOB,
        aggregate_type="Job",
        aggregate_id=_COPY_JOB,
    )
    await _dispatch(
        uow,
        EventName.PRICING_COMPLETED,
        evidence.product_id,
        job_id=_PRICE_JOB,
        aggregate_type="Job",
        aggregate_id=_PRICE_JOB,
    )
    await _open(evidence, client, uow)
    drafts = _drafts(uow)
    assert len(drafts) == 1
    assert drafts[0].status == "READY"
    assert len([job for job in uow.session.jobs if job.job_type == "PricingJob"]) == 1
    assert shop.posts == 1


async def test_another_workflow_does_not_add_a_second_draft_job(tmp_path: Path) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = _Uow()
    evidence = chain_evidence()
    first = await _open(evidence, client, uow)
    second = await _open(evidence, client, uow, workflow_id=_OTHER_WORKFLOW)
    assert first.ready is True
    assert second.ready is True
    assert len(_drafts(uow)) == 1
    assert _drafts(uow)[0].status == "READY"
    assert shop.posts == 1


async def test_a_failure_after_dispatch_leaves_no_job_or_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(_source: object, _target: object) -> None:
        raise RuntimeError("after dispatch")

    monkeypatch.setattr(successor, "require_job_transition", _boom)
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = _Uow()
    with pytest.raises(RuntimeError, match="after dispatch"):
        await _open(chain_evidence(), client, uow)
    assert uow.session.jobs == []
    assert uow.events.names == []
    assert shop.posts == 1


async def test_the_ready_status_is_flushed(tmp_path: Path) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = _Uow()
    await _open(chain_evidence(), client, uow)
    assert uow.session.flush_statuses[-1] == ("READY",)


async def test_a_missing_successor_is_refused(tmp_path: Path) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = _Uow(_MissingJob())
    with pytest.raises(RuntimeError, match="draft successor missing"):
        await _open(chain_evidence(), client, uow)


async def test_an_illegal_transition_is_refused(tmp_path: Path) -> None:
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    uow = _Uow(_CancelledJob())
    with pytest.raises(InvalidTransitionError, match="CANCELLED -> READY"):
        await _open(chain_evidence(), client, uow)


async def test_an_existing_event_with_no_job_does_not_flush(tmp_path: Path) -> None:
    evidence = chain_evidence()
    uow = _Uow()
    await uow.events.append(
        event_name=EventName.ASSETS_COMPLETED,
        aggregate_type="products",
        aggregate_id=evidence.product_id,
        workflow_id=_WORKFLOW,
        job_id=None,
        dedupe_key=":".join(
            (
                EventName.ASSETS_COMPLETED.value,
                str(evidence.product_id),
                str(_WORKFLOW),
                "null",
            )
        ),
        occurred_at=_NOW,
    )
    uow.session.flush_statuses.clear()
    shop = Store()
    client = EtsyDraftClient(shop, DraftLedger(tmp_path))
    receipt = await _open(evidence, client, uow)
    assert receipt.ready is True
    assert uow.session.jobs == []
    assert uow.session.flush_statuses == []
