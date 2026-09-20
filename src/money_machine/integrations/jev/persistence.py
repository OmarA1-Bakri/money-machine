"""Persistence operations for Jev evaluations.

Store and retrieve Jev decision engine evaluation results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.integrations.jev.models import DecisionPacket, DecisionResult
from money_machine.persistence.tables import JevEvaluation

if TYPE_CHECKING:
    from collections.abc import Sequence


async def store_evaluation(
    session: AsyncSession,
    packet: DecisionPacket,
    result: DecisionResult,
    decision_id: UUID | None = None,
    derived: dict | None = None,
) -> JevEvaluation:
    """Store a Jev evaluation result.

    Idempotent: stores new row each time (audit trail of all evaluations).

    Args:
        session: Database session
        packet: Original decision packet
        result: Jev evaluation result
        decision_id: Optional link to decisions table
        derived: Optional derived data (gates, actions, etc.)

    Returns:
        Persisted JevEvaluation record
    """
    evaluation = JevEvaluation(
        decision_id=decision_id,
        decision_type=packet.decision_type,
        packet=packet.model_dump(),
        answers=result.answers,
        derived=derived or {},
        model_id=result.model_id,
        latency_ms=result.latency_ms,
    )

    session.add(evaluation)
    await session.flush()
    return evaluation


async def get_evaluation(session: AsyncSession, evaluation_id: UUID) -> JevEvaluation | None:
    """Get a Jev evaluation by ID.

    Args:
        session: Database session
        evaluation_id: Evaluation UUID

    Returns:
        JevEvaluation if found, else None
    """
    result = await session.execute(
        select(JevEvaluation).where(JevEvaluation.id == evaluation_id)
    )
    return result.scalar_one_or_none()


async def get_evaluations_for_decision(
    session: AsyncSession, decision_id: UUID
) -> Sequence[JevEvaluation]:
    """Get all Jev evaluations linked to a decision.

    Args:
        session: Database session
        decision_id: Decision UUID

    Returns:
        List of JevEvaluation records (may be empty)
    """
    result = await session.execute(
        select(JevEvaluation)
        .where(JevEvaluation.decision_id == decision_id)
        .order_by(JevEvaluation.evaluated_at)
    )
    return result.scalars().all()


async def get_recent_evaluations(
    session: AsyncSession,
    decision_type: str | None = None,
    limit: int = 100,
) -> Sequence[JevEvaluation]:
    """Get recent Jev evaluations, optionally filtered by decision type.

    Args:
        session: Database session
        decision_type: Optional decision type filter
        limit: Maximum results to return

    Returns:
        List of JevEvaluation records, newest first
    """
    query = select(JevEvaluation).order_by(JevEvaluation.evaluated_at.desc()).limit(limit)

    if decision_type:
        query = query.where(JevEvaluation.decision_type == decision_type)

    result = await session.execute(query)
    return result.scalars().all()
