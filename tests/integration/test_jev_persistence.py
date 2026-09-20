"""Integration tests for Jev persistence.

Tests store_evaluation/get_evaluation round-trip with database.
Tests shadow evaluation hooks prove no job/decision mutation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.enums import DecisionType
from money_machine.domain.models.evidence import EvidenceReference
from money_machine.domain.models.portfolio import PortfolioDecision
from money_machine.integrations.jev import (
    DecisionPacket,
    DecisionResult,
    FakeJevProvider,
    NoulQuestion,
)
from money_machine.integrations.jev.persistence import get_evaluation, store_evaluation
from money_machine.integrations.jev.shadow import (
    maybe_shadow_evaluate,
    shadow_evaluate_decision,
)
from money_machine.persistence.unit_of_work import UnitOfWork


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


class TestShadowEvaluation:
    """Tests that prove shadow hook calls + persist without mutating job/decision state."""

    async def test_shadow_evaluate_decision_does_not_mutate_decision(
        self, session: AsyncSession
    ) -> None:
        """Shadow evaluation persists result but never mutates the decision object."""
        # Create a HOLD decision
        decision = PortfolioDecision(
            decision_id=uuid4(),
            workflow_id=uuid4(),
            product_id=uuid4(),
            listing_id=uuid4(),
            decision=DecisionType.HOLD,
            metrics_snapshot_ids=(uuid4(),),
            cohort_reference="test-cohort",
            rule_version="v1.0",
            explanation="Test decision for shadow eval",
            evidence=(
                EvidenceReference(
                    artifact_id=uuid4(),
                    check_name="test_check",
                    verdict="PASS",
                ),
            ),
            decided_at=datetime.now(UTC),
        )

        # Capture original state
        original_state = decision.model_dump()

        # Set up fake Jev client
        fake_client = FakeJevProvider()
        fake_client.set_answers("shadow_mode_jev_only_log", {"should_log": True})

        # Create UoW and call shadow hook
        uow = UnitOfWork(session)
        await shadow_evaluate_decision(uow, fake_client, decision, decision_db_id=None)
        await session.commit()

        # Assert decision object unchanged
        assert decision.model_dump() == original_state
        assert decision.decision == DecisionType.HOLD
        assert decision.repair_job_id is None
        assert decision.deactivation_job_id is None
        assert decision.successor_workflow_id is None

        # Assert shadow evaluation was called (proves persist path was exercised)
        assert fake_client.get_call_count("shadow_mode_jev_only_log") == 1

    async def test_maybe_shadow_evaluate_with_client_calls_shadow(
        self, session: AsyncSession
    ) -> None:
        """maybe_shadow_evaluate calls shadow_evaluate_decision when client provided."""
        decision = PortfolioDecision(
            decision_id=uuid4(),
            workflow_id=uuid4(),
            product_id=uuid4(),
            listing_id=uuid4(),
            decision=DecisionType.HOLD,
            metrics_snapshot_ids=(uuid4(),),
            cohort_reference="test-cohort",
            rule_version="v1.0",
            explanation="Test decision",
            evidence=(
                EvidenceReference(
                    artifact_id=uuid4(),
                    check_name="test_check",
                    verdict="PASS",
                ),
            ),
            decided_at=datetime.now(UTC),
        )

        original_state = decision.model_dump()

        fake_client = FakeJevProvider()
        fake_client.set_answers("shadow_mode_jev_only_log", {"should_log": True})

        uow = UnitOfWork(session)
        await maybe_shadow_evaluate(uow, fake_client, decision, decision_db_id=None)
        await session.commit()

        # Decision unchanged
        assert decision.model_dump() == original_state
        # Shadow was called
        assert fake_client.get_call_count("shadow_mode_jev_only_log") == 1

    async def test_maybe_shadow_evaluate_without_client_is_noop(
        self, session: AsyncSession
    ) -> None:
        """maybe_shadow_evaluate does nothing when client is None (safe no-op)."""
        decision = PortfolioDecision(
            decision_id=uuid4(),
            workflow_id=uuid4(),
            product_id=uuid4(),
            listing_id=uuid4(),
            decision=DecisionType.HOLD,
            metrics_snapshot_ids=(uuid4(),),
            cohort_reference="test-cohort",
            rule_version="v1.0",
            explanation="Test decision",
            evidence=(
                EvidenceReference(
                    artifact_id=uuid4(),
                    check_name="test_check",
                    verdict="PASS",
                ),
            ),
            decided_at=datetime.now(UTC),
        )

        original_state = decision.model_dump()

        uow = UnitOfWork(session)
        # No client provided
        await maybe_shadow_evaluate(uow, None, decision, decision_db_id=None)
        await session.commit()

        # Decision unchanged
        assert decision.model_dump() == original_state

    async def test_shadow_evaluate_never_mutates_job_state(self, session: AsyncSession) -> None:
        """Shadow evaluation never changes job IDs on the decision (Exit 78 / uncommissioned)."""
        # Create a REPAIR decision with job ID
        repair_job_id = uuid4()
        decision = PortfolioDecision(
            decision_id=uuid4(),
            workflow_id=uuid4(),
            product_id=uuid4(),
            listing_id=uuid4(),
            decision=DecisionType.REPAIR,
            metrics_snapshot_ids=(uuid4(),),
            cohort_reference="test-cohort",
            rule_version="v1.0",
            explanation="Repair decision",
            evidence=(
                EvidenceReference(
                    artifact_id=uuid4(),
                    check_name="test_check",
                    verdict="FAIL",
                ),
            ),
            repair_job_id=repair_job_id,
            decided_at=datetime.now(UTC),
        )

        # Capture job state
        assert decision.repair_job_id == repair_job_id
        assert decision.deactivation_job_id is None

        fake_client = FakeJevProvider()
        fake_client.set_answers("shadow_mode_jev_only_log", {"should_log": False})

        uow = UnitOfWork(session)
        await shadow_evaluate_decision(uow, fake_client, decision, decision_db_id=None)
        await session.commit()

        # Job IDs unchanged
        assert decision.repair_job_id == repair_job_id
        assert decision.deactivation_job_id is None
        assert decision.successor_workflow_id is None
        # Decision type unchanged
        assert decision.decision == DecisionType.REPAIR
