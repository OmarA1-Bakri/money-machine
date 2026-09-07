"""Canonical strict Pydantic contracts for Session 01 domain work."""

from money_machine.domain.models.common import (
    ArtifactReference,
    CheckResult,
    ContractError,
    EffectReference,
    EvidenceReference,
    SuccessContract,
)
from money_machine.domain.models.jobs import AgentResult, JobEnvelope
from money_machine.domain.models.listings import ListingPackage, PreflightResult
from money_machine.domain.models.portfolio import (
    IncidentResult,
    MetricsSnapshot,
    PortfolioDecision,
)
from money_machine.domain.models.products import (
    BuildResult,
    DedupeCollision,
    DedupeResult,
    ProductQAResult,
    ProductSpec,
    ResearchObservation,
    ResearchReport,
    TeardownReport,
)
from money_machine.domain.models.rules import ListingRules, ProductShapeRules

__all__ = [
    "AgentResult",
    "ArtifactReference",
    "BuildResult",
    "CheckResult",
    "ContractError",
    "DedupeCollision",
    "DedupeResult",
    "EffectReference",
    "EvidenceReference",
    "IncidentResult",
    "JobEnvelope",
    "ListingPackage",
    "ListingRules",
    "MetricsSnapshot",
    "PortfolioDecision",
    "PreflightResult",
    "ProductQAResult",
    "ProductShapeRules",
    "ProductSpec",
    "ResearchObservation",
    "ResearchReport",
    "SuccessContract",
    "TeardownReport",
]
