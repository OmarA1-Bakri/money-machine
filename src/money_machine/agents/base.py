"""Agent runtime contracts: definition, context, base agent, and commissioning gates.

Contract: Session 04 L1 — AgentRunner core lane (W4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Self
from uuid import UUID

from money_machine.config.settings import AgentCommissioningState
from money_machine.config.settings import AgentDefinition as ConfigAgentDefinition
from money_machine.domain.models.jobs import AgentResult, JobEnvelope
from money_machine.integrations.llm.interface import LLMProvider

EXECUTABLE_COMMISSIONING_STATES: Final[frozenset[AgentCommissioningState]] = frozenset(
    {
        AgentCommissioningState.TESTED,
        AgentCommissioningState.COMMISSIONED,
    }
)


class AgentRuntimeError(Exception):
    """Base exception for agent runtime failures."""


class AgentNotCommissionedError(AgentRuntimeError):
    """Raised when a production job targets an agent that is not executable."""


class AgentNotImplementedError(AgentRuntimeError):
    """Raised when no implementation exists for a registered agent (L2)."""


class AgentRegistryError(AgentRuntimeError):
    """Raised when the registry cannot resolve an agent or prompt reference."""


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """Runtime view of one configured agent definition."""

    agent_id: str
    name: str
    contract_version: int
    system_prompt_reference: str
    input_contracts: tuple[str, ...]
    output_contracts: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    default_side_effect_class: str
    timeout_seconds: int
    commissioning_state: AgentCommissioningState
    commissioning_evidence: tuple[str, ...]
    database_id: UUID | None = None

    @classmethod
    def from_config(
        cls,
        config: ConfigAgentDefinition,
        *,
        database_id: UUID | None = None,
    ) -> Self:
        return cls(
            agent_id=config.agent_id,
            name=config.name,
            contract_version=config.contract_version,
            system_prompt_reference=config.system_prompt_reference,
            input_contracts=config.input_contracts,
            output_contracts=config.output_contracts,
            allowed_tools=config.allowed_tools,
            default_side_effect_class=config.default_side_effect_class.value,
            timeout_seconds=config.timeout_seconds,
            commissioning_state=config.commissioning_state,
            commissioning_evidence=config.commissioning_evidence,
            database_id=database_id,
        )

    def allows_production_execution(self) -> bool:
        """Return whether this agent may execute a production job."""
        return self.commissioning_state in EXECUTABLE_COMMISSIONING_STATES


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Execution context passed into one agent invocation."""

    job: JobEnvelope
    definition: AgentDefinition
    run_id: UUID
    prompt_text: str
    prompt_reference: str
    prompt_sha256: str
    prompt_version: int
    provider: LLMProvider
    run_at: datetime
    tool_registry: object | None = None  # L2: ToolRegistry for invoke_tool()

    @property
    def agent_run_id(self) -> UUID:
        """Alias for L2 compatibility."""
        return self.run_id

    def invoke_tool(self, tool_id: str, **kwargs: object) -> Any:  # noqa: ANN401
        """L2: Invoke a tool through the registry with allowlist enforcement."""
        if self.tool_registry is None:
            raise AgentRuntimeError("ToolRegistry not available in context")
        # Import here to avoid circular dependency
        from money_machine.agents.tool_registry import ToolRegistry

        if not isinstance(self.tool_registry, ToolRegistry):
            raise AgentRuntimeError("Invalid tool_registry type")
        return self.tool_registry.invoke(
            tool_id,
            allowed_tools=frozenset(self.definition.allowed_tools),
            agent_id=self.definition.agent_id,
            **kwargs,
        )


class BaseAgent(ABC):
    """Abstract agent implementation invoked by ``AgentRunner``."""

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute one job and return a terminal structured result."""


def parse_system_prompt_reference(reference: str) -> tuple[str, str]:
    """Parse ``agent://{agent_id}/system/{version}`` into agent id and version label."""
    if not reference.startswith("agent://"):
        msg = f"unsupported prompt reference scheme: {reference!r}"
        raise AgentRegistryError(msg)
    remainder = reference.removeprefix("agent://")
    parts = remainder.split("/")
    if len(parts) != 3 or parts[1] != "system":
        msg = f"malformed agent prompt reference: {reference!r}"
        raise AgentRegistryError(msg)
    agent_id, version = parts[0], parts[2]
    if not agent_id or not version:
        msg = f"malformed agent prompt reference: {reference!r}"
        raise AgentRegistryError(msg)
    return agent_id, version


def assert_production_executable(definition: AgentDefinition) -> None:
    """Fail closed when an agent is not executable in production."""
    if definition.allows_production_execution():
        return
    msg = (
        f"agent {definition.agent_id} is {definition.commissioning_state.value}; "
        "production execution requires TESTED or COMMISSIONED"
    )
    raise AgentNotCommissionedError(msg)
