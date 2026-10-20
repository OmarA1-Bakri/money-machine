"""A durable job survives a new connection and is claimed once."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from money_machine.deploy.database_migrations import apply_database_migrations
from money_machine.deploy.durable_jobs import DurableJobRefusal, record_durable_jobs

ROOT = Path(__file__).parents[2]
_SHARED = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/money_machine"
_REMOTE = "postgresql+asyncpg://money_machine:redacted@db.example:5432/mm_t_0123456789abcdef0123"
_OTHER = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/app_database"
_ISOLATED = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/mm_t_0123456789abcdef0123"


def test_a_memory_claim_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(DurableJobRefusal, match="memory"):
        record_durable_jobs(_ISOLATED, memory_only=True)


def test_a_docker_socket_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(DurableJobRefusal, match="docker_socket"):
        record_durable_jobs(_ISOLATED, docker_socket=True)


def test_the_shared_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(DurableJobRefusal, match="shared"):
        record_durable_jobs(_SHARED)


def test_a_remote_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(DurableJobRefusal, match="remote"):
        record_durable_jobs(_REMOTE)


def test_a_standing_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(DurableJobRefusal, match="isolated"):
        record_durable_jobs(_OTHER)


def test_a_missing_exit_78_hold_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _refuse_contact(monkeypatch)
    worker = tmp_path / "src/money_machine/orchestration/worker.py"
    scheduler = tmp_path / "src/money_machine/orchestration/scheduler.py"
    worker.parent.mkdir(parents=True)
    worker.write_text("no hold\n", encoding="utf-8")
    scheduler.write_text("Exit 78\n", encoding="utf-8")

    with pytest.raises(DurableJobRefusal, match="exit_78"):
        record_durable_jobs(_ISOLATED, root=tmp_path)


async def test_a_durable_job_is_claimed_from_a_new_connection(test_database: str) -> None:
    await asyncio.to_thread(apply_database_migrations, test_database, ROOT)

    recorded = await asyncio.to_thread(record_durable_jobs, test_database, root=ROOT)

    assert recorded.succeeded is True
    assert recorded.persisted is True
    assert recorded.claimed_status == "RUNNING"
    assert recorded.lease_owner == "worker-0"
    assert recorded.future_status == "READY"
    assert recorded.second_claim is False
    assert recorded.worker_running is False
    assert recorded.containers_started is False


def _refuse_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("contact")

    monkeypatch.setattr("money_machine.deploy.durable_jobs.create_async_engine", boom)
