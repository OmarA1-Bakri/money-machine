"""Record that the production compose spec succeeds without building it.

``compose.prod.yaml`` and the six runbooks are the package. This module
reads that package. It does not call Docker, build an image, or start a
container.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from money_machine.deploy.packaging import (
    REQUIRED_SERVICES,
    PackagingRefusal,
    define_production_package,
)


class ProductionComposeRefusal(ValueError):
    """The production package or an image build is refused."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProductionCompose:
    """The rendered production services. Nothing was built or started."""

    succeeded: bool
    services: tuple[str, ...]
    worker_restart: str
    scheduler_restart: str
    image_built: bool
    containers_started: bool


def record_production_compose(root: Path | None = None) -> ProductionCompose:
    """Read the production package. Docker is not called."""
    try:
        package = define_production_package(root)
    except PackagingRefusal as error:
        raise ProductionComposeRefusal(error.code) from error
    if package.docker_compose_config_ran or package.services != REQUIRED_SERVICES:
        raise ProductionComposeRefusal("package")
    if package.worker_restart != "no" or package.scheduler_restart != "no":
        raise ProductionComposeRefusal("restart")
    return ProductionCompose(
        succeeded=True,
        services=package.services,
        worker_restart=package.worker_restart,
        scheduler_restart=package.scheduler_restart,
        image_built=False,
        containers_started=False,
    )


def refuse_image_build(requested: str) -> None:
    """A request to build or start the production stack is not applied."""
    folded = requested.casefold()
    blocked = ("compose build", "compose up", "docker build", "publish")
    if any(token in folded for token in blocked):
        raise ProductionComposeRefusal("build")
