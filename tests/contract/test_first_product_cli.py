from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest
from alembic import command
from alembic.config import Config
from typer.testing import CliRunner

from money_machine.cli.commands import database as database_command
from money_machine.cli.main import app
from money_machine.config.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "research" / "valid_packet_30.json"


def _last_json(output: str) -> dict[str, object]:
    for line in reversed(output.splitlines()):
        try:
            value = cast(object, json.loads(line))
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            mapping = cast(dict[object, object], value)
            if all(isinstance(key, str) for key in mapping):
                return {cast(str, key): nested for key, nested in mapping.items()}
    raise AssertionError(f"no JSON object in output: {output}")


def test_first_product_cli_exposes_only_bounded_local_operator_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command_name in ("db", "research", "workflow", "worker", "artifacts", "scheduler"):
        assert command_name in result.output
    lowered = result.output.casefold()
    for forbidden in ("publish", "purchase", "message-customer", "live-effect", "spend"):
        assert forbidden not in lowered


@pytest.mark.skipif(
    "MONEY_MACHINE_TEST_DATABASE_URL" not in os.environ,
    reason="requires isolated PostgreSQL contract database",
)
def test_first_product_cli_import_start_drain_replay_and_inspect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_url = os.environ["MONEY_MACHINE_TEST_DATABASE_URL"]
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("MONEY_MACHINE_DATABASE_URL", database_url)
    monkeypatch.setenv("MONEY_MACHINE_CONFIG_ROOT", str(REPO_ROOT / "config"))
    monkeypatch.setenv("MONEY_MACHINE_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("MONEY_MACHINE_WORKER_ID", "contract-cli-worker")
    runner = CliRunner()
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.downgrade(config, "base")

    migrated = runner.invoke(app, ["db", "migrate", "--json"])
    assert migrated.exit_code == 0, migrated.output
    assert _last_json(migrated.output) == {
        "external_mutations": 0,
        "revision": "head",
        "spend_usd": "0.00",
        "status": "migrated",
    }

    imported = runner.invoke(app, ["research", "import", "--packet", str(FIXTURE), "--json"])
    assert imported.exit_code == 0, imported.output
    import_receipt = _last_json(imported.output)
    packet_id = str(import_receipt["packet_id"])
    assert import_receipt["row_count"] == 30
    assert import_receipt["persisted"] is True

    started = runner.invoke(
        app,
        ["workflow", "start", "first-product", "--packet-id", packet_id, "--json"],
    )
    assert started.exit_code == 0, started.output
    start_receipt = _last_json(started.output)
    workflow_id = str(start_receipt["workflow_run_id"])
    assert start_receipt["replayed"] is False

    drained = runner.invoke(app, ["worker", "drain", "--max-jobs", "20", "--json"])
    assert drained.exit_code == 0, drained.output
    drain_receipt = _last_json(drained.output)
    assert drain_receipt["processed_count"] == 8
    assert drain_receipt["final_status"] == "idle"
    assert drain_receipt["external_mutations"] == 0
    assert drain_receipt["spend_usd"] == "0.00"

    status = runner.invoke(app, ["workflow", "status", workflow_id, "--json"])
    assert status.exit_code == 0, status.output
    status_receipt = _last_json(status.output)
    assert status_receipt["state"] == "DRAFT_READY"
    jobs = status_receipt["jobs"]
    events = status_receipt["events"]
    assert isinstance(jobs, list) and len(cast(list[object], jobs)) == 8
    assert isinstance(events, list) and len(cast(list[object], events)) == 8
    assert "lease_token" not in status.output
    assert "lease_owner" not in status.output

    replay = runner.invoke(
        app,
        ["workflow", "start", "first-product", "--packet-id", packet_id, "--json"],
    )
    assert replay.exit_code == 0, replay.output
    replay_receipt = _last_json(replay.output)
    assert replay_receipt["workflow_run_id"] == workflow_id
    assert replay_receipt["replayed"] is True

    inspected = runner.invoke(app, ["artifacts", "inspect", workflow_id, "--json"])
    assert inspected.exit_code == 0, inspected.output
    inspection = _last_json(inspected.output)
    assert Path(str(inspection["local_root"])).is_absolute()
    durable_count = inspection["durable_artifact_count"]
    file_count = inspection["file_count"]
    files = inspection["files"]
    assert isinstance(durable_count, int) and durable_count >= 25
    assert isinstance(file_count, int) and file_count >= 25
    assert isinstance(files, list)
    assert all(
        isinstance(item, dict)
        and not Path(str(cast(dict[str, object], item)["relative_path"])).is_absolute()
        for item in cast(list[object], files)
    )

    workflow_root = artifact_root / workflow_id
    sibling_root = artifact_root / "sibling-workflow"
    workflow_root.rename(sibling_root)
    workflow_root.symlink_to(sibling_root, target_is_directory=True)

    symlinked = runner.invoke(app, ["artifacts", "inspect", workflow_id, "--json"])
    assert symlinked.exit_code != 0
    assert _last_json(symlinked.output)["error"] == {
        "code": "VALUEERROR",
        "message": "artifact root is not confined",
    }


def test_research_validate_only_failure_is_machine_readable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "MONEY_MACHINE_DATABASE_URL",
        "postgresql+asyncpg://operator:local@127.0.0.1/money_machine",
    )
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["research", "import", "--packet", str(malformed), "--validate-only", "--json"],
    )

    assert result.exit_code != 0
    error = _last_json(result.output)["error"]
    assert isinstance(error, dict)
    assert error["code"] == "VALUEERROR"
    assert isinstance(error["message"], str) and error["message"]


