"""Restore one fixture shop and one isolated database.

The fixture snapshot copies the workflow, job, product, listing, incident,
artifact, and simulation config. A second restore inserts nothing. The
database copy uses ``CREATE DATABASE ... TEMPLATE`` on a loopback throwaway
whose name starts with ``mm_t_``. The shared database is refused before a
connection. ``pg_dump`` is not run.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from money_machine.assets.backup_restore import (
    BackupRefusal,
    FixtureSnapshot,
    FixtureStore,
    backup,
    restore_snapshot,
)
from money_machine.deploy.database_migrations import (
    MIGRATION_CHAIN,
    DatabaseMigrationRefusal,
    refuse_shared_database,
)
from money_machine.persistence.tables import EXPECTED_TABLES

_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
_NAME = re.compile(r"^mm_t_[0-9a-f]{20}$")
_TERMINATE = text(
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
    " WHERE datname = :name AND pid <> pg_backend_pid()"
)
_TABLES = text(
    "SELECT table_name FROM information_schema.tables"
    " WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
)
_VERSION = text("SELECT version_num FROM alembic_version")

Probe = Callable[[str], None]


class BackupRestoreRefusal(ValueError):
    """The snapshot, the database copy, or a live backup is refused."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class _Copy:
    """Tables and Alembic version read from the restored database."""

    tables: tuple[str, ...]
    head: str


@dataclass(frozen=True, slots=True)
class BackupRestore:
    """A fixture restore plus a copy of an isolated database."""

    succeeded: bool
    schema_head: str
    tables: tuple[str, ...]
    workflow_count: int
    job_count: int
    product_count: int
    listing_count: int
    incident_count: int
    artifact_count: int
    second_restore_inserted: int
    live_postgres: bool


def refuse_live_backup(requested: str) -> None:
    """A live database backup is not taken."""
    folded = requested.casefold()
    if "pg_dump" in folded or "pg_restore" in folded or "money_machine" in folded:
        raise BackupRestoreRefusal("live_postgres")
    if folded.strip() != "postgres":
        return
    try:
        backup(mode="postgres")
    except BackupRefusal as error:
        raise BackupRestoreRefusal(error.code) from error
    raise BackupRestoreRefusal("live_postgres")


def record_backup_restore(
    source_url: str,
    admin_url: str,
    *,
    probe: Probe | None = None,
) -> BackupRestore:
    """Restore the fixture shop and copy one throwaway database."""
    _refuse_source(source_url)
    _refuse_admin(admin_url)
    snapshot = _snapshot()
    target = FixtureStore()
    first = restore_snapshot(target, snapshot)
    second = restore_snapshot(target, snapshot)
    if not _restored(snapshot, target, first.inserted, second.inserted):
        raise BackupRestoreRefusal("fixture")
    copied = _copy_database(source_url, admin_url, probe)
    return BackupRestore(
        succeeded=True,
        schema_head=copied.head,
        tables=copied.tables,
        workflow_count=first.workflow_count,
        job_count=first.job_count,
        product_count=first.product_count,
        listing_count=first.listing_count,
        incident_count=first.incident_count,
        artifact_count=first.artifact_count,
        second_restore_inserted=second.inserted,
        live_postgres=False,
    )


def _snapshot() -> FixtureSnapshot:
    try:
        snapshot = backup(mode="fixture")
    except BackupRefusal as error:
        raise BackupRestoreRefusal(error.code) from error
    if snapshot.config.publishing_mode != "simulation":
        raise BackupRestoreRefusal("live_config")
    return snapshot


def _restored(
    snapshot: FixtureSnapshot,
    target: FixtureStore,
    inserted: int,
    again: int,
) -> bool:
    workflow = snapshot.workflows[0]
    job = snapshot.jobs[0]
    product = snapshot.products[0]
    listing = snapshot.listings[0]
    incident = snapshot.incidents[0]
    artifact = snapshot.artifacts[0]
    return (
        inserted == 7
        and again == 0
        and len(snapshot.workflows) == 1
        and len(snapshot.jobs) == 1
        and len(snapshot.products) == 1
        and len(snapshot.listings) == 1
        and len(snapshot.incidents) == 1
        and len(snapshot.artifacts) == 1
        and listing.listing_state == "DRAFT"
        and target.workflows.get(workflow.workflow_id) == workflow
        and target.jobs.get(job.job_id) == job
        and target.products.get(product.product_id) == product
        and target.listings.get(listing.listing_id) == listing
        and target.incidents.get(incident.incident_id) == incident
        and target.artifacts.get(artifact.artifact_id) == artifact
        and target.config == snapshot.config
    )


def _refuse_source(url: str) -> None:
    try:
        refuse_shared_database(url)
    except DatabaseMigrationRefusal as error:
        raise BackupRestoreRefusal(error.code) from error
    name = make_url(url).database
    if name is None or _NAME.fullmatch(name) is None:
        raise BackupRestoreRefusal("isolated")


def _refuse_admin(url: str) -> None:
    try:
        parsed = make_url(url)
    except Exception as error:
        raise BackupRestoreRefusal("url") from error
    host = parsed.host
    name = parsed.database
    if host is None or name is None or host == "" or name == "":
        raise BackupRestoreRefusal("url")
    if host.casefold() not in _LOOPBACK:
        raise BackupRestoreRefusal("remote")
    if name.casefold() != "postgres":
        raise BackupRestoreRefusal("admin")


def _copy_database(source_url: str, admin_url: str, probe: Probe | None) -> _Copy:
    source_name = make_url(source_url).database or ""
    restore_name = "mm_t_" + uuid4().hex[:20]
    if _NAME.fullmatch(restore_name) is None:
        raise BackupRestoreRefusal("isolated")
    restore_url = (
        make_url(admin_url).set(database=restore_name).render_as_string(hide_password=False)
    )
    try:
        asyncio.run(_create(admin_url, source_name, restore_name))
        copied = asyncio.run(_read(restore_url))
        if probe is not None:
            probe(restore_url)
        return copied
    except BackupRestoreRefusal:
        raise
    except Exception as error:
        raise BackupRestoreRefusal("restore") from error
    finally:
        asyncio.run(_drop(admin_url, restore_name))


async def _create(admin_url: str, source_name: str, restore_name: str) -> None:
    statement = text(f'CREATE DATABASE "{restore_name}" TEMPLATE "{source_name}"')
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(_TERMINATE, {"name": source_name})
            try:
                await connection.execute(statement)
            except Exception:
                await connection.execute(_TERMINATE, {"name": source_name})
                await connection.execute(statement)
    finally:
        await engine.dispose()


async def _read(url: str) -> _Copy:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            rows = (await connection.execute(_TABLES)).scalars().all()
            version = (await connection.execute(_VERSION)).scalar_one_or_none()
    finally:
        await engine.dispose()
    present = tuple(sorted(str(row) for row in rows if str(row) != "alembic_version"))
    expected: tuple[str, ...] = tuple(EXPECTED_TABLES)
    head = "" if version is None else str(version)
    if present != expected or head != MIGRATION_CHAIN[-1]:
        raise BackupRestoreRefusal("restore")
    return _Copy(present, head)


async def _drop(admin_url: str, restore_name: str) -> None:
    statement = text(f'DROP DATABASE IF EXISTS "{restore_name}" WITH (FORCE)')
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(statement)
    finally:
        await engine.dispose()
