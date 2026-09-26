"""Browser session management from Session 06 prompt section 3.

Fixtures and a fake driver only. No network, no Notion, no Playwright launch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from money_machine.integrations.notion.browser_session import (
    PROFILE_ROOT,
    SCREENSHOT_ROOT,
    BrowserSessionError,
    BrowserSessionManager,
    ProfileStatus,
    profile_path,
    profile_status,
    selector_text,
)
from money_machine.observability.receipts import NotionOperationReceipt

_WHEN = datetime(2026, 9, 26, 21, 0, tzinfo=UTC)


class FakeDriver:
    """Records calls. Raises only what a test plants."""

    def __init__(self) -> None:
        self.opens: list[str] = []
        self.kinds: list[str] = []
        self.clicks: list[tuple[str, str]] = []
        self.reads: list[tuple[str, str]] = []
        self.screenshots: list[tuple[str, str]] = []
        self.closes: list[object] = []
        self.observes: list[str] = []
        self.page_kind_value: str | Exception = "normal"
        self.click_result: str | Exception = "applied"
        self.read_results: list[str | Exception] = ["ok"]
        self.observe_result: str | Exception = "applied"
        self.close_error: Exception | None = None
        self.screenshot_error: Exception | None = None
        self.open_result: object | None = None
        self._session = 0

    def open(self, profile_name: str) -> object:
        self.opens.append(profile_name)
        if self.open_result is not None:
            return self.open_result
        self._session += 1
        return f"session-{self._session}"

    def page_kind(self, session_id: str) -> str:
        self.kinds.append(session_id)
        if isinstance(self.page_kind_value, Exception):
            raise self.page_kind_value
        return self.page_kind_value

    def click(self, session_id: str, selector: str) -> str:
        self.clicks.append((session_id, selector))
        if isinstance(self.click_result, Exception):
            raise self.click_result
        return self.click_result

    def read(self, session_id: str, selector: str) -> str:
        self.reads.append((session_id, selector))
        if not self.read_results:
            raise TimeoutError("read timed out")
        item = self.read_results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def screenshot(self, session_id: str, path: str) -> None:
        self.screenshots.append((session_id, path))
        if self.screenshot_error is not None:
            raise self.screenshot_error

    def close(self, session_id: object) -> None:
        self.closes.append(session_id)
        if self.close_error is not None:
            raise self.close_error

    def observe(self, session_id: str) -> str:
        self.observes.append(session_id)
        if isinstance(self.observe_result, Exception):
            raise self.observe_result
        return self.observe_result


def _manager(driver: FakeDriver | None = None) -> tuple[BrowserSessionManager, FakeDriver]:
    fake = driver or FakeDriver()
    return BrowserSessionManager(fake), fake


def _open(manager: BrowserSessionManager, name: str = "shop-a") -> str:
    return manager.open_session(name, ProfileStatus.AUTHENTICATED)


def _mutate(
    manager: BrowserSessionManager,
    *,
    profile_name: str = "shop-a",
    operation: str = "publish_page",
    key: str = "job-1:publish_page",
) -> NotionOperationReceipt:
    return manager.mutate(
        profile_name,
        operation,
        job_id="job-1",
        workspace="workspace-1",
        target="page-1",
        idempotency_key=key,
        timestamp=_WHEN,
    )


def test_browser_profiles_stay_outside_git() -> None:
    ignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "runtime/browser-profiles/*" in ignore
    assert "!runtime/browser-profiles/.gitkeep" in ignore
    assert profile_path("shop-a") == "runtime/browser-profiles/shop-a"
    assert PROFILE_ROOT == "runtime/browser-profiles"
    assert SCREENSHOT_ROOT == "runtime/screenshots"


def test_profile_slug_is_accepted() -> None:
    assert profile_path("a") == "runtime/browser-profiles/a"
    assert profile_path("a1") == "runtime/browser-profiles/a1"
    assert profile_path("a-b") == "runtime/browser-profiles/a-b"
    assert profile_path("a" * 64) == f"runtime/browser-profiles/{'a' * 64}"


@pytest.mark.parametrize(
    ("name", "match"),
    [
        ("", "present"),
        (" a", "present"),
        ("a ", "present"),
        (1, "present"),
        ("A", "lowercase slug"),
        ("a/b", "lowercase slug"),
        ("..", "lowercase slug"),
        ("a..b", "lowercase slug"),
        ("-a", "hyphen"),
        ("a-", "hyphen"),
        ("a" * 65, "too long"),
        ("a\u00a0b", "control character"),
        ("a\nb", "control character"),
    ],
)
def test_profile_name_is_rejected(name: object, match: str) -> None:
    with pytest.raises(BrowserSessionError, match=match):
        profile_path(name)


def test_profile_status_requires_bool_flags() -> None:
    with pytest.raises(BrowserSessionError, match="bool"):
        profile_status(present=1, authenticated=False)
    with pytest.raises(BrowserSessionError, match="bool"):
        profile_status(present=True, authenticated=1)


def test_absent_profile_cannot_be_authenticated() -> None:
    with pytest.raises(BrowserSessionError, match="absent profile"):
        profile_status(present=False, authenticated=True)


def test_profile_status_values() -> None:
    assert profile_status(present=False, authenticated=False) is ProfileStatus.ABSENT
    assert profile_status(present=True, authenticated=False) is ProfileStatus.UNAUTHENTICATED
    assert profile_status(present=True, authenticated=True) is ProfileStatus.AUTHENTICATED


def test_selector_text_is_the_catalogue_value() -> None:
    assert selector_text("publish_toggle") == '[data-testid="publish-to-web"]'
    with pytest.raises(BrowserSessionError, match="selector is not known"):
        selector_text("css")
    with pytest.raises(BrowserSessionError, match="selector is not known"):
        selector_text(1)


@pytest.mark.parametrize(
    "status",
    [ProfileStatus.ABSENT, ProfileStatus.UNAUTHENTICATED],
)
def test_open_requires_an_authenticated_profile(status: ProfileStatus) -> None:
    manager, driver = _manager()
    with pytest.raises(BrowserSessionError, match="not authenticated"):
        manager.open_session("shop-a", status)
    assert driver.opens == []


def test_string_status_is_not_authenticated() -> None:
    manager, driver = _manager()
    with pytest.raises(BrowserSessionError, match="not authenticated"):
        manager.open_session("shop-a", "authenticated")  # type: ignore[arg-type]
    assert driver.opens == []


def test_healthy_session_is_reused() -> None:
    manager, driver = _manager()
    first = _open(manager)
    second = _open(manager)
    assert first == second == "session-1"
    assert driver.opens == ["shop-a"]


def test_two_profiles_are_not_the_same_session() -> None:
    manager, driver = _manager()
    first = _open(manager, "shop-a")
    second = _open(manager, "shop-b")
    assert first != second
    assert driver.opens == ["shop-a", "shop-b"]
    assert _open(manager, "shop-a") == first
    assert driver.opens == ["shop-a", "shop-b"]


def test_open_rejects_a_bad_session_id() -> None:
    manager, driver = _manager()
    driver.open_result = "../escape"
    with pytest.raises(BrowserSessionError, match="session id"):
        _open(manager)
    assert driver.closes == ["../escape"]
    driver.open_result = None
    assert _open(manager) == "session-1"
    assert driver.opens == ["shop-a", "shop-a"]


def test_open_rejects_a_bad_session_id_when_close_fails() -> None:
    manager, driver = _manager()
    driver.open_result = "../escape"
    driver.close_error = ConnectionError("down")
    with pytest.raises(BrowserSessionError, match="session id") as caught:
        _open(manager)
    assert isinstance(caught.value.__cause__, ConnectionError)
    assert driver.closes == ["../escape"]
    with pytest.raises(BrowserSessionError, match="profile is locked"):
        _open(manager)
    assert driver.opens == ["shop-a"]


def test_open_rejects_a_non_string_session_id() -> None:
    manager, driver = _manager()
    driver.open_result = 1
    with pytest.raises(BrowserSessionError, match="session id"):
        _open(manager)
    assert driver.closes == [1]
    assert driver.opens == ["shop-a"]


def test_open_rejects_an_invalid_profile_name() -> None:
    manager, driver = _manager()
    with pytest.raises(BrowserSessionError, match="lowercase slug"):
        manager.open_session("A", ProfileStatus.AUTHENTICATED)
    assert driver.opens == []


@pytest.mark.parametrize(
    ("operation", "selector"),
    [
        ("publish_page", '[data-testid="publish-to-web"]'),
        ("unpublish_page", '[data-testid="unpublish"]'),
        ("set_duplicate_as_template", '[data-testid="duplicate-as-template"]'),
        ("set_search_indexing", '[data-testid="search-indexing"]'),
    ],
)
def test_mutation_clicks_the_operation_selector(operation: str, selector: str) -> None:
    manager, driver = _manager()
    session_id = _open(manager)
    receipt = _mutate(manager, operation=operation, key=f"job-1:{operation}")
    assert receipt.status == "Success"
    assert receipt.evidence == "applied"
    assert receipt.operation == operation
    assert receipt.timestamp == _WHEN
    pre = receipt.pre_state
    assert pre is not None
    assert pre["session_id"] == session_id
    assert pre["profile"] == "shop-a"
    assert driver.clicks == [(session_id, selector)]
    assert driver.screenshots == []
    assert driver.observes == []
    assert len(manager.receipts) == 1


def test_replay_returns_the_same_receipt() -> None:
    manager, driver = _manager()
    _open(manager)
    first = _mutate(manager)
    second = _mutate(manager)
    assert second is first
    assert len(driver.clicks) == 1
    assert len(manager.receipts) == 1


def test_a_new_key_is_a_new_receipt() -> None:
    manager, _driver = _manager()
    _open(manager)
    first = _mutate(manager, key="one")
    second = _mutate(manager, key="two")
    assert first is not second
    assert len(manager.receipts) == 2


@pytest.mark.parametrize(
    "kind",
    ["captcha", "verification"],
)
def test_challenge_page_fails_closed(kind: str) -> None:
    manager, driver = _manager()
    _open(manager)
    driver.page_kind_value = kind
    receipt = _mutate(manager)
    assert receipt.status == "Failure"
    assert receipt.evidence == f"runtime/screenshots/session-1-{kind}.png"
    assert driver.clicks == []
    assert driver.observes == []
    assert len(driver.screenshots) == 1
    assert len(manager.receipts) == 1
    with pytest.raises(BrowserSessionError, match="restarted"):
        _mutate(manager, key="other")


def test_unknown_page_kind_is_not_clicked() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.page_kind_value = "login-wall"
    receipt = _mutate(manager)
    assert receipt.status == "Failure"
    assert receipt.evidence.endswith("-unknown-page.png")
    assert driver.clicks == []
    post = receipt.post_state
    assert post["click"] == "not-clicked"
    assert post["page_kind"] == "login-wall"
    with pytest.raises(BrowserSessionError, match="restarted"):
        _mutate(manager, key="other")


def test_uncertain_click_is_reconciled_when_applied() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.click_result = "uncertain"
    driver.observe_result = "applied"
    receipt = _mutate(manager)
    assert receipt.status == "Success"
    assert receipt.evidence == "reconciled"
    assert len(driver.clicks) == 1
    assert driver.observes == ["session-1"]
    assert driver.screenshots == []
    again = _mutate(manager, key="next")
    assert again.status == "Success"
    assert len(driver.clicks) == 2


def test_click_timeout_is_reconciled() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.click_result = TimeoutError("timed out")
    driver.observe_result = "applied"
    receipt = _mutate(manager)
    assert receipt.status == "Success"
    assert receipt.evidence == "reconciled"
    assert len(driver.clicks) == 1
    assert len(driver.observes) == 1


def test_uncertain_click_absent_is_a_failure() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.click_result = "uncertain"
    driver.observe_result = "absent"
    receipt = _mutate(manager)
    assert receipt.status == "Failure"
    assert receipt.evidence == "runtime/screenshots/session-1-uncertain.png"
    assert receipt.post_state["observed"] == "absent"
    assert len(driver.clicks) == 1
    with pytest.raises(BrowserSessionError, match="restarted"):
        _mutate(manager, key="other")


def test_uncertain_click_unknown_stays_unknown() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.click_result = "uncertain"
    driver.observe_result = "unknown"
    receipt = _mutate(manager)
    assert receipt.status == "Unknown"
    assert receipt.post_state["observed"] == "unknown"
    assert len(driver.clicks) == 1
    with pytest.raises(BrowserSessionError, match="restarted"):
        _mutate(manager, key="other")


def test_garbage_observe_result_is_unknown() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.click_result = "uncertain"
    driver.observe_result = "maybe"
    receipt = _mutate(manager)
    assert receipt.status == "Unknown"
    assert receipt.post_state["observed"] == "unknown"
    with pytest.raises(BrowserSessionError, match="restarted"):
        _mutate(manager, key="other")


def test_observe_timeout_is_unknown() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.click_result = "uncertain"
    driver.observe_result = TimeoutError("observe timed out")
    receipt = _mutate(manager)
    assert receipt.status == "Unknown"
    assert len(manager.receipts) == 1
    assert driver.screenshots != []
    with pytest.raises(BrowserSessionError, match="restarted"):
        _mutate(manager, key="other")


def test_connection_error_does_not_observe() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.click_result = ConnectionError("down")
    receipt = _mutate(manager)
    assert receipt.status == "Failure"
    assert receipt.evidence.endswith("-connection.png")
    assert receipt.post_state["click"] == "connection"
    assert driver.observes == []
    assert len(driver.clicks) == 1
    assert len(manager.receipts) == 1


def test_click_runtime_error_is_one_failure_receipt() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.click_result = RuntimeError("boom")
    receipt = _mutate(manager)
    assert receipt.status == "Failure"
    assert receipt.evidence.endswith("-error.png")
    assert receipt.post_state["click"] == "error"
    assert driver.observes == []
    assert len(manager.receipts) == 1


def test_screenshot_failure_still_records_one_receipt() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.page_kind_value = "captcha"
    driver.screenshot_error = RuntimeError("disk")
    receipt = _mutate(manager)
    assert receipt.status == "Failure"
    assert receipt.evidence == "screenshot-failed"
    assert len(manager.receipts) == 1


def test_replay_after_failure_does_not_click() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.page_kind_value = "captcha"
    first = _mutate(manager)
    second = _mutate(manager)
    assert second is first
    assert driver.clicks == []
    assert len(manager.receipts) == 1


def test_mutate_before_open_records_nothing() -> None:
    manager, driver = _manager()
    with pytest.raises(BrowserSessionError, match="not open"):
        _mutate(manager)
    assert manager.receipts == ()
    assert driver.clicks == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("job_id", ""),
        ("job_id", " job"),
        ("workspace", ""),
        ("target", "page "),
        ("idempotency_key", ""),
    ],
)
def test_mutation_tokens_must_be_present(field: str, value: str) -> None:
    manager, driver = _manager()
    _open(manager)
    kwargs: dict[str, object] = {
        "job_id": "job-1",
        "workspace": "workspace-1",
        "target": "page-1",
        "idempotency_key": "key-1",
        "timestamp": _WHEN,
    }
    kwargs[field] = value
    with pytest.raises(BrowserSessionError, match="present"):
        manager.mutate("shop-a", "publish_page", **kwargs)  # type: ignore[arg-type]
    assert driver.clicks == []
    assert manager.receipts == ()


def test_naive_timestamp_is_rejected() -> None:
    manager, driver = _manager()
    _open(manager)
    with pytest.raises(BrowserSessionError, match="timezone-aware"):
        manager.mutate(
            "shop-a",
            "publish_page",
            job_id="job-1",
            workspace="workspace-1",
            target="page-1",
            idempotency_key="key-1",
            timestamp=datetime(2026, 9, 26, 21, 0),
        )
    assert driver.kinds == []


def test_unknown_operation_is_rejected() -> None:
    manager, driver = _manager()
    _open(manager)
    with pytest.raises(BrowserSessionError, match="operation"):
        _mutate(manager, operation="delete_workspace")
    assert driver.kinds == []
    assert manager.receipts == ()


def test_receipts_property_is_a_tuple() -> None:
    manager, _driver = _manager()
    _open(manager)
    _mutate(manager)
    assert isinstance(manager.receipts, tuple)


def test_read_retries_timeout_then_returns() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.read_results = [TimeoutError("one"), TimeoutError("two"), "url"]
    assert manager.read("shop-a", "public_url") == "url"
    assert len(driver.reads) == 3
    assert driver.screenshots == []
    assert manager.receipts == ()
    assert driver.reads[0][1] == '[data-testid="public-url-display"]'


def test_read_stops_after_three_timeouts() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.read_results = [TimeoutError("x"), TimeoutError("y"), TimeoutError("z"), "late"]
    with pytest.raises(BrowserSessionError, match="read timed out"):
        manager.read("shop-a", "share_menu")
    assert len(driver.reads) == 3
    assert driver.screenshots[0][1].endswith("-timeout.png")
    with pytest.raises(BrowserSessionError, match="restarted"):
        manager.read("shop-a", "share_menu")


def test_read_does_not_retry_a_connection_error() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.read_results = [ConnectionError("down"), "url"]
    with pytest.raises(BrowserSessionError, match="connection failed"):
        manager.read("shop-a", "public_url")
    assert len(driver.reads) == 1
    assert driver.screenshots[0][1].endswith("-connection.png")
    assert manager.receipts == ()


def test_read_rejects_a_mutation_selector() -> None:
    manager, driver = _manager()
    with pytest.raises(BrowserSessionError, match="not readable"):
        manager.read("shop-a", "publish_toggle")
    assert driver.reads == []
    assert driver.opens == []


def test_restart_rejects_an_invalid_profile_name() -> None:
    manager, driver = _manager()
    with pytest.raises(BrowserSessionError, match="lowercase slug"):
        manager.restart("A")
    assert driver.closes == []


def test_restart_closes_and_opens_a_new_session() -> None:
    manager, driver = _manager()
    first = _open(manager)
    manager.restart("shop-a")
    assert driver.closes == [first]
    second = _open(manager)
    assert second == "session-2"
    assert driver.opens == ["shop-a", "shop-a"]


def test_failed_restart_locks_the_profile() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.close_error = ConnectionError("down")
    with pytest.raises(BrowserSessionError, match="restart failed") as caught:
        manager.restart("shop-a")
    assert isinstance(caught.value.__cause__, ConnectionError)
    with pytest.raises(BrowserSessionError, match="profile is locked"):
        manager.restart("shop-a")
    with pytest.raises(BrowserSessionError, match="profile is locked"):
        _open(manager)
    assert driver.opens == ["shop-a"]


def test_restart_without_a_session_is_rejected() -> None:
    manager, _driver = _manager()
    with pytest.raises(BrowserSessionError, match="no session to restart"):
        manager.restart("shop-a")


def test_tainted_session_is_not_reused_until_restart() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.page_kind_value = "captcha"
    _mutate(manager)
    with pytest.raises(BrowserSessionError, match="restarted"):
        _open(manager)
    driver.page_kind_value = "normal"
    manager.restart("shop-a")
    assert _open(manager) == "session-2"
    receipt = _mutate(manager, key="after")
    assert receipt.status == "Success"


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("observe"),
        ValueError("observe"),
        OSError("observe"),
        ConnectionError("observe"),
    ],
    ids=["RuntimeError", "ValueError", "OSError", "ConnectionError"],
)
def test_observe_exception_is_one_unknown_receipt(error: Exception) -> None:
    manager, driver = _manager()
    _open(manager)
    driver.click_result = "uncertain"
    driver.observe_result = error
    receipt = _mutate(manager)
    assert receipt.status == "Unknown"
    assert len(manager.receipts) == 1
    assert len(driver.clicks) == 1
    replay = _mutate(manager)
    assert replay is receipt
    assert len(driver.clicks) == 1
    with pytest.raises(BrowserSessionError, match="restarted"):
        _mutate(manager, key="other")


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (RuntimeError("kind"), "error"),
        (TimeoutError("kind"), "timeout"),
        (ConnectionError("kind"), "connection"),
    ],
    ids=["error", "timeout", "connection"],
)
def test_page_kind_error_records_one_receipt(error: Exception, reason: str) -> None:
    manager, driver = _manager()
    _open(manager)
    driver.page_kind_value = error
    receipt = _mutate(manager)
    assert receipt.status == "Failure"
    assert receipt.post_state["page_kind"] == "unknown"
    assert receipt.post_state["click"] == reason
    assert str(receipt.evidence).endswith(f"-{reason}.png")
    assert driver.clicks == []
    assert len(manager.receipts) == 1
    assert len(driver.kinds) == 1
    replay = _mutate(manager)
    assert replay is receipt
    assert len(driver.kinds) == 1
    with pytest.raises(BrowserSessionError, match="restarted"):
        _mutate(manager, key="other")


def test_locked_profile_blocks_mutate_and_read() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.close_error = ConnectionError("down")
    with pytest.raises(BrowserSessionError, match="restart failed"):
        manager.restart("shop-a")
    with pytest.raises(BrowserSessionError, match="profile is locked"):
        _mutate(manager)
    with pytest.raises(BrowserSessionError, match="profile is locked"):
        manager.read("shop-a", "public_url")
    assert driver.clicks == []
    assert driver.reads == []


def test_unknown_click_result_is_one_error_receipt() -> None:
    manager, driver = _manager()
    _open(manager)
    driver.click_result = "maybe"
    receipt = _mutate(manager)
    assert receipt.status == "Failure"
    assert receipt.post_state["click"] == "error"
    assert str(receipt.evidence).endswith("-error.png")
    assert len(manager.receipts) == 1
    assert len(driver.clicks) == 1


def test_idempotency_key_is_bound_to_the_call() -> None:
    manager, driver = _manager()
    _open(manager)
    first = _mutate(manager)
    mismatches: tuple[dict[str, object], ...] = (
        {"profile_name": "shop-b"},
        {"operation": "unpublish_page"},
        {"job_id": "job-2"},
        {"workspace": "workspace-2"},
        {"target": "page-2"},
    )
    for extra in mismatches:
        kwargs: dict[str, object] = {
            "profile_name": "shop-a",
            "operation": "publish_page",
            "job_id": "job-1",
            "workspace": "workspace-1",
            "target": "page-1",
            "idempotency_key": "job-1:publish_page",
            "timestamp": _WHEN,
        }
        kwargs.update(extra)
        with pytest.raises(BrowserSessionError, match="does not match"):
            manager.mutate(
                str(kwargs["profile_name"]),
                str(kwargs["operation"]),
                job_id=kwargs["job_id"],
                workspace=kwargs["workspace"],
                target=kwargs["target"],
                idempotency_key=kwargs["idempotency_key"],
                timestamp=kwargs["timestamp"],
            )
    assert len(driver.clicks) == 1
    assert len(driver.kinds) == 1
    assert _mutate(manager) is first


def test_operation_must_be_a_string() -> None:
    manager, driver = _manager()
    _open(manager)
    with pytest.raises(BrowserSessionError, match="operation"):
        manager.mutate(
            "shop-a",
            ["publish_page"],  # type: ignore[arg-type]
            job_id="job-1",
            workspace="workspace-1",
            target="page-1",
            idempotency_key="key-1",
            timestamp=_WHEN,
        )
    assert driver.kinds == []
    assert manager.receipts == ()


def test_timestamp_must_be_a_datetime() -> None:
    manager, driver = _manager()
    _open(manager)
    with pytest.raises(BrowserSessionError, match="timezone-aware"):
        manager.mutate(
            "shop-a",
            "publish_page",
            job_id="job-1",
            workspace="workspace-1",
            target="page-1",
            idempotency_key="key-1",
            timestamp="2026-09-26T21:00:00+00:00",
        )
    assert driver.kinds == []
    assert manager.receipts == ()


def test_session_module_does_not_reference_playwright() -> None:
    source = Path("src/money_machine/integrations/notion/browser_session.py").read_text(
        encoding="utf-8"
    )
    assert "playwright" not in source.lower()
    assert "urllib" not in source
    assert "socket" not in source
