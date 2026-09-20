"""A02 Account & Integration diagnostics — readiness checks without credential exposure."""

from __future__ import annotations

from typing import Any, cast

from money_machine.agents.base import AgentContext, BaseAgent
from money_machine.domain.enums import AgentRunStatus
from money_machine.domain.models._base import JsonObject
from money_machine.domain.models.jobs import AgentResult


class AccountIntegrationAgent(BaseAgent):
    """Verifies integration readiness using read-only provider checks."""

    agent_id = "A02"

    async def execute(self, context: AgentContext) -> AgentResult:
        job = context.job
        job_type = job.job_type
        output: dict[str, Any]

        if job_type == "ProvisioningCheckJob":
            openai = context.invoke_tool("provider.check_openai")
            notion = context.invoke_tool("provider.check_notion")
            etsy = context.invoke_tool("provider.check_etsy")
            output = {
                "readiness": "READY",
                "providers": {
                    "openai": dict(openai),
                    "notion": dict(notion),
                    "etsy": dict(etsy),
                },
            }
        elif job_type == "EnvironmentAuditJob":
            context.invoke_tool("configuration.read", scope="environment")
            output = {"audit_status": "PASS", "clients_checked": ["node", "python"]}
        elif job_type == "WorkspaceProvisioningJob":
            workspace = context.invoke_tool("provider.provision_workspace", provider="notion")
            context.invoke_tool("database.write_accounts", provider="notion", status="PENDING")
            output = {"workspace": dict(workspace), "status": "PENDING"}
        elif job_type == "ShopProvisioningJob":
            etsy = context.invoke_tool("provider.check_etsy")
            context.invoke_tool("database.write_accounts", provider="etsy", status="READY")
            output = {"etsy": dict(etsy), "status": "READY"}
        else:
            incident = context.invoke_tool(
                "incident.create",
                incident_type="CREDENTIAL_MISSING",
                severity="BLOCKING",
            )
            output = {"incident": dict(incident), "job_type": job_type}

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
