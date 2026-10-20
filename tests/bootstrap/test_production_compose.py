"""The production compose spec succeeds and an image build is refused."""

from __future__ import annotations

from pathlib import Path

import pytest

from money_machine.deploy.packaging import PackagingRefusal, define_production_package
from money_machine.deploy.production_compose import (
    ProductionComposeRefusal,
    record_production_compose,
    refuse_image_build,
)

ROOT = Path(__file__).parents[2]


def test_the_production_compose_succeeds() -> None:
    recorded = record_production_compose(ROOT)

    assert recorded.succeeded is True
    assert recorded.services == ("postgres", "api", "web", "worker", "scheduler")
    assert recorded.worker_restart == "no"
    assert recorded.scheduler_restart == "no"
    assert recorded.image_built is False
    assert recorded.containers_started is False


def test_an_image_build_is_refused() -> None:
    with pytest.raises(ProductionComposeRefusal, match="build"):
        refuse_image_build("docker compose build")


def test_reading_the_spec_is_not_a_build() -> None:
    refuse_image_build("compose.prod.yaml")


def test_a_missing_production_spec_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ProductionComposeRefusal, match="compose"):
        record_production_compose(tmp_path)


def test_a_compose_config_shortcut_is_refused() -> None:
    with pytest.raises(PackagingRefusal, match="compose_config"):
        define_production_package(ROOT, accept_compose_config=True)
