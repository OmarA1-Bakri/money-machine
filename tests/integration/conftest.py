"""Migration and session fixtures for database-backed tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from money_machine.config.runtime import DatabaseSettings
from money_machine.persistence.database import create_engine, create_session_factory
from tests.integration.alembic_support import upgrade


@pytest.fixture
async def migrated_url(test_database: str, repository_root: Path) -> AsyncGenerator[str]:
    """A throwaway database at head revision."""
    await asyncio.to_thread(upgrade, test_database, repository_root)
    yield test_database


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
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    """One session per test, rolled back at the end."""
    async with session_factory() as active:
        yield active
        await active.rollback()
