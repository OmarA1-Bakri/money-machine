"""Parametrized roster contract tests for every A01-A16 entry.

S04 W8 (S04-11): config/agents.yaml is the roster source of truth. Commissioned/tested
agents (A01/A02) exercise library contract paths only. Uncommissioned agents fail closed
via DESIGNED commissioning state, missing implementations, and production refusal.

No worker claim path; Exit 78 unchanged; CI/library-only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Final
from uuid import uuid4

import pytest

from money_machine.agents import (
    AgentContext,
    AgentNotCommissionedError,
    AgentNotImplementedError,
    AgentRegistry,
    ToolRegistry,
    assert_agent_may_execute,
    assert_production_executable,
    parse_system_prompt_reference,
)
from money_machine.agents.prompt_store import PromptStore
from money_machine.config.loader import load_yaml_model
from money_machine.config.settings import AgentCommissioningState, AgentDefinition, AgentsConfig
from money_machine.domain.enums import JobStatus, RetryClass, SideEffectClass
from money_machine.domain.models.common import ArtifactReference, SuccessContract
from money_machine.domain.models.jobs import AgentResult, JobEnvelope
from money_machine.domain.models.listings import ListingPackage, PreflightResult
from money_machine.domain.models.portfolio import IncidentResult, MetricsSnapshot, PortfolioDecision
from money_machine.domain.models.products import (
    BuildResult,
    DedupeResult,
    ProductQAResult,
    ProductSpec,
    ResearchReport,
    TeardownReport,
)

CONFIG_PATH: Final = Path("config/agents.yaml")
ROSTER: Final = tuple(f"A{number:02d}" for number in range(1, 17))
TESTED_AGENTS: Final = frozenset({"A01", "A02"})
DESIGNED_AGENTS: Final = frozenset(agent_id for agent_id in ROSTER if agent_id not in TESTED_AGENTS)

CONTRACT_MODELS: Final = {
    "JobEnvelope": JobEnvelope,
    "AgentResult": AgentResult,
    "ArtifactReference": ArtifactReference,
    "IncidentResult": IncidentResult,
    "ResearchReport": ResearchReport,
    "TeardownReport": TeardownReport,
    "ProductSpec": ProductSpec,
    "DedupeResult": DedupeResult,
    "BuildResult": BuildResult,
    "ProductQAResult": ProductQAResult,
    "ListingPackage": ListingPackage,
    "PreflightResult": PreflightResult,
    "MetricsSnapshot": MetricsSnapshot,
    "PortfolioDecision": PortfolioDecision,
}


def _config_entry(agents_config: AgentsConfig, agent_id: str) -> AgentDefinition:
    for entry in agents_config.agents:
        if entry.agent_id == agent_id:
            return entry
    msg = f"missing roster entry for {agent_id}"
    raise AssertionError(msg)


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


def test_agents_yaml_validates_complete_roster(agents_config: AgentsConfig) -> None:
    assert agents_config.version == 1
    assert tuple(entry.agent_id for entry in agents_config.agents) == ROSTER


def test_registry_loads_exactly_sixteen_agents(registry: AgentRegistry) -> None:
    definitions = registry.all_definitions()
    assert len(definitions) == 16
    assert {definition.agent_id for definition in definitions} == set(ROSTER)


def test_registry_allowlists_reference_only_known_tools(registry: AgentRegistry) -> None:
    registry.validate_tool_allowlists(ToolRegistry.canonical().known_tool_ids())


@pytest.mark.parametrize("agent_id", ROSTER)
def test_roster_commissioning_state_is_honest(
    agents_config: AgentsConfig,
    registry: AgentRegistry,
    agent_id: str,
) -> None:
    config_entry = _config_entry(agents_config, agent_id)
    runtime = registry.get_definition(agent_id)

    if agent_id in TESTED_AGENTS:
        expected = AgentCommissioningState.TESTED
    else:
        expected = AgentCommissioningState.DESIGNED

    assert config_entry.commissioning_state is expected
    assert runtime.commissioning_state is expected
    assert config_entry.commissioning_evidence == ()


@pytest.mark.parametrize("agent_id", ROSTER)
def test_contract_models_import_for_roster_entry(
    agents_config: AgentsConfig,
    agent_id: str,
) -> None:
    entry = _config_entry(agents_config, agent_id)
    contract_names = set(entry.input_contracts) | set(entry.output_contracts)
    assert contract_names, f"{agent_id} must declare at least one contract"
    for contract_name in contract_names:
        assert contract_name in CONTRACT_MODELS, (
            f"{agent_id} references unknown contract {contract_name!r}"
        )


@pytest.mark.parametrize("agent_id", ROSTER)
def test_allowed_tools_resolve_from_canonical_registry(
    registry: AgentRegistry,
    agent_id: str,
) -> None:
    tools = ToolRegistry.canonical()
    definition = registry.get_definition(agent_id)
    assert definition.allowed_tools, f"{agent_id} must declare allowed_tools"
    for tool_id in definition.allowed_tools:
        tools.resolve(tool_id)


@pytest.mark.parametrize("agent_id", ROSTER)
def test_side_effect_policy_is_declared_and_consistent(
    agents_config: AgentsConfig,
    agent_id: str,
) -> None:
    entry = _config_entry(agents_config, agent_id)
    assert entry.allowed_side_effect_classes
    assert entry.default_side_effect_class in entry.allowed_side_effect_classes
    for side_effect_class in entry.allowed_side_effect_classes:
        assert isinstance(side_effect_class, SideEffectClass)


@pytest.mark.parametrize("agent_id", ROSTER)
def test_system_prompt_reference_matches_agent_id(
    registry: AgentRegistry,
    agent_id: str,
) -> None:
    definition = registry.get_definition(agent_id)
    referenced_agent_id, version = parse_system_prompt_reference(definition.system_prompt_reference)
    assert referenced_agent_id == agent_id
    assert version.startswith("v")


@pytest.mark.parametrize("agent_id", TESTED_AGENTS)
def test_tested_agent_prompt_file_exists(
    repository_root: Path,
    registry: AgentRegistry,
    agent_id: str,
) -> None:
    definition = registry.get_definition(agent_id)
    referenced_agent_id, version = parse_system_prompt_reference(definition.system_prompt_reference)
    prompt_path = repository_root / "prompts" / "agents" / referenced_agent_id / f"{version}.md"
    assert prompt_path.is_file(), f"missing prompt for tested agent {agent_id}"


@pytest.mark.parametrize("agent_id", TESTED_AGENTS)
def test_tested_agent_prompt_passes_store_integrity_checks(
    repository_root: Path,
    registry: AgentRegistry,
    agent_id: str,
) -> None:
    definition = registry.get_definition(agent_id)
    referenced_agent_id, version = parse_system_prompt_reference(definition.system_prompt_reference)
    prompt_path = repository_root / "prompts" / "agents" / referenced_agent_id / f"{version}.md"
    content = prompt_path.read_text(encoding="utf-8")
    expected_hash = sha256(content.encode("utf-8")).hexdigest()
    store = PromptStore(repository_root)
    assert store.load(referenced_agent_id, version, expected_hash=expected_hash) == content


@pytest.mark.parametrize("agent_id", TESTED_AGENTS)
def test_tested_agent_allows_production_gate(registry: AgentRegistry, agent_id: str) -> None:
    definition = registry.get_definition(agent_id)
    assert definition.allows_production_execution() is True
    assert_agent_may_execute(definition, production=True)
    assert_production_executable(definition)


@pytest.mark.parametrize("agent_id", DESIGNED_AGENTS)
def test_designed_agent_refuses_production_execution(
    registry: AgentRegistry,
    agent_id: str,
) -> None:
    definition = registry.get_definition(agent_id)
    assert definition.commissioning_state is AgentCommissioningState.DESIGNED
    assert definition.allows_production_execution() is False
    with pytest.raises(AgentNotCommissionedError, match=agent_id):
        assert_production_executable(definition)
    with pytest.raises(AgentNotCommissionedError, match=agent_id):
        assert_agent_may_execute(definition, production=True)


@pytest.mark.parametrize("agent_id", DESIGNED_AGENTS)
def test_designed_agent_allows_simulation_gate(registry: AgentRegistry, agent_id: str) -> None:
    definition = registry.get_definition(agent_id)
    assert_agent_may_execute(definition, production=False)


@pytest.mark.parametrize("agent_id", DESIGNED_AGENTS)
def test_designed_agent_has_no_implementation(registry: AgentRegistry, agent_id: str) -> None:
    with pytest.raises(AgentNotImplementedError, match=agent_id):
        registry.get_implementation(agent_id)


@pytest.mark.parametrize("agent_id", TESTED_AGENTS)
def test_tested_agent_has_implementation(registry: AgentRegistry, agent_id: str) -> None:
    implementation = registry.get_implementation(agent_id)
    assert implementation is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("agent_id", "job_type", "output_key"),
    [
        ("A01", "BootstrapRecordsJob", "initial_workflows_created"),
        ("A02", "ProvisioningCheckJob", "providers"),
    ],
)
async def test_tested_agent_executes_library_contract_path(
    registry: AgentRegistry,
    agent_id: str,
    job_type: str,
    output_key: str,
) -> None:
    """Library-only execution: no AgentRunner DB path, no worker claim, no live providers."""
    job = _job_for(agent_id, job_type=job_type)
    definition = registry.get_definition(agent_id)
    implementation = registry.get_implementation(agent_id)

    context = AgentContext(
        job=job,
        definition=definition,
        run_id=uuid4(),
        prompt_text="",
        prompt_reference=definition.system_prompt_reference,
        prompt_sha256="0" * 64,
        prompt_version=1,
        provider=None,  # type: ignore[arg-type]
        run_at=datetime.now(tz=UTC),
        tool_registry=ToolRegistry.canonical(),
    )

    result = await implementation.execute(context)
    assert result.agent_id == agent_id
    assert result.status.value == "SUCCESS"
    assert output_key in result.output
