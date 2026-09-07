from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from money_machine.config import (
    AUTONOMY_EXAMPLE_FILE_NAME,
    AUTONOMY_FILE_NAME,
    ENVIRONMENT_VARIABLE,
    PLAYBOOK_MACHINE_WEEKLY_CAP,
    AgentsConfig,
    AutonomyConfig,
    ConfigLoadError,
    ProductRulesConfig,
    PublishingRampConfig,
    RuntimeEnvironment,
    TelemetryConfig,
    WorkflowDefinition,
    WorkflowJobDefinition,
    WorkflowsConfig,
    apply_environment_safety,
    load_config_bundle,
    load_yaml_model,
    resolve_runtime_environment,
    validate_config_bundle,
)
from money_machine.domain.enums import AutonomyMode, SideEffectClass
from money_machine.domain.events import TelemetryEventName
from money_machine.domain.models import ListingRules, ProductShapeRules

CONFIG_DIR = Path(__file__).parents[2] / "config"


def load_source_configs() -> tuple[
    ProductRulesConfig,
    PublishingRampConfig,
    AutonomyConfig,
    AgentsConfig,
    WorkflowsConfig,
]:
    return (
        load_yaml_model(CONFIG_DIR / "product_rules.yaml", ProductRulesConfig),
        load_yaml_model(CONFIG_DIR / "publishing_ramp.yaml", PublishingRampConfig),
        load_yaml_model(CONFIG_DIR / "autonomy.example.yaml", AutonomyConfig),
        load_yaml_model(CONFIG_DIR / "agents.yaml", AgentsConfig),
        load_yaml_model(CONFIG_DIR / "workflows.yaml", WorkflowsConfig),
    )


def load_telemetry() -> TelemetryConfig:
    return load_yaml_model(CONFIG_DIR / "telemetry.yaml", TelemetryConfig)


def test_source_configuration_encodes_all_playbook_defaults() -> None:
    product_rules, ramp, autonomy, agents, workflows = load_source_configs()

    assert (product_rules.research_rows.minimum, product_rules.research_rows.maximum) == (
        25,
        40,
    )
    assert product_rules.shortlisted_candidates == 5
    assert (
        product_rules.qualification.build_threshold,
        product_rules.qualification.maximum_score,
    ) == (30, 40)
    assert (product_rules.niche_selection.primary, product_rules.niche_selection.backup) == (
        1,
        1,
    )
    assert (product_rules.product_shape.hubs.minimum, product_rules.product_shape.hubs.maximum) == (
        6,
        8,
    )
    assert (
        product_rules.product_shape.colour_variants.minimum,
        product_rules.product_shape.colour_variants.maximum,
    ) == (3, 4)
    assert product_rules.listing_assets.tags == 13
    assert product_rules.listing_assets.images == 10
    assert product_rules.listing_assets.videos == 1
    assert product_rules.listing_assets.description_sections == 8
    assert product_rules.listing_assets.quantity == 999
    assert product_rules.portfolio.maturity_live_days == 30
    assert product_rules.portfolio.cull_bottom_percent == Decimal("80")
    assert product_rules.portfolio.deep_pass_cadence == "monthly"
    assert product_rules.experiments.new_fronts_per_batch == 1

    assert (ramp.launch_target.minimum, ramp.launch_target.maximum) == (2, 3)
    assert ramp.initial_weekly_cap == 2
    assert ramp.hard_weekly_cap == 15 == PLAYBOOK_MACHINE_WEEKLY_CAP
    assert ramp.publishing_enabled is False

    assert autonomy.mode is AutonomyMode.SIMULATION
    assert autonomy.weekly_listing_cap == 2
    assert autonomy.external_mutations_enabled is False
    assert autonomy.external_spend_enabled is False
    assert autonomy.external_message_enabled is False
    assert autonomy.authorized_recipient_scopes == ()

    assert {definition.agent_id for definition in agents.agents} == {
        f"A{number:02d}" for number in range(1, 17)
    }
    configured_jobs = {job.job_type for workflow in workflows.workflows for job in workflow.jobs}
    assert {
        "ResearchCollectionJob",
        "ProductBuildJob",
        "PublishListingJob",
        "WeeklyReviewJob",
        "DeactivateListingJob",
        "SuccessorProductJob",
        "IncidentRepairJob",
    } <= configured_jobs


