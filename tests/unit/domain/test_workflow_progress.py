"""Exact workflow progress derived from durable first-product events."""

from __future__ import annotations

import pytest

from money_machine.domain.enums import ProductState
from money_machine.domain.events import DomainEventName
from money_machine.domain.workflow_progress import next_product_state


@pytest.mark.parametrize(
    ("job_type", "current", "event", "expected"),
    [
        (
            "ADMIT_RESEARCH_PACKET",
            ProductState.RESEARCHED,
            DomainEventName.RESEARCH_PACKET_ADMITTED,
            ProductState.RESEARCHED,
        ),
        (
            "QUALIFY_CANDIDATES",
            ProductState.RESEARCHED,
            DomainEventName.CANDIDATE_SHORTLISTED,
            ProductState.QUALIFIED,
        ),
        (
            "CREATE_PRODUCT_SPEC",
            ProductState.QUALIFIED,
            DomainEventName.PRODUCT_SPEC_CREATED,
            ProductState.SPECIFIED,
        ),
        (
            "CHECK_CATALOGUE_DEDUPE",
            ProductState.SPECIFIED,
            DomainEventName.DEDUPE_PASSED,
            ProductState.DEDUPE_PASSED,
        ),
        (
            "BUILD_PRODUCT",
            ProductState.DEDUPE_PASSED,
            DomainEventName.PRODUCT_BUILT,
            ProductState.BUILT,
        ),
        (
            "RUN_PRODUCT_QA",
            ProductState.BUILT,
            DomainEventName.PRODUCT_QA_PASSED,
            ProductState.QA_PASSED,
        ),
        (
            "CREATE_LISTING_PACKAGE",
            ProductState.QA_PASSED,
            DomainEventName.LISTING_PACKAGE_CREATED,
            ProductState.MERCHANDISED,
        ),
        (
            "RUN_PREFLIGHT",
            ProductState.MERCHANDISED,
            DomainEventName.DRAFT_READY,
            ProductState.DRAFT_READY,
        ),
    ],
)
def test_first_product_events_advance_only_the_exact_workflow_stage(
    job_type: str,
    current: ProductState,
    event: DomainEventName,
    expected: ProductState,
) -> None:
    assert next_product_state(job_type, current, event) is expected


def test_first_product_event_rejects_out_of_order_or_terminal_progress() -> None:
    with pytest.raises(ValueError, match="workflow event/state mismatch"):
        next_product_state("BUILD_PRODUCT", ProductState.RESEARCHED, DomainEventName.PRODUCT_BUILT)
    with pytest.raises(ValueError, match="workflow event/state mismatch"):
        next_product_state("RUN_PREFLIGHT", ProductState.DRAFT_READY, DomainEventName.DRAFT_READY)
    with pytest.raises(ValueError, match="workflow event/state mismatch"):
        next_product_state(
            "BUILD_PRODUCT", ProductState.DEDUPE_PASSED, DomainEventName.DEDUPE_PASSED
        )
