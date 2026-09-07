"""Database command entry points.

The commands themselves live in :mod:`money_machine.cli.main`, which owns argument parsing
and the single reporting format. This module re-exports them so the canonical command
module path stays meaningful.
"""

from money_machine.cli.main import command_db_seed, command_db_upgrade

__all__ = ["command_db_seed", "command_db_upgrade"]
