"""Target, token, and evidence guards for the Session 07 sandbox runner.

Space and parent ids are constants. The token is never accepted from argv,
a file, or stdin. Redaction runs before any evidence file is written.
"""

from __future__ import annotations

import base64
import contextlib
import errno
import json
import os
import stat
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, Protocol
from urllib.parse import quote

from money_machine.cli.notion import contains_secret_shape, redact_secret_shapes, token_shape_ok

EXIT_OK = 0
EXIT_USAGE = 64
EXIT_TARGET = 65
EXIT_NO_TOKEN = 66
EXIT_API = 69
EXIT_REDACTION = 70
SANDBOX_SPACE_ID = "89282fb0-af94-8106-809e-0003c027fa07"
SANDBOX_PARENT_PAGE_ID = "3ed82fb0-af94-80dc-8272-f40b16376b81"
_TOKEN_ENV = "NOTION_SANDBOX_TOKEN"
_CERT_ENV = ("SSL_CERT_DIR", "SSL_CERT_FILE", "SSLKEYLOGFILE")
_OVERRIDE_ENV = (
    "NOTION_CONFIG",
    "NOTION_PARENT_PAGE_ID",
    "NOTION_SANDBOX_CONFIG",
    "NOTION_SANDBOX_PARENT",
    "NOTION_SANDBOX_PARENT_PAGE_ID",
    "NOTION_SANDBOX_SPACE_ID",
    "NOTION_SANDBOX_TOKEN_FILE",
    "NOTION_SPACE_ID",
    "NOTION_TOKEN_FILE",
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
# get_public_url is a read and is intentionally absent from this tuple.
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

    def __init__(self, message: str, code: int = EXIT_API) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BotView:
    """Bot identity from a read-only users call."""

    user_id: object
    user_type: object
    space_id: str


@dataclass(frozen=True)
class PageView:
    """Page identity from a read or a child-page write."""

    page_id: str
    parent_id: str
    space_id: str
    url: str
    archived: bool
    parent_type: str = ""
    created_by: str = ""
    created_time: datetime | None = None


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
    if type(bot.user_type) is not str or bot.user_type != "bot":
        return False
    if page.archived or page.parent_type in {"database_id", "data_source_id"}:
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


def cert_env_set(environ: Mapping[str, str]) -> bool:
    """True when the process points TLS at a custom trust store."""
    return any(name in environ for name in _CERT_ENV)


def space_conflicts(space_id: str) -> bool:
    """An explicit space that is not the sandbox. An absent space does not conflict."""
    found = canonical_id(space_id)
    return found != "" and found != SANDBOX_SPACE_ID


def argv_refused(argv: Sequence[str]) -> bool:
    """True when argv carries a token or a retargeting flag."""
    for arg in argv:
        head, _separator, _tail = arg.partition("=")
        if head in _OVERRIDE_FLAGS:
            return True
        if contains_secret_shape(arg):
            return True
    return False


def _unsafe_exact(token: str) -> bool:
    """Whitespace and JSON literals would rewrite the evidence document."""
    return token.strip() == "" or token in {"true", "false", "null"}


def _encoded_forms(token: str | None) -> tuple[str, ...]:
    """Url-encoding and base64 of a shaped token. Other tokens have none."""
    if token is None or not token_shape_ok(token):
        return ()
    # A shaped token always holds "_", so the url form (with %5F) differs from it.
    # Base64 has neither "_" nor "%", so the digest differs from both.
    encoded = quote(token, safe="").replace("_", "%5F")
    digest = base64.b64encode(token.encode("utf-8")).decode("ascii")
    return (encoded, digest)


def redact_text(text: str, token: str | None) -> str:
    """Replace shaped secrets, the exact token, and its base64 and url-encoded copies."""
    cleaned = redact_secret_shapes(text)
    # The empty token is whitespace-only, so _unsafe_exact covers it.
    if token is not None and not _unsafe_exact(token):
        cleaned = _scrub_hex(cleaned.replace(token, "[REDACTED]"), _folded_hex(token))
    for form in _encoded_forms(token):
        if form in cleaned:
            cleaned = cleaned.replace(form, "[REDACTED]")
    return cleaned


def _scrub_hex(text: str, folded: str) -> str:
    if folded == "":
        return text
    pieces: list[str] = []
    index = 0
    lowered = text.lower()
    while True:
        found = lowered.find(folded, index)
        if found < 0:
            pieces.append(text[index:])
            return "".join(pieces)
        pieces.append(text[index:found])
        pieces.append("[REDACTED]")
        index = found + len(folded)


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
    """Follow the qa stage. ``NOT_RUN`` is not a pass.

    A supplied ``PASS`` is returned unchanged. The runner cannot produce that
    status while the qa slot is None. ``test_token_env_and_redaction_units``
    pins the mapping.
    """
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


def _folded_hex(token: str) -> str:
    """Lowercase hex of a long hex token, or empty when it is not one."""
    compact = token.replace("-", "")
    if len(compact) < 32:
        return ""
    if any(character not in "0123456789abcdefABCDEF" for character in compact):
        return ""
    return compact.lower()


def leaks(text: str, token: str | None) -> bool:
    """True when the text still contains a secret, including encoded copies."""
    if token is not None and not _unsafe_exact(token):
        if token in text:
            return True
        folded = _folded_hex(token)
        if folded != "" and folded in text.lower().replace("-", ""):
            return True
    if any(form in text for form in _encoded_forms(token)):
        return True
    return contains_secret_shape(text)


def _dump(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def render_evidence(payload: Mapping[str, object], token: str | None) -> tuple[str, str]:
    """Return the JSON text and ``PASS`` or ``FAIL``."""
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
    return text + "\n", result


def _refuse_path(message: str = "evidence path is refused") -> NoReturn:
    raise SandboxError(message, code=EXIT_USAGE)


def under_proc(path: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    return absolute == Path("/proc") or Path("/proc") in absolute.parents


def open_evidence(path: Path) -> None:
    """Refuse a bad evidence path. The file is created only with finished bytes."""
    # An empty argument is Path("."), which exists, so the lstat below refuses it.
    if under_proc(path):
        _refuse_path()
    try:
        info = path.lstat()
    except FileNotFoundError:
        info = None
    except OSError:
        _refuse_path()
    if info is not None:
        _refuse_path()
    parent = path.parent
    try:
        parent_info = parent.lstat()
    except OSError:
        _refuse_path()
    # lstat never reports a symlink as a directory, so this refuses a symlinked parent too.
    if not stat.S_ISDIR(parent_info.st_mode):
        _refuse_path()
    if parent_info.st_mode & 0o200 == 0:
        _refuse_path()


_DISK_ERRNO = {errno.EDQUOT, errno.EFBIG, errno.EIO, errno.ENOSPC}


def _failure_text(payload: Mapping[str, object], token: str | None, prefix: str) -> str:
    ids = _created_page_ids(payload)
    detail = prefix if ids == "" else f"{prefix}: {ids}"
    return redact_text(detail, token)


def _created_page_ids(payload: Mapping[str, object]) -> str:
    found = payload.get("created_pages")
    if type(found) is not list:
        return ""
    ids: list[str] = []
    for item in found:
        if type(item) is not dict:
            continue
        page_id = item.get("id")
        if type(page_id) is str and page_id != "":
            ids.append(page_id)
    return ", ".join(ids)


def _write_all(fd: int, encoded: bytes) -> None:
    pending = memoryview(encoded)
    while len(pending) > 0:
        written = os.write(fd, pending)
        if written <= 0 or written > len(pending):
            raise SandboxError("evidence write failed")
        pending = pending[written:]


def _destination_appeared(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def commit_evidence(path: Path, payload: Mapping[str, object], token: str | None) -> str:
    """Write a complete JSON file via a temporary file and an atomic link.

    The destination is absent until the temporary file holds every byte.
    An interrupt unlinks the temporary file and leaves the previous destination.
    """
    open_evidence(path)
    text, result = render_evidence(payload, token)
    encoded = text.encode("utf-8")
    temporary = path.with_name(f".{path.name}.tmp")
    tmp_fd = -1
    try:
        tmp_fd = os.open(
            temporary,
            os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY,
            0o600,
        )
        opened = os.fstat(tmp_fd)
        if stat.S_IMODE(opened.st_mode) != 0o600:
            raise OSError(errno.EPERM, "mode")
        _write_all(tmp_fd, encoded)
        os.fchmod(tmp_fd, 0o600)
        os.fsync(tmp_fd)
        os.close(tmp_fd)
        tmp_fd = -1
        if _destination_appeared(path):
            raise SandboxError(
                _failure_text(payload, token, "evidence file changed during the run")
            )
        os.link(temporary, path)
        current = path.lstat()
        if stat.S_ISLNK(current.st_mode) or current.st_size != len(encoded):
            with contextlib.suppress(OSError):
                os.unlink(path)
            raise SandboxError(
                _failure_text(payload, token, "evidence file changed during the run")
            )
    except SandboxError:
        raise
    except OSError as exc:
        if exc.errno in _DISK_ERRNO:
            raise SandboxError(_failure_text(payload, token, "evidence write failed")) from None
        raise SandboxError("evidence path is refused", code=EXIT_USAGE) from None
    finally:
        if tmp_fd >= 0:
            with contextlib.suppress(OSError):
                os.close(tmp_fd)
        with contextlib.suppress(OSError):
            os.unlink(temporary)
    return result


def write_evidence(path: Path, payload: Mapping[str, object], token: str | None) -> str:
    """Write JSON once the path is acceptable. ``PASS`` means it was clean."""
    return commit_evidence(path, payload, token)


def evidence_sections(
    counts: Mapping[str, int],
    created: list[dict[str, str]],
) -> dict[str, object]:
    """Fixture pipeline counts stay apart from the live child-page writes.

    ``get_public_url`` is a read. It is not in ``PIPELINE_WRITE_METHODS`` and
    it is not included in ``write_counts``.
    """
    fixture = {name: value for name, value in counts.items() if name != "create_child_page"}
    live_count = counts.get("create_child_page", 0)
    return {
        "fixture": {"label": "fixture", "write_counts": fixture},
        "live": {
            "created_pages": created,
            "label": "live",
            "write_counts": {"create_child_page": live_count},
        },
    }


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
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            cwd=root,
            capture_output=True,
            text=True,
        )
    except OSError:
        raise SandboxError("git sha is unavailable") from None
    sha = completed.stdout.strip()
    if completed.returncode != 0 or len(sha) != 40:
        raise SandboxError("git sha is unavailable")
    if any(character not in "0123456789abcdef" for character in sha):
        raise SandboxError("git sha is unavailable")
    return sha


def control_ids(root: Path) -> dict[str, object]:
    """Read-only control ids. The state file is not written."""
    try:
        raw = (root / "docs" / "control" / "IMPLEMENTATION_STATE.json").read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise SandboxError("control state is unreadable") from None
    if type(payload) is not dict:
        raise SandboxError("control state is unreadable")
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
