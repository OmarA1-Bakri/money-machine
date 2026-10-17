"""Refuse every production service control.

Exit 78 stays held. A status word is not a running service. No docker socket
is opened. ``worker.py`` and ``scheduler.py`` are read, not edited.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SERVICE_CONTROLS = (
    "start",
    "stop",
    "restart",
    "status",
    "logs",
    "scale",
    "scheduler_singleton",
    "migrate",
    "safe_update",
)
_STATUS_WORDS = frozenset({"running", "healthy", "up", "started", "ok", "online", "active"})
_SINGLETON_ACTIONS = frozenset({"start", "restart", "scale"})
_WORKER = Path("src/money_machine/orchestration/worker.py")
_SCHEDULER = Path("src/money_machine/orchestration/scheduler.py")


class ServiceControlRefusal(ValueError):
    """The control did not start, stop, or report a running service."""

    def __init__(self, code: str) -> None:
        self.code = code
        self.running = False
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class Exit78Hold:
    """The worker and scheduler files still name Exit 78. Nothing is running."""

    worker_held: bool
    scheduler_held: bool
    running: bool


def confirm_exit_78_held(root: Path | None = None) -> Exit78Hold:
    """Read the worker and scheduler sources. A missing Exit 78 line is a refusal."""
    repo = Path(__file__).resolve().parents[3] if root is None else root
    worker = (repo / _WORKER).read_text(encoding="utf-8")
    scheduler = (repo / _SCHEDULER).read_text(encoding="utf-8")
    if "Exit 78 held" not in worker or "Exit 78" not in scheduler:
        raise ServiceControlRefusal("exit_78")
    return Exit78Hold(worker_held=True, scheduler_held=True, running=False)


def control_service(
    action: str,
    *,
    service: str = "worker",
    status_word: str | None = None,
    scheduler_count: int = 0,
    replicas: int = 1,
    docker_socket: bool = False,
) -> None:
    """Refuse one named control. The call does not open a socket or a database.

    ``status_word`` never means the service is running. A second scheduler
    raises ``scheduler_singleton``. Every other named control raises ``closed``.
    """
    if docker_socket:
        raise ServiceControlRefusal("docker_socket")
    folded = action.strip().casefold().replace("-", "_").replace(" ", "_")
    if folded not in SERVICE_CONTROLS:
        raise ServiceControlRefusal("unknown")
    if status_word is not None and status_word.strip().casefold() in _STATUS_WORDS:
        raise ServiceControlRefusal("status_word")
    if folded == "scheduler_singleton":
        raise ServiceControlRefusal("scheduler_singleton")
    second_scheduler = scheduler_count >= 1 or replicas != 1
    if service == "scheduler" and folded in _SINGLETON_ACTIONS and second_scheduler:
        raise ServiceControlRefusal("scheduler_singleton")
    raise ServiceControlRefusal("closed")
