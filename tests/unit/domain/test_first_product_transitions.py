"""Transition and event-name tests for the first-product workflow."""

from __future__ import annotations

from itertools import pairwise
from types import MappingProxyType

import pytest

import money_machine.domain.value_objects as value_objects
from money_machine.domain.enums import JobState, ProductState
from money_machine.domain.events import DomainEventName
from money_machine.domain.value_objects import (
    JOB_TRANSITIONS,
    PRODUCT_TRANSITIONS,
    assert_job_transition,
    assert_product_transition,
)


def test_product_happy_path_allows_only_adjacent_stages() -> None:
    path = (
        ProductState.RESEARCHED,
        ProductState.QUALIFIED,
        ProductState.SPECIFIED,
        ProductState.DEDUPE_PASSED,
        ProductState.BUILT,
        ProductState.QA_PASSED,
        ProductState.MERCHANDISED,
        ProductState.PREFLIGHT_PASSED,
        ProductState.DRAFT_READY,
    )
    for current, target in pairwise(path):
        assert_product_transition(current, target)

    with pytest.raises(ValueError, match="product transition"):
        assert_product_transition(ProductState.RESEARCHED, ProductState.SPECIFIED)
    with pytest.raises(ValueError, match="product transition"):
        assert_product_transition(ProductState.BUILT, ProductState.SPECIFIED)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ProductState.RESEARCHED, ProductState.INSUFFICIENT_EVIDENCE),
        (ProductState.QUALIFIED, ProductState.INSUFFICIENT_EVIDENCE),
        (ProductState.RESEARCHED, ProductState.REJECTED),
        (ProductState.SPECIFIED, ProductState.REJECTED),
        (ProductState.BUILT, ProductState.FAILED),
        (ProductState.PREFLIGHT_PASSED, ProductState.FAILED),
    ],
)
def test_product_terminal_branches_are_explicit(
    current: ProductState, target: ProductState
) -> None:
    assert_product_transition(current, target)


@pytest.mark.parametrize(
    "terminal",
    [
        ProductState.DRAFT_READY,
        ProductState.INSUFFICIENT_EVIDENCE,
        ProductState.REJECTED,
        ProductState.FAILED,
    ],
)
def test_product_terminal_states_have_no_outgoing_transition(terminal: ProductState) -> None:
    assert PRODUCT_TRANSITIONS[terminal] == frozenset()
    with pytest.raises(ValueError, match="product transition"):
        assert_product_transition(terminal, ProductState.RESEARCHED)


def test_job_leasing_retry_success_failure_and_cancellation_transitions() -> None:
    allowed = (
        (JobState.PENDING, JobState.READY),
        (JobState.READY, JobState.LEASED),
        (JobState.LEASED, JobState.RUNNING),
        (JobState.LEASED, JobState.READY),
        (JobState.RUNNING, JobState.RETRY_WAIT),
        (JobState.RETRY_WAIT, JobState.READY),
        (JobState.RUNNING, JobState.SUCCEEDED),
        (JobState.RUNNING, JobState.FAILED),
        (JobState.PENDING, JobState.CANCELLED),
        (JobState.READY, JobState.CANCELLED),
        (JobState.LEASED, JobState.CANCELLED),
        (JobState.RUNNING, JobState.CANCELLED),
        (JobState.RETRY_WAIT, JobState.CANCELLED),
    )
    for current, target in allowed:
        assert_job_transition(current, target)

    with pytest.raises(ValueError, match="job transition"):
        assert_job_transition(JobState.PENDING, JobState.RUNNING)
    with pytest.raises(ValueError, match="job transition"):
        assert_job_transition(JobState.RETRY_WAIT, JobState.SUCCEEDED)


@pytest.mark.parametrize("terminal", [JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED])
def test_job_terminal_states_have_no_outgoing_transition(terminal: JobState) -> None:
    assert JOB_TRANSITIONS[terminal] == frozenset()
    with pytest.raises(ValueError, match="job transition"):
        assert_job_transition(terminal, JobState.READY)


def test_transition_tables_are_immutable() -> None:
    assert isinstance(PRODUCT_TRANSITIONS, MappingProxyType)
    assert isinstance(JOB_TRANSITIONS, MappingProxyType)
    assert not hasattr(value_objects, "_product_transitions")


def test_domain_event_names_are_exact_and_stable() -> None:
    assert [event.value for event in DomainEventName] == [
        "research_packet_admitted",
        "candidate_shortlisted",
        "product_spec_created",
        "dedupe_passed",
        "product_built",
        "product_qa_passed",
        "listing_package_created",
        "preflight_passed",
        "draft_ready",
        "insufficient_evidence",
        "workflow_rejected",
        "workflow_failed",
    ]
