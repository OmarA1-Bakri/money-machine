"""Unit tests for agent roster registration and commissioning fail-closed behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from money_machine.agents import (
    AgentNotCommissionedError,
    AgentNotImplementedError,
    AgentRegistry,
    AgentRunner,
    ToolRegistry,
    assert_agent_may_execute,
)
from money_machine.config.loader import load_yaml_model
from money_machine.config.settings import AgentCommissioningState, AgentsConfig
from money_machine.domain.enums import JobStatus, RetryClass, SideEffectClass
from money_machine.domain.models.common import SuccessContract
from money_machine.domain.models.jobs import JobEnvelope

CONFIG_PATH = Path("config/agents.yaml")


def _job_for(agent_id: str, job_type: str = "BootstrapRecordsJob") -> JobEnvelope:
    return JobEnvelope(
        job_id=uuid4(),
        workflow_id=uuid4(),
        object_id=uuid4(),
        job_type=job_type,
        object_type="workflow",
        owner_agent_id=agent_id,
        status=JobStatus.READY,
        input={"scope": "test"},
        scheduled_at=datetime(2026, 9, 20, 10, 0, tzinfo=UTC),
        attempt=1,
        max_attempts=3,
        idempotency_key=f"test:{agent_id}:{job_type}",
        side_effect_class=SideEffectClass.NONE,
        retry_class=RetryClass.SAFE,
        success_contract=SuccessContract(output_model="AgentResult"),
    )


@pytest.fixture
def agents_config() -> AgentsConfig:
    return load_yaml_model(CONFIG_PATH, AgentsConfig)


@pytest.fixture
def registry(agents_config: AgentsConfig) -> AgentRegistry:
    return AgentRegistry.from_config(agents_config)


def test_registry_loads_all_sixteen_agents(registry: AgentRegistry) -> None:
    definitions = registry.all_definitions()
    assert len(definitions) == 16
    assert {definition.agent_id for definition in definitions} == {
        f"A{number:02d}" for number in range(1, 17)
    }


def test_a01_and_a02_are_tested_others_designed(registry: AgentRegistry) -> None:
    a01 = registry.get_definition("A01")
    a02 = registry.get_definition("A02")
    assert a01.commissioning_state is AgentCommissioningState.TESTED
    assert a02.commissioning_state is AgentCommissioningState.TESTED

    for agent_id in (f"A{number:02d}" for number in range(3, 17)):
        definition = registry.get_definition(agent_id)
        assert definition.commissioning_state is AgentCommissioningState.DESIGNED


def test_uncommissioned_agent_refuses_production_execution(registry: AgentRegistry) -> None:
    designed = registry.get_definition("A03")
    with pytest.raises(AgentNotCommissionedError, match="A03"):
        assert_agent_may_execute(designed, production=True)


def test_designed_agent_allows_simulation_gate(registry: AgentRegistry) -> None:
    designed = registry.get_definition("A07")
    assert_agent_may_execute(designed, production=False)


@pytest.mark.asyncio
async def test_a01_executes_with_allowed_tools(registry: AgentRegistry) -> None:
    runner = AgentRunner(registry, ToolRegistry.canonical())
    result = await runner.execute(_job_for("A01"), production=False)
    assert result.agent_id == "A01"
    assert result.status.value == "SUCCESS"
    assert "initial_workflows_created" in result.output


@pytest.mark.asyncio
async def test_a02_executes_provisioning_check(registry: AgentRegistry) -> None:
    runner = AgentRunner(registry, ToolRegistry.canonical())
    result = await runner.execute(
        _job_for("A02", job_type="ProvisioningCheckJob"),
        production=False,
    )
    assert result.agent_id == "A02"
    assert result.output["readiness"] == "READY"


@pytest.mark.asyncio
async def test_unimplemented_agent_raises_on_production(registry: AgentRegistry) -> None:
    runner = AgentRunner(registry, ToolRegistry.canonical())
    with pytest.raises(AgentNotCommissionedError):
        await runner.execute(_job_for("A03", job_type="ResearchCollectionJob"), production=True)


@pytest.mark.asyncio
async def test_unimplemented_agent_has_no_implementation(registry: AgentRegistry) -> None:
    with pytest.raises(AgentNotImplementedError):
        registry.get_implementation("A05")


@pytest.mark.parametrize(
    "agent_id",
    [f"A{number:02d}" for number in range(3, 17)],
)
def test_designed_agents_resolve_tools_from_registry(
    registry: AgentRegistry,
    agent_id: str,
) -> None:
    tools = ToolRegistry.canonical()
    definition = registry.get_definition(agent_id)
    for tool_id in definition.allowed_tools:
        tools.resolve(tool_id)


@pytest.mark.parametrize("agent_id", ["A01", "A02"])
def test_tested_agents_have_prompt_files(agent_id: str) -> None:
    prompt_path = Path("prompts/agents") / agent_id / "v1.md"
    assert prompt_path.is_file(), f"Missing prompt for {agent_id}"
