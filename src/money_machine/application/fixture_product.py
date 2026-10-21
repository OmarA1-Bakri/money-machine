"""Fixture library product path; no worker or live provider is commissioned."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from uuid import uuid5

from money_machine.agents.contracts.merchandising import (
    BuiltVariant,
    FactKey,
    FreeGiftConfig,
    MerchandisingInput,
    NotificationDashboardBehaviour,
    ProductFact,
    SupportConfig,
    encode_dashboard,
    encode_free_gift,
    encode_support,
    money_text,
)
from money_machine.agents.implementations.merchandising import configured_listing_rules
from money_machine.agents.implementations.notion_aesthetics import (
    build_aesthetics_and_content_completion,
)
from money_machine.agents.implementations.notion_dashboard import build_dashboard_and_navigation
from money_machine.agents.implementations.notion_fact_ledger import run_fact_ledger
from money_machine.agents.implementations.notion_hubs import build_identity_specific_hubs
from money_machine.agents.implementations.notion_notifications import build_notification_dashboard
from money_machine.agents.implementations.notion_product_builder import (
    build_top_level_page_and_design_shell,
)
from money_machine.agents.implementations.notion_qa import run_product_qa
from money_machine.agents.implementations.notion_shared_databases import build_shared_databases
from money_machine.agents.implementations.notion_variants import build_variants
from money_machine.application.fixture_provider import durable_probe
from money_machine.config.loader import load_yaml_model
from money_machine.config.settings import ProductRulesConfig
from money_machine.domain.models.product_spec import ProductSpec as BuildSpec
from money_machine.domain.models.products import ProductSpec

ROOT = Path(__file__).resolve().parents[3]


def merchandising_spec(spec: BuildSpec) -> ProductSpec:
    """Explicit lossless concept bridge; build-only design fields stay in source spec."""
    if spec.lineage_kind != "ORIGINAL" or spec.research_run_id is None:
        raise ValueError("fixture bridge requires an original research-backed spec")
    rules = load_yaml_model(ROOT / "config/product_rules.yaml", ProductRulesConfig)
    return ProductSpec(
        spec_id=spec.spec_id,
        product_id=spec.product_id,
        workflow_id=spec.workflow_id,
        version=spec.version,
        lineage_kind=spec.lineage_kind,
        identity=spec.identity,
        base_category=spec.base_category,
        buyer_problem=spec.buyer_problem,
        title=spec.title,
        tier=spec.tier,
        real_price=spec.real_price,
        anchor_price=spec.anchor_price,
        currency=spec.currency,
        shape_rules=rules.product_shape_rules(),
        hubs=tuple(hub.name for hub in spec.hubs),
        colour_variants=spec.colour_variants,
        features=(spec.flagship_feature, "Shared databases"),
        experiment_plan=spec.experiment_hypothesis,
        concept_fingerprint=spec.concept_fingerprint,
        source_evidence=spec.evidence,
        created_at=spec.created_at,
    )


async def build_product(spec: BuildSpec, directory: Path, when: datetime):
    """Run all existing builder phases, structural gate, variants, QA and ledger."""
    probe = durable_probe(directory / "fixture-notion.json")
    checkpoint = directory / "build-checkpoint.json"
    for stage in (
        build_top_level_page_and_design_shell,
        build_shared_databases,
        build_dashboard_and_navigation,
        build_identity_specific_hubs,
        build_notification_dashboard,
        build_aesthetics_and_content_completion,
    ):
        if checkpoint.exists():
            import json

            saved = json.loads(checkpoint.read_text())
            names = saved.get("checkpoint_names", [])
            # The existing checkpoint names are authoritative, not this receipt.
            if stage.__name__.removeprefix("build_") in names:
                continue
        built = await stage(spec, probe, checkpoint, recorded_at=when)
    from money_machine.agents.implementations.notion_variants import load_variant_checkpoint

    built, _ = load_variant_checkpoint(checkpoint)
    if len(built.database_ids) != 6 or len(built.identity_hubs) != len(spec.hubs):
        raise ValueError("base structure failed: shared databases or hubs")
    built = await build_variants(spec, probe, checkpoint, recorded_at=when)
    built = await run_product_qa(spec, probe, checkpoint, recorded_at=when)
    if built.qa is None or built.qa.verdict != "PASS" or not all(ok for _, ok in built.qa.checks):
        raise ValueError("real product QA blocked")
    built = await run_fact_ledger(spec, probe, checkpoint, recorded_at=when)
    if built.fact_ledger is None or built.fact_ledger.verdict != "PASS":
        raise ValueError("fact ledger blocked")
    return probe, built


def merchandising_request(spec: BuildSpec, built) -> MerchandisingInput:
    """Project checked ledger facts and explicit fixture policies into typed claims."""
    product = merchandising_spec(spec)
    ledger = dict(built.fact_ledger.facts)
    # Devices remain explicitly unverified, as the existing QA records. No compatibility
    # claim is invented. Support/gift are explicit fixture offers, never live services.
    dashboard = NotificationDashboardBehaviour(present=True, outputs=("Notification dashboard",))
    support = SupportConfig(offered=False)
    gift = FreeGiftConfig(offered=True, name="Starter checklist", community="Fixture circle")
    values: dict[FactKey, str] = {
        "page_count": ledger["page_count"],
        "hubs": "|".join(product.hubs),
        "colour_names": "|".join(product.colour_variants),
        "features": "|".join(product.features),
        "shop_name": "Fixture Shop",
        "price": money_text(product.real_price),
        "anchor_price": money_text(product.anchor_price),
        "currency": product.currency,
        "identity": product.identity,
        "base_category": product.base_category,
        "buyer_problem": product.buyer_problem,
        "support": encode_support(support),
        "free_gift": encode_free_gift(gift),
        "dashboard_outputs": encode_dashboard(dashboard),
        "supported_devices": ledger["supported_devices"],
        "secret_links": built.variants[0].secret_link,
    }
    facts = tuple(
        ProductFact(
            fact_id=uuid5(product.spec_id, key),
            product_id=product.product_id,
            spec_id=product.spec_id,
            fact_key=key,
            fact_value=value,
        )
        for key, value in values.items()
    )
    return MerchandisingInput(
        spec=product,
        facts=facts,
        hubs=product.hubs,
        page_count=int(ledger["page_count"]),
        variants=tuple(
            BuiltVariant(
                name=row.name,
                colour="#" + hashlib.sha256(row.name.encode()).hexdigest()[:6].upper(),
            )
            for row in built.variants
        ),
        notification_dashboard=dashboard,
        shop_name=values["shop_name"],
        price=product.real_price,
        anchor_price=product.anchor_price,
        support=support,
        free_gift=gift,
        rules=configured_listing_rules(),
    )