def test_source_configuration_loads_as_one_cross_validated_bundle() -> None:
    bundle = load_config_bundle(CONFIG_DIR, environment=RuntimeEnvironment.DEVELOPMENT)

    assert bundle.autonomy.mode is AutonomyMode.SIMULATION
    assert len(bundle.agents.agents) == 16
    assert bundle.publishing_ramp.hard_weekly_cap == 15


def test_configuration_binds_domain_rules_that_contracts_enforce() -> None:
    product_rules, _, _, _, _ = load_source_configs()

    listing_rules = product_rules.listing_rules()
    shape_rules = product_rules.product_shape_rules()

    assert listing_rules == ListingRules(
        rule_version="product-rules-v1",
        tags=13,
        images=10,
        videos=1,
        description_sections=8,
        quantity=999,
        image_role="listing_image",
        video_role="listing_video",
    )
    assert shape_rules == ProductShapeRules(
        rule_version="product-rules-v1",
        hubs_minimum=6,
        hubs_maximum=8,
        colour_variants_minimum=3,
        colour_variants_maximum=4,
    )


def test_production_requires_the_operator_autonomy_file_not_the_example(tmp_path: Path) -> None:
    assert not (CONFIG_DIR / AUTONOMY_FILE_NAME).exists(), "operator file must not be tracked"
    with pytest.raises(ConfigLoadError, match=r"production requires .*autonomy\.yaml"):
        load_config_bundle(CONFIG_DIR, environment=RuntimeEnvironment.PRODUCTION)

    for name in (
        "product_rules.yaml",
        "publishing_ramp.yaml",
        AUTONOMY_EXAMPLE_FILE_NAME,
        "agents.yaml",
        "workflows.yaml",
        "telemetry.yaml",
    ):
        (tmp_path / name).write_bytes((CONFIG_DIR / name).read_bytes())
    example = load_yaml_model(tmp_path / AUTONOMY_EXAMPLE_FILE_NAME, AutonomyConfig)
    live = AutonomyConfig.model_validate(
        {
            **example.model_dump(),
            "mode": AutonomyMode.LIVE,
            "external_mutations_enabled": True,
            "auto_deactivate": True,
        }
    )
    operator = tmp_path / AUTONOMY_FILE_NAME
    operator.write_text(yaml.safe_dump(live.model_dump(mode="json")), encoding="utf-8")

    production = load_config_bundle(tmp_path, environment=RuntimeEnvironment.PRODUCTION)
    assert production.autonomy.mode is AutonomyMode.LIVE
    assert production.autonomy.auto_deactivate is True
    development = load_config_bundle(tmp_path, environment=RuntimeEnvironment.DEVELOPMENT)
    assert development.autonomy.mode is AutonomyMode.SIMULATION
    assert development.autonomy.auto_deactivate is False


def test_symlinked_autonomy_file_cannot_smuggle_the_template_into_production(
    tmp_path: Path,
) -> None:
    for name in (
        "product_rules.yaml",
        "publishing_ramp.yaml",
        AUTONOMY_EXAMPLE_FILE_NAME,
        "agents.yaml",
        "workflows.yaml",
        "telemetry.yaml",
    ):
        (tmp_path / name).write_bytes((CONFIG_DIR / name).read_bytes())
    (tmp_path / AUTONOMY_FILE_NAME).symlink_to(tmp_path / AUTONOMY_EXAMPLE_FILE_NAME)

    with pytest.raises(ConfigLoadError, match="not a symlink"):
        load_config_bundle(tmp_path, environment=RuntimeEnvironment.PRODUCTION)


def test_runtime_environment_defaults_to_development_and_rejects_unknown_values() -> None:
    assert resolve_runtime_environment({}) is RuntimeEnvironment.DEVELOPMENT
    assert resolve_runtime_environment({ENVIRONMENT_VARIABLE: "test"}) is RuntimeEnvironment.TEST
    assert (
        resolve_runtime_environment({ENVIRONMENT_VARIABLE: " Production "})
        is RuntimeEnvironment.PRODUCTION
    )
    with pytest.raises(ConfigLoadError, match="is not a runtime environment"):
        resolve_runtime_environment({ENVIRONMENT_VARIABLE: "staging"})
    assert ENVIRONMENT_VARIABLE == "APP_ENV"


