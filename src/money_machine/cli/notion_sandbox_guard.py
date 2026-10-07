"""Target, token, and evidence guards for the Session 07 sandbox runner.

Space and parent ids are constants. The token is never accepted from argv,
a file, or stdin. Redaction runs before any evidence file is written.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from money_machine.cli.notion import contains_secret_shape, redact_secret_shapes

EXIT_OK = 0
EXIT_USAGE = 64
EXIT_TARGET = 65
EXIT_NO_TOKEN = 66
EXIT_API = 69
EXIT_REDACTION = 70
SANDBOX_SPACE_ID = "89282fb0-af94-8106-809e-0003c027fa07"
SANDBOX_PARENT_PAGE_ID = "3ed82fb0-af94-80dc-8272-f40b16376b81"
_TOKEN_ENV = "NOTION_SANDBOX_TOKEN"
_OVERRIDE_ENV = (
    "NOTION_PARENT_PAGE_ID",
    "NOTION_SANDBOX_PARENT",
    "NOTION_SANDBOX_PARENT_PAGE_ID",
    "NOTION_SANDBOX_SPACE_ID",
    "NOTION_SANDBOX_TOKEN_FILE",
    "NOTION_SPACE_ID",
    "NOTION_WORKSPACE_ID",
)
_OVERRIDE_FLAGS = frozenset(
    {
        "--api-key",
        "--parent",
        "--parent-id",
        "--parent-page",
        "--parent-page-id",
        "--space",
        "--space-id",
        "--token",
        "--token-file",
        "--workspace",
        "--workspace-id",
    }
)
PIPELINE_WRITE_METHODS = (
    "add_callout_block",
    "add_child_page",
    "add_filter",
    "add_property",
    "add_sort",
    "add_text_block",
    "create_board_view",
    "create_calendar_view",
    "create_database",
    "create_formula",
    "create_linked_view",
    "create_page",
    "create_relation",
    "create_rollup",
    "create_table_view",
    "drop_page_property",
    "duplicate_page",
    "move_page",
    "publish_page",
    "rename_page",
    "set_cover",
    "set_duplicate_as_template",
    "set_icon",
    "set_search_indexing",
    "set_view_title_visibility",
    "unpublish_page",
)


class SandboxError(Exception):
    """A sandbox failure whose text is safe to log."""


@dataclass(frozen=True)
class BotView:
    """Bot identity from a read-only users call."""

    user_id: str
    user_type: str
    space_id: str


@dataclass(frozen=True)
class PageView:
    """Page identity from a read or a child-page write."""

    page_id: str
    parent_id: str
    space_id: str
    url: str
    archived: bool


class SandboxClient(Protocol):
    """Reads of the asserted target, and child pages under that parent."""

    write_counts: dict[str, int]

    def read_bot(self) -> BotView:
        """Return the token's bot user."""
        ...

    def read_page(self, page_id: str) -> PageView:
        """Return one page."""
        ...

    def create_child_page(self, parent_id: str, title: str) -> PageView:
        """Create one child page."""
        ...


def canonical_id(value: object) -> str:
    """Dashed lowercase UUID, or empty when the value is not one."""
    if type(value) is not str:
        return ""
    compact = value.replace("-", "").lower()
    if len(compact) != 32:
        return ""
    if any(character not in "0123456789abcdef" for character in compact):
        return ""
    return f"{compact[0:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:32]}"


def target_ok(bot: BotView, page: PageView) -> bool:
    """The bot and the parent page match the sandbox constants exactly."""
    if bot.user_type != "bot":
        return False
    if page.archived:
        return False
    if canonical_id(bot.space_id) != SANDBOX_SPACE_ID:
        return False
    if canonical_id(page.page_id) != SANDBOX_PARENT_PAGE_ID:
        return False
    return canonical_id(page.space_id) == SANDBOX_SPACE_ID


def parent_is_allowed(parent_id: str, allowed: tuple[str, ...]) -> bool:
    """A write parent is the sandbox parent or a page this run created."""
    candidate = canonical_id(parent_id)
    if candidate == "":
        return False
    return any(canonical_id(item) == candidate for item in allowed)


