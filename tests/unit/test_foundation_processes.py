from types import ModuleType
from typing import NoReturn

import pytest

from money_machine.orchestration import _foundation, scheduler, worker
from money_machine.orchestration._foundation import EXIT_UNAVAILABLE


def test_unimplemented_processes_fail_closed() -> None:
    assert worker.main() == EXIT_UNAVAILABLE
    assert scheduler.main() == EXIT_UNAVAILABLE


def test_unavailable_does_not_reconfigure_process_logging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_basic_config(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("library helper must not configure root logging")

    monkeypatch.setattr(_foundation.logging, "basicConfig", reject_basic_config)

    assert _foundation.unavailable("worker") == EXIT_UNAVAILABLE


@pytest.mark.parametrize(
    ("entrypoint", "service"),
    [(worker, "worker"), (scheduler, "scheduler")],
)
def test_entrypoint_configures_logging_before_reporting_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    entrypoint: ModuleType,
    service: str,
) -> None:
    events: list[object] = []

    def configure_logging(**options: object) -> None:
        events.append(("configured", options))

    def report_unavailable(reported_service: str) -> int:
        events.append(("unavailable", reported_service))
        return EXIT_UNAVAILABLE

    monkeypatch.setattr(entrypoint.logging, "basicConfig", configure_logging)
    monkeypatch.setattr(entrypoint, "unavailable", report_unavailable)

    assert entrypoint.main() == EXIT_UNAVAILABLE
    assert events == [
        (
            "configured",
            {"level": entrypoint.logging.INFO, "format": "%(levelname)s %(message)s"},
        ),
        ("unavailable", service),
    ]
