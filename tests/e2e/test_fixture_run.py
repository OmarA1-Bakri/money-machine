"""The explicit fixture command must produce real persisted bytes."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.integration.alembic_support import upgrade


async def test_fixture_command_writes_verified_bundle(tmp_path: Path, test_database: str) -> None:
    upgrade(test_database, Path.cwd())
    env = dict(
        os.environ,
        APP_ENV="test",
        MONEY_MACHINE_DATABASE_URL=test_database,
        MONEY_MACHINE_RUN_ID="test-fixture-bundle",
        MONEY_MACHINE_EVIDENCE_ROOT=str(tmp_path),
    )
    completed = subprocess.run(
        ["bash", "scripts/e2e.sh", "--fixture"], env=env, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    ids = json.loads((tmp_path / "test-fixture-bundle" / "ids.json").read_text())
    assert ids["product_id"] and ids["listing_version_id"]
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine

    from money_machine.persistence.tables import AgentRun, Job, ListingVersionArtifact

    engine = create_async_engine(test_database)
    try:
        async with engine.connect() as connection:
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
    replay = subprocess.run(
        ["bash", "scripts/e2e.sh", "--fixture"], env=env, capture_output=True, text=True
    )
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == ids
    assert (bundle / "receipts.jsonl").read_bytes() == before
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
