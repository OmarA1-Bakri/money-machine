"""Scheduler process placeholder that fails closed until scheduling exists."""

from money_machine.orchestration._foundation import unavailable


def main() -> int:
    """Refuse to claim scheduler capability before it is implemented."""
    return unavailable("scheduler")


if __name__ == "__main__":
    raise SystemExit(main())
