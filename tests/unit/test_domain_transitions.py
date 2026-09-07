from __future__ import annotations

from itertools import pairwise
from uuid import uuid4

import pytest

from money_machine.domain.enums import (
    AgentRunStatus,
    AutonomyMode,
    BranchOutcome,
    CapabilityChannel,
    DecisionType,
    IncidentType,
    JobStatus,
    ProductLifecycleState,
    RetryClass,
    SideEffectClass,
)
from money_machine.domain.errors import InvalidTransitionError
from money_machine.domain.events import EventName
from money_machine.orchestration.transition_guard import (
    JOB_TERMINAL_RESULTS,
    JOB_TRANSITIONS,
    PORTFOLIO_DECISION_PATHS,
    PRODUCT_TERMINAL_RESULTS,
    PRODUCT_TRANSITIONS,
    SUCCESSOR_WORKFLOW_ENTRY_STATE,
    require_job_transition,
    require_product_transition,
    require_successor_spawn,
)


def enum_values(enum_type: type[object]) -> set[str]:
    return {str(member) for member in enum_type}  # type: ignore[call-overload]


def assert_valid_product_path(path: tuple[ProductLifecycleState, ...]) -> None:
    for source, target in pairwise(path):
        require_product_transition(source, target)


def test_product_lifecycle_enum_matches_the_documented_state_machine() -> None:
    assert enum_values(ProductLifecycleState) == {
        "DISCOVERED",
        "RESEARCHING",
        "RESEARCH_COMPLETE",
        "QUALIFYING",
        "QUALIFIED",
        "REJECTED",
        "TEARDOWN_PENDING",
        "TEARDOWN_COMPLETE",
        "SPEC_READY",
        "DEDUPE_CHECK",
        "RECONCEPTING",
        "BUILDING",
        "BUILD_QA",
        "BUILD_REPAIR",
        "VARIANT_BUILD",
        "VARIANT_QA",
        "MERCHANDISING",
        "ASSET_BUILD",
        "ASSET_QA",
        "DRAFTING",
        "DRAFT_READY",
        "PREFLIGHT",
        "LISTING_REPAIR",
        "READY_TO_PUBLISH",
        "PUBLISHED",
        "POST_PUBLISH_QA",
        "INCIDENT_REPAIR",
        "OBSERVING",
        "MATURE",
        "EVALUATING",
        "REPAIRING",
        "DEACTIVATING",
        "DEACTIVATED",
        "SUCCESSOR_SPEC",
    }


