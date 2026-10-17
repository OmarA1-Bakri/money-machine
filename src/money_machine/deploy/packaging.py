"""Read the production package from the compose spec and the six runbooks.

The check does not run ``docker compose config``, build an image, or print a
secret. Worker and scheduler restart stay ``no`` while Exit 78 is held.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

REQUIRED_SERVICES = ("postgres", "api", "web", "worker", "scheduler")
HEALTHCHECKED_SERVICES = ("postgres", "api")
FAIL_CLOSED_SERVICES = ("worker", "scheduler")
POSTGRES_VOLUME = "postgres-data"
RUNBOOKS = (
    "docs/runbooks/LOCAL_DEVELOPMENT.md",
    "docs/runbooks/BACKUP_RESTORE.md",
    "docs/runbooks/INCIDENTS.md",
    "docs/runbooks/LIVE_COMMISSIONING.md",
    "docs/runbooks/ACCOUNT_CONNECTIONS.md",
    "docs/runbooks/PROVIDER_RECOVERY.md",
)
_COMPOSE = "compose.prod.yaml"
_SECRET_SHAPES = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\bsk-[A-Za-z0-9]{8,}"
    r"|\bghp_[A-Za-z0-9]{8,}"
    r"|postgres(?:ql)?://[^/\s:]+:[^@\s]+@"
)
_SECRET_ASSIGNMENT = re.compile(
    r"\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*(?!\$)(\S{6,})",
    re.IGNORECASE,
)
_SECRET_KEYS = ("PASSWORD", "SECRET", "TOKEN", "API_KEY")


class PackagingRefusal(ValueError):
    """The compose spec or a runbook does not match the fail-closed package."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProductionPackage:
    """The services, volume, healthchecks, and runbooks the proof checked."""

    services: tuple[str, ...]
    postgres_volume: str
    healthchecks: tuple[str, ...]
    worker_restart: str
    scheduler_restart: str
    runbooks: tuple[str, ...]
    docker_compose_config_ran: bool


def define_production_package(
    root: Path | None = None,
    *,
    accept_compose_config: bool = False,
) -> ProductionPackage:
    """Read ``compose.prod.yaml`` and the six runbooks from ``root``."""
    repo = Path(__file__).resolve().parents[3] if root is None else root
    compose_path = repo / _COMPOSE
    document = _load_mapping(compose_path, "compose")
    _refuse_secret_text(compose_path.read_text(encoding="utf-8"))
    runbooks = {relative: _read_runbook(repo / relative) for relative in RUNBOOKS}
    return inspect_production_package(
        document,
        runbooks,
        accept_compose_config=accept_compose_config,
    )


def inspect_production_package(
    document: Mapping[str, object],
    runbooks: Mapping[str, str],
    *,
    accept_compose_config: bool = False,
) -> ProductionPackage:
    """Check one parsed compose document and the runbook texts.

    ``accept_compose_config`` is refused. A passing docker compose config is
    not this package.
    """
    if accept_compose_config:
        raise PackagingRefusal("compose_config")
    services = _services(document)
    restarts: dict[str, str] = {}
    healthchecks: list[str] = []
    for name in REQUIRED_SERVICES:
        service = _service(services, name)
        _refuse_literal_secrets(service)
        if name in FAIL_CLOSED_SERVICES:
            restarts[name] = _restart(service)
        if name in HEALTHCHECKED_SERVICES:
            if not isinstance(service.get("healthcheck"), dict):
                raise PackagingRefusal("healthcheck")
            healthchecks.append(name)
        if name == "postgres":
            _require_volume(service, document)
    _require_runbooks(runbooks)
    return ProductionPackage(
        services=REQUIRED_SERVICES,
        postgres_volume=POSTGRES_VOLUME,
        healthchecks=tuple(healthchecks),
        worker_restart=restarts["worker"],
        scheduler_restart=restarts["scheduler"],
        runbooks=RUNBOOKS,
        docker_compose_config_ran=False,
    )


def _load_mapping(path: Path, code: str) -> dict[str, object]:
    if not path.is_file():
        raise PackagingRefusal(code)
    loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise PackagingRefusal(code)
    return {str(key): value for key, value in loaded.items()}


def _read_runbook(path: Path) -> str:
    if not path.is_file():
        raise PackagingRefusal("runbook")
    return path.read_text(encoding="utf-8")


def _services(document: Mapping[str, object]) -> Mapping[str, object]:
    services = document.get("services")
    if not isinstance(services, dict):
        raise PackagingRefusal("service")
    return {str(key): value for key, value in services.items()}


def _service(services: Mapping[str, object], name: str) -> Mapping[str, object]:
    service = services.get(name)
    if not isinstance(service, dict):
        raise PackagingRefusal("service")
    return {str(key): value for key, value in service.items()}


def _restart(service: Mapping[str, object]) -> str:
    restart = service.get("restart")
    if restart != "no":
        raise PackagingRefusal("restart")
    return "no"


def _require_volume(service: Mapping[str, object], document: Mapping[str, object]) -> None:
    volumes = service.get("volumes")
    named = document.get("volumes")
    mounted = isinstance(volumes, list) and any(
        isinstance(item, str) and item.split(":", 1)[0] == POSTGRES_VOLUME for item in volumes
    )
    declared = isinstance(named, dict) and POSTGRES_VOLUME in named
    if not mounted or not declared:
        raise PackagingRefusal("volume")


def _require_runbooks(runbooks: Mapping[str, str]) -> None:
    if tuple(runbooks) != RUNBOOKS:
        raise PackagingRefusal("runbook")
    for relative in RUNBOOKS:
        text = runbooks[relative]
        _refuse_secret_text(text)
        if "Exit 78" not in text:
            raise PackagingRefusal("exit_78")


def _refuse_secret_text(text: str) -> None:
    if _SECRET_SHAPES.search(text) or _SECRET_ASSIGNMENT.search(text):
        raise PackagingRefusal("secret")


def _refuse_literal_secrets(service: Mapping[str, object]) -> None:
    environment = service.get("environment")
    if environment is None:
        return
    pairs: list[tuple[object, object]]
    if isinstance(environment, dict):
        pairs = list(environment.items())
    elif isinstance(environment, list):
        pairs = []
        for item in environment:
            if isinstance(item, str) and "=" in item:
                key, value = item.split("=", 1)
                pairs.append((key, value))
    else:
        raise PackagingRefusal("secret")
    for key, value in pairs:
        if not isinstance(key, str) or not isinstance(value, str):
            raise PackagingRefusal("secret")
        folded = key.upper()
        if any(marker in folded for marker in _SECRET_KEYS) and not value.startswith("$"):
            raise PackagingRefusal("secret")