def token_from_environ(environ: Mapping[str, str]) -> str | None:
    """Read only ``NOTION_SANDBOX_TOKEN``."""
    value = environ.get(_TOKEN_ENV)
    if type(value) is not str or value == "":
        return None
    return value


def override_env(environ: Mapping[str, str]) -> bool:
    """True when the environment tries to name a space or a parent."""
    return any(name in environ for name in _OVERRIDE_ENV)


def argv_refused(argv: Sequence[str]) -> bool:
    """True when argv carries a token or a retargeting flag."""
    for arg in argv:
        head, _separator, _tail = arg.partition("=")
        if head in _OVERRIDE_FLAGS:
            return True
        if contains_secret_shape(arg):
            return True
    return False


def redact_text(text: str, token: str | None) -> str:
    """Replace shaped secrets and the exact token value."""
    cleaned = redact_secret_shapes(text)
    if token is not None and token != "" and token in cleaned:
        cleaned = cleaned.replace(token, "[REDACTED]")
    return cleaned


def stage_status(runner_name: str | None, outcome: str | None) -> str:
    """A missing runner is ``NOT_RUN``. It is never ``PASS``."""
    if runner_name is None:
        return "NOT_RUN"
    if outcome == "PASS":
        return "PASS"
    if outcome == "FAILED":
        return "FAILED"
    if outcome == "BLOCKED":
        return "BLOCKED"
    return "NOT_RUN"


def qa_verdict(stages: Sequence[Mapping[str, object]]) -> str:
    """Follow the qa stage. ``NOT_RUN`` is not a pass."""
    status = "NOT_RUN"
    for stage in stages:
        found = stage.get("status")
        if stage.get("name") == "qa" and type(found) is str:
            status = found
    if status == "PASS":
        return "PASS"
    if status == "FAILED":
        return "FAIL"
    if status == "BLOCKED":
        return "BLOCKED"
    return "NOT_RUN"


def empty_write_counts() -> dict[str, int]:
    """Counted methods start at zero."""
    counts = {name: 0 for name in PIPELINE_WRITE_METHODS}
    counts["create_child_page"] = 0
    return counts


def leaks(text: str, token: str | None) -> bool:
    """True when the text still contains a secret."""
    if token is not None and token != "" and token in text:
        return True
    return contains_secret_shape(text)


def _dump(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def write_evidence(path: Path, payload: Mapping[str, object], token: str | None) -> str:
    """Write JSON. ``PASS`` means the document was clean before redaction."""
    document = dict(payload)
    document["redaction_self_check"] = "PASS"
    text = _dump(document)
    result = "PASS"
    if leaks(text, token):
        document["redaction_self_check"] = "FAIL"
        text = redact_text(_dump(document), token)
        result = "FAIL"
        if leaks(text, token):
            text = redact_text(
                _dump({"error": "redaction self-check failed", "redaction_self_check": "FAIL"}),
                token,
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    return result


def stamp(moment: datetime) -> str:
    """UTC timestamp with a ``Z`` suffix."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_root() -> Path:
    """The checkout that holds ``pyproject.toml`` and ``docs/control``."""
    start = Path(__file__).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir():
            return candidate
    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir():
            return candidate
    raise SandboxError("repository root is unavailable")


def git_sha(root: Path) -> str:
    """Checkout SHA. It is not taken from argv."""
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        cwd=root,
        capture_output=True,
        text=True,
    )
    sha = completed.stdout.strip()
    if completed.returncode != 0 or len(sha) != 40:
        raise SandboxError("git sha is unavailable")
    if any(character not in "0123456789abcdef" for character in sha):
        raise SandboxError("git sha is unavailable")
    return sha


def control_ids(root: Path) -> dict[str, object]:
    """Read-only control ids. The state file is not written."""
    raw = (root / "docs" / "control" / "IMPLEMENTATION_STATE.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    revision = payload.get("state_revision")
    session = payload.get("current_session")
    head = payload.get("head_sha")
    if type(revision) is not int or type(session) is not int or type(head) is not str:
        raise SandboxError("control state is unreadable")
    return {
        "control_head_sha": head,
        "control_state_revision": revision,
        "current_session": session,
    }
