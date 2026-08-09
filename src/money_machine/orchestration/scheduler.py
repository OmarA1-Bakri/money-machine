"""Scheduler process placeholder that fails closed until scheduling exists."""

import logging

from money_machine.orchestration._foundation import unavailable


def main() -> int:
    """Refuse to claim scheduler capability before it is implemented."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return unavailable("scheduler")


if __name__ == "__main__":
    raise SystemExit(main())
