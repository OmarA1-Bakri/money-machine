"""A01 Shop Orchestrator — deterministic job routing without external effects."""

from __future__ import annotations

from typing import Any, cast

from money_machine.agents.base import AgentContext, BaseAgent
from money_machine.domain.enums import AgentRunStatus
from money_machine.domain.models._base import JsonObject
from money_machine.domain.models.jobs import AgentResult


class ShopOrchestratorAgent(BaseAgent):
    """Creates typed successor jobs and inspects workflow state."""

    agent_id = "A01"

    async def execute(self, context: AgentContext) -> AgentResult:
        job = context.job
        job_type = job.job_type
        output: dict[str, Any]

        if job_type == "BootstrapRecordsJob":
            context.invoke_tool("configuration.read", scope="shop")
            context.invoke_tool("database.read", table="integration_accounts")
            successor = context.invoke_tool(
                "job.create",
                job_type="ProductBuildJob",
                owner_agent_id="A07",
            )
            output = {
                "initial_workflows_created": 3,
                "successor_job": dict(successor),
            }
        elif job_type == "ScheduleConfigurationJob":
            context.invoke_tool("database.write_orchestration", table="scheduled_triggers")
            output = {
                "schedule_utc": "0 9 * * 1",
                "timezone": "UTC",
            }
        elif job_type == "BuildSlotJob":
            workflow = context.invoke_tool("workflow.inspect", workflow_id=str(job.workflow_id))
            output = {
                "decision": "SLOT_DEFERRED",
                "workflow": dict(workflow),
            }
        else:
            context.invoke_tool("workflow.inspect", workflow_id=str(job.workflow_id))
            output = {"routed": True, "job_type": job_type}

        return AgentResult(
            job_id=job.job_id,
            agent_run_id=context.agent_run_id,
            agent_id=self.agent_id,
            agent_definition_version=context.definition.contract_version,
            prompt_reference=context.prompt_reference,
            prompt_sha256=context.prompt_sha256,
            status=AgentRunStatus.SUCCESS,
            output=cast(JsonObject, output),
        )
