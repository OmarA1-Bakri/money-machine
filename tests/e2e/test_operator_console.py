"""Live browser acceptance for the seven request-time operator collections.

Run against the integrated fixture stack; no test-only dataset supplies the UI.
The proving test deliberately uses only dependencies available on the baseline.
"""

from __future__ import annotations

import asyncio
import os
import signal
import socket
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest
from playwright.sync_api import Page, sync_playwright

ROUTES = [
    ("/", "now"),
    ("/pipeline", "pipeline"),
    ("/shop", "shop"),
    ("/blocked", "blocked"),
    ("/decisions", "decisions"),
    ("/incidents", "incidents"),
    ("/settings", "settings"),
]


def _assert_port_free(port: int) -> None:
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(f"Assigned console test port {port} is occupied") from error


async def _database_action(admin: str, name: str, *, drop: bool = False) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(admin, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            command = (
                f'DROP DATABASE "{name}" WITH (FORCE)' if drop else f'CREATE DATABASE "{name}"'
            )
            await connection.execute(text(command))
    finally:
        await engine.dispose()


def _wait_for(url: str, process: subprocess.Popen[bytes], log: Path) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Console test service exited: {log.read_text()}")
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Console test service did not become ready: {log.read_text()}")


@pytest.fixture(scope="module")
def operator_stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[str, str, str]]:
    """External mode preserves baseline RED; default mode owns an isolated real stack."""
    run_id = os.environ.get("MONEY_MACHINE_RUN_ID", "20261020T211445Z")
    external_web = os.environ.get("MONEY_MACHINE_WEB_URL")
    api_url = os.environ.get("API_BASE_URL", "http://127.0.0.1:8100")
    if external_web:
        yield external_web, api_url, run_id
        return

    _assert_port_free(8100)
    _assert_port_free(3100)
    admin = os.environ.get("MONEY_MACHINE_TEST_ADMIN_DATABASE_URL")
    if not admin:
        raise RuntimeError(
            "Self-contained console E2E requires the explicit test admin database URL"
        )
    root = Path(__file__).resolve().parents[2]
    output = tmp_path_factory.mktemp("operator-console")
    name = "mm_console_" + uuid.uuid4().hex[:16]
    database_url = admin.rsplit("/", 1)[0] + "/" + name
    environment = {
        **os.environ,
        "APP_ENV": "test",
        "MONEY_MACHINE_DATABASE_URL": database_url,
        "MONEY_MACHINE_RUN_ID": run_id,
        "MONEY_MACHINE_EVIDENCE_ROOT": str(output),
        "API_BASE_URL": "http://127.0.0.1:8100",
        "NEXT_TELEMETRY_DISABLED": "1",
    }
    processes: list[subprocess.Popen[bytes]] = []
    asyncio.run(_database_action(admin, name))
    try:
        for command in [
            ["uv", "run", "--frozen", "alembic", "upgrade", "head"],
            ["bash", "scripts/e2e.sh", "--fixture"],
        ]:
            completed = subprocess.run(
                command, cwd=root, env=environment, capture_output=True, text=True, timeout=240
            )
            assert completed.returncode == 0, completed.stdout + completed.stderr
        for command, filename, url in [
            (
                [
                    "uv",
                    "run",
                    "--frozen",
                    "uvicorn",
                    "money_machine.api.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8100",
                ],
                "api.log",
                f"http://127.0.0.1:8100/operator/now?{urlencode({'run_id': run_id})}",
            ),
            (
                [
                    "pnpm",
                    "--filter",
                    "@money-machine/web",
                    "dev",
                    "--hostname",
                    "127.0.0.1",
                    "--port",
                    "3100",
                ],
                "web.log",
                "http://127.0.0.1:3100",
            ),
        ]:
            log = output / filename
            with log.open("wb") as stream:
                process = subprocess.Popen(
                    command,
                    cwd=root,
                    env=environment,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            processes.append(process)
            _wait_for(url, process, log)
        yield "http://127.0.0.1:3100", "http://127.0.0.1:8100", run_id
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        asyncio.run(_database_action(admin, name, drop=True))


@pytest.fixture
def operator_page() -> Iterator[Page]:
    with sync_playwright() as playwright:
        executable = os.environ.get("MONEY_MACHINE_BROWSER_EXECUTABLE")
        browser = playwright.chromium.launch(
            executable_path=executable,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        yield page
        browser.close()


@pytest.mark.parametrize(("route", "view"), ROUTES)
def test_all_routes_show_run_records(
    operator_page: Page, operator_stack: tuple[str, str, str], route: str, view: str
) -> None:
    web_url, api_url, run_id = operator_stack
    query = urlencode({"run_id": run_id})
    operator_page.goto(f"{web_url}{route}?{query}", wait_until="networkidle")
    main = operator_page.locator("main").inner_text()
    assert run_id in main
    response = httpx.get(f"{api_url}/operator/{view}?{query}")
    assert response.status_code == 200
    envelope = response.json()
    assert envelope["run_id"] == run_id
    assert envelope["items"], f"{view} must contain persisted fixture rows"
    for item in envelope["items"]:
        assert item["label"] in main
        assert item["state"] in main
        assert item["id"] in main
        if view in {"now", "pipeline", "shop"} and item["product_id"]:
            assert item["product_id"] in main
        if view == "shop" and item["listing_version_id"]:
            assert item["listing_version_id"] in main
    for link in operator_page.locator("nav a").all():
        assert f"run_id={run_id}" in (link.get_attribute("href") or "")
