"""Fixture failure injections for Session 13.

Each named failure ends in recovery or an exact blocked state. The runner
uses the retry policy, the listing receipt, the publishing ramp, the link
rules, and the selector catalogue. It does not open a socket, read a
credential, start the worker, or edit the scheduler.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from money_machine.assets.link_validation import refuse_graph_uri
from money_machine.assets.mutation_receipt import (
    ListingMutation,
    MutationReceipt,
    ReadObservation,
    ReceiptBook,
    WriteTimeout,
    commit_listing_mutation,
)
from money_machine.assets.publishing_ramp_decision import decide_publishing_ramp
from money_machine.domain.enums import JobStatus, RetryClass
from money_machine.integrations.notion.browser_session import BrowserSessionError, selector_text
from money_machine.orchestration.retry import RetryDecision, evaluate_retry

Disposition = Literal["RECOVERED", "BLOCKED"]
_NOW = datetime(2026, 10, 17, 14, 25, tzinfo=UTC)
_ACCEPTED_PDF = "https://www.notion.so/delivery-readme"
_WRONG_PDF = "https://www.notion.so/wrong-file"

INJECTIONS: tuple[str, ...] = (
    "worker_crash",
    "scheduler_restart",
    "database_reconnect",
    "expired_lease",
    "duplicate_event",
    "duplicate_publish_request",
    "provider_timeout_before_response",
    "provider_timeout_after_success",
    "expired_etsy_token",
    "expired_notion_session",
    "malformed_llm_output",
    "unavailable_llm_provider",
    "asset_render_failure",
    "wrong_pdf_link",
    "stale_product_facts",
    "browser_selector_change",
    "ramp_full",
    "spend_cap_reached",
)


class FailureInjectionError(ValueError):
    """A named injection did not end in its recovery or blocked state."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class InjectionOutcome:
    """One injection and the exact state it reached."""

    name: str
    disposition: Disposition
    state: str
    detail: str


@dataclass(frozen=True, slots=True)
class ScheduledJob:
    """One in-memory schedule row. A restart promotes due rows once."""

    job_id: str
    next_fire_at: datetime
    status: JobStatus


@dataclass(frozen=True, slots=True)
class HeldLease:
    """A lease that refuses work after it expires. The job is not executed."""

    job_id: str
    expires_at: datetime

    def run(self, now: datetime) -> bool:
        """Return whether the job may run. An expired lease returns false."""
        _require_aware(now)
        _require_aware(self.expires_at)
        return now < self.expires_at


@dataclass(frozen=True, slots=True)
class ListingFacts:
    """Fact version that listing copy is allowed to use."""

    spec_version: int
    fact_version: int


class EventLog:
    """In-memory events keyed by id. A second append returns the first body."""

    def __init__(self) -> None:
        self._bodies: dict[str, str] = {}

    def append(self, event_id: str, body: str) -> str:
        """Store a new id. A repeated id returns the stored body."""
        if event_id == "" or body == "":
            raise ValueError("event id and body are required")
        stored = self._bodies.get(event_id)
        if stored is not None:
            return stored
        self._bodies[event_id] = body
        return body

    def __len__(self) -> int:
        return len(self._bodies)


class DatabaseConnection:
    """A reconnect that fails once and then connects. No database is opened."""

    def __init__(self) -> None:
        self.attempts = 0
        self.status = "DOWN"

    def connect(self) -> str:
        """Record one attempt. The second attempt is CONNECTED."""
        self.attempts += 1
        if self.attempts == 1:
            self.status = "DOWN"
            return self.status
        self.status = "CONNECTED"
        return self.status


class ModelProvider:
    """A model boundary that refuses when it is unavailable. No network call."""

    def __init__(self, *, available: bool) -> None:
        self.available = available
        self.calls = 0

    def complete(self, prompt: str) -> str | None:
        """Return nothing when the provider is down. A live call is not made."""
        if prompt == "" or not self.available:
            return None
        self.calls += 1
        return prompt


class SpendLedger:
    """An in-memory spend cap. A zero balance records no spend."""

    def __init__(self, remaining_cents: int) -> None:
        if remaining_cents < 0:
            raise ValueError("remaining cannot be negative")
        self.remaining_cents = remaining_cents
        self.spent: tuple[int, ...] = ()

    def spend(self, cents: int) -> bool:
        """Record a positive spend that fits. A shortfall records nothing."""
        if cents <= 0:
            raise ValueError("spend must be positive")
        if cents > self.remaining_cents:
            return False
        self.remaining_cents -= cents
        self.spent = (*self.spent, cents)
        return True


