"""FastAPI application factory."""

from fastapi import FastAPI

from money_machine.api.routers.health import router as health_router
from money_machine.version import __version__


def create_app() -> FastAPI:
    """Create the API application without performing external I/O."""
    application = FastAPI(
        title="Money Machine API",
        version=__version__,
        description="Operator API for the Money Machine modular monolith.",
    )
    application.include_router(health_router)
    return application


app = create_app()
