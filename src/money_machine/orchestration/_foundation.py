"""Shared fail-closed foundation process behavior."""

import logging

EXIT_UNAVAILABLE = 78
LOGGER = logging.getLogger(__name__)


def unavailable(service: str) -> int:
    """Return a non-success status for a process not implemented in Session 00."""
    LOGGER.error(
        "%s is registered but unavailable in the Session 00 foundation; no jobs were processed",
        service,
    )
    return EXIT_UNAVAILABLE
