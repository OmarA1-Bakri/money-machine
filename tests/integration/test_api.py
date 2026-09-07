"""Operator API behaviour, including readiness that actually fails."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from money_machine.api.dependencies import ApplicationState
from money_machine.api.main import create_app
from money_machine.config.runtime import DatabaseSettings, ProviderSettings, RuntimeSettings, Secret
from money_machine.config.settings import RuntimeEnvironment
from tests.integration.factories import make_job, make_shop, make_workflow

SECRET_VALUE = "do-not-log-me"


def settings_for(url: str) -> RuntimeSettings:
    """Runtime settings pointing at one throwaway database."""
    return RuntimeSettings(
        environment=RuntimeEnvironment.TEST,
        database=DatabaseSettings(url=url),
        providers=(
            ProviderSettings(name="etsy", api_key=Secret(SECRET_VALUE)),
            ProviderSettings(name="notion"),
        ),
    )


@pytest.fixture
async def client(migrated_url: str) -> AsyncGenerator[AsyncClient]:
    """An async client bound to the app with a migrated database."""
    application = create_app()
    state = ApplicationState.create(settings_for(migrated_url))
    application.state.application = state
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://api") as active:
        yield active
    await state.dispose()


@pytest.fixture
async def unreachable_client() -> AsyncGenerator[AsyncClient]:
    """A client whose database does not exist, to prove readiness fails."""
    application = create_app()
    settings = settings_for("postgresql+asyncpg://money_machine@127.0.0.1:1/absent")
    state = ApplicationState.create(settings)
    application.state.application = state
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://api") as active:
        yield active
    await state.dispose()


async def test_health_reports_liveness_without_a_dependency_claim(client: AsyncClient) -> None:
    """Health is liveness only, as its docstring promises."""
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "api"
    assert "database" not in body


async def test_readiness_passes_on_a_migrated_database(client: AsyncClient) -> None:
    """Readiness proves the database is reachable and migrated."""
    response = await client.get("/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["database"]["reachable"] is True
    assert body["database"]["migration_revision"] is not None
    assert body["environment"] == "test"


async def test_readiness_fails_when_the_database_is_unreachable(
    unreachable_client: AsyncClient,
) -> None:
    """A readiness endpoint that cannot fail is worthless; this one returns 503."""
    response = await unreachable_client.get("/readiness")

    assert response.status_code == 503
    body = response.json()
    assert body["ready"] is False
    assert body["database"]["reachable"] is False
    assert body["database"]["migration_revision"] is None


async def test_health_still_passes_when_the_database_is_unreachable(
    unreachable_client: AsyncClient,
) -> None:
    """Liveness and readiness are different questions."""
    response = await unreachable_client.get("/health")

    assert response.status_code == 200


async def test_version_and_database_endpoints(client: AsyncClient) -> None:
    """Version and database status are typed and carry no credential."""
    version = await client.get("/version")
    database = await client.get("/database")

    assert version.status_code == 200
    assert version.json()["environment"] == "test"
    assert database.status_code == 200
    body = database.json()
    assert body["reachable"] is True
    assert "money_machine" in body["url"] or "mm_t_" in body["url"]


async def test_no_endpoint_returns_a_secret(client: AsyncClient) -> None:
    """A credential must not reach a response body, even indirectly."""
    for path in ("/health", "/readiness", "/version", "/database", "/integrations/status"):
        response = await client.get(path)
        assert SECRET_VALUE not in response.text, path


async def test_integration_status_reports_presence_only(client: AsyncClient) -> None:
    """Configured or not configured, from settings, with no provider call."""
    response = await client.get("/integrations/status")

    assert response.status_code == 200
    body = response.json()
    providers = {row["name"]: row for row in body["providers"]}
    assert providers["etsy"]["configured"] is True
    assert providers["notion"]["configured"] is False
    assert {row["effect_mode"] for row in body["providers"]} == {"simulation"}
    assert all(row["commissioned"] is False for row in body["providers"])
    assert "api_key" not in providers["etsy"]


async def test_workflow_and_job_endpoints_page_and_detail(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """List endpoints are bounded pages; detail endpoints resolve or 404."""
    async with session_factory() as session:
        shop = await make_shop(session)
        workflow = await make_workflow(session, shop)
        job = await make_job(session, workflow)
        await session.commit()
        workflow_id, job_id = workflow.id, job.id

    workflows = await client.get("/workflows", params={"limit": 10})
    jobs = await client.get("/jobs", params={"limit": 10})
    detail = await client.get(f"/workflows/{workflow_id}")
    job_detail = await client.get(f"/jobs/{job_id}")
    missing = await client.get("/workflows/00000000-0000-0000-0000-000000000000")

    assert workflows.status_code == 200
    assert workflows.json()["total"] == 1
    assert workflows.json()["items"][0]["product_state"] == "DISCOVERED"
    assert jobs.json()["items"][0]["owner_agent_id"] == "A03"
    assert detail.json()["id"] == str(workflow_id)
    assert job_detail.json()["status"] == "READY"
    assert missing.status_code == 404


async def test_list_endpoints_reject_an_unbounded_page(client: AsyncClient) -> None:
    """A caller cannot ask for an unbounded result set."""
    assert (await client.get("/jobs", params={"limit": 1000})).status_code == 422
    assert (await client.get("/jobs", params={"offset": -1})).status_code == 422
