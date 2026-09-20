"""Logical agent runtime: definitions, registry, runner, tool permissions, and commissioning gates.

L1: AgentRunner orchestration, prompt loading, provider calls, persistence
L2: ToolRegistry, per-agent tool allowlists, roster registration
"""

from money_machine.agents.base import (
    EXECUTABLE_COMMISSIONING_STATES,
    AgentContext,
    AgentDefinition,
    AgentNotCommissionedError,
    AgentNotImplementedError,
    AgentRegistryError,
    AgentRuntimeError,
    BaseAgent,
    assert_agent_may_execute,
    assert_production_executable,
    parse_system_prompt_reference,
)
from money_machine.agents.registry import AgentRegistry
from money_machine.agents.runtime import AgentRunner, AgentRunReceipt, input_hash
from money_machine.agents.tool_registry import (
    ToolDefinition,
    ToolNotFoundError,
    ToolPermissionError,
    ToolRegistry,
)

__all__ = [
    "EXECUTABLE_COMMISSIONING_STATES",
    "AgentContext",
    "AgentDefinition",
    "AgentNotCommissionedError",
    "AgentNotImplementedError",
    "AgentRegistry",
    "AgentRegistryError",
    "AgentRunReceipt",
    "AgentRunner",
    "AgentRuntimeError",
    "BaseAgent",
    "ToolDefinition",
    "ToolNotFoundError",
    "ToolPermissionError",
    "ToolRegistry",
    "assert_agent_may_execute",
    "assert_production_executable",
    "input_hash",
    "parse_system_prompt_reference",
]