def test_every_documented_product_transition_is_executable() -> None:
    documented_edges = {
        (ProductLifecycleState.DISCOVERED, ProductLifecycleState.RESEARCHING),
        (ProductLifecycleState.RESEARCHING, ProductLifecycleState.RESEARCH_COMPLETE),
        (ProductLifecycleState.RESEARCH_COMPLETE, ProductLifecycleState.QUALIFYING),
        (ProductLifecycleState.QUALIFYING, ProductLifecycleState.QUALIFIED),
        (ProductLifecycleState.QUALIFYING, ProductLifecycleState.REJECTED),
        (ProductLifecycleState.QUALIFIED, ProductLifecycleState.TEARDOWN_PENDING),
        (ProductLifecycleState.TEARDOWN_PENDING, ProductLifecycleState.TEARDOWN_COMPLETE),
        (ProductLifecycleState.TEARDOWN_COMPLETE, ProductLifecycleState.SPEC_READY),
        (ProductLifecycleState.SPEC_READY, ProductLifecycleState.DEDUPE_CHECK),
        (ProductLifecycleState.DEDUPE_CHECK, ProductLifecycleState.RECONCEPTING),
        (ProductLifecycleState.RECONCEPTING, ProductLifecycleState.SPEC_READY),
        (ProductLifecycleState.DEDUPE_CHECK, ProductLifecycleState.BUILDING),
        (ProductLifecycleState.BUILDING, ProductLifecycleState.BUILD_QA),
        (ProductLifecycleState.BUILD_QA, ProductLifecycleState.BUILD_REPAIR),
        (ProductLifecycleState.BUILD_REPAIR, ProductLifecycleState.BUILD_QA),
        (ProductLifecycleState.BUILD_QA, ProductLifecycleState.VARIANT_BUILD),
        (ProductLifecycleState.VARIANT_BUILD, ProductLifecycleState.VARIANT_QA),
        (ProductLifecycleState.VARIANT_QA, ProductLifecycleState.VARIANT_BUILD),
        (ProductLifecycleState.VARIANT_QA, ProductLifecycleState.MERCHANDISING),
        (ProductLifecycleState.MERCHANDISING, ProductLifecycleState.ASSET_BUILD),
        (ProductLifecycleState.ASSET_BUILD, ProductLifecycleState.ASSET_QA),
        (ProductLifecycleState.ASSET_QA, ProductLifecycleState.ASSET_BUILD),
        (ProductLifecycleState.ASSET_QA, ProductLifecycleState.DRAFTING),
        (ProductLifecycleState.DRAFTING, ProductLifecycleState.DRAFT_READY),
        (ProductLifecycleState.DRAFT_READY, ProductLifecycleState.PREFLIGHT),
        (ProductLifecycleState.PREFLIGHT, ProductLifecycleState.LISTING_REPAIR),
        (ProductLifecycleState.LISTING_REPAIR, ProductLifecycleState.PREFLIGHT),
        (ProductLifecycleState.PREFLIGHT, ProductLifecycleState.READY_TO_PUBLISH),
        (ProductLifecycleState.READY_TO_PUBLISH, ProductLifecycleState.PUBLISHED),
        (ProductLifecycleState.PUBLISHED, ProductLifecycleState.POST_PUBLISH_QA),
        (ProductLifecycleState.POST_PUBLISH_QA, ProductLifecycleState.INCIDENT_REPAIR),
        (ProductLifecycleState.INCIDENT_REPAIR, ProductLifecycleState.POST_PUBLISH_QA),
        (ProductLifecycleState.POST_PUBLISH_QA, ProductLifecycleState.OBSERVING),
        (ProductLifecycleState.OBSERVING, ProductLifecycleState.MATURE),
        (ProductLifecycleState.MATURE, ProductLifecycleState.EVALUATING),
        (ProductLifecycleState.EVALUATING, ProductLifecycleState.OBSERVING),
        (ProductLifecycleState.EVALUATING, ProductLifecycleState.REPAIRING),
        (ProductLifecycleState.REPAIRING, ProductLifecycleState.OBSERVING),
        (ProductLifecycleState.EVALUATING, ProductLifecycleState.DEACTIVATING),
        (ProductLifecycleState.DEACTIVATING, ProductLifecycleState.DEACTIVATED),
        (ProductLifecycleState.EVALUATING, ProductLifecycleState.SUCCESSOR_SPEC),
        (ProductLifecycleState.SUCCESSOR_SPEC, ProductLifecycleState.OBSERVING),
    }
    executable_edges = {
        (source, target) for source, targets in PRODUCT_TRANSITIONS.items() for target in targets
    }

    assert executable_edges == documented_edges


def test_every_undocumented_product_transition_fails_closed() -> None:
    """Exhaustive: every (source, target) pair absent from the table is rejected."""
    rejected = 0
    for source in ProductLifecycleState:
        for target in ProductLifecycleState:
            if target in PRODUCT_TRANSITIONS[source]:
                require_product_transition(source, target)
                continue
            with pytest.raises(InvalidTransitionError, match=f"{source}.*{target}"):
                require_product_transition(source, target)
            rejected += 1
    edge_count = sum(len(targets) for targets in PRODUCT_TRANSITIONS.values())
    assert rejected == len(ProductLifecycleState) ** 2 - edge_count
    assert rejected > edge_count


def test_every_undocumented_job_transition_fails_closed() -> None:
    for source in JobStatus:
        for target in JobStatus:
            if target in JOB_TRANSITIONS[source]:
                require_job_transition(source, target)
            else:
                with pytest.raises(InvalidTransitionError, match=f"{source}.*{target}"):
                    require_job_transition(source, target)


