"""Test fixtures for S05 L3 — A05 Product Strategy scorer."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.research import CandidateProfile


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
    risk_notes: str = "",
) -> CandidateProfile:
    """Create a test candidate profile."""
    return CandidateProfile(
        identity=identity,
        base_category=category,
        price_range=(Decimal("10.00"), Decimal("25.00")),
        observation_count=15,
        shop_count=8,
        young_fast_shop_count=3,
        risk_notes=risk_notes,
    )


# High-scoring candidate (should pass threshold)
QUALIFIED_CANDIDATE = create_candidate(
    identity="Digital Planner Template",
    category="Productivity",
    risk_notes="Market saturation (LOW)",
)

# Medium-scoring candidate (edge case around threshold)
THRESHOLD_CANDIDATE = create_candidate(
    identity="Basic Budget Tracker",
    category="Finance",
    risk_notes="Limited differentiation (MEDIUM)",
)

# Low-scoring candidate (should fail threshold)
REJECTED_CANDIDATE = create_candidate(
    identity="Complex Enterprise Solution",
    category="Business",
    risk_notes="High complexity (HIGH); Long implementation time (HIGH)",
)

# Backup candidate (should be second choice)
BACKUP_CANDIDATE = create_candidate(
    identity="Simple Task Manager",
    category="Productivity",
    risk_notes="Competition (LOW)",
)

# Complete shortlist with 5 candidates
COMPLETE_SHORTLIST = (
    QUALIFIED_CANDIDATE,
    BACKUP_CANDIDATE,
    THRESHOLD_CANDIDATE,
    REJECTED_CANDIDATE,
    create_candidate("Generic Template", "Design"),
)
