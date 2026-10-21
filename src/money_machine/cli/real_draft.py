"""Explicit D-0039 operator-assisted private build; no publishing or paid calls."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import stat
import subprocess
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from notion_client import AsyncClient
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from money_machine.application.real_draft_authority import DraftRunAuthority, DraftRunRefused
from money_machine.application.real_notion_build import RealNotionProductBuilder
from money_machine.domain.enums import AgentRunStatus, JobStatus
from money_machine.domain.models.product_spec import ProductSpec as Spec
from money_machine.orchestration.transition_guard import require_job_transition
from money_machine.persistence.tables import (
    AgentDefinition,
    AgentRun,
    Job,
    MarketListingObservation,
    Product,
    ProductCandidate,
    ProductSpec,
    PromptVersion,
    ResearchRun,
    Shop,
    WorkflowRun,
)

ROOT = Path("/srv/work/money-machine")
APPROVAL_FILE = Path("/srv/work/state/real-draft-approval.json")
ACTIVE_RUN_FILE = Path("/srv/work/state/active-real-draft-run-id")
ALLOWED_DATABASE = "mm_verified_20261020t211445z"


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def validate_database_url(url: str) -> None:
    try:
        u = make_url(url)
    except Exception:
        raise DraftRunRefused("database_scope") from None
    if (
        u.drivername != "postgresql+asyncpg"
        or u.host != "127.0.0.1"
        or u.port != 55432
        or u.database != ALLOWED_DATABASE
        or u.query
    ):
        raise DraftRunRefused("database_scope")


def read_private_credential(path: Path) -> str:
    """Validate ownership and mode on the same no-follow descriptor that is read."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise DraftRunRefused("private_credential_file_required") from None
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.getuid()
        ):
            raise DraftRunRefused("private_credential_file_required")
        with os.fdopen(fd, "r", closefd=False) as source:
            return source.read().strip()
    finally:
        os.close(fd)


def preflight(
    *, spec_path: Path, run_id: str, workspace_id: UUID, expected_head: str, root: Path = ROOT
) -> Spec:
    if root.resolve() != ROOT or _git(root, "rev-parse", "--show-toplevel") != str(ROOT):
        raise DraftRunRefused("canonical_root_required")
    if _git(root, "rev-parse", "HEAD") != expected_head:
        raise DraftRunRefused("expected_head_mismatch")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise DraftRunRefused("reviewed_clean_worktree_required")
    state = json.loads((root / "docs/control/IMPLEMENTATION_STATE.json").read_text())
    if (
        state["repo_root"] != str(ROOT)
        or state["branch"] != "build/full-automation"
        or _git(root, "branch", "--show-current") != state["branch"]
        or state["state_revision"] != 65
        or state["current_session"] != 7
        or state["session_status"] != "incomplete"
        or any(state["required_completion_evidence"].values())
        or state["commissioned_agents"]
    ):
        raise DraftRunRefused("audited_control_recovery_required")
    from money_machine.control.recovery import verify_recovery_authority

    verify_recovery_authority(root)
    spec = Spec.model_validate_json(spec_path.read_text())
    # Operator-owned scope metadata is kept outside Git with the active run checkpoint.
    # It binds this reusable implementation to ONE approved product, not a new workflow engine.
    info = APPROVAL_FILE.lstat()
    if (
        APPROVAL_FILE.is_symlink()
        or not stat.S_ISREG(info.st_mode)
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_uid != os.getuid()
    ):
        raise DraftRunRefused("private_run_approval_required")
    approved = json.loads(APPROVAL_FILE.read_text())
    digest = hashlib.sha256(spec.model_dump_json().encode()).hexdigest()
    if (
        ACTIVE_RUN_FILE.read_text().strip() != run_id
        or approved.get("run_id") != run_id
        or approved.get("product_id") != str(spec.product_id)
        or approved.get("spec_sha256") != digest
    ):
        raise DraftRunRefused("one_approved_product_required")
    if (
        not run_id
        or len(run_id) > 80
        or any(
            c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
            for c in run_id
        )
    ):
        raise DraftRunRefused("run_id_scope")
    if str(workspace_id) != "e3696df7-ed66-811f-97fc-00038e866626":
        raise DraftRunRefused("verified_workspace_required")
    if (
        spec.currency != "GBP"
        or spec.real_price != Decimal("7.50")
        or spec.anchor_price != spec.real_price
    ):
        raise DraftRunRefused("approved_product_price_scope")
    return spec


def _uid(run_id: str, kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, "money-machine:" + run_id + ":real:" + kind)


