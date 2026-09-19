"""Fixtures for orchestration unit tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from money_machine.config.runtime import DatabaseSettings
from money_machine.persistence.database import create_engine, create_session_factory


@pytest.fixture
async def engine(migrated_url: str) -> AsyncGenerator[AsyncEngine]:
    """An engine bound to a migrated throwaway database."""
    created = create_engine(DatabaseSettings(url=migrated_url))
    try:
        yield created
    finally:
        await created.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """A session factory for the migrated database."""
    return create_session_factory(engine)


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    """One session per test, rolled back at the end."""
    async with session_factory() as active:
        yield active
        await active.rollback()
