"""Alembic environment.

The database URL comes from runtime settings, never from ``alembic.ini``, so a password
cannot be committed and cannot be printed by Alembic's own logging.
"""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from money_machine.config.runtime import load_runtime_settings
from money_machine.persistence.tables import Base

config = context.config
target_metadata = Base.metadata


def database_url() -> str:
    """Resolve the connection string, preferring an explicit Alembic override."""
    override = config.get_main_option("sqlalchemy.url", None)
    if override:
        return override
    return load_runtime_settings().database.dsn()


IGNORED_TABLES = frozenset({"alembic_version"})


def include_object(
    obj: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object,
) -> bool:
    """Keep Alembic's attention on this application's own tables.

    A reflected table that is not in the metadata is *included* on purpose: otherwise a
    table dropped from ``tables.py`` would linger in the database while ``alembic check``
    reported no drift.
    """
    del obj, compare_to
    if type_ == "table" and name is not None:
        if name in IGNORED_TABLES:
            return False
        return name in Base.metadata.tables or reflected
    return True


def run_migrations_offline() -> None:
    """Emit SQL without a live connection."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations on an established synchronous connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against the async driver."""
    section: dict[str, str] = dict(config.get_section(config.config_ini_section) or {})
    section["sqlalchemy.url"] = database_url()
    engine = async_engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
