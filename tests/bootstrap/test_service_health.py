"""API, web, and PostgreSQL health, with the worker and scheduler held."""

from __future__ import annotations

from pathlib import Path

import pytest

from money_machine.deploy.service_health import ServiceHealthRefusal, record_service_health
from money_machine.version import __version__
from tests.conftest import admin_url

ROOT = Path(__file__).parents[2]
_SHARED = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/money_machine"
_REMOTE = "postgresql+asyncpg://money_machine:redacted@db.example:5432/postgres"
_OTHER = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/mm_t_0123456789abcdef0123"
_ADMIN = "postgresql+asyncpg://money_machine:redacted@127.0.0.1:5432/postgres"


def test_a_docker_socket_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(ServiceHealthRefusal, match="docker_socket"):
        record_service_health(_ADMIN, docker_socket=True)


def test_a_running_claim_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(ServiceHealthRefusal, match="status_word"):
        record_service_health(_ADMIN, claim_running=True)


def test_the_shared_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(ServiceHealthRefusal, match="shared"):
        record_service_health(_SHARED)


def test_a_remote_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(ServiceHealthRefusal, match="remote"):
        record_service_health(_REMOTE)


def test_a_non_admin_database_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)

    with pytest.raises(ServiceHealthRefusal, match="admin"):
        record_service_health(_OTHER)


def test_a_missing_exit_78_hold_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _refuse_contact(monkeypatch)
    _write_hold(tmp_path, worker="no hold\n", scheduler="Exit 78\n")

    with pytest.raises(ServiceHealthRefusal, match="exit_78"):
        record_service_health(_ADMIN, root=tmp_path)


def test_a_changed_web_route_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_contact(monkeypatch)
    _write_hold(tmp_path, worker="Exit 78 held\n", scheduler="Exit 78\n")
    route = tmp_path / "apps/web/app/api/health/route.ts"
    route.parent.mkdir(parents=True)
    route.write_text('export function GET() { return { status: "up" }; }\n', encoding="utf-8")

    with pytest.raises(ServiceHealthRefusal, match="web_route"):
        record_service_health(_ADMIN, root=tmp_path)


def test_service_health_round_trip(postgres_available: bool) -> None:
    if not postgres_available:
        pytest.skip("PostgreSQL is unavailable")

    recorded = record_service_health(admin_url(), root=ROOT)

    assert recorded.succeeded is True
    assert recorded.api_status == "ok"
    assert recorded.api_service == "api"
    assert recorded.api_version == __version__
    assert recorded.web_status == "healthy"
    assert recorded.web_service == "operator-console"
    assert recorded.web_dependencies == "unverified"
    assert recorded.web_external_actions is False
    assert recorded.postgres_reachable is True
    assert recorded.worker_held is True
    assert recorded.scheduler_held is True
    assert recorded.worker_running is False
    assert recorded.scheduler_running is False
    assert recorded.containers_started is False


def _refuse_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("contact")

    monkeypatch.setattr("money_machine.deploy.service_health.create_async_engine", boom)


def _write_hold(root: Path, *, worker: str, scheduler: str) -> None:
    worker_path = root / "src/money_machine/orchestration/worker.py"
    scheduler_path = root / "src/money_machine/orchestration/scheduler.py"
    worker_path.parent.mkdir(parents=True)
    worker_path.write_text(worker, encoding="utf-8")
    scheduler_path.write_text(scheduler, encoding="utf-8")
