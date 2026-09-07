import logging
import os
import subprocess
import sys

import pytest

from money_machine.orchestration import _foundation, scheduler, worker
from money_machine.orchestration._foundation import EXIT_UNAVAILABLE
from money_machine.orchestration.scheduler import main as scheduler_main
from money_machine.orchestration.worker import main as worker_main


def test_unimplemented_processes_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both entry points exit 78 even when the database check cannot run."""

    def no_check(service: str) -> bool | None:
        del service
        return None

    monkeypatch.setattr(_foundation, "report_database_connectivity", no_check)

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

    def uncommissioned_stub(service: str) -> int:
        assert service == "worker"
        return EXIT_UNAVAILABLE

    monkeypatch.setattr(worker.logging, "basicConfig", record_config)
    monkeypatch.setattr(worker, "uncommissioned_process", uncommissioned_stub)

    assert worker.main() == EXIT_UNAVAILABLE
    assert calls == [{"level": logging.INFO, "format": "%(levelname)s %(message)s"}]


def test_scheduler_entrypoint_configures_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def record_config(**kwargs: object) -> None:
        calls.append(kwargs)

    def uncommissioned_stub(service: str) -> int:
        assert service == "scheduler"
        return EXIT_UNAVAILABLE

    monkeypatch.setattr(scheduler.logging, "basicConfig", record_config)
    monkeypatch.setattr(scheduler, "uncommissioned_process", uncommissioned_stub)

    assert scheduler.main() == EXIT_UNAVAILABLE
    assert calls == [{"level": logging.INFO, "format": "%(levelname)s %(message)s"}]


def test_connectivity_check_is_read_only_and_never_claims_work(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The uncommissioned path may prove connectivity, then must still exit 78."""
    checked: list[str] = []

    def record_check(service: str) -> bool:
        checked.append(service)
        return True

    monkeypatch.setattr(_foundation, "report_database_connectivity", record_check)
    caplog.set_level(logging.ERROR, logger=_foundation.__name__)

    assert _foundation.uncommissioned_process("worker") == EXIT_UNAVAILABLE
    assert checked == ["worker"]
    assert "no jobs were processed" in caplog.records[-1].message


def test_worker_module_exposes_no_claim_surface() -> None:
    """Session 02 must not introduce a job-claiming entry point (addendum 1)."""
    for module in (worker, scheduler, _foundation):
        exported = {name for name in dir(module) if not name.startswith("_")}
        assert not {"claim", "claim_job", "lease", "lease_job", "run_loop", "poll"} & exported


@pytest.mark.parametrize(
    "module",
    ["money_machine.orchestration.worker", "money_machine.orchestration.scheduler"],
)
def test_real_entry_points_exit_78_after_a_connectivity_check(module: str) -> None:
    """A real subprocess proves the fail-closed exit and reports its database check."""
    result = subprocess.run(
        [sys.executable, "-m", module],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
        env={**os.environ, "APP_ENV": "test"},
    )

    assert result.returncode == EXIT_UNAVAILABLE
    assert result.stdout == ""
    assert "database check" in result.stderr
    assert "no jobs were processed" in result.stderr
