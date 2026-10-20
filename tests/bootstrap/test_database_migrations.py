"""Database migrations succeed on an isolated database and reverse."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from money_machine.deploy.database_migrations import (
    MIGRATION_CHAIN,
    DatabaseMigrationRefusal,
    apply_database_migrations,
    read_migration_chain,
)
from money_machine.persistence.tables import EXPECTED_TABLES

ROOT = Path(__file__).parents[2]
_SHARED = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/money_machine"
_REMOTE = "postgresql+asyncpg://money_machine:redacted@db.example:5432/mm_t_isolated"
_TABLES = text(
    "SELECT table_name FROM information_schema.tables"
    " WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
)


def test_the_migration_chain_is_linear() -> None:
    assert read_migration_chain(ROOT) == MIGRATION_CHAIN
    assert MIGRATION_CHAIN[-1] == "b2c3d4e5f6a7"


def test_a_missing_chain_is_refused(tmp_path: Path) -> None:
    with pytest.raises(DatabaseMigrationRefusal, match="chain"):
        read_migration_chain(tmp_path)


def test_the_shared_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(DatabaseMigrationRefusal, match="shared"):
        apply_database_migrations(_SHARED, ROOT)


def test_a_remote_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(DatabaseMigrationRefusal, match="remote"):
        apply_database_migrations(_REMOTE, ROOT)


async def test_an_isolated_database_migrates_and_reverses(test_database: str) -> None:
    recorded = await asyncio.to_thread(apply_database_migrations, test_database, ROOT)
    present = await _live_tables(test_database)

    assert recorded.succeeded is True
    assert recorded.applied is True
    assert recorded.shared_database is False
    assert recorded.head == "b2c3d4e5f6a7"
    assert recorded.revisions == MIGRATION_CHAIN
    assert set(recorded.tables) == set(EXPECTED_TABLES)
    assert present - {"alembic_version"} == set(EXPECTED_TABLES)


def _refuse_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    def contacted(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("database was contacted")

    monkeypatch.setattr(
        "money_machine.deploy.database_migrations.create_async_engine",
        contacted,
    )
    monkeypatch.setattr(
        "money_machine.deploy.database_migrations.command.upgrade",
        contacted,
    )
    monkeypatch.setattr(
        "money_machine.deploy.database_migrations.command.downgrade",
        contacted,
    )


async def _live_tables(url: str) -> set[str]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            rows = (await connection.execute(_TABLES)).scalars().all()
    finally:
        await engine.dispose()
    return {str(row) for row in rows}
