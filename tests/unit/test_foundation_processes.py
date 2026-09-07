import logging
import subprocess
import sys

import pytest

from money_machine.orchestration import _foundation, scheduler, worker
from money_machine.orchestration._foundation import EXIT_UNAVAILABLE
from money_machine.orchestration.scheduler import main as scheduler_main
from money_machine.orchestration.worker import main as worker_main


def test_unimplemented_processes_fail_closed() -> None:
    assert worker_main() == EXIT_UNAVAILABLE
    assert scheduler_main() == EXIT_UNAVAILABLE


def test_shared_unavailable_helper_does_not_configure_root_logging(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def reject_basic_config(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("shared helper configured process-wide logging")

    monkeypatch.setattr(_foundation.logging, "basicConfig", reject_basic_config)
    caplog.set_level(logging.ERROR, logger=_foundation.__name__)

    assert _foundation.unavailable("probe") == EXIT_UNAVAILABLE
    assert [(record.name, record.message) for record in caplog.records] == [
        (
            _foundation.__name__,
            "probe is registered but unavailable in the Session 00 foundation; "
            "no jobs were processed",
        )
    ]


def test_worker_entrypoint_configures_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def record_config(**kwargs: object) -> None:
        calls.append(kwargs)

    def unavailable_stub(service: str) -> int:
        assert service == "worker"
        return EXIT_UNAVAILABLE

    monkeypatch.setattr(worker.logging, "basicConfig", record_config)
    monkeypatch.setattr(worker, "unavailable", unavailable_stub)

    assert worker.main() == EXIT_UNAVAILABLE
    assert calls == [{"level": logging.INFO, "format": "%(levelname)s %(message)s"}]


def test_scheduler_entrypoint_configures_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def record_config(**kwargs: object) -> None:
        calls.append(kwargs)

    def unavailable_stub(service: str) -> int:
        assert service == "scheduler"
        return EXIT_UNAVAILABLE

    monkeypatch.setattr(scheduler.logging, "basicConfig", record_config)
    monkeypatch.setattr(scheduler, "unavailable", unavailable_stub)

    assert scheduler.main() == EXIT_UNAVAILABLE
    assert calls == [{"level": logging.INFO, "format": "%(levelname)s %(message)s"}]


@pytest.mark.parametrize(
    "module", ["money_machine.orchestration.worker", "money_machine.orchestration.scheduler"]
)
def test_real_entry_points_exit_78_without_processing_anything(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", module],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == EXIT_UNAVAILABLE
    assert result.stdout == ""
    assert "no jobs were processed" in result.stderr
