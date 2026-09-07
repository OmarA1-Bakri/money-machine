"""Shared fixtures.

Database-backed tests need a real PostgreSQL instance because the constraints under test
are database constraints. Each test module gets its own throwaway database, created and
dropped around the test, so nothing touches the developer's database or another branch's
leftovers. When PostgreSQL is unavailable the database tests skip with an explicit reason
rather than passing vacuously.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Final

import pytest

REPOSITORY_ROOT: Final = Path(__file__).parents[1]
ADMIN_URL_VARIABLE: Final = "MONEY_MACHINE_TEST_ADMIN_DATABASE_URL"
DEFAULT_ADMIN_URL: Final = (
    "postgresql+asyncpg://money_machine:local_development_only@127.0.0.1:5432/postgres"
)


def admin_url() -> str:
    """The maintenance connection used to create and drop test databases."""
    return os.environ.get(ADMIN_URL_VARIABLE, DEFAULT_ADMIN_URL)


def database_url(name: str) -> str:
    """The connection string for one named test database."""
    base = admin_url()
    return base.rsplit("/", 1)[0] + "/" + name


async def _postgres_available() -> bool:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(admin_url(), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def postgres_available() -> bool:
    """Whether a usable PostgreSQL instance is reachable for this run."""
    import asyncio

    return asyncio.run(_postgres_available())


@pytest.fixture
async def test_database(
    request: pytest.FixtureRequest, postgres_available: bool
) -> AsyncGenerator[str]:
    """Create a throwaway database for one test and drop it afterwards."""
    if not postgres_available:
        pytest.skip(
            "PostgreSQL is unavailable; start it with `bash scripts/verify_postgres.sh`"
            f" or set {ADMIN_URL_VARIABLE}"
        )
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    name = f"mm_t_{uuid.uuid4().hex[:20]}"
    engine = create_async_engine(admin_url(), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await engine.dispose()

    try:
        yield database_url(name)
    finally:
        engine = create_async_engine(admin_url(), isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        finally:
            await engine.dispose()
    del request


@pytest.fixture
def repository_root() -> Path:
    """The repository root, for tests that read tracked files."""
    return REPOSITORY_ROOT


@pytest.fixture
def simulation_environment(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """Force the test environment, so no test can reach a non-simulation mode."""
    monkeypatch.setenv("APP_ENV", "test")
    yield
