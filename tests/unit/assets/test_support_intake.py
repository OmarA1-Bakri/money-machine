"""Level 1 pins for in-memory support intake."""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest

from money_machine.assets.support_intake import (
    IntakeLedger,
    SupportRefusal,
    VerificationRead,
    draft_reply,
    open_issue,
    record_repair,
    resolve_issue,
)
from money_machine.domain.enums import IncidentType

_WHEN = datetime(2026, 10, 16, 12, tzinfo=UTC)
_LATER = datetime(2026, 10, 16, 13, tzinfo=UTC)
_HASH = "a" * 64
_OTHER_HASH = "b" * 64
_ROOT = Path(__file__).parents[3]

type _Code = Literal[
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


def _uuid(number: int):
    from uuid import UUID

    return UUID(int=number)


def _open(ledger: IntakeLedger, code: _Code = "BROKEN_DELIVERY_LINK", **overrides: object):
    arguments: dict[str, object] = {
        "shop_id": _uuid(1),
        "buyer_reference": "buyer-opaque-1",
        "listing_id": _uuid(2),
        "product_id": _uuid(3),
        "variant_id": _uuid(4),
        "issue_code": code,
        "safe_summary": "the purchase cannot be used",
        "attachment_sha256": _HASH,
        "attachment_content_type": "application/pdf",
        "received_at": _WHEN,
        "urgency": "normal",
        "notice_sha256": _OTHER_HASH if code == "LISTING_DEACTIVATED" else None,
        "resume_job_id": _uuid(8) if code == "AGENT_RUN_INTERRUPTED" else None,
        "resume_phase": 2 if code == "AGENT_RUN_INTERRUPTED" else None,
    }
    arguments.update(overrides)
    return open_issue(ledger, **arguments)  # type: ignore[arg-type]


def _read(
    *, fresh: str = _HASH, verification: int = 9, read_at: datetime = _LATER
) -> VerificationRead:
    return VerificationRead(
        repair_job_id=_uuid(7),
        verification_job_id=_uuid(verification),
        repaired_hash=_HASH,
        fresh_hash=fresh,
        repaired_at=_WHEN,
        read_at=read_at,
        fix="the file hash is aaaa",
        access_path="path-token-1",
    )


@pytest.mark.parametrize(
    ("code", "incident_type", "first_job", "preempts"),
    [
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
    ],
)
def test_each_code_maps_without_reading_the_summary(
    code: _Code,
    incident_type: IncidentType,
    first_job: str | None,
    preempts: bool,
) -> None:
    record = _open(
        IntakeLedger(),
        code,
        safe_summary="pdf formula colour link",
        caller_priority=0 if preempts else 100,
    )

    assert record.issue_code == code
    assert record.incident_type is incident_type
    assert record.preempts_routine is preempts
    assert record.jobs_inserted == 0
    assert record.provider_writes == 0
    assert record.send_count == 0
    assert record.new_product_ids == ()
    assert all(step.inserted is False for step in record.plan)
    if first_job is None:
        assert record.plan == ()
    else:
        assert record.plan[0].job_type == first_job


def test_summary_words_do_not_select_a_broken_link() -> None:
    record = _open(IntakeLedger(), "WRONG_VARIANT_LINK", safe_summary="pdf formula colour")

    assert record.incident_type is IncidentType.LISTING_DEFECT
    assert [step.job_type for step in record.plan] == ["IncidentRepairJob", "ListingRepairJob"]


def test_second_intake_returns_the_first_incident_and_summary() -> None:
    ledger = IntakeLedger()
    first = _open(ledger)
    second = _open(ledger, safe_summary="a later safe note")

    assert second.incident_id == first.incident_id
    assert second.safe_summary == first.safe_summary
    assert len(ledger.issues()) == 1


def test_secret_text_is_refused_without_echoing_the_value() -> None:
    with pytest.raises(SupportRefusal, match="unsafe_summary") as caught:
        _open(IntakeLedger(), safe_summary="see https://secret.example/token")
    assert "secret.example" not in str(caught.value)


def test_account_verification_blocks_with_no_plan() -> None:
    record = _open(IntakeLedger(), "ACCOUNT_VERIFICATION")

    assert record.status == "BLOCKED"
    assert record.plan == ()
    assert record.provider_writes == 0
    assert record.send_count == 0


def test_dedupe_cites_the_existing_product_and_inserts_nothing() -> None:
    record = _open(IntakeLedger(), "DEDUPE_REJECTION")

    assert record.cited_product_id == _uuid(3)
    assert record.new_product_ids == ()
    assert [step.job_type for step in record.plan] == ["ReconceptProductJob"]
    assert record.jobs_inserted == 0


def test_interrupted_run_echoes_the_job_and_refuses_phase_zero() -> None:
    record = _open(IntakeLedger(), "AGENT_RUN_INTERRUPTED")

    assert record.resume_job_id == _uuid(8)
    assert record.resume_phase == 2
    with pytest.raises(SupportRefusal, match="resume_phase"):
        _open(IntakeLedger(), "AGENT_RUN_INTERRUPTED", resume_phase=0)


def test_no_sales_names_two_uninserted_steps_fourteen_days_apart() -> None:
    record = _open(IntakeLedger(), "NO_SALES_DIAGNOSIS")

    assert [(step.job_type, step.day_offset, step.inserted) for step in record.plan] == [
        ("ListingRepairJob", 0, False),
        ("ResearchCollectionJob", 14, False),
    ]
    assert record.plan[1].day_offset - record.plan[0].day_offset == 14


def test_deactivated_listing_keeps_the_notice_hash_and_does_not_reactivate() -> None:
    record = _open(IntakeLedger(), "LISTING_DEACTIVATED")

    assert record.notice_sha256 == _OTHER_HASH
    assert record.reactivation_executed is False


def test_resolve_requires_a_later_matching_read_from_another_job() -> None:
    closed = resolve_issue(_read())
    assert closed.status == "RESOLVED"
    assert closed.verification_job_id == _uuid(9)
    assert closed.resolution_reference == _HASH
    assert closed.send_count == 0

    still_open = resolve_issue(_read(fresh=_OTHER_HASH))
    assert still_open.status == "OPEN"
    assert still_open.verification_job_id is None
    assert still_open.resolution_reference is None
    assert still_open.resolved_at is None

    same_job = resolve_issue(_read(verification=7))
    assert same_job.status == "OPEN"


def test_draft_uses_only_the_verification_and_auto_sends_nothing() -> None:
    ledger = IntakeLedger()
    drafted = draft_reply(ledger, _read(), mode="draft")
    assert drafted.send_count == 0
    assert (
        drafted.body
        == "We received this once. the file hash is aaaa path-token-1 Reply if the issue remains."
    )
    assert drafted.body is not None
    assert drafted.body.count("We received this once.") == 1
    assert drafted.body.count("Reply if the issue remains.") == 1

    silent = draft_reply(ledger, _read(fresh=_OTHER_HASH), mode="draft")
    assert silent.body is None
    assert silent.send_count == 0

    auto = draft_reply(ledger, _read(), mode="auto")
    assert auto.body is None
    assert auto.send_count == 0
    assert ledger.sends == 0


def test_one_idempotency_key_keeps_one_repair_version() -> None:
    ledger = IntakeLedger()
    incident_id = _open(ledger).incident_id
    first = record_repair(
        ledger,
        incident_id=incident_id,
        idempotency_key="repair-1",
        artifact_hash=_HASH,
    )
    second = record_repair(
        ledger,
        incident_id=incident_id,
        idempotency_key="repair-1",
        artifact_hash=_OTHER_HASH,
    )

    assert second.version_id == first.version_id
    assert second.artifact_hash == _HASH
    assert ledger.repair_count(incident_id) == 1


def test_a16_stays_designed_and_the_module_does_not_call_out() -> None:
    import money_machine.assets.support_intake as intake

    block = (
        (_ROOT / "config" / "agents.yaml").read_text(encoding="utf-8").split("agent_id: A16", 1)[1]
    )
    assert "commissioning_state: DESIGNED" in block
    assert "commissioning_evidence: []" in block
    source = inspect.getsource(intake)
    modules: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    assert all("scheduler" not in module and "worker" not in module for module in modules)
    assert "socket" not in source
    assert "httpx" not in source
    assert "SESSION_11_SUPPORT_AND_REPAIR_COMPLETE" not in source
