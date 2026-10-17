"""Earn the Session 11 intake, routing, repair, draft, and control keys.

The proof does not open a socket, read a credential, insert a job, or send a message.
"""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

from money_machine.assets.support_intake import (
    IntakeLedger,
    IntakeRecord,
    IssueCode,
    SupportRefusal,
    VerificationRead,
    draft_reply,
    open_issue,
    record_repair,
    resolve_issue,
)
from money_machine.control.session_15_proof import session_15_pointer_holds
from money_machine.domain.enums import IncidentType

INTAKE_EVIDENCE_KEY = "support_intake_implemented"
ROUTING_EVIDENCE_KEY = "incident_routing_implemented"
REPAIR_EVIDENCE_KEY = "repair_resolution_implemented"
DRAFT_EVIDENCE_KEY = "draft_reply_implemented"
CONTROL_EVIDENCE_KEY = "control_files_and_checkpoint_current"
_CLOSURE_EVIDENCE_KEY = "evidence_closure_commit_recorded"
EARNED_EVIDENCE_KEYS = frozenset(
    {
        INTAKE_EVIDENCE_KEY,
        ROUTING_EVIDENCE_KEY,
        REPAIR_EVIDENCE_KEY,
        DRAFT_EVIDENCE_KEY,
        CONTROL_EVIDENCE_KEY,
    }
)
_BEHAVIORAL_KEYS = (
    INTAKE_EVIDENCE_KEY,
    ROUTING_EVIDENCE_KEY,
    REPAIR_EVIDENCE_KEY,
    DRAFT_EVIDENCE_KEY,
)
_CONTROL_FILES = (
    Path("docs/control/IMPLEMENTATION_STATE.json"),
    Path("docs/control/IMPLEMENTATION_LOG.md"),
    Path("docs/control/DECISIONS.md"),
    Path("docs/control/TEST_EVIDENCE.md"),
    Path("docs/control/NEXT_SESSION.md"),
    Path("docs/control/SESSION_EVIDENCE.md"),
)
_PRIOR_HEAD = "f16c7ed0598daf3f4627955b52585f253ae1b918"
_CLOSURE_HEAD = "d095501665fbda0f9e6a0e77b57531bc33fda4e2"
_SESSION_12_CLOSURE = "d81db61033561bdd40869ff1316f0c935c74cdf4"
_SESSION_13_CLOSURE = "fbaf8e8bdd73b1e3b6fa4f87158574057b72d18a"
_SESSION_14_PROMPT = "17_SESSION_14_DEPLOYMENT.md"
_SESSION_14_CLOSURE = "02c26f39ac8800db03ae7f5d1d346487a5ce123e"
_SESSION_15_PROMPT = "18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md"
_SESSION_14_KEYS = frozenset(
    {
        "deployment_target_recorded",
        "production_packaging_defined",
        "release_rollback_implemented",
        "service_controls_fail_closed",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
_SESSION_15_KEYS = frozenset(
    {
        "acceptance_matrix_recorded",
        "control_files_and_checkpoint_current",
        "deployed_state_checked",
        "evidence_closure_commit_recorded",
        "linked_workflow_fixture",
        "provider_connections_fail_closed",
        "standing_authority_recorded",
    }
)
_SESSION_11_PROMPT = "14_SESSION_11_CUSTOMER_SUPPORT_AND_REPAIR.md"
_SESSION_12_PROMPT = "15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md"
_SESSION_13_PROMPT = "16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md"
_SESSION_12_KEYS = frozenset(
    {
        "console_read_model_implemented",
        "exception_views_implemented",
        "telemetry_redaction_implemented",
        "operator_actions_fail_closed",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
_SESSION_13_KEYS = frozenset(
    {
        "implementation_matrix_recorded",
        "synthetic_paths_implemented",
        "failure_injection_implemented",
        "backup_restore_fixture_implemented",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
_DRAFT_BODY = (
    "We received this once. the file hash is aaaa path-token-1 Reply if the issue remains."
)
_WHEN = datetime(2026, 10, 16, 12, tzinfo=UTC)
_LATER = datetime(2026, 10, 16, 12, 5, tzinfo=UTC)
_SHOP = UUID("00000000-0000-4000-8000-000000000011")
_LISTING = UUID("00000000-0000-4000-8000-000000000012")
_PRODUCT = UUID("00000000-0000-4000-8000-000000000013")
_VARIANT = UUID("00000000-0000-4000-8000-000000000014")
_HASH = "ab" * 32
_NOTICE = "cd" * 32
_OTHER = "ef" * 32
_SECRET = "sk_exampletoken"
_RESUME = UUID("00000000-0000-4000-8000-000000000018")
_REPAIR = UUID("00000000-0000-4000-8000-000000000017")
_VERIFY = UUID("00000000-0000-4000-8000-000000000019")
_ROUTES: tuple[tuple[IssueCode, IncidentType, str | None, bool], ...] = (
    ("BROKEN_DELIVERY_LINK", IncidentType.BROKEN_LINK, "IncidentRepairJob", True),
    ("NOTION_PAGE_UNPUBLISHED", IncidentType.BUILD_DEFECT, "IncidentRepairJob", True),
    ("WRONG_VARIANT_LINK", IncidentType.LISTING_DEFECT, "IncidentRepairJob", True),
    ("NO_ACCESS_BLOCK", IncidentType.BROKEN_LINK, "IncidentRepairJob", True),
    ("LINKED_VIEW_BROKEN", IncidentType.BUILD_DEFECT, "IncidentRepairJob", True),
    ("FORMULA_ERROR", IncidentType.BUILD_DEFECT, "IncidentRepairJob", True),
    ("DOWNLOAD_FILE_MISSING", IncidentType.LISTING_DEFECT, "IncidentRepairJob", True),
    ("LISTING_DEACTIVATED", IncidentType.LISTING_DEFECT, "ListingRepairJob", False),
    ("ACCOUNT_VERIFICATION", IncidentType.CREDENTIAL_FAILURE, None, False),
    ("DEDUPE_REJECTION", IncidentType.CUSTOMER_ISSUE, "ReconceptProductJob", False),
    ("AGENT_RUN_INTERRUPTED", IncidentType.TERMINAL_JOB_FAILURE, "IncidentRepairJob", False),
    ("NO_SALES_DIAGNOSIS", IncidentType.LISTING_DEFECT, "ListingRepairJob", False),
    ("OTHER_PRODUCT_DEFECT", IncidentType.BUILD_DEFECT, "IncidentRepairJob", False),
)


class Session11ProofError(ValueError):
    """The Session 11 fixture did not earn its evidence key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def prove_session_11() -> frozenset[str]:
    """Return the earned Session 11 keys. A miss raises instead of returning them."""
    _prove_intake()
    _prove_routing()
    _prove_repair()
    _prove_draft()
    _prove_control_files()
    return EARNED_EVIDENCE_KEYS


def _open(
    ledger: IntakeLedger,
    *,
    received_at: datetime = _WHEN,
    safe_summary: str = "the purchase cannot be used",
    buyer_reference: str = "buyer-opaque-1",
) -> IntakeRecord:
    return open_issue(
        ledger,
        shop_id=_SHOP,
        buyer_reference=buyer_reference,
        listing_id=_LISTING,
        product_id=_PRODUCT,
        variant_id=_VARIANT,
        issue_code="BROKEN_DELIVERY_LINK",
        safe_summary=safe_summary,
        attachment_sha256=_HASH,
        attachment_content_type="application/pdf",
        received_at=received_at,
        urgency="normal",
    )


def _prove_intake() -> None:
    if "incident_id" in inspect.signature(open_issue).parameters:
        raise Session11ProofError("intake_id")
    ledger = IntakeLedger()
    first = _open(ledger)
    second = _open(ledger, safe_summary="a later safe note")
    if (
        second.incident_id != first.incident_id
        or second.safe_summary != first.safe_summary
        or len(ledger.issues()) != 1
    ):
        raise Session11ProofError("intake_idempotent")
    other = _open(ledger, received_at=_LATER)
    if other.incident_id == first.incident_id or len(ledger.issues()) != 2:
        raise Session11ProofError("intake_key")
    if (
        first.attachment_sha256 != _HASH
        or first.attachment_content_type != "application/pdf"
        or isinstance(first.attachment_sha256, bytes)
        or first.send_count != 0
        or first.provider_writes != 0
        or first.jobs_inserted != 0
        or any(step.inserted for step in first.plan)
    ):
        raise Session11ProofError("intake_store")
    try:
        _open(IntakeLedger(), safe_summary=f"see {_SECRET}")
    except SupportRefusal as error:
        if error.code != "unsafe_summary" or _SECRET in str(error):
            raise Session11ProofError("intake_secret") from error
    else:
        raise Session11ProofError("intake_secret")
    source = Path(open_issue.__code__.co_filename).read_text(encoding="utf-8")
    if (
        "import httpx" in source
        or "import socket" in source
        or "SESSION_11_SUPPORT_AND_REPAIR_COMPLETE" in source
    ):
        raise Session11ProofError("intake_boundary")
    root = Path(__file__).resolve().parents[3]
    block = (root / "config" / "agents.yaml").read_text(encoding="utf-8").split("agent_id: A16", 1)
    if len(block) != 2:
        raise Session11ProofError("intake_a16")
    agent = block[1]
    if "commissioning_state: DESIGNED" not in agent or "commissioning_evidence: []" not in agent:
        raise Session11ProofError("intake_a16")


def _prove_routing() -> None:
    """Each issue code keeps its own type and plan. Summary words do not select it."""
    for code, incident_type, first_job, preempts in _ROUTES:
        record = open_issue(
            IntakeLedger(),
            shop_id=_SHOP,
            buyer_reference="buyer-opaque-1",
            listing_id=_LISTING,
            product_id=_PRODUCT,
            variant_id=_VARIANT,
            issue_code=code,
            safe_summary="pdf formula colour link",
            attachment_sha256=_HASH,
            attachment_content_type="application/pdf",
            received_at=_WHEN,
            urgency="normal",
            notice_sha256=_NOTICE if code == "LISTING_DEACTIVATED" else None,
            resume_job_id=_RESUME if code == "AGENT_RUN_INTERRUPTED" else None,
            resume_phase=2 if code == "AGENT_RUN_INTERRUPTED" else None,
            caller_priority=0 if preempts else 100,
        )
        jobs = [step.job_type for step in record.plan]
        if record.issue_code != code or record.incident_type is not incident_type:
            raise Session11ProofError("route_type")
        if record.preempts_routine is not preempts:
            raise Session11ProofError("route_priority")
        if (
            record.jobs_inserted != 0
            or record.provider_writes != 0
            or record.send_count != 0
            or any(step.inserted for step in record.plan)
        ):
            raise Session11ProofError("route_insert")
        if first_job is None:
            if record.plan != ():
                raise Session11ProofError("route_plan")
        elif not jobs or jobs[0] != first_job:
            raise Session11ProofError("route_plan")
        if code == "ACCOUNT_VERIFICATION" and record.status != "BLOCKED":
            raise Session11ProofError("route_account")
        if code == "DEDUPE_REJECTION" and (
            record.cited_product_id != _PRODUCT or record.new_product_ids != ()
        ):
            raise Session11ProofError("route_dedupe")
        if code == "NO_SALES_DIAGNOSIS" and (
            jobs != ["ListingRepairJob", "ResearchCollectionJob"]
            or [step.day_offset for step in record.plan] != [0, 14]
        ):
            raise Session11ProofError("route_sales")
        if code == "AGENT_RUN_INTERRUPTED" and (
            record.resume_job_id != _RESUME or record.resume_phase != 2
        ):
            raise Session11ProofError("route_resume")
    try:
        open_issue(
            IntakeLedger(),
            shop_id=_SHOP,
            buyer_reference="buyer-opaque-1",
            listing_id=_LISTING,
            product_id=_PRODUCT,
            variant_id=_VARIANT,
            issue_code=cast(IssueCode, "AGENT_RUN_INTERRUPTED"),
            safe_summary="the purchase cannot be used",
            attachment_sha256=_HASH,
            attachment_content_type="application/pdf",
            received_at=_WHEN,
            urgency="normal",
            resume_job_id=_RESUME,
            resume_phase=0,
        )
    except SupportRefusal as error:
        if error.code != "resume_phase":
            raise Session11ProofError("route_phase") from error
    else:
        raise Session11ProofError("route_phase")


def _verification(
    *,
    fresh: str = _HASH,
    verification: UUID = _VERIFY,
    read_at: datetime = _LATER,
    fix: str = "the file hash is aaaa",
    access_path: str = "path-token-1",
) -> VerificationRead:
    return VerificationRead(
        repair_job_id=_REPAIR,
        verification_job_id=verification,
        repaired_hash=_HASH,
        fresh_hash=fresh,
        repaired_at=_WHEN,
        read_at=read_at,
        fix=fix,
        access_path=access_path,
    )


def _prove_repair() -> None:
    """One idempotency key keeps one version. A close needs a later matching read."""
    ledger = IntakeLedger()
    incident = _open(ledger)
    first = record_repair(
        ledger,
        incident_id=incident.incident_id,
        idempotency_key="repair-1",
        artifact_hash=_HASH,
    )
    second = record_repair(
        ledger,
        incident_id=incident.incident_id,
        idempotency_key="repair-1",
        artifact_hash=_OTHER,
    )
    other = record_repair(
        ledger,
        incident_id=incident.incident_id,
        idempotency_key="repair-2",
        artifact_hash=_OTHER,
    )
    if (
        second.version_id != first.version_id
        or second.artifact_hash != _HASH
        or other.version_id == first.version_id
        or ledger.repair_count(incident.incident_id) != 2
    ):
        raise Session11ProofError("repair_version")
    try:
        record_repair(
            ledger,
            incident_id=incident.incident_id,
            idempotency_key=" ",
            artifact_hash=_HASH,
        )
    except SupportRefusal as error:
        if error.code != "idempotency_key":
            raise Session11ProofError("repair_key") from error
    else:
        raise Session11ProofError("repair_key")
    closed = resolve_issue(_verification())
    mismatch = resolve_issue(_verification(fresh=_OTHER))
    same_job = resolve_issue(_verification(verification=_REPAIR))
    same_time = resolve_issue(_verification(read_at=_WHEN))
    if (
        closed.status != "RESOLVED"
        or closed.verification_job_id != _VERIFY
        or closed.resolution_reference != _HASH
        or closed.resolved_at != _LATER
        or closed.send_count != 0
    ):
        raise Session11ProofError("repair_close")
    if (
        mismatch.status != "OPEN"
        or mismatch.verification_job_id is not None
        or mismatch.resolution_reference is not None
        or same_job.status != "OPEN"
        or same_time.status != "OPEN"
        or incident.jobs_inserted != 0
        or incident.send_count != 0
    ):
        raise Session11ProofError("repair_open")


def _prove_draft() -> None:
    """A draft uses the verification's own words. Auto and a failed read send nothing."""
    ledger = IntakeLedger()
    drafted = draft_reply(ledger, _verification(), mode="draft")
    body = drafted.body
    if (
        body != _DRAFT_BODY
        or drafted.send_count != 0
        or ledger.sends != 0
        or body.count("We received this once.") != 1
        or body.count("Reply if the issue remains.") != 1
    ):
        raise Session11ProofError("draft_body")
    silent = draft_reply(ledger, _verification(fresh=_OTHER), mode="draft")
    auto = draft_reply(ledger, _verification(), mode="auto")
    if (
        silent.body is not None
        or silent.send_count != 0
        or auto.body is not None
        or auto.send_count != 0
        or ledger.sends != 0
    ):
        raise Session11ProofError("draft_silent")
    try:
        draft_reply(ledger, _verification(fix=f"see {_SECRET}"), mode="draft")
    except SupportRefusal as error:
        if error.code != "reply" or _SECRET in str(error):
            raise Session11ProofError("draft_secret") from error
    else:
        raise Session11ProofError("draft_secret")
    try:
        draft_reply(ledger, _verification(fix=" "), mode="draft")
    except SupportRefusal as error:
        if error.code != "reply":
            raise Session11ProofError("draft_blank") from error
    else:
        raise Session11ProofError("draft_blank")


def _prove_control_files() -> None:
    """The continuity files and the catalogue match the checked-in pointer."""
    root = Path(__file__).resolve().parents[3]
    for relative in _CONTROL_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise Session11ProofError("control_files")
    # session_evidence imports state, and state imports this module.
    from money_machine.control.session_evidence import render_session_evidence

    catalogue = root / "docs/control/SESSION_EVIDENCE.md"
    if catalogue.read_text(encoding="utf-8") != render_session_evidence():
        raise Session11ProofError("control_checkpoint")
    decoded: object = json.loads(
        (root / "docs/control/IMPLEMENTATION_STATE.json").read_text(encoding="utf-8")
    )
    if not isinstance(decoded, dict):
        raise Session11ProofError("control_checkpoint")
    evidence = decoded.get("required_completion_evidence")
    recorded = set(evidence) if isinstance(evidence, dict) else set()
    status = decoded.get("session_status")
    if decoded.get("current_session") == 15:
        _prove_activated_session_15(decoded, evidence, status, recorded)
        return
    if decoded.get("current_session") == 14:
        _prove_activated_session_14(decoded, evidence, status, recorded)
        return
    if decoded.get("current_session") == 13:
        _prove_activated_session_13(decoded, evidence, status, recorded)
        return
    if decoded.get("current_session") == 12:
        _prove_activated_session_12(decoded, evidence, status, recorded)
        return
    if (
        decoded.get("current_session") != 11
        or decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or recorded != set(_BEHAVIORAL_KEYS) | {CONTROL_EVIDENCE_KEY, _CLOSURE_EVIDENCE_KEY}
        or not isinstance(evidence, dict)
        or status not in {"incomplete", "complete"}
    ):
        raise Session11ProofError("control_checkpoint")
    for key in _BEHAVIORAL_KEYS:
        if evidence.get(key) is not True:
            raise Session11ProofError("control_checkpoint")
    if status == "incomplete":
        if (
            decoded.get("head_sha") != _PRIOR_HEAD
            or decoded.get("next_session") != 11
            or decoded.get("completed_sessions") != list(range(11))
            or decoded.get("next_prompt") != _SESSION_11_PROMPT
            or evidence.get(_CLOSURE_EVIDENCE_KEY) is not False
            or not isinstance(evidence.get(CONTROL_EVIDENCE_KEY), bool)
        ):
            raise Session11ProofError("control_checkpoint")
        return
    if (
        decoded.get("head_sha") != _CLOSURE_HEAD
        or decoded.get("next_session") != 12
        or decoded.get("completed_sessions") != list(range(12))
        or decoded.get("next_prompt") != _SESSION_12_PROMPT
        or evidence.get(_CLOSURE_EVIDENCE_KEY) is not True
        or evidence.get(CONTROL_EVIDENCE_KEY) is not True
    ):
        raise Session11ProofError("control_checkpoint")


def _prove_activated_session_12(
    decoded: dict[str, object],
    evidence: object,
    status: object,
    recorded: set[str],
) -> None:
    """Session 11 stays closed while Session 12 is incomplete or complete."""
    values_are_bool = isinstance(evidence, dict) and all(
        isinstance(value, bool) for value in evidence.values()
    )
    if (
        decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or recorded != set(_SESSION_12_KEYS)
        or not values_are_bool
        or not isinstance(evidence, dict)
        or len(evidence) != len(recorded)
        or status not in {"incomplete", "complete"}
    ):
        raise Session11ProofError("control_checkpoint")
    if status == "incomplete":
        if (
            decoded.get("head_sha") != _CLOSURE_HEAD
            or decoded.get("next_session") != 12
            or decoded.get("completed_sessions") != list(range(12))
            or decoded.get("next_prompt") != _SESSION_12_PROMPT
        ):
            raise Session11ProofError("control_checkpoint")
        return
    if (
        decoded.get("head_sha") != _SESSION_12_CLOSURE
        or decoded.get("next_session") != 13
        or decoded.get("completed_sessions") != list(range(13))
        or decoded.get("next_prompt") != _SESSION_13_PROMPT
        or any(value is not True for value in evidence.values())
    ):
        raise Session11ProofError("control_checkpoint")


def _prove_activated_session_13(
    decoded: dict[str, object],
    evidence: object,
    status: object,
    recorded: set[str],
) -> None:
    """Session 11 stays closed while Session 13 is complete."""
    values_are_bool = isinstance(evidence, dict) and all(
        isinstance(value, bool) for value in evidence.values()
    )
    if (
        decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or decoded.get("head_sha") != _SESSION_13_CLOSURE
        or recorded != set(_SESSION_13_KEYS)
        or not values_are_bool
        or not isinstance(evidence, dict)
        or len(evidence) != len(recorded)
        or status != "complete"
        or decoded.get("next_session") != 14
        or decoded.get("completed_sessions") != list(range(14))
        or decoded.get("next_prompt") != _SESSION_14_PROMPT
        or any(value is not True for value in evidence.values())
    ):
        raise Session11ProofError("control_checkpoint")


def _prove_activated_session_15(
    decoded: dict[str, object],
    evidence: object,
    status: object,
    recorded: set[str],
) -> None:
    """Session 11 stays closed while Session 15 is activated."""
    values_are_bool = isinstance(evidence, dict) and all(
        isinstance(value, bool) for value in evidence.values()
    )
    if (
        decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or decoded.get("head_sha") != _SESSION_14_CLOSURE
        or recorded != set(_SESSION_15_KEYS)
        or not values_are_bool
        or not isinstance(evidence, dict)
        or len(evidence) != len(recorded)
        or status != "incomplete"
        or decoded.get("next_session") != 15
        or decoded.get("completed_sessions") != list(range(15))
        or decoded.get("next_prompt") != _SESSION_15_PROMPT
        or not session_15_pointer_holds(evidence)
    ):
        raise Session11ProofError("control_checkpoint")


def _prove_activated_session_14(
    decoded: dict[str, object],
    evidence: object,
    status: object,
    recorded: set[str],
) -> None:
    """Session 11 stays closed while Session 14 is complete."""
    values_are_bool = isinstance(evidence, dict) and all(
        isinstance(value, bool) for value in evidence.values()
    )
    if (
        decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or decoded.get("head_sha") != _SESSION_14_CLOSURE
        or recorded != set(_SESSION_14_KEYS)
        or not values_are_bool
        or not isinstance(evidence, dict)
        or len(evidence) != len(recorded)
        or status != "complete"
        or decoded.get("next_session") != 15
        or decoded.get("completed_sessions") != list(range(15))
        or decoded.get("next_prompt") != _SESSION_15_PROMPT
        or any(value is not True for value in evidence.values())
    ):
        raise Session11ProofError("control_checkpoint")
