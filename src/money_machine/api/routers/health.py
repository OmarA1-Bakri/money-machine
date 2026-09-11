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
from money_machine.persistence.database import (
    check_connectivity,
    current_migration_revisions,
    schema_is_current,
)
from money_machine.version import __version__

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report that this API process is alive. This makes no dependency claim."""
    return HealthResponse(status="ok", service="api", version=__version__)


async def _database_status(state: StateDependency) -> DatabaseStatus:
    reachable = await check_connectivity(state.engine)
    revision: str | None = None
    schema_current = False
    if reachable:
        try:
            async with state.engine.connect() as connection:
                revisions = await current_migration_revisions(connection)
                revision = revisions[0] if len(revisions) == 1 else None
                schema_current = await schema_is_current(connection, revisions)
        except Exception:  # readiness reports, it does not raise
            revision = None
    return DatabaseStatus(
        url=state.settings.database.safe_url,
        reachable=reachable,
        migration_revision=revision,
        schema_current=schema_current,
    )


@router.get("/readiness", response_model=ReadinessResponse)
async def readiness(
    state: StateDependency,
    response: Response,
) -> ReadinessResponse:
    """Report readiness, proved against the database rather than assumed.

    Returns 503 when the database is unreachable, at different migration heads, or
    missing a required table/column, so liveness cannot imply compatibility.
    """
    database = await _database_status(state)
    ready = database.reachable and database.schema_current
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
