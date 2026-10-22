"""The explicit fixture command must produce real persisted bytes."""

import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from money_machine.application.fixture_run import FixtureRun
from tests.integration.alembic_support import upgrade


def test_fixture_run_resolves_relative_evidence_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    run = FixtureRun("relative-root", Path("relative-evidence"))
    assert run.directory.is_absolute()
    assert run.directory == tmp_path / "relative-evidence" / "relative-root" / "e2e"
    assert run.directory.is_dir()


async def test_fixture_command_writes_verified_bundle(tmp_path: Path, test_database: str) -> None:
    upgrade(test_database, Path.cwd())
    env = dict(
        os.environ,
        APP_ENV="test",
        MONEY_MACHINE_DATABASE_URL=test_database,
        MONEY_MACHINE_RUN_ID="test-fixture-bundle",
        MONEY_MACHINE_EVIDENCE_ROOT=os.path.relpath(tmp_path),
    )
    completed = subprocess.run(
        ["bash", "scripts/e2e.sh", "--fixture"], env=env, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    ids = json.loads((tmp_path / "test-fixture-bundle" / "ids.json").read_text())
    assert ids["product_id"] and ids["listing_version_id"]
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine

    from money_machine.persistence.tables import (
        AgentRun,
        Artifact,
        Job,
        ListingVersionArtifact,
        WorkflowRun,
    )

    engine = create_async_engine(test_database)
    try:
        async with engine.connect() as connection:
            workflow = (
                await connection.execute(
                    select(WorkflowRun.completed_at, WorkflowRun.product_state).where(
                        WorkflowRun.id == ids["workflow_id"]
                    )
                )
            ).one()
            assert workflow.completed_at is not None
            assert workflow.product_state == "DISCOVERED"
            draft_jobs = (
                (
                    await connection.execute(
                        select(Job.status).where(
                            Job.workflow_id == ids["workflow_id"], Job.job_type == "DraftListingJob"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert draft_jobs == ["READY"]
            outputs = (
                (
                    await connection.execute(
                        select(AgentRun.output)
                        .join(Job, AgentRun.job_id == Job.id)
                        .where(Job.workflow_id == ids["workflow_id"])
                    )
                )
                .scalars()
                .all()
            )
            membership = (
                await connection.execute(
                    select(ListingVersionArtifact.role, ListingVersionArtifact.artifact_id).where(
                        ListingVersionArtifact.listing_version_id == ids["listing_version_id"]
                    )
                )
            ).all()
            storage_references = (
                (
                    await connection.execute(
                        select(Artifact.storage_reference)
                        .join(
                            ListingVersionArtifact,
                            ListingVersionArtifact.artifact_id == Artifact.id,
                        )
                        .where(
                            ListingVersionArtifact.listing_version_id == ids["listing_version_id"]
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(storage_references) == 13
            assert all(Path(reference).is_absolute() for reference in storage_references)
            assert all(Path(reference).is_file() for reference in storage_references)
            assert len(membership) == 13
            assert len({row.artifact_id for row in membership}) == 13
            assert sorted(row.role for row in membership) == sorted(
                ["listing_image"] * 10 + ["listing_video", "delivery_pdf", "free_gift_pdf"]
            )
            assert outputs
            assert all(
                output["execution_kind"] == "deterministic_fixture_library" for output in outputs
            )
            assert all(output["prompt_used"] is False for output in outputs)
    finally:
        await engine.dispose()
    bundle = tmp_path / "test-fixture-bundle" / "e2e"
    rows = [json.loads(line) for line in (bundle / "lineage.jsonl").read_text().splitlines()]
    assert len([row for row in rows if row["kind"] == "listing_image"]) == 10
    assert any(row["relative_path"].endswith(".mp4") for row in rows)
    import hashlib

    for row in rows:
        value = (bundle / row["relative_path"]).read_bytes()
        assert len(value) == row["byte_size"] > 0
        assert hashlib.sha256(value).hexdigest() == row["sha256"]

    before = (bundle / "receipts.jsonl").read_bytes()
    receipts_hash = hashlib.sha256(before).hexdigest()
    env["MONEY_MACHINE_EVIDENCE_ROOT"] = str(tmp_path.resolve())
    replay = subprocess.run(
        ["bash", "scripts/e2e.sh", "--fixture"], env=env, capture_output=True, text=True
    )
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == ids
    assert (bundle / "receipts.jsonl").read_bytes() == before
    assert hashlib.sha256((bundle / "receipts.jsonl").read_bytes()).hexdigest() == receipts_hash
    assert len(json.loads((bundle / "fixture-marketplace.json").read_text())) == 1
    target = bundle / rows[0]["relative_path"]
    original = target.read_bytes()
    target.write_bytes(original + b"tampered")
    refused = subprocess.run(
        ["bash", "scripts/e2e.sh", "--fixture"], env=env, capture_output=True, text=True
    )
    assert refused.returncode != 0 and "artifact bytes changed" in refused.stderr
    target.write_bytes(original)
    target.rename(target.with_suffix(".held"))
    missing = subprocess.run(
        ["bash", "scripts/e2e.sh", "--fixture"], env=env, capture_output=True, text=True
    )
    assert missing.returncode != 0 and "FileNotFoundError" in missing.stderr
    target.with_suffix(".held").rename(target)


def test_default_remains_uncommissioned() -> None:
    completed = subprocess.run(["bash", "scripts/e2e.sh"], capture_output=True, text=True)
    assert completed.returncode == 78
    assert "uncommissioned" in completed.stderr


@pytest.mark.parametrize("boundary", ["render", "draft"])
async def test_crash_after_render_reconciles_without_duplicate_draft(
    tmp_path: Path, test_database: str, boundary: str
) -> None:
    upgrade(test_database, Path.cwd())
    env = dict(
        os.environ,
        APP_ENV="test",
        MONEY_MACHINE_DATABASE_URL=test_database,
        MONEY_MACHINE_RUN_ID="test-render-restart",
        MONEY_MACHINE_EVIDENCE_ROOT=str(tmp_path),
        MONEY_MACHINE_FIXTURE_INTERRUPT_AFTER=boundary,
    )
    interrupted = subprocess.run(
        ["bash", "scripts/e2e.sh", "--fixture"], env=env, capture_output=True, text=True
    )
    assert interrupted.returncode != 0 and "intentional fixture interruption" in interrupted.stderr
    bundle = tmp_path / env["MONEY_MACHINE_RUN_ID"] / "e2e"
    manifest = (bundle / "lineage.jsonl").read_bytes()
    env.pop("MONEY_MACHINE_FIXTURE_INTERRUPT_AFTER")
    completed = subprocess.run(
        ["bash", "scripts/e2e.sh", "--fixture"], env=env, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr
    assert (bundle / "lineage.jsonl").read_bytes() == manifest
    assert len(json.loads((bundle / "fixture-marketplace.json").read_text())) == 1
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import create_async_engine

    from money_machine.persistence import tables as t

    ids = json.loads(completed.stdout)
    engine = create_async_engine(test_database)
    try:
        async with engine.connect() as connection:
            workflow = (
                await connection.execute(
                    select(t.WorkflowRun.completed_at, t.WorkflowRun.product_state).where(
                        t.WorkflowRun.id == ids["workflow_id"]
                    )
                )
            ).one()
            assert workflow.completed_at is not None
            assert workflow.product_state == "DISCOVERED"
            jobs = (
                await connection.execute(
                    select(t.Job.job_type, t.Job.status).where(
                        t.Job.workflow_id == ids["workflow_id"]
                    )
                )
            ).all()
            assert (
                sum(job.job_type == "DraftListingJob" and job.status == "READY" for job in jobs)
                == 1
            )
            assert (
                sum(
                    job.job_type == "ExpectedFixtureNegativeJob" and job.status == "BLOCKED"
                    for job in jobs
                )
                == 1
            )
            tables = (
                t.EtsyListing,
                t.ListingVersion,
                t.Event,
                t.Incident,
                t.Decision,
                t.DecisionEvidence,
                t.IntegrationAccount,
            )
            counts = [
                (await connection.execute(select(func.count()).select_from(table))).scalar_one()
                for table in tables
            ]
            assert counts == [1, 1, 3, 1, 1, 1, 1]
            assert sorted(
                (await connection.execute(select(t.Event.event_name))).scalars().all()
            ) == ["ASSETS_COMPLETED", "BUILD_COMPLETED", "BUILD_QA_PASSED"]
        receipts = (bundle / "receipts.jsonl").read_bytes()
        stages = [json.loads(line)["stage"] for line in receipts.splitlines()]
        assert len(stages) == len(set(stages))
        assert {"fixture_etsy_draft", "expected_negative"}.issubset(stages)
        replay = subprocess.run(
            ["bash", "scripts/e2e.sh", "--fixture"], env=env, capture_output=True, text=True
        )
        assert replay.returncode == 0, replay.stderr
        assert json.loads(replay.stdout) == ids
        assert (bundle / "receipts.jsonl").read_bytes() == receipts
        assert len(json.loads((bundle / "fixture-marketplace.json").read_text())) == 1
        async with engine.connect() as connection:
            assert [
                (await connection.execute(select(func.count()).select_from(table))).scalar_one()
                for table in tables
            ] == counts
            assert (
                await connection.execute(
                    select(t.WorkflowRun.completed_at).where(t.WorkflowRun.id == ids["workflow_id"])
                )
            ).scalar_one() == workflow.completed_at
    finally:
        await engine.dispose()


def test_live_mode_is_refused_before_evidence(tmp_path: Path) -> None:
    env = dict(
        os.environ,
        APP_ENV="test",
        MONEY_MACHINE_EFFECT_MODE="live",
        MONEY_MACHINE_EVIDENCE_ROOT=str(tmp_path),
    )
    result = subprocess.run(
        ["bash", "scripts/e2e.sh", "--fixture"], env=env, capture_output=True, text=True
    )
    assert result.returncode != 0 and "refuses live/provider mode" in result.stderr
    assert list(tmp_path.iterdir()) == []


async def test_partial_render_refuses_existing_different_video(
    tmp_path: Path, test_database: str
) -> None:
    upgrade(test_database, Path.cwd())
    run_id = "test-partial-video"
    bundle = tmp_path / run_id / "e2e"
    bundle.mkdir(parents=True)
    target = bundle / "walkthrough.mp4"
    original = b"preserve prior partial-render evidence"
    target.write_bytes(original)
    env = dict(
        os.environ,
        APP_ENV="test",
        MONEY_MACHINE_DATABASE_URL=test_database,
        MONEY_MACHINE_RUN_ID=run_id,
        MONEY_MACHINE_EVIDENCE_ROOT=str(tmp_path),
    )
    completed = subprocess.run(
        ["bash", "scripts/e2e.sh", "--fixture"], env=env, capture_output=True, text=True
    )
    assert completed.returncode != 0
    assert "refuse replacing existing artifact: walkthrough.mp4" in completed.stderr
    assert target.read_bytes() == original


async def test_malformed_rendered_pdf_is_refused_before_fixture_draft(
    tmp_path: Path, test_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import create_async_engine

    from money_machine.assets import fixture_bundle
    from money_machine.persistence import tables as t

    upgrade(test_database, Path.cwd())
    original_renderer = fixture_bundle.render_readme_pdf

    def malformed_renderer(*args, **kwargs):
        rendered = original_renderer(*args, **kwargs)
        assert b"/Type /Catalog" in rendered.pdf
        mutated = rendered.pdf.replace(b"/Type /Catalog", b"/Evil /Catalog", 1)
        return replace(rendered, pdf=mutated)

    monkeypatch.setattr(fixture_bundle, "render_readme_pdf", malformed_renderer)
    run = FixtureRun("malformed-export", tmp_path)
    with pytest.raises(ValueError, match="pdf catalog keys"):
        await run.execute(test_database)
    assert not (run.directory / "fixture-marketplace.json").exists()
    engine = create_async_engine(test_database)
    try:
        async with engine.connect() as connection:
            assert (
                await connection.execute(select(func.count()).select_from(t.EtsyListing))
            ).scalar_one() == 0
            assert (
                await connection.execute(
                    select(func.count())
                    .select_from(t.Job)
                    .where(t.Job.job_type == "DraftListingJob")
                )
            ).scalar_one() == 0
            assert (
                await connection.execute(
                    select(t.WorkflowRun.completed_at).where(
                        t.WorkflowRun.id == run.key("workflow")
                    )
                )
            ).scalar_one() is None
    finally:
        await engine.dispose()
