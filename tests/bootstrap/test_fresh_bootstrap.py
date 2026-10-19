"""A fresh bootstrap checks the frozen locks and does not start containers."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from money_machine.deploy.bootstrap import (
    BootstrapRefusal,
    record_fresh_bootstrap,
    refuse_stack_start,
)

ROOT = Path(__file__).parents[2]
_SCRIPT = (
    "uv sync --frozen\n"
    "pnpm install --frozen-lockfile\n"
    "docker compose config --quiet\n"
)
_COMPOSE = """
services:
  postgres:
    healthcheck: {test: ["CMD", "true"]}
  api:
    healthcheck: {test: ["CMD", "true"]}
  web:
    healthcheck: {test: ["CMD", "true"]}
  worker:
    restart: "no"
  scheduler:
    restart: "no"
"""


def test_the_fresh_bootstrap_succeeds() -> None:
    recorded = record_fresh_bootstrap(ROOT)

    assert recorded.succeeded is True
    assert recorded.python_lock_checked is True
    assert recorded.node_lock_checked is True
    assert recorded.compose_rendered is True
    assert recorded.services == ("postgres", "api", "web", "worker", "scheduler")
    assert recorded.containers_started is False


def test_a_stack_start_is_refused() -> None:
    with pytest.raises(BootstrapRefusal, match="start"):
        refuse_stack_start("docker compose up")


def test_a_lock_check_is_not_a_stack_start() -> None:
    refuse_stack_start("uv lock --check")


def test_a_script_without_the_frozen_install_is_refused(tmp_path: Path) -> None:
    _tree(tmp_path, script="echo ready\n")

    with pytest.raises(BootstrapRefusal, match="script"):
        record_fresh_bootstrap(tmp_path, runner=_ok)


def test_a_python_lock_failure_is_refused(tmp_path: Path) -> None:
    _tree(tmp_path)

    with pytest.raises(BootstrapRefusal, match="python"):
        record_fresh_bootstrap(tmp_path, runner=_fail_python)


def test_a_running_worker_is_refused(tmp_path: Path) -> None:
    _tree(tmp_path, compose=_COMPOSE.replace('restart: "no"', "restart: always", 1))

    with pytest.raises(BootstrapRefusal, match="compose"):
        record_fresh_bootstrap(tmp_path, runner=_ok)


def _ok(args: Sequence[str], cwd: Path) -> int:
    del args, cwd
    return 0


def _fail_python(args: Sequence[str], cwd: Path) -> int:
    del cwd
    if args[0] == "uv":
        return 1
    return 0


def _tree(path: Path, *, script: str = _SCRIPT, compose: str = _COMPOSE) -> None:
    scripts = path / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "bootstrap.sh").write_text(script, encoding="utf-8")
    (scripts / "bootstrap.ps1").write_text(script, encoding="utf-8")
    (path / "compose.yaml").write_text(compose, encoding="utf-8")
