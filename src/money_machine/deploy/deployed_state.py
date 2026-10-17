"""Read the deployed checkpoint and refuse a live smoke.

The check reads the continuity files. It does not start a service, open a
socket, or edit ``worker.py`` or ``scheduler.py``. Exit 78 stays held.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from money_machine.deploy.checkpoint import inspect_deployment_checkpoint
from money_machine.deploy.controls import confirm_exit_78_held


class DeployedStateRefusal(ValueError):
    """A live smoke, a docker socket, or a service start was requested."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DeployedState:
    """The checkpoint reading. A smoke did not run and no service started."""

    revision: int
    updated_at: str
    head_sha: str
    true_keys: tuple[str, ...]
    smoke_ran: bool
    services_started: bool
    exit_78_held: bool


def check_deployed_state(
    root: Path | None = None,
    *,
    expected_revision: int,
    expected_updated_at: str,
    expected_true_keys: frozenset[str],
    closure_head: str,
    live_smoke: bool = False,
    docker_socket: bool = False,
    start_services: bool = False,
) -> DeployedState:
    """Read the checkpoint. A live smoke, a socket, or a service start is refused."""
    if live_smoke:
        raise DeployedStateRefusal("live_smoke")
    if docker_socket:
        raise DeployedStateRefusal("docker_socket")
    if start_services:
        raise DeployedStateRefusal("service_start")
    held = confirm_exit_78_held(root)
    if held.running is not False or held.worker_held is not True or held.scheduler_held is not True:
        raise DeployedStateRefusal("exit_78")
    checkpoint = inspect_deployment_checkpoint(
        root,
        expected_revision=expected_revision,
        expected_updated_at=expected_updated_at,
        expected_true_keys=expected_true_keys,
        closure_head=closure_head,
    )
    return DeployedState(
        revision=checkpoint.revision,
        updated_at=checkpoint.updated_at,
        head_sha=checkpoint.head_sha,
        true_keys=checkpoint.true_keys,
        smoke_ran=False,
        services_started=False,
        exit_78_held=True,
    )
