"""Worker command surface.

The worker is not commissioned: job claiming commissioned in Session 04. Invoking the
process exits 78 after a read-only database connectivity check.
"""

from money_machine.orchestration.worker import main

__all__ = ["main"]