class _ScriptedListing:
    """Listing double. The first create can time out. The read is scripted."""

    def __init__(self, *, fail_first: bool, observed_id: str | None) -> None:
        self.creates = 0
        self.fail_first = fail_first
        self.observed_id = observed_id

    def create(self, idempotency_key: str) -> str:
        self.creates += 1
        if self.fail_first and self.creates == 1:
            raise WriteTimeout(idempotency_key)
        return "provider-created"

    def read(self, idempotency_key: str) -> ReadObservation:
        del idempotency_key
        return ReadObservation(observed=True, provider_id=self.observed_id, unknown=False)


def recover_crashed_job(*, now: datetime) -> tuple[JobStatus, RetryDecision]:
    """A crashed RUNNING job fails, then a SAFE retry returns it to READY."""
    _require_aware(now)
    status = JobStatus.RUNNING
    status = JobStatus.FAILED
    decision = evaluate_retry(
        retry_class=RetryClass.SAFE,
        current_attempt=0,
        max_attempts=3,
        now=now,
    )
    if decision.can_retry and decision.scheduled_at is not None:
        status = JobStatus.READY
    if status is not JobStatus.READY or not decision.can_retry or decision.next_attempt != 1:
        raise FailureInjectionError("worker_crash")
    return status, decision


def restart_schedule(jobs: tuple[ScheduledJob, ...], now: datetime) -> tuple[ScheduledJob, ...]:
    """Promote each due job once. A repeated id is not queued again."""
    _require_aware(now)
    promoted: list[ScheduledJob] = []
    seen: set[str] = set()
    for job in jobs:
        if job.job_id in seen:
            continue
        seen.add(job.job_id)
        if job.next_fire_at <= now:
            promoted.append(ScheduledJob(job.job_id, job.next_fire_at, JobStatus.READY))
        else:
            promoted.append(job)
    return tuple(promoted)


def token_status(expires_at: datetime, now: datetime) -> str:
    """Return CREDENTIAL_EXPIRED when the supplied expiry is not in the future."""
    _require_aware(expires_at)
    _require_aware(now)
    if expires_at <= now:
        return "CREDENTIAL_EXPIRED"
    return "VALID"


def notion_session_status(expires_at: datetime, now: datetime) -> str:
    """Return SESSION_EXPIRED when the supplied session expiry has passed."""
    _require_aware(expires_at)
    _require_aware(now)
    if expires_at <= now:
        return "SESSION_EXPIRED"
    return "VALID"


def parse_model_output(payload: str) -> dict[str, str] | None:
    """Parse title and body. Missing or blank fields are not listing copy."""
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    title = decoded.get("title")
    body = decoded.get("body")
    if not isinstance(title, str) or title.strip() == "":
        return None
    if not isinstance(body, str) or body.strip() == "":
        return None
    return {"title": title, "body": body}


def render_png(png: bytes) -> str | None:
    """Return a memory URI for real bytes. Empty bytes write no URI."""
    if png == b"":
        return None
    return "memory://asset.png"


def listing_copy(facts: ListingFacts) -> str | None:
    """Return copy only when the fact version matches the spec version."""
    if facts.fact_version != facts.spec_version:
        return None
    return "Household reset planner"


def publish_duplicate() -> tuple[MutationReceipt, int]:
    """Commit one publish twice. The second call does not create again."""
    fixture = _ScriptedListing(fail_first=False, observed_id=None)
    book = ReceiptBook()
    mutation = _mutation("duplicate-publish")
    first = commit_listing_mutation(book, fixture, mutation)
    second = commit_listing_mutation(book, fixture, mutation)
    if first != second or fixture.creates != 1 or first.effect_state != "CONFIRMED":
        raise FailureInjectionError("duplicate_publish")
    return first, fixture.creates


def publish_timeout_before_response() -> tuple[MutationReceipt, int]:
    """A timeout with an absent read creates once more and confirms."""
    fixture = _ScriptedListing(fail_first=True, observed_id=None)
    receipt = commit_listing_mutation(ReceiptBook(), fixture, _mutation("timeout-before"))
    if fixture.creates != 2 or receipt.effect_state != "CONFIRMED":
        raise FailureInjectionError("timeout_before")
    if receipt.provider_id != "provider-created":
        raise FailureInjectionError("timeout_before")
    return receipt, fixture.creates


