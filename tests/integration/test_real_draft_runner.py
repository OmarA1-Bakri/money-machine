from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from money_machine.application.real_draft_authority import DraftRunAuthority, DraftRunRefused
from money_machine.cli.real_draft import claim_build_job, main, validate_database_url
from money_machine.persistence.tables import Job, Shop, WorkflowRun


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u@127.0.0.1:5432/mm_verified_20261020t211445z",
        "postgresql+asyncpg://u@localhost:55432/mm_verified_20261020t211445z",
        "postgresql+asyncpg://u@127.0.0.1:55432/other",
        "postgresql+asyncpg://u@127.0.0.1:55432/mm_verified_20261020t211445z?host=evil",
    ],
)
def test_wrong_database_refused(url):
    with pytest.raises(DraftRunRefused):
        validate_database_url(url)


def test_exact_database_allowed():
    validate_database_url("postgresql+asyncpg://u@127.0.0.1:55432/mm_verified_20261020t211445z")


def test_dry_run_never_reads_credentials_or_database(monkeypatch, tmp_path):
    import money_machine.cli.real_draft as module

    def checked_preflight(**_kwargs: object) -> dict[str, str]:
        return {"product_id": "checked"}

    def forbidden_execute(*_args: object, **_kwargs: object) -> None:
        pytest.fail("execute called")

    monkeypatch.setattr(module, "preflight", checked_preflight)
    monkeypatch.setattr(module, "execute", forbidden_execute)
    assert (
        main(
            [
                "--spec",
                str(tmp_path / "spec"),
                "--run-id",
                "x",
                "--workspace-id",
                str(uuid4()),
                "--credential-file",
                "/must/not/read",
                "--evidence-root",
                str(tmp_path),
                "--expected-head",
                "a" * 40,
            ]
        )
        == 0
    )


async def own_jobs(factory):
    now = datetime.now(UTC)
    product = uuid4()
    authority = DraftRunAuthority(run_id="runner-test", product_id=product)
    async with factory() as s, s.begin():
        shop = Shop(name="QuietlyBuiltStudio")
        s.add(shop)
        await s.flush()
        workflow = WorkflowRun(
            shop_id=shop.id, workflow_type="RealProductDraft:runner-test", workflow_version=1
        )
        s.add(workflow)
        await s.flush()
        jobs = []
        for index in range(2):
            job = Job(
                workflow_id=workflow.id,
                job_type="RealProductBuild",
                object_type="Product",
                object_id=product if index == 0 else uuid4(),
                owner_agent_id="A07",
                status="READY",
                input={"run_id": authority.run_id},
                scheduled_at=now,
                idempotency_key=str(uuid4()),
                side_effect_class="EXTERNAL_WRITE",
                retry_class="RECONCILE_FIRST",
                allowed_mode="draft",
            )
            s.add(job)
            await s.flush()
            jobs.append(job.id)
    return authority, jobs


@pytest.mark.asyncio
async def test_claim_only_own_job_and_refuse_active_owner(session_factory):
    authority, (own, other) = await own_jobs(session_factory)
    now = datetime.now(UTC)
    async with session_factory() as s, s.begin():
        await claim_build_job(s, own, authority, owner="one", now=now)
    async with session_factory() as s, s.begin():
        with pytest.raises(DraftRunRefused, match="active_job_owner"):
            await claim_build_job(s, own, authority, owner="two", now=now)
    async with session_factory() as s:
        untouched = await s.get(Job, other)
        assert untouched.status == "READY" and untouched.lease_owner is None
        held = await s.get(Job, own)
        assert held.lease_owner == "one"
        assert held.lease_expires_at == now + timedelta(hours=2)


@pytest.mark.asyncio
async def test_claim_wrong_scope_refused(session_factory):
    authority, (_, other) = await own_jobs(session_factory)
    async with session_factory() as s, s.begin():
        with pytest.raises(DraftRunRefused, match="build_job_scope"):
            await claim_build_job(s, other, authority, owner="one", now=datetime.now(UTC))
    async with session_factory() as s:
        assert await s.scalar(select(Job.status).where(Job.id == other)) == "READY"


