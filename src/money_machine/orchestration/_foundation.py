"""Shared fail-closed foundation process behavior.

The worker and scheduler are registered but not commissioned. Session 02 gave them a
read-only database connectivity check so a container proves it can reach PostgreSQL, and
then they still exit 78. Claiming, leasing or transitioning a job is commissioned in
Session 03 (corrective addendum 1).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

EXIT_UNAVAILABLE: Final = 78
LOGGER = logging.getLogger(__name__)


def unavailable(service: str) -> int:
    """Return a non-success status for a process that is not commissioned."""
    LOGGER.error(
        "%s is registered but unavailable in the Session 00 foundation; no jobs were processed",
        service,
    )
    return EXIT_UNAVAILABLE


def report_database_connectivity(service: str) -> bool | None:
    """Log whether the database is reachable, without claiming any work.

    Returns True or False when a check ran, and None when settings are unavailable. This
    is a read: it executes ``SELECT 1`` and nothing else. It never reads the job table.
    """
    from money_machine.config.runtime import RuntimeSettingsError, load_runtime_settings
    from money_machine.persistence.database import check_connectivity, create_engine

    try:
        settings = load_runtime_settings()
    except RuntimeSettingsError as error:
        LOGGER.error("%s cannot resolve settings: %s", service, error)
        return None

    async def probe() -> bool:
        engine = create_engine(settings.database)
        try:
            return await check_connectivity(engine)
        finally:
            await engine.dispose()

    reachable = asyncio.run(probe())
    LOGGER.info(
        "%s database check: url=%s reachable=%s",
        service,
        settings.database.safe_url,
        reachable,
    )
    return reachable


def uncommissioned_process(service: str) -> int:
    """Run the full uncommissioned startup path: check connectivity, then exit 78."""
    report_database_connectivity(service)
    return unavailable(service)
