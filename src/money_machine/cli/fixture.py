"""The explicit fixture entrypoint; production commissioning remains unchanged."""

from money_machine.application.fixture_run import run_fixture

if __name__ == "__main__":
    raise SystemExit(run_fixture())