def publish_timeout_after_success() -> tuple[MutationReceipt, int]:
    """A timeout whose read already has an id does not create again."""
    fixture = _ScriptedListing(fail_first=True, observed_id="provider-observed")
    receipt = commit_listing_mutation(ReceiptBook(), fixture, _mutation("timeout-after"))
    if fixture.creates != 1 or receipt.effect_state != "CONFIRMED":
        raise FailureInjectionError("timeout_after")
    if receipt.provider_id != "provider-observed":
        raise FailureInjectionError("timeout_after")
    return receipt, fixture.creates


def run_failure_injections() -> tuple[InjectionOutcome, ...]:
    """Run every named injection. A second call returns the same outcomes."""
    outcomes = (
        _worker_crash(),
        _scheduler_restart(),
        _database_reconnect(),
        _expired_lease(),
        _duplicate_event(),
        _duplicate_publish(),
        _timeout_before(),
        _timeout_after(),
        _expired_etsy(),
        _expired_notion(),
        _malformed_output(),
        _unavailable_provider(),
        _render_failure(),
        _wrong_pdf(),
        _stale_facts(),
        _selector_change(),
        _ramp_full(),
        _spend_cap(),
    )
    if tuple(item.name for item in outcomes) != INJECTIONS:
        raise FailureInjectionError("injection_names")
    return outcomes


def _worker_crash() -> InjectionOutcome:
    status, decision = recover_crashed_job(now=_NOW)
    detail = (
        f"can_retry={str(decision.can_retry).lower()};"
        f"next_attempt={decision.next_attempt};status={status.value}"
    )
    return _outcome("worker_crash", "RECOVERED", status.value, detail)


def _scheduler_restart() -> InjectionOutcome:
    due = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)
    later = datetime(2026, 10, 17, 16, 0, tzinfo=UTC)
    jobs = (
        ScheduledJob("job-a", due, JobStatus.PENDING),
        ScheduledJob("job-a", due, JobStatus.PENDING),
        ScheduledJob("job-b", later, JobStatus.PENDING),
    )
    once = restart_schedule(jobs, _NOW)
    twice = restart_schedule(once, _NOW)
    ready = sum(job.status is JobStatus.READY for job in twice)
    if twice != once or len(twice) != 2 or ready != 1:
        raise FailureInjectionError("scheduler_restart")
    return _outcome(
        "scheduler_restart",
        "RECOVERED",
        JobStatus.READY.value,
        f"ready={ready};count={len(twice)}",
    )


def _database_reconnect() -> InjectionOutcome:
    connection = DatabaseConnection()
    first = connection.connect()
    second = connection.connect()
    if first != "DOWN" or second != "CONNECTED" or connection.attempts != 2:
        raise FailureInjectionError("database_reconnect")
    return _outcome(
        "database_reconnect",
        "RECOVERED",
        "CONNECTED",
        f"attempts={connection.attempts};status={connection.status}",
    )


def _expired_lease() -> InjectionOutcome:
    lease = HeldLease("job-lease", datetime(2026, 10, 17, 14, 0, tzinfo=UTC))
    executed = lease.run(_NOW)
    if executed:
        raise FailureInjectionError("expired_lease")
    return _outcome("expired_lease", "BLOCKED", "LEASE_EXPIRED", "executed=false")


def _duplicate_event() -> InjectionOutcome:
    log = EventLog()
    first = log.append("event-1", "listing.updated")
    second = log.append("event-1", "listing.updated.again")
    if first != second or len(log) != 1 or first != "listing.updated":
        raise FailureInjectionError("duplicate_event")
    return _outcome("duplicate_event", "RECOVERED", "DEDUPED", f"length={len(log)}")


def _duplicate_publish() -> InjectionOutcome:
    receipt, creates = publish_duplicate()
    return _outcome(
        "duplicate_publish_request",
        "RECOVERED",
        receipt.effect_state,
        f"creates={creates};effect={receipt.effect_state}",
    )


def _timeout_before() -> InjectionOutcome:
    receipt, creates = publish_timeout_before_response()
    return _outcome(
        "provider_timeout_before_response",
        "RECOVERED",
        receipt.effect_state,
        f"creates={creates};effect={receipt.effect_state}",
    )


