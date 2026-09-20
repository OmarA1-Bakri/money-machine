"""Agent definition, prompt version and agent run access."""

from __future__ import annotations

from sqlalchemy import select

from money_machine.persistence.repositories._base import Repository
from money_machine.persistence.tables import AgentDefinition, AgentRun, AgentToolCall, PromptVersion


class AgentDefinitionRepository(Repository[AgentDefinition]):
    """The A01-A16 roster and its commissioning states."""

    model = AgentDefinition

    async def by_agent_id(self, agent_id: str) -> AgentDefinition | None:
        """Fetch the current contract version for one agent."""
        statement = (
            select(AgentDefinition)
            .where(AgentDefinition.agent_id == agent_id)
            .order_by(AgentDefinition.contract_version.desc())
            .limit(1)
        )
        return (await self.session.execute(statement)).scalars().one_or_none()

    async def roster(self) -> tuple[AgentDefinition, ...]:
        """The whole roster in agent-ID order."""
        statement = select(AgentDefinition).order_by(AgentDefinition.agent_id)
        return tuple((await self.session.execute(statement)).scalars().all())

    async def commissioned(self) -> tuple[AgentDefinition, ...]:
        """Only agents whose commissioning state is COMMISSIONED."""
        statement = select(AgentDefinition).where(
            AgentDefinition.commissioning_state == "COMMISSIONED"
        )
        return tuple((await self.session.execute(statement)).scalars().all())


class PromptVersionRepository(Repository[PromptVersion]):
    """Immutable, hashed prompt versions. Prompt text is never stored."""

    model = PromptVersion

    async def by_reference(self, reference: str) -> PromptVersion | None:
        """The highest version recorded for one prompt reference."""
        statement = (
            select(PromptVersion)
            .where(PromptVersion.prompt_reference == reference)
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        return (await self.session.execute(statement)).scalars().one_or_none()

    async def by_sha256(self, digest: str) -> PromptVersion | None:
        """The prompt version holding one content hash."""
        statement = select(PromptVersion).where(PromptVersion.sha256 == digest)
        return (await self.session.execute(statement)).scalars().one_or_none()


class AgentRunRepository(Repository[AgentRun]):
    """Agent executions carrying the lineage chain."""

    model = AgentRun

    async def for_job(self, job_id: object) -> tuple[AgentRun, ...]:
        """Every run for one job, oldest first."""
        statement = select(AgentRun).where(AgentRun.job_id == job_id).order_by(AgentRun.started_at)
        return tuple((await self.session.execute(statement)).scalars().all())

    async def for_agent(self, agent_id: str) -> tuple[AgentRun, ...]:
        """Every run for one agent, oldest first."""
        statement = (
            select(AgentRun).where(AgentRun.agent_id == agent_id).order_by(AgentRun.started_at)
        )
        return tuple((await self.session.execute(statement)).scalars().all())


class AgentToolCallRepository(Repository[AgentToolCall]):
    """Tool invocations recorded against agent runs."""

    model = AgentToolCall

    async def for_run(self, agent_run_id: object) -> tuple[AgentToolCall, ...]:
        """Every tool call for one agent run, oldest first."""
        statement = (
            select(AgentToolCall)
            .where(AgentToolCall.agent_run_id == agent_run_id)
            .order_by(AgentToolCall.created_at)
        )
        return tuple((await self.session.execute(statement)).scalars().all())
