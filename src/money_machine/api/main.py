"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from money_machine.api.dependencies import ApplicationState
from money_machine.api.routers.health import router as health_router
from money_machine.api.routers.integrations import router as integrations_router
from money_machine.api.routers.jobs import router as jobs_router
from money_machine.api.routers.workflows import router as workflows_router
from money_machine.version import __version__


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
    """Build engine and session factory at startup; dispose them at shutdown.

    No connection is opened here: startup must not fail because the database is briefly
    unavailable. Readiness is what reports that.
    """
    state = ApplicationState.create()
    application.state.application = state
    try:
        yield
    finally:
        await state.dispose()


def create_app() -> FastAPI:
    """Create the API application without performing external I/O."""
    application = FastAPI(
        title="Money Machine API",
        version=__version__,
        description="Operator API for the Money Machine modular monolith.",
        lifespan=lifespan,
    )
    application.include_router(health_router)
    application.include_router(workflows_router)
    application.include_router(jobs_router)
    application.include_router(integrations_router)
    return application


app = create_app()
