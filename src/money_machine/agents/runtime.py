"""Agent runner orchestration and durable run receipts.

Contract: Session 04 L1 — AgentRunner core lane (W4). Exit 78 and the production
claim path remain out of scope; this module executes agents only when invoked directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.agents.base import (
    AgentContext,
    AgentDefinition,
    AgentNotCommissionedError,
    AgentRegistryError,
    BaseAgent,
    assert_production_executable,
    parse_system_prompt_reference,
)
from money_machine.agents.prompt_store import PromptStore
from money_machine.agents.registry import AgentRegistry
from money_machine.domain.enums import AgentRunStatus
from money_machine.domain.models.common import ContractError
from money_machine.domain.models.jobs import AgentResult, JobEnvelope
from money_machine.integrations.llm.interface import LLMCallMetadata, LLMProvider
from money_machine.persistence.repositories.agents import (
    AgentDefinitionRepository,
    AgentRunRepository,
    PromptVersionRepository,
)
from money_machine.persistence.tables import AgentDefinition as AgentDefinitionRow
from money_machine.persistence.tables import AgentRun, PromptVersion

LOGGER: Final = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentRunReceipt:
    """Durable receipt for one agent execution persisted to ``agent_runs``."""

    run_id: UUID
    job_id: UUID
    agent_id: str
    agent_definition_id: UUID
    agent_definition_version: int
    prompt_version_id: UUID
    prompt_reference: str
    prompt_sha256: str
    status: AgentRunStatus
    output: dict[str, Any]
    error: ContractError | None
    started_at: datetime
    completed_at: datetime
    metadata: LLMCallMetadata | None = None


class AgentRunner:
    """Orchestrate agent execution with commissioning gates and run receipts."""

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        prompt_store: PromptStore,
        provider: LLMProvider,
    ) -> None:
        self._registry = registry
        self._prompt_store = prompt_store
        self._provider = provider

    @classmethod
    def from_repository_root(
        cls,
        repository_root: Path | str,
        *,
        provider: LLMProvider,
    ) -> AgentRunner:
        root = Path(repository_root)
        return cls(
            registry=AgentRegistry.from_yaml(root),
            prompt_store=PromptStore(root),
            provider=provider,
        )

    def definition_for_job(self, job: JobEnvelope) -> AgentDefinition:
        """Resolve the owning agent definition for one job envelope."""
        return self._registry.get(job.owner_agent_id)

    def assert_production_executable(self, definition: AgentDefinition) -> None:
        """Fail closed when the agent is not executable in production."""
        assert_production_executable(definition)

    async def execute(
        self,
        session: AsyncSession,
        *,
        job: JobEnvelope,
        agent: BaseAgent,
        production: bool = True,
        run_at: datetime | None = None,
    ) -> tuple[AgentResult, AgentRunReceipt]:
        """Execute one agent for a job, persist a run receipt, and return both."""
        started_at = run_at or datetime.now(tz=UTC)
        definition = self.definition_for_job(job)
        if production:
            self.assert_production_executable(definition)

        db_definition = await self._load_database_definition(session, definition)
        prompt_version = await self._load_prompt_version(session, definition)
        prompt_agent_id, prompt_version_label = parse_system_prompt_reference(
            definition.system_prompt_reference
        )
        if prompt_agent_id != definition.agent_id:
            msg = (
                f"prompt reference agent {prompt_agent_id} does not match "
                f"definition agent {definition.agent_id}"
            )
            raise AgentRegistryError(msg)

        prompt_text = self._prompt_store.load(
            prompt_agent_id,
            prompt_version_label,
            expected_hash=prompt_version.sha256,
        )
        run_id = uuid4()
        context = AgentContext(
            job=job,
            definition=definition,
            run_id=run_id,
            prompt_text=prompt_text,
            prompt_reference=prompt_version.prompt_reference,
            prompt_sha256=prompt_version.sha256,
            prompt_version=prompt_version.version,
            provider=self._provider,
            run_at=started_at,
        )
        try:
            result = await agent.execute(context)
        except AgentNotCommissionedError:
            raise
        except Exception as error:
            completed_at = datetime.now(tz=UTC)
            contract_error = ContractError(
                code="AGENT_EXECUTION_FAILED",
                message=str(error),
                retryable=False,
            )
            receipt = await self._persist_run(
                session,
                run_id=run_id,
                job=job,
                definition=db_definition,
                prompt_version=prompt_version,
                status=AgentRunStatus.FAILURE,
                output={},
                error=contract_error,
                started_at=started_at,
                completed_at=completed_at,
            )
            failure = AgentResult(
                job_id=job.job_id,
                agent_run_id=run_id,
                agent_id=definition.agent_id,
                agent_definition_version=definition.contract_version,
                prompt_reference=prompt_version.prompt_reference,
                prompt_sha256=prompt_version.sha256,
                status=AgentRunStatus.FAILURE,
                output={},
                error=contract_error,
            )
            LOGGER.exception(
                "agent execution failed",
                extra={
                    "job_id": str(job.job_id),
                    "agent_id": definition.agent_id,
                    "run_id": str(run_id),
                },
            )
            return failure, receipt

        if result.agent_run_id != run_id:
            msg = "agent result must cite the run id assigned by AgentRunner"
            raise AgentRegistryError(msg)
        if result.job_id != job.job_id:
            msg = "agent result job_id must match the job envelope"
            raise AgentRegistryError(msg)

        completed_at = datetime.now(tz=UTC)
        receipt = await self._persist_run(
            session,
            run_id=run_id,
            job=job,
            definition=db_definition,
            prompt_version=prompt_version,
            status=result.status,
            output=dict(result.output),
            error=result.error,
            started_at=started_at,
            completed_at=completed_at,
        )
        return result, receipt

    async def _load_database_definition(
        self,
        session: AsyncSession,
        definition: AgentDefinition,
    ) -> AgentDefinitionRow:
        row = await AgentDefinitionRepository(session).by_agent_id(definition.agent_id)
        if row is None:
            msg = f"agent definition row missing for {definition.agent_id}"
            raise AgentRegistryError(msg)
        if row.contract_version != definition.contract_version:
            msg = (
                f"database contract version {row.contract_version} "
                f"does not match config {definition.contract_version} for {definition.agent_id}"
            )
            raise AgentRegistryError(msg)
        return row

    async def _load_prompt_version(
        self,
        session: AsyncSession,
        definition: AgentDefinition,
    ) -> PromptVersion:
        prompt_repo = PromptVersionRepository(session)
        row = await prompt_repo.by_reference(definition.system_prompt_reference)
        if row is None:
            msg = f"prompt version missing for {definition.system_prompt_reference}"
            raise AgentRegistryError(msg)
        return row

    async def _persist_run(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        job: JobEnvelope,
        definition: AgentDefinitionRow,
        prompt_version: PromptVersion,
        status: AgentRunStatus,
        output: dict[str, Any],
        error: ContractError | None,
        started_at: datetime,
        completed_at: datetime,
        metadata: LLMCallMetadata | None = None,
    ) -> AgentRunReceipt:
        error_payload = None if error is None else error.model_dump(mode="json")
        run = AgentRun(
            id=run_id,
            job_id=job.job_id,
            agent_definition_id=definition.id,
            agent_id=definition.agent_id,
            agent_definition_version=definition.contract_version,
            prompt_version_id=prompt_version.id,
            prompt_reference=prompt_version.prompt_reference,
            prompt_sha256=prompt_version.sha256,
            status=status.value,
            output=output,
            error=error_payload,
            started_at=started_at,
            completed_at=completed_at,
        )
        AgentRunRepository(session).add(run)
        await session.flush()
        return AgentRunReceipt(
            run_id=run_id,
            job_id=job.job_id,
            agent_id=definition.agent_id,
            agent_definition_id=definition.id,
            agent_definition_version=definition.contract_version,
            prompt_version_id=prompt_version.id,
            prompt_reference=prompt_version.prompt_reference,
            prompt_sha256=prompt_version.sha256,
            status=status,
            output=output,
            error=error,
            started_at=started_at,
            completed_at=completed_at,
            metadata=metadata,
        )


def input_hash(job: JobEnvelope) -> str:
    """Return a stable SHA-256 digest of job input for receipt metadata."""
    payload = job.model_dump_json()
    return sha256(payload.encode("utf-8")).hexdigest()
