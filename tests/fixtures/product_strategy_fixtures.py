"""Test fixtures for S05 L3 — A05 Product Strategy scorer."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.research import CandidateRisk, ProductCandidate


def create_evidence_ref(summary: str) -> EvidenceReference:
    """Create a test evidence reference."""
    return EvidenceReference(
        evidence_id=uuid4(),
        evidence_type="test_evidence",
        source_reference="test_source",
        observed_at=datetime.now(UTC),
        sha256="0" * 64,
        safe_summary=summary,
    )


def create_candidate(
    identity: str,
    category: str,
    workflow_id: UUID | None = None,
    research_run_id: UUID | None = None,
    risks: tuple[CandidateRisk, ...] = (),
) -> ProductCandidate:
    """Create a test product candidate."""
    return ProductCandidate(
        candidate_id=uuid4(),
        workflow_id=workflow_id or uuid4(),
        research_run_id=research_run_id or uuid4(),
        identity=identity,
        base_category=category,
        risks=risks,
        evidence=(create_evidence_ref(f"Evidence for {identity}"),),
        created_at=datetime.now(UTC),
    )


# High-scoring candidate (should pass threshold)
QUALIFIED_CANDIDATE = create_candidate(
    identity="Digital Planner Template",
    category="Productivity",
    risks=(CandidateRisk(risk="Market saturation", severity="LOW"),),
)

# Medium-scoring candidate (edge case around threshold)
THRESHOLD_CANDIDATE = create_candidate(
    identity="Basic Budget Tracker",
    category="Finance",
    risks=(CandidateRisk(risk="Limited differentiation", severity="MEDIUM"),),
)

# Low-scoring candidate (should fail threshold)
REJECTED_CANDIDATE = create_candidate(
    identity="Complex Enterprise Solution",
    category="Business",
    risks=(
        CandidateRisk(risk="High complexity", severity="HIGH"),
        CandidateRisk(risk="Long implementation time", severity="HIGH"),
    ),
)

# Backup candidate (should be second choice)
BACKUP_CANDIDATE = create_candidate(
    identity="Simple Task Manager",
    category="Productivity",
    risks=(CandidateRisk(risk="Competition", severity="LOW"),),
)

# Complete shortlist with 5 candidates
COMPLETE_SHORTLIST = (
    QUALIFIED_CANDIDATE,
    BACKUP_CANDIDATE,
    THRESHOLD_CANDIDATE,
    REJECTED_CANDIDATE,
    create_candidate("Generic Template", "Design"),
)
