"""Browser session management.

Session 06 prompt heading "### 3. Implement browser session management"
(``prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md``).

Profiles stay under ``runtime/browser-profiles``, which git ignores.
Screenshots stay under ``runtime/screenshots``. A profile is reused only
while it is authenticated, open, and healthy. A read retries a timeout and
does not retry a connection failure. A mutation is not clicked twice. An
uncertain click is reconciled by observing, and a captcha or verification
page fails closed. Each mutation records one receipt. This module does not
launch a browser engine, open a network connection, or write a cookie file.
A driver is injected.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from money_machine.observability.receipts import NotionOperationReceipt, ReceiptStatus

PROFILE_ROOT = "runtime/browser-profiles"
SCREENSHOT_ROOT = "runtime/screenshots"
_MAX_READ_ATTEMPTS = 3
_FORBIDDEN_NAME_CATEGORIES: frozenset[str] = frozenset({"Cc", "Cf", "Zl", "Zp", "Zs"})
_SCREENSHOT_REASONS: frozenset[str] = frozenset(
    {
        "captcha",
        "verification",
        "unknown-page",
        "timeout",
        "connection",
        "uncertain",
        "error",
    }
)
_SELECTORS: dict[str, str] = {
    "publish_toggle": '[data-testid="publish-to-web"]',
    "unpublish_toggle": '[data-testid="unpublish"]',
    "duplicate_template": '[data-testid="duplicate-as-template"]',
    "search_indexing": '[data-testid="search-indexing"]',
    "public_url": '[data-testid="public-url-display"]',
    "share_menu": '[data-testid="share-menu"]',
}
_OPERATION_SELECTORS: dict[str, str] = {
    "publish_page": "publish_toggle",
    "unpublish_page": "unpublish_toggle",
    "set_duplicate_as_template": "duplicate_template",
    "set_search_indexing": "search_indexing",
}
_READ_SELECTORS: frozenset[str] = frozenset({"public_url", "share_menu"})


class BrowserSessionError(Exception):
    """Fail-closed session error. No browser is launched."""


class ProfileStatus(Enum):
    """Authenticated-profile status. Callers pass the member, not its text."""

    ABSENT = "absent"
    UNAUTHENTICATED = "unauthenticated"
    AUTHENTICATED = "authenticated"


class BrowserDriver(Protocol):
    """Injected browser boundary. Tests pass a fake. Production is out of scope."""

    def open(self, profile_name: str) -> str:
        """Open one profile and return its session id."""
        ...

    def page_kind(self, session_id: str) -> str:
        """Return normal, captcha, verification, or another page kind."""
        ...

    def click(self, session_id: str, selector: str) -> str:
        """Click one selector. Return applied or uncertain."""
        ...

    def read(self, session_id: str, selector: str) -> str:
        """Read one selector."""
        ...

    def screenshot(self, session_id: str, path: str) -> None:
        """Capture one screenshot at a caller-built path."""
        ...

    def close(self, session_id: str) -> None:
        """Close one session."""
        ...

    def observe(self, session_id: str) -> str:
        """Reconcile an uncertain click: applied, absent, or unknown."""
        ...


@dataclass(slots=True)
class _OpenSession:
    profile_name: str
    session_id: str
    healthy: bool
    locked: bool


def profile_status(*, present: object, authenticated: object) -> ProfileStatus:
    """Return absent, unauthenticated, or authenticated. Flags must be bool."""
    if not isinstance(present, bool) or not isinstance(authenticated, bool):
        raise BrowserSessionError("profile flags must be bool")
    if authenticated and not present:
        raise BrowserSessionError("absent profile cannot be authenticated")
    if not present:
        return ProfileStatus.ABSENT
    if not authenticated:
        return ProfileStatus.UNAUTHENTICATED
    return ProfileStatus.AUTHENTICATED


def profile_path(name: object) -> str:
    """Return the gitignored profile directory for one slug."""
    if not isinstance(name, str) or name == "" or name != name.strip():
        raise BrowserSessionError("profile name must be present")
    if any(unicodedata.category(char) in _FORBIDDEN_NAME_CATEGORIES for char in name):
        raise BrowserSessionError("profile name must not contain a control character")
    _slug(name, "profile name")
    return f"{PROFILE_ROOT}/{name}"


def selector_text(name: object) -> str:
    """Return the selector string for a known logical name."""
    if not isinstance(name, str) or name not in _SELECTORS:
        raise BrowserSessionError("selector is not known")
    return _SELECTORS[name]


def _slug(value: str, label: str) -> None:
    if len(value) > 64:
        raise BrowserSessionError(f"{label} is too long")
    if value.startswith("-") or value.endswith("-"):
        raise BrowserSessionError(f"{label} must not start or end with a hyphen")
    if not all(_slug_char(char) for char in value):
        raise BrowserSessionError(f"{label} must be a lowercase slug")


def _slug_char(char: str) -> bool:
    return char.isascii() and (char.islower() or char.isdigit() or char == "-")


def _require_token(label: str, value: object) -> str:
    if not isinstance(value, str) or value == "" or value != value.strip():
        raise BrowserSessionError(f"{label} must be present")
    return value


def _require_timestamp(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise BrowserSessionError("timestamp must be timezone-aware")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise BrowserSessionError("timestamp must be timezone-aware")
    return value


def _require_session_id(value: object) -> str:
    if not isinstance(value, str) or value == "":
        raise BrowserSessionError("session id must be present")
    _slug(value, "session id")
    return value


class BrowserSessionManager:
    """One in-process session policy. The driver performs no live browser work here."""

    def __init__(self, driver: BrowserDriver) -> None:
        self._driver = driver
        self._open: dict[str, _OpenSession] = {}
        self._receipts: list[NotionOperationReceipt] = []
        self._seen: dict[str, NotionOperationReceipt] = {}

    @property
    def receipts(self) -> tuple[NotionOperationReceipt, ...]:
        """Receipts recorded by this manager, in order."""
        return tuple(self._receipts)

    def open_session(self, profile_name: str, status: ProfileStatus) -> str:
        """Open an authenticated profile, or reuse its healthy session."""
        profile_path(profile_name)
        if status is not ProfileStatus.AUTHENTICATED:
            raise BrowserSessionError("profile is not authenticated")
        current = self._open.get(profile_name)
        if current is not None and current.locked:
            raise BrowserSessionError("profile is locked")
        if current is not None and not current.healthy:
            raise BrowserSessionError("session must be restarted")
        if current is not None:
            return current.session_id
        session_id = _require_session_id(self._driver.open(profile_name))
        self._open[profile_name] = _OpenSession(
            profile_name=profile_name,
            session_id=session_id,
            healthy=True,
            locked=False,
        )
        return session_id

    def restart(self, profile_name: str) -> None:
        """Close the session. A failed close locks the profile."""
        profile_path(profile_name)
        current = self._open.get(profile_name)
        if current is None:
            raise BrowserSessionError("no session to restart")
        if current.locked:
            raise BrowserSessionError("profile is locked")
        try:
            self._driver.close(current.session_id)
        except Exception as exc:
            current.locked = True
            raise BrowserSessionError("restart failed") from exc
        self._open.pop(profile_name)

    def read(self, profile_name: str, selector_name: str) -> str:
        """Read a known selector. A timeout is retried. A connection error is not."""
        if selector_name not in _READ_SELECTORS:
            raise BrowserSessionError("selector is not readable")
        session = self._require_open(profile_name)
        selector = selector_text(selector_name)
        last_timeout: TimeoutError | None = None
        for _ in range(_MAX_READ_ATTEMPTS):
            try:
                return self._driver.read(session.session_id, selector)
            except TimeoutError as exc:
                last_timeout = exc
            except ConnectionError as exc:
                self._note_error(session, "connection")
                raise BrowserSessionError("connection failed") from exc
        self._note_error(session, "timeout")
        raise BrowserSessionError("read timed out") from last_timeout

    def mutate(
        self,
        profile_name: str,
        operation: str,
        *,
        job_id: object,
        workspace: object,
        target: object,
        idempotency_key: object,
        timestamp: object,
    ) -> NotionOperationReceipt:
        """Run one mutation and record exactly one receipt."""
        job = _require_token("job id", job_id)
        space = _require_token("workspace", workspace)
        page = _require_token("target", target)
        key = _require_token("idempotency key", idempotency_key)
        moment = _require_timestamp(timestamp)
        selector = _mutation_selector(operation)
        existing = self._seen.get(key)
        if existing is not None:
            return existing
        session = self._require_open(profile_name)
        kind = self._driver.page_kind(session.session_id)
        if kind == "captcha":
            return self._block(session, job, operation, space, page, key, moment, kind, "captcha")
        if kind == "verification":
            return self._block(
                session, job, operation, space, page, key, moment, kind, "verification"
            )
        if kind != "normal":
            return self._block(
                session, job, operation, space, page, key, moment, kind, "unknown-page"
            )
        outcome = self._click(session, selector)
        if outcome == "applied":
            return self._record(
                session,
                job,
                operation,
                space,
                page,
                key,
                moment,
                status="Success",
                evidence="applied",
                click="applied",
                observed="not-observed",
                kind=kind,
                taint=False,
            )
        if outcome == "uncertain":
            return self._reconcile(session, job, operation, space, page, key, moment, kind)
        return self._block(session, job, operation, space, page, key, moment, kind, outcome)

    def _require_open(self, profile_name: str) -> _OpenSession:
        current = self._open.get(profile_name)
        if current is None:
            raise BrowserSessionError("session is not open")
        if current.locked:
            raise BrowserSessionError("profile is locked")
        if not current.healthy:
            raise BrowserSessionError("session must be restarted")
        return current

    def _click(self, session: _OpenSession, selector: str) -> str:
        try:
            outcome = self._driver.click(session.session_id, selector)
        except TimeoutError:
            return "uncertain"
        except ConnectionError:
            return "connection"
        except Exception:
            return "error"
        if outcome in {"applied", "uncertain"}:
            return outcome
        return "error"

    def _reconcile(
        self,
        session: _OpenSession,
        job: str,
        operation: str,
        workspace: str,
        target: str,
        key: str,
        timestamp: datetime,
        kind: str,
    ) -> NotionOperationReceipt:
        try:
            observed = self._driver.observe(session.session_id)
        except (TimeoutError, ConnectionError):
            observed = "unknown"
        if observed == "applied":
            return self._record(
                session,
                job,
                operation,
                workspace,
                target,
                key,
                timestamp,
                status="Success",
                evidence="reconciled",
                click="uncertain",
                observed="applied",
                kind=kind,
                taint=False,
            )
        if observed == "absent":
            status: ReceiptStatus = "Failure"
        else:
            status = "Unknown"
        evidence = self._capture(session, "uncertain")
        return self._record(
            session,
            job,
            operation,
            workspace,
            target,
            key,
            timestamp,
            status=status,
            evidence=evidence,
            click="uncertain",
            observed=observed if observed in {"absent", "unknown"} else "unknown",
            kind=kind,
            taint=True,
        )

    def _block(
        self,
        session: _OpenSession,
        job: str,
        operation: str,
        workspace: str,
        target: str,
        key: str,
        timestamp: datetime,
        kind: str,
        reason: str,
    ) -> NotionOperationReceipt:
        evidence = self._capture(session, reason)
        click = "not-clicked" if reason in {"captcha", "verification", "unknown-page"} else reason
        return self._record(
            session,
            job,
            operation,
            workspace,
            target,
            key,
            timestamp,
            status="Failure",
            evidence=evidence,
            click=click,
            observed="not-observed",
            kind=kind,
            taint=True,
        )

    def _note_error(self, session: _OpenSession, reason: str) -> None:
        session.healthy = False
        self._capture(session, reason)

    def _capture(self, session: _OpenSession, reason: str) -> str:
        if reason not in _SCREENSHOT_REASONS:
            raise BrowserSessionError("screenshot reason is not known")
        path = f"{SCREENSHOT_ROOT}/{session.session_id}-{reason}.png"
        try:
            self._driver.screenshot(session.session_id, path)
        except Exception:
            return "screenshot-failed"
        return path

    def _record(
        self,
        session: _OpenSession,
        job: str,
        operation: str,
        workspace: str,
        target: str,
        key: str,
        timestamp: datetime,
        *,
        status: ReceiptStatus,
        evidence: str,
        click: str,
        observed: str,
        kind: str,
        taint: bool,
    ) -> NotionOperationReceipt:
        if taint:
            session.healthy = False
        receipt = NotionOperationReceipt(
            job_id=job,
            operation=operation,
            workspace=workspace,
            target=target,
            pre_state={"profile": session.profile_name, "session_id": session.session_id},
            post_state={"click": click, "observed": observed, "page_kind": kind},
            provider_response={"page_kind": kind, "click": click, "observed": observed},
            evidence=evidence,
            timestamp=timestamp,
            idempotency_key=key,
            status=status,
        )
        self._receipts.append(receipt)
        self._seen[key] = receipt
        return receipt


def _mutation_selector(operation: object) -> str:
    if not isinstance(operation, str):
        raise BrowserSessionError("operation is not a browser mutation")
    logical = _OPERATION_SELECTORS.get(operation)
    if logical is None:
        raise BrowserSessionError("operation is not a browser mutation")
    return selector_text(logical)
