"""Navigation guard for the Session 07 sandbox and anonymous Notion sessions.

This does not replace ``TranslatingBrowserSession.navigate``. That wiring is a
later phase. Callers that already have a page view can ask whether a click is
allowed; a refusal performs zero clicks.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

from money_machine.cli.notion_sandbox_guard import (
    SANDBOX_PARENT_PAGE_ID,
    SANDBOX_SPACE_ID,
    PageView,
    canonical_id,
)

SANDBOX_HOST = "www.notion.so"
ANONYMOUS_HOST_SUFFIX = "notion.site"


class NavigationGuardError(RuntimeError):
    """The page is not an allowed navigation target."""


class SandboxSessionSignedOut(NavigationGuardError):
    """The sandbox session has no signed-in page."""


@dataclass(frozen=True)
class NavigationRequest:
    """One proposed click. ``listed_urls`` is the operator allowlist."""

    role: str
    signed_in: bool
    listed_urls: frozenset[str]
    expected_page_id: str
    page: PageView | None


def _page_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        return ""
    return canonical_id(segments[-1])


def guard_navigation(request: NavigationRequest, click: Callable[[], None]) -> None:
    """Click only when the loaded page matches the session role. Otherwise raise first."""
    if request.role == "sandbox" and not request.signed_in:
        raise SandboxSessionSignedOut("sandbox session is signed out")
    if request.role == "anonymous" and request.signed_in:
        raise NavigationGuardError("anonymous session must not be signed in")
    if request.role not in {"sandbox", "anonymous"}:
        raise NavigationGuardError("unknown session role")
    page = request.page
    if page is None:
        raise NavigationGuardError("page did not load")
    parsed = urlparse(page.url)
    host = parsed.hostname or ""
    if request.role == "sandbox" and host != SANDBOX_HOST:
        raise NavigationGuardError("sandbox navigation must stay on www.notion.so")
    if (
        request.role == "anonymous"
        and host != ANONYMOUS_HOST_SUFFIX
        and not host.endswith(f".{ANONYMOUS_HOST_SUFFIX}")
    ):
        raise NavigationGuardError("anonymous navigation must stay on notion.site")
    if page.url not in request.listed_urls:
        raise NavigationGuardError("public url is not listed")
    loaded_id = _page_id_from_url(page.url)
    expected = canonical_id(request.expected_page_id)
    page_id = canonical_id(page.page_id)
    if loaded_id == "" or loaded_id != expected or loaded_id != page_id:
        raise NavigationGuardError("loaded page id does not match the canonical id")
    if request.role == "sandbox":
        if canonical_id(page.space_id) != SANDBOX_SPACE_ID:
            raise NavigationGuardError("page is in a foreign space")
        parent = canonical_id(page.parent_id)
        if parent != SANDBOX_PARENT_PAGE_ID and page_id != SANDBOX_PARENT_PAGE_ID:
            raise NavigationGuardError("parent chain does not reach the sandbox parent")
    click()
