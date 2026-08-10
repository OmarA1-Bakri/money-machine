"""Typed adverse terminal outcomes for the first-product workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from money_machine.domain.enums import ProductState
from money_machine.domain.events import DomainEventName
from money_machine.domain.models.candidate import CandidateShortlist, QualificationScore
from money_machine.domain.models.listing import PreflightResult
from money_machine.domain.models.product import ProductQAResult
from money_machine.domain.models.product_spec import DedupeResult
from money_machine.domain.models.workflow import WorkflowBlocker, WorkflowRun
from money_machine.domain.value_objects import FrozenModel
from money_machine.domain.workflow_progress import (
    terminal_event_name,
    terminal_product_state,
    validate_terminal_result,
)

NOW = datetime(2026, 8, 10, tzinfo=UTC)


def _blocker(state: ProductState = ProductState.REJECTED) -> WorkflowBlocker:
    return WorkflowBlocker(
        blocker_id="BLK-test",
        job_id=UUID("00000000-0000-0000-0000-000000000301"),
        terminal_state=state,
        code="CATALOGUE_DUPLICATE",
        message="The product specification matches an existing catalogue item.",
        result_type="dedupe_results",
        result_id="DDR-test",
        result_sha256="a" * 64,
        occurred_at=NOW,
    )


def _workflow(
    state: ProductState,
    blocker: WorkflowBlocker | None,
) -> WorkflowRun:
    return WorkflowRun(
        workflow_run_id=UUID("00000000-0000-0000-0000-000000000302"),
        workflow_type="FIRST_PRODUCT_VERTICAL_SLICE",
        packet_id="RPK-blocker",
        state=state,
        idempotency_key="workflow:RPK-blocker",
        terminal_blocker=blocker,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.parametrize(
    ("state", "event"),
    [
        (ProductState.INSUFFICIENT_EVIDENCE, DomainEventName.INSUFFICIENT_EVIDENCE),
        (ProductState.REJECTED, DomainEventName.WORKFLOW_REJECTED),
        (ProductState.FAILED, DomainEventName.WORKFLOW_FAILED),
    ],
)
def test_adverse_terminal_states_have_exact_events(
    state: ProductState,
    event: DomainEventName,
) -> None:
    assert terminal_event_name(state) is event


def test_terminal_blocker_requires_adverse_state_and_complete_result_identity() -> None:
    with pytest.raises(ValidationError, match="adverse terminal state"):
        _blocker(ProductState.DRAFT_READY)
    with pytest.raises(ValidationError, match="result identity fields"):
        WorkflowBlocker.model_validate({**_blocker().model_dump(mode="python"), "result_id": None})


def test_workflow_requires_matching_blocker_only_for_adverse_terminal_state() -> None:
    blocker = _blocker()
    assert _workflow(ProductState.REJECTED, blocker).terminal_blocker == blocker
    with pytest.raises(ValidationError, match="requires terminal_blocker"):
        _workflow(ProductState.REJECTED, None)
    with pytest.raises(ValidationError, match="only valid for an adverse terminal state"):
        _workflow(ProductState.SPECIFIED, blocker)
    with pytest.raises(ValidationError, match="must match workflow state"):
        _workflow(ProductState.FAILED, blocker)


def test_workflow_revalidates_nested_blocker_instances_before_persistence() -> None:
    forged = _blocker().model_copy(update={"code": ""})
    with pytest.raises(ValidationError, match="at least 1 character"):
        _workflow(ProductState.REJECTED, forged)


@pytest.mark.parametrize(
    ("job_type", "state", "result_type", "result"),
    [
        (
            "QUALIFY_CANDIDATES",
            ProductState.INSUFFICIENT_EVIDENCE,
            "candidate_shortlists",
            CandidateShortlist(
                shortlist_id="CS-qualifying",
                packet_id="RPK-qualifying",
                candidates=(
                    QualificationScore(
                        candidate_id="candidate-qualifying",
                        demand=8,
                        differentiation=8,
                        build_feasibility=7,
                        buyer_value=7,
                        evidence_ids=("EV-qualifying",),
                    ),
                ),
                selected_candidate_id="candidate-qualifying",
                backup_candidate_id=None,
                shortlist_sha256="b" * 64,
            ),
        ),
        (
            "CHECK_CATALOGUE_DEDUPE",
            ProductState.REJECTED,
            "dedupe_results",
            DedupeResult(
                dedupe_result_id="DDR-passing",
                product_spec_id="PS-passing",
                passed=True,
                matched_product_spec_ids=(),
                reasons=(),
                result_sha256="c" * 64,
            ),
        ),
        (
            "RUN_PRODUCT_QA",
            ProductState.REJECTED,
            "product_qa_results",
            ProductQAResult(
                qa_result_id="PQA-passing",
                build_id="BLD-passing",
                passed=True,
                findings=(),
                checked_at=NOW,
                result_sha256="d" * 64,
            ),
        ),
        (
            "RUN_PREFLIGHT",
            ProductState.REJECTED,
            "preflight_results",
            PreflightResult(
                preflight_result_id="PFR-passing",
                listing_package_id="LP-passing",
                passed=True,
                findings=(),
                checked_at=NOW,
                external_effect_mode="draft",
                incremental_spend=Decimal("0.00"),
                publication_receipt_present=False,
                result_sha256="e" * 64,
            ),
        ),
    ],
)
def test_adverse_terminal_rejects_semantically_successful_result(
    job_type: str,
    state: ProductState,
    result_type: str,
    result: FrozenModel,
) -> None:
    with pytest.raises(ValueError, match="terminal result semantic mismatch"):
        validate_terminal_result(job_type, state, result_type, result)


@pytest.mark.parametrize(
    ("job_type", "current", "target"),
    [
        (
            "QUALIFY_CANDIDATES",
            ProductState.RESEARCHED,
            ProductState.INSUFFICIENT_EVIDENCE,
        ),
        ("CHECK_CATALOGUE_DEDUPE", ProductState.SPECIFIED, ProductState.REJECTED),
        ("RUN_PRODUCT_QA", ProductState.BUILT, ProductState.REJECTED),
        ("RUN_PREFLIGHT", ProductState.MERCHANDISED, ProductState.REJECTED),
        ("BUILD_PRODUCT", ProductState.DEDUPE_PASSED, ProductState.FAILED),
    ],
)
def test_only_declared_job_and_state_can_enter_an_adverse_terminal(
    job_type: str,
    current: ProductState,
    target: ProductState,
) -> None:
    assert terminal_product_state(job_type, current, target) is target

    with pytest.raises(ValueError, match="workflow terminal mismatch"):
        terminal_product_state(job_type, ProductState.DRAFT_READY, target)


def test_business_rejection_is_not_authorized_for_build_or_spec_creation() -> None:
    with pytest.raises(ValueError, match="workflow terminal mismatch"):
        terminal_product_state(
            "BUILD_PRODUCT",
            ProductState.DEDUPE_PASSED,
            ProductState.REJECTED,
        )
    with pytest.raises(ValueError, match="workflow terminal mismatch"):
        terminal_product_state(
            "CREATE_PRODUCT_SPEC",
            ProductState.QUALIFIED,
            ProductState.INSUFFICIENT_EVIDENCE,
        )
