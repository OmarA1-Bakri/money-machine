"""Liveness, readiness, version and database status."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from money_machine.api.dependencies import SettingsDependency, StateDependency
from money_machine.api.schemas import (
    DatabaseStatus,
    HealthResponse,
    ReadinessResponse,
    VersionResponse,
)
from money_machine.persistence.database import check_connectivity, current_migration_revision
from money_machine.version import __version__

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report that this API process is alive. This makes no dependency claim."""
    return HealthResponse(status="ok", service="api", version=__version__)


async def _database_status(state: StateDependency) -> DatabaseStatus:
    reachable = await check_connectivity(state.engine)
    revision: str | None = None
    if reachable:
        try:
            async with state.engine.connect() as connection:
                revision = await current_migration_revision(connection)
        except Exception:  # readiness reports, it does not raise
            revision = None
    return DatabaseStatus(
        url=state.settings.database.safe_url,
        reachable=reachable,
        migration_revision=revision,
    )


@router.get("/readiness", response_model=ReadinessResponse)
async def readiness(
    state: StateDependency,
    response: Response,
) -> ReadinessResponse:
    """Report readiness, proved against the database rather than assumed.

    Returns 503 when the database is unreachable or unmigrated, so an orchestrator can
    tell "alive" from "able to serve".
    """
    database = await _database_status(state)
    ready = database.reachable and database.migration_revision is not None
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        ready=ready,
        service="api",
        version=__version__,
        environment=state.settings.environment.value,
        database=database,
    )


@router.get("/database", response_model=DatabaseStatus)
async def database(state: StateDependency) -> DatabaseStatus:
    """Report database reachability and the applied migration revision."""
    return await _database_status(state)


@router.get("/version", response_model=VersionResponse)
async def version(settings: SettingsDependency) -> VersionResponse:
    """Report build identity and the active environment."""
    return VersionResponse(version=__version__, environment=settings.environment.value)
