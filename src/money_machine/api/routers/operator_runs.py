"""Resolve operator run identity without broadening a real run to its whole shop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from money_machine.persistence.tables import Shop, WorkflowRun

ExecutionMode = Literal["fixture", "real_draft"]


@dataclass(frozen=True)
class OperatorRun:
    shop: Shop
    run_id: str
    execution_mode: ExecutionMode

    def workflow_scope(self) -> ColumnElement[bool]:
        return (
            WorkflowRun.workflow_type == "RealProductDraft:" + self.run_id
            if self.execution_mode == "real_draft"
            else true()
        )


async def select_operator_run(session: AsyncSession, run_id: str | None) -> OperatorRun:
    fixtures = select(Shop)
    fixtures = fixtures.where(
        Shop.name.startswith("fixture:", autoescape=True)
        if run_id is None
        else Shop.name == "fixture:" + run_id
    )
    shop = await session.scalar(fixtures.order_by(Shop.created_at.desc(), Shop.id.desc()).limit(1))
    if shop is not None:
        return OperatorRun(shop, shop.name.removeprefix("fixture:"), "fixture")
    if run_id is not None:
        shop = await session.scalar(
            select(Shop)
            .join(WorkflowRun, WorkflowRun.shop_id == Shop.id)
            .where(
                Shop.name == "QuietlyBuiltStudio",
                WorkflowRun.workflow_type == "RealProductDraft:" + run_id,
            )
            .limit(1)
        )
        if shop is not None:
            return OperatorRun(shop, run_id, "real_draft")
    raise HTTPException(status_code=404, detail="operator run not found")
