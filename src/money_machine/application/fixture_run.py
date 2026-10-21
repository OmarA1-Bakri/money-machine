"""Explicit fixture application, persisting real library outputs in canonical tables."""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import yaml
from pydantic import TypeAdapter
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from money_machine.agents.base import AgentContext
from money_machine.agents.contracts.product_strategy import (
    ProductStrategyInput,
    ProductStrategyResult,
)
from money_machine.agents.implementations.market_research import MarketResearchAgent
from money_machine.agents.implementations.merchandising import merchandise
from money_machine.agents.implementations.product_strategy import A05ProductStrategy
from money_machine.agents.registry import AgentRegistry
from money_machine.application.fixture_product import ROOT, build_product, merchandising_request
from money_machine.assets.draft_listing_successor import create_ready_draft_listing_job
from money_machine.assets.etsy_draft import DraftEvidence
from money_machine.assets.etsy_preflight import (
    EtsyPreflightDraft,
    PreflightBlocked,
    PreflightClaim,
    run_etsy_preflight,
)
from money_machine.assets.fixture_bundle import render_bundle, sha, verify_bundle, write_json
from money_machine.domain.enums import AgentRunStatus, JobStatus, RetryClass, SideEffectClass
from money_machine.domain.models.common import SuccessContract
from money_machine.domain.models.jobs import JobEnvelope
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.models.research import ResearchReport
from money_machine.integrations.etsy.draft_client import DraftLedger, EtsyDraftClient
from money_machine.integrations.llm.fake_provider import FakeLLMProvider
from money_machine.persistence import tables as t
from money_machine.persistence.database import create_session_factory
from money_machine.persistence.seed import seed
from money_machine.persistence.unit_of_work import UnitOfWork


class FixtureDraftTransport:
    """Run-scoped fixture marketplace; persistent rows reconcile a killed process."""

    def __init__(self, directory: Path, listing_id: int):
        self.path = directory / "fixture-marketplace.json"
        self.listing_id = listing_id
        self.posts = 0

    def exchange(self, call):
        rows = json.loads(self.path.read_text()) if self.path.exists() else []
        if call.method == "GET":
            offset = int(dict(call.query).get("offset", "0"))
            return {"count": len(rows), "results": rows[offset : offset + 100]}
        if call.method != "POST":
            raise ValueError("fixture transport refuses unsupported mutation")
        row = dict(call.body or ())
        row.update(state="draft", listing_id=self.listing_id)
        rows.append(row)
        write_json(self.path, rows)
        self.posts += 1
        return row


