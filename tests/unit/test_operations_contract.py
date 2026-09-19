"""Deployment and operations contract checks that need no containers.

Each assertion pins a finding an independent reviewer demonstrated: a healthcheck that
could never pass, a credential that survived in a URL, a gate that did not run on this
branch, and a build context that carried private material.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Final, cast

import pytest
import yaml
from sqlalchemy.engine import make_url

from money_machine.config.loader import resolve_runtime_environment
from money_machine.config.runtime import (
    REDACTED,
    SECRET_QUERY_KEYS,
    DatabaseSettings,
    Secret,
    load_runtime_settings,
)

ROOT: Final = Path(__file__).parents[2]
COMPOSE: Final = ROOT / "compose.yaml"
COMPOSE_PROD: Final = ROOT / "compose.prod.yaml"
CI: Final = ROOT / ".github/workflows/ci.yml"
DOCKERIGNORE: Final = ROOT / ".dockerignore"
ENV_EXAMPLE: Final = ROOT / ".env.example"


def load_yaml(path: Path) -> dict[Any, Any]:
    """Parse one YAML document as a mapping.

    The key type is ``Any`` because a GitHub workflow's bare ``on:`` key is parsed by YAML
    as the boolean ``True``.
    """
    return cast(dict[Any, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


def services(path: Path) -> dict[str, Any]:
    """The service definitions in one Compose file."""
    return cast(dict[str, Any], load_yaml(path)["services"])


def test_the_api_container_probe_is_liveness_not_readiness() -> None:
    """A readiness probe here would keep a fresh, unmigrated stack permanently unhealthy."""
    for path in (COMPOSE, COMPOSE_PROD):
        probe = " ".join(services(path)["api"]["healthcheck"]["test"])
        assert "/health" in probe, path.name
        assert "/readiness" not in probe, path.name


def test_worker_and_scheduler_stay_fail_closed_in_both_compose_files() -> None:
    """Neither may restart-loop, and neither may claim a health contract it cannot meet."""
    for path in (COMPOSE, COMPOSE_PROD):
        for name in ("worker", "scheduler"):
            service = services(path)[name]
            assert service["restart"] == "no", f"{path.name}:{name}"
            assert "healthcheck" not in service, f"{path.name}:{name}"


def test_production_images_are_built_from_the_maintained_dockerfiles() -> None:
    """Production must not build from a stale image definition."""
    production = services(COMPOSE_PROD)

    assert production["api"]["build"]["dockerfile"] == "infra/docker/api.Dockerfile"
    assert production["web"]["build"]["dockerfile"] == "infra/docker/web.Dockerfile"


def test_production_services_select_the_production_environment() -> None:
    """Production must not silently inherit the loader's development default."""
    production = services(COMPOSE_PROD)
    for name in ("api", "worker", "scheduler"):
        environment = resolve_runtime_environment(production[name]["environment"])
        assert environment.value == "production", name


@pytest.mark.parametrize("password", ["literal%40value", "reserved@:/?#%value", " padded "])
@pytest.mark.parametrize("compose_path", [COMPOSE, COMPOSE_PROD])
@pytest.mark.parametrize("external_override", [False, True])
def test_compose_preserves_the_postgres_password(
    password: str, compose_path: Path, external_override: bool
) -> None:
    """The actual resolved Compose carrier must give the server and driver the same secret."""
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in {"DATABASE_URL", "DATABASE_PASSWORD", "POSTGRES_PASSWORD"}
        and not name.startswith("MONEY_MACHINE_")
    }
    environment["POSTGRES_PASSWORD"] = password
    environment["POSTGRES_USER"] = "operator"
    environment["POSTGRES_DB"] = "mm"
    if external_override:
        environment["DATABASE_URL"] = "postgresql+asyncpg://operator:remote%40secret@remote:5432/mm"
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            os.devnull,
            "-f",
            str(compose_path),
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    resolved = json.loads(result.stdout)["services"]
    server_password = resolved["postgres"]["environment"]["POSTGRES_PASSWORD"]
    expected_password = (
        "remote@secret" if external_override and compose_path == COMPOSE else server_password
    )
    for name in ("api", "worker", "scheduler"):
        settings = load_runtime_settings(resolved[name]["environment"])
        assert make_url(settings.database.dsn()).password == expected_password
        assert password not in settings.database.safe_url


