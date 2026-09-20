"""Unit tests for ToolRegistry allowlist enforcement."""

from __future__ import annotations

import pytest

from money_machine.agents.tool_registry import (
    ToolDefinition,
    ToolNotFoundError,
    ToolPermissionError,
    ToolRegistry,
)
from money_machine.domain.enums import SideEffectClass


def test_canonical_registry_resolves_every_configured_tool() -> None:
    from pathlib import Path

    from money_machine.agents.registry import AgentRegistry
    from money_machine.config.loader import load_yaml_model
    from money_machine.config.settings import AgentsConfig

    config = load_yaml_model(Path("config/agents.yaml"), AgentsConfig)
    registry = AgentRegistry.from_config(config)
    tools = ToolRegistry.canonical()
    registry.validate_tool_allowlists(tools.known_tool_ids())


def test_allowed_tool_invocation_succeeds() -> None:
    registry = ToolRegistry.canonical()
    result = registry.invoke(
        "job.create",
        allowed_tools=frozenset({"job.create", "workflow.inspect"}),
        agent_id="A01",
        job_type="DedupeJob",
    )
    assert result["simulated"] is True
    assert result["side_effect_class"] == SideEffectClass.NONE.value


def test_disallowed_tool_raises_permission_error() -> None:
    registry = ToolRegistry.canonical()
    with pytest.raises(ToolPermissionError, match="not allowed to invoke tool"):
        registry.invoke(
            "etsy.read_listing",
            allowed_tools=frozenset({"job.create"}),
            agent_id="A01",
        )


def test_unknown_tool_raises_not_found() -> None:
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError, match="Unknown tool"):
        registry.get("nonexistent.tool")


def test_custom_tool_registration() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition("custom.read", SideEffectClass.EXTERNAL_READ, "custom"),
        lambda **_kwargs: {"ok": True},  # type: ignore[no-untyped-def]
    )
    result = registry.invoke(
        "custom.read",
        allowed_tools=frozenset({"custom.read"}),
        agent_id="A99",
    )
    assert result["ok"] is True


def test_a01_cannot_call_etsy_tools() -> None:
    registry = ToolRegistry.canonical()
    a01_tools = frozenset(
        {
            "job.create",
            "workflow.inspect",
            "job.retry",
            "configuration.read",
            "database.read",
            "database.write_orchestration",
        }
    )
    registry.invoke("job.create", allowed_tools=a01_tools, agent_id="A01")
    with pytest.raises(ToolPermissionError):
        registry.invoke("etsy.read_listing", allowed_tools=a01_tools, agent_id="A01")


def test_a02_can_check_providers_but_not_publish() -> None:
    registry = ToolRegistry.canonical()
    a02_tools = frozenset(
        {
            "provider.check_openai",
            "provider.check_notion",
            "provider.check_etsy",
            "database.read",
            "configuration.read",
            "incident.create",
        }
    )
    registry.invoke("provider.check_etsy", allowed_tools=a02_tools, agent_id="A02")
    with pytest.raises(ToolPermissionError):
        registry.invoke("etsy.publish_listing", allowed_tools=a02_tools, agent_id="A02")
