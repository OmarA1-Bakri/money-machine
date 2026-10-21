"""Real database fixture summaries and fail-closed local artifact delivery."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from money_machine.api.dependencies import ApplicationState
from money_machine.api.main import create_app
from money_machine.persistence.tables import AgentRun, Artifact, Asset, Job, WorkflowRun
from tests.e2e.test_operator_api import operator_state as operator_state
from tests.e2e.test_operator_api import seed_product, seed_views
from tests.integration.factories import make_artifact, make_job

RUN_ID = "20261020T211445Z"


async def seed_proof(
    state: ApplicationState,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], Artifact, Path, bytes]:
    monkeypatch.setenv("MONEY_MACHINE_EVIDENCE_ROOT", str(root))
    rows = await seed_views(state.session_factory)
    content = b"<!doctype html><h1>Actual fixture template</h1>"
    path = root / RUN_ID / "e2e" / "product.html"
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    async with state.session_factory() as session:
        workflow = await session.get(WorkflowRun, rows["now"].workflow_id)
        assert workflow is not None
        job = await make_job(session, workflow)
        job.job_type = "DraftListingJob"
        from sqlalchemy import select

        producing_job = await session.get(Job, rows["pipeline"].id)
        run = await session.scalar(select(AgentRun).where(AgentRun.job_id == rows["pipeline"].id))
        assert producing_job is not None and run is not None
        artifact = await make_artifact(
            session, producing_job, run, logical_role=f"fixture:{RUN_ID}:product"
        )
        artifact.media_type = "application/octet-stream"
        artifact.byte_size = len(content)
        artifact.sha256 = hashlib.sha256(content).hexdigest()
        artifact.storage_reference = str(path)
        session.add(
            Asset(
                id=uuid4(),
                product_id=rows["now"].id,
                artifact_id=artifact.id,
                asset_role="product_html",
                ordinal=0,
            )
        )
        await session.commit()
    return rows, artifact, path, content


def client_for(state: ApplicationState) -> AsyncClient:
    app = create_app()
    app.state.application = state
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://api")


async def test_summary_reports_only_persisted_completion_and_actual_rows(
    operator_state: ApplicationState,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows, artifact, _path, content = await seed_proof(operator_state, tmp_path, monkeypatch)
    foreign_id = await seed_product(operator_state.session_factory, "another-run")
    async with client_for(operator_state) as client:
        response = await client.get(f"/operator/runs/{RUN_ID}/summary")
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "run_id",
            "workflow_id",
            "product_id",
            "listing_version_id",
            "product_title",
            "fixture_completed",
            "completed_at",
            "product_state",
            "jobs",
            "artifacts",
        }
        assert body["run_id"] == RUN_ID
        assert body["workflow_id"] == str(rows["now"].workflow_id)
        assert body["product_id"] == str(rows["now"].id)
        assert body["listing_version_id"] == str(rows["shop"].id)
        assert body["product_title"] == "Stored planner"
        assert body["product_state"] == "DISCOVERED"
        assert body["fixture_completed"] is False
        assert body["completed_at"] is None
        assert {job["status"] for job in body["jobs"]} == {"READY", "BLOCKED"}
        assert any(job["job_type"] == "DraftListingJob" for job in body["jobs"])
        assert body["artifacts"] == [
            {
                "id": str(artifact.id),
                "label": artifact.logical_role,
                "kind": "product_html",
                "media_type": "text/html",
                "byte_size": len(content),
                "href": f"/operator/runs/{RUN_ID}/artifacts/{artifact.id}",
            }
        ]
        assert foreign_id not in response.text
        assert str(tmp_path) not in response.text
        async with operator_state.session_factory() as session:
            workflow = await session.get(WorkflowRun, rows["now"].workflow_id)
            assert workflow is not None
            workflow.completed_at = datetime(2026, 10, 22, tzinfo=UTC)
            await session.commit()
        completed = (await client.get(f"/operator/runs/{RUN_ID}/summary")).json()
        assert completed["fixture_completed"] is True
        assert completed["completed_at"].startswith("2026-10-22T00:00:00")
        assert completed["product_state"] == "DISCOVERED"
        assert (await client.get("/operator/runs/missing/summary")).status_code == 404


async def test_artifact_returns_verified_bytes_inert_html_and_scopes_run(
    operator_state: ApplicationState,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _rows, artifact, _path, content = await seed_proof(operator_state, tmp_path, monkeypatch)
    await seed_product(operator_state.session_factory, "another-run")
    async with client_for(operator_state) as client:
        response = await client.get(f"/operator/runs/{RUN_ID}/artifacts/{artifact.id}")
        assert response.status_code == 200
        assert response.content == content
        assert response.headers["content-type"].startswith("text/html")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["cache-control"] == "no-store"
        csp = response.headers["content-security-policy"]
        assert "sandbox;" in csp and "default-src 'none'" in csp
        assert "form-action 'none'" in csp and "base-uri 'none'" in csp
        assert "allow-scripts" not in csp
        assert (
            await client.get(f"/operator/runs/another-run/artifacts/{artifact.id}")
        ).status_code == 404
        assert (await client.get(f"/operator/runs/{RUN_ID}/artifacts/{uuid4()}")).status_code == 404


@pytest.mark.parametrize(
    "damage", ["hash", "length", "missing", "escape", "symlink", "parent_symlink", "scheme"]
)
async def test_artifacts_reject_tampering_and_path_escapes(
    operator_state: ApplicationState,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    _rows, artifact, path, content = await seed_proof(operator_state, tmp_path, monkeypatch)
    if damage == "hash":
        path.write_bytes(b"x" * len(content))
    elif damage == "length":
        path.write_bytes(content + b"x")
    elif damage == "missing":
        path.unlink()
    elif damage == "symlink":
        outside = tmp_path / "outside.html"
        outside.write_bytes(content)
        path.unlink()
        path.symlink_to(outside)
    elif damage == "parent_symlink":
        relocated = tmp_path / "relocated"
        path.parent.rename(relocated)
        path.parent.symlink_to(relocated, target_is_directory=True)
    else:
        outside = tmp_path / "outside.html"
        outside.write_bytes(content)
        async with operator_state.session_factory() as session:
            stored = await session.get(Artifact, artifact.id)
            assert stored is not None
            stored.storage_reference = str(outside) if damage == "escape" else path.as_uri()
            await session.commit()
    async with client_for(operator_state) as client:
        response = await client.get(f"/operator/runs/{RUN_ID}/artifacts/{artifact.id}")
        assert response.status_code == 409
        assert response.json() == {"detail": "fixture artifact unavailable or changed"}
        assert str(tmp_path) not in response.text


@pytest.mark.parametrize(
    ("role", "media_type", "content"),
    [
        ("delivery_pdf", "application/pdf", b"%PDF-1.7\nfixture bytes"),
        ("listing_image", "image/png", b"\x89PNG\r\n\x1a\nfixture bytes"),
        ("walkthrough", "video/mp4", b"fixture video bytes"),
    ],
)
async def test_artifact_serves_persisted_delivery_and_media_types(
    operator_state: ApplicationState,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    media_type: str,
    content: bytes,
) -> None:
    from sqlalchemy import select

    _rows, artifact, path, _original = await seed_proof(operator_state, tmp_path, monkeypatch)
    path.write_bytes(content)
    async with operator_state.session_factory() as session:
        stored = await session.get(Artifact, artifact.id)
        asset = await session.scalar(select(Asset).where(Asset.artifact_id == artifact.id))
        assert stored is not None and asset is not None
        stored.media_type = media_type
        stored.byte_size = len(content)
        stored.sha256 = hashlib.sha256(content).hexdigest()
        asset.asset_role = role
        await session.commit()
    async with client_for(operator_state) as client:
        response = await client.get(f"/operator/runs/{RUN_ID}/artifacts/{artifact.id}")
        assert response.status_code == 200
        assert response.content == content
        assert response.headers["content-type"] == media_type
        summary = (await client.get(f"/operator/runs/{RUN_ID}/summary")).json()
        assert summary["artifacts"][0]["kind"] == role
        assert summary["artifacts"][0]["media_type"] == media_type
