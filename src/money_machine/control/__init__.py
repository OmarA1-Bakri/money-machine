"""Fail-closed control-state transitions."""

from money_machine.control.state import (
    ControlStateError,
    apply_completion_transition,
    validate_completion_transition,
)

__all__ = [
    "ControlStateError",
    "apply_completion_transition",
    "validate_completion_transition",
]
