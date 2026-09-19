"""Worker process.

Not commissioned. It proves database connectivity, logs the result, and exits 78 without
claiming, leasing or transitioning any job. Exit 78 stub; job processing commissioned in Session 04.
"""

import logging

from money_machine.orchestration._foundation import uncommissioned_process


def main() -> int:
    """Refuse to claim worker capability before it is implemented."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return uncommissioned_process("worker")


if __name__ == "__main__":
    raise SystemExit(main())
