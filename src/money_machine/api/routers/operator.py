"""Read persisted run records without exposing provider payloads."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from money_machine.api.dependencies import SessionDependency
from money_machine.api.routers.operator_runs import ExecutionMode, select_operator_run
from money_machine.persistence.tables import (
    Decision,
    EtsyListing,
    Incident,
    IntegrationAccount,
    Job,
    ListingVersion,
    Product,
    WorkflowRun,
)

router = APIRouter(prefix="/operator", tags=["operator"])


class OperatorView(StrEnum):
    NOW = "now"
    PIPELINE = "pipeline"
    SHOP = "shop"
    BLOCKED = "blocked"
    DECISIONS = "decisions"
    INCIDENTS = "incidents"
    SETTINGS = "settings"


class OperatorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    state: str
    detail: str
    product_id: UUID | None
    listing_version_id: UUID | None


class OperatorEnvelope(BaseModel):
    run_id: str
    execution_mode: ExecutionMode
    view: OperatorView
    items: list[OperatorRecord]


def _reason(payload: dict[str, object]) -> str:
    value = payload.get("reason")
    return value if isinstance(value, str) else ""


@router.get("/{view}", response_model=OperatorEnvelope)
async def operator_view(
    view: OperatorView,
    session: SessionDependency,
    run_id: Annotated[
        str | None, Query(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    ] = None,
) -> OperatorEnvelope:
    """Resolve the selected shop and read its current rows on every request."""
    try:
        selected = await select_operator_run(session, run_id)
        shop = selected.shop
        scope = selected.workflow_scope()
        products = (
            await session.execute(
                select(Product, WorkflowRun)
                .join(WorkflowRun, Product.workflow_id == WorkflowRun.id)
                .where(Product.shop_id == shop.id, WorkflowRun.shop_id == shop.id, scope)
                .order_by(Product.created_at, Product.id)
            )
        ).all()
        by_workflow = {workflow.id: product for product, workflow in products}
        versions = (
            await session.execute(
                select(ListingVersion, EtsyListing, Product)
                .join(EtsyListing, ListingVersion.listing_id == EtsyListing.id)
                .join(Product, ListingVersion.product_id == Product.id)
                .join(WorkflowRun, Product.workflow_id == WorkflowRun.id)
                .where(
                    EtsyListing.shop_id == shop.id,
                    Product.shop_id == shop.id,
                    WorkflowRun.shop_id == shop.id,
                    EtsyListing.product_id == Product.id,
                    scope,
                )
                .order_by(
                    ListingVersion.listing_version, ListingVersion.created_at, ListingVersion.id
                )
            )
        ).all()
        latest = {version.product_id: version.id for version, _listing, _product in versions}
        items: list[OperatorRecord] = []

        def record(
            row_id: UUID,
            label: str,
            state: str,
            detail: str,
            product: Product | None,
            listing_id: UUID | None = None,
        ) -> None:
            items.append(
                OperatorRecord(
                    id=str(row_id),
                    label=label,
                    state=state,
                    detail=detail,
                    product_id=product.id if product else None,
                    listing_version_id=listing_id or (latest.get(product.id) if product else None),
                )
            )

        if view == OperatorView.NOW:
            for product, workflow in products:
                record(
                    product.id,
                    product.working_title,
                    workflow.product_state,
                    product.base_category,
                    product,
                )
        elif view == OperatorView.SHOP:
            for version, listing, product in versions:
                record(
                    version.id,
                    version.title,
                    listing.listing_state,
                    f"version {version.listing_version}; {version.currency} {version.price}",
                    product,
                    version.id,
                )
        elif view in (OperatorView.PIPELINE, OperatorView.BLOCKED):
            query = (
                select(Job)
                .join(WorkflowRun, Job.workflow_id == WorkflowRun.id)
                .where(WorkflowRun.shop_id == shop.id, scope)
            )
            if view == OperatorView.BLOCKED:
                query = query.where(Job.status == "BLOCKED")
            for job in await session.scalars(query.order_by(Job.created_at, Job.id)):
                record(
                    job.id,
                    job.job_type,
                    job.status,
                    _reason(job.input),
                    by_workflow.get(job.workflow_id),
                )
        elif view == OperatorView.DECISIONS:
            query = (
                select(Decision)
                .join(WorkflowRun, Decision.workflow_id == WorkflowRun.id)
                .where(WorkflowRun.shop_id == shop.id, scope)
            )
            by_product = {product.id: product for product, _workflow in products}
            for decision in await session.scalars(query.order_by(Decision.decided_at, Decision.id)):
                record(
                    decision.id,
                    decision.decision_type,
                    decision.branch_outcome or decision.decision or "",
                    decision.explanation,
                    by_product.get(decision.product_id),
                )
        elif view == OperatorView.INCIDENTS:
            query = select(Incident).where(Incident.shop_id == shop.id)
            if selected.execution_mode == "real_draft":
                query = query.join(WorkflowRun, Incident.workflow_id == WorkflowRun.id).where(
                    WorkflowRun.shop_id == shop.id, scope
                )
            for incident in await session.scalars(query.order_by(Incident.opened_at, Incident.id)):
                product = by_workflow.get(incident.workflow_id)
                # Explicit incident lineage must also belong to this shop's product.
                version_id = incident.listing_version_id
                if version_id not in {version.id for version, _listing, _product in versions}:
                    version_id = None
                record(
                    incident.id,
                    incident.incident_type,
                    incident.incident_state,
                    _reason(incident.safe_detail),
                    product,
                    version_id,
                )
                items[-1].listing_version_id = version_id
        else:
            query = select(IntegrationAccount).where(IntegrationAccount.shop_id == shop.id)
            product = products[-1][0] if products and selected.execution_mode == "fixture" else None
            for account in await session.scalars(
                query.order_by(IntegrationAccount.provider, IntegrationAccount.id)
            ):
                mode = account.safe_detail.get("mode")
                detail = f"mode={mode}" if isinstance(mode, str) else ""
                if account.blocker_code:
                    detail += f"; blocker={account.blocker_code}"
                record(account.id, account.provider, account.connection_state, detail, product)
        return OperatorEnvelope(
            run_id=selected.run_id, execution_mode=selected.execution_mode, view=view, items=items
        )
    except (SQLAlchemyError, OSError) as error:
        raise HTTPException(status_code=503, detail="operator database unavailable") from error