async def prepare_run(
    session: AsyncSession,
    spec: Spec,
    authority: DraftRunAuthority,
    *,
    research: dict[str, Any],
    shortlist: dict[str, Any],
) -> UUID:
    if spec.product_id != authority.product_id:
        raise DraftRunRefused("product_authority_mismatch")
    evidence_digest = hashlib.sha256(
        json.dumps({"research": research, "shortlist": shortlist}, sort_keys=True).encode()
    ).hexdigest()
    spec_json = spec.model_dump(mode="json")
    digest = hashlib.sha256(spec.model_dump_json().encode()).hexdigest()
    build_id = _uid(authority.run_id, "build-job")
    existing = await session.get(ProductSpec, spec.spec_id)
    if existing:
        run = await session.get(AgentRun, spec.producing_agent_run_id)
        job = await session.get(Job, build_id)
        if (
            existing.product_id != spec.product_id
            or existing.workflow_id != spec.workflow_id
            or run is None
            or run.input_hash != digest
            or job is None
            or job.input.get("run_id") != authority.run_id
            or job.input.get("evidence_sha256") != evidence_digest
        ):
            raise DraftRunRefused("existing_product_spec_mismatch")
        return build_id
    if (
        research.get("run_id") != authority.run_id
        or shortlist.get("run_id") != authority.run_id
        or len(research.get("rows", [])) != 36
        or len(shortlist.get("shortlist", [])) != 5
    ):
        raise DraftRunRefused("actual_research_and_shortlist_required")
    if spec.research_run_id is None:
        raise DraftRunRefused("research_lineage_required")
    now = datetime.now(UTC)
    shop = await session.scalar(select(Shop).where(Shop.name == authority.shop_name))
    if shop is None:
        shop = Shop(name=authority.shop_name, connection_state="UNCONNECTED", timezone="UTC")
        session.add(shop)
        await session.flush()
    workflow = await session.get(WorkflowRun, spec.workflow_id)
    if workflow is None:
        workflow = WorkflowRun(
            id=spec.workflow_id,
            shop_id=shop.id,
            workflow_type="RealProductDraft:" + authority.run_id,
            workflow_version=1,
            product_state="DISCOVERED",
        )
        session.add(workflow)
        await session.flush()
    if (
        workflow.shop_id != shop.id
        or workflow.workflow_type != "RealProductDraft:" + authority.run_id
    ):
        raise DraftRunRefused("workflow_scope")
    research_job_id = _uid(authority.run_id, "research-job")
    for jid, kind, agent, status, effect in [
        (research_job_id, "MarketResearchJob", "A03", "SUCCEEDED", "EXTERNAL_READ"),
        (spec.producing_job_id, "ProductStrategyJob", "A05", "SUCCEEDED", "EXTERNAL_READ"),
        (build_id, "RealProductBuild", "A07", "READY", "EXTERNAL_WRITE"),
    ]:
        if await session.get(Job, jid) is not None:
            raise DraftRunRefused("partial_job_lineage_conflict")
        session.add(
            Job(
                id=jid,
                workflow_id=spec.workflow_id,
                job_type=kind,
                object_type="Product",
                object_id=spec.product_id,
                owner_agent_id=agent,
                status=status,
                input={
                    "run_id": authority.run_id,
                    "spec_sha256": digest,
                    "evidence_sha256": evidence_digest,
                    "execution_kind": "operator_assisted_codex_session",
                    "publish_enabled": False,
                    "spend_enabled": False,
                },
                success_contract={"scope": "D-0039 private product and Etsy draft only"},
                scheduled_at=now,
                idempotency_key="real:" + authority.run_id + ":" + kind,
                side_effect_class=effect,
                retry_class="RECONCILE_FIRST" if effect == "EXTERNAL_WRITE" else "SAFE",
                allowed_mode="draft",
            )
        )
    await session.flush()
    session.add(
        ResearchRun(
            id=spec.research_run_id,
            workflow_id=spec.workflow_id,
            job_id=research_job_id,
            source_policy_version="real-public-browser-v1",
            query_terms=[research.get("query", "")],
            observation_count=36,
            completed_at=now,
        )
    )
    await session.flush()
    for row in research["rows"]:
        session.add(
            MarketListingObservation(
                research_run_id=spec.research_run_id,
                source_reference=row["source_url"],
                title=row["title_observation"],
                price=Decimal(row["displayed_price_gbp"]),
                anchor_price=None,
                currency="GBP",
                identity_niche=None,
                base_category="Notion Planner",
                facts={
                    "provenance": "real_public_browser",
                    "sales_verified": False,
                    "shop_age_verified": False,
                },
                observed_at=datetime.fromisoformat(row["observed_at"]),
            )
        )
    for row in shortlist["shortlist"]:
        scores = row["scores"]
        if (
            len(scores) != 4
            or sum(scores) != row["total"]
            or not all(type(x) is int and 0 <= x <= 10 for x in scores)
        ):
            raise DraftRunRefused("scoring_evidence_invalid")
        session.add(
            ProductCandidate(
                workflow_id=spec.workflow_id,
                research_run_id=spec.research_run_id,
                identity=row["identity"],
                base_category=row["category"],
                impulse_priced_score=scores[0],
                tangible_score=scores[1],
                honest_promise_score=scores[2],
                trendy_but_tricky_score=scores[3],
                total_score=row["total"],
                maximum_score=40,
                selection=row["selection"],
            )
        )
    definition = await session.scalar(
        select(AgentDefinition)
        .where(AgentDefinition.agent_id == "A05")
        .order_by(AgentDefinition.contract_version.desc())
        .limit(1)
    )
    prompt = await session.scalar(
        select(PromptVersion)
        .where(PromptVersion.prompt_reference == "agent://A05/system/v1")
        .order_by(PromptVersion.version.desc())
        .limit(1)
    )
    if definition is None or prompt is None:
        raise DraftRunRefused("registered_strategy_metadata_required")
    session.add(
        AgentRun(
            id=spec.producing_agent_run_id,
            job_id=spec.producing_job_id,
            agent_definition_id=definition.id,
            agent_id="A05",
            agent_definition_version=definition.contract_version,
            prompt_version_id=prompt.id,
            prompt_reference=prompt.prompt_reference,
            prompt_sha256=prompt.sha256,
            model=None,
            input_hash=digest,
            token_count=None,
            cost_usd=None,
            status=AgentRunStatus.SUCCESS.value,
            output={
                "execution_kind": "operator_assisted_codex_session",
                "prompt_used": False,
                "spec_sha256": digest,
                "paid_llm_calls": 0,
            },
            error=None,
            started_at=spec.created_at,
            completed_at=spec.created_at,
        )
    )
    await session.flush()
    session.add(
        Product(
            id=spec.product_id,
            shop_id=shop.id,
            workflow_id=spec.workflow_id,
            producing_job_id=spec.producing_job_id,
            identity=spec.identity,
            base_category=spec.base_category,
            working_title=spec.title,
        )
    )
    await session.flush()
    session.add(
        ProductSpec(
            id=spec.spec_id,
            product_id=spec.product_id,
            workflow_id=spec.workflow_id,
            version=spec.version,
            producing_job_id=spec.producing_job_id,
            producing_agent_run_id=spec.producing_agent_run_id,
            research_run_id=spec.research_run_id,
            lineage_kind="ORIGINAL",
            identity=spec.identity,
            base_category=spec.base_category,
            buyer_problem=spec.buyer_problem,
            title=spec.title,
            tier=spec.tier,
            real_price=spec.real_price,
            anchor_price=spec.anchor_price,
            currency=spec.currency,
            hubs=spec_json["hubs"],
            colour_variants=spec_json["colour_variants"],
            features=[
                {
                    "flagship_feature": spec.flagship_feature,
                    "feature_targets": spec_json["feature_targets"],
                    "palette_name": spec.palette_name,
                    "palette_tokens": spec_json["palette_tokens"],
                }
            ],
            experiment_plan=spec.experiment_hypothesis,
            concept_fingerprint=spec.concept_fingerprint,
            rule_version=spec.rule_version,
        )
    )
    await session.flush()
    return build_id


