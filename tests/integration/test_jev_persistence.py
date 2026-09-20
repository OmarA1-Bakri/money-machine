"""Integration tests for Jev persistence.

Tests store_evaluation/get_evaluation round-trip with database.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.integrations.jev import (
    DecisionPacket,
    DecisionResult,
    NoulQuestion,
)
from money_machine.integrations.jev.persistence import get_evaluation, store_evaluation


class TestPersistence:
    """Tests for Jev evaluation persistence (store_evaluation / get_evaluation round-trip)."""

    async def test_store_and_retrieve_evaluation(self, session: AsyncSession) -> None:
        """Round-trip: store evaluation, then retrieve it back with all fields intact."""
        packet = DecisionPacket(
            decision_type="preflight_blockers_present",
            context={"workflow_id": "test-abc"},
            questions=[
                NoulQuestion(question_id="has_blockers", prompt="Any blockers?"),
            ],
        )

        result = DecisionResult(
            decision_type="preflight_blockers_present",
            answers={"has_blockers": True},
            model_id="jev-1.0",
            latency_ms=150,
        )

        derived = {"shadow_mode": True, "source": "test"}

        # Store
        stored = await store_evaluation(
            session=session,
            packet=packet,
            result=result,
            decision_id=None,
            derived=derived,
        )
        await session.commit()

        # Retrieve
        retrieved = await get_evaluation(session, stored.id)

        assert retrieved is not None
        assert retrieved.id == stored.id
        assert retrieved.decision_type == "preflight_blockers_present"
        assert retrieved.packet == packet.model_dump()
        assert retrieved.answers == {"has_blockers": True}
        assert retrieved.derived == derived
        assert retrieved.model_id == "jev-1.0"
        assert retrieved.latency_ms == 150

    async def test_store_without_derived(self, session: AsyncSession) -> None:
        """Can store evaluation without derived data."""
        packet = DecisionPacket(
            decision_type="test_decision",
            context={},
            questions=[NoulQuestion(question_id="q1", prompt="Test")],
        )

        result = DecisionResult(
            decision_type="test_decision",
            answers={"q1": False},
            model_id="jev-1.0",
            latency_ms=100,
        )

        stored = await store_evaluation(
            session=session,
            packet=packet,
            result=result,
            derived=None,
        )
        await session.commit()

        retrieved = await get_evaluation(session, stored.id)

        assert retrieved is not None
        # derived=None is stored as {}
        assert retrieved.derived == {}
