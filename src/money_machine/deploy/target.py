"""Select the host the application deploys to.

The default is the existing local and single-server topology. A new paid host
is refused unless an explicit authority record is passed, and even then no
host is created.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DeploymentTargetName = Literal["local-wsl", "new-paid"]
_KNOWN_TARGETS = frozenset({"local-wsl", "new-paid"})
_DEPLOYMENT_DOC = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "DEPLOYMENT.md"
_LOCAL_RATIONALE = (
    "local and single-server topology. "
    "Exit 78 is uncommissioned. "
    "No unapproved spend. "
    "No host is created."
)


class DeploymentTargetRefusal(ValueError):
    """The requested target is empty, unknown, or would spend without authority."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PaidHostAuthority:
    """An explicit approval to name a paid host. Naming it does not create it."""

    record_id: str
    approved_paid_host: bool


@dataclass(frozen=True, slots=True)
class DeploymentTarget:
    """The selected target. ``host_created`` stays false."""

    target: DeploymentTargetName
    rationale: str
    host_created: bool


def select_deployment_target(
    requested: str = "local-wsl",
    *,
    owned_vps: str | None = None,
    authority: PaidHostAuthority | None = None,
) -> DeploymentTarget:
    """Return ``local-wsl`` when no owned VPS is supplied.

    ``new-paid`` raises ``unapproved_spend`` unless ``authority`` approves it.
    An approval still does not create a host.
    """
    _require_deployment_document()
    if requested == "":
        raise DeploymentTargetRefusal("empty_target")
    if requested not in _KNOWN_TARGETS:
        raise DeploymentTargetRefusal("unknown_target")
    if requested == "new-paid":
        return _named_paid_host(authority)
    if owned_vps is not None and owned_vps.strip() == "":
        raise DeploymentTargetRefusal("empty_target")
    return DeploymentTarget(
        target="local-wsl",
        rationale=_LOCAL_RATIONALE,
        host_created=False,
    )


def _named_paid_host(authority: PaidHostAuthority | None) -> DeploymentTarget:
    if (
        authority is None
        or authority.approved_paid_host is not True
        or authority.record_id.strip() == ""
    ):
        raise DeploymentTargetRefusal("unapproved_spend")
    return DeploymentTarget(
        target="new-paid",
        rationale="A paid host was named by an authority record. No host is created.",
        host_created=False,
    )


def _require_deployment_document() -> None:
    text = _DEPLOYMENT_DOC.read_text(encoding="utf-8")
    if "local and single-server" not in text:
        raise DeploymentTargetRefusal("topology")
    if "Exit 78 is not deployment success" not in text:
        raise DeploymentTargetRefusal("exit_78")
