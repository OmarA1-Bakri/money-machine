"""Live Notion reads and child-page writes for the sandbox parent only.

Tests do not construct this client. The runner does, and only when no fake
client was injected.
"""

from __future__ import annotations

import json
import ssl
import urllib.request
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Protocol, cast

from money_machine.cli.notion_sandbox_guard import (
    SANDBOX_PARENT_PAGE_ID,
    BotView,
    PageView,
    SandboxError,
    canonical_id,
    empty_write_counts,
    leaks,
    parent_is_allowed,
    redact_text,
    space_conflicts,
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


def asserted_body_parent(parent_id: str) -> str:
    """Parent id written into a create body. Callers still assert it."""
    return canonical_id(parent_id)


class RefuseRedirect(urllib.request.HTTPRedirectHandler):
    """A 3xx must not send the bearer token to another host."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: _Readable,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        del req, fp, code, msg, headers, newurl
        raise SandboxError("notion api error")


def default_tls_context() -> ssl.SSLContext:
    """A client context from the compiled-in CA file.

    ``SSL_CERT_FILE``, ``SSL_CERT_DIR``, and ``SSLKEYLOGFILE`` are not read
    and the process environment is left unchanged.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    cafile = ssl.get_default_verify_paths().openssl_cafile
    if type(cafile) is str and cafile != "":
        try:
            context.load_verify_locations(cafile=cafile)
        except OSError:
            return context
    return context


def sandbox_opener() -> urllib.request.OpenerDirector:
    """HTTPS opener that ignores proxies and refuses redirects."""
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        RefuseRedirect(),
        urllib.request.HTTPSHandler(context=default_tls_context()),
    )


class LiveSandboxClient:
    """Official API client. The token stays on the Authorization header."""

    def __init__(self, token: str, opener: Callable[..., _Readable] | None = None) -> None:
        self._token = token
        director = sandbox_opener()
        self._proxy_targets = dict(proxy_map(director))
        self._opener = (
            opener if opener is not None else cast(Callable[..., _Readable], director.open)
        )
        self._bot_space = ""
        self._created_ids: list[str] = []
        self._evidence_ids: list[str] | None = None
        self._evidence_rows: list[dict[str, str]] | None = None
        self.write_counts: dict[str, int] = empty_write_counts()

    def bind_created(self, ids: list[str], rows: list[dict[str, str]]) -> None:
        """Record each accepted create into the run's evidence lists."""
        self._evidence_ids = ids
        self._evidence_rows = rows

    def proxy_targets(self) -> dict[str, str]:
        """Proxy map installed on the default opener. Empty means no proxy."""
        return dict(self._proxy_targets)

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
        payload = self._send("GET", f"/v1/pages/{expected}", None)
        fallback = self._bot_space if expected == SANDBOX_PARENT_PAGE_ID else ""
        page = parse_page(payload, fallback_space=fallback, expected_id=expected)
        if page is None:
            raise SandboxError("notion api error")
        return page

    def create_child_page(self, parent_id: str, title: str) -> PageView:
        allowed = (SANDBOX_PARENT_PAGE_ID, *self._created_ids)
        parent = canonical_id(parent_id)
        if not parent_is_allowed(parent, allowed):
            raise SandboxError("parent is not the sandbox parent")
        body_parent = asserted_body_parent(parent)
        body = json.dumps(
            {
                "parent": {"page_id": body_parent, "type": "page_id"},
                "properties": {"title": {"title": [{"text": {"content": title}}]}},
            }
        ).encode("utf-8")
        sent = json.loads(body)
        sent_parent = sent.get("parent") if type(sent) is dict else None
        if (
            type(sent_parent) is not dict
            or sent_parent.get("page_id") != parent
            or sent_parent.get("type") != "page_id"
        ):
            raise SandboxError("parent is not the sandbox parent")
        payload = self._send("POST", "/v1/pages", body)
        page = parse_page(payload, fallback_space="", expected_id="")
        if page is None:
            raise SandboxError("notion api error")
        self._publish(page)
        return page

    def _publish(self, page: PageView) -> None:
        """Append the id as soon as the create response parses. No further read."""
        page_id = canonical_id(page.page_id)
        if page_id == "" or space_conflicts(page.space_id):
            return
        if page_id not in self._created_ids:
            self._created_ids.append(page_id)
        evidence_ids = self._evidence_ids
        evidence_rows = self._evidence_rows
        if evidence_ids is None or evidence_rows is None or page_id in evidence_ids:
            return
        evidence_ids.append(page_id)
        evidence_rows.append(
            {"id": page_id, "parent_id": canonical_id(page.parent_id), "url": page.url}
        )

    def _send(self, method: str, path: str, body: bytes | None) -> object:
        url = NOTION_API_ORIGIN + path
        if leaks(url, self._token) or leaks(url.replace("-", ""), self._token):
            raise SandboxError("notion api error")
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header("Notion-Version", NOTION_VERSION)
        request.add_header("Accept", "application/json")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            response = self._opener(request, timeout=_TIMEOUT_SECONDS)
            status = getattr(response, "status", None)
            if type(status) is not int:
                status = getattr(response, "code", None)
            if type(status) is int and 300 <= status < 400:
                response.close()
                raise SandboxError("notion api error")
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


