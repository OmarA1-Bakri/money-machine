"""The operator command line: real invocations against a real database."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from money_machine.cli.main import EXIT_UNAVAILABLE


def run_cli(
    *arguments: str, url: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Invoke the real console script through the module entry point."""
    environment = {
        **os.environ,
        "APP_ENV": "test",
        "MONEY_MACHINE_DATABASE_URL": url,
        **(extra_env or {}),
    }
    return subprocess.run(
        [sys.executable, "-m", "money_machine.cli.main", *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
        env=environment,
    )


async def test_status_reports_a_reachable_migrated_database(migrated_url: str) -> None:
    """Status is typed output, and it reports reachability rather than assuming it."""
    result = await asyncio.to_thread(run_cli, "status", url=migrated_url)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["environment"] == "test"
    assert payload["database"]["reachable"] is True
    assert payload["worker_commissioned"] is False
    assert payload["scheduler_commissioned"] is False


async def test_status_fails_when_the_database_is_down() -> None:
    """A status command that always exits zero would be useless."""
    result = await asyncio.to_thread(
        run_cli,
        "status",
        url="postgresql+asyncpg://money_machine@127.0.0.1:1/absent",
    )

    assert result.returncode == EXIT_UNAVAILABLE
    assert json.loads(result.stdout)["database"]["reachable"] is False


async def test_db_upgrade_then_seed_is_idempotent(test_database: str) -> None:
    """The documented operator path works end to end: upgrade, seed, seed again."""
    upgrade_result = await asyncio.to_thread(run_cli, "db", "upgrade", url=test_database)
    first = await asyncio.to_thread(run_cli, "db", "seed", url=test_database)
    second = await asyncio.to_thread(run_cli, "db", "seed", url=test_database)

    assert upgrade_result.returncode == 0, upgrade_result.stderr
    assert json.loads(upgrade_result.stdout)["migrated"] is True
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["total_created"] > 0
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["total_created"] == 0


async def test_workflow_and_job_listings_run_against_an_empty_database(
    migrated_url: str,
) -> None:
    """Listing commands return typed, empty results rather than failing."""
    workflows = await asyncio.to_thread(run_cli, "workflow", "list", url=migrated_url)
    jobs = await asyncio.to_thread(run_cli, "job", "list", url=migrated_url)

    assert workflows.returncode == 0, workflows.stderr
    assert json.loads(workflows.stdout) == {"workflows": []}
    assert jobs.returncode == 0, jobs.stderr
    assert json.loads(jobs.stdout) == {"jobs": []}


async def test_integrations_status_never_reveals_a_credential(migrated_url: str) -> None:
    """Presence only: the command reports booleans and no secret value."""
    result = await asyncio.to_thread(
        run_cli,
        "integrations",
        "status",
        url=migrated_url,
        extra_env={"ETSY_API_KEY": "cli-secret-value"},
    )

    assert result.returncode == 0, result.stderr
    assert "cli-secret-value" not in result.stdout
    assert "cli-secret-value" not in result.stderr
    providers = {row["name"]: row for row in json.loads(result.stdout)["providers"]}
    assert providers["etsy"]["configured"] is True
    assert providers["etsy"]["effect_mode"] == "simulation"


async def test_production_without_a_database_url_fails_closed() -> None:
    """A missing production setting is a clear failure, not a silent default."""
    environment = {key: value for key, value in os.environ.items() if "DATABASE_URL" not in key}
    environment["APP_ENV"] = "production"
    result = await asyncio.to_thread(
        lambda: subprocess.run(
            [sys.executable, "-m", "money_machine.cli.main", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            env=environment,
        )
    )

    assert result.returncode == EXIT_UNAVAILABLE
    assert "DATABASE_URL is required" in result.stderr


@pytest.mark.parametrize("arguments", [("db",), ("workflow",), ("job",), ("integrations",)])
async def test_incomplete_commands_report_usage(
    arguments: tuple[str, ...], migrated_url: str
) -> None:
    """A command group without a subcommand is a usage error, not a crash."""
    result = await asyncio.to_thread(run_cli, *arguments, url=migrated_url)

    assert result.returncode == 2
    assert "usage:" in result.stderr


def test_console_scripts_are_distinct() -> None:
    """The operator CLI is separate from the fail-closed control utility."""
    pyproject = (Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8")

    assert 'money-machine = "money_machine.cli.main:main"' in pyproject
    assert 'money-machine-control = "money_machine.control.cli:main"' in pyproject