async def claim_build_job(
    session: AsyncSession, job_id: UUID, authority: DraftRunAuthority, *, owner: str, now: datetime
) -> Job:
    job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if (
        job is None
        or job.object_id != authority.product_id
        or job.input.get("run_id") != authority.run_id
        or job.allowed_mode != "draft"
        or job.side_effect_class != "EXTERNAL_WRITE"
    ):
        raise DraftRunRefused("build_job_scope")
    shop_name = await session.scalar(
        select(Shop.name)
        .join(WorkflowRun, WorkflowRun.shop_id == Shop.id)
        .where(WorkflowRun.id == job.workflow_id)
    )
    if shop_name != authority.shop_name:
        raise DraftRunRefused("build_job_shop_scope")
    if job.status == "RUNNING" and job.lease_expires_at is not None and job.lease_expires_at > now:
        raise DraftRunRefused("active_job_owner")
    if job.status == "READY":
        require_job_transition(JobStatus.READY, JobStatus.RUNNING)
    elif job.status != "RUNNING":
        raise DraftRunRefused("build_job_not_claimable")
    job.status = "RUNNING"
    job.lease_owner = owner
    job.lease_expires_at = now + timedelta(hours=2)
    job.heartbeat_at = now
    job.updated_at = now
    await session.flush()
    return job


