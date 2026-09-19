"""Unit tests for Action 7: prove workflow templates/job specs loadable from YAML.

Workbook Action 7 requirement: within Exit 78 library scope, prove that named
workflow job types and their configurations are resolvable from workflows.yaml.
The canonical workflow authority is config/workflows.yaml (ProductLifecycleWorkflow).
"""

from money_machine.orchestration.successor_factory import load_workflows_config


class TestWorkflowConfigLoadable:
    """Test that workflow configuration is loadable and contains expected job types."""

    def test_workflows_yaml_loads_successfully(self) -> None:
        """workflows.yaml loads and parses into WorkflowsConfig model."""
        _event_map, workflows_config = load_workflows_config()

        assert workflows_config.version == 1
        assert len(workflows_config.workflows) >= 1
        assert workflows_config.workflows[0].workflow_type == "ProductLifecycleWorkflow"

    def test_workflow_contains_job_definitions(self) -> None:
        """ProductLifecycleWorkflow contains job definitions with specs."""
        _event_map, workflows_config = load_workflows_config()

        workflow = workflows_config.workflows[0]
        assert len(workflow.jobs) > 0

        # Verify first job has required fields
        job = workflow.jobs[0]
        assert hasattr(job, "job_type")
        assert hasattr(job, "owner_agent_id")
        assert hasattr(job, "side_effect_class")
        assert hasattr(job, "retry_class")

    def test_named_job_types_resolvable(self) -> None:
        """Named job types from workbook templates are resolvable from YAML.

        Workbook Action 7 mentions conceptual groupings:
        - product_experiment: ResearchCollectionJob, QualificationJob, DedupeJob
        - competitor_teardown: CompetitorPurchaseJob, TeardownJob
        - publish_listing: DraftListingJob, PreflightJob, PublishListingJob
        - weekly_review: WeeklyReviewJob
        - monthly_deep_pass: MonthlyDeepPassJob
        - incident_repair: IncidentRepairJob
        """
        _event_map, workflows_config = load_workflows_config()

        workflow = workflows_config.workflows[0]
        job_types = {job.job_type for job in workflow.jobs}

        # Verify named job types from workbook templates exist
        expected_types = {
            "ResearchCollectionJob",
            "QualificationJob",
            "DedupeJob",
            "CompetitorPurchaseJob",
            "TeardownJob",
            "DraftListingJob",
            "PreflightJob",
            "PublishListingJob",
            "WeeklyReviewJob",
            "MonthlyDeepPassJob",
            "IncidentRepairJob",
        }

        assert expected_types.issubset(job_types), (
            f"Missing job types: {expected_types - job_types}"
        )

    def test_job_specs_have_complete_metadata(self) -> None:
        """Job specs contain all required metadata fields."""
        _event_map, workflows_config = load_workflows_config()

        workflow = workflows_config.workflows[0]

        # Check a few key jobs have complete specs
        research_job = next(j for j in workflow.jobs if j.job_type == "ResearchCollectionJob")
        assert research_job.owner_agent_id == "A03"
        assert research_job.side_effect_class in ["NONE", "EXTERNAL_READ", "EXTERNAL_WRITE", "EXTERNAL_SPEND", "EXTERNAL_MESSAGE"]
        assert research_job.retry_class in ["SAFE", "IDEMPOTENT", "RECONCILE_FIRST", "MANUAL_RESUME"]
        assert len(research_job.allowed_modes) > 0
        assert len(research_job.output_contracts) > 0
        assert len(research_job.admitted_events) > 0

    def test_entry_job_types_defined(self) -> None:
        """Workflow defines entry job types."""
        _event_map, workflows_config = load_workflows_config()

        workflow = workflows_config.workflows[0]
        assert len(workflow.entry_job_types) > 0
        assert "ProvisioningCheckJob" in workflow.entry_job_types or "ScheduleConfigurationJob" in workflow.entry_job_types
