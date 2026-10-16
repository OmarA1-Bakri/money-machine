"""Create the ready DraftListingJob after the asset chain passes.

Prompt sections 9 and 10 say ``ASSET_QA_PASSED`` then ``CREATE_ETSY_DRAFT``
ready. Those are labels. The durable names are ``ASSETS_COMPLETED`` and
``DraftListingJob`` (D-0033). This module does not claim the job and does
not start the worker.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from money_machine.assets.etsy_draft import DraftEvidence, prepare_etsy_draft
from money_machine.domain.enums import JobStatus
from money_machine.domain.events import EventName
from money_machine.integrations.etsy.draft_client import DraftReceipt, EtsyDraftClient
from money_machine.orchestration.event_dispatcher import EventDispatcher
from money_machine.orchestration.transition_guard import require_job_transition
from money_machine.persistence.tables import Job
from money_machine.persistence.unit_of_work import UnitOfWork


async def create_ready_draft_listing_job(
    evidence: DraftEvidence,
    client: EtsyDraftClient,
    uow: UnitOfWork,
    *,
    workflow_id: UUID,
    occurred_at: datetime,
) -> DraftReceipt:
    """Return the ready draft and leave one unrun ``DraftListingJob``.

    A gate refusal raises ``DraftGateError`` before any event is written.
    One product has one draft job. Copy and pricing do not spawn another,
    and a second workflow does not either. A failure after dispatch rolls
    the event and the job back.
    """
    receipt = prepare_etsy_draft(evidence, client)
    try:
        dispatcher = EventDispatcher(uow)
        job_ids = await dispatcher.dispatch(
            event_name=EventName.ASSETS_COMPLETED,
            aggregate_type="products",
            aggregate_id=evidence.product_id,
            workflow_id=workflow_id,
            job_id=None,
            payload={
                "spec_version": evidence.spec_version,
                "listing_id": receipt.listing_id,
            },
            occurred_at=occurred_at,
        )
        for job_id in job_ids:
            job = await uow.session.get(Job, job_id)
            if not isinstance(job, Job):
                raise RuntimeError("draft successor missing")
            status = JobStatus(job.status)
            if status is JobStatus.READY:
                continue
            require_job_transition(status, JobStatus.READY)
            job.status = JobStatus.READY.value
            job.updated_at = occurred_at
        if job_ids:
            await uow.session.flush()
    except Exception:
        await uow.rollback()
        raise
    return receipt
