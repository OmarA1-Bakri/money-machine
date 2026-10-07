"""Live Notion reads and child-page writes for the sandbox parent only.

Tests do not construct this client. The runner does, and only when no fake
client was injected.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable, Mapping
from typing import Protocol, cast

from money_machine.cli.notion_sandbox_guard import (
    SANDBOX_PARENT_PAGE_ID,
    SANDBOX_SPACE_ID,
    BotView,
    PageView,
    SandboxError,
    canonical_id,
    empty_write_counts,
    leaks,
    parent_is_allowed,
    redact_text,
)

NOTION_API_ORIGIN = "https://api.notion.com"
NOTION_VERSION = "2026-03-11"
_TIMEOUT_SECONDS = 30


class _Readable(Protocol):
    def read(self) -> bytes:
        """Return the response body."""
        ...

    def close(self) -> None:
        """Close the response."""
        ...


class LiveSandboxClient:
    """Official API client. The token stays on the Authorization header."""

    def __init__(self, token: str, opener: Callable[..., _Readable] | None = None) -> None:
        self._token = token
        self._opener = (
            opener if opener is not None else cast(Callable[..., _Readable], urllib.request.urlopen)
        )
        self._bot_space = ""
        self._created_ids: list[str] = []
        self.write_counts: dict[str, int] = empty_write_counts()

    def __repr__(self) -> str:
        return "LiveSandboxClient"

    def read_bot(self) -> BotView:
        payload = self._send("GET", "/v1/users/me", None)
        bot = parse_bot(payload)
        if bot is None:
            raise SandboxError("notion api error")
        self._bot_space = bot.space_id
        return bot

    def read_page(self, page_id: str) -> PageView:
        expected = canonical_id(page_id)
        if expected == "":
            raise SandboxError("notion api error")
        payload = self._send("GET", f"/v1/pages/{page_id}", None)
        fallback = self._bot_space if expected == SANDBOX_PARENT_PAGE_ID else ""
        page = parse_page(payload, fallback_space=fallback, expected_id=expected)
        if page is None:
            raise SandboxError("notion api error")
        return page

    def create_child_page(self, parent_id: str, title: str) -> PageView:
        allowed = (SANDBOX_PARENT_PAGE_ID, *self._created_ids)
        if not parent_is_allowed(parent_id, allowed):
            raise SandboxError("parent is not the sandbox parent")
        body = json.dumps(
            {
                "parent": {"page_id": canonical_id(parent_id), "type": "page_id"},
                "properties": {"title": {"title": [{"text": {"content": title}}]}},
            }
        ).encode("utf-8")
        payload = self._send("POST", "/v1/pages", body)
        page = parse_page(payload, fallback_space=SANDBOX_SPACE_ID, expected_id="")
        if page is None:
            raise SandboxError("notion api error")
        self._created_ids.append(page.page_id)
        return page

    def _send(self, method: str, path: str, body: bytes | None) -> object:
        url = NOTION_API_ORIGIN + path
        if leaks(url, self._token):
            raise SandboxError("notion api error")
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header("Notion-Version", NOTION_VERSION)
        request.add_header("Accept", "application/json")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            response = self._opener(request, timeout=_TIMEOUT_SECONDS)
            raw = response.read()
            response.close()
        except SandboxError:
            raise
        except Exception as exc:
            raise SandboxError(redact_text(str(exc), self._token)) from None
        if type(raw) is not bytes:
            raise SandboxError("notion api error")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise SandboxError(redact_text(str(exc), self._token)) from None


def parse_bot(payload: object) -> BotView | None:
    """Map a users/me payload. A missing workspace id stays empty."""
    if type(payload) is not dict:
        return None
    user_id = payload.get("id")
    user_type = payload.get("type")
    if type(user_id) is not str or type(user_type) is not str:
        return None
    space = ""
    bot = payload.get("bot")
    if type(bot) is dict and type(bot.get("workspace_id")) is str:
        space = canonical_id(bot["workspace_id"])
    return BotView(user_id=user_id, user_type=user_type, space_id=space)


def parse_page(payload: object, *, fallback_space: str, expected_id: str) -> PageView | None:
    """Map a page payload. The bot space fills in only for the expected page."""
    if type(payload) is not dict or payload.get("object") not in {None, "page"}:
        return None
    page_id = canonical_id(payload.get("id"))
    if page_id == "":
        return None
    parent_id = ""
    space = explicit_space(payload)
    parent = payload.get("parent")
    if type(parent) is dict:
        if space == "":
            space = explicit_space(parent)
        if parent.get("type") == "page_id":
            parent_id = canonical_id(parent.get("page_id"))
    if space == "" and page_id == canonical_id(expected_id):
        space = canonical_id(fallback_space)
    url = payload.get("url")
    if type(url) is not str or url == "":
        url = f"https://www.notion.so/{page_id.replace('-', '')}"
    archived = payload.get("archived") is True or payload.get("in_trash") is True
    return PageView(
        page_id=page_id,
        parent_id=parent_id,
        space_id=space,
        url=url,
        archived=archived,
    )


def explicit_space(payload: Mapping[str, object]) -> str:
    """A space id carried on the payload, or empty."""
    for key in ("space_id", "workspace_id"):
        value = payload.get(key)
        if type(value) is str and canonical_id(value) != "":
            return canonical_id(value)
    return ""
