from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import cast

import pytest
from alembic import command
from alembic.config import Config
from typer.testing import CliRunner

from money_machine.cli.commands import database as database_command
from money_machine.cli.main import app
from money_machine.config.settings import Settings
from money_machine.domain.models.asset import ArtifactReference
from money_machine.integrations.storage.local import LocalArtifactStore

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


def _single_qualifying_fixture(tmp_path: Path) -> Path:
    payload = cast(dict[str, object], json.loads(FIXTURE.read_text(encoding="utf-8")))
    observations = cast(list[dict[str, object]], payload["observations"])
    for observation in observations:
        if str(observation["identity_niche"]).strip().casefold() == "budget moms":
            continue
        inputs = cast(dict[str, str], observation["qualification_inputs"])
        for dimension in inputs:
            inputs[dimension] = "1"
    path = tmp_path / "single-qualifying.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


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
@pytest.mark.parametrize(
    "single_qualifying",
    (False, True),
    ids=("multiple-qualifying", "single-qualifying"),
)
def test_first_product_cli_import_start_drain_replay_and_inspect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    single_qualifying: bool,
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

    fixture = _single_qualifying_fixture(tmp_path) if single_qualifying else FIXTURE
    imported = runner.invoke(app, ["research", "import", "--packet", str(fixture), "--json"])
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

    exported = runner.invoke(app, ["artifacts", "export", workflow_id, "--json"])
    assert exported.exit_code == 0, exported.output
    export_receipt = _last_json(exported.output)
    product_id = str(export_receipt["product_id"])
    export_root = Path(str(export_receipt["artifact_path"]))
    assert product_id.startswith("PS-")
    assert export_root == artifact_root / "products" / product_id
    assert export_receipt["replayed"] is False
    assert export_receipt["external_mutations"] == 0
    assert export_receipt["spend_usd"] == "0.00"
    assert (export_root / "research" / "packet.json").is_file()
    assert (export_root / "shortlist.json").is_file()
    assert (export_root / "qualification.json").is_file()
    assert (export_root / "primary.json").is_file()
    assert (export_root / "backup.json").is_file() is not single_qualifying
    assert (export_root / "product-spec.json").is_file()
    assert (export_root / "dedupe-result.json").is_file()
    assert (export_root / "product").is_dir()
    assert len(list((export_root / "variants").glob("*.css"))) in {3, 4}
    assert (export_root / "qa-result.json").is_file()
    assert (export_root / "listing" / "listing-package.json").is_file()
    assert len(list((export_root / "images").glob("*.png"))) == 10
    assert (export_root / "video" / "preview.mp4").is_file()
    assert (export_root / "access" / "README-access.pdf").is_file()
    assert (export_root / "preflight-result.json").is_file()
    assert (export_root / "manifest.json").is_file()
    assert (export_root / "PRODUCT_REVIEW.md").is_file()
    manifest = cast(
        dict[str, object], json.loads((export_root / "manifest.json").read_text(encoding="utf-8"))
    )
    assert manifest["terminal_state"] == "DRAFT_READY"
    assert manifest["research_rows"] == 30
    assert manifest["candidates_scored"] == 5
    assert manifest["candidates_shortlisted"] == 5
    assert manifest["tags"] == 13
    assert manifest["images"] == 10
    assert manifest["videos"] == 1
    assert manifest["access_pdfs"] == 1
    assert manifest["external_mutations"] == 0
    assert manifest["spend_usd"] == "0.00"
    inventory = cast(list[dict[str, object]], manifest["files"])
    assert len(inventory) + 1 == export_receipt["file_count"]
    for item in inventory:
        path = export_root / str(item["relative_path"])
        data = path.read_bytes()
        assert len(data) == item["byte_count"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
    committed_bytes = {
        path.relative_to(export_root).as_posix(): path.read_bytes()
        for path in export_root.rglob("*")
        if path.is_file()
    }
    review_text = (export_root / "PRODUCT_REVIEW.md").read_text(encoding="utf-8")
    assert ("- Backup:" in review_text) is not single_qualifying

    export_replay = runner.invoke(app, ["artifacts", "export", workflow_id, "--json"])
    assert export_replay.exit_code == 0, export_replay.output
    replay_receipt = _last_json(export_replay.output)
    assert replay_receipt["manifest_sha256"] == export_receipt["manifest_sha256"]
    assert replay_receipt["file_count"] == export_receipt["file_count"]
    assert replay_receipt["replayed"] is True
    assert {
        path.relative_to(export_root).as_posix(): path.read_bytes()
        for path in export_root.rglob("*")
        if path.is_file()
    } == committed_bytes

    (export_root / "manifest.json").unlink()
    (export_root / "primary.json").unlink()
    resumed = runner.invoke(app, ["artifacts", "export", workflow_id, "--json"])
    assert resumed.exit_code == 0, resumed.output
    resumed_receipt = _last_json(resumed.output)
    assert resumed_receipt["manifest_sha256"] == export_receipt["manifest_sha256"]
    assert resumed_receipt["replayed"] is False
    assert (export_root / "primary.json").is_file()

    if not single_qualifying:
        (export_root / "manifest.json").unlink()
        (export_root / "primary.json").unlink()
        original_put_bytes = LocalArtifactStore.put_bytes
        injected = False

        def inject_during_export(
            store: LocalArtifactStore,
            relative_path: str | Path | PurePosixPath,
            data: bytes,
            media_type: str,
        ) -> ArtifactReference:
            nonlocal injected
            path = PurePosixPath(str(relative_path))
            targets_export = store.root == export_root or path.is_relative_to(
                PurePosixPath("products") / product_id
            )
            if targets_export and not injected:
                injected = True
                (export_root / "injected-during-export.bin").write_bytes(b"foreign")
            return original_put_bytes(store, relative_path, data, media_type)

        monkeypatch.setattr(LocalArtifactStore, "put_bytes", inject_during_export)
        raced = runner.invoke(app, ["artifacts", "export", workflow_id, "--json"])
        assert raced.exit_code != 0
        assert _last_json(raced.output)["error"] == {
            "code": "VALUEERROR",
            "message": "export contains unexpected files: injected-during-export.bin",
        }
        monkeypatch.setattr(LocalArtifactStore, "put_bytes", original_put_bytes)
        (export_root / "injected-during-export.bin").unlink()
        recovered = runner.invoke(app, ["artifacts", "export", workflow_id, "--json"])
        assert recovered.exit_code == 0, recovered.output

    unexpected = export_root / "unexpected.bin"
    unexpected.write_bytes(b"foreign")
    unexpected_replay = runner.invoke(app, ["artifacts", "export", workflow_id, "--json"])
    assert unexpected_replay.exit_code != 0
    assert _last_json(unexpected_replay.output)["error"] == {
        "code": "VALUEERROR",
        "message": "export contains unexpected files: unexpected.bin",
    }
    unexpected.unlink()

    (export_root / "primary.json").write_bytes(b"forged")
    forged_replay = runner.invoke(app, ["artifacts", "export", workflow_id, "--json"])
    assert forged_replay.exit_code != 0
    assert _last_json(forged_replay.output)["error"] == {
        "code": "VALUEERROR",
        "message": "artifact byte count mismatch",
    }

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
    assert "artifacts export" in combined
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
