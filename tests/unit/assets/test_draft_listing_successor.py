"""A passed asset chain creates one ready DraftListingJob and does not run it."""

from __future__ import annotations

import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from money_machine.agents.contracts.merchandising import IMAGE_ROLES
from money_machine.assets.draft_listing_successor import create_ready_draft_listing_job
from money_machine.assets.etsy_draft import DraftEvidence, DraftGateError
from money_machine.domain.events import EventName
from money_machine.integrations.etsy.draft_client import (
    DraftLedger,
    DraftReceipt,
    EtsyDraftClient,
)
from money_machine.orchestration.successor_factory import load_event_successor_map
from money_machine.persistence.repositories.events import EventAppendError
from money_machine.persistence.tables import Job
from money_machine.persistence.unit_of_work import UnitOfWork
from tests.unit.assets.test_etsy_draft_ready import chain_assets, chain_evidence
from tests.unit.integrations.test_etsy_draft_client import Store

_WORKFLOW = UUID("00000000-0000-4000-8000-0000000000d1")
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

    async def by_dedupe_key(self, dedupe_key: str) -> object | None:
        if dedupe_key not in self._keys:
            return None
        return object()


class _Session:
    def __init__(self) -> None:
        self.jobs: list[Job] = []
        self._by_id: dict[UUID, Job] = {}

    def add(self, instance: object) -> None:
        if isinstance(instance, Job):
            self.jobs.append(instance)
            self._by_id[instance.id] = instance

    async def flush(self) -> None:
        return None

    async def get(self, _entity: object, ident: UUID) -> Job | None:
        return self._by_id.get(ident)


class _Uow:
    def __init__(self) -> None:
        self.events = _Events()
        self.session = _Session()


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
) -> DraftReceipt:
    return await create_ready_draft_listing_job(
        evidence,
        client,
        cast(UnitOfWork, uow),
        workflow_id=_WORKFLOW,
        occurred_at=_NOW,
    )


def test_assets_completed_still_names_only_draft_listing_job() -> None:
    successor_map = load_event_successor_map()
    assert successor_map["ASSETS_COMPLETED"] == ["DraftListingJob"]
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

    monkeypatch.setattr(
        "money_machine.orchestration.leases.claim_ready_job",
        _executed,
    )
    monkeypatch.setattr(
        "money_machine.orchestration.worker._execute_job_with_runner",
        _executed,
    )
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