def test_terminal_results_are_derived_from_the_transition_tables() -> None:
    product_terminals = {state for state, targets in PRODUCT_TRANSITIONS.items() if not targets}
    assert product_terminals == set(PRODUCT_TERMINAL_RESULTS)
    job_terminals = {status for status, targets in JOB_TRANSITIONS.items() if not targets}
    assert job_terminals == set(JOB_TERMINAL_RESULTS)
    assert set(PRODUCT_TRANSITIONS) == set(ProductLifecycleState)
    assert set(JOB_TRANSITIONS) == set(JobStatus)


def test_job_state_machine_is_exact_and_impossible_restarts_fail() -> None:
    assert {
        JobStatus.PENDING: frozenset({JobStatus.BLOCKED, JobStatus.READY, JobStatus.CANCELLED}),
        JobStatus.BLOCKED: frozenset({JobStatus.READY, JobStatus.CANCELLED}),
        JobStatus.READY: frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
        JobStatus.RUNNING: frozenset(
            {
                JobStatus.SUCCEEDED,
                JobStatus.FAILED,
                JobStatus.BLOCKED,
                JobStatus.UNCERTAIN_EXTERNAL_EFFECT,
            }
        ),
        JobStatus.FAILED: frozenset({JobStatus.READY, JobStatus.TERMINAL_FAILURE}),
        JobStatus.UNCERTAIN_EXTERNAL_EFFECT: frozenset(
            {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.BLOCKED}
        ),
        JobStatus.SUCCEEDED: frozenset(),
        JobStatus.TERMINAL_FAILURE: frozenset(),
        JobStatus.CANCELLED: frozenset(),
    } == JOB_TRANSITIONS

    with pytest.raises(InvalidTransitionError, match=r"SUCCEEDED.*RUNNING"):
        require_job_transition(JobStatus.SUCCEEDED, JobStatus.RUNNING)
    with pytest.raises(InvalidTransitionError, match=r"UNCERTAIN_EXTERNAL_EFFECT.*READY"):
        require_job_transition(JobStatus.UNCERTAIN_EXTERNAL_EFFECT, JobStatus.READY)


def test_every_terminal_branch_has_a_defined_durable_result() -> None:
    assert {
        ProductLifecycleState.REJECTED: EventName.PRODUCT_REJECTED,
        ProductLifecycleState.DEACTIVATED: EventName.LISTING_CULLED,
    } == PRODUCT_TERMINAL_RESULTS
    assert {
        JobStatus.SUCCEEDED: "success_contract",
        JobStatus.TERMINAL_FAILURE: "structured_error",
        JobStatus.CANCELLED: "cancellation_reason",
    } == JOB_TERMINAL_RESULTS
    assert enum_values(AgentRunStatus) == {
        "SUCCESS",
        "FAILURE",
        "BLOCKED",
        "UNCERTAIN_EXTERNAL_EFFECT",
    }


def test_cull_reaches_deactivation_and_multiply_reaches_a_successor_workflow() -> None:
    cull_path = PORTFOLIO_DECISION_PATHS[DecisionType.CULL]
    multiply_path = PORTFOLIO_DECISION_PATHS[DecisionType.MULTIPLY]

    assert_valid_product_path(cull_path)
    assert cull_path[-1] is ProductLifecycleState.DEACTIVATED
    assert_valid_product_path(multiply_path)
    assert ProductLifecycleState.SUCCESSOR_SPEC in multiply_path
    assert multiply_path[-1] is ProductLifecycleState.OBSERVING

    parent_workflow = uuid4()
    entry = require_successor_spawn(ProductLifecycleState.SUCCESSOR_SPEC, parent_workflow, uuid4())
    assert entry is SUCCESSOR_WORKFLOW_ENTRY_STATE is ProductLifecycleState.DEDUPE_CHECK
    assert ProductLifecycleState.BUILDING in PRODUCT_TRANSITIONS[entry]


