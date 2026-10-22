"""One-send guard tests: isolated databases, synthetic approvals and mock transport only."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
from notion_client import AsyncClient
from sqlalchemy import select

from money_machine.application import real_draft_authority as authority_module
from money_machine.application.real_draft_authority import DraftRunRefused
from money_machine.application.real_draft_effects import DraftEffectUncertain, SqlDraftEffects
from money_machine.domain.enums import AgentRunStatus, SideEffectClass
from money_machine.domain.models.common import ContractError
from money_machine.integrations.notion.real_product_adapter import RealPrivateNotionAdapter
from money_machine.orchestration.idempotency import record_effect_attempt, reserve_idempotency_key
from money_machine.persistence.tables import (
    AgentDefinition,
    AgentRun,
    EffectAttempt,
    Incident,
    Job,
    PromptVersion,
    Receipt,
)
from tests.integration.test_agent_run_lifecycle import observer
from tests.integration.test_real_draft_effects import prepare


@pytest.fixture
async def recovery(session_factory, request, repository_root):
    old, parent = await prepare(session_factory)
    now = datetime.now(UTC)
    runner_mode = getattr(request, "param", None) == "runner"
    prompt_file = repository_root / "prompts/agents/A07/v1.md"
    original_key = "synthetic-original-unknown"
    async with session_factory() as session, session.begin():
        original = await session.get(Job, old.job_id)
        original.status = "BLOCKED"
        await reserve_idempotency_key(
            session,
            idempotency_key=original_key,
            job_id=old.job_id,
            operation="notion.private_product.write",
            side_effect_class=SideEffectClass.EXTERNAL_WRITE,
        )
        attempt = await record_effect_attempt(
            session,
            idempotency_key=original_key,
            job_id=old.job_id,
            agent_run_id=None,
            provider="notion",
            operation="notion.private_product.write",
            effect_state="UNKNOWN",
            provider_object_id=None,
            reconciliation_attempt=3,
        )
        for index in range(14):
            session.add(
                Receipt(
                    job_id=old.job_id,
                    idempotency_key=f"confirmed-{index}",
                    provider="notion",
                    operation="notion.private_product.write",
                    side_effect_class="EXTERNAL_WRITE",
                    autonomy_mode="draft",
                    effect_state="CONFIRMED",
                    provider_object_id=str(uuid4()),
                )
            )
        from money_machine.persistence.tables import WorkflowRun

        workflow = await session.get(WorkflowRun, original.workflow_id)
        incident = Incident(
            shop_id=workflow.shop_id,
            incident_type="UNCERTAIN_EXTERNAL_EFFECT",
            affected_object_type="Product",
            affected_object_id=original.object_id,
            workflow_id=original.workflow_id,
            opened_by_job_id=old.job_id,
        )
        session.add(incident)
        job = Job(
            workflow_id=original.workflow_id,
            job_type="BuildRepairJob",
            object_type="Product",
            object_id=original.object_id,
            owner_agent_id="A07",
            status="RUNNING",
            input={"run_id": old.authority.run_id},
            scheduled_at=now,
            idempotency_key=str(uuid4()),
            side_effect_class="EXTERNAL_WRITE",
            retry_class="RECONCILE_FIRST",
            allowed_mode="draft",
            lease_owner="repair-owner",
            lease_expires_at=now + timedelta(minutes=10),
        )
        session.add(job)
        await session.flush()
        definition = AgentDefinition(
            agent_id="A07",
            name="Synthetic guard-test builder",
            implementation_version=1,
            contract_version=1,
            timeout_seconds=600,
            default_side_effect_class="EXTERNAL_WRITE",
            default_retry_class="RECONCILE_FIRST",
            commissioning_state="DESIGNED",
            commissioning_evidence=[],
        )
        prompt = PromptVersion(
            prompt_reference="agent://A07/system/v1",
            version=1,
            sha256=hashlib.sha256(prompt_file.read_bytes()).hexdigest()
            if runner_mode
            else "a" * 64,
            source_path="prompts/agents/A07/v1.md"
            if runner_mode
            else "tests/integration/test_notification_recovery_guard.py",
        )
        session.add_all([definition, prompt])
        await session.flush()
        active = observer(session)
        from money_machine.observability.correlation import CorrelationContext

        run_context, run = None, None
        if not runner_mode:
            run_context = active.begin_run(
                correlation=CorrelationContext(job.id, "A07", job.workflow_id, attempt=job.attempt),
                agent_definition_id=definition.id,
                agent_definition_version=1,
                prompt_version_id=prompt.id,
                prompt_reference=prompt.prompt_reference,
                prompt_sha256=prompt.sha256,
                run_number=1,
                model=None,
                input_payload={"fixture": "synthetic guard test"},
            )
            run = await active.persist_started_run(run_context, lease_owner="repair-owner")
        body = {
            "parent": {"type": "page_id", "page_id": str(parent)},
            "title": [{"type": "text", "text": {"content": "Notification"}}],
            "is_inline": True,
            "initial_data_source": {"properties": {"Name": {"title": {}}}},
        }
        approval = authority_module.NotificationReplacementApproval(
            approval_id=uuid4(),
            repair_job_id=job.id,
            original_job_id=old.job_id,
            original_attempt_id=attempt.id,
            original_effect_key=original_key,
            workflow_id=job.workflow_id,
            product_id=job.object_id,
            run_id=old.authority.run_id,
            parent_id=parent,
            request_sha256=authority_module.notion_request_sha256(body),
            spec_sha256="b" * 64,
            decision_sha256="c" * 64,
            operator_reference="TEST ONLY, not actual approval",
            approved_at=now,
            expires_at=now + timedelta(hours=1),
        )
        job.input = {
            **job.input,
            "notification_recovery": {"approval": approval.model_dump(mode="json")},
        }
        job_id, run_id, incident_id = job.id, run.id if run is not None else None, incident.id
    effects = SqlDraftEffects(
        session_factory, old.authority, job_id, lease_owner="repair-owner", agent_run_id=run_id
    )
    state: dict[str, Any] = {
        "posts": 0,
        "failure": None,
        "object": None,
        "visible": True,
        "crash": None,
        "props": {"Name": {"title": {}}},
    }
    db_id = str(uuid4())

    def handler(request):
        path = request.url.path.removeprefix("/v1/")
        if request.method == "GET" and path == f"pages/{parent}":
            return httpx.Response(
                200,
                json={
                    "id": str(parent),
                    "parent": {"type": "workspace"},
                    "archived": False,
                    "public_url": None,
                },
            )
        if request.method == "GET" and path == f"databases/{db_id}":
            return httpx.Response(200, json=state["object"])
        assert request.method == "POST" and path == "databases"
        state["posts"] += 1
        assert json.loads(request.content) == body
        if state["failure"] in (400, 429):
            return httpx.Response(
                state["failure"], json={"code": "validation_error", "message": "test"}
            )
        state["object"] = {
            "id": db_id,
            "data_sources": [{"id": str(uuid4())}],
            "parent": {"type": "page_id", "page_id": str(parent)},
            "archived": False,
            "public_url": None,
        }
        if state["failure"] == "lost":
            raise httpx.ReadTimeout("test response lost", request=request)
        return httpx.Response(200, json=state["object"])

    async def before_send(method, path, body):
        if state["crash"] == "before":
            raise RuntimeError("before consumption")
        await effects.consume_notification_recovery_send(
            state.get("approval", approval), method, path, body
        )
        if state.get("mutate"):
            state["props"]["Name"] = {"number": {}}
        if state["crash"] == "after":
            raise RuntimeError("after durable consumption, before transport")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sdk = AsyncClient(auth="fixture-only", notion_version="2025-09-03", client=client)
        adapter = RealPrivateNotionAdapter(
            old.authority, sdk=sdk, before_write=effects.assert_lease, before_send=before_send
        )

        async def execute(operation_key=None):
            async def read(known):
                return (
                    (await adapter.get_database(db_id))
                    if state["object"] and state["visible"]
                    else None
                )

            return await effects.execute(
                operation_key or approval.operation_key,
                provider="notion",
                operation="notion.private_product.write",
                notion_parent_id=parent,
                reconcile=read,
                create=lambda: adapter.create_database(parent, "Notification", state["props"]),
            )

        state["runner_root"] = repository_root
        state["sdk"] = sdk
        state["run_context"] = run_context
        state["adapter"] = adapter
        yield state, effects, approval, execute
    async with session_factory() as session:
        assert (await session.get(Job, old.job_id)).status == "BLOCKED"
        assert (await session.get(Incident, incident_id)).incident_state == "OPEN"
        original_attempts = list(
            (
                await session.scalars(
                    select(EffectAttempt).where(EffectAttempt.job_id == old.job_id)
                )
            ).all()
        )
        assert len(original_attempts) == 1 and original_attempts[0].effect_state == "UNKNOWN"
        receipts = list(
            (await session.scalars(select(Receipt).where(Receipt.job_id == old.job_id))).all()
        )
        assert len(receipts) == 14 and all(r.effect_state == "CONFIRMED" for r in receipts)


@pytest.mark.asyncio
async def test_one_send_success_replay_and_trace(recovery, session_factory):
    state, effects, _approval, execute = recovery
    first = await execute()
    assert await execute() == first
    assert state["posts"] == 1
    async with session_factory() as session:
        job = await session.get(Job, effects.job_id)
        assert job.input["notification_recovery"]["send_consumed_at"]
        attempts = list(
            (
                await session.scalars(
                    select(EffectAttempt).where(EffectAttempt.job_id == effects.job_id)
                )
            ).all()
        )
        assert all(a.agent_run_id == effects.agent_run_id for a in attempts)
        receipt = await session.scalar(select(Receipt).where(Receipt.job_id == effects.job_id))
        assert receipt.safe_detail["agent_run_id"] == str(effects.agent_run_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [400, 429, "lost"])
async def test_replay_never_resends_after_any_provider_outcome(recovery, failure):
    state, _, _, execute = recovery
    state["failure"] = failure
    state["visible"] = False
    for _ in range(2):
        with pytest.raises((DraftRunRefused, DraftEffectUncertain)):
            await execute()
    assert state["posts"] == 1
    if failure == "lost":
        state["visible"] = True
        assert (await execute())["id"] == state["object"]["id"]
        assert state["posts"] == 1


@pytest.mark.asyncio
async def test_concurrent_dispatch_sends_once(recovery):
    state, _, _, execute = recovery
    results = await asyncio.gather(execute(), execute(), return_exceptions=True)
    assert state["posts"] == 1
    assert any(isinstance(r, dict) for r in results)
    assert all(isinstance(r, (dict, DraftRunRefused, DraftEffectUncertain)) for r in results)


@pytest.mark.asyncio
@pytest.mark.parametrize("crash", ["before", "after"])
async def test_crash_around_authority_consumption(recovery, crash):
    state, _, _, execute = recovery
    state["crash"] = crash
    with pytest.raises(DraftRunRefused):
        await execute()
    assert state["posts"] == 0
    state["crash"] = None
    if crash == "after":
        with pytest.raises(DraftRunRefused):
            await execute()
        assert state["posts"] == 0
    else:
        await execute()
        assert state["posts"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "damage", ["body", "approval", "expired", "run", "lease", "key", "original"]
)
async def test_wrong_scope_or_authority_refused_without_send(recovery, session_factory, damage):
    state, effects, approval, execute = recovery
    if damage == "body":
        state["props"] = {"Different": {"title": {}}}
    elif damage == "run":
        effects.agent_run_id = uuid4()
    elif damage in ("approval", "expired", "lease", "original"):
        async with session_factory() as session, session.begin():
            job = await session.get(Job, effects.job_id)
            if damage == "approval":
                job.input = {"run_id": approval.run_id}
            if damage == "expired":
                state["approval"] = approval.model_copy(
                    update={
                        "approved_at": datetime.now(UTC) - timedelta(hours=2),
                        "expires_at": datetime.now(UTC) - timedelta(hours=1),
                    }
                )
                job.input = {
                    **job.input,
                    "notification_recovery": {
                        "approval": state["approval"].model_dump(mode="json")
                    },
                }
            if damage == "lease":
                job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            if damage == "original":
                state["approval"] = approval.model_copy(update={"original_attempt_id": uuid4()})
                job.input = {
                    **job.input,
                    "notification_recovery": {
                        "approval": state["approval"].model_dump(mode="json")
                    },
                }
    with pytest.raises((DraftRunRefused, DraftEffectUncertain)):
        await execute("wrong-operation" if damage == "key" else None)
    assert state["posts"] == 0


@pytest.mark.asyncio
async def test_missing_request_guard_refuses_even_after_crash_left_a_permit(recovery):
    state, _, _, execute = recovery
    state["crash"] = "after"
    with pytest.raises(DraftRunRefused):
        await execute()
    state["crash"] = None
    state["adapter"]._before_send = None
    with pytest.raises(DraftRunRefused):
        await execute()
    assert state["posts"] == 0


@pytest.mark.asyncio
async def test_mutation_of_caller_properties_cannot_change_approved_wire_body(recovery):
    state, _, _, execute = recovery
    state["mutate"] = True
    await execute()
    assert state["posts"] == 1
    assert state["props"]["Name"] == {"number": {}}


@pytest.mark.asyncio
async def test_no_explicit_approval_sends_nothing(recovery):
    state, _, _, execute = recovery
    state["approval"] = None
    with pytest.raises(DraftRunRefused):
        await execute()
    assert state["posts"] == 0


@pytest.mark.asyncio
async def test_expiry_during_guard_lock_wait_refuses_send(recovery, session_factory, monkeypatch):
    state, effects, approval, execute = recovery
    # A deterministic clock advances while the send guard awaits its job lock.
    import money_machine.application.real_draft_effects as module

    real_datetime = module.datetime
    now = [real_datetime.now(UTC)]
    approval = approval.model_copy(update={"expires_at": now[0] + timedelta(minutes=1)})
    state["approval"] = approval
    async with session_factory() as session, session.begin():
        job = await session.get(Job, effects.job_id)
        job.input = {
            **job.input,
            "notification_recovery": {"approval": approval.model_dump(mode="json")},
        }

    class Clock:
        @classmethod
        def now(cls, tz):
            return now[0]

    monkeypatch.setattr(module, "datetime", Clock)
    original = effects._job
    calls = 0

    async def waited(session):
        nonlocal calls
        job = await original(session)
        calls += 1
        # execute's reservation/recheck locks are first; guard's lock is third.
        if calls == 3:
            now[0] = approval.expires_at + timedelta(seconds=1)
        return job

    monkeypatch.setattr(effects, "_job", waited)
    with pytest.raises(DraftRunRefused):
        await execute()
    assert state["posts"] == 0
    async with session_factory() as session:
        job = await session.get(Job, effects.job_id)
        assert "send_consumed_at" not in job.input["notification_recovery"]


@pytest.mark.asyncio
async def test_approval_revocation_after_consumption_refuses_wire_send(recovery, session_factory):
    state, effects, _, execute = recovery
    adapter = state["adapter"]
    guard = adapter._before_send

    async def revoked(method, path, body):
        await guard(method, path, body)
        async with session_factory() as session, session.begin():
            job = await session.get(Job, effects.job_id)
            value = dict(job.input["notification_recovery"])
            value["approval"] = {}
            job.input = {**job.input, "notification_recovery": value}

    adapter._before_send = revoked
    with pytest.raises(DraftRunRefused):
        await execute()
    assert state["posts"] == 0


@pytest.mark.asyncio
async def test_hook_cannot_mutate_transport_body_after_digest_validation(recovery):
    state, _, _, execute = recovery
    adapter = state["adapter"]
    guard = adapter._before_send

    async def changed(method, path, body):
        await guard(method, path, body)
        body["initial_data_source"]["properties"] = {"Wrong": {"number": {}}}

    adapter._before_send = changed
    await execute()
    assert state["posts"] == 1  # mock also asserts exact approved request body


@pytest.mark.asyncio
async def test_missing_metadata_and_missing_hook_cannot_downgrade_recovery(
    recovery, session_factory
):
    state, effects, approval, execute = recovery
    async with session_factory() as session, session.begin():
        job = await session.get(Job, effects.job_id)
        job.input = {"run_id": approval.run_id}
    state["adapter"]._before_send = None
    with pytest.raises(DraftRunRefused):
        await execute()
    assert state["posts"] == 0


@pytest.mark.asyncio
async def test_expiry_after_consumption_before_final_lease_check(
    recovery, session_factory, monkeypatch
):
    state, effects, approval, execute = recovery
    import money_machine.application.real_draft_effects as module

    clock = [datetime.now(UTC)]

    class Clock:
        @classmethod
        def now(cls, tz):
            return clock[0]

    approval = approval.model_copy(update={"expires_at": clock[0] + timedelta(minutes=1)})
    state["approval"] = approval
    async with session_factory() as session, session.begin():
        job = await session.get(Job, effects.job_id)
        job.input = {
            **job.input,
            "notification_recovery": {"approval": approval.model_dump(mode="json")},
        }
    monkeypatch.setattr(module, "datetime", Clock)
    adapter = state["adapter"]
    guard = adapter._before_send

    async def expired(method, path, body):
        await guard(method, path, body)
        clock[0] += timedelta(minutes=2)

    adapter._before_send = expired
    with pytest.raises(DraftRunRefused):
        await execute()
    assert state["posts"] == 0


@pytest.mark.parametrize("end_before_send", [True, False])
async def test_guard_uses_active_observer_run_and_retains_trace_after_failure(
    recovery, session_factory, end_before_send
):
    state, effects, _approval, execute = recovery
    context = state["run_context"]
    async with session_factory() as session:
        run = await session.get(AgentRun, context.run_id)
        assert run.status == "RUNNING" and run.completed_at is None
        if end_before_send:
            await observer(session).finalize_run(
                context,
                status=AgentRunStatus.FAILURE,
                output={},
                error=ContractError(code="TEST_FAILED", message="synthetic terminal failure"),
            )
            await session.commit()
    if end_before_send:
        with pytest.raises(DraftRunRefused, match="active_agent_run_required"):
            await execute()
        assert state["posts"] == 0
    else:
        state["failure"] = "lost"
        with pytest.raises(DraftEffectUncertain):
            await execute()
        assert state["posts"] == 1
        async with session_factory() as session:
            await observer(session).finalize_run(
                context,
                status=AgentRunStatus.FAILURE,
                output={},
                error=ContractError(code="TEST_LOST_RESPONSE", message="synthetic lost response"),
            )
            await session.commit()
        with pytest.raises(DraftRunRefused, match="active_agent_run_required"):
            await execute()
        assert state["posts"] == 1
        async with session_factory() as session:
            attempts = list(
                (
                    await session.scalars(
                        select(EffectAttempt).where(EffectAttempt.job_id == effects.job_id)
                    )
                ).all()
            )
            assert attempts and all(attempt.agent_run_id == context.run_id for attempt in attempts)
            assert attempts[-1].effect_state == "UNKNOWN"


@pytest.mark.parametrize("change", ["owner", "attempt"])
async def test_old_active_run_cannot_be_reused_after_lease_turnover(
    recovery, session_factory, change
):
    state, effects, _approval, _execute = recovery
    new_owner = "new-repair-owner" if change == "owner" else effects.lease_owner
    async with session_factory() as session:
        job = await session.get(Job, effects.job_id)
        job.lease_owner = new_owner
        if change == "attempt":
            job.attempt += 1
        await session.commit()
    # Even a caller possessing the new valid lease cannot borrow the prior run.
    stale_trace = SqlDraftEffects(
        session_factory,
        effects.authority,
        effects.job_id,
        lease_owner=new_owner,
        agent_run_id=effects.agent_run_id,
    )

    async def forbidden_create() -> dict[str, object]:
        raise AssertionError("old run must be refused before any provider call")

    async def absent(_known: str | None) -> None:
        return None

    with pytest.raises(DraftRunRefused, match="active_agent_run_required"):
        await stale_trace.execute(
            "no-borrowing-run",
            provider="notion",
            operation="notion.private_product.write",
            notion_parent_id=_approval.parent_id,
            create=forbidden_create,
            reconcile=absent,
        )
    assert state["posts"] == 0
