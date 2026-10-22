"""A07 context-to-guard integration: fixture DB and injected mock SDK only."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from money_machine.agents.base import AgentContext, BaseAgent
from money_machine.agents.prompt_store import PromptStore
from money_machine.agents.registry import AgentRegistry
from money_machine.agents.runtime import AgentRunner
from money_machine.application import real_draft_effects
from money_machine.application.real_draft_authority import DraftRunRefused
from money_machine.domain.enums import AgentRunStatus, JobStatus, RetryClass, SideEffectClass
from money_machine.domain.models.common import SuccessContract
from money_machine.domain.models.jobs import AgentResult, JobEnvelope
from money_machine.integrations.llm.fake_provider import FakeLLMProvider
from money_machine.persistence.tables import AgentRun, EffectAttempt, Job, Receipt
from tests.integration.test_notification_recovery_guard import recovery as recovery


def envelope_for(job: Job) -> JobEnvelope:
    return JobEnvelope(
        job_id=job.id,
        workflow_id=job.workflow_id,
        object_id=job.object_id,
        job_type=job.job_type,
        object_type=job.object_type,
        owner_agent_id=job.owner_agent_id,
        status=JobStatus(job.status),
        input=job.input,
        scheduled_at=job.scheduled_at,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        idempotency_key=job.idempotency_key,
        side_effect_class=SideEffectClass(job.side_effect_class),
        retry_class=RetryClass(job.retry_class),
        success_contract=SuccessContract(output_model="AgentResult"),
    )


async def context_for(factory, effects, state, repository_root):
    async with factory() as session:
        job = await session.get(Job, effects.job_id)
        assert job is not None
        observation = state["run_context"]
        return AgentContext(
            job=envelope_for(job),
            definition=AgentRegistry.from_yaml(repository_root).get("A07"),
            run_id=observation.run_id,
            prompt_text="Synthetic fixture; never a production prompt",
            prompt_reference=observation.prompt_reference,
            prompt_sha256=observation.prompt_sha256,
            prompt_version=1,
            provider=FakeLLMProvider(),
            run_at=observation.started_at,
            lease_owner="repair-owner",
        )


@pytest.mark.parametrize("revoke", [False, True])
async def test_binding_connects_actual_run_to_one_guarded_send(
    recovery, session_factory, repository_root, revoke
):
    state, old_effects, approval, _execute = recovery
    context = await context_for(session_factory, old_effects, state, repository_root)
    effects, adapter = await real_draft_effects.SqlDraftEffects.bind_notification_recovery(
        context,
        session_factory=session_factory,
        authority=old_effects.authority,
        sdk=state["sdk"],
        approval=approval,
    )
    assert effects.agent_run_id == context.run_id
    assert effects.lease_owner == context.lease_owner

    async def reconcile(known):
        return await adapter.get_database(known) if known else None

    async def create():
        return await adapter.create_database(approval.parent_id, "Notification", state["props"])

    if revoke:
        async with session_factory() as session:
            job = await session.get(Job, effects.job_id)
            job.input = {**job.input, "notification_recovery": {}}
            await session.commit()
        with pytest.raises(DraftRunRefused, match="durable_effect_guard_refused"):
            await effects.execute(
                approval.operation_key,
                provider="notion",
                operation="notion.private_product.write",
                create=create,
                reconcile=reconcile,
                notion_parent_id=approval.parent_id,
            )
        assert state["posts"] == 0
        return
    for _ in range(2):
        await effects.execute(
            approval.operation_key,
            provider="notion",
            operation="notion.private_product.write",
            create=create,
            reconcile=reconcile,
            notion_parent_id=approval.parent_id,
        )
    assert state["posts"] == 1


@pytest.mark.parametrize(
    "wrong",
    [
        "missing_lease",
        "lease",
        "run",
        "prompt",
        "prompt_version",
        "agent",
        "definition_version",
        "product",
        "job_type",
        "attempt",
        "approval",
        "expired",
    ],
)
async def test_binding_refuses_context_and_approval_drift(
    recovery, session_factory, repository_root, wrong
):
    state, old_effects, approval, _execute = recovery
    context = await context_for(session_factory, old_effects, state, repository_root)
    if wrong == "missing_lease":
        context = replace(context, lease_owner=None)
    elif wrong == "lease":
        context = replace(context, lease_owner="not-the-worker")
    elif wrong == "run":
        context = replace(context, run_id=uuid4())
    elif wrong == "prompt":
        context = replace(context, prompt_sha256="f" * 64)
    elif wrong == "prompt_version":
        context = replace(context, prompt_version=2)
    elif wrong == "agent":
        context = replace(context, definition=AgentRegistry.from_yaml(repository_root).get("A06"))
    elif wrong == "definition_version":
        context = replace(context, definition=replace(context.definition, contract_version=2))
    elif wrong == "product":
        context = replace(context, job=context.job.model_copy(update={"object_id": uuid4()}))
    elif wrong == "job_type":
        context = replace(
            context, job=context.job.model_copy(update={"job_type": "RealProductBuild"})
        )
    elif wrong == "attempt":
        context = replace(
            context, job=context.job.model_copy(update={"attempt": context.job.attempt + 1})
        )
    elif wrong == "approval":
        approval = approval.model_copy(update={"decision_sha256": "f" * 64})
    elif wrong == "expired":
        approval = approval.model_copy(
            update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
        )
        async with session_factory() as session:
            job = await session.get(Job, old_effects.job_id)
            job.input = {
                **job.input,
                "notification_recovery": {"approval": approval.model_dump(mode="json")},
            }
            await session.commit()
    with pytest.raises(DraftRunRefused):
        await real_draft_effects.SqlDraftEffects.bind_notification_recovery(
            context,
            session_factory=session_factory,
            authority=old_effects.authority,
            sdk=state["sdk"],
            approval=approval,
        )
    assert state["posts"] == 0 and state["object"] is None


@pytest.mark.parametrize("recovery", ["runner"], indirect=True)
@pytest.mark.parametrize("lost_response", [False, True])
async def test_actual_runner_supplies_guard_lineage_and_retry_cannot_resend(
    recovery, session_factory, repository_root, lost_response
):
    state, old_effects, approval, _execute = recovery
    seen = []

    class BindingProbeAgent(BaseAgent):
        async def execute(self, context):
            assert context.lease_owner == "repair-owner"
            effects, adapter = await real_draft_effects.SqlDraftEffects.bind_notification_recovery(
                context,
                session_factory=session_factory,
                authority=old_effects.authority,
                sdk=state["sdk"],
                approval=approval,
            )
            seen.append(context.run_id)

            async def create():
                return await adapter.create_database(
                    approval.parent_id, "Notification", state["props"]
                )

            async def read(known):
                return await adapter.get_database(known) if known else None

            await effects.execute(
                approval.operation_key,
                provider="notion",
                operation="notion.private_product.write",
                create=create,
                reconcile=read,
                notion_parent_id=approval.parent_id,
            )
            return AgentResult(
                job_id=context.job.job_id,
                agent_run_id=context.run_id,
                agent_id="A07",
                agent_definition_version=context.definition.contract_version,
                prompt_reference=context.prompt_reference,
                prompt_sha256=context.prompt_sha256,
                status=AgentRunStatus.SUCCESS,
                output={"synthetic_binding_test": True},
            )

    if lost_response:
        state["failure"] = "lost"
    runner = AgentRunner(
        registry=AgentRegistry.from_yaml(repository_root),
        prompt_store=PromptStore(state["runner_root"]),
        provider=FakeLLMProvider(),
    )
    async with session_factory() as session:
        job = await session.get(Job, old_effects.job_id)
        envelope = envelope_for(job)
        for _ in range(2):
            result, receipt = await runner.execute(
                session,
                job=envelope,
                agent=BindingProbeAgent(),
                production=False,
                lease_owner="repair-owner",
            )
            assert result.status == (
                AgentRunStatus.FAILURE if lost_response else AgentRunStatus.SUCCESS
            )
            assert receipt.run_id == result.agent_run_id
    assert state["posts"] == 1 and len(seen) == 2 and len(set(seen)) == 2
    async with session_factory() as session:
        attempts = list(
            (
                await session.scalars(
                    select(EffectAttempt).where(EffectAttempt.job_id == old_effects.job_id)
                )
            ).all()
        )
        assert attempts and all(row.agent_run_id in seen for row in attempts)
        assert attempts[-1].effect_state == ("UNKNOWN" if lost_response else "CONFIRMED")
        receipts = list(
            (
                await session.scalars(select(Receipt).where(Receipt.job_id == old_effects.job_id))
            ).all()
        )
        assert len(receipts) == (0 if lost_response else 1)
        runs = list(
            (
                await session.scalars(select(AgentRun).where(AgentRun.job_id == old_effects.job_id))
            ).all()
        )
        assert len(runs) == 2 and all(row.completed_at is not None for row in runs)