def test_weekly_caps_cannot_exceed_the_playbook_machine_cap() -> None:
    _, ramp, autonomy, _, _ = load_source_configs()

    with pytest.raises(ValidationError, match="less than or equal to 15"):
        PublishingRampConfig.model_validate({**ramp.model_dump(), "hard_weekly_cap": 16})
    with pytest.raises(ValidationError, match="less than or equal to 15"):
        PublishingRampConfig.model_validate({**ramp.model_dump(), "hard_weekly_cap": 100})
    with pytest.raises(ValidationError, match="less than or equal to 15"):
        AutonomyConfig.model_validate({**autonomy.model_dump(), "weekly_listing_cap": 16})
    PublishingRampConfig.model_validate({**ramp.model_dump(), "hard_weekly_cap": 15})


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"weekly_listing_cap": 0}, "greater than 0"),
        ({"paid_tool_monthly_cap": "-1.00"}, "greater than or equal to"),
        ({"undocumented_switch": True}, "Extra inputs are not permitted"),
        ({"auto_publish": True}, "auto_publish requires live external mutations"),
        ({"mode": "Live"}, "not a valid AutonomyMode"),
        ({"external_spend_enabled": True}, "simulation forbids external authority"),
    ],
)
def test_autonomy_rejections_fail_closed(overrides: dict[str, Any], expected: str) -> None:
    _, _, autonomy, _, _ = load_source_configs()
    with pytest.raises(ValidationError, match=expected):
        AutonomyConfig.model_validate({**autonomy.model_dump(), **overrides})


def test_strict_configuration_rejects_unknown_keys_and_invalid_ranges() -> None:
    product_rules, _, _, _, _ = load_source_configs()
    dumped: dict[str, Any] = product_rules.model_dump()

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProductRulesConfig.model_validate({**dumped, "undocumented_rule": 1})
    with pytest.raises(ValidationError, match="minimum cannot exceed maximum"):
        ProductRulesConfig.model_validate(
            {
                **dumped,
                "research_rows": {"minimum": 41, "maximum": 40},
            }
        )


def test_configuration_rejects_contradictory_thresholds_and_caps() -> None:
    product_rules, ramp, _, _, _ = load_source_configs()

    with pytest.raises(ValidationError, match="build threshold cannot exceed maximum score"):
        ProductRulesConfig.model_validate(
            {
                **product_rules.model_dump(),
                "qualification": {"build_threshold": 41, "maximum_score": 40},
            }
        )
    with pytest.raises(ValidationError, match="initial weekly cap cannot exceed hard weekly cap"):
        PublishingRampConfig.model_validate(
            {
                **ramp.model_dump(),
                "initial_weekly_cap": 16,
                "hard_weekly_cap": 15,
            }
        )


def test_autonomy_rejects_unbacked_live_effect_authority() -> None:
    _, _, autonomy, _, _ = load_source_configs()
    dumped = autonomy.model_dump()

    with pytest.raises(ValidationError, match="auto_publish requires live external mutations"):
        AutonomyConfig.model_validate(
            {
                **dumped,
                "mode": AutonomyMode.LIVE,
                "auto_publish": True,
                "external_mutations_enabled": False,
            }
        )
    with pytest.raises(ValidationError, match="message authority requires a positive cap"):
        AutonomyConfig.model_validate(
            {
                **dumped,
                "mode": AutonomyMode.LIVE,
                "external_message_enabled": True,
                "message_monthly_cap": 0,
            }
        )
    with pytest.raises(ValidationError, match="message authority requires recipient scopes"):
        AutonomyConfig.model_validate(
            {
                **dumped,
                "mode": AutonomyMode.LIVE,
                "external_message_enabled": True,
                "message_monthly_cap": 1,
            }
        )


def test_test_and_development_environments_force_simulation_only() -> None:
    _, _, autonomy, _, _ = load_source_configs()
    live = AutonomyConfig.model_validate(
        {
            **autonomy.model_dump(),
            "mode": AutonomyMode.LIVE,
            "external_mutations_enabled": True,
            "auto_publish": True,
        }
    )

    for environment in (RuntimeEnvironment.TEST, RuntimeEnvironment.DEVELOPMENT):
        effective = apply_environment_safety(live, environment)
        assert effective.mode is AutonomyMode.SIMULATION
        assert effective.external_mutations_enabled is False
        assert effective.external_spend_enabled is False
        assert effective.external_message_enabled is False
        assert effective.auto_publish is False
        assert effective.auto_deactivate is False
        assert effective.competitor_purchase_enabled is False
        assert effective.live_checkout_test_enabled is False
        assert effective.paid_tool_monthly_cap == Decimal("0")


