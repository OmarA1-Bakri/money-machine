"""Typed contracts for bounded review subagent artifacts.

Contract: Session 04 W6 — subagent review support lane (S04-09).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, cast

from pydantic import BeforeValidator

from money_machine.domain.models._base import ContractModel, NonEmptyStr
from money_machine.domain.models.common import EvidenceReference


def _coerce_tuple(value: Any) -> Any:
    if type(value) is list:
        return tuple(cast(list[Any], value))
    return value


def _coerce_review_verdict(value: Any) -> Any:
    if isinstance(value, ReviewVerdict):
        return value
    if type(value) is str:
        return ReviewVerdict(value)
    return value


class ReviewVerdict(StrEnum):
    """Terminal review outcome returned by one bounded review subagent."""

    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVISION = "NEEDS_REVISION"


class ReviewFinding(ContractModel):
    """One structured finding from a review subagent."""

    code: NonEmptyStr
    message: NonEmptyStr
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


ReviewVerdictValue = Annotated[ReviewVerdict, BeforeValidator(_coerce_review_verdict)]
ReviewFindings = Annotated[tuple[ReviewFinding, ...], BeforeValidator(_coerce_tuple)]
ReviewEvidenceRefs = Annotated[tuple[EvidenceReference, ...], BeforeValidator(_coerce_tuple)]


class ReviewSubagentResult(ContractModel):
    """Structured output produced by one review subagent invocation."""

    findings: ReviewFindings
    verdict: ReviewVerdictValue
    evidence_refs: ReviewEvidenceRefs = ()
