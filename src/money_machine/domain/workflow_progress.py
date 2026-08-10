"""Typed durable progress contract for the first-product workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from money_machine.domain.enums import ProductState
from money_machine.domain.events import DomainEventName
from money_machine.domain.value_objects import assert_product_transition


@dataclass(frozen=True, slots=True)
class WorkflowProgressContract:
    """One exact job/event pair and its durable workflow state change."""

    event: DomainEventName
    current: ProductState
    target: ProductState


FIRST_PRODUCT_WORKFLOW_PROGRESS: Final[Mapping[str, WorkflowProgressContract]] = MappingProxyType(
    {
        "ADMIT_RESEARCH_PACKET": WorkflowProgressContract(
            DomainEventName.RESEARCH_PACKET_ADMITTED,
            ProductState.RESEARCHED,
            ProductState.RESEARCHED,
        ),
        "QUALIFY_CANDIDATES": WorkflowProgressContract(
            DomainEventName.CANDIDATE_SHORTLISTED,
            ProductState.RESEARCHED,
            ProductState.QUALIFIED,
        ),
        "CREATE_PRODUCT_SPEC": WorkflowProgressContract(
            DomainEventName.PRODUCT_SPEC_CREATED,
            ProductState.QUALIFIED,
            ProductState.SPECIFIED,
        ),
        "CHECK_CATALOGUE_DEDUPE": WorkflowProgressContract(
            DomainEventName.DEDUPE_PASSED,
            ProductState.SPECIFIED,
            ProductState.DEDUPE_PASSED,
        ),
        "BUILD_PRODUCT": WorkflowProgressContract(
            DomainEventName.PRODUCT_BUILT,
            ProductState.DEDUPE_PASSED,
            ProductState.BUILT,
        ),
        "RUN_PRODUCT_QA": WorkflowProgressContract(
            DomainEventName.PRODUCT_QA_PASSED,
            ProductState.BUILT,
            ProductState.QA_PASSED,
        ),
        "CREATE_LISTING_PACKAGE": WorkflowProgressContract(
            DomainEventName.LISTING_PACKAGE_CREATED,
            ProductState.QA_PASSED,
            ProductState.MERCHANDISED,
        ),
        "RUN_PREFLIGHT": WorkflowProgressContract(
            DomainEventName.DRAFT_READY,
            ProductState.MERCHANDISED,
            ProductState.DRAFT_READY,
        ),
    }
)

_ADVERSE_TERMINAL_EVENTS: Final[Mapping[ProductState, DomainEventName]] = MappingProxyType(
    {
        ProductState.INSUFFICIENT_EVIDENCE: DomainEventName.INSUFFICIENT_EVIDENCE,
        ProductState.REJECTED: DomainEventName.WORKFLOW_REJECTED,
        ProductState.FAILED: DomainEventName.WORKFLOW_FAILED,
    }
)

_BUSINESS_TERMINALS: Final[Mapping[str, ProductState]] = MappingProxyType(
    {
        "QUALIFY_CANDIDATES": ProductState.INSUFFICIENT_EVIDENCE,
        "CHECK_CATALOGUE_DEDUPE": ProductState.REJECTED,
        "RUN_PRODUCT_QA": ProductState.REJECTED,
        "RUN_PREFLIGHT": ProductState.REJECTED,
    }
)


def next_product_state(
    job_type: str,
    current: ProductState,
    event: DomainEventName,
) -> ProductState:
    """Return the only state authorized by an exact job/event completion."""

    contract = FIRST_PRODUCT_WORKFLOW_PROGRESS.get(job_type)
    if contract is None or contract.event is not event or contract.current is not current:
        raise ValueError(f"workflow event/state mismatch: {job_type} {current.value} {event.value}")

    if contract.target is ProductState.DRAFT_READY:
        assert_product_transition(current, ProductState.PREFLIGHT_PASSED)
        assert_product_transition(ProductState.PREFLIGHT_PASSED, contract.target)
    elif contract.target is not current:
        assert_product_transition(current, contract.target)
    return contract.target


def terminal_event_name(state: ProductState) -> DomainEventName:
    """Return the exact event reserved for one adverse terminal state."""

    event = _ADVERSE_TERMINAL_EVENTS.get(state)
    if event is None:
        raise ValueError(f"state is not an adverse terminal: {state.value}")
    return event


def terminal_product_state(
    job_type: str,
    current: ProductState,
    target: ProductState,
) -> ProductState:
    """Authorize only an exact business terminal or technical failure transition."""

    progress = FIRST_PRODUCT_WORKFLOW_PROGRESS.get(job_type)
    business_target = _BUSINESS_TERMINALS.get(job_type)
    authorized = (
        progress is not None
        and progress.current is current
        and (target is ProductState.FAILED or business_target is target)
    )
    if not authorized:
        raise ValueError(f"workflow terminal mismatch: {job_type} {current.value} {target.value}")
    assert_product_transition(current, target)
    return target
