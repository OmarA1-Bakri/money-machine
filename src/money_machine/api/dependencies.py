"""Application state and request dependencies for the operator API."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from money_machine.config.runtime import RuntimeSettings, load_runtime_settings
from money_machine.persistence.database import create_engine, create_session_factory


@dataclass
class ApplicationState:
    """Long-lived, process-wide resources."""

    settings: RuntimeSettings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    @classmethod
    def create(cls, settings: RuntimeSettings | None = None) -> ApplicationState:
        """Build state without opening a connection."""
        resolved = settings or load_runtime_settings()
        engine = create_engine(resolved.database)
        return cls(settings=resolved, engine=engine, session_factory=create_session_factory(engine))

    async def dispose(self) -> None:
        """Release the connection pool."""
        await self.engine.dispose()


def application_state(request: Request) -> ApplicationState:
    """Resolve the application state attached at startup."""
    state: ApplicationState = request.app.state.application
    return state


def settings(state: Annotated[ApplicationState, Depends(application_state)]) -> RuntimeSettings:
    """Resolve runtime settings for one request."""
    return state.settings


async def database_session(
    state: Annotated[ApplicationState, Depends(application_state)],
) -> AsyncGenerator[AsyncSession]:
    """Yield a request-scoped session that never commits implicitly."""
    async with state.session_factory() as session:
        yield session


StateDependency = Annotated[ApplicationState, Depends(application_state)]
SettingsDependency = Annotated[RuntimeSettings, Depends(settings)]
SessionDependency = Annotated[AsyncSession, Depends(database_session)]
