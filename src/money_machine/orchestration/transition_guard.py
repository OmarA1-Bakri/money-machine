"""Immutable lifecycle and durable-job transition tables."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final
from uuid import UUID

from money_machine.domain.enums import DecisionType, JobStatus, ProductLifecycleState
from money_machine.domain.errors import InvalidTransitionError
from money_machine.domain.events import EventName

PRODUCT_TRANSITIONS: Final[Mapping[ProductLifecycleState, frozenset[ProductLifecycleState]]] = (
    MappingProxyType(
        {
            ProductLifecycleState.DISCOVERED: frozenset({ProductLifecycleState.RESEARCHING}),
            ProductLifecycleState.RESEARCHING: frozenset({ProductLifecycleState.RESEARCH_COMPLETE}),
            ProductLifecycleState.RESEARCH_COMPLETE: frozenset({ProductLifecycleState.QUALIFYING}),
            ProductLifecycleState.QUALIFYING: frozenset(
                {ProductLifecycleState.QUALIFIED, ProductLifecycleState.REJECTED}
            ),
            ProductLifecycleState.QUALIFIED: frozenset({ProductLifecycleState.TEARDOWN_PENDING}),
            ProductLifecycleState.REJECTED: frozenset(),
            ProductLifecycleState.TEARDOWN_PENDING: frozenset(
                {ProductLifecycleState.TEARDOWN_COMPLETE}
            ),
            ProductLifecycleState.TEARDOWN_COMPLETE: frozenset({ProductLifecycleState.SPEC_READY}),
            ProductLifecycleState.SPEC_READY: frozenset({ProductLifecycleState.DEDUPE_CHECK}),
            ProductLifecycleState.DEDUPE_CHECK: frozenset(
                {ProductLifecycleState.RECONCEPTING, ProductLifecycleState.BUILDING}
            ),
            ProductLifecycleState.RECONCEPTING: frozenset({ProductLifecycleState.SPEC_READY}),
            ProductLifecycleState.BUILDING: frozenset({ProductLifecycleState.BUILD_QA}),
            ProductLifecycleState.BUILD_QA: frozenset(
                {ProductLifecycleState.BUILD_REPAIR, ProductLifecycleState.VARIANT_BUILD}
            ),
            ProductLifecycleState.BUILD_REPAIR: frozenset({ProductLifecycleState.BUILD_QA}),
            ProductLifecycleState.VARIANT_BUILD: frozenset({ProductLifecycleState.VARIANT_QA}),
            ProductLifecycleState.VARIANT_QA: frozenset(
                {ProductLifecycleState.VARIANT_BUILD, ProductLifecycleState.MERCHANDISING}
            ),
            ProductLifecycleState.MERCHANDISING: frozenset({ProductLifecycleState.ASSET_BUILD}),
            ProductLifecycleState.ASSET_BUILD: frozenset({ProductLifecycleState.ASSET_QA}),
            ProductLifecycleState.ASSET_QA: frozenset(
                {ProductLifecycleState.ASSET_BUILD, ProductLifecycleState.DRAFTING}
            ),
            ProductLifecycleState.DRAFTING: frozenset({ProductLifecycleState.DRAFT_READY}),
            ProductLifecycleState.DRAFT_READY: frozenset({ProductLifecycleState.PREFLIGHT}),
            ProductLifecycleState.PREFLIGHT: frozenset(
                {
                    ProductLifecycleState.LISTING_REPAIR,
                    ProductLifecycleState.READY_TO_PUBLISH,
                }
            ),
            ProductLifecycleState.LISTING_REPAIR: frozenset({ProductLifecycleState.PREFLIGHT}),
            ProductLifecycleState.READY_TO_PUBLISH: frozenset({ProductLifecycleState.PUBLISHED}),
            ProductLifecycleState.PUBLISHED: frozenset({ProductLifecycleState.POST_PUBLISH_QA}),
            ProductLifecycleState.POST_PUBLISH_QA: frozenset(
                {ProductLifecycleState.INCIDENT_REPAIR, ProductLifecycleState.OBSERVING}
            ),
            ProductLifecycleState.INCIDENT_REPAIR: frozenset(
                {ProductLifecycleState.POST_PUBLISH_QA}
            ),
            ProductLifecycleState.OBSERVING: frozenset({ProductLifecycleState.MATURE}),
            ProductLifecycleState.MATURE: frozenset({ProductLifecycleState.EVALUATING}),
            ProductLifecycleState.EVALUATING: frozenset(
                {
                    ProductLifecycleState.OBSERVING,
                    ProductLifecycleState.REPAIRING,
                    ProductLifecycleState.DEACTIVATING,
                    ProductLifecycleState.SUCCESSOR_SPEC,
                }
            ),
            ProductLifecycleState.REPAIRING: frozenset({ProductLifecycleState.OBSERVING}),
            ProductLifecycleState.DEACTIVATING: frozenset({ProductLifecycleState.DEACTIVATED}),
            ProductLifecycleState.DEACTIVATED: frozenset(),
            # MULTIPLY is a workflow boundary (D-0017): the winner returns to OBSERVING and a
            # NEW workflow starts at SUCCESSOR_WORKFLOW_ENTRY_STATE. There is deliberately no
            # same-workflow edge from SUCCESSOR_SPEC back into the build lifecycle.
            ProductLifecycleState.SUCCESSOR_SPEC: frozenset({ProductLifecycleState.OBSERVING}),
        }
    )
)

JOB_TRANSITIONS: Final[Mapping[JobStatus, frozenset[JobStatus]]] = MappingProxyType(
    {
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
    }
)

PRODUCT_TERMINAL_RESULTS: Final[Mapping[ProductLifecycleState, EventName]] = MappingProxyType(
    {
        ProductLifecycleState.REJECTED: EventName.PRODUCT_REJECTED,
        ProductLifecycleState.DEACTIVATED: EventName.LISTING_CULLED,
    }
)

JOB_TERMINAL_RESULTS: Final[Mapping[JobStatus, str]] = MappingProxyType(
    {
        JobStatus.SUCCEEDED: "success_contract",
        JobStatus.TERMINAL_FAILURE: "structured_error",
        JobStatus.CANCELLED: "cancellation_reason",
    }
)

PORTFOLIO_DECISION_PATHS: Final[Mapping[DecisionType, tuple[ProductLifecycleState, ...]]] = (
    MappingProxyType(
        {
            DecisionType.HOLD: (
                ProductLifecycleState.EVALUATING,
                ProductLifecycleState.OBSERVING,
            ),
            DecisionType.REPAIR: (
                ProductLifecycleState.EVALUATING,
                ProductLifecycleState.REPAIRING,
                ProductLifecycleState.OBSERVING,
            ),
            DecisionType.CULL: (
                ProductLifecycleState.EVALUATING,
                ProductLifecycleState.DEACTIVATING,
                ProductLifecycleState.DEACTIVATED,
            ),
            DecisionType.MULTIPLY: (
                ProductLifecycleState.EVALUATING,
                ProductLifecycleState.SUCCESSOR_SPEC,
                ProductLifecycleState.OBSERVING,
            ),
        }
    )
)

ORIGINAL_WORKFLOW_ENTRY_STATE: Final[ProductLifecycleState] = ProductLifecycleState.DISCOVERED
SUCCESSOR_WORKFLOW_ENTRY_STATE: Final[ProductLifecycleState] = ProductLifecycleState.DEDUPE_CHECK
"""A MULTIPLY successor begins at the dedupe gate in its own workflow (workbook §10, D-0017)."""

SUCCESSOR_SPAWN_SOURCE_STATE: Final[ProductLifecycleState] = ProductLifecycleState.SUCCESSOR_SPEC


def require_product_transition(
    source: ProductLifecycleState,
    target: ProductLifecycleState,
) -> None:
    """Reject any product transition absent from the canonical table."""
    if target not in PRODUCT_TRANSITIONS[source]:
        raise InvalidTransitionError(f"invalid product transition: {source} -> {target}")


def require_job_transition(source: JobStatus, target: JobStatus) -> None:
    """Reject any job transition absent from the canonical table."""
    if target not in JOB_TRANSITIONS[source]:
        raise InvalidTransitionError(f"invalid job transition: {source} -> {target}")


def require_successor_spawn(
    parent_state: ProductLifecycleState,
    parent_workflow_id: UUID,
    successor_workflow_id: UUID,
) -> ProductLifecycleState:
    """Authorize the cross-workflow MULTIPLY edge and return the successor's entry state.

    The parent must be in ``SUCCESSOR_SPEC`` and the successor must be a distinct workflow.
    The parent's own lifecycle never re-enters ``DEDUPE_CHECK``.
    """
    if parent_state is not SUCCESSOR_SPAWN_SOURCE_STATE:
        raise InvalidTransitionError(
            f"successor workflows spawn only from {SUCCESSOR_SPAWN_SOURCE_STATE}, "
            f"not {parent_state}"
        )
    if parent_workflow_id == successor_workflow_id:
        raise InvalidTransitionError(
            "successor workflow must differ from the parent workflow; "
            f"{SUCCESSOR_SPAWN_SOURCE_STATE} -> {SUCCESSOR_WORKFLOW_ENTRY_STATE} "
            "is not a same-workflow transition"
        )
    return SUCCESSOR_WORKFLOW_ENTRY_STATE
