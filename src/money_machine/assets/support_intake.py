"""In-memory support intake. No provider call and no inserted job.

The issue code is an argument. Summary text does not choose it. A second
intake with the same shop, buyer reference, and received time returns the
first incident. ``auto`` does not send.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid5

from money_machine.domain.enums import IncidentType

_NAMESPACE = UUID("b7c1d2e3-4f50-4a61-8b72-9c0d1e2f3a4b")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SECRET_MARKS = ("@", "://", "bearer", "sk_")
_ACK = "We received this once."
_INVITE = "Reply if the issue remains."

type IssueCode = Literal[
    "BROKEN_DELIVERY_LINK",
    "NOTION_PAGE_UNPUBLISHED",
    "WRONG_VARIANT_LINK",
    "NO_ACCESS_BLOCK",
    "LINKED_VIEW_BROKEN",
    "FORMULA_ERROR",
    "DOWNLOAD_FILE_MISSING",
    "LISTING_DEACTIVATED",
    "ACCOUNT_VERIFICATION",
    "DEDUPE_REJECTION",
    "AGENT_RUN_INTERRUPTED",
    "NO_SALES_DIAGNOSIS",
    "OTHER_PRODUCT_DEFECT",
]
type IntakeStatus = Literal["OPEN", "BLOCKED", "RESOLVED"]
type ReplyMode = Literal["draft", "auto"]


class SupportRefusal(ValueError):
    """The intake cannot be stored."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class PlanStep:
    """A named existing job type. ``inserted`` stays false in this wave."""

    job_type: str
    day_offset: int
    inserted: bool


@dataclass(frozen=True, slots=True)
class IntakeRecord:
    """One ledger incident. The id is derived from the idempotency key."""

    incident_id: UUID
    shop_id: UUID
    buyer_reference: str
    listing_id: UUID | None
    product_id: UUID
    variant_id: UUID | None
    issue_code: IssueCode
    incident_type: IncidentType
    safe_summary: str
    attachment_sha256: str
    attachment_content_type: str
    received_at: datetime
    urgency: Literal["low", "normal", "high"]
    status: IntakeStatus
    plan: tuple[PlanStep, ...]
    preempts_routine: bool
    cited_product_id: UUID | None
    new_product_ids: tuple[UUID, ...]
    resume_job_id: UUID | None
    resume_phase: int | None
    notice_sha256: str | None
    reactivation_executed: bool
    send_count: int
    provider_writes: int
    jobs_inserted: int


@dataclass(frozen=True, slots=True)
class RepairVersion:
    """One retained repair version for an idempotency key."""

    version_id: UUID
    incident_id: UUID
    idempotency_key: str
    artifact_hash: str


@dataclass(frozen=True, slots=True)
class Resolution:
    """Close result. A mismatched fresh read stays open."""

    status: IntakeStatus
    repair_job_id: UUID
    verification_job_id: UUID | None
    resolution_reference: str | None
    resolved_at: datetime | None
    send_count: int


@dataclass(frozen=True, slots=True)
class VerificationRead:
    """A fresh read supplied by the caller. This module does not fetch it."""

    repair_job_id: UUID
    verification_job_id: UUID
    repaired_hash: str
    fresh_hash: str
    repaired_at: datetime
    read_at: datetime
    fix: str
    access_path: str


@dataclass(frozen=True, slots=True)
class SupportReply:
    """A draft body, or no body when the mode is auto or the read failed."""

    body: str | None
    send_count: int


@dataclass(frozen=True, slots=True)
class _Spec:
    incident_type: IncidentType
    plan: tuple[PlanStep, ...]
    preempts_routine: bool
    status: IntakeStatus


def _step(job_type: str, day_offset: int = 0) -> PlanStep:
    return PlanStep(job_type=job_type, day_offset=day_offset, inserted=False)


