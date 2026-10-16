"""In-memory Etsy preflight checklist.

Repairable rows return ``PreflightResult`` with ``PASS`` or ``FAIL``. An
unsupported claim is not that result: it is blocked and carries no repair job.
Links, duplicate-as-template, indexing, nested variants, hero order, blank
tags, and sale price stay on the next slice.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from money_machine.domain.enums import BranchOutcome
from money_machine.domain.models.common import CheckResult, EvidenceReference
from money_machine.domain.models.listings import PreflightResult

_REQUIRED_QUANTITY = 999
_REQUIRED_TAGS = 13
_REQUIRED_IMAGES = 10
_REQUIRED_VIDEOS = 1
_REPAIR_QUANTITY = "repair_quantity"
_REPAIR_TAGS = "repair_tags"
_REPAIR_IMAGES = "repair_images"
_REPAIR_VIDEO = "repair_video"
_NAMESPACE = uuid5(NAMESPACE_URL, "https://money-machine.invalid/etsy-preflight")
_OBSERVED_AT = datetime(2026, 10, 16, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class PreflightClaim:
    """One listing claim. ``fact_ref is None`` means nothing backs the string."""

    text: str
    fact_ref: str | None


@dataclass(frozen=True, slots=True)
class EtsyPreflightDraft:
    """Checklist input. A bad row is allowed here so preflight can refuse it."""

    quantity: int
    tags: tuple[str, ...]
    images: tuple[str, ...]
    videos: int
    claims: tuple[PreflightClaim, ...]


@dataclass(frozen=True, slots=True)
class PreflightBlocked:
    """Unsupported claim. Not a ``PreflightResult``. No repair job."""

    blocked: Literal[True] = True
    repair_job_types: tuple[str, ...] = ()


def run_etsy_preflight(draft: EtsyPreflightDraft) -> PreflightResult | PreflightBlocked:
    """Judge one in-memory listing. Unsupported claims never become a repair."""
    if any(claim.fact_ref is None for claim in draft.claims):
        return PreflightBlocked()
    checks, jobs = _repairable(draft)
    return _result(draft, checks, jobs)


def _repairable(draft: EtsyPreflightDraft) -> tuple[tuple[CheckResult, ...], tuple[str, ...]]:
    checks: list[CheckResult] = []
    jobs: list[str] = []
    _pin_quantity(draft, checks, jobs)
    _pin_tags(draft, checks, jobs)
    _pin_images(draft, checks, jobs)
    _pin_video(draft, checks, jobs)
    return tuple(checks), tuple(jobs)


def _pin_quantity(draft: EtsyPreflightDraft, checks: list[CheckResult], jobs: list[str]) -> None:
    if draft.quantity != _REQUIRED_QUANTITY:
        _fail(checks, jobs, "quantity", "quantity_not_999", _REPAIR_QUANTITY, draft.quantity)
        return
    _ok(checks, "quantity", draft.quantity)


def _pin_tags(draft: EtsyPreflightDraft, checks: list[CheckResult], jobs: list[str]) -> None:
    count = len(draft.tags)
    if count != _REQUIRED_TAGS:
        _fail(checks, jobs, "tags", "tag_count", _REPAIR_TAGS, count)
        return
    _ok(checks, "tags", count)


def _pin_images(draft: EtsyPreflightDraft, checks: list[CheckResult], jobs: list[str]) -> None:
    count = len(draft.images)
    if count != _REQUIRED_IMAGES:
        _fail(checks, jobs, "images", "image_count", _REPAIR_IMAGES, count)
        return
    _ok(checks, "images", count)


def _pin_video(draft: EtsyPreflightDraft, checks: list[CheckResult], jobs: list[str]) -> None:
    if draft.videos != _REQUIRED_VIDEOS:
        _fail(checks, jobs, "video", "video_count", _REPAIR_VIDEO, draft.videos)
        return
    _ok(checks, "video", draft.videos)


def _ok(checks: list[CheckResult], name: str, observed: int) -> None:
    checks.append(_check(name, True, None, observed))


def _fail(
    checks: list[CheckResult],
    jobs: list[str],
    name: str,
    defect_code: str,
    job: str,
    observed: int,
) -> None:
    checks.append(_check(name, False, defect_code, observed))
    jobs.append(job)


def _check(name: str, passed: bool, defect_code: str | None, observed: int) -> CheckResult:
    return CheckResult(
        name=name,
        passed=passed,
        defect_code=defect_code,
        evidence=(_evidence(name, observed),),
        observed_value=observed,
    )


def _evidence(name: str, observed: int) -> EvidenceReference:
    summary = f"{name}={observed}"
    return EvidenceReference(
        evidence_id=uuid5(_NAMESPACE, summary),
        evidence_type="preflight-check",
        source_reference=f"memory://etsy-preflight/{name}",
        observed_at=_OBSERVED_AT,
        sha256=hashlib.sha256(summary.encode()).hexdigest(),
        safe_summary=summary,
    )


def _result(
    draft: EtsyPreflightDraft,
    checks: tuple[CheckResult, ...],
    jobs: tuple[str, ...],
) -> PreflightResult:
    digest = _digest(draft)
    failed = any(not check.passed for check in checks)
    outcome = BranchOutcome.FAIL if failed else BranchOutcome.PASS
    evidence = tuple(item for check in checks for item in check.evidence)
    return PreflightResult(
        result_id=uuid5(_NAMESPACE, f"result:{digest}"),
        listing_package_id=uuid5(_NAMESPACE, f"package:{digest}"),
        listing_package_sha256=digest,
        outcome=outcome,
        checks=checks,
        repair_job_types=jobs,
        evidence=evidence,
        completed_at=_OBSERVED_AT,
    )


def _digest(draft: EtsyPreflightDraft) -> str:
    claim_rows = tuple((claim.text, claim.fact_ref) for claim in draft.claims)
    payload = repr((draft.quantity, draft.tags, draft.images, draft.videos, claim_rows))
    return hashlib.sha256(payload.encode()).hexdigest()
