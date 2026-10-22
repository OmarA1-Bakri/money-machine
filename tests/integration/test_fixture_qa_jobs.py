"""Persisted repair/retest events, real identity lineage and crash reconciliation."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.application.fixture_provider import durable_probe
from money_machine.persistence import tables as t
from money_machine.persistence.seed import seed
from money_machine.persistence.unit_of_work import UnitOfWork
from tests.integration.factories import make_job, make_shop, make_workflow
from tests.unit.agents.test_notion_formula_repair import prepare_variants
from tests.unit.agents.test_notion_product_qa import QA_AT, planner_spec


async def setup_build(session: AsyncSession, tmp_path: Path):
    await seed(session, repository_root=Path.cwd())
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(session, workflow)
    job.job_type, job.owner_agent_id = "ProductBuildJob", "A07"
    spec = planner_spec().model_copy(update={"workflow_id": workflow.id})
    job.object_type, job.object_id, job.status = "products", spec.product_id, "SUCCEEDED"
    probe = durable_probe(tmp_path / "fixture.json")
    path = tmp_path / "build.json"
    await prepare_variants(spec, probe, path)
    db, prop = next(
        (db, p) for db in probe.databases.values() for p in db.properties if p.type == "formula"
    )
    original = prop.config["formula"].expression
    await probe.update_formula(db.id, prop.id, "length(prop('Title'))")
    await session.commit()
    return spec, job, probe, path, db.id, prop.id, original


@pytest.mark.parametrize("interrupt", [False, True])
async def test_durable_formula_repair_retests_and_replays_without_duplicates(
    session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interrupt: bool
) -> None:
    from money_machine.application.fixture_qa_jobs import run_fixture_qa_jobs

    spec, build, probe, path, db_id, prop_id, expected = await setup_build(session, tmp_path)
    ids = (set(probe.pages), set(probe.databases))
    writes = []
    original = probe.update_formula

    async def update(*args):
        writes.append(args)
        result = await original(*args)
        if interrupt and len(writes) == 1:
            raise RuntimeError("simulated response loss after durable write")
        return result

    monkeypatch.setattr(probe, "update_formula", update)
    uow = UnitOfWork(session)
    if interrupt:
        with pytest.raises(ValueError, match="fixture repair interrupted"):
            await run_fixture_qa_jobs(uow, build, spec, probe, path, recorded_at=QA_AT)
        await session.rollback()
        # The provider persisted the write; re-open it as a restarted process would.
        probe = durable_probe(tmp_path / "fixture.json")
        monkeypatch.setattr(probe, "update_formula", update)

    result = await run_fixture_qa_jobs(uow, build, spec, probe, path, recorded_at=QA_AT)
    await session.commit()
    assert result.qa is not None and result.qa.verdict == "PASS"
    assert all(ok for _, ok in result.qa.checks)
    found = next(p for p in probe.databases[db_id].properties if p.id == prop_id)
    assert found.config["formula"].expression == expected
    assert len(writes) == 1
    assert set(probe.databases) == ids[1]
    assert len(set(probe.pages) - ids[0]) == 1  # Only the existing QA duplicate proof.

    jobs = list(
        (await session.scalars(select(t.Job).where(t.Job.workflow_id == build.workflow_id))).all()
    )
    assert [j.job_type for j in jobs].count("BuildRepairJob") == 1
    assert [j.job_type for j in jobs].count("ProductQAJob") == 2
    events = list(
        (
            await session.scalars(select(t.Event).where(t.Event.workflow_id == build.workflow_id))
        ).all()
    )
    names = [e.event_name for e in events]
    assert names.count("BUILD_QA_FAILED") == names.count("REPAIR_APPLIED") == 1
    assert names.count("REPAIR_COMPLETED") == names.count("BUILD_QA_PASSED") == 1
    traces = json.loads(path.read_text())["provider_object_references"]["qa_executions"]
    assert len([r for r in traces if r["job_type"] == "ProductQAJob"]) == 2
    for trace in traces:
        run = await session.get(t.AgentRun, trace["agent_run_id"])
        assert run is not None
        job = await session.get(t.Job, run.job_id)
        assert job is not None and str(job.id) == trace["job_id"]
        assert trace["parent_job_id"] == job.input["parent_job_id"]
        assert trace["agent_definition_id"] == str(run.agent_definition_id)
        assert trace["prompt_sha256"] == run.prompt_sha256
        assert trace["identity_registry"] == "money_machine.agent_definitions"
        assert trace["thredos_registration"] == "unverified"
    receipts = list((await session.scalars(select(t.Receipt))).all())
    assert len(receipts) == 1 and receipts[0].provider == "notion_fixture"

    await run_fixture_qa_jobs(uow, build, spec, probe, path, recorded_at=QA_AT)
    await session.commit()
    assert len(writes) == 1
    assert len(
        (await session.scalars(select(t.Job).where(t.Job.workflow_id == build.workflow_id))).all()
    ) == len(jobs)
    assert len(
        (
            await session.scalars(select(t.Event).where(t.Event.workflow_id == build.workflow_id))
        ).all()
    ) == len(events)


async def test_unrelated_structural_damage_does_not_get_formula_repair(
    session: AsyncSession, tmp_path: Path
) -> None:
    from money_machine.application.fixture_qa_jobs import run_fixture_qa_jobs

    spec, build, probe, path, db_id, _, _ = await setup_build(session, tmp_path)
    probe.databases[db_id] = replace(probe.databases[db_id], title="Unexpected database")
    result = await run_fixture_qa_jobs(
        UnitOfWork(session), build, spec, probe, path, recorded_at=QA_AT
    )
    assert result.qa is not None and result.qa.verdict == "BLOCKED"
    assert not (
        await session.scalars(select(t.Job).where(t.Job.job_type == "BuildRepairJob"))
    ).all()


@pytest.mark.parametrize("damage", ["unchanged_formula", "new_structural_defect"])
async def test_repair_cannot_complete_without_fresh_passing_readback(
    session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    from money_machine.application.fixture_qa_jobs import run_fixture_qa_jobs

    spec, build, probe, path, db_id, prop_id, _ = await setup_build(session, tmp_path)
    original = probe.update_formula

    async def broken_update(*args):
        if damage == "unchanged_formula":
            return next(p for p in probe.databases[db_id].properties if p.id == prop_id).config[
                "formula"
            ]
        result = await original(*args)
        probe.databases[db_id].title = "Unexpected database"
        return result

    monkeypatch.setattr(probe, "update_formula", broken_update)
    if damage == "unchanged_formula":
        with pytest.raises(ValueError, match="fixture repair interrupted"):
            await run_fixture_qa_jobs(
                UnitOfWork(session), build, spec, probe, path, recorded_at=QA_AT
            )
    else:
        result = await run_fixture_qa_jobs(
            UnitOfWork(session), build, spec, probe, path, recorded_at=QA_AT
        )
        assert result.qa is not None and result.qa.verdict == "BLOCKED"
    events = (await session.scalars(select(t.Event))).all()
    assert not any(e.event_name in {"REPAIR_COMPLETED", "BUILD_QA_PASSED"} for e in events)
    if damage == "unchanged_formula":
        assert not any(e.event_name == "REPAIR_APPLIED" for e in events)


async def test_repair_retries_after_failure_before_write(
    session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from money_machine.application.fixture_qa_jobs import run_fixture_qa_jobs

    spec, build, probe, path, _, _, _ = await setup_build(session, tmp_path)
    original = probe.update_formula
    attempts = []

    async def interrupted_update(*args):
        attempts.append(args)
        if len(attempts) == 1:
            raise RuntimeError("fixture failure before write")
        return await original(*args)

    monkeypatch.setattr(probe, "update_formula", interrupted_update)
    with pytest.raises(ValueError, match="fixture repair interrupted"):
        await run_fixture_qa_jobs(UnitOfWork(session), build, spec, probe, path, recorded_at=QA_AT)
    result = await run_fixture_qa_jobs(
        UnitOfWork(session), build, spec, probe, path, recorded_at=QA_AT
    )
    assert result.qa is not None and result.qa.verdict == "PASS"
    assert len(attempts) == 2
    assert len((await session.scalars(select(t.Receipt))).all()) == 1


async def test_fixture_repair_retry_budget_is_bounded(
    session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from money_machine.application.fixture_qa_jobs import run_fixture_qa_jobs

    spec, build, probe, path, _, _, _ = await setup_build(session, tmp_path)
    attempts = []

    async def fail(*args):
        attempts.append(args)
        raise RuntimeError("fixture unavailable")

    monkeypatch.setattr(probe, "update_formula", fail)
    for _ in range(3):
        with pytest.raises(ValueError, match="fixture repair interrupted"):
            await run_fixture_qa_jobs(
                UnitOfWork(session), build, spec, probe, path, recorded_at=QA_AT
            )
    with pytest.raises(ValueError, match="retry budget exhausted"):
        await run_fixture_qa_jobs(UnitOfWork(session), build, spec, probe, path, recorded_at=QA_AT)
    assert len(attempts) == 3
    repair = (await session.scalars(select(t.Job).where(t.Job.job_type == "BuildRepairJob"))).one()
    assert repair.attempt == repair.max_attempts == 3
    assert repair.status == "TERMINAL_FAILURE"


async def test_corrected_blocked_qa_is_retested(session: AsyncSession, tmp_path: Path) -> None:
    from money_machine.application.fixture_qa_jobs import run_fixture_qa_jobs

    spec, build, probe, path, db_id, _, _ = await setup_build(session, tmp_path)
    title = probe.databases[db_id].title
    probe.databases[db_id].title = "Unexpected database"
    result = await run_fixture_qa_jobs(
        UnitOfWork(session), build, spec, probe, path, recorded_at=QA_AT
    )
    assert result.qa is not None and result.qa.verdict == "BLOCKED"
    probe.databases[db_id].title = title
    result = await run_fixture_qa_jobs(
        UnitOfWork(session), build, spec, probe, path, recorded_at=QA_AT
    )
    assert result.qa is not None and result.qa.verdict == "PASS"
    assert not (
        await session.scalars(
            select(t.Job).where(
                t.Job.workflow_id == build.workflow_id, t.Job.status.in_(["PENDING", "RUNNING"])
            )
        )
    ).all()


async def test_confirmed_repair_is_not_repeated_after_checkpoint_failure_and_drift(
    session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from money_machine.application import fixture_qa_jobs as module

    spec, build, probe, path, db_id, prop_id, _ = await setup_build(session, tmp_path)
    original = probe.update_formula
    writes = []

    async def update(*args):
        writes.append(args)
        return await original(*args)

    def fail_record(*args):
        raise OSError("fixture checkpoint write failed")

    monkeypatch.setattr(probe, "update_formula", update)
    with monkeypatch.context() as patch:
        patch.setattr(module, "record_applied_repairs", fail_record)
        with pytest.raises(ValueError, match="fixture repair interrupted"):
            await module.run_fixture_qa_jobs(
                UnitOfWork(session), build, spec, probe, path, recorded_at=QA_AT
            )
    assert len((await session.scalars(select(t.Receipt))).all()) == 1
    prop = next(p for p in probe.databases[db_id].properties if p.id == prop_id)
    prop.config["formula"] = replace(prop.config["formula"], expression="length(prop('Title'))")
    with pytest.raises(ValueError, match="fixture repair interrupted"):
        await module.run_fixture_qa_jobs(
            UnitOfWork(session), build, spec, probe, path, recorded_at=QA_AT
        )
    assert len(writes) == 1


async def test_failed_terminal_commit_keeps_existing_lease_and_no_orphan_trace(
    session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from money_machine.application.fixture_qa_jobs import run_fixture_qa_jobs

    spec, build, probe, path, _, _, _ = await setup_build(session, tmp_path)
    original = probe.update_formula
    writes = []

    async def update(*args):
        writes.append(args)
        return await original(*args)

    monkeypatch.setattr(probe, "update_formula", update)
    uow = UnitOfWork(session)
    commit = uow.commit
    failed = False

    async def interrupted_commit():
        nonlocal failed
        repair = (
            await session.scalars(
                select(t.Job).where(t.Job.job_type == "BuildRepairJob", t.Job.status == "SUCCEEDED")
            )
        ).one_or_none()
        if repair is not None and not failed:
            failed = True
            raise RuntimeError("fixture terminal commit failed")
        await commit()

    with monkeypatch.context() as patch:
        patch.setattr(uow, "commit", interrupted_commit)
        with pytest.raises(RuntimeError, match="fixture terminal commit failed"):
            await run_fixture_qa_jobs(uow, build, spec, probe, path, recorded_at=QA_AT)
    await session.rollback()
    await session.refresh(build)
    with pytest.raises(ValueError, match="requires existing lease recovery"):
        await run_fixture_qa_jobs(uow, build, spec, probe, path, recorded_at=QA_AT)
    assert len(writes) == 1
    assert not (await session.scalars(select(t.Receipt))).all()
    traces = json.loads(path.read_text())["provider_object_references"]["qa_executions"]
    for trace in traces:
        assert await session.get(t.AgentRun, trace["agent_run_id"]) is not None