_SPECS: dict[IssueCode, _Spec] = {
    "BROKEN_DELIVERY_LINK": _Spec(
        IncidentType.BROKEN_LINK,
        (
            _step("IncidentRepairJob"),
            _step("NotionRepairJob"),
            _step("LinkVerificationJob"),
        ),
        True,
        "OPEN",
    ),
    "NOTION_PAGE_UNPUBLISHED": _Spec(
        IncidentType.BUILD_DEFECT,
        (_step("IncidentRepairJob"), _step("NotionRepairJob")),
        True,
        "OPEN",
    ),
    "WRONG_VARIANT_LINK": _Spec(
        IncidentType.LISTING_DEFECT,
        (_step("IncidentRepairJob"), _step("ListingRepairJob")),
        True,
        "OPEN",
    ),
    "NO_ACCESS_BLOCK": _Spec(
        IncidentType.BROKEN_LINK,
        (_step("IncidentRepairJob"), _step("NotionRepairJob")),
        True,
        "OPEN",
    ),
    "LINKED_VIEW_BROKEN": _Spec(
        IncidentType.BUILD_DEFECT,
        (_step("IncidentRepairJob"), _step("NotionRepairJob")),
        True,
        "OPEN",
    ),
    "FORMULA_ERROR": _Spec(
        IncidentType.BUILD_DEFECT,
        (_step("IncidentRepairJob"), _step("NotionRepairJob")),
        True,
        "OPEN",
    ),
    "DOWNLOAD_FILE_MISSING": _Spec(
        IncidentType.LISTING_DEFECT,
        (_step("IncidentRepairJob"), _step("ListingRepairJob")),
        True,
        "OPEN",
    ),
    "LISTING_DEACTIVATED": _Spec(
        IncidentType.LISTING_DEFECT,
        (_step("ListingRepairJob"),),
        False,
        "OPEN",
    ),
    "ACCOUNT_VERIFICATION": _Spec(IncidentType.CREDENTIAL_FAILURE, (), False, "BLOCKED"),
    "DEDUPE_REJECTION": _Spec(
        IncidentType.CUSTOMER_ISSUE,
        (_step("ReconceptProductJob"),),
        False,
        "OPEN",
    ),
    "AGENT_RUN_INTERRUPTED": _Spec(
        IncidentType.TERMINAL_JOB_FAILURE,
        (_step("IncidentRepairJob"),),
        False,
        "OPEN",
    ),
    "NO_SALES_DIAGNOSIS": _Spec(
        IncidentType.LISTING_DEFECT,
        (_step("ListingRepairJob", 0), _step("ResearchCollectionJob", 14)),
        False,
        "OPEN",
    ),
    "OTHER_PRODUCT_DEFECT": _Spec(
        IncidentType.BUILD_DEFECT,
        (_step("IncidentRepairJob"),),
        False,
        "OPEN",
    ),
}


class IntakeLedger:
    """Unique index for support incidents and repair versions."""

    def __init__(self) -> None:
        self._issues: dict[tuple[UUID, str, datetime], IntakeRecord] = {}
        self._repairs: dict[tuple[UUID, str], RepairVersion] = {}
        self.sends = 0

    def issues(self) -> tuple[IntakeRecord, ...]:
        return tuple(self._issues.values())

    def get_issue(self, key: tuple[UUID, str, datetime]) -> IntakeRecord | None:
        return self._issues.get(key)

    def put_issue(self, key: tuple[UUID, str, datetime], record: IntakeRecord) -> None:
        self._issues[key] = record

    def get_repair(self, key: tuple[UUID, str]) -> RepairVersion | None:
        return self._repairs.get(key)

    def put_repair(self, key: tuple[UUID, str], version: RepairVersion) -> None:
        self._repairs[key] = version

    def repair_count(self, incident_id: UUID) -> int:
        return sum(1 for key in self._repairs if key[0] == incident_id)


def _clean_reference(value: str, code: str) -> str:
    text = value.strip()
    if text == "" or any(mark in text.casefold() for mark in _SECRET_MARKS):
        raise SupportRefusal(code)
    return text


