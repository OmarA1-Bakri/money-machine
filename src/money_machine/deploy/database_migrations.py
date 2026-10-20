"""Apply the migration chain to an isolated database and prove it reverses.

The chain is the three revisions under ``migrations/versions``. This module
upgrades a loopback database that is not the shared ``money_machine``
database, downgrades it to base, and upgrades it again. A remote host is
refused before any connection.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from money_machine.persistence.tables import EXPECTED_TABLES

MIGRATION_CHAIN = (
    "9f46f3152a68",
    "a1b2c3d4e5f6",
    "b2c3d4e5f6a7",
)
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
_SHARED = frozenset({"money_machine", "postgres", "template0", "template1"})
_TABLES = text(
    "SELECT table_name FROM information_schema.tables"
    " WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
)
_VERSION = text("SELECT version_num FROM alembic_version")

Operation = Callable[[Config, str], None]


class DatabaseMigrationRefusal(ValueError):
    """The chain is wrong, or the database must not be migrated."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class _Catalogue:
    """Tables and the Alembic version present after one command."""

    tables: frozenset[str]
    head: str | None


@dataclass(frozen=True, slots=True)
class DatabaseMigrations:
    """The chain applied to an isolated database. The shared database was not used."""

    succeeded: bool
    head: str
    revisions: tuple[str, ...]
    tables: tuple[str, ...]
    applied: bool
    shared_database: bool


def read_migration_chain(root: Path | None = None) -> tuple[str, ...]:
    """The linear revisions from base to head. No database is contacted."""
    repo = _root(root)
    try:
        script = ScriptDirectory.from_config(_script_config(repo))
        heads = script.get_heads()
    except Exception as error:
        raise DatabaseMigrationRefusal("chain") from error
    if len(heads) != 1:
        raise DatabaseMigrationRefusal("chain")
    ordered: list[str] = []
    current = script.get_revision(heads[0])
    while True:
        ordered.append(current.revision)
        down = current.down_revision
        if down is None:
            break
        if not isinstance(down, str):
            raise DatabaseMigrationRefusal("chain")
        current = script.get_revision(down)
    ordered.reverse()
    if tuple(ordered) != MIGRATION_CHAIN:
        raise DatabaseMigrationRefusal("chain")
    return MIGRATION_CHAIN


def refuse_shared_database(url: str) -> None:
    """A shared, maintenance, or non-local database is not migrated."""
    try:
        parsed = make_url(url)
    except Exception as error:
        raise DatabaseMigrationRefusal("url") from error
    name = parsed.database
    host = parsed.host
    if name is None or host is None or name == "" or host == "":
        raise DatabaseMigrationRefusal("url")
    if host.casefold() not in _LOOPBACK:
        raise DatabaseMigrationRefusal("remote")
    if name.casefold() in _SHARED:
        raise DatabaseMigrationRefusal("shared")


def apply_database_migrations(url: str, root: Path | None = None) -> DatabaseMigrations:
    """Upgrade, reverse, and upgrade an isolated database. The shared one is refused."""
    refuse_shared_database(url)
    repo = _root(root)
    revisions = read_migration_chain(repo)
    head = revisions[-1]
    _run(command.upgrade, url, repo, "head", "upgrade")
    _require_schema(_catalogue(url, "upgrade"), head, "upgrade")
    _run(command.downgrade, url, repo, "base", "downgrade")
    emptied = _catalogue(url, "downgrade")
    if emptied.tables - {"alembic_version"} or emptied.head is not None:
        raise DatabaseMigrationRefusal("downgrade")
    _run(command.upgrade, url, repo, "head", "upgrade")
    restored = _catalogue(url, "upgrade")
    _require_schema(restored, head, "upgrade")
    tables = tuple(sorted(restored.tables - {"alembic_version"}))
    return DatabaseMigrations(
        succeeded=True,
        head=head,
        revisions=revisions,
        tables=tables,
        applied=True,
        shared_database=False,
    )


def _root(root: Path | None) -> Path:
    if root is None:
        return Path(__file__).resolve().parents[3]
    return root


def _script_config(root: Path) -> Config:
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return config


def _config(root: Path, url: str) -> Config:
    config = _script_config(root)
    config.set_main_option("sqlalchemy.url", url)
    return config


def _run(operation: Operation, url: str, root: Path, revision: str, code: str) -> None:
    config = _config(root, url)

    def invoke() -> None:
        operation(config, revision)

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(invoke).result()
    except Exception as error:
        raise DatabaseMigrationRefusal(code) from error


def _require_schema(catalogue: _Catalogue, head: str, code: str) -> None:
    present = tuple(sorted(catalogue.tables - {"alembic_version"}))
    expected: tuple[str, ...] = tuple(EXPECTED_TABLES)
    if catalogue.head != head or present != expected:
        raise DatabaseMigrationRefusal(code)


def _catalogue(url: str, code: str) -> _Catalogue:
    try:
        return asyncio.run(_read_catalogue(url))
    except Exception as error:
        raise DatabaseMigrationRefusal(code) from error


async def _read_catalogue(url: str) -> _Catalogue:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            rows = (await connection.execute(_TABLES)).scalars().all()
            version = (await connection.execute(_VERSION)).scalar_one_or_none()
    finally:
        await engine.dispose()
    head = None if version is None else str(version)
    return _Catalogue(frozenset(str(row) for row in rows), head)
