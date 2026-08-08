from money_machine.orchestration._foundation import EXIT_UNAVAILABLE
from money_machine.orchestration.scheduler import main as scheduler_main
from money_machine.orchestration.worker import main as worker_main


def test_unimplemented_processes_fail_closed() -> None:
    assert worker_main() == EXIT_UNAVAILABLE
    assert scheduler_main() == EXIT_UNAVAILABLE
