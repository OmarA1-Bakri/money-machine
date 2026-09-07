"""Async engine and session management for the single canonical database."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from money_machine.config.runtime import DatabaseSettings


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
    """Read the applied Alembic revision, or None when the table is absent."""
    result = await connection.execute(
        text(
            "SELECT version_num FROM alembic_version"
            " WHERE EXISTS (SELECT 1 FROM information_schema.tables"
            " WHERE table_name = 'alembic_version')"
        )
    )
    row = result.first()
    return None if row is None else str(row[0])
