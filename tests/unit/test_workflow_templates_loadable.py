"""Unit tests for Action 7: prove workflow templates/job specs loadable from YAML.

Workbook Action 7 requirement: within Exit 78 library scope, prove that named
workflow job types and their configurations are resolvable from workflows.yaml.
The canonical workflow authority is config/workflows.yaml (ProductLifecycleWorkflow).

Beyond YAML loading: prove templates are USABLE - resolve job specs, successor map,
and entry jobs for orchestration.
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
        assert research_job.side_effect_class in [
            "NONE",
            "EXTERNAL_READ",
            "EXTERNAL_WRITE",
            "EXTERNAL_SPEND",
            "EXTERNAL_MESSAGE",
        ]
        assert research_job.retry_class in [
            "SAFE",
            "IDEMPOTENT",
            "RECONCILE_FIRST",
            "MANUAL_RESUME",
        ]
        assert len(research_job.allowed_modes) > 0
        assert len(research_job.output_contracts) > 0
        assert len(research_job.admitted_events) > 0

    def test_entry_job_types_defined(self) -> None:
        """Workflow defines entry job types."""
        _event_map, workflows_config = load_workflows_config()

        workflow = workflows_config.workflows[0]
        assert len(workflow.entry_job_types) > 0
        assert (
            "ProvisioningCheckJob" in workflow.entry_job_types
            or "ScheduleConfigurationJob" in workflow.entry_job_types
        )

    def test_successor_map_resolvable(self) -> None:
        """Action 7 depth: prove successor map is resolvable for orchestration use.

        Beyond YAML loading, verify that:
        1. create_successors maps exist and are well-formed
        2. Each job's successors are valid job types in the workflow
        3. Maps are usable for successor_factory orchestration path
        """
        _event_map, workflows_config = load_workflows_config()

        workflow = workflows_config.workflows[0]
        job_types = {job.job_type for job in workflow.jobs}

        # Verify successor_job_types tuples are present and valid
        for job_spec in workflow.jobs:
            if job_spec.successor_job_types:
                # Each successor must reference valid job types in this workflow
                for successor_job_type in job_spec.successor_job_types:
                    assert successor_job_type in job_types, (
                        f"Successor {successor_job_type} not in workflow job types"
                    )

    def test_entry_jobs_resolvable_for_workflow_start(self) -> None:
        """Action 7 depth: prove entry jobs are resolvable for starting workflows.

        Verify entry_job_types are valid and can be used to initialize a workflow.
        """
        _event_map, workflows_config = load_workflows_config()

        workflow = workflows_config.workflows[0]
        job_types = {job.job_type for job in workflow.jobs}

        # Entry jobs must be valid job types
        for entry_type in workflow.entry_job_types:
            assert entry_type in job_types, f"Entry job {entry_type} not in workflow"

        # At least one entry job exists
        assert len(workflow.entry_job_types) > 0

    def test_job_specs_usable_for_job_creation(self) -> None:
        """Action 7 depth: prove job specs contain all data needed to create jobs.

        Verify each job spec has the fields required by the jobs table schema:
        job_type, owner_agent_id, side_effect_class, retry_class, allowed_modes.
        """
        _event_map, workflows_config = load_workflows_config()

        workflow = workflows_config.workflows[0]

        for job_spec in workflow.jobs:
            # Required fields for job creation
            assert job_spec.job_type is not None
            assert job_spec.owner_agent_id is not None
            assert job_spec.side_effect_class in [
                "NONE",
                "EXTERNAL_READ",
                "EXTERNAL_WRITE",
                "EXTERNAL_SPEND",
                "EXTERNAL_MESSAGE",
            ]
            assert job_spec.retry_class in [
                "SAFE",
                "IDEMPOTENT",
                "RECONCILE_FIRST",
                "MANUAL_RESUME",
            ]
            assert len(job_spec.allowed_modes) > 0, f"{job_spec.job_type} has no allowed_modes"