class FixtureRun:
    def __init__(self, run_id: str, root: Path):
        self.run_id = run_id
        self.directory = root / run_id / "e2e"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.namespace = uuid5(NAMESPACE_URL, "money-machine:fixture:" + run_id)
        self.when = datetime(2026, 10, 20, 21, 14, 45, tzinfo=UTC)
        self.receipts = []

    def key(self, label: str):
        return uuid5(self.namespace, label)

    def receipt(self, stage, implementation, output, job=None):
        row = dict(
            run_id=self.run_id,
            stage=stage,
            implementation=implementation,
            mode="fixture",
            execution_kind="deterministic_fixture_library",
            prompt_used=False,
            outcome="RECORDED",
            input_id=str(self.key("workflow")),
            output_id=str(output),
            job_id=str(job.id) if job else None,
        )
        self.receipts.append(row)
        (self.directory / "receipts.jsonl").write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in self.receipts)
        )

    async def job(self, session, name, agent):
        row = await session.get(t.Job, self.key(name))
        if row is None:
            row = t.Job(
                id=self.key(name),
                workflow_id=self.key("workflow"),
                job_type=name,
                object_type="products",
                object_id=self.key("product"),
                owner_agent_id=agent,
                status="RUNNING",
                input={"mode": "fixture", "run_id": self.run_id},
                success_contract={"output_model": "FixtureLibraryOutput"},
                scheduled_at=self.when,
                idempotency_key=f"fixture:{self.run_id}:{name}",
                side_effect_class="NONE",
                retry_class="SAFE",
                allowed_mode="simulation",
                created_at=self.when,
                updated_at=self.when,
            )
            session.add(row)
            await session.flush()
        return row

    async def agent_run(self, session, job, output):
        definition = (
            await session.scalars(
                select(t.AgentDefinition).where(t.AgentDefinition.agent_id == job.owner_agent_id)
            )
        ).one()
        runtime = AgentRegistry.from_yaml(ROOT).get(job.owner_agent_id)
        prompt = (
            await session.scalars(
                select(t.PromptVersion).where(
                    t.PromptVersion.prompt_reference == runtime.system_prompt_reference
                )
            )
        ).one_or_none()
        if prompt is None:
            matches = tuple(
                (ROOT / "src/money_machine/agents/prompts").glob(job.owner_agent_id + "_*.md")
            )
            if len(matches) != 1:
                raise ValueError("fixture agent source prompt is ambiguous")
            source_path = matches[0].relative_to(ROOT)
            prompt = t.PromptVersion(
                id=self.key("prompt:" + job.owner_agent_id),
                prompt_reference=runtime.system_prompt_reference,
                version=1,
                sha256=sha(matches[0].read_bytes()),
                source_path=str(source_path),
            )
            session.add(prompt)
            await session.flush()
        source = ROOT / prompt.source_path
        if sha(source.read_bytes()) != prompt.sha256:
            raise ValueError("prompt source hash mismatch")
        row = await session.get(t.AgentRun, self.key(job.job_type + ":run"))
        if row is None:
            row = t.AgentRun(
                id=self.key(job.job_type + ":run"),
                job_id=job.id,
                agent_definition_id=definition.id,
                agent_id=definition.agent_id,
                agent_definition_version=definition.contract_version,
                prompt_version_id=prompt.id,
                prompt_reference=prompt.prompt_reference,
                prompt_sha256=prompt.sha256,
                status="SUCCESS",
                output={
                    "execution_kind": "deterministic_fixture_library",
                    "prompt_used": False,
                    **output,
                },
                started_at=self.when,
                completed_at=self.when,
                token_count=0,
                cost_usd=0,
            )
            session.add(row)
            await session.flush()
        return row, prompt, runtime

    async def research(self, session, workflow, job):
        from datetime import timedelta
        from decimal import Decimal

        from money_machine.domain.models.research import (
            CandidateProfile,
            ListingObservation,
            ShopObservation,
            ShortlistAnalysis,
        )

        existing = (
            await session.scalars(select(t.ResearchRun).where(t.ResearchRun.job_id == job.id))
        ).one_or_none()
        if existing is None:
            return await MarketResearchAgent().execute(workflow.id, job, UnitOfWork(session))
        if existing.completed_at is None:
            raise ValueError("incomplete research requires reconciliation; no duplicate collection")
        listings = list(
            (
                await session.scalars(
                    select(t.MarketListingObservation).where(
                        t.MarketListingObservation.research_run_id == existing.id
                    )
                )
            ).all()
        )
        shops = list(
            (
                await session.scalars(
                    select(t.MarketShopObservation).where(
                        t.MarketShopObservation.research_run_id == existing.id
                    )
                )
            ).all()
        )
        candidates = list(
            (
                await session.scalars(
                    select(t.ProductCandidate)
                    .where(t.ProductCandidate.research_run_id == existing.id)
                    .order_by(t.ProductCandidate.created_at, t.ProductCandidate.id)
                )
            ).all()
        )
        profiles: list[CandidateProfile] = []
        for candidate in candidates:
            matching = [
                row
                for row in listings
                if row.identity_niche == candidate.identity
                and row.base_category == candidate.base_category
            ]
            prices = [row.price for row in matching if row.price is not None]
            refs = {row.facts.get("shop_reference") for row in matching}
            related = [row for row in shops if row.shop_reference in refs]
            config = yaml.safe_load((ROOT / "config/research.yaml").read_text())["research"]
            cutoff = existing.completed_at - timedelta(days=config["young_shop_age_days"])
            young = sum(
                1
                for row in related
                if row.shop_opened_on
                and row.shop_opened_on >= cutoff
                and row.shop_sales
                and row.shop_sales >= config["fast_shop_sales_threshold"]
            )
            risks = []
            if not young:
                risks.append("No young-and-fast shops observed")
            if max(prices) > Decimal("15.00"):
                risks.append("High price point may reduce impulse purchases")
            if len(matching) < 5:
                risks.append("Limited market evidence (< 5 observations)")
            profiles.append(
                CandidateProfile(
                    candidate.identity,
                    candidate.base_category,
                    (min(prices), max(prices)),
                    len(matching),
                    len(related),
                    young,
                    "; ".join(risks) if risks else "No significant risks identified",
                )
            )
        profiles.sort(
            key=lambda row: row.observation_count + row.young_fast_shop_count * 2, reverse=True
        )
        return ResearchReport(
            existing.id,
            workflow.id,
            job.id,
            existing.source_policy_version,
            existing.query_terms,
            len(listings),
            len(listings),
            len(shops),
            [
                ListingObservation(
                    row.source_reference,
                    row.title,
                    row.price,
                    row.anchor_price,
                    row.currency,
                    row.identity_niche,
                    row.base_category,
                    row.facts,
                    row.observed_at,
                )
                for row in listings
            ],
            [
                ShopObservation(
                    row.source_reference,
                    row.shop_reference,
                    row.shop_sales,
                    row.shop_opened_on,
                    row.badges,
                    row.observed_at,
                )
                for row in shops
            ],
            ShortlistAnalysis(
                existing.id,
                workflow.id,
                profiles,
                len({row.identity_niche for row in listings}),
                len({row.base_category for row in listings}),
                existing.completed_at,
            ),
            existing.completed_at,
        )

    async def execute(self, url):
        engine = create_async_engine(url)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                database_name = (
                    await session.execute(text("SELECT current_database()"))
                ).scalar_one()
                binding_path = self.directory / "database-binding.json"
                if (
                    binding_path.exists()
                    and json.loads(binding_path.read_text())["database_name"] != database_name
                ):
                    raise ValueError("fixture evidence belongs to another database")
                if not binding_path.exists() and (self.directory / "research.json").exists():
                    raise ValueError("unbound prior evidence must be preserved and reconciled")
                write_json(binding_path, {"database_name": database_name})
                existing = await session.get(t.ListingVersion, self.key("listing-version"))
                if existing is not None:
                    rows = verify_bundle(self.directory)
                    for row in rows:
                        artifact = await session.get(t.Artifact, UUID(row["artifact_id"]))
                        if (
                            artifact is None
                            or artifact.sha256 != row["sha256"]
                            or artifact.byte_size != row["byte_size"]
                        ):
                            raise ValueError("artifact database lineage disagrees")
                    product = await session.get(t.Product, self.key("product"))
                    if product is None:
                        raise ValueError("persisted listing has no fixture product")
                    self.shop_id = product.shop_id
                    ids = self.ids()
                    write_json(self.directory.parent / "ids.json", ids)
                    return ids
                await seed(session, repository_root=ROOT, shop_name="fixture:" + self.run_id)
                shop = (
                    await session.scalars(
                        select(t.Shop).where(t.Shop.name == "fixture:" + self.run_id)
                    )
                ).one()
                self.shop_id = shop.id
                workflow = await session.get(t.WorkflowRun, self.key("workflow"))
                if workflow is None:
                    workflow = t.WorkflowRun(
                        id=self.key("workflow"),
                        shop_id=shop.id,
                        workflow_type="fixture_recovery",
                        workflow_version=1,
                        product_state="DISCOVERED",
                        started_at=self.when,
                    )
                    session.add(workflow)
                    await session.flush()
                await session.commit()
                research_job = await self.job(session, "MarketResearchJob", "A03")
                await session.commit()
                report_path = self.directory / "research.json"
                if report_path.exists():
                    report = TypeAdapter(ResearchReport).validate_json(report_path.read_text())
                else:
                    report = await self.research(session, workflow, research_job)
                    write_json(
                        report_path, TypeAdapter(ResearchReport).dump_python(report, mode="json")
                    )
                research_job.status = "SUCCEEDED"
                await self.agent_run(
                    session,
                    research_job,
                    TypeAdapter(ResearchReport).dump_python(report, mode="json"),
                )
                self.receipt(
                    "research",
                    "money_machine.agents.implementations.market_research.MarketResearchAgent",
                    report.research_run_id,
                    research_job,
                )
                if (
                    report.observation_count < 25
                    or report.observation_count > 40
                    or len(report.shortlist.candidates) != 5
                ):
                    raise ValueError("research shape violated")
                await session.commit()
                if os.environ.get("MONEY_MACHINE_FIXTURE_INTERRUPT_AFTER") == "research":
                    raise RuntimeError("intentional fixture interruption after durable research")
                strategy_job = await self.job(session, "ProductStrategyJob", "A05")
                strategy_run, prompt, definition = await self.agent_run(session, strategy_job, {})
                strategy_input = ProductStrategyInput(
                    job_id=strategy_job.id,
                    workflow_id=workflow.id,
                    research_run_id=report.research_run_id,
                    candidates=tuple(report.shortlist.candidates),
                )
                strategy_job.input = strategy_input.model_dump(mode="json")
                envelope = JobEnvelope(
                    job_id=strategy_job.id,
                    workflow_id=workflow.id,
                    object_id=self.key("product"),
                    job_type=strategy_job.job_type,
                    object_type="products",
                    owner_agent_id="A05",
                    status=JobStatus.RUNNING,
                    input=strategy_job.input,
                    scheduled_at=self.when,
                    attempt=0,
                    max_attempts=3,
                    idempotency_key=strategy_job.idempotency_key,
                    side_effect_class=SideEffectClass.NONE,
                    retry_class=RetryClass.SAFE,
                    success_contract=SuccessContract(output_model="ProductStrategyResult"),
                )
                spec_path = self.directory / "product-spec.json"
                if spec_path.exists():
                    spec = ProductSpec.model_validate_json(spec_path.read_text())
                else:
                    context = AgentContext(
                        envelope,
                        definition,
                        strategy_run.id,
                        (ROOT / prompt.source_path).read_text(),
                        prompt.prompt_reference,
                        prompt.sha256,
                        prompt.version,
                        FakeLLMProvider(),
                        self.when,
                    )
                    result = await A05ProductStrategy().execute(context)
                    if result.status is not AgentRunStatus.SUCCESS:
                        raise ValueError("strategy failed")
                    strategy = ProductStrategyResult.model_validate(result.output, strict=False)
                    if strategy.product_spec is None:
                        raise ValueError("strategy rejected research candidates")
                    # Preserve actual generated concept/prices/hubs/evidence; stable local identity
                    # names this run's first concept. No disconnected fixture ProductSpec.
                    spec = strategy.product_spec.model_copy(
                        update={"spec_id": self.key("spec"), "product_id": self.key("product")}
                    )
                    write_json(spec_path, spec.model_dump(mode="json"))
                    strategy_run.output = result.output
                product = await session.get(t.Product, spec.product_id)
                if product is None:
                    session.add(
                        t.Product(
                            id=spec.product_id,
                            shop_id=shop.id,
                            workflow_id=workflow.id,
                            producing_job_id=strategy_job.id,
                            identity=spec.identity,
                            base_category=spec.base_category,
                            working_title=spec.title,
                            created_at=self.when,
                        )
                    )
                    await session.flush()
                    session.add(
                        t.ProductSpec(
                            id=spec.spec_id,
                            product_id=spec.product_id,
                            workflow_id=workflow.id,
                            version=1,
                            producing_job_id=strategy_job.id,
                            producing_agent_run_id=strategy_run.id,
                            research_run_id=report.research_run_id,
                            identity=spec.identity,
                            base_category=spec.base_category,
                            buyer_problem=spec.buyer_problem,
                            title=spec.title,
                            tier=spec.tier,
                            real_price=spec.real_price,
                            anchor_price=spec.anchor_price,
                            currency=spec.currency,
                            hubs=[hub.model_dump() for hub in spec.hubs],
                            colour_variants=list(spec.colour_variants),
                            features=[spec.flagship_feature],
                            experiment_plan=spec.experiment_hypothesis,
                            concept_fingerprint=spec.concept_fingerprint,
                            rule_version=spec.rule_version,
                            created_at=self.when,
                        )
                    )
                    await session.flush()
                strategy_job.status = "SUCCEEDED"
                self.receipt(
                    "shortlist_score_spec",
                    "money_machine.agents.implementations.product_strategy.A05ProductStrategy",
                    spec.spec_id,
                    strategy_job,
                )
                await session.commit()
                build_job = await self.job(session, "ProductBuildJob", "A07")
                await session.commit()
                probe, built = await build_product(spec, self.directory, self.when)
                request = merchandising_request(spec, built)
                copy = merchandise(request)
                # Synchronous Playwright must run outside this event loop.
                rows, assets = await asyncio.to_thread(
                    render_bundle, spec, probe, built, request, copy, self.directory
                )
                if os.environ.get("MONEY_MACHINE_FIXTURE_INTERRUPT_AFTER") == "render":
                    raise RuntimeError("intentional fixture interruption after durable render")
                await self.persist_delivery(
                    session, shop, workflow, spec, built, request, copy, rows, assets, build_job
                )
                return self.ids()
        finally:
            await engine.dispose()

    def ids(self):
        return dict(
            run_id=self.run_id,
            product_id=str(self.key("product")),
            listing_version_id=str(self.key("listing-version")),
            workflow_id=str(self.key("workflow")),
            shop_id=str(self.shop_id),
        )

    async def persist_delivery(
        self, session, shop, workflow, spec, built, request, copy, rows, assets, build_job
    ):
        await self.agent_run(
            session, build_job, {"qa": asdict(built.qa), "fact_ledger": asdict(built.fact_ledger)}
        )
        session.add(
            t.NotionBuild(
                id=self.key("build"),
                product_id=spec.product_id,
                spec_id=spec.spec_id,
                job_id=build_job.id,
                build_kind="PRIMARY",
                build_version=built.build_version,
                checkpoint_names=list(built.checkpoint_names),
                provider_object_references=json.loads(
                    (self.directory / "build-checkpoint.json").read_text()
                )["provider_object_references"],
                completed_at=self.when,
                created_at=self.when,
            )
        )
        await session.flush()
        session.add(
            t.QaResult(
                id=self.key("qa"),
                build_id=self.key("build"),
                job_id=build_job.id,
                outcome=built.qa.verdict,
                checks=[{"name": name, "passed": passed} for name, passed in built.qa.checks],
                defect_codes=[],
                completed_at=self.when,
            )
        )
        for variant in built.variants:
            session.add(
                t.ProductVariant(
                    id=self.key("variant:" + variant.name),
                    product_id=spec.product_id,
                    spec_id=spec.spec_id,
                    variant_name=variant.name,
                    build_version=built.build_version,
                    duplicate_as_template_enabled=True,
                    search_indexing_disabled=True,
                    links_verified_at=self.when,
                    created_at=self.when,
                )
            )
        for fact in request.facts:
            session.add(
                t.ProductFact(
                    id=fact.fact_id,
                    product_id=spec.product_id,
                    spec_id=spec.spec_id,
                    fact_key=fact.fact_key,
                    fact_value={
                        "value": fact.fact_value,
                        "source": "checked_fixture_ledger_or_explicit_fixture_policy",
                    },
                    verification_job_id=build_job.id,
                    verified_at=self.when,
                )
            )
        build_job.status = "SUCCEEDED"
        self.receipt(
            "notion_build_variants_qa_facts",
            "money_machine.integrations.notion.fixture_adapter.FixtureNotionAdapter",
            self.key("build"),
            build_job,
        )
        asset_job = await self.job(session, "AssetRenderJob", "A11")
        asset_run, _, _ = await self.agent_run(session, asset_job, {"artifacts": rows})
        for row in rows:
            session.add(
                t.Artifact(
                    id=UUID(row["artifact_id"]),
                    logical_role=f"fixture:{self.run_id}:{row['relative_path']}",
                    media_type="image/png"
                    if row["relative_path"].endswith(".png")
                    else "video/mp4"
                    if row["relative_path"].endswith(".mp4")
                    else "application/pdf"
                    if row["relative_path"].endswith(".pdf")
                    else "application/octet-stream",
                    sha256=row["sha256"],
                    byte_size=row["byte_size"],
                    storage_reference=str(self.directory / row["relative_path"]),
                    producing_job_id=asset_job.id,
                    producing_agent_run_id=asset_run.id,
                    retention_class="fixture_evidence",
                    created_at=self.when,
                )
            )
        await session.flush()
        for index, row in enumerate(rows):
            session.add(
                t.Asset(
                    id=self.key("asset:" + row["relative_path"]),
                    product_id=spec.product_id,
                    artifact_id=UUID(row["artifact_id"]),
                    asset_role=row["kind"],
                    ordinal=index,
                    created_at=self.when,
                )
            )
            for parent in row["parent_artifact_ids"]:
                session.add(
                    t.ArtifactLineage(
                        artifact_id=UUID(row["artifact_id"]), parent_artifact_id=UUID(parent)
                    )
                )
        asset_job.status = "SUCCEEDED"
        self.receipt(
            "merchandising_assets",
            "money_machine.agents.implementations.merchandising.merchandise",
            self.key("listing-version"),
            asset_job,
        )
        tags = tuple(tag.text for tag in copy.draft.tags)
        description = "\n\n".join(section.text for section in copy.draft.description_sections)
        if len(tags) != 13 or any(len(tag) > 20 for tag in tags):
            raise ValueError("tag gate failed")
        preflight = run_etsy_preflight(
            EtsyPreflightDraft(
                quantity=request.rules.quantity,
                tags=tags,
                images=tuple(
                    row["relative_path"] for row in rows if row["kind"] == "listing_image"
                ),
                videos=len([row for row in rows if row["kind"] == "walkthrough"]),
                claims=tuple(
                    PreflightClaim(claim.stated_value, str(claim.fact_id))
                    for claim in copy.draft.claims
                ),
            )
        )
        if isinstance(preflight, PreflightBlocked) or preflight.outcome.value != "PASS":
            raise ValueError("preflight refused fixture package")
        verify_bundle(self.directory)
        preflight_job = await self.job(session, "EtsyPreflightJob", "A13")
        await self.agent_run(session, preflight_job, preflight.model_dump(mode="json"))
        preflight_job.status = "SUCCEEDED"
        listing = t.EtsyListing(
            id=self.key("listing"),
            shop_id=shop.id,
            product_id=spec.product_id,
            listing_state="DRAFT",
            created_at=self.when,
        )
        session.add(listing)
        await session.flush()
        package = sha(
            json.dumps(
                {
                    "run_id": self.run_id,
                    "draft": copy.draft.model_dump(mode="json"),
                    "artifacts": rows,
                },
                sort_keys=True,
            ).encode()
        )
        session.add(
            t.ListingVersion(
                id=self.key("listing-version"),
                listing_id=listing.id,
                product_id=spec.product_id,
                spec_id=spec.spec_id,
                producing_job_id=asset_job.id,
                qa_result_id=self.key("qa"),
                listing_version=1,
                title=copy.draft.title.text,
                description_sections=[
                    section.model_dump(mode="json") for section in copy.draft.description_sections
                ],
                tags=list(tags),
                currency=spec.currency,
                price=spec.real_price,
                anchor_price=spec.anchor_price,
                quantity=request.rules.quantity,
                rule_version=request.rules.rule_version,
                package_sha256=package,
                created_at=self.when,
            )
        )
        await session.flush()
        session.add(
            t.PreflightResult(
                id=self.key("preflight"),
                listing_version_id=self.key("listing-version"),
                job_id=preflight_job.id,
                outcome="PASS",
                listing_package_sha256=package,
                checks=[check.model_dump(mode="json") for check in preflight.checks],
                repair_job_types=[],
                completed_at=self.when,
            )
        )
        self.receipt(
            "preflight",
            "money_machine.assets.etsy_preflight.run_etsy_preflight",
            self.key("preflight"),
            preflight_job,
        )
        numeric = int(self.namespace.hex[:13], 16) + 1
        (self.directory / "draft-ledger").mkdir(exist_ok=True)
        transport = FixtureDraftTransport(self.directory, numeric)
        evidence = DraftEvidence(
            product_id=spec.product_id,
            spec_version=spec.version,
            shop_id=numeric,
            product_qa="passed",
            claims_passed=True,
            assets=assets,
            pdf_roles=("readme", "free_gift"),
            links_passed=True,
            title=copy.draft.title.text,
            description=description,
            price=str(spec.real_price),
            quantity=request.rules.quantity,
            who_made="i_did",
            when_made="2020_2026",
            taxonomy_id=2078,
        )
        receipt = await create_ready_draft_listing_job(
            evidence,
            EtsyDraftClient(transport, DraftLedger(self.directory / "draft-ledger")),
            UnitOfWork(session),
            workflow_id=workflow.id,
            occurred_at=self.when,
        )
        if os.environ.get("MONEY_MACHINE_FIXTURE_INTERRUPT_AFTER") == "draft":
            raise RuntimeError("intentional fixture interruption after durable draft")
        listing.provider_listing_id = str(receipt.listing_id)
        self.receipt(
            "fixture_etsy_draft",
            "money_machine.application.fixture_run.FixtureDraftTransport",
            receipt.listing_id,
        )
        negative = run_etsy_preflight(
            EtsyPreflightDraft(
                quantity=request.rules.quantity,
                tags=tags,
                images=tuple(str(index) for index in range(10)),
                videos=1,
                claims=(PreflightClaim("Unsupported fixture claim", None),),
            )
        )
        if not isinstance(negative, PreflightBlocked):
            raise ValueError("expected negative did not block")
        blocked = await self.job(session, "ExpectedFixtureNegativeJob", "A13")
        blocked.status = "BLOCKED"
        blocked.input = {
            "mode": "fixture",
            "reason": "Expected fixture negative: unsupported claim has no fact reference",
        }
        session.add(
            t.Incident(
                id=self.key("incident"),
                shop_id=shop.id,
                incident_type="LISTING_DEFECT",
                affected_object_type="listing_versions",
                affected_object_id=self.key("listing-version"),
                workflow_id=workflow.id,
                listing_version_id=self.key("listing-version"),
                opened_by_job_id=blocked.id,
                safe_detail={"reason": blocked.input["reason"]},
                opened_at=self.when,
            )
        )
        session.add(
            t.Decision(
                id=self.key("decision"),
                workflow_id=workflow.id,
                job_id=blocked.id,
                decision_type="EXPECTED_FIXTURE_NEGATIVE",
                branch_outcome="FAIL",
                product_id=spec.product_id,
                listing_id=listing.id,
                rule_version=request.rules.rule_version,
                explanation=blocked.input["reason"],
                decided_at=self.when,
            )
        )
        await session.flush()
        proof = next(row for row in rows if row["kind"] == "product_structure")
        session.add(
            t.DecisionEvidence(
                decision_id=self.key("decision"),
                evidence_type="fixture_negative",
                source_reference=str(self.directory / "receipts.jsonl"),
                artifact_id=UUID(proof["artifact_id"]),
                observed_at=self.when,
            )
        )
        session.add(
            t.IntegrationAccount(
                id=self.key("integration"),
                shop_id=shop.id,
                provider="fixture",
                capability_channel="INTERNAL_RENDERER",
                connection_state="UNCONNECTED",
                credential_present=False,
                blocker_code="FIXTURE_ONLY",
                safe_detail={"mode": "fixture", "reason": "No live provider connection"},
                checked_at=self.when,
                created_at=self.when,
            )
        )
        self.receipt(
            "expected_negative",
            "money_machine.assets.etsy_preflight.run_etsy_preflight",
            self.key("decision"),
            blocked,
        )
        await session.commit()
        write_json(self.directory.parent / "ids.json", self.ids())


def run_fixture() -> int:
    if os.environ.get("APP_ENV") != "test":
        raise ValueError("fixture command requires APP_ENV=test")
    if os.environ.get("MONEY_MACHINE_EFFECT_MODE", "simulation") not in {"fixture", "simulation"}:
        raise ValueError("fixture command refuses live/provider mode")
    run_id = os.environ.get("MONEY_MACHINE_RUN_ID", "fixture-local")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id) is None:
        raise ValueError("invalid fixture run id")
    url = os.environ.get("MONEY_MACHINE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("explicit fixture database URL required")
    run = FixtureRun(
        run_id, Path(os.environ.get("MONEY_MACHINE_EVIDENCE_ROOT", ".runtime/fixture-evidence"))
    )
    print(json.dumps(asyncio.run(run.execute(url)), sort_keys=True))
    return 0
