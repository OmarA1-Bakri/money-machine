"""Earn Session 07 evidence by running the fixture build.

The live sandbox is not started. A07, A08, and A09 are not commissioned.
A key is earned only when both the mass build and the business build produce
the artifact that key names.
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from money_machine.agents.implementations.notion_aesthetics import (
    build_aesthetics_and_content_completion,
)
from money_machine.agents.implementations.notion_dashboard import build_dashboard_and_navigation
from money_machine.agents.implementations.notion_fact_ledger import run_fact_ledger
from money_machine.agents.implementations.notion_hubs import build_identity_specific_hubs
from money_machine.agents.implementations.notion_notifications import build_notification_dashboard
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    ProductBuildCheckpoint,
    build_top_level_page_and_design_shell,
)
from money_machine.agents.implementations.notion_qa import run_product_qa
from money_machine.agents.implementations.notion_shared_databases import (
    build_shared_databases,
    shared_database_kinds,
)
from money_machine.agents.implementations.notion_test_matrix import run_test_matrix
from money_machine.agents.implementations.notion_variants import build_variants
from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.product_spec import ColourToken, Hub, ProductSpec
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter

BEHAVIORAL_EVIDENCE_KEYS = frozenset(
    {
        "notion_product_builder_implemented",
        "shared_databases_built",
        "home_dashboard_built",
        "notification_dashboard_built",
        "identity_hubs_built",
        "variant_builder_implemented",
        "product_qa_implemented",
        "product_fact_ledger_persisted",
        "build_workflow_linked",
        "product_build_tests_pass",
    }
)
CONTROL_EVIDENCE_KEY = "control_files_and_checkpoint_current"
CLOSURE_EVIDENCE_KEY = "evidence_closure_commit_recorded"
_READY = "ListingCopyJob"
_PHASE_ONE = datetime(2026, 10, 3, 0, 30, tzinfo=UTC)
_DATABASES = datetime(2026, 10, 5, 20, 0, tzinfo=UTC)
_DASHBOARD = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)
_HUBS = datetime(2026, 10, 5, 23, 45, tzinfo=UTC)
_NOTIFICATIONS = datetime(2026, 10, 6, 0, 30, tzinfo=UTC)
_AESTHETICS = datetime(2026, 10, 6, 1, 30, tzinfo=UTC)
_VARIANTS = datetime(2026, 10, 6, 2, 30, tzinfo=UTC)
_QA = datetime(2026, 10, 6, 3, 30, tzinfo=UTC)
_LEDGER = datetime(2026, 10, 7, 5, 0, tzinfo=UTC)
_MATRIX = datetime(2026, 10, 10, 2, 0, tzinfo=UTC)
_TIERS = (
    ("mass", "Weekly Planner", "Home Dashboard Planner", "Hub"),
    ("business", "Studio Ledger", "Studio Home", "Desk"),
)


class Session07ProofError(ValueError):
    """The fixture build did not earn a Session 07 key."""

    def __init__(self, code: str) -> None:
        """Store the failing-step code on the error."""
        super().__init__(code)
        self.code = code


def _spec(tier: str, identity: str, title: str, hub_name: str) -> ProductSpec:
    """Build a fixture product spec for one tier of the Session 07 proof."""
    return ProductSpec(
        spec_id=uuid4(),
        product_id=uuid4(),
        workflow_id=uuid4(),
        version=1,
        producing_job_id=uuid4(),
        producing_agent_run_id=uuid4(),
        identity=identity,
        base_category="Planners",
        buyer_problem="Keep one week visible",
        title=title,
        tier=tier,
        real_price=Decimal("9.99"),
        anchor_price=Decimal("19.99"),
        currency="USD",
        palette_name="Modern Minimalist",
        palette_tokens=(
            ColourToken(name="Primary", hex="#2C3E50"),
            ColourToken(name="Secondary", hex="#3498DB"),
            ColourToken(name="Accent", hex="#E74C3C"),
        ),
        hubs=tuple(
            Hub(name=f"{hub_name} {index}", description=f"{identity} copy {index}", page_count=3)
            for index in range(1, 7)
        ),
        colour_variants=("Blue", "Green", "Purple"),
        flagship_feature="One visible week",
        experiment_hypothesis="A visible week is enough",
        shared_databases=(),
        page_target_min=40,
        page_target_max=60,
        concept_fingerprint=("a" if tier == "mass" else "b") * 64,
        rule_version="v1",
        evidence=(
            EvidenceReference(
                evidence_id=uuid4(),
                evidence_type="fixture",
                source_reference="src/money_machine/control/session_07_proof.py",
                observed_at=_PHASE_ONE,
                safe_summary="Session 07 fixture proof",
            ),
        ),
        created_at=_PHASE_ONE,
    )


async def _build(spec: ProductSpec, root: Path) -> ProductBuildCheckpoint:
    """Run every build phase against the fixture adapter and return the final checkpoint."""
    probe = FixtureNotionAdapter()
    path = root / "build.json"
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=_PHASE_ONE)
    await build_shared_databases(spec, probe, path, recorded_at=_DATABASES)
    await build_dashboard_and_navigation(spec, probe, path, recorded_at=_DASHBOARD)
    await build_identity_specific_hubs(spec, probe, path, recorded_at=_HUBS)
    await build_notification_dashboard(spec, probe, path, recorded_at=_NOTIFICATIONS)
    await build_aesthetics_and_content_completion(spec, probe, path, recorded_at=_AESTHETICS)
    await build_variants(spec, probe, path, recorded_at=_VARIANTS)
    await run_product_qa(spec, probe, path, recorded_at=_QA)
    await run_fact_ledger(spec, probe, path, recorded_at=_LEDGER)
    return await run_test_matrix(spec, probe, path, recorded_at=_MATRIX)


def _require(condition: bool, code: str) -> None:
    """Raise ``Session07ProofError`` with ``code`` when ``condition`` is false."""
    if not condition:
        raise Session07ProofError(code)


def _earned(spec: ProductSpec, checkpoint: ProductBuildCheckpoint) -> frozenset[str]:
    """Check the checkpoint proves every behavioral key and return the keys it earned."""
    kinds = shared_database_kinds(spec)
    matrix = checkpoint.test_matrix
    ledger = checkpoint.fact_ledger
    link = checkpoint.workflow_link
    qa = checkpoint.qa
    notice = checkpoint.notification_dashboard
    _require(checkpoint.page_id != "" and checkpoint.shell_block_id != "", "builder")
    _require(checkpoint.checkpoint_names == BUILD_PHASES, "phases")
    _require(
        tuple(kind for kind, _database_id in checkpoint.database_ids) == kinds,
        "databases",
    )
    _require(len(checkpoint.dashboard_pieces) > 0, "home")
    _require(
        tuple(hub.name for hub in checkpoint.identity_hubs) == tuple(hub.name for hub in spec.hubs),
        "hubs",
    )
    _require(notice is not None and notice.database_id != "", "notifications")
    _require(
        tuple(record.name for record in checkpoint.variants) == spec.colour_variants,
        "variants",
    )
    _require(qa is not None and qa.verdict == "PASS" and qa.proof_page_id != "", "qa")
    _require(ledger is not None and ledger.verdict == "PASS" and len(ledger.facts) > 0, "ledger")
    _require(
        link is not None
        and link.verdict == "PASS"
        and link.ready == _READY
        and len(link.steps) > 0,
        "workflow",
    )
    _require(
        matrix is not None
        and matrix.verdict == "PASS"
        and matrix.tier == spec.tier
        and all(passed for _name, passed in matrix.checks),
        "matrix",
    )
    return BEHAVIORAL_EVIDENCE_KEYS


async def prove_session_07() -> frozenset[str]:
    """Return the behavioral keys when both fixture tiers pass."""
    earned = BEHAVIORAL_EVIDENCE_KEYS
    for tier, identity, title, hub_name in _TIERS:
        spec = _spec(tier, identity, title, hub_name)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = await _build(spec, Path(directory))
        earned = earned & _earned(spec, checkpoint)
    if earned != BEHAVIORAL_EVIDENCE_KEYS:
        raise Session07ProofError("incomplete")
    return earned
