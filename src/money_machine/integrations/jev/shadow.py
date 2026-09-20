"""Jev shadow evaluation hooks.

Shadow-mode Jev calls that log/persist without mutating workflow state.
Safe to call from any decision path; never blocks or fails the main execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from money_machine.integrations.jev import DecisionPacket, JevClient, NoulQuestion
from money_machine.integrations.jev.persistence import store_evaluation

if TYPE_CHECKING:
    from money_machine.domain.models.portfolio import PortfolioDecision
    from money_machine.persistence.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


async def shadow_evaluate_decision(
    uow: UnitOfWork,
    jev_client: JevClient,
    decision: PortfolioDecision,
    decision_db_id: UUID | None = None,
) -> None:
    """Shadow-evaluate a portfolio decision with Jev.

    Calls Jev Gateway with shadow_mode_jev_only_log decision type.
    Logs and persists the result.
    Never mutates workflow state; never blocks or fails the main path.

    Safe to call from any decision path. Errors are caught and logged only.

    Args:
        uow: Unit of work (for persistence)
        jev_client: Jev client (real or fake)
        decision: Portfolio decision to shadow-evaluate
        decision_db_id: Optional DB ID to link the evaluation
    """
    try:
        # Build shadow decision packet
        packet = DecisionPacket(
            decision_type="shadow_mode_jev_only_log",
            context={
                "workflow_id": str(decision.workflow_id),
                "product_id": str(decision.product_id),
                "listing_id": str(decision.listing_id),
                "decision": decision.decision.value,
                "cohort_reference": decision.cohort_reference,
                "explanation": decision.explanation,
            },
            questions=[
                NoulQuestion(
                    question_id="should_log",
                    prompt="Should this decision be logged for shadow analysis?",
                ),
            ],
        )

        # Evaluate with Jev (timeout 5s for shadow)
        result = await jev_client.evaluate(packet, timeout=5.0)

        # Persist evaluation result
        async with uow.session() as session:
            await store_evaluation(
                session=session,
                packet=packet,
                result=result,
                decision_id=decision_db_id,
                derived={"shadow_mode": True, "source": "dispatch_decision"},
            )
            await session.commit()

        logger.info(
            "Shadow Jev evaluation logged",
            extra={
                "decision_type": "shadow_mode_jev_only_log",
                "workflow_id": str(decision.workflow_id),
                "model_id": result.model_id,
                "latency_ms": result.latency_ms,
            },
        )

    except Exception as e:
        # Shadow hook never blocks main path - log and continue
        logger.warning(
            "Shadow Jev evaluation failed (non-blocking)",
            extra={
                "decision_type": "shadow_mode_jev_only_log",
                "workflow_id": str(decision.workflow_id),
                "error": str(e),
            },
            exc_info=True,
        )


async def maybe_shadow_evaluate(
    uow: UnitOfWork,
    jev_client: JevClient | None,
    decision: PortfolioDecision,
    decision_db_id: UUID | None = None,
) -> None:
    """Maybe call shadow_evaluate_decision if Jev client is configured.

    Convenience wrapper that checks if jev_client is provided before calling.
    Safe to call unconditionally - no-op if jev_client is None.

    Args:
        uow: Unit of work
        jev_client: Jev client (None disables shadow eval)
        decision: Portfolio decision
        decision_db_id: Optional DB ID to link the evaluation
    """
    if jev_client is not None:
        await shadow_evaluate_decision(uow, jev_client, decision, decision_db_id)
