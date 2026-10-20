"""Record health for the API, web, PostgreSQL, worker, and scheduler.

The API liveness function is called in process. The web route is the static
contract in ``apps/web``. PostgreSQL answers ``SELECT 1`` on a throwaway
loopback database that is dropped before the function returns. The worker and
scheduler stay Exit 78: they are held and not running. Docker is not called
and no container is started.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from money_machine.api.routers.health import health
from money_machine.deploy.controls import ServiceControlRefusal, confirm_exit_78_held
from money_machine.persistence.database import check_connectivity

_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
_SHARED = frozenset({"money_machine", "template0", "template1"})
_NAME = re.compile(r"^mm_t_[0-9a-f]{20}$")
_WEB = Path("apps/web/app/api/health/route.ts")
_WEB_BODY = re.compile(
    r"export const dynamic = \"force-static\";\s+"
    r"export function GET\(\) \{\s+"
    r"return NextResponse\.json\(\{\s+"
    r"service: \"operator-console\",\s+"
    r"status: \"healthy\",\s+"
    r"dependencies: \"unverified\",\s+"
    r"externalActions: false,\s+"
    r"\}\);\s+"
    r"\}",
    re.MULTILINE,
)


class ServiceHealthRefusal(ValueError):
    """A health claim started a process or used a database that is not isolated."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ServiceHealth:
    """In-process liveness, a static web route, and one PostgreSQL round trip."""

    succeeded: bool
    api_status: str
    api_service: str
    api_version: str
    web_status: str
    web_service: str
    web_dependencies: str
    web_external_actions: bool
    postgres_reachable: bool
    worker_held: bool
    scheduler_held: bool
    worker_running: bool
    scheduler_running: bool
    containers_started: bool


def record_service_health(
    admin_url: str,
    *,
    root: Path | None = None,
    docker_socket: bool = False,
    claim_running: bool = False,
) -> ServiceHealth:
    """Prove the five-service health contract without starting a container."""
    if docker_socket:
        raise ServiceHealthRefusal("docker_socket")
    if claim_running:
        raise ServiceHealthRefusal("status_word")
    _refuse_admin(admin_url)
    repo = Path(__file__).resolve().parents[3] if root is None else root
    _require_hold(repo)
    _require_web(repo)
    api = asyncio.run(health())
    if api.status != "ok" or api.service != "api" or api.version == "":
        raise ServiceHealthRefusal("api")
    reachable = _postgres_round_trip(admin_url)
    if not reachable:
        raise ServiceHealthRefusal("postgres")
    return ServiceHealth(
        succeeded=True,
        api_status=api.status,
        api_service=api.service,
        api_version=api.version,
        web_status="healthy",
        web_service="operator-console",
        web_dependencies="unverified",
        web_external_actions=False,
        postgres_reachable=True,
        worker_held=True,
        scheduler_held=True,
        worker_running=False,
        scheduler_running=False,
        containers_started=False,
    )


def _require_hold(root: Path) -> None:
    try:
        held = confirm_exit_78_held(root)
    except ServiceControlRefusal as error:
        raise ServiceHealthRefusal(error.code) from error
    if not held.worker_held or not held.scheduler_held or held.running:
        raise ServiceHealthRefusal("exit_78")


def _require_web(root: Path) -> None:
    path = root / _WEB
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ServiceHealthRefusal("web_route") from error
    if _WEB_BODY.search(text) is None:
        raise ServiceHealthRefusal("web_route")


def _refuse_admin(url: str) -> None:
    try:
        parsed = make_url(url)
    except Exception as error:
        raise ServiceHealthRefusal("url") from error
    host = parsed.host
    name = parsed.database
    if host is None or name is None or host == "" or name == "":
        raise ServiceHealthRefusal("url")
    if host.casefold() not in _LOOPBACK:
        raise ServiceHealthRefusal("remote")
    folded = name.casefold()
    if folded in _SHARED:
        raise ServiceHealthRefusal("shared")
    if folded != "postgres":
        raise ServiceHealthRefusal("admin")


def _postgres_round_trip(admin_url: str) -> bool:
    name = "mm_t_" + uuid4().hex[:20]
    if _NAME.fullmatch(name) is None:
        raise ServiceHealthRefusal("isolated")
    probe = make_url(admin_url).set(database=name).render_as_string(hide_password=False)
    try:
        asyncio.run(_create(admin_url, name))
        return asyncio.run(_reachable(probe))
    except ServiceHealthRefusal:
        raise
    except Exception as error:
        raise ServiceHealthRefusal("postgres") from error
    finally:
        asyncio.run(_drop(admin_url, name))


async def _create(admin_url: str, name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await engine.dispose()


async def _reachable(url: str) -> bool:
    engine = create_async_engine(url)
    try:
        return await check_connectivity(engine)
    finally:
        await engine.dispose()


async def _drop(admin_url: str, name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        await engine.dispose()