def test_multiply_never_re_enters_dedupe_on_the_winner_workflow() -> None:
    with pytest.raises(InvalidTransitionError, match=r"SUCCESSOR_SPEC.*DEDUPE_CHECK"):
        require_product_transition(
            ProductLifecycleState.SUCCESSOR_SPEC,
            ProductLifecycleState.DEDUPE_CHECK,
        )
    same_workflow = uuid4()
    with pytest.raises(InvalidTransitionError, match="must differ from the parent workflow"):
        require_successor_spawn(ProductLifecycleState.SUCCESSOR_SPEC, same_workflow, same_workflow)
    with pytest.raises(InvalidTransitionError, match="spawn only from SUCCESSOR_SPEC"):
        require_successor_spawn(ProductLifecycleState.OBSERVING, uuid4(), uuid4())


def test_non_lifecycle_taxonomies_are_separate_and_complete() -> None:
    assert enum_values(BranchOutcome) == {"PASS", "FAIL", "TOO_CLOSE"}
    assert enum_values(DecisionType) == {"HOLD", "REPAIR", "CULL", "MULTIPLY"}
    assert enum_values(SideEffectClass) == {
        "NONE",
        "EXTERNAL_READ",
        "EXTERNAL_WRITE",
        "EXTERNAL_SPEND",
        "EXTERNAL_MESSAGE",
    }
    assert enum_values(RetryClass) == {
        "SAFE",
        "IDEMPOTENT",
        "RECONCILE_FIRST",
        "MANUAL_RESUME",
        "NEVER",
    }
    assert enum_values(AutonomyMode) == {"simulation", "draft", "live"}
    assert enum_values(CapabilityChannel) == {
        "DIRECT_API",
        "COMPOSIO",
        "BROWSER",
        "INTERNAL_RENDERER",
        "MANUAL_EXTERNAL_BLOCKER",
    }
    assert {
        IncidentType.BROKEN_LINK,
        IncidentType.CUSTOMER_ISSUE,
        IncidentType.BUILD_DEFECT,
        IncidentType.LISTING_DEFECT,
        IncidentType.CREDENTIAL_FAILURE,
        IncidentType.PROVIDER_MISMATCH,
        IncidentType.TERMINAL_JOB_FAILURE,
        IncidentType.UNCERTAIN_EXTERNAL_EFFECT,
    } == set(IncidentType)


def test_event_enum_contains_the_canonical_catalogue() -> None:
    assert enum_values(EventName) == {
        "ACCOUNT_CONNECTED",
        "RESEARCH_COMPLETED",
        "NICHE_SHORTLISTED",
        "PRODUCT_QUALIFIED",
        "PRODUCT_REJECTED",
        "TEARDOWN_COMPLETED",
        "PRODUCT_SPEC_CREATED",
        "DEDUPE_PASSED",
        "DEDUPE_FAILED",
        "BUILD_COMPLETED",
        "BUILD_QA_PASSED",
        "BUILD_QA_FAILED",
        "VARIANTS_COMPLETED",
        "ASSETS_COMPLETED",
        "DRAFT_CREATED",
        "PREFLIGHT_PASSED",
        "PREFLIGHT_FAILED",
        "LISTING_PUBLISHED",
        "POST_PUBLISH_VERIFIED",
        "METRICS_CAPTURED",
        "LISTING_MATURED",
        "LISTING_HELD",
        "LISTING_REPAIR_REQUESTED",
        "LISTING_CULLED",
        "WINNER_DETECTED",
        "SUCCESSOR_CREATED",
        "CUSTOMER_ISSUE_RECEIVED",
        "BROKEN_LINK_DETECTED",
        "REPAIR_COMPLETED",
        "JOB_FAILED",
        "JOB_STALLED",
        "CREDENTIAL_REQUIRED",
        "ENVIRONMENT_AUDITED",
        "SHOP_BOOTSTRAPPED",
        "NICHE_SELECTED",
        "COMPETITOR_PURCHASED",
        "VARIANT_LINKS_VERIFIED",
        "SCREENSHOTS_CAPTURED",
        "LISTING_COPY_COMPLETED",
        "DELIVERY_FILES_COMPLETED",
        "PRICING_COMPLETED",
        "PROOF_FEEDBACK_CAPTURED",
        "SCHEDULE_CONFIGURED",
        "BUILD_SLOT_DEFERRED",
        "MONTHLY_REVIEW_COMPLETED",
        "SCALE_DECIDED",
        "LISTING_CULL_REQUESTED",
        "REPAIR_APPLIED",
    }
