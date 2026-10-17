"""Each named failure ends in recovery or an exact blocked state."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

from money_machine.assets.failure_injection import (
    INJECTIONS,
    DatabaseConnection,
    EventLog,
    HeldLease,
    ListingFacts,
    ModelProvider,
    ScheduledJob,
    SpendLedger,
    listing_copy,
    parse_model_output,
    publish_duplicate,
    publish_timeout_after_success,
    publish_timeout_before_response,
    recover_crashed_job,
    render_png,
    restart_schedule,
    run_failure_injections,
    token_status,
)
from money_machine.domain.enums import JobStatus, RetryClass
from money_machine.orchestration.retry import evaluate_retry

_NOW = datetime(2026, 10, 17, 14, 25, tzinfo=UTC)
_MODULE = Path("src/money_machine/assets/failure_injection.py")
_EXPECTED = {
    "worker_crash": ("RECOVERED", "READY", "can_retry=true;next_attempt=1;status=READY"),
    "scheduler_restart": ("RECOVERED", "READY", "ready=1;count=2"),
    "database_reconnect": ("RECOVERED", "CONNECTED", "attempts=2;status=CONNECTED"),
    "expired_lease": ("BLOCKED", "LEASE_EXPIRED", "executed=false"),
    "duplicate_event": ("RECOVERED", "DEDUPED", "length=1"),
    "duplicate_publish_request": ("RECOVERED", "CONFIRMED", "creates=1;effect=CONFIRMED"),
    "provider_timeout_before_response": ("RECOVERED", "CONFIRMED", "creates=2;effect=CONFIRMED"),
    "provider_timeout_after_success": (
        "RECOVERED",
        "CONFIRMED",
        "creates=1;effect=CONFIRMED;provider=provider-observed",
    ),
    "expired_etsy_token": (
        "BLOCKED",
        "CREDENTIAL_EXPIRED",
        "read_env=false;state=CREDENTIAL_EXPIRED",
    ),
    "expired_notion_session": (
        "BLOCKED",
        "SESSION_EXPIRED",
        "read_env=false;state=SESSION_EXPIRED",
    ),
    "malformed_llm_output": ("BLOCKED", "MALFORMED_OUTPUT", "parsed=false"),
    "unavailable_llm_provider": ("BLOCKED", "PROVIDER_UNAVAILABLE", "calls=0"),
    "asset_render_failure": ("BLOCKED", "RENDER_FAILED", "uri="),
    "wrong_pdf_link": ("BLOCKED", "LINK_MISMATCH", "reason=link_mismatch"),
    "stale_product_facts": ("BLOCKED", "STALE_FACTS", "copy="),
    "browser_selector_change": ("BLOCKED", "SELECTOR_UNKNOWN", "known=false"),
    "ramp_full": ("BLOCKED", "RAMP_FULL", "may_publish=false"),
    "spend_cap_reached": ("BLOCKED", "SPEND_CAP", "spent=0"),
}


def test_every_named_injection_has_its_own_ending() -> None:
    outcomes = run_failure_injections()
    assert tuple(item.name for item in outcomes) == INJECTIONS
    assert run_failure_injections() == outcomes
    for item in outcomes:
        assert (item.disposition, item.state, item.detail) == _EXPECTED[item.name]
    assert {item.disposition for item in outcomes} == {"RECOVERED", "BLOCKED"}


def test_worker_crash_uses_the_safe_retry_policy() -> None:
    status, decision = recover_crashed_job(now=_NOW)
    direct = evaluate_retry(
        retry_class=RetryClass.SAFE,
        current_attempt=0,
        max_attempts=3,
        now=_NOW,
    )
    assert status is JobStatus.READY
    assert decision == direct
    assert decision.can_retry is True
    assert decision.next_attempt == 1
    assert decision.scheduled_at is not None


def test_scheduler_restart_promotes_a_due_job_once() -> None:
    due = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)
    later = datetime(2026, 10, 17, 16, 0, tzinfo=UTC)
    jobs = (
        ScheduledJob("job-a", due, JobStatus.PENDING),
        ScheduledJob("job-a", due, JobStatus.PENDING),
        ScheduledJob("job-b", later, JobStatus.PENDING),
    )
    once = restart_schedule(jobs, _NOW)
    twice = restart_schedule(once, _NOW)
    assert twice == once
    assert len(twice) == 2
    assert sum(job.status is JobStatus.READY for job in twice) == 1
    assert twice[1].status is JobStatus.PENDING


def test_database_reconnect_records_two_attempts() -> None:
    connection = DatabaseConnection()
    assert connection.connect() == "DOWN"
    assert connection.connect() == "CONNECTED"
    assert connection.attempts == 2


def test_expired_lease_does_not_execute() -> None:
    lease = HeldLease("job-lease", datetime(2026, 10, 17, 14, 0, tzinfo=UTC))
    assert lease.run(_NOW) is False


def test_duplicate_event_keeps_the_first_body() -> None:
    log = EventLog()
    assert log.append("event-1", "listing.updated") == "listing.updated"
    assert log.append("event-1", "listing.updated.again") == "listing.updated"
    assert len(log) == 1


def test_duplicate_publish_creates_once() -> None:
    receipt, creates = publish_duplicate()
    assert creates == 1
    assert receipt.effect_state == "CONFIRMED"
    assert receipt.provider_id == "provider-created"


def test_timeout_before_response_creates_the_absent_write_once() -> None:
    receipt, creates = publish_timeout_before_response()
    assert creates == 2
    assert receipt.effect_state == "CONFIRMED"
    assert receipt.provider_id == "provider-created"


def test_timeout_after_success_keeps_the_observed_id() -> None:
    receipt, creates = publish_timeout_after_success()
    assert creates == 1
    assert receipt.effect_state == "CONFIRMED"
    assert receipt.provider_id == "provider-observed"


def test_blocked_injections_do_not_invent_a_success() -> None:
    assert token_status(datetime(2026, 10, 16, tzinfo=UTC), _NOW) == "CREDENTIAL_EXPIRED"
    assert parse_model_output('{"title": "Planner"}') is None
    provider = ModelProvider(available=False)
    assert provider.complete("write the listing") is None
    assert provider.calls == 0
    assert render_png(b"") is None
    assert listing_copy(ListingFacts(spec_version=2, fact_version=1)) is None
    ledger = SpendLedger(0)
    assert ledger.spend(100) is False
    assert ledger.spent == ()


def test_module_imports_no_socket_and_reads_no_credential() -> None:
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    folded = " ".join(imported)
    for token in ("socket", "httpx", "urllib", "requests", "playwright", "dotenv", "os"):
        assert token not in folded
    source = _MODULE.read_text(encoding="utf-8")
    assert "worker.py" not in source
    assert "scheduler.py" not in source
