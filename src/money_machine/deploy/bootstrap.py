"""Record a fresh bootstrap without starting a container.

The operator scripts install frozen Python and Node locks, then ask Docker
to render ``compose.yaml``. This module runs the two frozen checks and
renders that file itself. It does not call Docker and it does not start
the stack.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

_SCRIPTS = ("scripts/bootstrap.sh", "scripts/bootstrap.ps1")
_REQUIRED = (
    "uv sync --frozen",
    "pnpm install --frozen-lockfile",
    "docker compose config --quiet",
)
_FORBIDDEN = ("docker compose up", "git push", "publish", "checkout")
_SERVICES = ("postgres", "api", "web", "worker", "scheduler")
_HEALTH = ("postgres", "api", "web")
_HELD = ("worker", "scheduler")
_PYTHON = ("uv", "lock", "--check")
_NODE = ("pnpm", "install", "--frozen-lockfile", "--lockfile-only", "--ignore-scripts")

Runner = Callable[[Sequence[str], Path], int]


class BootstrapRefusal(ValueError):
    """The scripts, the locks, the compose spec, or a stack start is refused."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class FreshBootstrap:
    """The frozen checks and the rendered compose services."""

    python_lock_checked: bool
    node_lock_checked: bool
    compose_rendered: bool
    services: tuple[str, ...]
    containers_started: bool
    succeeded: bool


def record_fresh_bootstrap(
    root: Path | None = None,
    *,
    runner: Runner | None = None,
) -> FreshBootstrap:
    """Check the frozen locks and render the compose file. No container starts."""
    repo = Path(__file__).resolve().parents[3] if root is None else root
    _scripts(repo)
    services = _compose(repo)
    execute = _default_runner if runner is None else runner
    if execute(_PYTHON, repo) != 0:
        raise BootstrapRefusal("python")
    if execute(_NODE, repo) != 0:
        raise BootstrapRefusal("node")
    return FreshBootstrap(
        python_lock_checked=True,
        node_lock_checked=True,
        compose_rendered=True,
        services=services,
        containers_started=False,
        succeeded=True,
    )


def refuse_stack_start(requested: str) -> None:
    """A request to start the stack is not applied."""
    folded = requested.casefold()
    if any(token in folded for token in ("compose up", "publish", "purchase", "checkout")):
        raise BootstrapRefusal("start")


def _scripts(repo: Path) -> None:
    for relative in _SCRIPTS:
        path = repo / relative
        if not path.is_file():
            raise BootstrapRefusal("script")
        text = path.read_text(encoding="utf-8")
        if any(part not in text for part in _REQUIRED):
            raise BootstrapRefusal("script")
        folded = text.casefold()
        if any(part in folded for part in _FORBIDDEN):
            raise BootstrapRefusal("effect")


def _compose(repo: Path) -> tuple[str, ...]:
    path = repo / "compose.yaml"
    if not path.is_file():
        raise BootstrapRefusal("compose")
    loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise BootstrapRefusal("compose")
    services = loaded.get("services")
    if not isinstance(services, dict) or tuple(services) != _SERVICES:
        raise BootstrapRefusal("compose")
    for name in _HEALTH:
        service = services[name]
        if not isinstance(service, dict) or "healthcheck" not in service:
            raise BootstrapRefusal("compose")
    for name in _HELD:
        service = services[name]
        if not isinstance(service, dict) or service.get("restart") != "no":
            raise BootstrapRefusal("compose")
    return _SERVICES


def _default_runner(args: Sequence[str], cwd: Path) -> int:
    try:
        completed = subprocess.run(
            list(args),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
    except (subprocess.CalledProcessError, OSError) as error:
        raise BootstrapRefusal("command") from error
    return completed.returncode
