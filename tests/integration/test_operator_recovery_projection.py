"""Read-only recovery proof from real runner/SQL fixtures; no provider transport."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from money_machine.api.dependencies import ApplicationState
from money_machine.api.main import create_app
from money_machine.config.runtime import DatabaseSettings, RuntimeSettings
from money_machine.config.settings import RuntimeEnvironment
from money_machine.persistence import tables as t
from tests.integration.factories import make_job, make_workflow
from tests.integration.test_notification_recovery_guard import recovery as recovery
from tests.integration.test_notification_recovery_invocation import invocation as invocation
from tests.integration.test_real_draft_runner import runner_inputs as runner_inputs

pytestmark = pytest.mark.parametrize("recovery", ["runner"], indirect=True)


@pytest.mark.parametrize("mode", ["success", "readback"])
async def test_summary_projects_recovery_without_completing_or_mutating_it(
    invocation, session_factory, engine, migrated_url, mode
):
    state, execute, approval, database_id, source_id, spec = invocation
    state["mode"] = None if mode == "success" else mode
    result, _ = await execute()
    async with session_factory() as session, session.begin():
        workflow = await session.get(t.WorkflowRun, spec.workflow_id)
        workflow.workflow_type = "RealProductDraft:" + approval.run_id
        job = await session.get(t.Job, approval.repair_job_id)
        before = dict(job.input)
    app = create_app()
    app.state.application = ApplicationState(
        RuntimeSettings(
            environment=RuntimeEnvironment.TEST, database=DatabaseSettings(url=migrated_url)
        ),
        engine,
        session_factory,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api") as client:
        response = await client.get(f"/operator/runs/{approval.run_id}/summary")
        assert response.status_code == 200
        body = response.json()
        assert body["recoveries"] == [
            {
                "job_id": str(approval.repair_job_id),
                "agent_run_id": str(result.agent_run_id),
                "agent_run_status": "SUCCESS" if mode == "success" else "UNCERTAIN_EXTERNAL_EFFECT",
                "effect_state": "CONFIRMED" if mode == "success" else "UNKNOWN",
                "database_id": database_id,
                "data_source_id": source_id,
            }
        ]
        assert body["pending_effects"] == (1 if mode == "success" else 2)
        assert body["workflow_completed"] is False
        assert body["fixture_completed"] is False
        assert (
            next(j for j in body["jobs"] if j["id"] == str(approval.repair_job_id))["status"]
            == "RUNNING"
        )
        assert "request_sha256" not in response.text and "operator_reference" not in response.text
        assert (await client.get(f"/operator/runs/{approval.run_id}/summary")).json() == body
    async with session_factory() as session:
        assert (await session.get(t.Job, approval.repair_job_id)).input == before
        original = await session.get(t.EffectAttempt, approval.original_attempt_id)
        assert original.effect_state == "UNKNOWN"
    assert state["posts"] == 1  # Only the fixture execution; GETs never send.


async def test_summary_scopes_recoveries_and_reports_latest_run_with_partial_identities(
    invocation, session_factory, engine, migrated_url
):
    _state, execute, approval, _database_id, _source_id, spec = invocation
    result, _ = await execute()
    foreign_ids = []
    async with session_factory() as session, session.begin():
        workflow = await session.get(t.WorkflowRun, spec.workflow_id)
        workflow.workflow_type = "RealProductDraft:" + approval.run_id
        job = await session.get(t.Job, approval.repair_job_id)
        job.input = {
            **job.input,
            "notification_recovery": {
                "accepted_resource": {
                    "database_id": "https://private.invalid/secret",
                    "data_source_id": None,
                },
                "approval": {"operator_reference": "private-approval-marker"},
            },
        }
        run = await session.get(t.AgentRun, result.agent_run_id)
        run.output = {"secret": "private-output-marker"}
        values = {column.name: getattr(run, column.name) for column in t.AgentRun.__table__.columns}
        latest = t.AgentRun(
            **{
                **values,
                "id": uuid4(),
                "run_number": run.run_number + 1,
                "status": "RUNNING",
                "completed_at": None,
                "output": {},
                "started_at": datetime.now(UTC),
            }
        )
        session.add(latest)
        foreign_workflow = await make_workflow(session, await session.get(t.Shop, workflow.shop_id))
        foreign_workflow.workflow_type = "RealProductDraft:another-run"
        for parent in (workflow, foreign_workflow):
            foreign = await make_job(session, parent)
            foreign.job_type, foreign.owner_agent_id = "BuildRepairJob", "A07"
            foreign.object_type, foreign.object_id = "Product", uuid4()
            foreign_ids.extend([str(foreign.id), str(uuid4())])
            foreign.input = {
                "notification_recovery": {
                    "accepted_resource": {
                        "database_id": foreign_ids[-1],
                        "data_source_id": str(uuid4()),
                    }
                }
            }
    app = create_app()
    app.state.application = ApplicationState(
        RuntimeSettings(
            environment=RuntimeEnvironment.TEST, database=DatabaseSettings(url=migrated_url)
        ),
        engine,
        session_factory,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api") as client:
        response = await client.get(f"/operator/runs/{approval.run_id}/summary")
        assert response.status_code == 200
        proofs = response.json()["recoveries"]
        assert len(proofs) == 1
        assert proofs[0]["agent_run_id"] == str(latest.id)
        assert proofs[0]["agent_run_status"] == "RUNNING"
        assert proofs[0]["database_id"] is None and proofs[0]["data_source_id"] is None
        # The preexisting job list can contain another product's job; recovery details cannot.
        assert not any(value in str(proofs) for value in foreign_ids)
        for marker in ("private.invalid", "private-approval-marker", "private-output-marker"):
            assert marker not in response.text


async def test_summary_does_not_invent_a_run_or_effect_before_execution(
    invocation, session_factory, engine, migrated_url
):
    _state, _execute, approval, _database_id, _source_id, spec = invocation
    async with session_factory() as session, session.begin():
        workflow = await session.get(t.WorkflowRun, spec.workflow_id)
        assert workflow is not None
        workflow.workflow_type = "RealProductDraft:" + approval.run_id
    app = create_app()
    app.state.application = ApplicationState(
        RuntimeSettings(
            environment=RuntimeEnvironment.TEST, database=DatabaseSettings(url=migrated_url)
        ),
        engine,
        session_factory,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api") as client:
        response = await client.get(f"/operator/runs/{approval.run_id}/summary")
        assert response.status_code == 200
        assert response.json()["recoveries"] == [
            {
                "job_id": str(approval.repair_job_id),
                "agent_run_id": None,
                "agent_run_status": None,
                "effect_state": None,
                "database_id": None,
                "data_source_id": None,
            }
        ]


@pytest.mark.parametrize("damage", ["unrelated_write", "different_database", "missing_key"])
async def test_summary_never_confirms_an_uncorrelated_recovery(
    invocation, session_factory, engine, migrated_url, damage
):
    from sqlalchemy import update

    _state, execute, approval, database_id, _source_id, spec = invocation
    await execute()
    async with session_factory() as session, session.begin():
        workflow = await session.get(t.WorkflowRun, spec.workflow_id)
        assert workflow is not None
        workflow.workflow_type = "RealProductDraft:" + approval.run_id
        job = await session.get(t.Job, approval.repair_job_id)
        assert job is not None
        record = dict(job.input["notification_recovery"])
        if damage == "unrelated_write":
            await session.execute(
                update(t.EffectAttempt)
                .where(t.EffectAttempt.job_id == job.id)
                .values(idempotency_key="unrelated-notification-write")
            )
        elif damage == "missing_key":
            record.pop("effect_key")
        else:
            record["accepted_resource"] = {
                **record["accepted_resource"],
                "database_id": str(uuid4()),
            }
        job.input = {**job.input, "notification_recovery": record}
    app = create_app()
    app.state.application = ApplicationState(
        RuntimeSettings(
            environment=RuntimeEnvironment.TEST, database=DatabaseSettings(url=migrated_url)
        ),
        engine,
        session_factory,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api") as client:
        response = await client.get(f"/operator/runs/{approval.run_id}/summary")
        assert response.status_code == 200
        proof = response.json()["recoveries"][0]
        assert proof["agent_run_status"] == "SUCCESS"
        assert proof["effect_state"] is None
        if damage == "different_database":
            assert proof["database_id"] != database_id