@pytest.fixture
def runner_inputs():
    from decimal import Decimal
    from typing import Any

    from money_machine.domain.models.common import EvidenceReference
    from money_machine.domain.models.product_spec import ColourToken, Hub
    from money_machine.domain.models.product_spec import ProductSpec as Spec

    now = datetime.now(UTC)
    product = uuid4()
    authority = DraftRunAuthority(run_id="prepare-test", product_id=product)
    spec = Spec(
        spec_id=uuid4(),
        product_id=product,
        workflow_id=uuid4(),
        version=1,
        producing_job_id=uuid4(),
        producing_agent_run_id=uuid4(),
        research_run_id=uuid4(),
        identity="Test planner",
        base_category="Notion Planner",
        buyer_problem="Plan the week",
        title="Test Money and Life Planner",
        tier="low-ticket",
        real_price=Decimal("7.50"),
        anchor_price=Decimal("7.50"),
        currency="GBP",
        palette_name="Test",
        palette_tokens=tuple(
            ColourToken(name=n, hex=h)
            for n, h in (("Forest", "#2F5D50"), ("Sand", "#C8B89D"), ("Slate", "#64748B"))
        ),
        hubs=tuple(
            Hub(name=n, description="Planning", page_count=3)
            for n in ("Daily Plan", "Calendar", "Routines", "Money", "Meals", "Notes")
        ),
        colour_variants=("Forest", "Sand", "Slate"),
        flagship_feature="Connected overview",
        shared_databases=("Tasks", "Events", "Habits", "Finance", "Meals", "Notes"),
        page_target_min=25,
        page_target_max=100,
        experiment_hypothesis="Test planning",
        concept_fingerprint="a" * 64,
        rule_version="test-v1",
        evidence=(
            EvidenceReference(
                evidence_id=uuid4(),
                evidence_type="TEST_ONLY",
                source_reference="test-only",
                observed_at=now,
                sha256="b" * 64,
                safe_summary="Test",
            ),
        ),
        created_at=now,
    )
    research: dict[str, Any] = {
        "run_id": authority.run_id,
        "query": "test",
        "rows": [
            {
                "source_url": f"https://example.invalid/listing/{i}",
                "title_observation": f"Test {i}",
                "displayed_price_gbp": "7.50",
                "observed_at": now.isoformat(),
            }
            for i in range(36)
        ],
    }
    shortlist: dict[str, Any] = {
        "run_id": authority.run_id,
        "shortlist": [
            {
                "identity": f"Candidate {i}",
                "category": "Notion Planner",
                "scores": [8, 8, 8, 8],
                "total": 32,
                "selection": "PRIMARY" if i == 0 else "BACKUP" if i == 1 else "REJECTED",
            }
            for i in range(5)
        ],
    }
    return spec, authority, research, shortlist


@pytest.mark.asyncio
async def test_prepare_run_persists_real_lineage_and_replays_without_duplicates(
    session_factory, runner_inputs
):
    from sqlalchemy import func

    from money_machine.cli.real_draft import prepare_run
    from money_machine.persistence.tables import (
        AgentDefinition,
        AgentRun,
        MarketListingObservation,
        Product,
        ProductCandidate,
        ProductSpec,
        PromptVersion,
        ResearchRun,
    )

    spec, authority, research, shortlist = runner_inputs
    async with session_factory() as session, session.begin():
        session.add(
            AgentDefinition(
                agent_id="A05",
                name="Test",
                implementation_version=1,
                contract_version=1,
                default_side_effect_class="EXTERNAL_READ",
                default_retry_class="SAFE",
                timeout_seconds=600,
                commissioning_state="DESIGNED",
                commissioning_evidence=[],
            )
        )
        session.add(
            PromptVersion(
                prompt_reference="agent://A05/system/v1",
                version=1,
                sha256="c" * 64,
                source_path="test-only",
            )
        )
    async with session_factory() as session, session.begin():
        job_id = await prepare_run(session, spec, authority, research=research, shortlist=shortlist)
    async with session_factory() as session, session.begin():
        assert (
            await prepare_run(session, spec, authority, research=research, shortlist=shortlist)
            == job_id
        )
        for table, count in (
            (Job, 3),
            (Product, 1),
            (ProductSpec, 1),
            (ResearchRun, 1),
            (MarketListingObservation, 36),
            (ProductCandidate, 5),
            (AgentRun, 1),
        ):
            assert await session.scalar(select(func.count()).select_from(table)) == count
        run = await session.get(AgentRun, spec.producing_agent_run_id)
        assert run is not None and run.status == "SUCCESS"
        assert run.model is None and run.cost_usd is None and run.token_count is None
        assert run.output["prompt_used"] is False and run.output["paid_llm_calls"] == 0
        workflow = await session.get(WorkflowRun, spec.workflow_id)
        assert workflow is not None and workflow.completed_at is None
        job = await session.get(Job, job_id)
        assert job is not None and job.status == "READY" and job.allowed_mode == "draft"
        assert job.input["publish_enabled"] is False and job.input["spend_enabled"] is False

        changed = spec.model_copy(update={"title": "Changed title"})
        with pytest.raises(DraftRunRefused, match="existing_product_spec_mismatch"):
            await prepare_run(session, changed, authority, research=research, shortlist=shortlist)
        with pytest.raises(DraftRunRefused, match="existing_product_spec_mismatch"):
            await prepare_run(
                session,
                spec,
                authority,
                research={**research, "query": "changed"},
                shortlist=shortlist,
            )
        wrong_authority = DraftRunAuthority(run_id=authority.run_id, product_id=uuid4())
        with pytest.raises(DraftRunRefused, match="product_authority_mismatch"):
            await prepare_run(
                session, spec, wrong_authority, research=research, shortlist=shortlist
            )