def _sha256(value: str, code: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise SupportRefusal(code)
    return value


def open_issue(
    ledger: IntakeLedger,
    *,
    shop_id: UUID,
    buyer_reference: str,
    listing_id: UUID | None,
    product_id: UUID,
    variant_id: UUID | None,
    issue_code: IssueCode,
    safe_summary: str,
    attachment_sha256: str,
    attachment_content_type: str,
    received_at: datetime,
    urgency: Literal["low", "normal", "high"],
    notice_sha256: str | None = None,
    resume_job_id: UUID | None = None,
    resume_phase: int | None = None,
    caller_priority: int | None = None,
) -> IntakeRecord:
    """Store one incident. An existing key returns the first record unchanged."""
    del caller_priority
    reference = _clean_reference(buyer_reference, "buyer_reference")
    summary = _clean_reference(safe_summary, "unsafe_summary")
    digest = _sha256(attachment_sha256, "attachment_sha256")
    content_type = attachment_content_type.strip()
    if content_type == "" or any(mark in content_type.casefold() for mark in _SECRET_MARKS):
        raise SupportRefusal("content_type")
    if urgency not in ("low", "normal", "high"):
        raise SupportRefusal("urgency")
    spec = _SPECS.get(issue_code)
    if spec is None:
        raise SupportRefusal("issue_code")
    notice: str | None = None
    if issue_code == "LISTING_DEACTIVATED":
        if notice_sha256 is None:
            raise SupportRefusal("notice")
        notice = _sha256(notice_sha256, "notice")
    resumed: UUID | None = None
    phase: int | None = None
    if issue_code == "AGENT_RUN_INTERRUPTED":
        if resume_job_id is None or resume_phase is None or resume_phase < 1:
            raise SupportRefusal("resume_phase")
        resumed = resume_job_id
        phase = resume_phase
    cited = product_id if issue_code == "DEDUPE_REJECTION" else None
    key = (shop_id, reference, received_at)
    existing = ledger.get_issue(key)
    if existing is not None:
        return existing
    record = IntakeRecord(
        incident_id=uuid5(_NAMESPACE, f"{shop_id}:{reference}:{received_at.isoformat()}"),
        shop_id=shop_id,
        buyer_reference=reference,
        listing_id=listing_id,
        product_id=product_id,
        variant_id=variant_id,
        issue_code=issue_code,
        incident_type=spec.incident_type,
        safe_summary=summary,
        attachment_sha256=digest,
        attachment_content_type=content_type,
        received_at=received_at,
        urgency=urgency,
        status=spec.status,
        plan=spec.plan,
        preempts_routine=spec.preempts_routine,
        cited_product_id=cited,
        new_product_ids=(),
        resume_job_id=resumed,
        resume_phase=phase,
        notice_sha256=notice,
        reactivation_executed=False,
        send_count=0,
        provider_writes=0,
        jobs_inserted=0,
    )
    ledger.put_issue(key, record)
    return record


def record_repair(
    ledger: IntakeLedger,
    *,
    incident_id: UUID,
    idempotency_key: str,
    artifact_hash: str,
) -> RepairVersion:
    """Keep one version per incident and idempotency key."""
    key_text = idempotency_key.strip()
    if key_text == "":
        raise SupportRefusal("idempotency_key")
    digest = _sha256(artifact_hash, "artifact_hash")
    key = (incident_id, key_text)
    existing = ledger.get_repair(key)
    if existing is not None:
        return existing
    version = RepairVersion(
        version_id=uuid5(_NAMESPACE, f"{incident_id}:{key_text}:{digest}"),
        incident_id=incident_id,
        idempotency_key=key_text,
        artifact_hash=digest,
    )
    ledger.put_repair(key, version)
    return version


def _verified(read: VerificationRead) -> bool:
    return (
        read.verification_job_id != read.repair_job_id
        and read.fresh_hash == read.repaired_hash
        and read.read_at > read.repaired_at
    )


def resolve_issue(read: VerificationRead) -> Resolution:
    """Close only after a later matching read from a different job."""
    if not _verified(read):
        return Resolution(
            status="OPEN",
            repair_job_id=read.repair_job_id,
            verification_job_id=None,
            resolution_reference=None,
            resolved_at=None,
            send_count=0,
        )
    return Resolution(
        status="RESOLVED",
        repair_job_id=read.repair_job_id,
        verification_job_id=read.verification_job_id,
        resolution_reference=read.fresh_hash,
        resolved_at=read.read_at,
        send_count=0,
    )


def draft_reply(ledger: IntakeLedger, read: VerificationRead, *, mode: ReplyMode) -> SupportReply:
    """Draft from the verification's own fix and path. Auto sends nothing."""
    if mode == "auto" or not _verified(read):
        reply = SupportReply(body=None, send_count=0)
    else:
        fix = read.fix.strip()
        path = read.access_path.strip()
        if (
            fix == ""
            or path == ""
            or any(mark in f"{fix} {path}".casefold() for mark in _SECRET_MARKS)
        ):
            raise SupportRefusal("reply")
        reply = SupportReply(body=f"{_ACK} {fix} {path} {_INVITE}", send_count=0)
    if ledger.sends != 0:
        raise SupportRefusal("sends")
    return reply


def no_sales_span(record: IntakeRecord) -> timedelta | None:
    """Return the gap between the two no-sales steps, when that code was used."""
    if record.issue_code != "NO_SALES_DIAGNOSIS" or len(record.plan) != 2:
        return None
    return timedelta(days=record.plan[1].day_offset - record.plan[0].day_offset)
