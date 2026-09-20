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
    """Scheduler exits 78 when database check cannot run. Worker gates also fail without config."""

    def no_check(service: str) -> bool | None:
        del service
        return None

    # Mock commissioning gates to fail (simulates missing config)
    def gates_fail() -> bool:
        return False

    monkeypatch.setattr(_foundation, "report_database_connectivity", no_check)
    monkeypatch.setattr(worker, "_check_commissioning_gates", gates_fail)

    # Both fail when commissioning gates fail (no valid config)
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

    def gates_fail() -> bool:
        return False

    def unavailable_stub(service: str) -> int:
        assert service == "worker"
        return EXIT_UNAVAILABLE

    monkeypatch.setattr(worker.logging, "basicConfig", record_config)
    monkeypatch.setattr(worker, "_check_commissioning_gates", gates_fail)
    monkeypatch.setattr(worker, "unavailable", unavailable_stub)

    assert worker.main() == EXIT_UNAVAILABLE
    assert calls == [
        {"level": logging.INFO, "format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}
    ]


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
    # Scheduler uses different logging format
    assert len(calls) == 1
    assert calls[0]["level"] == logging.INFO


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
    [
        "money_machine.orchestration.scheduler",
        # Worker excluded: lifts Exit 78 when gates pass, runs indefinitely
    ],
)
def test_real_entry_points_exit_78_after_a_connectivity_check(module: str) -> None:
    """Scheduler subprocess proves fail-closed exit (Wave 9: worker path only)."""
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
    # Scheduler remains fail-closed with honest messaging
    assert "Scheduler cycle not implemented" in result.stderr
    assert "worker path only" in result.stderr
    assert "no jobs processed" in result.stderr
"""Test that commissioning gates pass for real A01/A02 agents."""
import pytest
from pathlib import Path

def test_commissioning_gates_pass_for_tested_agents():
    """Prove gates return True for A01/A02 with real roster/prompts."""
    from money_machine.orchestration.worker import _check_commissioning_gates
    
    # Gates should pass when A01/A02 are TESTED with valid prompts
    result = _check_commissioning_gates()
    
    # Must return True (not False which would cause Exit 78)
    assert result is True, "Commissioning gates failed for TESTED agents A01/A02"


def test_worker_enters_claim_loop_when_gates_pass(monkeypatch: pytest.MonkeyPatch):
    """Prove that when gates pass, worker enters claim loop (not Exit 78)."""
    from money_machine.orchestration import worker
    from money_machine.orchestration._foundation import EXIT_UNAVAILABLE
    
    # Track whether worker loop was called
    loop_called = []
    
    async def mock_loop():
        loop_called.append(True)
        # Exit immediately to prevent infinite loop
        return
    
    # Gates pass (use real check)
    assert worker._check_commissioning_gates() is True
    
    # Mock the worker loop to prevent infinite execution
    monkeypatch.setattr(worker, "_worker_loop", mock_loop)
    
    # Worker main should NOT return EXIT_UNAVAILABLE when gates pass
    # It should call the loop and return 0
    exit_code = worker.main()
    
    # Verify loop was called
    assert loop_called, "Worker loop was not called despite gates passing"
    
    # Verify exit code is success (not EXIT_UNAVAILABLE)
    assert exit_code == 0, f"Worker returned {exit_code} instead of 0 when gates pass"
    assert exit_code != EXIT_UNAVAILABLE, "Worker returned Exit 78 despite gates passing"
