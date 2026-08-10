from __future__ import annotations

import hashlib
import json
from pathlib import Path

from money_machine.domain.models.product_spec import ProductFact, ProductSpec
from money_machine.integrations.notion.fixture_adapter import LocalNotionAdapter


def test_local_bundle_is_self_contained_and_manifest_verifiable(tmp_path: Path) -> None:
    spec = ProductSpec(
        product_spec_id="spec-local-integration",
        candidate_id="candidate-local-integration",
        identity_niche="Home Bakers",
        base_category="Order Planner",
        target_buyer="People managing Home Bakers",
        promised_outcome="A structured Order Planner workspace",
        hubs=("Home", "Orders", "Customers", "Calendar", "Recipes", "Costs"),
        colour_variants=("Berry", "Vanilla", "Cocoa"),
        features=("order queue", "cost notes"),
        product_facts=(
            ProductFact(
                claim="Configured with 6 hubs",
                category="HUB_INVENTORY",
                evidence_ids=("evidence-local",),
            ),
            ProductFact(
                claim="Includes order queue",
                category="FEATURE",
                evidence_ids=("evidence-local",),
            ),
            ProductFact(
                claim="Includes cost notes",
                category="FEATURE",
                evidence_ids=("evidence-local",),
            ),
            ProductFact(
                claim="Configured with 3 colour variants",
                category="COLOUR_VARIANTS",
                evidence_ids=("evidence-local",),
            ),
            ProductFact(
                claim="People managing Home Bakers",
                category="BUYER_FIT",
                evidence_ids=("evidence-local",),
            ),
            ProductFact(
                claim="A structured Order Planner workspace",
                category="WORKFLOW_OUTCOME",
                evidence_ids=("evidence-local",),
            ),
        ),
        source_evidence_ids=("evidence-local",),
        spec_sha256="5" * 64,
    )

    build = LocalNotionAdapter().build(spec, tmp_path / "bundle")
    root = Path(build.root_artifact_path)
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)

    assert hashlib.sha256(manifest_bytes).hexdigest() == build.manifest_sha256
    for entry in manifest["artifacts"]:
        path = root / entry["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    rendered_text = "\n".join(
        path.read_text(encoding="utf-8") for path in root.rglob("*") if path.is_file()
    )
    assert "http://" not in rendered_text
    assert "https://" not in rendered_text
    assert (root / "assets").is_dir()
