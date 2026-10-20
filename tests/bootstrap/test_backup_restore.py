"""Backup and restore succeed for the fixture shop and an isolated database."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from money_machine.deploy.backup_restore import (
    BackupRestoreRefusal,
    record_backup_restore,
    refuse_live_backup,
)
from money_machine.deploy.database_migrations import apply_database_migrations
from money_machine.persistence.tables import EXPECTED_TABLES
from tests.conftest import admin_url

ROOT = Path(__file__).parents[2]
_SHARED = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/money_machine"
_REMOTE = "postgresql+asyncpg://money_machine:redacted@db.example:5432/mm_t_0123456789abcdef0123"
_OTHER = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/app_database"
_ADMIN = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/postgres"
_TABLES = text(
    "SELECT table_name FROM information_schema.tables"
    " WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
)


def test_a_live_backup_is_refused() -> None:
    with pytest.raises(BackupRestoreRefusal, match="live_postgres"):
        refuse_live_backup("pg_dump")
    with pytest.raises(BackupRestoreRefusal, match="live_postgres"):
        refuse_live_backup("postgres")


def test_the_shared_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(BackupRestoreRefusal, match="shared"):
        record_backup_restore(_SHARED, _ADMIN)


def test_a_remote_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(BackupRestoreRefusal, match="remote"):
        record_backup_restore(_REMOTE, _ADMIN)


def test_a_standing_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(BackupRestoreRefusal, match="isolated"):
        record_backup_restore(_OTHER, _ADMIN)


async def test_an_isolated_backup_restores(test_database: str) -> None:
    await asyncio.to_thread(apply_database_migrations, test_database, ROOT)
    seen: list[set[str]] = []

    def probe(url: str) -> None:
        seen.append(asyncio.run(_live_tables(url)))

    recorded = await asyncio.to_thread(
        record_backup_restore, test_database, admin_url(), probe=probe
    )

    assert recorded.succeeded is True
    assert recorded.live_postgres is False
    assert recorded.schema_head == "b2c3d4e5f6a7"
    assert recorded.second_restore_inserted == 0
    assert recorded.workflow_count == 1
    assert recorded.job_count == 1
    assert recorded.product_count == 1
    assert recorded.listing_count == 1
    assert recorded.incident_count == 1
    assert recorded.artifact_count == 1
    assert set(recorded.tables) == set(EXPECTED_TABLES)
    assert seen[0] - {"alembic_version"} == set(EXPECTED_TABLES)
    assert make_url(test_database).database != "money_machine"


def _refuse_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    def contacted(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("database was contacted")

    monkeypatch.setattr(
        "money_machine.deploy.backup_restore.create_async_engine",
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