def test_cross_file_validation_rejects_job_authority_outside_owner_contract() -> None:
    product_rules, ramp, autonomy, agents, workflows = load_source_configs()
    workflow = workflows.workflows[0]
    jobs = list(workflow.jobs)
    build_index = next(index for index, job in enumerate(jobs) if job.job_type == "ProductBuildJob")
    jobs[build_index] = WorkflowJobDefinition.model_validate(
        {**jobs[build_index].model_dump(), "owner_agent_id": "A16"}
    )
    invalid_workflows = WorkflowsConfig.model_validate(
        {
            **workflows.model_dump(),
            "workflows": ({**workflow.model_dump(), "jobs": tuple(jobs)},),
        }
    )

    with pytest.raises(ValueError, match="ProductBuildJob assigns EXTERNAL_WRITE to A16"):
        validate_config_bundle(
            product_rules=product_rules,
            publishing_ramp=ramp,
            autonomy=autonomy,
            agents=agents,
            workflows=invalid_workflows,
            telemetry=load_telemetry(),
        )


def test_workflow_graph_rejects_unreachable_jobs_and_draft_spend_or_message() -> None:
    _, _, _, _, workflows = load_source_configs()
    workflow = workflows.workflows[0]
    dumped = workflow.model_dump()
    jobs = list(dumped["jobs"])
    jobs.append(
        {
            **jobs[-1],
            "job_type": "OrphanJob",
            "successor_job_types": (),
        }
    )
    with pytest.raises(ValidationError, match="unreachable: OrphanJob"):
        WorkflowDefinition.model_validate({**dumped, "jobs": tuple(jobs)})

    spend_job = next(job for job in workflow.jobs if job.job_type == "CompetitorPurchaseJob")
    with pytest.raises(ValidationError, match="draft mode prohibits spend and message effects"):
        WorkflowJobDefinition.model_validate(
            {**spend_job.model_dump(), "allowed_modes": ("simulation", "draft", "live")}
        )
    message_job = next(job for job in workflow.jobs if job.job_type == "ProofDistributionJob")
    assert AutonomyMode.DRAFT not in message_job.allowed_modes
    assert AutonomyMode.SIMULATION in message_job.allowed_modes


def test_source_workflow_covers_repair_loop_and_every_documented_job_is_reachable() -> None:
    _, _, _, agents, workflows = load_source_configs()
    workflow = workflows.workflows[0]
    configured = {job.job_type: job for job in workflow.jobs}

    assert {"LinkVerificationJob", "NotionRepairJob", "ScaleEvaluationJob"} <= configured.keys()
    assert "CullDecisionJob" not in configured
    assert "LinkVerificationJob" in configured["WeeklyReviewJob"].successor_job_types
    assert "NotionRepairJob" in configured["IncidentRepairJob"].successor_job_types
    assert "ScaleEvaluationJob" in configured["MonthlyDeepPassJob"].successor_job_types
    assert AutonomyMode.SIMULATION in configured["ProvisioningCheckJob"].allowed_modes
    owner = next(agent for agent in agents.agents if agent.agent_id == "A09")
    assert "NOTION_LINK_READ" in owner.provider_operations


def test_commissioned_agents_require_locatable_evidence() -> None:
    _, _, _, agents, _ = load_source_configs()
    agent = agents.agents[0].model_dump()

    with pytest.raises(ValidationError, match="String should match pattern"):
        AgentsConfig.model_validate(
            {
                **agents.model_dump(),
                "agents": (
                    {
                        **agent,
                        "commissioning_state": "COMMISSIONED",
                        "commissioning_evidence": ("anything",),
                    },
                    *(other.model_dump() for other in agents.agents[1:]),
                ),
            }
        )
    with pytest.raises(ValidationError, match="must not contain"):
        AgentsConfig.model_validate(
            {
                **agents.model_dump(),
                "agents": (
                    {
                        **agent,
                        "commissioning_state": "COMMISSIONED",
                        "commissioning_evidence": ("docs/../.env",),
                    },
                    *(other.model_dump() for other in agents.agents[1:]),
                ),
            }
        )
    with pytest.raises(ValidationError, match="COMMISSIONED requires evidence"):
        AgentsConfig.model_validate(
            {
                **agents.model_dump(),
                "agents": (
                    {**agent, "commissioning_state": "COMMISSIONED", "commissioning_evidence": ()},
                    *(other.model_dump() for other in agents.agents[1:]),
                ),
            }
        )
    assert all(agent.commissioning_state.value != "COMMISSIONED" for agent in agents.agents)