def _timeout_after() -> InjectionOutcome:
    receipt, creates = publish_timeout_after_success()
    return _outcome(
        "provider_timeout_after_success",
        "RECOVERED",
        receipt.effect_state,
        f"creates={creates};effect={receipt.effect_state};provider={receipt.provider_id}",
    )


def _expired_etsy() -> InjectionOutcome:
    state = token_status(datetime(2026, 10, 16, tzinfo=UTC), _NOW)
    if state != "CREDENTIAL_EXPIRED":
        raise FailureInjectionError("expired_etsy_token")
    return _outcome(
        "expired_etsy_token", "BLOCKED", state, "read_env=false;state=CREDENTIAL_EXPIRED"
    )


def _expired_notion() -> InjectionOutcome:
    state = notion_session_status(datetime(2026, 10, 16, tzinfo=UTC), _NOW)
    if state != "SESSION_EXPIRED":
        raise FailureInjectionError("expired_notion_session")
    return _outcome(
        "expired_notion_session",
        "BLOCKED",
        state,
        "read_env=false;state=SESSION_EXPIRED",
    )


def _malformed_output() -> InjectionOutcome:
    parsed = parse_model_output('{"title": "Planner"}')
    if parsed is not None:
        raise FailureInjectionError("malformed_llm_output")
    return _outcome("malformed_llm_output", "BLOCKED", "MALFORMED_OUTPUT", "parsed=false")


def _unavailable_provider() -> InjectionOutcome:
    provider = ModelProvider(available=False)
    completed = provider.complete("write the listing")
    if completed is not None or provider.calls != 0:
        raise FailureInjectionError("unavailable_llm_provider")
    return _outcome(
        "unavailable_llm_provider",
        "BLOCKED",
        "PROVIDER_UNAVAILABLE",
        f"calls={provider.calls}",
    )


def _render_failure() -> InjectionOutcome:
    uri = render_png(b"")
    if uri is not None:
        raise FailureInjectionError("asset_render_failure")
    return _outcome("asset_render_failure", "BLOCKED", "RENDER_FAILED", "uri=")


def _wrong_pdf() -> InjectionOutcome:
    reason = refuse_graph_uri(_WRONG_PDF, accepted=frozenset({_ACCEPTED_PDF}))
    if reason != "link_mismatch":
        raise FailureInjectionError("wrong_pdf_link")
    return _outcome("wrong_pdf_link", "BLOCKED", "LINK_MISMATCH", f"reason={reason}")


def _stale_facts() -> InjectionOutcome:
    copy = listing_copy(ListingFacts(spec_version=2, fact_version=1))
    if copy is not None:
        raise FailureInjectionError("stale_product_facts")
    return _outcome("stale_product_facts", "BLOCKED", "STALE_FACTS", "copy=")


def _selector_change() -> InjectionOutcome:
    try:
        selector_text("listing_price_button")
    except BrowserSessionError as error:
        if str(error) != "selector is not known":
            raise FailureInjectionError("browser_selector_change") from error
    else:
        raise FailureInjectionError("browser_selector_change")
    return _outcome("browser_selector_change", "BLOCKED", "SELECTOR_UNKNOWN", "known=false")


def _ramp_full() -> InjectionOutcome:
    decision = decide_publishing_ramp(
        publishing_enabled=True,
        initial_weekly_cap=2,
        hard_weekly_cap=2,
        rolling_window_days=7,
        reconciled_count=2,
        oldest_reconciled_at=datetime(2026, 10, 10, tzinfo=UTC),
        unreconciled_count=0,
    )
    if decision.may_publish:
        raise FailureInjectionError("ramp_full")
    return _outcome(
        "ramp_full",
        "BLOCKED",
        "RAMP_FULL",
        f"may_publish={str(decision.may_publish).lower()}",
    )


def _spend_cap() -> InjectionOutcome:
    ledger = SpendLedger(0)
    recorded = ledger.spend(100)
    if recorded or ledger.spent:
        raise FailureInjectionError("spend_cap_reached")
    return _outcome("spend_cap_reached", "BLOCKED", "SPEND_CAP", "spent=0")


def _outcome(name: str, disposition: Disposition, state: str, detail: str) -> InjectionOutcome:
    return InjectionOutcome(name=name, disposition=disposition, state=state, detail=detail)


def _mutation(idempotency_key: str) -> ListingMutation:
    return ListingMutation(
        operation="create",
        listing_target="listing",
        pre_state="absent",
        expected_post_state="draft",
        idempotency_key=idempotency_key,
    )


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("timestamp must be timezone-aware")