def test_every_python_image_carries_what_the_runtime_reads() -> None:
    """Configuration, prompts and migrations are needed at runtime, so they must be present."""
    for name in ("api", "worker", "scheduler"):
        body = (ROOT / f"infra/docker/{name}.Dockerfile").read_text(encoding="utf-8")
        assert "COPY config ./config" in body, name
        assert "COPY prompts ./prompts" in body, name
    root_image = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for required in ("COPY config", "COPY prompts", "COPY migrations", "COPY alembic.ini"):
        assert required in root_image


def test_the_build_context_excludes_private_material() -> None:
    """The private source, environment files and operator authority never reach the daemon."""
    patterns = {
        line.strip()
        for line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    for required in ("*.pdf", ".env", "config/autonomy.yaml", "runtime/", ".git", ".omx/"):
        assert required in patterns, required


def test_continuous_integration_gates_this_branch_and_proves_what_it_claims() -> None:
    """A gate that does not run on the working branch is not a gate."""
    workflow = load_yaml(CI)
    body = CI.read_text(encoding="utf-8")
    steps = workflow["jobs"]["verify"]["steps"]
    commands = " ".join(str(step.get("run", "")) for step in steps)

    # PyYAML parses the bare key `on:` as the boolean True.
    triggers = cast(dict[str, Any], workflow[True])
    assert "build/full-automation" in triggers["push"]["branches"]
    assert "continue-on-error" not in body
    assert "|| true" not in body
    assert "postgres" in workflow["jobs"]["verify"]["services"]
    assert "alembic upgrade head" in commands
    assert "alembic check" in commands
    assert "alembic downgrade base" in commands
    assert "money-machine db seed" in commands
    assert "seed is not idempotent" in commands, "the second seed run must be asserted"
    assert "ruff format --check src tests scripts migrations" in commands
    assert "ruff check src tests scripts apps migrations" in commands


def test_the_uncommissioned_workflows_are_untouched_refusal_gates() -> None:
    """The end-to-end and release workflows must keep refusing until commissioned."""
    e2e = (ROOT / ".github/workflows/e2e.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch" in e2e
    assert "scripts/e2e.sh" in e2e
    assert "workflow_dispatch" in release


@pytest.mark.parametrize("key", sorted(SECRET_QUERY_KEYS))
def test_a_credential_in_a_query_parameter_is_stripped(key: str) -> None:
    """A driver honours these parameters, so they must never survive into a stored URL."""
    settings = DatabaseSettings(
        url=f"postgresql+asyncpg://user@db:5432/mm?{key}=QUERY_CANARY&sslmode=disable"
    )

    assert "QUERY_CANARY" not in settings.safe_url
    assert "QUERY_CANARY" not in repr(settings)
    assert "QUERY_CANARY" not in settings.model_dump_json()
    assert "sslmode=disable" in settings.safe_url
    assert settings.password is not None
    assert settings.password.reveal() == "QUERY_CANARY"


def test_a_query_credential_and_an_explicit_one_must_agree() -> None:
    """Two disagreeing sources are a configuration error, not a silent preference."""
    with pytest.raises(ValueError, match="supplied twice with different values"):
        DatabaseSettings(
            url="postgresql+asyncpg://user@db:5432/mm?password=one",
            password=Secret("two"),
        )


def test_the_environment_example_matches_what_the_code_reads() -> None:
    """A documented variable nobody reads is a trap; an undocumented one is a surprise."""
    body = ENV_EXAMPLE.read_text(encoding="utf-8")
    documented = {
        line.split("=", 1)[0]
        for line in body.splitlines()
        if line and not line.startswith("#") and "=" in line
    }

    for required in (
        "APP_ENV",
        "MONEY_MACHINE_DATABASE_URL",
        "MONEY_MACHINE_DATABASE_PASSWORD",
        "DATABASE_URL",
        "API_PORT",
        "WEB_PORT",
        "POSTGRES_PORT",
    ):
        assert required in documented, required
    for provider in ("LLM", "ETSY", "NOTION", "COMPOSIO", "POSTHOG"):
        assert f"{provider}_API_KEY" in documented, provider
    assert "NOTION_TOKEN" not in documented, "renamed: the loader reads NOTION_API_KEY"
    assert "EXTERNAL_EFFECT_MODE" not in documented, "nothing reads this flag"


def test_provider_credentials_are_discovered_under_the_documented_names() -> None:
    """The names in the example file are the names the loader actually reads."""
    settings = load_runtime_settings(
        {
            "LLM_API_KEY": "a",
            "ETSY_API_KEY": "b",
            "NOTION_API_KEY": "c",
            "COMPOSIO_API_KEY": "d",
            "POSTHOG_API_KEY": "e",
        }
    )

    assert all(provider.configured for provider in settings.providers)
    assert REDACTED in json.dumps(settings.model_dump(mode="json"))
