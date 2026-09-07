"""Scheduler command surface.

The scheduler is not commissioned: trigger firing is a later session. Invoking the process
exits 78 after a read-only database connectivity check.
"""

from money_machine.orchestration.scheduler import main

__all__ = ["main"]