@pytest.mark.parametrize("violation", ["clean", "tracked", "untracked", "run", "product", "spec"])
def test_preflight_binds_clean_reviewed_tree_and_one_approved_product(
    monkeypatch, tmp_path, runner_inputs, violation
):
    import hashlib
    import json

    import money_machine.cli.real_draft as module
    import money_machine.control.recovery as recovery

    spec, authority, _, _ = runner_inputs
    control = tmp_path / "docs/control"
    control.mkdir(parents=True)
    (control / "IMPLEMENTATION_STATE.json").write_text(
        json.dumps(
            {
                "repo_root": str(tmp_path),
                "branch": "build/full-automation",
                "state_revision": 65,
                "current_session": 7,
                "session_status": "incomplete",
                "required_completion_evidence": {str(i): False for i in range(12)},
                "commissioned_agents": [],
            }
        )
    )
    approved = tmp_path / "approval.json"
    active = tmp_path / "active-run"
    active.write_text(authority.run_id)
    approved.write_text(
        json.dumps(
            {
                "run_id": authority.run_id,
                "product_id": str(spec.product_id),
                "spec_sha256": hashlib.sha256(spec.model_dump_json().encode()).hexdigest(),
            }
        )
    )
    approved.chmod(0o600)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(spec.model_dump_json())
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "APPROVAL_FILE", approved, raising=False)
    monkeypatch.setattr(module, "ACTIVE_RUN_FILE", active, raising=False)

    def fake_git(_root: object, *arguments: str) -> str:
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(tmp_path)
        if arguments == ("rev-parse", "HEAD"):
            return "a" * 40
        if arguments == ("branch", "--show-current"):
            return "build/full-automation"
        if arguments[0] == "status":
            return (
                " M src/changed.py"
                if violation == "tracked"
                else ("?? src/injected.py" if violation == "untracked" else "")
            )
        raise AssertionError(arguments)

    def authority_checked(_root: object) -> None:
        pass

    monkeypatch.setattr(module, "_git", fake_git)
    monkeypatch.setattr(recovery, "verify_recovery_authority", authority_checked)
    run_id = authority.run_id
    if violation == "run":
        run_id += "-second"
    if violation == "product":
        spec_path.write_text(spec.model_copy(update={"product_id": uuid4()}).model_dump_json())
    if violation == "spec":
        spec_path.write_text(
            spec.model_copy(update={"title": "Different product"}).model_dump_json()
        )

    def launch_preflight():
        return module.preflight(
            spec_path=spec_path,
            run_id=run_id,
            workspace_id=module.UUID("e3696df7-ed66-811f-97fc-00038e866626"),
            expected_head="a" * 40,
            root=tmp_path,
        )

    if violation == "clean":
        assert launch_preflight() == spec
    else:
        with pytest.raises(DraftRunRefused):
            launch_preflight()


@pytest.mark.parametrize(
    "case", ["valid", "foreign_owner", "world_readable", "symlink", "directory"]
)
def test_credential_requires_owned_private_regular_file(monkeypatch, tmp_path, case):
    import money_machine.cli.real_draft as module

    p = tmp_path / "credential"
    p.write_text("test-only-credential")
    p.chmod(0o600)
    if case == "foreign_owner":
        actual_uid = module.os.getuid()
        monkeypatch.setattr(module.os, "getuid", lambda: actual_uid + 1)
    elif case == "world_readable":
        p.chmod(0o644)
    elif case == "symlink":
        link = tmp_path / "link"
        link.symlink_to(p)
        p = link
    elif case == "directory":
        p = tmp_path
    if case == "valid":
        assert module.read_private_credential(p) == "test-only-credential"
    else:
        with pytest.raises(DraftRunRefused, match="private_credential_file_required"):
            module.read_private_credential(p)


@pytest.mark.asyncio
async def test_real_sdk_retains_paced_mock_transport_headers_and_closes_it():
    import time

    import httpx

    from money_machine.cli.real_draft import private_notion_client

    timestamps = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-only-token"
        assert request.headers["Notion-Version"] == "2025-09-03"
        timestamps.append(time.monotonic())
        return httpx.Response(200, json={"object": "user", "id": str(uuid4())})

    async with private_notion_client(
        "test-only-token", transport=httpx.MockTransport(handle)
    ) as sdk:
        client = sdk.client
        # Fail before sending anything if SDK context entry discarded our transport/hooks.
        assert len(client.event_hooks["request"]) == 1
        await sdk.users.me()
        await sdk.users.me()
        assert len(timestamps) == 2 and timestamps[1] - timestamps[0] >= 0.35
    assert client.is_closed
