"""Unit tests for agent registry, commissioning gates, and runner receipts."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from money_machine.agents.base import (
    AgentDefinition,
    AgentNotCommissionedError,
    assert_production_executable,
    parse_system_prompt_reference,
)
from money_machine.agents.runtime import (
    AgentRunner,
    _provider_model_name,
    _receipt_from_run,
)
from money_machine.config.settings import AgentCommissioningState
from money_machine.domain.enums import AgentRunStatus, JobStatus, RetryClass, SideEffectClass
from money_machine.domain.models.common import SuccessContract
from money_machine.domain.models.jobs import JobEnvelope
from money_machine.integrations.llm.fake_provider import FakeLLMProvider
from money_machine.persistence.tables import AgentRun


def test_parse_system_prompt_reference() -> None:
    agent_id, version = parse_system_prompt_reference("agent://A01/system/v1")
    assert agent_id == "A01"
    assert version == "v1"


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


def test_provider_model_name_reads_fake_provider_default() -> None:
    assert _provider_model_name(FakeLLMProvider(default_model="lane-model")) == "lane-model"
    assert _provider_model_name(MagicMock()) is None


def test_receipt_from_run_maps_persisted_row() -> None:
    run_id = uuid4()
    job_id = uuid4()
    definition_id = uuid4()
    prompt_id = uuid4()
    started_at = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    completed_at = datetime(2026, 9, 20, 12, 1, tzinfo=UTC)
    run = AgentRun(
        id=run_id,
        job_id=job_id,
        agent_definition_id=definition_id,
        agent_id="A01",
        agent_definition_version=1,
        prompt_version_id=prompt_id,
        prompt_reference="agent://A01/system/v1",
        prompt_sha256="a" * 64,
        run_number=2,
        model="fake-model-1",
        input_hash="b" * 64,
        token_count=42,
        cost_usd=Decimal("0.01"),
        status="SUCCESS",
        output={"ok": True},
        error=None,
        started_at=started_at,
        completed_at=completed_at,
    )
    receipt = _receipt_from_run(run, error=None)
    assert receipt.run_id == run_id
    assert receipt.job_id == job_id
    assert receipt.agent_id == "A01"
    assert receipt.status is AgentRunStatus.SUCCESS
    assert receipt.output == {"ok": True}
    assert receipt.started_at == started_at
    assert receipt.completed_at == completed_at


def test_runner_accepts_injected_observer(repository_root: Path) -> None:
    observer = MagicMock()
    runner = AgentRunner.from_repository_root(
        repository_root,
        provider=FakeLLMProvider(),
    )
    runner_with_observer = AgentRunner(
        registry=runner._registry,
        prompt_store=runner._prompt_store,
        provider=runner._provider,
        observer=observer,
    )
    assert runner_with_observer._observer is observer


def test_runner_assert_production_executable(repository_root: Path) -> None:
    runner = AgentRunner.from_repository_root(
        repository_root,
        provider=FakeLLMProvider(),
    )
    definition = runner.definition_for_job(
        _job_for("A03")
    )  # L2: Use A03 (DESIGNED) instead of A01 (TESTED)
    with pytest.raises(AgentNotCommissionedError):
        runner.assert_production_executable(definition)
