"""Shared fail-closed foundation process behavior."""

import logging

EXIT_UNAVAILABLE = 78


def unavailable(service: str) -> int:
    """Return a non-success status for a process not implemented in Session 00."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.error(
        "%s is registered but unavailable in the Session 00 foundation; no jobs were processed",
        service,
    )
    return EXIT_UNAVAILABLE
