"""The ``money-machine`` operator command line.

Separate from ``money-machine-control``, which is the fail-closed repository-control
utility and must not be used for routine operation.

Every command is read-only or database-local. No command performs a provider call, reads a
credential value, or publishes anything.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

from money_machine.config.runtime import (
    RuntimeSettings,
    RuntimeSettingsError,
    load_runtime_settings,
)
from money_machine.version import __version__

EXIT_OK: Final = 0
EXIT_USAGE: Final = 64
EXIT_UNAVAILABLE: Final = 78
"""Reserved for a surface that is registered but not commissioned."""

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[3]


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, default=str))


def _fail(message: str, code: int = EXIT_UNAVAILABLE) -> int:
    print(message, file=sys.stderr)
    return code


def _settings() -> RuntimeSettings:
    return load_runtime_settings()


def command_status(arguments: argparse.Namespace) -> int:
    """Report process, environment and database status."""
    del arguments
    from money_machine.persistence.database import check_connectivity, create_engine

    settings = _settings()

    async def probe() -> bool:
        engine = create_engine(settings.database)
        try:
            return await check_connectivity(engine)
        finally:
            await engine.dispose()

    reachable = asyncio.run(probe())
    _print(
        {
            "version": __version__,
            "environment": settings.environment.value,
            "database": {"url": settings.database.safe_url, "reachable": reachable},
            "worker_commissioned": settings.worker.commissioned,
            "scheduler_commissioned": settings.scheduler.commissioned,
        }
    )
    return EXIT_OK if reachable else EXIT_UNAVAILABLE


def command_db_upgrade(arguments: argparse.Namespace) -> int:
    """Apply all outstanding migrations."""
    del arguments
    from alembic import command
    from alembic.config import Config

    config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPOSITORY_ROOT / "migrations"))
    command.upgrade(config, "head")
    _print({"migrated": True, "revision": "head"})
    return EXIT_OK


def command_db_seed(arguments: argparse.Namespace) -> int:
    """Seed canonical configuration idempotently."""
    from money_machine.persistence.database import create_engine, create_session_factory
    from money_machine.persistence.seed import seed

    settings = _settings()

    async def run() -> dict[str, int]:
        engine = create_engine(settings.database)
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                report = await seed(
                    session,
                    repository_root=REPOSITORY_ROOT,
                    shop_name=arguments.shop,
                )
                await session.commit()
                return {
                    "shops_created": report.shops_created,
                    "agents_created": report.agents_created,
                    "prompt_versions_created": report.prompt_versions_created,
                    "config_references_created": report.config_references_created,
                    "total_created": report.total_created,
                }
        finally:
            await engine.dispose()

    _print(asyncio.run(run()))
    return EXIT_OK


def command_workflow_list(arguments: argparse.Namespace) -> int:
    """List durable workflows."""
    from money_machine.persistence.database import create_engine, create_session_factory
    from money_machine.persistence.repositories.workflows import WorkflowRunRepository

    settings = _settings()

    async def run() -> list[dict[str, Any]]:
        engine = create_engine(settings.database)
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                page = await WorkflowRunRepository(session).page(limit=arguments.limit)
                return [
                    {
                        "id": str(row.id),
                        "workflow_type": row.workflow_type,
                        "product_state": row.product_state,
                        "started_at": row.started_at,
                    }
                    for row in page.items
                ]
        finally:
            await engine.dispose()

    _print({"workflows": asyncio.run(run())})
    return EXIT_OK


def command_job_list(arguments: argparse.Namespace) -> int:
    """List durable jobs. Listing is not claiming; claiming is Session 03."""
    from money_machine.persistence.database import create_engine, create_session_factory
    from money_machine.persistence.repositories.jobs import JobRepository

    settings = _settings()

    async def run() -> list[dict[str, Any]]:
        engine = create_engine(settings.database)
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                page = await JobRepository(session).page(limit=arguments.limit)
                return [
                    {
                        "id": str(row.id),
                        "job_type": row.job_type,
                        "status": row.status,
                        "owner_agent_id": row.owner_agent_id,
                        "scheduled_at": row.scheduled_at,
                    }
                    for row in page.items
                ]
        finally:
            await engine.dispose()

    _print({"jobs": asyncio.run(run())})
    return EXIT_OK


def command_integrations_status(arguments: argparse.Namespace) -> int:
    """Report which providers are configured, from settings presence only.

    This command never reads a credential value, never performs a network call, and never
    opens a browser profile (D-0016, corrective addendum 5).
    """
    del arguments
    settings = _settings()
    _print(
        {
            "environment": settings.environment.value,
            "providers": [
                {
                    "name": provider.name,
                    "configured": provider.configured,
                    "effect_mode": provider.effect_mode,
                    "commissioned": provider.commissioned,
                }
                for provider in settings.providers
            ],
        }
    )
    return EXIT_OK


Handler = Callable[[argparse.Namespace], int]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="money-machine", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    database = subparsers.add_parser("db", help="database migrations and seeding")
    database_actions = database.add_subparsers(dest="db_command", required=True)
    upgrade = database_actions.add_parser("upgrade", help="apply outstanding migrations")
    upgrade.set_defaults(handler=command_db_upgrade)
    seed_parser = database_actions.add_parser("seed", help="seed canonical configuration")
    seed_parser.add_argument("--shop", default="default", help="shop name to seed")
    seed_parser.set_defaults(handler=command_db_seed)

    status = subparsers.add_parser("status", help="report process and database status")
    status.set_defaults(handler=command_status)

    workflow = subparsers.add_parser("workflow", help="inspect workflows")
    workflow_actions = workflow.add_subparsers(dest="workflow_command", required=True)
    workflow_list = workflow_actions.add_parser("list", help="list workflows")
    workflow_list.add_argument("--limit", type=int, default=50)
    workflow_list.set_defaults(handler=command_workflow_list)

    job = subparsers.add_parser("job", help="inspect jobs")
    job_actions = job.add_subparsers(dest="job_command", required=True)
    job_list = job_actions.add_parser("list", help="list jobs")
    job_list.add_argument("--limit", type=int, default=50)
    job_list.set_defaults(handler=command_job_list)

    integrations = subparsers.add_parser("integrations", help="inspect provider readiness")
    integration_actions = integrations.add_subparsers(dest="integrations_command", required=True)
    integrations_status = integration_actions.add_parser(
        "status",
        help="report configured or not configured, without reading any credential",
    )
    integrations_status.set_defaults(handler=command_integrations_status)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one operator command."""
    arguments = _parser().parse_args(argv)
    handler: Handler = arguments.handler
    try:
        return handler(arguments)
    except RuntimeSettingsError as error:
        return _fail(f"configuration error: {error}")
    except Exception as error:  # the CLI reports failures, it does not raise tracebacks
        return _fail(f"command failed: {type(error).__name__}: {error}")


if __name__ == "__main__":
    raise SystemExit(main())
