"""Shared-session rollback, one event, and the worker draft path."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

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


async def test_a_later_workflow_keeps_the_callers_session(tmp_path: Path) -> None:
    for status in ("RUNNING", "SUCCEEDED"):
        ledger = tmp_path / status
        ledger.mkdir()
        shop = Store()
        client = EtsyDraftClient(shop, DraftLedger(ledger))
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
