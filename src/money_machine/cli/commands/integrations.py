"""Integration readiness command entry point.

Reports configured or not configured from settings presence. Never reads a credential
value, performs a provider call, or opens a browser profile.
"""

from money_machine.cli.main import command_integrations_status

__all__ = ["command_integrations_status"]
