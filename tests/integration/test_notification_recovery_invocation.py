"""Finite A07 recovery: synthetic canonical rows and mock Notion SDK only."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import pytest
from notion_client import AsyncClient
from sqlalchemy import select

from money_machine.agents.prompt_store import PromptStore
from money_machine.agents.registry import AgentRegistry
from money_machine.agents.runtime import AgentRunner
from money_machine.application.real_draft_authority import notion_request_sha256
from money_machine.application.real_notion_build import SOURCES, notification_schema, schemas
from money_machine.domain.enums import AgentRunStatus
from money_machine.integrations.llm.fake_provider import FakeLLMProvider
from money_machine.persistence import tables as t
from tests.integration.test_notification_recovery_binding import envelope_for
from tests.integration.test_notification_recovery_guard import recovery as recovery
from tests.integration.test_real_draft_runner import runner_inputs as runner_inputs

pytestmark = pytest.mark.parametrize("recovery", ["runner"], indirect=True)


@pytest.fixture
async def invocation(recovery, runner_inputs, session_factory, repository_root):
    held, old_effects, original_approval, _ = recovery
    spec = runner_inputs[0].model_copy(
        update={
            "product_id": original_approval.product_id,
            "workflow_id": original_approval.workflow_id,
        }
    )
    digest = hashlib.sha256(spec.model_dump_json().encode()).hexdigest()
    databases = {name: str(uuid4()) for name in SOURCES}
    sources = {name: str(uuid4()) for name in SOURCES}
    props = notification_schema(sources, spec.currency)
    body = {
        "parent": {"type": "page_id", "page_id": str(original_approval.parent_id)},
        "title": [{"type": "text", "text": {"content": "Notification"}}],
        "is_inline": True,
        "initial_data_source": {"properties": props},
    }
    approval = original_approval.model_copy(
        update={"spec_sha256": digest, "request_sha256": notion_request_sha256(body)}
    )
    now = datetime.now(UTC)
    async with session_factory() as session, session.begin():
        original = await session.get(t.Job, approval.original_job_id)
        original.input = {**original.input, "spec_sha256": digest}
        definition = t.AgentDefinition(
            agent_id="A05",
            name="Synthetic producer",
            implementation_version=1,
            contract_version=1,
            timeout_seconds=600,
            default_side_effect_class="EXTERNAL_READ",
            default_retry_class="SAFE",
            commissioning_state="DESIGNED",
            commissioning_evidence=[],
        )
        prompt = t.PromptVersion(
            prompt_reference="agent://A05/system/v1",
            version=1,
            sha256="c" * 64,
            source_path="synthetic-test-only",
        )
        producer = t.Job(
            id=spec.producing_job_id,
            workflow_id=spec.workflow_id,
            object_type="Product",
            object_id=spec.product_id,
            job_type="ProductStrategyJob",
            owner_agent_id="A05",
            status="SUCCEEDED",
            input={"spec_sha256": digest},
            scheduled_at=now,
            idempotency_key=str(uuid4()),
            side_effect_class="EXTERNAL_READ",
            retry_class="SAFE",
            allowed_mode="draft",
        )
        research_job = t.Job(
            workflow_id=spec.workflow_id,
            object_type="ResearchRun",
            object_id=spec.research_run_id,
            job_type="MarketResearchJob",
            owner_agent_id="A03",
            status="SUCCEEDED",
            input={},
            scheduled_at=now,
            idempotency_key=str(uuid4()),
            side_effect_class="EXTERNAL_READ",
            retry_class="SAFE",
            allowed_mode="draft",
        )
        session.add_all([definition, prompt, producer, research_job])
        await session.flush()
        session.add(
            t.ResearchRun(
                id=spec.research_run_id,
                workflow_id=spec.workflow_id,
                job_id=research_job.id,
                source_policy_version="synthetic-only",
            )
        )
        await session.flush()
        session.add(
            t.AgentRun(
                id=spec.producing_agent_run_id,
                job_id=producer.id,
                agent_definition_id=definition.id,
                agent_id="A05",
                agent_definition_version=1,
                prompt_version_id=prompt.id,
                prompt_reference=prompt.prompt_reference,
                prompt_sha256=prompt.sha256,
                input_hash=digest,
                status="SUCCESS",
                output={"synthetic": True},
                started_at=now,
                completed_at=now,
            )
        )
        workflow = await session.get(t.WorkflowRun, spec.workflow_id)
        session.add(
            t.Product(
                id=spec.product_id,
                shop_id=workflow.shop_id,
                workflow_id=spec.workflow_id,
                producing_job_id=producer.id,
                identity=spec.identity,
                base_category=spec.base_category,
                working_title=spec.title,
            )
        )
        await session.flush()
        projection = spec.model_dump(mode="json")
        session.add(
            t.ProductSpec(
                id=spec.spec_id,
                product_id=spec.product_id,
                workflow_id=spec.workflow_id,
                version=spec.version,
                producing_job_id=producer.id,
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
                hubs=projection["hubs"],
                colour_variants=projection["colour_variants"],
                features=[
                    {
                        "flagship_feature": spec.flagship_feature,
                        "feature_targets": projection["feature_targets"],
                        "palette_name": spec.palette_name,
                        "palette_tokens": projection["palette_tokens"],
                    }
                ],
                experiment_plan=spec.experiment_hypothesis,
                concept_fingerprint=spec.concept_fingerprint,
                rule_version=spec.rule_version,
            )
        )
        job = await session.get(t.Job, approval.repair_job_id)
        job.input = {
            **job.input,
            "spec_sha256": digest,
            "notification_recovery": {
                "approval": approval.model_dump(mode="json"),
                "source_database_ids": databases,
                "source_data_source_ids": sources,
            },
        }
    state: dict[str, Any] = {
        "posts": 0,
        "reads": 0,
        "new": None,
        "mode": None,
        "late_candidate": False,
        "schema_drift": False,
        "candidate": False,
        "readback_failed": False,
        "notification_drift": False,
        "paginate": False,
        "notes_reads": 0,
        "source_identity_drift": False,
    }
    new_db, new_ds = str(uuid4()), str(uuid4())
    parent = str(approval.parent_id)

    def database(name, database_id, source_id):
        return {
            "id": database_id,
            "object": "database",
            "parent": {"type": "page_id", "page_id": parent},
            "title": [{"plain_text": name}],
            "data_sources": [{"id": source_id, "name": name}],
            "archived": False,
            "public_url": None,
        }

    def source(database_id, source_id, properties):
        observed = {
            name: {"id": str(i), "name": name, "type": next(iter(shape)), **shape}
            for i, (name, shape) in enumerate(properties.items())
        }
        if state["schema_drift"]:
            observed = {**observed, "Injected": {"type": "checkbox", "checkbox": {}}}
        if state["notification_drift"] and source_id == new_ds:
            observed["Notification"] = {"type": "formula", "formula": {"expression": "bad"}}
        return {
            "id": source_id,
            "object": "data_source",
            "parent": {"type": "database_id", "database_id": database_id},
            "properties": observed,
            "archived": False,
            "public_url": None,
        }

    async def handler(request):
        path = request.url.path.removeprefix("/v1/")
        if request.method == "GET":
            state["reads"] += 1
            if path == f"pages/{parent}":
                return httpx.Response(
                    200,
                    json={
                        "id": parent,
                        "parent": {"type": "workspace"},
                        "archived": False,
                        "public_url": None,
                    },
                )
            if path == f"blocks/{parent}/children":
                children = [
                    {"id": value, "type": "child_database", "child_database": {"title": name}}
                    for name, value in databases.items()
                ]
                if state["new"] or state["candidate"]:
                    children.append(
                        {
                            "id": new_db,
                            "type": "child_database",
                            "child_database": {"title": "Notification"},
                        }
                    )
                if state["paginate"] and not request.url.params.get("start_cursor"):
                    return httpx.Response(
                        200, json={"results": children[:3], "has_more": True, "next_cursor": "next"}
                    )
                if state["paginate"]:
                    children = children[3:]
                return httpx.Response(
                    200, json={"results": children, "has_more": False, "next_cursor": None}
                )
            for name in SOURCES:
                if path == f"databases/{databases[name]}":
                    return httpx.Response(200, json=database(name, databases[name], sources[name]))
                if path == f"data_sources/{sources[name]}":
                    if name == "Notes":
                        state["notes_reads"] += 1
                        if state["late_candidate"] and state["notes_reads"] == 2:
                            state["candidate"] = True
                    return httpx.Response(
                        200, json=source(databases[name], sources[name], schemas()[name])
                    )
            if path == f"databases/{new_db}":
                if state["mode"] == "readback" and not state["readback_failed"]:
                    state["readback_failed"] = True
                    return httpx.Response(
                        503, json={"code": "service_unavailable", "message": "synthetic"}
                    )
                return httpx.Response(
                    200,
                    json=database(
                        "Notification",
                        new_db,
                        str(uuid4()) if state["source_identity_drift"] else new_ds,
                    ),
                )
            if path == f"data_sources/{new_ds}":
                return httpx.Response(200, json=source(new_db, new_ds, props))
        assert request.method == "POST" and path == "databases"
        state["posts"] += 1
        assert json.loads(request.content) == body
        if state["mode"] in (400, 429):
            return httpx.Response(
                state["mode"], json={"code": "validation_error", "message": "synthetic"}
            )
        state["new"] = database("Notification", new_db, new_ds)
        if state["mode"] == "lost":
            raise httpx.ReadTimeout("synthetic lost response", request=request)
        if state["mode"] == "missing_source_identity":
            return httpx.Response(
                200,
                json={key: value for key, value in state["new"].items() if key != "data_sources"},
            )
        return httpx.Response(200, json=state["new"])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sdk = AsyncClient(auth="synthetic-only", notion_version="2025-09-03", client=client)

        async def execute(**overrides):
            from money_machine.application.notification_recovery import NotificationRecoveryAgent

            agent = NotificationRecoveryAgent(
                session_factory=session_factory,
                authority=old_effects.authority,
                sdk=sdk,
                approval=approval,
                spec=overrides.get("spec", spec),
                source_database_ids=overrides.get("databases", databases),
                source_data_source_ids=sources,
            )
            runner = AgentRunner(
                registry=AgentRegistry.from_yaml(repository_root),
                prompt_store=PromptStore(held["runner_root"]),
                provider=FakeLLMProvider(),
            )
            async with session_factory() as session:
                job = await session.get(t.Job, approval.repair_job_id)
                return await runner.execute(
                    session,
                    job=envelope_for(job),
                    agent=agent,
                    production=False,
                    lease_owner="repair-owner",
                )

        yield state, execute, approval, new_db, new_ds, spec


async def test_finite_recovery_verifies_one_effect_and_replays_without_writes(
    invocation, session_factory
):
    state, execute, approval, database_id, source_id, _spec = invocation
    for _ in range(2):
        result, run = await execute()
        assert result.status == AgentRunStatus.SUCCESS, result.model_dump(mode="json")
        assert (
            result.output["database_id"] == database_id
            and result.output["data_source_id"] == source_id
        )
        assert (
            result.output["canonical_selected"] is False
            and result.output["repair_completed"] is False
        )
        assert run.run_id == result.agent_run_id
        assert len(result.effects) == 1 and result.effects[0].effect_state == "CONFIRMED"
    assert state["posts"] == 1
    async with session_factory() as session:
        receipts = list(
            (
                await session.scalars(
                    select(t.Receipt).where(t.Receipt.job_id == approval.repair_job_id)
                )
            ).all()
        )
        assert len(receipts) == 1 and receipts[0].provider_object_id == database_id
        assert (await session.get(t.Job, approval.repair_job_id)).status == "RUNNING"


@pytest.mark.parametrize(
    "wrong",
    [
        "spec",
        "projection",
        "ledger_hash",
        "source_metadata",
        "source_mapping",
        "producer_scope",
        "research_scope",
    ],
)
async def test_canonical_mismatch_refuses_before_provider_reads(invocation, session_factory, wrong):
    state, execute, approval, _, _, spec = invocation
    options = {}
    if wrong == "spec":
        options["spec"] = spec.model_copy(update={"identity": "Unapproved identity"})
    elif wrong == "source_mapping":
        options["databases"] = {name: str(uuid4()) for name in SOURCES}
    else:
        async with session_factory() as session:
            if wrong == "projection":
                row = await session.get(t.ProductSpec, spec.spec_id)
                row.currency = "USD"
            elif wrong == "ledger_hash":
                row = await session.get(t.Job, approval.original_job_id)
                row.input = {**row.input, "spec_sha256": "f" * 64}
            elif wrong == "producer_scope":
                row = await session.get(t.Job, spec.producing_job_id)
                row.owner_agent_id = "A06"
            elif wrong == "research_scope":
                row = await session.get(t.ResearchRun, spec.research_run_id)
                row.job_id = spec.producing_job_id
            else:
                row = await session.get(t.Job, approval.repair_job_id)
                record = {**row.input["notification_recovery"]}
                record.pop("source_database_ids")
                row.input = {**row.input, "notification_recovery": record}
            await session.commit()
    result, _ = await execute(**options)
    assert result.status == AgentRunStatus.FAILURE
    assert state["posts"] == state["reads"] == 0


@pytest.mark.parametrize("mode", ["candidate", "late_candidate", "schema_drift"])
async def test_preflight_refuses_candidates_and_schema_drift(invocation, mode):
    state, execute, *_ = invocation
    state[mode] = True
    state["paginate"] = True
    result, _ = await execute()
    assert result.status == AgentRunStatus.FAILURE and state["posts"] == 0
    if mode == "late_candidate":
        assert state["notes_reads"] == 2


@pytest.mark.parametrize("mode", [400, 429, "lost"])
async def test_finite_failure_replay_cannot_send_twice_or_adopt_a_title(
    invocation, session_factory, mode
):
    state, execute, approval, *_ = invocation
    state["mode"] = mode
    for _ in range(2):
        result, _ = await execute()
        assert result.status == (
            AgentRunStatus.UNCERTAIN_EXTERNAL_EFFECT if mode == "lost" else AgentRunStatus.FAILURE
        )
        assert len(result.effects) == 1
        assert result.effects[0].effect_state == ("UNKNOWN" if mode == "lost" else "ABSENT")
    assert state["posts"] == 1
    async with session_factory() as session:
        receipts = list(
            (
                await session.scalars(
                    select(t.Receipt).where(t.Receipt.job_id == approval.repair_job_id)
                )
            ).all()
        )
        assert not receipts
        job = await session.get(t.Job, approval.repair_job_id)
        assert job.input["notification_recovery"]["send_consumed_at"]


@pytest.mark.parametrize("mode", ["readback", "notification_drift"])
async def test_retained_accepted_identity_can_be_verified_without_resend(
    invocation, session_factory, mode
):
    state, execute, approval, database_id, _, _ = invocation
    if mode == "readback":
        state["mode"] = mode
    else:
        state[mode] = True
    result, _ = await execute()
    assert result.status == AgentRunStatus.UNCERTAIN_EXTERNAL_EFFECT and state["posts"] == 1
    assert result.effects[0].provider_object_id == database_id
    async with session_factory() as session:
        attempts = list(
            (
                await session.scalars(
                    select(t.EffectAttempt).where(t.EffectAttempt.job_id == approval.repair_job_id)
                )
            ).all()
        )
        assert any(
            row.provider_object_id == database_id and row.effect_state == "UNKNOWN"
            for row in attempts
        )
        assert not list(
            (
                await session.scalars(
                    select(t.Receipt).where(t.Receipt.job_id == approval.repair_job_id)
                )
            ).all()
        )
    state["mode"], state["notification_drift"] = None, False
    result, _ = await execute()
    assert result.status == AgentRunStatus.SUCCESS and state["posts"] == 1


async def test_candidate_disappearance_cannot_clear_approval_scoped_hold(
    invocation, session_factory
):
    state, execute, approval, *_ = invocation
    state["candidate"] = True
    result, _ = await execute()
    assert result.status == AgentRunStatus.FAILURE and state["posts"] == 0
    state["candidate"] = False
    result, _ = await execute()
    assert result.status == AgentRunStatus.FAILURE and state["posts"] == 0
    async with session_factory() as session:
        job = await session.get(t.Job, approval.repair_job_id)
        hold = job.input["notification_recovery"]["candidate_hold"]
        assert hold["approval_id"] == str(approval.approval_id) and hold["candidate_ids"]


@pytest.mark.parametrize("mode", ["source_identity_drift", "missing_source_identity"])
async def test_returned_source_identity_cannot_be_replaced_by_matching_readback(
    invocation, session_factory, mode
):
    state, execute, approval, database_id, source_id, _ = invocation
    if mode == "source_identity_drift":
        state[mode] = True
    else:
        state["mode"] = mode
    for _ in range(2):
        result, _ = await execute()
        assert result.status == AgentRunStatus.UNCERTAIN_EXTERNAL_EFFECT
        assert result.effects[0].effect_state == "UNKNOWN"
        assert result.effects[0].provider_object_id == database_id
    assert state["posts"] == 1
    async with session_factory() as session:
        job = await session.get(t.Job, approval.repair_job_id)
        accepted = job.input["notification_recovery"]["accepted_resource"]
        assert accepted == {
            "database_id": database_id,
            "data_source_id": source_id if mode == "source_identity_drift" else None,
        }
        assert not list(
            (
                await session.scalars(
                    select(t.Receipt).where(t.Receipt.job_id == approval.repair_job_id)
                )
            ).all()
        )


async def test_concurrent_finite_invocations_cannot_create_twice(invocation):
    state, execute, *_ = invocation
    results = await asyncio.gather(execute(), execute(), return_exceptions=True)
    assert state["posts"] == 1
    assert (
        sum(isinstance(row, tuple) and row[0].status == AgentRunStatus.SUCCESS for row in results)
        == 1
    )
