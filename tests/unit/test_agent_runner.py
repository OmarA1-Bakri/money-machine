"""Unit tests for agent registry, commissioning gates, and runner receipts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from money_machine.agents.base import (
    AgentDefinition,
    AgentNotCommissionedError,
    assert_production_executable,
    parse_system_prompt_reference,
)
from money_machine.agents.registry import AgentRegistry
from money_machine.agents.runtime import AgentRunner
from money_machine.config.settings import AgentCommissioningState
from money_machine.domain.enums import JobStatus, RetryClass, SideEffectClass
from money_machine.domain.models.common import SuccessContract
from money_machine.domain.models.jobs import JobEnvelope
from money_machine.integrations.llm.fake_provider import FakeLLMProvider


def test_registry_loads_sixteen_agents(repository_root: Path) -> None:
    registry = AgentRegistry.from_yaml(repository_root)
    roster = registry.roster()
    assert len(roster) == 16
    assert roster[0].agent_id == "A01"
    assert roster[-1].agent_id == "A16"


def test_parse_system_prompt_reference() -> None:
    agent_id, version = parse_system_prompt_reference("agent://A01/system/v1")
    assert agent_id == "A01"
    assert version == "v1"


def test_uncommissioned_agent_fails_closed(repository_root: Path) -> None:
    registry = AgentRegistry.from_yaml(repository_root)
    definition = registry.get("A03")  # L2: Use A03 (DESIGNED) instead of A01 (TESTED)
    assert definition.commissioning_state is AgentCommissioningState.DESIGNED
    with pytest.raises(AgentNotCommissionedError, match="production execution requires"):
        assert_production_executable(definition)


def test_tested_agent_allows_production_execution() -> None:
    definition = AgentDefinition(
        agent_id="A01",
        name="Shop Orchestrator",
        contract_version=1,
        system_prompt_reference="agent://A01/system/v1",
        input_contracts=("JobEnvelope",),
        output_contracts=("AgentResult",),
        allowed_tools=("INTERNAL_ORCHESTRATION",),
        default_side_effect_class="NONE",
        timeout_seconds=300,
        commissioning_state=AgentCommissioningState.TESTED,
        commissioning_evidence=(),
    )
    assert definition.allows_production_execution() is True
    assert_production_executable(definition)


def _job_for(agent_id: str) -> JobEnvelope:
    now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    job_id = uuid4()
    workflow_id = uuid4()
    object_id = uuid4()
    return JobEnvelope(
        job_id=job_id,
        workflow_id=workflow_id,
        object_id=object_id,
        job_type="BootstrapRecordsJob",
        object_type="workflow_runs",
        owner_agent_id=agent_id,  # type: ignore[arg-type]
        status=JobStatus.READY,
        input={"shop_id": str(object_id)},
        scheduled_at=now,
        attempt=0,
        max_attempts=3,
        idempotency_key=f"test:{job_id}",
        side_effect_class=SideEffectClass.NONE,
        retry_class=RetryClass.SAFE,
        success_contract=SuccessContract(output_model="AgentResult"),
    )


def test_runner_assert_production_executable(repository_root: Path) -> None:
    runner = AgentRunner.from_repository_root(
        repository_root,
        provider=FakeLLMProvider(),
    )
    definition = runner.definition_for_job(_job_for("A03"))  # L2: Use A03 (DESIGNED) instead of A01 (TESTED)
    with pytest.raises(AgentNotCommissionedError):
        runner.assert_production_executable(definition)