def test_telemetry_is_typed_disabled_and_matches_the_workbook_taxonomy() -> None:
    telemetry = load_telemetry()
    bundle = load_config_bundle(CONFIG_DIR, environment=RuntimeEnvironment.DEVELOPMENT)

    assert telemetry.enabled is False
    assert set(telemetry.allowed_events) == set(TelemetryEventName)
    assert len(TelemetryEventName) == 23
    assert bundle.telemetry == telemetry
    with pytest.raises(ValidationError, match="not a valid TelemetryEventName"):
        TelemetryConfig.model_validate(
            {**telemetry.model_dump(), "allowed_events": ("RESEARCH_COMPLETED",)}
        )
    with pytest.raises(ValidationError, match="enabled telemetry requires"):
        TelemetryConfig.model_validate(
            {**telemetry.model_dump(), "enabled": True, "allowed_events": ()}
        )


def test_yaml_loader_reports_invalid_or_non_mapping_documents(tmp_path: Path) -> None:
    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text("version: [\n", encoding="utf-8")
    sequence_yaml = tmp_path / "sequence.yaml"
    sequence_yaml.write_text("- version\n- 1\n", encoding="utf-8")

    with pytest.raises(ConfigLoadError, match="cannot parse YAML"):
        load_yaml_model(invalid_yaml, ProductRulesConfig)
    with pytest.raises(ConfigLoadError, match="must contain a mapping"):
        load_yaml_model(sequence_yaml, ProductRulesConfig)


def test_invalid_capability_enum_is_rejected_without_coercion() -> None:
    _, _, _, _, workflows = load_source_configs()
    job = workflows.workflows[0].jobs[0]

    with pytest.raises(ValidationError, match="not a valid SideEffectClass"):
        WorkflowJobDefinition.model_validate(
            {**job.model_dump(), "side_effect_class": "external-write"}
        )
    assert job.side_effect_class in set(SideEffectClass)


PLAYBOOK_TABLES = (
    Path(__file__).parents[2] / "docs/playbook/CHAPTER_TO_CAPABILITY_MAP.md",
    Path(__file__).parents[2] / "docs/playbook/PROMPT_LIBRARY_MAP.md",
)


def test_playbook_maps_agree_with_workflow_configuration_for_single_job_rows() -> None:
    """Docs are not authority, so they must not drift from the typed workflow graph."""
    _, _, _, _, workflows = load_source_configs()
    configured = {job.job_type: job for job in workflows.workflows[0].jobs}
    checked = 0
    for table in PLAYBOOK_TABLES:
        for line in table.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| ") or "Job" not in line:
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            job_cells = [
                cell for cell in cells if re.fullmatch(r"`[A-Z][A-Za-z]+Job`(?: \(.*\))?", cell)
            ]
            if len(job_cells) != 1:
                continue
            job_type = job_cells[0].split("`")[1]
            job = configured[job_type]
            effect_cells = [
                cell for cell in cells if cell.strip("`") in {c.value for c in SideEffectClass}
            ]
            mode_cells = [
                cell
                for cell in cells
                if re.fullmatch(
                    r"(?:simulation|draft|live)(?:/(?:simulation|draft|live))*(?: with .*)?", cell
                )
            ]
            assert effect_cells and mode_cells, (table.name, job_type)
            assert effect_cells[0].strip("`") == job.side_effect_class.value, (table.name, job_type)
            documented_modes = set(mode_cells[0].split(" with ")[0].split("/"))
            assert documented_modes == {mode.value for mode in job.allowed_modes}, (
                table.name,
                job_type,
            )
            checked += 1
    assert checked >= 10, checked


INTEGRATION_MATRIX = Path(__file__).parents[2] / "docs/architecture/INTEGRATION_MATRIX.md"


def test_every_capability_operation_has_a_matching_integration_matrix_row() -> None:
    """Exit criterion: the integration strategy is explicit for every provider operation."""
    _, _, _, agents, workflows = load_source_configs()
    documented: dict[str, str] = {}
    for line in INTEGRATION_MATRIX.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7 or not re.fullmatch(r"[A-Z][A-Z_]+", cells[1]):
            continue
        documented[cells[1]] = cells[2]

    configured = {
        job.capability_operation: job.capability_channel.value
        for workflow in workflows.workflows
        for job in workflow.jobs
        if job.capability_operation is not None and job.capability_channel is not None
    }
    agent_operations = {
        operation for agent in agents.agents for operation in agent.provider_operations
    }

    assert not set(configured) - set(documented), "workflow operations missing from the matrix"
    assert not agent_operations - set(documented), "agent operations missing from the matrix"
    for operation, channel in configured.items():
        assert documented[operation] == channel, operation
