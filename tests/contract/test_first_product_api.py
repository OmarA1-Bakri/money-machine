from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from money_machine.agents.runtime import FirstProductRuntime
from money_machine.api.main import create_app
from money_machine.application.services.research_service import ResearchService
from money_machine.persistence.database import Database
from money_machine.persistence.tables import listing_packages, product_specs
from money_machine.persistence.unit_of_work import UnitOfWork

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "research" / "valid_packet_30.json"


def _assert_no_absolute_paths(value: object) -> None:
    if isinstance(value, str):
        assert not value.startswith("/")
        assert not (len(value) > 2 and value[1:3] in {":\\", ":/"})
        assert not value.startswith("\\\\")
    elif isinstance(value, Mapping):
        for key, nested in cast(Mapping[object, object], value).items():
            assert key not in {"root_artifact_path", "lease_owner", "lease_token"}
            _assert_no_absolute_paths(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in cast(Sequence[object], value):
            _assert_no_absolute_paths(nested)


@pytest.mark.skipif(
    "MONEY_MACHINE_TEST_DATABASE_URL" not in os.environ,
    reason="requires isolated PostgreSQL contract database",
)
def test_first_product_api_is_read_only_redacted_and_repository_backed(tmp_path: Path) -> None:
    async def scenario() -> None:
        database_url = os.environ["MONEY_MACHINE_TEST_DATABASE_URL"]
        config = Config(str(REPO_ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", database_url)
        await asyncio.to_thread(command.downgrade, config, "base")
        await asyncio.to_thread(command.upgrade, config, "head")
        database = Database.from_url(database_url)
        packet = ResearchService().import_packet(
            FIXTURE,
            now=datetime(2026, 8, 10, tzinfo=UTC),
        )
        async with UnitOfWork(database) as uow:
            await uow.research.add_packet(packet)
        runtime = FirstProductRuntime(
            database,
            artifact_root=tmp_path / "artifacts",
            config_root=REPO_ROOT / "config",
            worker_id="contract-api-worker",
        )
        workflow_id = await runtime.start(packet.packet_id)
        results = await runtime.drain(max_jobs=20)
        assert results[-1].status == "idle"
        async with database.session_factory() as session:
            product_spec_id = await session.scalar(select(product_specs.c.product_spec_id))
            listing_package_id = await session.scalar(select(listing_packages.c.listing_package_id))
        assert product_spec_id is not None
        assert listing_package_id is not None

        app = create_app(database=database)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            workflow = await client.get(f"/workflows/{workflow_id}")
            jobs = await client.get(f"/workflows/{workflow_id}/jobs")
            product = await client.get(f"/products/{product_spec_id}")
            listing = await client.get(f"/listings/{listing_package_id}")
            missing = await client.get(f"/workflows/{UUID(int=0)}")
            malformed = await client.get("/workflows/not-a-uuid")
            denied = await client.post(f"/workflows/{workflow_id}")
            openapi = (await client.get("/openapi.json")).json()

        success_statuses = {
            workflow.status_code,
            jobs.status_code,
            product.status_code,
            listing.status_code,
        }
        assert success_statuses == {200}
        assert missing.status_code == 404
        assert malformed.status_code == 422
        assert denied.status_code == 405
        assert workflow.json()["state"] == "DRAFT_READY"
        assert len(jobs.json()) == 8
        assert len(listing.json()["listing_images"]) == 10
        assert listing.json()["preview_video"]["media_type"] == "video/mp4"
        for response in (workflow, jobs, product, listing):
            _assert_no_absolute_paths(response.json())
        for path, operations in openapi["paths"].items():
            if path.startswith(("/workflows", "/products", "/listings")):
                assert set(operations) == {"get"}
        await database.dispose()

    asyncio.run(scenario())
