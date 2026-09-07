"""Cross-file configuration validation and environment authority reduction."""

from __future__ import annotations

from decimal import Decimal

from money_machine.config.settings import (
    AgentsConfig,
    AutonomyConfig,
    ConfigurationBundle,
    ProductRulesConfig,
    PublishingRampConfig,
    RuntimeEnvironment,
    TelemetryConfig,
    WorkflowsConfig,
)
from money_machine.domain.enums import AutonomyMode


def apply_environment_safety(
    autonomy: AutonomyConfig,
    environment: RuntimeEnvironment,
) -> AutonomyConfig:
    """Reduce test and development authority to a simulation-only contract."""
    if environment is RuntimeEnvironment.PRODUCTION:
        return autonomy

    values = autonomy.model_dump()
    values.update(
        {
            "mode": AutonomyMode.SIMULATION,
            "external_mutations_enabled": False,
            "external_spend_enabled": False,
            "auto_publish": False,
            "auto_deactivate": False,
            "auto_multiply": False,
            "external_message_enabled": False,
            "message_monthly_cap": 0,
            "authorized_recipient_scopes": (),
            "competitor_purchase_enabled": False,
            "competitor_purchase_max_each": Decimal("0"),
            "competitor_purchase_monthly_cap": Decimal("0"),
            "live_checkout_test_enabled": False,
            "live_checkout_test_cap": Decimal("0"),
            "paid_tool_monthly_cap": Decimal("0"),
        }
    )
    return AutonomyConfig.model_validate(values)


def validate_config_bundle(
    *,
    product_rules: ProductRulesConfig,
    publishing_ramp: PublishingRampConfig,
    autonomy: AutonomyConfig,
    agents: AgentsConfig,
    workflows: WorkflowsConfig,
    telemetry: TelemetryConfig,
) -> ConfigurationBundle:
    """Reject contradictions that can only be detected across YAML files."""
    if autonomy.weekly_listing_cap > publishing_ramp.hard_weekly_cap:
        raise ValueError("autonomy weekly listing cap exceeds the publishing hard cap")
    if autonomy.auto_publish and not publishing_ramp.publishing_enabled:
        raise ValueError("auto_publish requires the publishing ramp to be enabled")

    agents_by_id = {definition.agent_id: definition for definition in agents.agents}
    for workflow in workflows.workflows:
        for job in workflow.jobs:
            owner = agents_by_id[job.owner_agent_id]
            if job.side_effect_class not in owner.allowed_side_effect_classes:
                raise ValueError(
                    f"{job.job_type} assigns {job.side_effect_class} to {owner.agent_id} "
                    "outside the agent side-effect contract"
                )
            if job.retry_class not in owner.allowed_retry_classes:
                raise ValueError(
                    f"{job.job_type} assigns {job.retry_class} to {owner.agent_id} "
                    "outside the agent retry contract"
                )
            if (
                job.capability_operation is not None
                and job.capability_operation not in owner.provider_operations
            ):
                raise ValueError(
                    f"{job.job_type} uses operation {job.capability_operation} "
                    f"outside {owner.agent_id} provider operations"
                )

    return ConfigurationBundle(
        product_rules=product_rules,
        publishing_ramp=publishing_ramp,
        autonomy=autonomy,
        agents=agents,
        workflows=workflows,
        telemetry=telemetry,
    )
