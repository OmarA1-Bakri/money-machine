"""Canonical domain enums, events, and errors."""

from money_machine.domain.enums import (
    AgentRunStatus,
    AutonomyMode,
    BranchOutcome,
    CapabilityChannel,
    DecisionType,
    IncidentType,
    JobStatus,
    ProductLifecycleState,
    RetryClass,
    SideEffectClass,
)
from money_machine.domain.errors import InvalidTransitionError
from money_machine.domain.events import EventName

__all__ = [
    "AgentRunStatus",
    "AutonomyMode",
    "BranchOutcome",
    "CapabilityChannel",
    "DecisionType",
    "EventName",
    "IncidentType",
    "InvalidTransitionError",
    "JobStatus",
    "ProductLifecycleState",
    "RetryClass",
    "SideEffectClass",
]
