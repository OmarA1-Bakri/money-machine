"""Scheduler process.

Not commissioned. It proves database connectivity, logs the result, and exits 78 without
firing any trigger or creating any job.
"""

import logging

from money_machine.orchestration._foundation import uncommissioned_process


def main() -> int:
    """Refuse to claim scheduler capability before it is implemented."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return uncommissioned_process("scheduler")


if __name__ == "__main__":
    raise SystemExit(main())