def test_database_migration_failure_is_machine_readable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MONEY_MACHINE_DATABASE_URL",
        "postgresql+asyncpg://operator:local@127.0.0.1/money_machine",
    )

    def fail_upgrade(*_args: object, **_kwargs: object) -> None:
        raise ValueError("synthetic migration failure")

    monkeypatch.setattr(database_command.command, "upgrade", fail_upgrade)

    result = CliRunner().invoke(app, ["db", "migrate", "--json"])

    assert result.exit_code != 0
    assert _last_json(result.output)["error"] == {
        "code": "VALUEERROR",
        "message": "synthetic migration failure",
    }


def test_first_product_cli_rejects_missing_database_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MONEY_MACHINE_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    result = CliRunner().invoke(app, ["workflow", "status", "not-a-uuid", "--json"])

    assert result.exit_code != 0
    assert _last_json(result.output)["error"] == {
        "code": "CONFIGURATION_ERROR",
        "message": "database URL is required",
    }


def test_operator_settings_reject_periodic_scheduler_enablement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "MONEY_MACHINE_DATABASE_URL",
        "postgresql+asyncpg://operator:local@127.0.0.1/money_machine",
    )
    monkeypatch.setenv("MONEY_MACHINE_CONFIG_ROOT", str(REPO_ROOT / "config"))
    monkeypatch.setenv("MONEY_MACHINE_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("MONEY_MACHINE_PERIODIC_SCHEDULER_ENABLED", "true")

    with pytest.raises(ValueError, match="periodic scheduling is disabled"):
        Settings.from_env()


def test_first_product_operator_scripts_are_bounded_and_parse_cleanly() -> None:
    shell_script = REPO_ROOT / "scripts" / "run_first_product_slice.sh"
    powershell_script = REPO_ROOT / "scripts" / "run_first_product_slice.ps1"

    assert shell_script.is_file()
    assert powershell_script.is_file()
    subprocess.run(["bash", "-n", str(shell_script)], check=True)
    combined = shell_script.read_text() + powershell_script.read_text()
    lowered = combined.casefold()
    for forbidden in ("publish", "purchase", "message customer", "--live", "jq "):
        assert forbidden not in lowered
    if powershell := shutil.which("pwsh"):
        subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-Command",
                f"[scriptblock]::Create((Get-Content -Raw '{powershell_script}')) | Out-Null",
            ],
            check=True,
        )