def _strict_bool(payload: Mapping[str, object], key: str) -> bool | None:
    """Missing is false. A non-bool value is rejected."""
    if key not in payload:
        return False
    value = payload[key]
    if type(value) is not bool:
        return None
    return value


def parse_page(payload: object, *, fallback_space: str, expected_id: str) -> PageView | None:
    """Map a page payload. The bot space fills in only for the expected page."""
    if type(payload) is not dict or payload.get("object") != "page":
        return None
    page_id = canonical_id(payload.get("id"))
    if page_id == "":
        return None
    parent_id = ""
    parent_type = ""
    space = explicit_space(payload)
    parent = payload.get("parent")
    if type(parent) is dict:
        if space == "":
            space = explicit_space(parent)
        found_type = parent.get("type")
        if type(found_type) is str:
            parent_type = found_type
        if found_type == "page_id":
            parent_id = canonical_id(parent.get("page_id"))
    if space == "" and page_id == canonical_id(expected_id):
        space = canonical_id(fallback_space)
    url = payload.get("url")
    if type(url) is not str or url == "":
        url = f"https://www.notion.so/{page_id.replace('-', '')}"
    archived_flag = _strict_bool(payload, "archived")
    alias_flag = _strict_bool(payload, "is_archived")
    trash_flag = _strict_bool(payload, "in_trash")
    if archived_flag is None or alias_flag is None or trash_flag is None:
        return None
    archived = archived_flag or alias_flag or trash_flag
    return PageView(
        page_id=page_id,
        parent_id=parent_id,
        space_id=space,
        url=url,
        archived=archived,
        parent_type=parent_type,
        created_by=_created_by(payload),
        created_time=parse_created_time(payload.get("created_time")),
    )


def parse_created_time(value: object) -> datetime | None:
    """Parse a Notion timestamp. Naive or blank values stay unset."""
    if type(value) is not str or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _created_by(payload: Mapping[str, object]) -> str:
    actor = payload.get("created_by")
    if type(actor) is not dict:
        return ""
    found = actor.get("id")
    if type(found) is not str:
        return ""
    return found


def proxy_map(director: urllib.request.OpenerDirector) -> dict[str, str]:
    proxies: dict[str, str] = {}
    handlers = getattr(director, "handlers", None)
    if type(handlers) is not list:
        return proxies
    for handler in handlers:
        if isinstance(handler, urllib.request.ProxyHandler):
            found = getattr(handler, "proxies", None)
            if type(found) is not dict:
                continue
            for key, value in found.items():
                if type(key) is str and type(value) is str:
                    proxies[key] = value
    return proxies


def explicit_space(payload: Mapping[str, object]) -> str:
    """A space id carried on the payload, or empty."""
    for key in ("space_id", "workspace_id"):
        value = payload.get(key)
        if type(value) is str and canonical_id(value) != "":
            return canonical_id(value)
    return ""
