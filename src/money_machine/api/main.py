"""Read-only FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from money_machine.api.routers.health import router as health_router
from money_machine.api.routers.jobs import router as jobs_router
from money_machine.api.routers.listings import router as listings_router
from money_machine.api.routers.products import router as products_router
from money_machine.api.routers.workflows import router as workflows_router
from money_machine.config.settings import Settings
from money_machine.persistence.database import Database
from money_machine.version import __version__


def create_app(database: Database | None = None) -> FastAPI:
    """Create the API application without performing external I/O."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
        owned = database is None
        active = Database.from_url(Settings.from_env().database_url) if owned else database
        if active is None:
            raise RuntimeError("API database is not initialized")
        application.state.database = active
        try:
            yield
        finally:
            if owned:
                await active.dispose()

    application = FastAPI(
        title="Money Machine API",
        version=__version__,
        description="Operator API for the Money Machine modular monolith.",
        lifespan=lifespan,
    )
    if database is not None:
        application.state.database = database
    application.include_router(health_router)
    application.include_router(workflows_router)
    application.include_router(jobs_router)
    application.include_router(products_router)
    application.include_router(listings_router)
    return application


app = create_app()
