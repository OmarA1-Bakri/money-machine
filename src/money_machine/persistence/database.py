"""Async engine and session management for the single canonical database."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import cache
from pathlib import Path

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from money_machine.config.runtime import DatabaseSettings
from money_machine.persistence.tables import Base


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create the async engine. The DSN is assembled here and never logged."""
    return create_async_engine(
        settings.dsn(),
        echo=settings.echo_sql,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout_seconds,
        pool_pre_ping=True,
        connect_args={
            "timeout": settings.command_timeout_seconds,
            "statement_cache_size": settings.statement_cache_size,
        },
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory that never expires attributes after commit."""
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    """Yield a session that commits on success and rolls back on any exception."""
    session = factory()
    try:
        yield session
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    finally:
        await session.close()


async def check_connectivity(engine: AsyncEngine) -> bool:
    """Prove an authenticated round trip. Returns False rather than raising."""
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            return result.scalar_one() == 1
    except Exception:
        return False


async def current_migration_revision(connection: AsyncConnection) -> str | None:
    """Read a single applied revision; absent or ambiguous heads return None."""
    revisions = await current_migration_revisions(connection)
    return revisions[0] if len(revisions) == 1 else None


async def current_migration_revisions(connection: AsyncConnection) -> tuple[str, ...]:
    """Read every applied head without creating a missing version table."""
    return await connection.run_sync(
        lambda sync: MigrationContext.configure(sync).get_current_heads()
    )


@cache
def expected_migration_revisions() -> frozenset[str]:
    """Resolve the heads shipped with this checkout/image, independently of cwd."""
    migrations = Path(__file__).resolve().parents[3] / "migrations"
    return frozenset(ScriptDirectory(str(migrations)).get_heads())


async def schema_is_current(connection: AsyncConnection, revisions: tuple[str, ...]) -> bool:
    """Require matching migration heads and every mapped table/column.

    This is a startup compatibility check, not a replacement for migration drift,
    constraint and permission verification at deployment.
    """
    expected = expected_migration_revisions()
    if not expected or frozenset(revisions) != expected:
        return False
    result = await connection.execute(
        text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema()"
        )
    )
    actual_columns = {(str(row[0]), str(row[1])) for row in result}
    required_columns = {
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
    }
    return required_columns <= actual_columns