@asynccontextmanager
async def private_notion_client(
    token: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> AsyncGenerator[AsyncClient, None]:
    """Own the paced transport; notion-client2.7.0 context entry replaces clients."""
    last_request = 0.0

    async def pace(_request: httpx.Request) -> None:
        nonlocal last_request
        await asyncio.sleep(max(0.0, 0.4 - (time.monotonic() - last_request)))
        last_request = time.monotonic()

    async with httpx.AsyncClient(
        event_hooks={"request": [pace]},
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        transport=transport,
    ) as http:
        # SDK2.7.0 __aenter__ creates a fresh HTTP client and discards the injected hooks.
        sdk = AsyncClient(auth=token, notion_version="2025-09-03", client=http, timeout_ms=20000)
        yield sdk


async def execute(args: argparse.Namespace, spec: Spec) -> dict[str, Any]:
    url = os.environ.get("MONEY_MACHINE_DATABASE_URL", "")
    validate_database_url(url)
    evidence = Path(args.evidence_root).resolve()
    if (
        evidence != Path("/srv/work/evidence") / args.run_id
        or Path(args.evidence_root).is_symlink()
    ):
        raise DraftRunRefused("evidence_root_scope")
    token = read_private_credential(Path(args.credential_file))
    authority = DraftRunAuthority(
        run_id=args.run_id,
        product_id=spec.product_id,
        verified_notion_parent_id=UUID(args.workspace_id),
    )
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owner = (
        "real-draft:" + str(os.getpid()) + ":" + uuid5(NAMESPACE_URL, str(time.time_ns())).hex[:12]
    )
    job_id = None
    try:
        async with private_notion_client(token) as sdk:
            me = await sdk.users.me()
            bot = me.get("bot", {})
            if (
                bot.get("workspace_id") != args.workspace_id
                or bot.get("owner", {}).get("type") != "user"
            ):
                raise DraftRunRefused("notion_workspace_identity_mismatch")
            research = json.loads(Path(args.research).read_text())
            shortlist = json.loads(Path(args.shortlist).read_text())
            async with factory() as session, session.begin():
                job_id = await prepare_run(
                    session, spec, authority, research=research, shortlist=shortlist
                )
                await claim_build_job(
                    session, job_id, authority, owner=owner, now=datetime.now(UTC)
                )
            builder = RealNotionProductBuilder(
                authority, sdk=sdk, session_factory=factory, job_id=job_id, lease_owner=owner
            )
            manifest = await builder.build(
                spec, run_id=args.run_id, workspace_id=UUID(args.workspace_id)
            )
            if (
                manifest.get("qa") != "provider_readback_checked"
                or manifest.get("publication") != "private"
            ):
                raise DraftRunRefused("real_build_readback_required")
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            path = evidence / ("real-notion-build-" + stamp + ".json")
            with path.open("x", encoding="utf-8") as output:
                output.write(
                    json.dumps(
                        {
                            **manifest,
                            "source_head": args.expected_head,
                            "recorded_at": datetime.now(UTC).isoformat(),
                            "workflow_complete": False,
                            "etsy_draft_verified": False,
                        },
                        indent=2,
                    )
                    + "\n"
                )
                output.flush()
                os.fsync(output.fileno())
            directory_fd = os.open(evidence, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            from money_machine.orchestration.leases import release_lease

            async with factory() as session, session.begin():
                await release_lease(
                    session,
                    job_id=job_id,
                    worker_id=owner,
                    final_status=JobStatus.SUCCEEDED,
                    now=datetime.now(UTC),
                )
            return {
                "run_id": args.run_id,
                "manifest_path": str(path),
                "private_folder_id": manifest["private_folder_id"],
                "notion_build_verified": True,
                "workflow_complete": False,
                "etsy_draft_verified": False,
            }
    finally:
        if job_id is not None:
            async with factory() as session, session.begin():
                job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
                if job is not None and job.status == "RUNNING" and job.lease_owner == owner:
                    job.lease_expires_at = datetime.now(UTC)
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "spec",
        "run-id",
        "workspace-id",
        "credential-file",
        "evidence-root",
        "expected-head",
    ):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--research")
    parser.add_argument("--shortlist")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        spec = preflight(
            spec_path=Path(args.spec),
            run_id=args.run_id,
            workspace_id=UUID(args.workspace_id),
            expected_head=args.expected_head,
        )
        if not args.execute:
            print(
                json.dumps(
                    {
                        "run_id": args.run_id,
                        "preflight": "passed",
                        "effects_performed": False,
                        "publishing_enabled": False,
                        "spending_enabled": False,
                    }
                )
            )
            return 0
        if not args.research or not args.shortlist:
            raise DraftRunRefused("actual_research_and_shortlist_required")
        print(json.dumps(asyncio.run(execute(args, spec)), sort_keys=True))
        return 0
    except DraftRunRefused as exc:
        print(json.dumps({"run_id": args.run_id, "status": "refused", "reason": str(exc)}))
        return 78
    except Exception:
        print(
            json.dumps(
                {
                    "run_id": args.run_id,
                    "status": "failed_or_uncertain",
                    "reason": "inspect_private_operation_evidence_no_secret_output",
                }
            )
        )
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
