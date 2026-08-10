"""Typed durable progress contract for the first-product workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from money_machine.domain.enums import ProductState
from money_machine.domain.events import DomainEventName
from money_machine.domain.models.candidate import CandidateShortlist
from money_machine.domain.models.listing import PreflightResult
from money_machine.domain.models.product import ProductQAResult
from money_machine.domain.models.product_spec import DedupeResult
from money_machine.domain.value_objects import FrozenModel, assert_product_transition


@dataclass(frozen=True, slots=True)
class WorkflowProgressContract:
    """One exact job/event pair and its durable workflow state change."""

    event: DomainEventName
    current: ProductState
    target: ProductState


@dataclass(frozen=True, slots=True)
class TerminalOutputContract:
    """Exact result table and validated model for one business terminal."""

    result_type: str
    result_model: type[FrozenModel]


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

FIRST_PRODUCT_TERMINAL_OUTPUTS: Final[Mapping[tuple[str, ProductState], TerminalOutputContract]] = (
    MappingProxyType(
        {
            ("QUALIFY_CANDIDATES", ProductState.INSUFFICIENT_EVIDENCE): TerminalOutputContract(
                "candidate_shortlists",
                CandidateShortlist,
            ),
            ("CHECK_CATALOGUE_DEDUPE", ProductState.REJECTED): TerminalOutputContract(
                "dedupe_results",
                DedupeResult,
            ),
            ("RUN_PRODUCT_QA", ProductState.REJECTED): TerminalOutputContract(
                "product_qa_results",
                ProductQAResult,
            ),
            ("RUN_PREFLIGHT", ProductState.REJECTED): TerminalOutputContract(
                "preflight_results",
                PreflightResult,
            ),
        }
    )
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


def validate_terminal_result(
    job_type: str,
    terminal_state: ProductState,
    result_type: str | None,
    result: FrozenModel | None,
) -> None:
    """Reject terminal results that differ from the durable job's exact contract."""

    if terminal_state is ProductState.FAILED:
        if result_type is not None or result is not None:
            raise ValueError("FAILED terminal result contract mismatch")
        return

    contract = FIRST_PRODUCT_TERMINAL_OUTPUTS.get((job_type, terminal_state))
    if (
        contract is None
        or result_type != contract.result_type
        or result is None
        or type(result) is not contract.result_model
    ):
        raise ValueError(f"terminal result contract mismatch for {job_type}")
    try:
        contract.result_model.model_validate(result.model_dump(mode="python"))
    except ValueError as exc:
        raise ValueError(f"terminal result model invalid for {job_type}") from exc
