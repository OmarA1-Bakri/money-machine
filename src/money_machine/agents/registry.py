"""Agent registry loading the configured A01-A16 roster.

Contract: Session 04 L1 — AgentRunner core lane (W4).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Self

from money_machine.agents.base import AgentDefinition, AgentRegistryError
from money_machine.config.loader import load_yaml_model
from money_machine.config.settings import AgentsConfig


class AgentRegistry:
    """In-memory registry of runtime agent definitions indexed by agent id."""

    def __init__(self, agents: Mapping[str, AgentDefinition]) -> None:
        if len(agents) != 16:
            msg = f"agent registry must contain exactly sixteen agents, got {len(agents)}"
            raise AgentRegistryError(msg)
        self._agents = dict(agents)

    @classmethod
    def from_config(cls, config: AgentsConfig) -> Self:
        agents = {
            definition.agent_id: AgentDefinition.from_config(definition)
            for definition in config.agents
        }
        return cls(agents)

    @classmethod
    def from_yaml(cls, repository_root: Path) -> Self:
        config = load_yaml_model(repository_root / "config" / "agents.yaml", AgentsConfig)
        return cls.from_config(config)

    def get(self, agent_id: str) -> AgentDefinition:
        """Return one agent definition or fail closed."""
        try:
            return self._agents[agent_id]
        except KeyError as error:
            msg = f"unknown agent id: {agent_id}"
            raise AgentRegistryError(msg) from error

    def roster(self) -> tuple[AgentDefinition, ...]:
        """Return the full roster in agent-id order."""
        return tuple(self._agents[agent_id] for agent_id in sorted(self._agents))

    def get_definition(self, agent_id: str) -> AgentDefinition:
        """L2 alias: Return one agent definition or fail closed."""
        return self.get(agent_id)

    def all_definitions(self) -> tuple[AgentDefinition, ...]:
        """L2: Return all agent definitions in agent-id order."""
        return self.roster()

    def get_implementation(self, agent_id: str):  # type: ignore[no-untyped-def]
        """L2: Return agent implementation or raise AgentNotImplementedError."""
        from money_machine.agents.base import AgentNotImplementedError

        # Map agent IDs to their implementations
        implementations: dict[str, str] = {
            "A01": "money_machine.agents.implementations.shop_orchestrator.ShopOrchestratorAgent",
            "A02": "money_machine.agents.implementations.account_integration.AccountIntegrationAgent",
        }

        if agent_id not in implementations:
            raise AgentNotImplementedError(f"Agent {agent_id} has no implementation")

        module_path, class_name = implementations[agent_id].rsplit(".", 1)
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, class_name)()

    def validate_tool_allowlists(self, known_tool_ids: frozenset[str]) -> None:
        """L2: Validate that all agent allowlists reference only known tools."""
        for definition in self.roster():
            unknown = set(definition.allowed_tools) - known_tool_ids
            if unknown:
                msg = f"agent {definition.agent_id} references unknown tools: {sorted(unknown)}"
                raise AgentRegistryError(msg)
