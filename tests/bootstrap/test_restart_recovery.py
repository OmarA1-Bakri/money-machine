"""Restart recovery reclaims an expired lease and leaves a live lease alone."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from money_machine.deploy.database_migrations import apply_database_migrations
from money_machine.deploy.restart_recovery import RestartRecoveryRefusal, record_restart_recovery

ROOT = Path(__file__).parents[2]
_SHARED = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/money_machine"
_REMOTE = "postgresql+asyncpg://money_machine:redacted@db.example:5432/mm_t_0123456789abcdef0123"
_OTHER = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/app_database"
_ISOLATED = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/mm_t_0123456789abcdef0123"


def test_a_process_restart_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(RestartRecoveryRefusal, match="process_restart"):
        record_restart_recovery(_ISOLATED, restart_command="docker compose restart")


def test_a_docker_socket_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(RestartRecoveryRefusal, match="docker_socket"):
        record_restart_recovery(_ISOLATED, docker_socket=True)


def test_the_shared_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(RestartRecoveryRefusal, match="shared"):
        record_restart_recovery(_SHARED)


def test_a_remote_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(RestartRecoveryRefusal, match="remote"):
        record_restart_recovery(_REMOTE)


def test_a_standing_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(RestartRecoveryRefusal, match="isolated"):
        record_restart_recovery(_OTHER)


def test_a_missing_exit_78_hold_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _refuse_contact(monkeypatch)
    worker = tmp_path / "src/money_machine/orchestration/worker.py"
    scheduler = tmp_path / "src/money_machine/orchestration/scheduler.py"
    worker.parent.mkdir(parents=True)
    worker.write_text("no hold\n", encoding="utf-8")
    scheduler.write_text("Exit 78\n", encoding="utf-8")

    with pytest.raises(RestartRecoveryRefusal, match="exit_78"):
        record_restart_recovery(_ISOLATED, root=tmp_path)


async def test_an_isolated_restart_recovers(test_database: str) -> None:
    await asyncio.to_thread(apply_database_migrations, test_database, ROOT)

    recorded = await asyncio.to_thread(record_restart_recovery, test_database, root=ROOT)

    assert recorded.succeeded is True
    assert recorded.recovered_status == "READY"
    assert recorded.recovered_attempt == 1
    assert recorded.lease_cleared is True
    assert recorded.live_status == "RUNNING"
    assert recorded.live_owner == "worker-live"
    assert recorded.second_reclaim_count == 0
    assert recorded.worker_running is False
    assert recorded.containers_started is False


def _refuse_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("contact")

    monkeypatch.setattr("money_machine.deploy.restart_recovery.create_async_engine", boom)
