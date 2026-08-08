import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).parents[2]
DATABASE_SERVICES = ("postgres", "api", "worker", "scheduler")
COMPOSE_TEXT = (ROOT / "compose.yaml").read_text(encoding="utf-8")
PRODUCTION_COMPOSE_TEXT = (ROOT / "compose.prod.yaml").read_text(encoding="utf-8")


def _service_block(service_name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(service_name)}:\n"
        r"(?P<body>.*?)(?=^  [a-z][a-z0-9_-]*:\n|^volumes:\n|\Z)",
        COMPOSE_TEXT,
    )
    assert match is not None, f"missing Compose service: {service_name}"
    return match.group("body")


def _production_service_block(service_name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(service_name)}:\n"
        r"(?P<body>.*?)(?=^  [a-z][a-z0-9_-]*:\n|^volumes:\n|\Z)",
        PRODUCTION_COMPOSE_TEXT,
    )
    assert match is not None, f"missing production Compose service: {service_name}"
    return match.group("body")


def _compose_config(environment: dict[str, str] | None = None) -> dict[str, Any]:
    process_environment = os.environ.copy()
    if environment is not None:
        process_environment.update(environment)
    # The contract test must not inherit a developer DATABASE_URL or repo-local
    # .env file; both would mask the nested defaults this test is proving.
    process_environment["DATABASE_URL"] = ""
    result = subprocess.run(
        ["docker", "compose", "--env-file", os.devnull, "config", "--format", "json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env=process_environment,
        text=True,
    )
    return cast(dict[str, Any], json.loads(result.stdout))


def test_compose_declares_truthful_foundation_services() -> None:
    services_section = COMPOSE_TEXT.split("services:\n", 1)[1].split("\nvolumes:\n", 1)[0]
    services = set(re.findall(r"^  ([a-z][a-z0-9_-]*):$", services_section, re.MULTILINE))

    assert services == {"api", "postgres", "scheduler", "web", "worker"}
    assert "healthcheck:" in _service_block("postgres")
    assert 'restart: "no"' in _service_block("worker")
    assert 'restart: "no"' in _service_block("scheduler")


def test_production_compose_keeps_uncommissioned_processes_fail_closed() -> None:
    assert 'restart: "no"' in _production_service_block("worker")
    assert 'restart: "no"' in _production_service_block("scheduler")


def test_compose_shares_one_interpolated_database_contract() -> None:
    assert "x-database-environment: &database-environment" in COMPOSE_TEXT
    assert "POSTGRES_DB: ${POSTGRES_DB:-money_machine}" in COMPOSE_TEXT
    assert "POSTGRES_USER: ${POSTGRES_USER:-money_machine}" in COMPOSE_TEXT
    assert "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-local_development_only}" in COMPOSE_TEXT
    assert (
        "DATABASE_URL: ${DATABASE_URL:-postgresql+asyncpg://"
        "${POSTGRES_USER:-money_machine}:${POSTGRES_PASSWORD:-local_development_only}"
        "@postgres:5432/${POSTGRES_DB:-money_machine}}"
    ) in COMPOSE_TEXT
    for service_name in DATABASE_SERVICES:
        assert "<<: *database-environment" in _service_block(service_name)


def test_compose_cli_resolves_custom_credentials_without_developer_env() -> None:
    expected_environment = {
        "POSTGRES_DB": "contract_db",
        "POSTGRES_USER": "contract_user",
        "POSTGRES_PASSWORD": "contract_password",
        "DATABASE_URL": "postgresql+asyncpg://contract_user:contract_password@postgres:5432/contract_db",
    }
    try:
        config = _compose_config(
            {
                "POSTGRES_DB": expected_environment["POSTGRES_DB"],
                "POSTGRES_USER": expected_environment["POSTGRES_USER"],
                "POSTGRES_PASSWORD": expected_environment["POSTGRES_PASSWORD"],
                "DATABASE_URL": "postgresql+asyncpg://stale:stale@elsewhere:5432/stale",
            }
        )
    except OSError as error:
        pytest.skip(f"Docker Compose CLI unavailable: {error}")
    services = cast(dict[str, dict[str, Any]], config["services"])
    for service_name in DATABASE_SERVICES:
        assert services[service_name]["environment"] == expected_environment


def test_postgres_verifiers_require_authenticated_tcp_query() -> None:
    bash_verifier = (ROOT / "scripts" / "verify_postgres.sh").read_text(encoding="utf-8")
    powershell_verifier = (ROOT / "scripts" / "verify_postgres.ps1").read_text(encoding="utf-8")

    for verifier in (bash_verifier, powershell_verifier):
        assert "PGPASSWORD" in verifier
        assert "127.0.0.1" in verifier
        assert "SELECT 1;" in verifier
        assert "pg_isready" not in verifier
