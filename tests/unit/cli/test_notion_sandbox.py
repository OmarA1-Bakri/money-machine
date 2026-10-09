"""Sandbox runner guards. Fake client only. Sockets stay closed."""

from __future__ import annotations

import ast
import asyncio
import base64
import contextlib
import errno
import hashlib
import io
import json
import logging
import os
import signal
import socket
import ssl
import stat
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Coroutine
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from urllib.parse import quote

import pytest

from money_machine.cli.notion_sandbox import main
from money_machine.cli.notion_sandbox_guard import (
    EXIT_API,
    EXIT_NO_TOKEN,
    EXIT_OK,
    EXIT_REDACTION,
    EXIT_TARGET,
    EXIT_USAGE,
    SANDBOX_PARENT_PAGE_ID,
    SANDBOX_SPACE_ID,
    BotView,
    PageView,
    SandboxClient,
    SandboxError,
    argv_refused,
    canonical_id,
    cert_env_set,
    commit_evidence,
    empty_write_counts,
    git_sha,
    leaks,
    open_evidence,
    override_env,
    parent_is_allowed,
    qa_verdict,
    redact_text,
    render_evidence,
    repo_root,
    space_conflicts,
    stage_status,
    target_ok,
    token_from_environ,
    under_proc,
    write_evidence,
)
from money_machine.cli.notion_sandbox_live import (
    NOTION_VERSION,
    LiveSandboxClient,
    RefuseRedirect,
    asserted_body_parent,
    explicit_space,
    parse_bot,
    parse_created_time,
    parse_page,
    proxy_map,
    sandbox_opener,
)
from money_machine.cli.notion_sandbox_live import (
    default_tls_context as sandbox_tls_context,
)
from money_machine.cli.notion_sandbox_pipeline import (
    SandboxRun,
    chain_reaches_sandbox,
    create_under,
    sandbox_product_spec,
    stage_runners,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter

_SECRET = "secret_" + ("a" * 43)
_NTN = "ntn_" + ("b" * 43)
_SHORT = "secret_abc"
_SPACE_RAW = "89282FB0AF948106809E0003C027FA07"
_PARENT_RAW = "3ED82FB0AF9480DC8272F40B16376B81"
_WRONG_SPACE = "89282fb0-ffff-8106-809e-0003c027fa07"
_WRONG_PARENT = "3ed82fb0-ffff-80dc-8272-f40b16376b81"
_LIE_ID = "DDDDDDDDDDDD4DDD8DDDDDDDDDDDDDD1"
_WHEN = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
_CHILD_IDS = (
    "AAAAAAAAAAAA4AAA8AAAAAAAAAAAAAA1",
    "AAAAAAAAAAAA4AAA8AAAAAAAAAAAAAA2",
    "AAAAAAAAAAAA4AAA8AAAAAAAAAAAAAA3",
    "AAAAAAAAAAAA4AAA8AAAAAAAAAAAAAA4",
    "AAAAAAAAAAAA4AAA8AAAAAAAAAAAAAA5",
)
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
_OVERRIDE_FLAGS = (
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
)
_ABSENT = ("qa", "fact_ledger", "workflow_link", "w11")
_STATE = Path("docs/control/IMPLEMENTATION_STATE.json")
_MODULES = (
    Path("src/money_machine/cli/notion_sandbox.py"),
    Path("src/money_machine/cli/notion_sandbox_guard.py"),
    Path("src/money_machine/cli/notion_sandbox_live.py"),
    Path("src/money_machine/cli/notion_sandbox_pipeline.py"),
)


class FakeSandbox:
    """In-memory target. It does not count writes; the runner does."""

    def __init__(
        self,
        *,
        space: str = _SPACE_RAW,
        page_id: str = _PARENT_RAW,
        page_space: str | None = None,
        archived: bool = False,
        user_type: object = "bot",
        user_id: object = "bot-user",
        error: BaseException | None = None,
    ) -> None:
        self.space = space
        self.page_id = page_id
        self.page_space = space if page_space is None else page_space
        self.archived = archived
        self.user_type = user_type
        self.user_id = user_id
        self.error = error
        self.write_counts: dict[str, int] = {}
        self.creates: list[tuple[str, str]] = []
        self.reads: list[str] = []
        self.pages: dict[str, PageView] = {}
        self._evidence_ids: list[str] | None = None
        self._evidence_rows: list[dict[str, str]] | None = None

    def bind_created(self, ids: list[str], rows: list[dict[str, str]]) -> None:
        self._evidence_ids = ids
        self._evidence_rows = rows

    def read_bot(self) -> BotView:
        self.reads.append("bot")
        if self.error is not None:
            raise self.error
        return BotView(user_id=self.user_id, user_type=self.user_type, space_id=self.space)

    def read_page(self, page_id: str) -> PageView:
        self.reads.append(page_id)
        wanted = canonical_id(page_id)
        stored = self.pages.get(wanted)
        if stored is not None:
            return stored
        if wanted == canonical_id(self.page_id):
            return PageView(
                page_id=wanted,
                parent_id="",
                space_id=self.page_space,
                url=f"https://www.notion.so/{_PARENT_RAW.lower()}",
                archived=self.archived,
                created_by=self._actor(),
                created_time=_WHEN,
            )
        return PageView(
            page_id=wanted,
            parent_id=_WRONG_PARENT,
            space_id=_WRONG_SPACE,
            url="https://www.notion.so/foreign",
            archived=False,
            created_by=self._actor(),
            created_time=_WHEN,
        )

    def create_child_page(self, parent_id: str, title: str) -> PageView:
        self.creates.append((parent_id, title))
        index = len(self.creates) - 1
        page_id = _CHILD_IDS[index]
        child = canonical_id(page_id)
        parent = canonical_id(parent_id)
        self.pages[child] = PageView(
            page_id=child,
            parent_id=parent,
            space_id=canonical_id(_SPACE_RAW),
            url=f"https://www.notion.so/{page_id.lower()}",
            archived=False,
            created_by=self._actor(),
            created_time=_WHEN,
        )
        page = PageView(
            page_id=page_id,
            parent_id=parent_id.replace("-", "").upper(),
            space_id=_SPACE_RAW,
            url=f"https://www.notion.so/{page_id.lower()}",
            archived=False,
            created_by=self._actor(),
            created_time=_WHEN,
        )
        self._publish(page)
        return page

    def _publish(self, page: PageView) -> None:
        page_id = canonical_id(page.page_id)
        if page_id == "" or space_conflicts(page.space_id):
            return
        evidence_ids = self._evidence_ids
        evidence_rows = self._evidence_rows
        if evidence_ids is None or evidence_rows is None or page_id in evidence_ids:
            return
        evidence_ids.append(page_id)
        evidence_rows.append(
            {"id": page_id, "parent_id": canonical_id(page.parent_id), "url": page.url}
        )

    def _actor(self) -> str:
        if type(self.user_id) is str:
            return self.user_id
        return "bot-user"


@pytest.fixture(autouse=True)
def _block_sockets(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("socket use is refused")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)


@pytest.fixture(autouse=True)
def _restore_sigint() -> object:  # pyright: ignore[reportUnusedFunction]
    previous = signal.getsignal(signal.SIGINT)
    try:
        yield
    finally:
        with contextlib.suppress(ValueError, TypeError, OSError):
            signal.signal(signal.SIGINT, previous)


@pytest.fixture
def evidence(tmp_path: Path) -> Path:
    return tmp_path / "evidence.json"


def _clock() -> datetime:
    return _WHEN


def _run(
    evidence: Path,
    argv: list[str],
    *,
    client: SandboxClient | None = None,
    environ: dict[str, str] | None = None,
    spec: object | None = None,
    caplog: pytest.LogCaptureFixture | None = None,
) -> tuple[int, str, str]:
    if caplog is not None:
        caplog.set_level(logging.DEBUG)
    code = main(
        argv,
        client=client,
        environ={} if environ is None else environ,
        spec=spec,
        clock=_clock,
    )
    text = evidence.read_text(encoding="utf-8") if evidence.is_file() else ""
    return code, text, "" if caplog is None else caplog.text


def _invoke(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    extra: list[str],
    *,
    client: SandboxClient | None = None,
    environ: dict[str, str] | None = None,
    spec: object | None = None,
) -> tuple[int, dict[str, object], str, str, str]:
    code, raw, logs = _run(
        evidence,
        ["--evidence-out", str(evidence), *extra],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET} if environ is None else environ,
        spec=spec,
        caplog=caplog,
    )
    captured = capsys.readouterr()
    payload = json.loads(raw) if raw else {}
    return code, payload, captured.out, captured.err, logs


def _writes(payload: dict[str, object]) -> int:
    counts = payload["write_counts"]
    assert isinstance(counts, dict)
    total = 0
    for label in ("fixture", "live"):
        section = counts[label]
        assert isinstance(section, dict)
        assert "get_public_url" not in section
        for value in section.values():
            assert type(value) is int
            total += value
    return total


def _echo(page: PageView, **changes: object) -> PageView:
    values: dict[str, object] = {
        "archived": page.archived,
        "created_by": page.created_by,
        "created_time": page.created_time,
        "page_id": page.page_id,
        "parent_id": page.parent_id,
        "parent_type": page.parent_type,
        "space_id": page.space_id,
        "url": page.url,
    }
    values.update(changes)
    return PageView(
        page_id=str(values["page_id"]),
        parent_id=str(values["parent_id"]),
        space_id=str(values["space_id"]),
        url=str(values["url"]),
        archived=bool(values["archived"]),
        parent_type=str(values["parent_type"]),
        created_by=str(values["created_by"]),
        created_time=values["created_time"]
        if isinstance(values["created_time"], datetime)
        else None,
    )


def _stage(payload: dict[str, object], name: str) -> dict[str, object]:
    stages = payload["stages"]
    assert isinstance(stages, list)
    found = next(item for item in stages if isinstance(item, dict) and item.get("name") == name)
    assert isinstance(found, dict)
    return found


def _assert_clean(*chunks: str) -> None:
    for chunk in chunks:
        assert _SECRET not in chunk
        assert _NTN not in chunk
        assert "ntn_" not in chunk
        assert "secret_" not in chunk


def test_exit_codes_leave_78_held() -> None:
    assert {EXIT_OK, EXIT_USAGE, EXIT_TARGET, EXIT_NO_TOKEN, EXIT_API, EXIT_REDACTION} == {
        0,
        64,
        65,
        66,
        69,
        70,
    }


def test_canonical_id_normalizes_and_rejects() -> None:
    assert canonical_id(_SPACE_RAW) == SANDBOX_SPACE_ID
    assert canonical_id(SANDBOX_SPACE_ID) == SANDBOX_SPACE_ID
    assert canonical_id("z" * 32) == ""
    assert canonical_id("a" * 31) == ""
    assert canonical_id("a" * 33) == ""
    assert canonical_id(None) == ""


def test_target_and_parent_guards() -> None:
    bot = BotView(user_id="bot-user", user_type="bot", space_id=_SPACE_RAW)
    page = PageView(
        page_id=_PARENT_RAW,
        parent_id="",
        space_id=_SPACE_RAW,
        url="https://www.notion.so/x",
        archived=False,
    )
    assert target_ok(bot, page) is True
    assert target_ok(BotView("bot-user", "person", _SPACE_RAW), page) is False
    assert target_ok(bot, PageView(page.page_id, "", page.space_id, page.url, True)) is False
    assert target_ok(BotView("bot-user", "bot", _WRONG_SPACE), page) is False
    assert target_ok(bot, PageView(_WRONG_PARENT, "", _SPACE_RAW, page.url, False)) is False
    assert target_ok(bot, PageView(_PARENT_RAW, "", _WRONG_SPACE, page.url, False)) is False
    database_parent = PageView(
        page.page_id,
        "",
        page.space_id,
        page.url,
        False,
        parent_type="database_id",
    )
    assert target_ok(bot, database_parent) is False
    data_source_parent = PageView(
        page.page_id,
        "",
        page.space_id,
        page.url,
        False,
        parent_type="data_source_id",
    )
    assert target_ok(bot, data_source_parent) is False
    assert parent_is_allowed(_WRONG_PARENT, (SANDBOX_PARENT_PAGE_ID,)) is False
    assert parent_is_allowed(SANDBOX_PARENT_PAGE_ID, (SANDBOX_PARENT_PAGE_ID,)) is True
    assert parent_is_allowed(_CHILD_IDS[0], (SANDBOX_PARENT_PAGE_ID, _CHILD_IDS[0])) is True
    assert parent_is_allowed("not-an-id", (SANDBOX_PARENT_PAGE_ID,)) is False
    assert parent_is_allowed("not-an-id", ("not-an-id",)) is False
    assert stage_status("run_build", "BLOCKED") == "BLOCKED"


def test_token_env_and_redaction_units() -> None:
    assert token_from_environ({"NOTION_API_KEY": _SECRET}) is None
    assert token_from_environ({"NOTION_SANDBOX_TOKEN": ""}) is None
    assert token_from_environ({"NOTION_SANDBOX_TOKEN": _SECRET}) == _SECRET
    assert override_env({"NOTION_SPACE_ID": ""}) is True
    assert override_env({"NOTION_SPACE_ID": SANDBOX_SPACE_ID}) is True
    assert override_env({"NOTION_SANDBOX_TOKEN": _SECRET}) is False
    assert redact_text(f"boom {_SHORT}", _SHORT) == "boom [REDACTED]"
    assert redact_text(f"boom {_NTN}", None) == "boom [REDACTED]"
    digest = base64.b64encode(_SECRET.encode("utf-8")).decode("ascii")
    encoded = quote(_SECRET, safe="").replace("_", "%5F")
    assert encoded != _SECRET
    assert digest not in redact_text(f"see {digest}", _SECRET)
    assert encoded not in redact_text(f"see {encoded}", _SECRET)
    assert redact_text('{"ok": true}', " ") == '{"ok": true}'
    assert redact_text('{"ok": true}', "true") == '{"ok": true}'
    assert "get_public_url" not in empty_write_counts()
    assert stage_status(None, "PASS") == "NOT_RUN"
    assert qa_verdict(({"name": "qa", "status": "PASS"},)) == "PASS"
    assert qa_verdict(({"name": "qa", "status": "NOT_RUN"},)) == "NOT_RUN"
    assert qa_verdict(({"name": "qa", "status": "FAILED"},)) == "FAIL"
    assert qa_verdict(({"name": "qa", "status": "BLOCKED"},)) == "BLOCKED"
    assert qa_verdict(({"name": "build", "status": "PASS"},)) == "NOT_RUN"
    assert (
        qa_verdict(
            (
                {"name": "qa", "status": "FAILED"},
                {"name": "build", "status": "PASS"},
            )
        )
        == "FAIL"
    )
    assert leaks(_SECRET, _SECRET) is True
    folded = "ab" * 16
    assert leaks(folded, folded.upper()) is True
    assert folded not in redact_text(f"id {folded}", folded.upper())


def test_git_sha_rejects_a_bad_rev_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake(stdout: str, code: int) -> None:
        def _run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(args=["git"], returncode=code, stdout=stdout)

        monkeypatch.setattr(subprocess, "run", _run)

    _fake("abc\n", 0)
    with pytest.raises(SandboxError):
        git_sha(Path("."))
    _fake("g" * 40 + "\n", 0)
    with pytest.raises(SandboxError):
        git_sha(Path("."))
    _fake("a" * 40 + "\n", 1)
    with pytest.raises(SandboxError):
        git_sha(Path("."))


def test_create_under_refuses_a_foreign_parent() -> None:
    client = FakeSandbox()
    ctx = SandboxRun(
        spec=object(),
        client=client,
        checkpoint=Path("checkpoint.json"),
        moment=_WHEN,
        write_counts={"create_child_page": 0},
    )
    with pytest.raises(SandboxError, match="sandbox parent"):
        create_under(ctx, _WRONG_PARENT, "nope")
    assert client.creates == []
    assert ctx.write_counts["create_child_page"] == 0


def test_write_evidence_redacts_a_planted_token(tmp_path: Path) -> None:
    path = tmp_path / "planted.json"
    result = write_evidence(path, {"note": _SECRET}, _SECRET)
    body = path.read_text(encoding="utf-8")
    assert result == "FAIL"
    assert _SECRET not in body
    assert json.loads(body)["redaction_self_check"] == "FAIL"


@pytest.mark.parametrize("space", [_WRONG_SPACE, "89282fb0-0000-8106-809e-0003c027fa07"])
def test_wrong_space_refuses_with_zero_writes(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    space: str,
) -> None:
    client = FakeSandbox(space=space)
    code, payload, out, err, logs = _invoke(evidence, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_TARGET
    assert err == "sandbox target mismatch\n"
    assert client.creates == []
    assert _writes(payload) == 0
    assert _stage(payload, "build")["status"] == "BLOCKED"
    assert _stage(payload, "qa")["status"] == "NOT_RUN"
    assert payload["qa_verdict"] == "NOT_RUN"
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


def test_wrong_parent_and_page_space_refuse(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    clients = (
        FakeSandbox(page_id=_WRONG_PARENT.replace("-", "").upper()),
        FakeSandbox(page_space=_WRONG_SPACE),
        FakeSandbox(archived=True),
        FakeSandbox(user_type="person"),
    )
    for index, client in enumerate(clients):
        evidence = tmp_path / f"evidence-{index}.json"
        code, payload, _out, err, _logs = _invoke(
            evidence, capsys, caplog, ["--execute"], client=client
        )
        assert code == EXIT_TARGET
        assert err == "sandbox target mismatch\n"
        assert client.creates == []
        assert payload["created_pages"] == []
        assert _stage(payload, "variants")["status"] == "BLOCKED"
        assert _stage(payload, "fact_ledger")["status"] == "NOT_RUN"


def test_short_token_is_refused(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeSandbox()
    code, _payload, out, err, logs = _invoke(
        evidence,
        capsys,
        caplog,
        ["--execute"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SHORT},
    )
    assert code == EXIT_USAGE
    assert err == "notion token shape is invalid\n"
    assert client.reads == []
    assert client.creates == []
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


def test_missing_token_ignores_other_sources(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(_SECRET))
    client = FakeSandbox()
    code, payload, out, err, logs = _invoke(
        evidence,
        capsys,
        caplog,
        [],
        client=client,
        environ={"NOTION_API_KEY": _SECRET},
    )
    assert code == EXIT_NO_TOKEN
    assert err == "notion sandbox token is missing\n"
    assert client.reads == []
    assert client.creates == []
    assert _writes(payload) == 0
    assert payload["redaction_self_check"] == "PASS"
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", _OVERRIDE_ENV)
@pytest.mark.parametrize("value", ["", SANDBOX_SPACE_ID, SANDBOX_PARENT_PAGE_ID])
def test_override_env_refuses(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    name: str,
    value: str,
) -> None:
    client = FakeSandbox()
    code, payload, out, err, logs = _invoke(
        evidence,
        capsys,
        caplog,
        ["--execute"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET, name: value},
    )
    assert code == EXIT_USAGE
    assert err == "usage error\n"
    assert client.creates == []
    assert payload["created_pages"] == []
    assert _writes(payload) == 0
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


@pytest.mark.parametrize("flag", _OVERRIDE_FLAGS)
def test_argv_refused_rejects_each_flag(flag: str) -> None:
    assert argv_refused([f"{flag}={SANDBOX_PARENT_PAGE_ID}"]) is True
    assert argv_refused([flag, SANDBOX_SPACE_ID]) is True


@pytest.mark.parametrize("flag", _OVERRIDE_FLAGS)
def test_override_flag_refuses(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    flag: str,
    tmp_path: Path,
) -> None:
    token_file = tmp_path / "token.txt"
    token_file.write_text(_SECRET, encoding="utf-8")
    client = FakeSandbox()
    code, _payload, out, err, logs = _invoke(
        evidence,
        capsys,
        caplog,
        ["--execute", f"{flag}={SANDBOX_PARENT_PAGE_ID}"],
        client=client,
    )
    assert code == EXIT_USAGE
    assert err == "usage error\n"
    assert client.reads == []
    assert token_file.read_text(encoding="utf-8") == _SECRET
    _assert_clean(out, err, logs)


def test_token_on_argv_is_refused(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    code, _payload, out, err, logs = _invoke(
        evidence, capsys, caplog, ["--dry-run", _SECRET], client=FakeSandbox()
    )
    assert code == EXIT_USAGE
    assert err == "usage error\n"
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


def test_token_in_error_is_redacted(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeSandbox(error=ValueError(f"failed {_SECRET} and {_NTN}"))
    code, payload, out, err, logs = _invoke(evidence, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_API
    assert err == "notion api error\n"
    assert client.creates == []
    assert payload["error"] == "notion api error"
    assert payload["redaction_self_check"] == "PASS"
    assert "[REDACTED]" in logs
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


def test_dry_run_is_the_default_and_writes_nothing(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    before = _STATE.read_bytes()
    client = FakeSandbox()
    code, payload, out, err, logs = _invoke(evidence, capsys, caplog, [], client=client)
    assert code == EXIT_OK
    assert err == ""
    assert payload["mode"] == "dry-run"
    assert client.reads == ["bot", SANDBOX_PARENT_PAGE_ID]
    assert client.creates == []
    assert payload["created_pages"] == []
    assert payload["flagged_pages"] == []
    assert payload["possible_orphans"] == []
    assert payload["rejected_pages"] == []
    assert _writes(payload) == 0
    assert _stage(payload, "build") == {
        "available": True,
        "name": "build",
        "planned": True,
        "status": "NOT_RUN",
    }
    for name in _ABSENT:
        assert _stage(payload, name)["status"] == "NOT_RUN"
        assert _stage(payload, name)["available"] is False
    assert payload["qa_verdict"] == "NOT_RUN"
    assert payload["redaction_self_check"] == "PASS"
    assert out.strip().endswith(str(evidence))
    assert _STATE.read_bytes() == before
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


def test_both_flags_and_secret_evidence_path_refuse(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    client = FakeSandbox()
    code, _payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute", "--dry-run"], client=client
    )
    assert code == EXIT_USAGE
    assert err == "usage error\n"
    assert client.creates == []
    secret_path = tmp_path / _SECRET
    code, raw, _logs = _run(
        secret_path,
        ["--evidence-out", str(secret_path), "--dry-run"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        caplog=caplog,
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert captured.err == "usage error\n"
    assert secret_path.exists() is False
    assert raw == ""
    _assert_clean(captured.out, captured.err)


def test_execute_on_the_fake_adapter_writes_evidence(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    before = _STATE.read_bytes()
    client = FakeSandbox()
    loaded_before = set(sys.modules)
    code, payload, out, err, logs = _invoke(evidence, capsys, caplog, ["--execute"], client=client)
    added = set(sys.modules) - loaded_before
    assert code == EXIT_OK
    assert err == ""
    assert payload["mode"] == "execute"
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    assert payload["git_sha"] == sha
    assert payload["started_at"] == "2026-10-07T12:00:00Z"
    assert payload["ended_at"] == "2026-10-07T12:00:00Z"
    assert payload["asserted_space_id"] == SANDBOX_SPACE_ID
    assert payload["asserted_parent_page_id"] == SANDBOX_PARENT_PAGE_ID
    assert payload["bot_user_id"] == "bot-user"
    assert payload["qa_verdict"] == "NOT_RUN"
    assert payload["redaction_self_check"] == "PASS"
    assert "error" not in payload
    assert payload.get("run_status") != "INTERRUPTED"
    state = json.loads(_STATE.read_text(encoding="utf-8"))
    assert payload["control_state_revision"] == state["state_revision"]
    assert payload["current_session"] == state["current_session"]
    assert stat.S_IMODE(evidence.stat().st_mode) == 0o600
    assert _stage(payload, "build")["status"] == "PASS"
    assert _stage(payload, "variants")["status"] == "PASS"
    for name in _ABSENT:
        assert _stage(payload, name)["status"] == "NOT_RUN"
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert len(created) == 5
    assert created[0]["parent_id"] == SANDBOX_PARENT_PAGE_ID
    product_id = created[0]["id"]
    for page in created[1:]:
        assert page["parent_id"] == product_id
        assert page["url"].startswith("https://www.notion.so/")
    counts = payload["write_counts"]
    assert isinstance(counts, dict)
    live_top = counts["live"]
    fixture_top = counts["fixture"]
    assert isinstance(live_top, dict)
    assert isinstance(fixture_top, dict)
    assert live_top["create_child_page"] == 5
    assert "create_child_page" not in fixture_top
    assert "get_public_url" not in fixture_top
    assert "get_public_url" not in live_top
    fixture = payload["fixture"]
    live = payload["live"]
    assert isinstance(fixture, dict)
    assert isinstance(live, dict)
    assert fixture["label"] == "fixture"
    assert live["label"] == "live"
    fixture_counts = fixture["write_counts"]
    live_counts = live["write_counts"]
    assert isinstance(fixture_counts, dict)
    assert isinstance(live_counts, dict)
    assert "create_child_page" not in fixture_counts
    assert "get_public_url" not in fixture_counts
    assert live_counts == {"create_child_page": 5}
    assert live["created_pages"] == created
    assert sum(fixture_counts.values()) > 0
    assert _STATE.read_bytes() == before
    assert not any("etsy" in name or "commission" in name or "scheduler" in name for name in added)
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


def test_absent_stage_failure_stays_not_run(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client, spec=object()
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert client.creates == []
    assert _stage(payload, "build")["status"] == "FAILED"
    assert isinstance(_stage(payload, "build")["error"], str)
    assert _stage(payload, "build")["error"] != ""
    assert _stage(payload, "variants")["status"] == "NOT_RUN"
    assert _stage(payload, "qa")["status"] == "NOT_RUN"
    assert payload["qa_verdict"] == "NOT_RUN"
    assert _writes(payload) == 0


def test_run_path_imports_no_etsy_or_commission() -> None:
    banned = ("etsy", "commission", "scheduler", "api_adapter", "browser_adapter")
    names = {"APINotionAdapter", "NotionAdapterRouter", "notion_client"}
    for path in _MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported = [node.module or "", *[alias.name for alias in node.names]]
            elif isinstance(node, ast.Call):
                func = node.func
                imported = [func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")]
            else:
                continue
            for item in imported:
                lowered = item.lower()
                assert not any(word in lowered for word in banned)
                assert item not in names


class _Response:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw
        self.closed = False

    def read(self) -> bytes:
        return self._raw

    def close(self) -> None:
        self.closed = True


class _Opener:
    def __init__(self, responses: list[bytes], *, fail: BaseException | None = None) -> None:
        self.responses = responses
        self.fail = fail
        self.calls: list[tuple[str, str, object, object]] = []
        self.requests: list[urllib.request.Request] = []

    def __call__(
        self,
        request: urllib.request.Request,
        data: object = None,
        *,
        timeout: object = None,
    ) -> _Response:
        method = request.get_method()
        url = request.full_url
        self.calls.append((method, url, data, timeout))
        self.requests.append(request)
        assert _SECRET not in url
        if self.fail is not None:
            raise self.fail
        return _Response(self.responses.pop(0))


def _bot_body() -> bytes:
    return json.dumps(
        {
            "bot": {"workspace_id": _SPACE_RAW},
            "id": "bot-user",
            "object": "user",
            "type": "bot",
        }
    ).encode("utf-8")


def _page_body(page_id: str, *, parent: str | None = None, space: str | None = None) -> bytes:
    payload: dict[str, object] = {
        "id": page_id,
        "object": "page",
        "parent": {"type": "workspace", "workspace": True},
        "url": f"https://www.notion.so/{page_id.lower()}",
    }
    if parent is not None:
        payload["parent"] = {"page_id": parent, "type": "page_id"}
    if space is not None:
        payload["space_id"] = space
    return json.dumps(payload).encode("utf-8")


def test_live_client_reads_without_writing_and_redacts() -> None:
    opener = _Opener([_bot_body(), _page_body(_PARENT_RAW)])
    client = LiveSandboxClient(_SECRET, opener)
    bot = client.read_bot()
    page = client.read_page(_PARENT_RAW)
    assert repr(client) == "LiveSandboxClient"
    assert bot.space_id == SANDBOX_SPACE_ID
    assert page.page_id == SANDBOX_PARENT_PAGE_ID
    assert page.space_id == SANDBOX_SPACE_ID
    assert [call[0] for call in opener.calls] == ["GET", "GET"]
    assert opener.requests[0].full_url == "https://api.notion.com/v1/users/me"
    page_url = f"https://api.notion.com/v1/pages/{SANDBOX_PARENT_PAGE_ID}"
    assert opener.requests[1].full_url == page_url
    assert _PARENT_RAW not in opener.requests[1].full_url
    for request in opener.requests:
        assert request.get_header("Authorization") == f"Bearer {_SECRET}"
        assert request.get_header("Notion-version") == NOTION_VERSION
        assert request.get_header("Accept") == "application/json"
        assert request.get_header("Content-type") is None
    assert all(call[3] == 30 and call[2] is None for call in opener.calls)
    assert sum(client.write_counts.values()) == 0
    with pytest.raises(Exception, match="sandbox parent"):
        client.create_child_page(_WRONG_PARENT, "nope")
    assert [call[0] for call in opener.calls] == ["GET", "GET"]
    failing = _Opener([], fail=ValueError(f"down {_SECRET} {_NTN}"))
    broken = LiveSandboxClient(_SECRET, failing)
    with pytest.raises(Exception, match="REDACTED") as caught:
        broken.read_bot()
    assert _SECRET not in str(caught.value)
    assert _NTN not in str(caught.value)


def test_live_space_fallback_is_only_the_asserted_parent() -> None:
    other = "CCCCCCCCCCCC4CCC8CCCCCCCCCCCCCC1"
    opener = _Opener([_bot_body(), _page_body(other), _page_body(_PARENT_RAW, space=_WRONG_SPACE)])
    client = LiveSandboxClient(_SECRET, opener)
    client.read_bot()
    foreign = client.read_page(canonical_id(other))
    conflict = client.read_page(SANDBOX_PARENT_PAGE_ID)
    assert foreign.space_id == ""
    assert conflict.space_id == _WRONG_SPACE


def test_live_child_page_does_not_count_its_own_write() -> None:
    created = "BBBBBBBBBBBB4BBB8BBBBBBBBBBBBBB1"
    opener = _Opener([_page_body(created, parent=_PARENT_RAW)])
    client = LiveSandboxClient(_SECRET, opener)
    page = client.create_child_page(_PARENT_RAW, "Sandbox Weekly Planner")
    assert page.page_id == canonical_id(created)
    assert page.parent_id == SANDBOX_PARENT_PAGE_ID
    assert opener.calls[0][0] == "POST"
    raw_body = opener.requests[0].data
    assert isinstance(raw_body, bytes)
    sent = json.loads(raw_body)
    assert sent["parent"] == {"page_id": SANDBOX_PARENT_PAGE_ID, "type": "page_id"}
    assert _PARENT_RAW not in raw_body.decode("utf-8")
    assert opener.requests[0].get_header("Content-type") == "application/json"
    assert sum(client.write_counts.values()) == 0


def _refused(
    path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    client: FakeSandbox,
) -> tuple[int, str]:
    caplog.set_level(logging.DEBUG)
    code = main(
        ["--evidence-out", str(path), "--execute"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "Traceback" not in caplog.text
    assert _SECRET not in captured.err
    assert _SECRET not in caplog.text
    assert client.reads == []
    assert client.creates == []
    return code, captured.err


def test_directory_evidence_path_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    folder = tmp_path / "evidence"
    folder.mkdir()
    code, err = _refused(folder, capsys, caplog, FakeSandbox())
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"


def test_file_parent_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    parent = tmp_path / "not-a-directory"
    parent.write_text("blocked", encoding="utf-8")
    code, err = _refused(parent / "evidence.json", capsys, caplog, FakeSandbox())
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert parent.read_text(encoding="utf-8") == "blocked"


def test_unwritable_directory_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o500)
    try:
        code, err = _refused(blocked / "evidence.json", capsys, caplog, FakeSandbox())
    finally:
        blocked.chmod(0o700)
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert list(blocked.iterdir()) == []


def test_proc_path_is_refused_before_open(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []

    def _spy(path: str | os.PathLike[str], flags: int, mode: int = 0o777) -> int:
        opened.append(os.fspath(path))
        raise OSError("opened")

    monkeypatch.setattr(os, "open", _spy)
    code, err = _refused(Path("/proc/self/ev.json"), capsys, caplog, FakeSandbox())
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert opened == []


def test_bad_git_dir_writes_nothing(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "missing-git"))
    code, err = _refused(evidence, capsys, caplog, FakeSandbox())
    assert code == EXIT_API
    assert err == "git sha is unavailable\n"
    assert evidence.exists() is False


def test_git_missing_from_path_writes_nothing(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    empty = tmp_path / "bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    code, err = _refused(evidence, capsys, caplog, FakeSandbox())
    assert code == EXIT_API
    assert err == "git sha is unavailable\n"
    assert evidence.exists() is False


def test_evidence_refuses_existing_file_and_symlink(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    existing = tmp_path / "evidence.json"
    existing.write_text("keep", encoding="utf-8")
    code, err = _refused(existing, capsys, caplog, FakeSandbox())
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert existing.read_text(encoding="utf-8") == "keep"
    target = tmp_path / "target.json"
    link = tmp_path / "link.json"
    link.symlink_to(target)
    code, err = _refused(link, capsys, caplog, FakeSandbox())
    assert code == EXIT_USAGE
    assert target.exists() is False


@pytest.mark.parametrize("token", [" ", "true"])
def test_blank_or_junk_token_exits_64(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    token: str,
) -> None:
    client = FakeSandbox()
    code, payload, out, err, logs = _invoke(
        evidence,
        capsys,
        caplog,
        ["--execute"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": token},
    )
    assert code == EXIT_USAGE
    assert err == "notion token shape is invalid\n"
    assert client.reads == []
    assert client.creates == []
    assert payload["redaction_self_check"] == "PASS"
    raw_evidence = evidence.read_text(encoding="utf-8")
    assert "[REDACTED]" not in raw_evidence
    assert json.loads(raw_evidence)["mode"] == "dry-run"
    _assert_clean(out, err, logs, raw_evidence)


def test_evidence_out_equals_matches_the_space_form(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(evidence, capsys, caplog, [], client=client)
    assert code == EXIT_OK
    spaced = payload["git_sha"]
    other = evidence.with_name("equals.json")
    code, raw, _logs = _run(
        other,
        [f"--evidence-out={other}"],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        caplog=caplog,
    )
    assert code == EXIT_OK
    assert err == ""
    assert json.loads(raw)["git_sha"] == spaced
    capsys.readouterr()
    code = main(
        ["--evidence-out="],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert captured.err == "evidence path is refused\n"
    assert "Traceback" not in captured.err


def test_abbreviations_are_refused(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeSandbox()
    caplog.set_level(logging.DEBUG)
    code = main(
        ["--exec", "--evidence-out", str(evidence)],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert captured.err == "usage error\n"
    assert "Traceback" not in captured.err
    assert client.creates == []
    code = main(
        ["--evid", str(evidence)],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert client.creates == []
    assert "Traceback" not in captured.err


def test_non_string_user_type_exits_69(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeSandbox(user_type=1)
    code, _payload, out, err, logs = _invoke(evidence, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_API
    assert err == "notion api error\n"
    assert "Traceback" not in err
    assert client.creates == []
    _assert_clean(out, err, logs)


class _LieResponse(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        return _echo(page, parent_id=_WRONG_PARENT)


class _LieReread(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        child = canonical_id(page.page_id)
        stored = self.pages[child]
        self.pages[child] = _echo(stored, parent_id=_WRONG_PARENT, space_id=_WRONG_SPACE)
        return page


class _WrongNest(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        if len(self.creates) == 2:
            child = canonical_id(page.page_id)
            stored = self.pages[child]
            self.pages[child] = _echo(stored, parent_id=SANDBOX_PARENT_PAGE_ID)
        return page


class _Interrupt(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        if len(self.creates) == 2:
            raise KeyboardInterrupt(_SECRET)
        return super().create_child_page(parent_id, title)


class _LieReturnedId(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        if len(self.creates) == 1:
            return _echo(page, page_id=_LIE_ID)
        return page

    def read_page(self, page_id: str) -> PageView:
        if canonical_id(page_id) == canonical_id(_LIE_ID) and self.pages:
            return next(iter(self.pages.values()))
        return super().read_page(page_id)


class _WrongSpaceReturn(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        if len(self.creates) == 1:
            return _echo(page, space_id=_WRONG_SPACE)
        return page


class _BrokenAncestor(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        if len(self.creates) == 2:
            product = canonical_id(_CHILD_IDS[0])
            stored = self.pages[product]
            self.pages[product] = _echo(stored, parent_id=_WRONG_PARENT)
        return page

    def read_page(self, page_id: str) -> PageView:
        if canonical_id(page_id) == canonical_id(_WRONG_PARENT):
            return PageView(
                page_id=canonical_id(page_id),
                parent_id="",
                space_id="",
                url="https://www.notion.so/foreign",
                archived=False,
                created_by=self._actor(),
                created_time=_WHEN,
            )
        return super().read_page(page_id)


class _SecretUrl(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        child = canonical_id(page.page_id)
        stored = self.pages[child]
        leaked = f"https://www.notion.so/{_SECRET}"
        self.pages[child] = _echo(stored, url=leaked)
        return _echo(page, url=leaked)


def test_lying_response_parent_stops(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _LieResponse()
    code, _payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 1
    assert canonical_id(client.creates[0][0]) == SANDBOX_PARENT_PAGE_ID


def test_lying_reread_stops_later_writes(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _LieReread()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 1
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert [page["id"] for page in created] == [canonical_id(_CHILD_IDS[0])]
    live = payload["live"]
    assert isinstance(live, dict)
    assert live["write_counts"] == {"create_child_page": 1}


def test_wrong_nesting_stops(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _WrongNest()
    code, _payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 2


def test_interrupt_writes_redacted_evidence(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _Interrupt()
    code, payload, out, err, logs = _invoke(evidence, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_API
    assert err.startswith("sandbox interrupted")
    assert canonical_id(_CHILD_IDS[0]) in err
    assert canonical_id(_CHILD_IDS[1]) in err
    assert "Traceback" not in err
    assert "Traceback" not in logs
    assert payload["run_status"] == "INTERRUPTED"
    assert _stage(payload, "build")["status"] == "PASS"
    assert _stage(payload, "variants")["status"] == "INTERRUPTED"
    assert _stage(payload, "qa")["status"] == "NOT_RUN"
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert [page["id"] for page in created] == [canonical_id(item) for item in _CHILD_IDS[:2]]
    assert len(client.creates) == 2
    live = payload["live"]
    fixture = payload["fixture"]
    assert isinstance(live, dict)
    assert isinstance(fixture, dict)
    assert live["write_counts"] == {"create_child_page": 2}
    assert live["created_pages"] == created
    fixture_counts = fixture["write_counts"]
    assert isinstance(fixture_counts, dict)
    assert sum(fixture_counts.values()) > 0
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


def test_failed_redaction_exits_70(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeSandbox(user_id=_SECRET)
    code, payload, out, err, logs = _invoke(evidence, capsys, caplog, [], client=client)
    assert code == EXIT_REDACTION
    assert err == "redaction self-check failed\n"
    assert "sandbox dry-run ok" not in logs
    assert payload["redaction_self_check"] == "FAIL"
    assert payload["bot_user_id"] == "[REDACTED]"
    assert payload["asserted_space_id"] == SANDBOX_SPACE_ID
    assert client.creates == []
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


def test_request_body_parent_is_asserted(monkeypatch: pytest.MonkeyPatch) -> None:
    created = "BBBBBBBBBBBB4BBB8BBBBBBBBBBBBBB1"
    opener = _Opener([_page_body(created, parent=_PARENT_RAW)])
    client = LiveSandboxClient(_SECRET, opener)

    def _foreign(_parent: str) -> str:
        return _WRONG_PARENT

    monkeypatch.setattr(
        "money_machine.cli.notion_sandbox_live.asserted_body_parent",
        _foreign,
    )
    with pytest.raises(SandboxError, match="sandbox parent"):
        client.create_child_page(SANDBOX_PARENT_PAGE_ID, "nope")
    assert opener.calls == []
    assert asserted_body_parent(SANDBOX_PARENT_PAGE_ID) == SANDBOX_PARENT_PAGE_ID


def test_https_proxy_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    client = LiveSandboxClient(_SECRET)
    assert client.proxy_targets() == {}
    assert client._opener is not None  # pyright: ignore[reportPrivateUsage]


def _flagged_page(**flags: object) -> bytes:
    payload = json.loads(_page_body(_PARENT_RAW))
    assert isinstance(payload, dict)
    payload.update(flags)
    return json.dumps(payload).encode("utf-8")


def _live_execute(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    opener: _Opener,
) -> tuple[int, str, list[str]]:
    client = LiveSandboxClient(_SECRET, opener)
    code, _payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    methods = [call[0] for call in opener.calls]
    return code, err, methods


def test_foreign_workspace_bot_writes_nothing(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = json.loads(_bot_body())
    assert isinstance(body, dict)
    bot = body["bot"]
    assert isinstance(bot, dict)
    bot["workspace_id"] = _WRONG_SPACE
    opener = _Opener([json.dumps(body).encode("utf-8"), _page_body(_PARENT_RAW)])
    code, err, methods = _live_execute(evidence, capsys, caplog, opener)
    assert code == EXIT_TARGET
    assert err == "sandbox target mismatch\n"
    assert methods == ["GET", "GET"]


@pytest.mark.parametrize("flag", ["archived", "in_trash", "is_archived"])
def test_trashed_parent_writes_nothing(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    flag: str,
) -> None:
    opener = _Opener([_bot_body(), _flagged_page(**{flag: True})])
    code, err, methods = _live_execute(evidence, capsys, caplog, opener)
    assert code == EXIT_TARGET
    assert err == "sandbox target mismatch\n"
    assert methods == ["GET", "GET"]


def test_string_in_trash_is_rejected(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    opener = _Opener([_bot_body(), _flagged_page(in_trash="true")])
    code, err, methods = _live_execute(evidence, capsys, caplog, opener)
    assert code == EXIT_API
    assert err == "notion api error\n"
    assert methods == ["GET", "GET"]


def test_database_parent_and_missing_object_write_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    database = _flagged_page(object="database")
    missing = json.loads(_page_body(_PARENT_RAW))
    assert isinstance(missing, dict)
    del missing["object"]
    for index, page in enumerate((database, json.dumps(missing).encode("utf-8"))):
        evidence = tmp_path / f"live-{index}.json"
        opener = _Opener([_bot_body(), page])
        code, err, methods = _live_execute(evidence, capsys, caplog, opener)
        assert code == EXIT_API
        assert err == "notion api error\n"
        assert methods == ["GET", "GET"]


def test_lying_create_id_stops_before_colours(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _LieReturnedId()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 1
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert [page["id"] for page in created] == [canonical_id(_LIE_ID)]
    assert all(canonical_id(parent) != canonical_id(_LIE_ID) for parent, _title in client.creates)


def test_wrong_space_on_create_return_stops(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _WrongSpaceReturn()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert _stage(payload, "build")["status"] == "FAILED"
    assert len(client.creates) == 1
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert [page["id"] for page in created] == [canonical_id(_CHILD_IDS[0])]
    assert payload["flagged_pages"] == [
        {"id": canonical_id(_CHILD_IDS[0]), "reason": "space_conflict"}
    ]
    live = payload["live"]
    assert isinstance(live, dict)
    assert live["write_counts"] == {"create_child_page": 1}


def test_token_in_created_url_exits_70(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _SecretUrl()
    code, payload, out, err, logs = _invoke(evidence, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_REDACTION
    assert err == "redaction self-check failed\n"
    assert "sandbox execute ok" not in logs
    assert payload["redaction_self_check"] == "FAIL"
    assert len(client.creates) == 5
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


def test_clock_runtime_error_is_redacted(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _boom() -> datetime:
        raise RuntimeError(f"clock {_SECRET}")

    client = FakeSandbox()
    caplog.set_level(logging.DEBUG)
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_boom,
    )
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert "Traceback" not in captured.err
    assert "Traceback" not in caplog.text
    assert _SECRET not in captured.err
    assert _SECRET not in caplog.text
    assert client.reads == []
    assert client.creates == []
    assert evidence.exists() is False


def test_evidence_write_oserror_is_redacted(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError(f"disk {_SECRET}")

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _boom)
    client = FakeSandbox()
    caplog.set_level(logging.DEBUG)
    code = main(
        ["--evidence-out", str(evidence), "--dry-run"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert captured.err == "evidence path is refused\n"
    assert "Traceback" not in captured.err
    assert "Traceback" not in caplog.text
    assert _SECRET not in captured.err
    assert _SECRET not in caplog.text
    assert client.creates == []
    written = evidence.read_text(encoding="utf-8") if evidence.exists() else ""
    assert _SECRET not in written


def test_encoded_token_is_redacted_from_info_logs(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    digest = base64.b64encode(_SECRET.encode("utf-8")).decode("ascii")
    encoded = quote(_SECRET, safe="").replace("_", "%5F")
    client = FakeSandbox(error=ValueError(f"down {digest} {encoded}"))
    code, _payload, out, err, logs = _invoke(evidence, capsys, caplog, [], client=client)
    assert code == EXIT_API
    assert digest not in logs
    assert encoded not in logs
    assert _SECRET not in logs
    assert client.creates == []
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


def test_hex_token_equal_to_the_page_id_sends_nothing() -> None:
    token = _PARENT_RAW.lower()
    opener = _Opener([_page_body(_PARENT_RAW)])
    client = LiveSandboxClient(token, opener)
    with pytest.raises(SandboxError, match="notion api error"):
        client.read_page(_PARENT_RAW)
    assert opener.calls == []


def test_database_id_parent_is_not_a_page_parent(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = json.loads(_page_body(_PARENT_RAW, space=_SPACE_RAW))
    assert isinstance(body, dict)
    body["parent"] = {"database_id": _WRONG_PARENT, "type": "database_id"}
    parsed = parse_page(body, fallback_space=SANDBOX_SPACE_ID, expected_id=SANDBOX_PARENT_PAGE_ID)
    assert parsed is not None
    assert parsed.parent_type == "database_id"
    assert parsed.parent_id == ""
    bot = BotView(user_id="bot-user", user_type="bot", space_id=SANDBOX_SPACE_ID)
    assert target_ok(bot, parsed) is False
    opener = _Opener([_bot_body(), json.dumps(body).encode("utf-8")])
    code, err, methods = _live_execute(evidence, capsys, caplog, opener)
    assert code == EXIT_TARGET
    assert err == "sandbox target mismatch\n"
    assert methods == ["GET", "GET"]


def test_read_base_exceptions_stay_redacted(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    samples: tuple[tuple[str, BaseException], ...] = (
        ("system", SystemExit(7)),
        ("interrupt", KeyboardInterrupt(_SECRET)),
        ("base", BaseException(_SECRET)),
    )
    for name, exc in samples:
        path = evidence.with_name(f"read-{name}.json")
        client = FakeSandbox(error=exc)
        code = main(
            ["--evidence-out", str(path), "--execute"],
            client=client,
            environ={"NOTION_SANDBOX_TOKEN": _SECRET},
            clock=_clock,
        )
        captured = capsys.readouterr()
        assert code == EXIT_API
        assert captured.err == "interrupted\n"
        assert "Traceback" not in captured.err
        assert "Traceback" not in caplog.text
        assert _SECRET not in captured.err
        assert _SECRET not in caplog.text
        body = path.read_text(encoding="utf-8")
        assert body != ""
        assert _SECRET not in body
        loaded = json.loads(body)
        assert loaded["error"] == "interrupted"
        assert loaded["run_status"] == "INTERRUPTED"
        assert _stage(loaded, "build")["status"] == "INTERRUPTED"
        assert _stage(loaded, "variants")["status"] == "NOT_RUN"
        assert _stage(loaded, "qa")["status"] == "NOT_RUN"
        assert client.creates == []


def test_parse_page_keeps_a_url_and_fills_a_blank_one() -> None:
    body = json.loads(_page_body(_PARENT_RAW, space=_SPACE_RAW))
    assert isinstance(body, dict)
    body["url"] = "https://www.notion.so/CustomTitle"
    page = parse_page(body, fallback_space=SANDBOX_SPACE_ID, expected_id=SANDBOX_PARENT_PAGE_ID)
    assert page is not None
    assert page.url == "https://www.notion.so/CustomTitle"
    del body["url"]
    blank = parse_page(body, fallback_space=SANDBOX_SPACE_ID, expected_id=SANDBOX_PARENT_PAGE_ID)
    assert blank is not None
    assert blank.url == f"https://www.notion.so/{_PARENT_RAW.lower()}"


def test_proxy_map_reads_string_proxy_entries() -> None:
    director = urllib.request.build_opener(
        urllib.request.ProxyHandler({"https": "http://127.0.0.1:9"})
    )
    assert proxy_map(director) == {"https": "http://127.0.0.1:9"}


def test_repo_root_falls_back_to_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    outside = tmp_path / "notion_sandbox_guard.py"
    real = Path.resolve

    def _resolve(self: Path, strict: bool = False) -> Path:
        if self.name == "notion_sandbox_guard.py":
            return outside
        return real(self, strict)

    monkeypatch.setattr(Path, "resolve", _resolve)
    assert repo_root() == Path.cwd()


def test_broken_ancestor_stops_later_writes(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _BrokenAncestor()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 2
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert [page["id"] for page in created] == [canonical_id(item) for item in _CHILD_IDS[:2]]


class _TrashOnChain(FakeSandbox):
    def read_page(self, page_id: str) -> PageView:
        page = super().read_page(page_id)
        if canonical_id(page_id) == canonical_id(_CHILD_IDS[0]) and len(self.creates) >= 2:
            return _echo(page, archived=True)
        return page


class _TrashOnConfirm(FakeSandbox):
    def read_page(self, page_id: str) -> PageView:
        page = super().read_page(page_id)
        if canonical_id(page_id) == canonical_id(_CHILD_IDS[0]) and len(self.creates) == 1:
            return _echo(page, archived=True)
        return page


class _StaleCreate(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        if len(self.creates) != 1:
            return page
        self.pages[canonical_id(_LIE_ID)] = _echo(page, page_id=_LIE_ID)
        return _echo(page, page_id=_LIE_ID, created_by="other-user")

    def read_page(self, page_id: str) -> PageView:
        stored = self.pages.get(canonical_id(page_id))
        if stored is not None and canonical_id(page_id) == canonical_id(_LIE_ID):
            return stored
        return super().read_page(page_id)


class _StaleConfirm(FakeSandbox):
    def read_page(self, page_id: str) -> PageView:
        page = super().read_page(page_id)
        if canonical_id(page_id) == canonical_id(_CHILD_IDS[0]) and len(self.creates) == 1:
            return _echo(page, created_time=datetime(2020, 1, 1, tzinfo=UTC))
        return page


class _RepeatColour(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        if len(self.creates) < 3:
            return page
        echo = self.pages[canonical_id(_CHILD_IDS[1])]
        return echo


def test_trashed_product_page_stops_further_writes(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _TrashOnChain()
    code, _payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 2


def test_trashed_confirm_stops_further_writes(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _TrashOnConfirm()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 1
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert [page["id"] for page in created] == [canonical_id(_CHILD_IDS[0])]
    assert payload["flagged_pages"] == [{"id": canonical_id(_CHILD_IDS[0]), "reason": "archived"}]
    assert payload["rejected_pages"] == []


def test_stale_foreign_page_is_not_a_parent(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _StaleCreate()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 1
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert created == []
    assert payload["rejected_pages"] == [{"id": canonical_id(_LIE_ID), "reason": "not_new"}]


def test_stale_confirm_stops_later_writes(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _StaleConfirm()
    code, _payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 1
    created = _payload["created_pages"]
    assert isinstance(created, list)
    assert created == []
    assert _payload["rejected_pages"] == [{"id": canonical_id(_CHILD_IDS[0]), "reason": "not_new"}]


def test_repeated_created_id_is_refused(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _RepeatColour()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    created = payload["created_pages"]
    assert isinstance(created, list)
    ids = [page["id"] for page in created]
    assert ids.count(canonical_id(_CHILD_IDS[1])) == 1
    assert len(client.creates) == 3


def test_non_string_bot_user_id_is_omitted(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeSandbox(user_id=7)
    code, payload, _out, err, _logs = _invoke(evidence, capsys, caplog, [], client=client)
    assert code == EXIT_OK
    assert err == ""
    assert payload["bot_user_id"] is None
    assert "error" not in payload
    assert client.creates == []


def test_base64_token_in_evidence_exits_70(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    digest = base64.b64encode(_SECRET.encode("utf-8")).decode("ascii")
    client = FakeSandbox(user_id=digest)
    code, payload, out, err, logs = _invoke(evidence, capsys, caplog, [], client=client)
    assert code == EXIT_REDACTION
    assert err == "redaction self-check failed\n"
    assert "sandbox dry-run ok" not in logs
    assert digest not in evidence.read_text(encoding="utf-8")
    assert payload["redaction_self_check"] == "FAIL"
    assert client.creates == []
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


def test_missing_workspace_id_writes_nothing(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = json.loads(_bot_body())
    assert isinstance(body, dict)
    bot = body["bot"]
    assert isinstance(bot, dict)
    del bot["workspace_id"]
    opener = _Opener([json.dumps(body).encode("utf-8"), _page_body(_PARENT_RAW)])
    code, err, methods = _live_execute(evidence, capsys, caplog, opener)
    assert code == EXIT_TARGET
    assert err == "sandbox target mismatch\n"
    assert methods == ["GET", "GET"]
    assert "POST" not in methods


def test_symlinked_parent_directory_is_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    path = link / "evidence.json"
    client = FakeSandbox()
    code, err = _refused(path, capsys, caplog, client)
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert path.exists() is False


def test_data_source_parent_writes_nothing(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = json.loads(_page_body(_PARENT_RAW, space=_SPACE_RAW))
    assert isinstance(body, dict)
    body["parent"] = {"data_source_id": _WRONG_PARENT, "type": "data_source_id"}
    parsed = parse_page(body, fallback_space=SANDBOX_SPACE_ID, expected_id=SANDBOX_PARENT_PAGE_ID)
    assert parsed is not None
    assert parsed.parent_type == "data_source_id"
    assert parsed.parent_id == ""
    bot = BotView(user_id="bot-user", user_type="bot", space_id=SANDBOX_SPACE_ID)
    assert target_ok(bot, parsed) is False
    opener = _Opener([_bot_body(), json.dumps(body).encode("utf-8")])
    code, err, methods = _live_execute(evidence, capsys, caplog, opener)
    assert code == EXIT_TARGET
    assert err == "sandbox target mismatch\n"
    assert methods == ["GET", "GET"]


def test_redirect_is_not_followed() -> None:
    class _Redirect:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def __call__(
            self,
            request: urllib.request.Request,
            data: object = None,
            *,
            timeout: object = None,
        ) -> _Response:
            del data, timeout
            self.urls.append(request.full_url)
            response = _Response(b"")
            response.status = 302  # type: ignore[attr-defined]
            return response

    opener = _Redirect()
    client = LiveSandboxClient(_SECRET, opener)
    with pytest.raises(SandboxError, match="notion api error"):
        client.read_bot()
    assert opener.urls == ["https://api.notion.com/v1/users/me"]
    assert all("evil.example" not in url for url in opener.urls)
    director = sandbox_opener()
    installed = getattr(director, "handlers", None)
    assert isinstance(installed, list)
    assert any(type(handler) is RefuseRedirect for handler in installed)
    request = urllib.request.Request("https://api.notion.com/v1/users/me")
    with pytest.raises(SandboxError, match="notion api error"):
        RefuseRedirect().redirect_request(
            request,
            _Response(b""),
            302,
            "Found",
            {},
            "https://evil.example/steal",
        )


def test_ssl_env_is_refused_and_ignored(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert cert_env_set({"SSL_CERT_FILE": "/tmp/ca.pem"}) is True
    assert cert_env_set({"SSL_CERT_DIR": "/tmp/cas"}) is True
    assert cert_env_set({"NOTION_SANDBOX_TOKEN": _SECRET}) is False
    client = FakeSandbox()
    for name in ("SSL_CERT_FILE", "SSL_CERT_DIR", "SSLKEYLOGFILE"):
        path = evidence.with_name(f"{name}.json")
        code, payload, out, err, logs = _invoke(
            path,
            capsys,
            caplog,
            ["--execute"],
            client=client,
            environ={"NOTION_SANDBOX_TOKEN": _SECRET, name: "/tmp/sandbox-ca.pem"},
        )
        assert code == EXIT_USAGE
        assert err == "usage error\n"
        assert client.reads == []
        assert client.creates == []
        assert _writes(payload) == 0
        _assert_clean(out, err, logs)
    monkeypatch.setenv("SSL_CERT_FILE", "/no/such/sandbox-ca.pem")
    monkeypatch.setenv("SSL_CERT_DIR", "/no/such/sandbox-cas")
    monkeypatch.setenv("SSLKEYLOGFILE", "/no/such/sandbox-keylog")
    before = dict(os.environ)
    context = sandbox_tls_context()
    assert dict(os.environ) == before
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    if os.path.isfile(ssl.get_default_verify_paths().openssl_cafile):
        # Debian 13 has no compiled-in cert.pem. The directory fallback is
        # test_tls_context_loads_the_compiled_in_paths.
        assert context.get_ca_certs()
    assert sandbox_opener() is not None


def test_enospc_after_creates_prints_ids(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> int:
        raise OSError(errno.ENOSPC, "nospace")

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _boom)
    client = FakeSandbox()
    caplog.set_level(logging.DEBUG)
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert "evidence path is refused" not in captured.err
    assert "evidence write failed" in captured.err
    assert canonical_id(_CHILD_IDS[0]) in captured.err
    assert _SECRET not in captured.err
    assert "Traceback" not in captured.err
    assert len(client.creates) == 5
    assert evidence.exists() is False
    assert evidence.with_name(f".{evidence.name}.tmp").exists() is False


def test_short_evidence_write_is_complete(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = os.write
    state = {"short": True}

    def _short(fd: int, data: bytes | bytearray | memoryview) -> int:
        if state["short"]:
            state["short"] = False
            return real(fd, bytes(data[:1]))
        return real(fd, data)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _short)
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(evidence, capsys, caplog, [], client=client)
    assert code == EXIT_OK
    assert err == ""
    assert state["short"] is False
    assert payload["mode"] == "dry-run"
    assert evidence.read_bytes().endswith(b"\n")


def test_swapped_evidence_file_does_not_exit_ok(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = os.write

    def _swap(fd: int, data: bytes | bytearray | memoryview) -> int:
        evidence.write_bytes(b"swapped")
        return real(fd, data)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _swap)
    client = FakeSandbox()
    code, _raw, _logs = _run(
        evidence,
        ["--evidence-out", str(evidence)],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        caplog=caplog,
    )
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert code != EXIT_OK
    assert "evidence file changed" in captured.err
    assert evidence.read_bytes() == b"swapped"
    assert client.creates == []


def test_control_state_container_exits_69(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = json.loads
    payloads: list[object] = [[], "control"]

    def _loads(text: str, *args: object, **kwargs: object) -> object:
        if "state_revision" in text and payloads:
            return payloads.pop(0)
        return real(text)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.json.loads", _loads)
    client = FakeSandbox()
    for index in range(2):
        path = tmp_path / f"control-{index}.json"
        code = main(
            ["--evidence-out", str(path), "--execute"],
            client=client,
            environ={"NOTION_SANDBOX_TOKEN": _SECRET},
            clock=_clock,
        )
        captured = capsys.readouterr()
        assert code == EXIT_API
        assert captured.err == "control state is unreadable\n"
        assert "Traceback" not in captured.err
        assert client.reads == []
        assert client.creates == []


def test_stdout_full_and_non_ascii_path_are_documented(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeSandbox()
    full = open("/dev/full", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    try:
        monkeypatch.setattr(sys, "stdout", full)
        code = main(
            ["--evidence-out", str(evidence), "--dry-run"],
            client=client,
            environ={"NOTION_SANDBOX_TOKEN": _SECRET},
            clock=_clock,
        )
        captured = capsys.readouterr()
        assert code == EXIT_API
        assert "stdout is unavailable" in captured.err
        assert json.loads(evidence.read_text(encoding="utf-8"))["mode"] == "dry-run"
        assert _SECRET not in captured.err
    finally:
        with contextlib.suppress(OSError):
            full.close()

    class _Ascii:
        def write(self, text: str) -> int:
            text.encode("ascii")
            return len(text)

        def flush(self) -> None:
            return None

    monkeypatch.setattr(sys, "stdout", _Ascii())
    path = evidence.with_name("证据.json")
    code = main(
        ["--evidence-out", str(path), "--dry-run"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert "stdout is unavailable" in captured.err
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["redaction_self_check"] == "PASS"
    assert _SECRET not in path.read_text(encoding="utf-8")


def _doc_page(page_id: str, parent: str | None) -> bytes:
    parent_payload: dict[str, object]
    if parent is None:
        parent_payload = {"type": "workspace", "workspace": True}
    else:
        parent_payload = {"page_id": parent, "type": "page_id"}
    return json.dumps(
        {
            "archived": False,
            "created_by": {"id": "bot-user", "object": "user"},
            "created_time": "2026-10-07T12:00:00.000Z",
            "id": page_id,
            "in_trash": False,
            "object": "page",
            "parent": parent_payload,
            "url": f"https://www.notion.so/{page_id.replace('-', '')}",
        }
    ).encode("utf-8")


class _DocOpener:
    def __init__(
        self,
        *,
        confirm_fails: bool = False,
        interrupt_after_store: int | None = None,
    ) -> None:
        self.confirm_fails = confirm_fails
        self.interrupt_after_store = interrupt_after_store
        self.posts: list[str] = []
        self.calls: list[tuple[str, str]] = []
        self.pages: dict[str, bytes] = {}

    def __call__(
        self,
        request: urllib.request.Request,
        data: object = None,
        *,
        timeout: object = None,
    ) -> _Response:
        del data
        method = request.get_method()
        url = request.full_url
        self.calls.append((method, url))
        assert url.startswith("https://api.notion.com/")
        assert timeout == 30
        assert _SECRET not in url
        if method == "GET" and url.endswith("/v1/users/me"):
            return _Response(_bot_body())
        if method == "GET" and "/v1/pages/" in url:
            page_id = url.rsplit("/", 1)[1]
            if page_id == SANDBOX_PARENT_PAGE_ID:
                return _Response(_doc_page(SANDBOX_PARENT_PAGE_ID, None))
            if self.confirm_fails and page_id == canonical_id(_CHILD_IDS[0]):
                return _Response(b'{"object":"error","status":404}')
            stored = self.pages.get(page_id)
            assert stored is not None
            return _Response(stored)
        if method == "POST" and url.endswith("/v1/pages"):
            raw = request.data
            assert isinstance(raw, bytes)
            body = json.loads(raw)
            assert isinstance(body, dict)
            parent = body["parent"]
            assert isinstance(parent, dict)
            parent_id = parent["page_id"]
            assert type(parent_id) is str
            page_id = canonical_id(_CHILD_IDS[len(self.posts)])
            self.posts.append(parent_id)
            encoded = _doc_page(page_id, parent_id)
            self.pages[page_id] = encoded
            if self.interrupt_after_store == len(self.posts):
                raise KeyboardInterrupt()
            return _Response(encoded)
        raise AssertionError(f"{method} {url}")


def test_doc_shaped_pages_execute_without_a_space(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    opener = _DocOpener()
    client = LiveSandboxClient(_SECRET, opener)
    code, payload, out, err, logs = _invoke(evidence, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_OK
    assert err == ""
    assert opener.posts == [
        SANDBOX_PARENT_PAGE_ID,
        canonical_id(_CHILD_IDS[0]),
        canonical_id(_CHILD_IDS[0]),
        canonical_id(_CHILD_IDS[0]),
        canonical_id(_CHILD_IDS[0]),
    ]
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert [page["id"] for page in created] == [canonical_id(item) for item in _CHILD_IDS]
    assert payload.get("run_status") != "INTERRUPTED"
    assert "error" not in payload
    live = payload["live"]
    assert isinstance(live, dict)
    assert live["write_counts"] == {"create_child_page": 5}
    _assert_clean(out, err, logs, evidence.read_text(encoding="utf-8"))


def test_doc_shaped_failure_still_records_the_created_id(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    opener = _DocOpener(confirm_fails=True)
    client = LiveSandboxClient(_SECRET, opener)
    code, payload, out, err, logs = _invoke(evidence, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert opener.posts == [SANDBOX_PARENT_PAGE_ID]
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert [page["id"] for page in created] == [canonical_id(_CHILD_IDS[0])]
    assert _SECRET not in evidence.read_text(encoding="utf-8")
    _assert_clean(out, err, logs)


def test_module_entry_point_runs_main(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("NOTION_SANDBOX_TOKEN", None)
    env.pop("SSL_CERT_FILE", None)
    env.pop("SSL_CERT_DIR", None)
    env["PYTHONIOENCODING"] = "utf-8"
    bare = subprocess.run(
        [sys.executable, "-m", "money_machine.cli.notion_sandbox"],
        capture_output=True,
        text=True,
        cwd=repo_root(),
        env=env,
        check=False,
    )
    assert bare.returncode == EXIT_USAGE
    assert "Traceback" not in bare.stderr
    path = tmp_path / "module-entry.json"
    missing = subprocess.run(
        [
            sys.executable,
            "-m",
            "money_machine.cli.notion_sandbox",
            "--evidence-out",
            str(path),
        ],
        capture_output=True,
        text=True,
        cwd=repo_root(),
        env=env,
        check=False,
    )
    assert missing.returncode == EXIT_NO_TOKEN
    assert path.is_file()
    assert _SECRET not in path.read_text(encoding="utf-8")


class _InterruptAfterStore(FakeSandbox):
    def __init__(self, index: int, exc: BaseException) -> None:
        super().__init__()
        self.index = index
        self.exc = exc

    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        if len(self.creates) == self.index + 1:
            raise self.exc
        return page


class _DocInterrupt(LiveSandboxClient):
    def __init__(self, opener: _DocOpener, index: int, exc: BaseException) -> None:
        super().__init__(_SECRET, opener)
        self.index = index
        self.exc = exc
        self.completed = 0

    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        self.completed += 1
        if self.completed == self.index + 1:
            raise self.exc
        return page


class _WrongSpaceAncestor(FakeSandbox):
    def read_page(self, page_id: str) -> PageView:
        page = super().read_page(page_id)
        if canonical_id(page_id) == SANDBOX_PARENT_PAGE_ID and self.creates:
            return _echo(page, space_id=_WRONG_SPACE)
        return page


class _LieParentOnly(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        child = canonical_id(page.page_id)
        self.pages[child] = _echo(self.pages[child], parent_id=_WRONG_PARENT)
        return page


class _LieSpaceOnly(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        child = canonical_id(page.page_id)
        self.pages[child] = _echo(self.pages[child], space_id=_WRONG_SPACE)
        return page


def _recorded(payload: dict[str, object]) -> list[str]:
    created = payload["created_pages"]
    assert isinstance(created, list)
    return [page["id"] for page in created if isinstance(page, dict)]


@pytest.mark.parametrize(
    ("index", "exc"),
    [
        (0, KeyboardInterrupt(_SECRET)),
        (2, BaseException(_SECRET)),
        (4, KeyboardInterrupt("stop")),
    ],
)
def test_interrupt_after_store_records_the_created_id(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    index: int,
    exc: BaseException,
) -> None:
    path = tmp_path / f"stored-{index}.json"
    client = _InterruptAfterStore(index, exc)
    code, payload, out, err, logs = _invoke(path, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_API
    assert err.startswith("sandbox interrupted")
    for page_id in _recorded(payload):
        assert page_id in err
    assert payload["run_status"] == "INTERRUPTED"
    assert len(client.creates) == index + 1
    assert _recorded(payload) == [canonical_id(item) for item in _CHILD_IDS[: index + 1]]
    assert "Traceback" not in err
    _assert_clean(out, err, logs, path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("index", "exc"),
    [
        (0, BaseException(_SECRET)),
        (2, KeyboardInterrupt(_SECRET)),
        (4, BaseException("stop")),
    ],
)
def test_doc_shaped_interrupt_after_store_records_the_created_id(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    index: int,
    exc: BaseException,
) -> None:
    path = tmp_path / f"doc-stored-{index}.json"
    opener = _DocOpener()
    client = _DocInterrupt(opener, index, exc)
    code, payload, out, err, logs = _invoke(path, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_API
    assert err.startswith("sandbox interrupted")
    for page_id in _recorded(payload):
        assert page_id in err
    assert payload["run_status"] == "INTERRUPTED"
    assert len(opener.posts) == index + 1
    assert _recorded(payload) == [canonical_id(item) for item in _CHILD_IDS[: index + 1]]
    assert "Traceback" not in err
    _assert_clean(out, err, logs, path.read_text(encoding="utf-8"))


def test_encoded_token_evidence_path_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeSandbox()
    digest = base64.b64encode(_SECRET.encode("utf-8")).decode("ascii")
    encoded = quote(_SECRET, safe="").replace("_", "%5F")
    for name in (digest, encoded):
        path = tmp_path / f"{name}.json"
        code, _payload, out, err, logs = _invoke(
            path,
            capsys,
            caplog,
            [],
            client=client,
            environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        )
        assert code == EXIT_USAGE
        assert err == "usage error\n"
        assert path.exists() is False
        assert client.reads == []
        assert client.creates == []
        _assert_clean(out, err, logs)


def test_wrong_space_ancestor_is_not_appended(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _WrongSpaceAncestor()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 1
    assert _recorded(payload) == [canonical_id(_CHILD_IDS[0])]
    assert payload["flagged_pages"] == [{"id": canonical_id(_CHILD_IDS[0]), "reason": "chain"}]


def test_parent_only_reread_stops_without_a_space_lie(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _LieParentOnly()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 1
    assert _recorded(payload) == [canonical_id(_CHILD_IDS[0])]


def test_space_only_reread_is_not_appended(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _LieSpaceOnly()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 1
    assert _recorded(payload) == [canonical_id(_CHILD_IDS[0])]
    assert payload["flagged_pages"] == [
        {"id": canonical_id(_CHILD_IDS[0]), "reason": "space_conflict"}
    ]


def test_sandbox_parent_in_a_foreign_space_fails_the_chain() -> None:
    client = FakeSandbox()
    ctx = SandboxRun(
        spec=object(),
        client=client,
        checkpoint=Path("checkpoint.json"),
        moment=_WHEN,
        write_counts={},
    )
    page = PageView(
        page_id=SANDBOX_PARENT_PAGE_ID,
        parent_id="",
        space_id=_WRONG_SPACE,
        url="https://www.notion.so/x",
        archived=False,
    )
    with pytest.raises(SandboxError, match="requested parent"):
        chain_reaches_sandbox(ctx, page)
    assert ctx.created == []
    assert client.reads == []


def test_empty_parent_chain_does_not_read_again() -> None:
    client = FakeSandbox()
    ctx = SandboxRun(
        spec=object(),
        client=client,
        checkpoint=Path("checkpoint.json"),
        moment=_WHEN,
        write_counts={},
    )
    page = PageView(
        page_id=canonical_id(_CHILD_IDS[0]),
        parent_id="",
        space_id=SANDBOX_SPACE_ID,
        url="https://www.notion.so/x",
        archived=False,
    )
    with pytest.raises(SandboxError, match="requested parent"):
        chain_reaches_sandbox(ctx, page)
    assert client.reads == []


def test_proc_path_helper_rejects_proc_itself() -> None:
    assert under_proc(Path("/proc")) is True
    assert under_proc(Path("/proc/self")) is True
    assert under_proc(Path("//proc/self/ev.json")) is True
    assert under_proc(Path("///proc/self/ev.json")) is True
    assert under_proc(Path("/tmp/evidence.json")) is False
    assert under_proc(Path("/proc/1/root/x")) is True


def test_string_revision_is_unreadable(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = json.loads

    def _loads(text: str, *args: object, **kwargs: object) -> object:
        if "state_revision" in text:
            return {"current_session": 7, "head_sha": "a" * 40, "state_revision": "58"}
        return real(text)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.json.loads", _loads)
    client = FakeSandbox()
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert captured.err == "control state is unreadable\n"
    assert client.reads == []
    assert client.creates == []


def test_repo_root_needs_both_markers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    expected = repo_root()
    monkeypatch.chdir(tmp_path)
    assert repo_root() == expected


def test_naive_clock_is_refused(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeSandbox()

    def _naive() -> datetime:
        return datetime(2026, 10, 7)

    caplog.set_level(logging.DEBUG)
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_naive,
    )
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert captured.err == "clock must be timezone-aware\n"
    assert client.reads == []
    assert client.creates == []
    assert evidence.exists() is False


def test_evidence_out_without_a_value_is_usage(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        ["--dry-run", "--evidence-out", str(evidence)],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert evidence.is_file()
    stray = Path("--evidence-out")
    if stray.exists():
        stray.unlink()
        raise AssertionError("the following flag was used as the evidence path")
    missing = main(
        ["--evidence-out"],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    assert missing == EXIT_USAGE
    assert "Traceback" not in captured.err


def test_non_string_bot_id_is_rejected(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert parse_bot({"bot": {"workspace_id": _SPACE_RAW}, "id": 7, "type": "bot"}) is None
    body = {"bot": {"workspace_id": _SPACE_RAW}, "id": 7, "object": "user", "type": "bot"}
    opener = _Opener([json.dumps(body).encode("utf-8"), _page_body(_PARENT_RAW)])
    code, err, methods = _live_execute(evidence, capsys, caplog, opener)
    assert code == EXIT_API
    assert err == "notion api error\n"
    assert "Traceback" not in err
    assert "NoneType" not in caplog.text
    assert "notion api error" in caplog.text
    assert methods == ["GET"]


def test_bot_payload_without_a_bot_object_exits_65(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = {"id": "bot-user", "object": "user", "type": "bot"}
    opener = _Opener([json.dumps(body).encode("utf-8"), _page_body(_PARENT_RAW, space=_SPACE_RAW)])
    code, err, methods = _live_execute(evidence, capsys, caplog, opener)
    assert code == EXIT_TARGET
    assert err == "sandbox target mismatch\n"
    assert "Traceback" not in err
    assert methods == ["GET", "GET"]
    assert "POST" not in methods


def test_proxy_map_drops_non_strings() -> None:
    class _Proxies(urllib.request.ProxyHandler):
        proxies: dict[str, object]

        def __init__(self) -> None:
            super().__init__({"http": "http://127.0.0.1:9"})
            self.proxies = {"https": 9, "http": "http://127.0.0.1:9"}

    director = urllib.request.build_opener(_Proxies())
    assert proxy_map(director) == {"http": "http://127.0.0.1:9"}


def test_explicit_space_refuses_a_malformed_id() -> None:
    with pytest.raises(SandboxError, match="notion api error"):
        explicit_space({"space_id": "nope", "workspace_id": SANDBOX_SPACE_ID})
    with pytest.raises(SandboxError, match="notion api error"):
        explicit_space({"space_id": 5, "workspace_id": _SPACE_RAW})
    assert explicit_space({"workspace_id": SANDBOX_SPACE_ID}) == SANDBOX_SPACE_ID
    assert explicit_space({"space_id": "", "workspace_id": SANDBOX_SPACE_ID}) == SANDBOX_SPACE_ID
    assert explicit_space({"workspace_id": None}) == ""
    assert explicit_space({"space_id": None, "workspace_id": SANDBOX_SPACE_ID}) == SANDBOX_SPACE_ID


def test_variants_without_a_product_page_are_a_sandbox_error() -> None:
    ctx = SandboxRun(
        spec=sandbox_product_spec(_WHEN),
        client=FakeSandbox(),
        checkpoint=Path("checkpoint.json"),
        moment=_WHEN,
        write_counts={},
        probe=FixtureNotionAdapter(),
        product_page_id=None,
    )

    async def _call() -> None:
        await stage_runners()["run_variants"](ctx)

    with pytest.raises(SandboxError, match="variants require the build stage"):
        asyncio.run(_call())


def test_parse_page_fallback_does_not_fill_a_different_page() -> None:
    body = json.loads(_page_body(canonical_id(_CHILD_IDS[0])))
    assert isinstance(body, dict)
    page = parse_page(
        body,
        fallback_space=SANDBOX_SPACE_ID,
        expected_id=SANDBOX_PARENT_PAGE_ID,
    )
    assert page is not None
    assert page.space_id == ""


def test_commit_evidence_rejects_a_replaced_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "evidence.json"
    real = os.write

    def _swap(fd: int, data: bytes | bytearray | memoryview) -> int:
        path.write_bytes(b"swapped")
        return real(fd, data)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _swap)
    with pytest.raises(SandboxError, match="changed") as caught:
        commit_evidence(path, {"note": "ok"}, None)
    assert caught.value.code == EXIT_API
    assert path.read_bytes() == b"swapped"


def _bound_run(client: FakeSandbox, *, bot_space_id: str = SANDBOX_SPACE_ID) -> SandboxRun:
    return SandboxRun(
        spec=sandbox_product_spec(_WHEN),
        client=client,
        checkpoint=Path("checkpoint.json"),
        moment=_WHEN,
        write_counts={},
        bot_user_id="bot-user",
        bot_space_id=bot_space_id,
    )


def test_equals_form_records_an_override_refusal(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeSandbox()
    code = main(
        [f"--evidence-out={evidence}"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET, "NOTION_TOKEN_FILE": "ignored"},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert captured.err == "usage error\n"
    assert evidence.is_file()
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["error"] == "usage error"
    assert client.reads == []
    assert client.creates == []


class _NoBind(FakeSandbox):
    def __getattribute__(self, name: str) -> object:
        if name == "bind_created":
            raise AttributeError(name)
        return super().__getattribute__(name)


def test_execute_without_bind_created_still_records(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _NoBind()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_OK
    assert err == ""
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert len(created) == 5
    assert "error" not in payload


def test_empty_bot_user_id_still_executes(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeSandbox(user_id="")
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_OK
    assert err == ""
    assert payload["bot_user_id"] == ""
    assert len(client.creates) == 5
    assert "error" not in payload


def test_zero_length_write_exits_69(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _zero(fd: int, data: bytes | bytearray | memoryview) -> int:
        del fd, data
        return 0

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _zero)
    code = main(
        ["--evidence-out", str(evidence)],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert captured.err == "evidence write failed\n"
    assert "Traceback" not in captured.err
    assert evidence.exists() is False


def test_enospc_ignores_pages_that_are_not_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(fd: int, data: bytes | bytearray | memoryview) -> int:
        del fd, data
        raise OSError(errno.ENOSPC, "nospace")

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _boom)
    pages: tuple[object, ...] = (7, ["nope"], [{"id": 7}], [{"id": ""}])
    for index, created in enumerate(pages):
        path = tmp_path / f"evidence-{index}.json"
        with pytest.raises(SandboxError) as caught:
            commit_evidence(path, {"created_pages": created}, None)
        assert str(caught.value) == "evidence write failed"
        assert caught.value.code == EXIT_API
        assert path.exists() is False


def test_repo_root_ignores_a_partial_marker() -> None:
    root = repo_root()
    decoy = root / "src" / "money_machine" / "pyproject.toml"
    decoy.write_text("[project]\nname = 'decoy'\n", encoding="utf-8")
    try:
        assert repo_root() == root
    finally:
        decoy.unlink()


def test_missing_created_time_is_not_new() -> None:
    class _NoTime(FakeSandbox):
        def create_child_page(self, parent_id: str, title: str) -> PageView:
            page = super().create_child_page(parent_id, title)
            return _echo(page, created_time=None)

    client = _NoTime()
    with pytest.raises(SandboxError, match="created page is not new"):
        create_under(_bound_run(client), SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    assert len(client.creates) == 1


def test_naive_created_time_is_not_new() -> None:
    class _Naive(FakeSandbox):
        def create_child_page(self, parent_id: str, title: str) -> PageView:
            page = super().create_child_page(parent_id, title)
            return _echo(page, created_time=datetime(2026, 10, 7, 12, 0))

    client = _Naive()
    with pytest.raises(SandboxError, match="created page is not new"):
        create_under(_bound_run(client), SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")


def test_foreign_bot_space_creates_nothing() -> None:
    client = FakeSandbox()
    with pytest.raises(SandboxError, match="not under the requested parent"):
        create_under(
            _bound_run(client, bot_space_id=_WRONG_SPACE),
            SANDBOX_PARENT_PAGE_ID,
            "Sandbox Weekly Planner",
        )
    assert client.creates == []


def test_create_that_returns_the_parent_id_is_not_new() -> None:
    class _ReturnsParent(FakeSandbox):
        def create_child_page(self, parent_id: str, title: str) -> PageView:
            page = super().create_child_page(parent_id, title)
            return _echo(page, page_id=SANDBOX_PARENT_PAGE_ID)

    client = _ReturnsParent()
    ctx = _bound_run(client)
    with pytest.raises(SandboxError, match="created page is not new"):
        create_under(ctx, SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    assert ctx.created == []


def test_confirm_of_a_different_id_keeps_the_created_page() -> None:
    class _OtherConfirm(FakeSandbox):
        def read_page(self, page_id: str) -> PageView:
            page = super().read_page(page_id)
            if canonical_id(page_id) == canonical_id(_CHILD_IDS[0]) and self.creates:
                return _echo(page, page_id=_LIE_ID)
            return page

    client = _OtherConfirm()
    ctx = _bound_run(client)
    with pytest.raises(SandboxError, match="not under the requested parent"):
        create_under(ctx, SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    assert [row["id"] for row in ctx.created] == [canonical_id(_CHILD_IDS[0])]


def test_empty_page_id_is_not_read() -> None:
    opener = _Opener([])
    client = LiveSandboxClient(_SECRET, opener)
    with pytest.raises(SandboxError, match="notion api error"):
        client.read_page("not-a-page")
    assert opener.calls == []


def test_unparsed_create_is_not_recorded() -> None:
    ids: list[str] = []
    rows: list[dict[str, str]] = []
    opener = _Opener([b'{"object":"error"}'])
    client = LiveSandboxClient(_SECRET, opener)
    client.bind_created(ids, rows)
    with pytest.raises(SandboxError, match="notion api error"):
        client.create_child_page(SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    assert ids == []
    assert rows == []


def test_wrong_space_create_is_not_published() -> None:
    raw = _page_body(
        canonical_id(_CHILD_IDS[0]),
        parent=SANDBOX_PARENT_PAGE_ID,
        space=_WRONG_SPACE,
    )
    ids: list[str] = []
    rows: list[dict[str, str]] = []
    client = LiveSandboxClient(_SECRET, _Opener([raw]))
    client.bind_created(ids, rows)
    page = client.create_child_page(SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    assert page.space_id == canonical_id(_WRONG_SPACE)
    assert ids == []
    assert rows == []


def test_publish_does_not_repeat_an_id() -> None:
    raw = _page_body(
        canonical_id(_CHILD_IDS[0]),
        parent=SANDBOX_PARENT_PAGE_ID,
        space=_SPACE_RAW,
    )
    client = LiveSandboxClient(_SECRET, _Opener([raw, raw]))
    client.create_child_page(SANDBOX_PARENT_PAGE_ID, "one")
    client.create_child_page(SANDBOX_PARENT_PAGE_ID, "two")
    recorded: list[str] = client._created_ids  # pyright: ignore[reportPrivateUsage]
    assert recorded == [canonical_id(_CHILD_IDS[0])]


class _CodeOnly:
    def __init__(self) -> None:
        self.code = 302
        self.read_called = False

    def read(self) -> bytes:
        self.read_called = True
        return b"{}"

    def close(self) -> None:
        return None


def test_redirect_code_is_refused_without_a_status() -> None:
    body = _CodeOnly()

    def _open(request: urllib.request.Request, timeout: object = None) -> _CodeOnly:
        del request, timeout
        return body

    client = LiveSandboxClient(_SECRET, _open)
    with pytest.raises(SandboxError, match="notion api error"):
        client.read_bot()
    assert body.read_called is False


class _TextBody:
    status = 200

    def read(self) -> bytes:
        return cast(bytes, "not-bytes")

    def close(self) -> None:
        return None


def test_non_byte_body_is_an_api_error() -> None:
    def _open(request: urllib.request.Request, timeout: object = None) -> _TextBody:
        del request, timeout
        return _TextBody()

    client = LiveSandboxClient(_SECRET, _open)
    with pytest.raises(SandboxError, match="notion api error"):
        client.read_bot()


def test_parse_bot_rejects_a_non_object() -> None:
    assert parse_bot(["bot"]) is None


def test_parse_page_rejects_a_non_id() -> None:
    page = parse_page(
        {"object": "page", "id": "nope", "url": "https://www.notion.so/nope"},
        fallback_space="",
        expected_id="",
    )
    assert page is None


def test_parent_object_can_carry_the_space() -> None:
    page = parse_page(
        {
            "id": _PARENT_RAW,
            "object": "page",
            "parent": {
                "page_id": _PARENT_RAW,
                "type": "page_id",
                "workspace_id": _SPACE_RAW,
            },
            "url": "https://www.notion.so/parent",
        },
        fallback_space="",
        expected_id="",
    )
    assert page is not None
    assert page.space_id == SANDBOX_SPACE_ID


def test_missing_parent_object_stays_a_page() -> None:
    page = parse_page(
        {"id": _PARENT_RAW, "object": "page", "url": "https://www.notion.so/parent"},
        fallback_space="",
        expected_id="",
    )
    assert page is not None
    assert page.parent_id == ""
    assert page.parent_type == ""


def test_non_string_parent_type_is_ignored() -> None:
    page = parse_page(
        {
            "id": _CHILD_IDS[0],
            "object": "page",
            "parent": {"page_id": _PARENT_RAW, "type": 1},
            "url": "https://www.notion.so/child",
        },
        fallback_space="",
        expected_id="",
    )
    assert page is not None
    assert page.parent_type == ""
    assert page.parent_id == ""


def test_database_parent_does_not_copy_a_page_id() -> None:
    page = parse_page(
        {
            "id": _CHILD_IDS[0],
            "object": "page",
            "parent": {"page_id": _PARENT_RAW, "type": "database_id"},
            "url": "https://www.notion.so/child",
        },
        fallback_space="",
        expected_id="",
    )
    assert page is not None
    assert page.parent_type == "database_id"
    assert page.parent_id == ""


def test_naive_timestamp_stays_unset() -> None:
    assert parse_created_time("2026-10-07T12:00:00") is None


def test_non_string_created_by_stays_blank() -> None:
    page = parse_page(
        {
            "created_by": {"id": 7},
            "id": _CHILD_IDS[0],
            "object": "page",
            "url": "https://www.notion.so/child",
        },
        fallback_space="",
        expected_id="",
    )
    assert page is not None
    assert page.created_by == ""


def test_proxy_map_ignores_a_missing_handler_list() -> None:
    class _Bare:
        handlers: object = None

    director = cast(urllib.request.OpenerDirector, _Bare())
    assert proxy_map(director) == {}


class _NotProxy(urllib.request.BaseHandler):
    proxies: dict[str, str]

    def __init__(self) -> None:
        super().__init__()
        self.proxies = {"http": "http://127.0.0.1:9"}

    def http_open(self, request: urllib.request.Request) -> object:
        return request


def test_proxy_map_ignores_handlers_that_are_not_proxies() -> None:
    director = urllib.request.build_opener(_NotProxy())
    assert proxy_map(director) == {}


class _NullProxies(urllib.request.ProxyHandler):
    proxies: object

    def __init__(self) -> None:
        super().__init__({"http": "http://127.0.0.1:9"})
        self.proxies = None


def test_proxy_map_ignores_a_non_dict_proxy_table() -> None:
    director = urllib.request.build_opener(_NullProxies())
    assert proxy_map(director) == {}


_OFF_MINUTE = datetime(2026, 10, 7, 12, 0, 37, tzinfo=UTC)


def _off_minute() -> datetime:
    return _OFF_MINUTE


def test_off_minute_clock_accepts_the_same_minute(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_off_minute,
    )
    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert captured.err == ""
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert len(created) == 5


def test_doc_shaped_off_minute_clock_exits_0(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    opener = _DocOpener()
    client = LiveSandboxClient(_SECRET, opener)
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_off_minute,
    )
    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert captured.err == ""
    assert len(opener.posts) == 5
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert len(created) == 5


def test_stale_page_is_still_refused_on_an_off_minute_clock(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=_StaleCreate(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_off_minute,
    )
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert "sandbox stage failed" in captured.err
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["created_pages"] == []
    assert payload["rejected_pages"] == [{"id": canonical_id(_LIE_ID), "reason": "not_new"}]


@pytest.mark.parametrize("token", ["REDACTED", "[REDACTED]"])
def test_marker_token_fails_the_redaction_self_check(token: str) -> None:
    text, result = render_evidence({"bot_user_id": token, "v": token}, token)
    assert result == "FAIL"
    assert leaks(text, token) is False
    assert "bot_user_id" not in text
    assert token not in text
    assert "redaction self-check failed" in text


@pytest.mark.parametrize("mode", [0o500, 0o555, 0o100])
def test_unwritable_parent_mode_is_refused_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: int,
) -> None:
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(mode)
    opened: list[str] = []
    real = os.open

    def _spy(
        path: str | os.PathLike[str],
        flags: int,
        open_mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        name = os.fspath(path)
        if name != "/dev/null":
            opened.append(name)
        return real(path, flags, open_mode, dir_fd=dir_fd)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.open", _spy)
    path = blocked / "evidence.json"
    try:
        with pytest.raises(SandboxError) as caught:
            write_evidence(path, {"note": "kept"}, None)
    finally:
        blocked.chmod(0o700)
    assert caught.value.code == EXIT_USAGE
    assert opened == []
    assert path.exists() is False


def test_evidence_open_requests_mode_0600(
    evidence: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    modes: list[int] = []
    real = os.open

    def _spy(
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if flags & os.O_CREAT:
            modes.append(mode)
        return real(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.open", _spy)
    code = main(
        ["--evidence-out", str(evidence)],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    assert code == EXIT_OK
    assert modes == [0o600]
    assert stat.S_IMODE(evidence.stat().st_mode) == 0o600


def test_loose_created_mode_is_refused(
    evidence: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = os.open

    def _loose(
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        del mode
        return real(path, flags, 0o666, dir_fd=dir_fd)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.open", _loose)
    code = main(
        ["--evidence-out", str(evidence)],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    assert code == EXIT_API
    assert code != EXIT_USAGE
    assert evidence.exists() is False


class _ForeignEarlier(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        if len(self.creates) != 3:
            return page
        earlier = canonical_id(_CHILD_IDS[1])
        return _echo(page, page_id=earlier, space_id=_WRONG_SPACE)


def test_later_create_returning_an_earlier_foreign_id_drops_it(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _ForeignEarlier()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 3
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert [page["id"] for page in created] == [canonical_id(_CHILD_IDS[0])]
    assert canonical_id(_CHILD_IDS[1]) not in [page["id"] for page in created]


def _guard_file_outside(monkeypatch: pytest.MonkeyPatch, outside: Path) -> None:
    original = Path.resolve

    def _resolve(self: Path) -> Path:
        if self.name == "notion_sandbox_guard.py":
            return outside
        return original(self)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.Path.resolve", _resolve)


def test_repo_root_outside_the_checkout_still_uses_the_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = repo_root()
    outside = tmp_path / "away" / "notion_sandbox_guard.py"
    outside.parent.mkdir()
    outside.write_text("not the checkout\n", encoding="utf-8")
    _guard_file_outside(monkeypatch, outside)
    monkeypatch.chdir(root / "docs")
    evidence = tmp_path / "evidence.json"
    code = main(
        ["--evidence-out", str(evidence)],
        environ={},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_NO_TOKEN
    assert captured.err == "notion sandbox token is missing\n"
    raw = evidence.read_text(encoding="utf-8")
    assert len(raw.encode("utf-8")) > 0
    payload = json.loads(raw)
    assert payload["error"] == "notion sandbox token is missing"
    assert "control state is unreadable" not in captured.err


@pytest.mark.parametrize("marker", ["pyproject", "control"])
def test_partial_marker_between_cwd_and_the_repo_is_not_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    marker: str,
) -> None:
    root = repo_root()
    partial = root / f"partial-marker-{marker}"
    nested = partial / "nested"
    nested.mkdir(parents=True)
    control = partial / "docs" / "control"
    project = partial / "pyproject.toml"
    if marker == "pyproject":
        project.write_text("[project]\nname = 'decoy'\n", encoding="utf-8")
    else:
        control.mkdir(parents=True)
    outside = tmp_path / "away" / "notion_sandbox_guard.py"
    outside.parent.mkdir()
    _guard_file_outside(monkeypatch, outside)
    monkeypatch.chdir(nested)
    try:
        assert repo_root() == root
    finally:
        if project.exists():
            project.unlink()
        if control.exists():
            control.rmdir()
            control.parent.rmdir()
        nested.rmdir()
        partial.rmdir()


def _signal_child(status: Path, evidence: Path, stop: str) -> str:
    test_file = Path(__file__).resolve()
    return f"""
import importlib.util
import os
import time

status = os.environ["SBX_STATUS"]
stop = os.environ["SBX_STOP"]
spec = importlib.util.spec_from_file_location("sbx_tests", {str(test_file)!r})
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

class Slow(module.FakeSandbox):
    def create_child_page(self, parent_id, title):
        page = super().create_child_page(parent_id, title)
        count = len(self.creates)
        with open(status, "w", encoding="utf-8") as handle:
            handle.write(str(count))
        if stop == "2" and count >= 2:
            time.sleep(30)
        if stop == "5" and count >= 5:
            time.sleep(30)
        return page

if stop == "write":
    import money_machine.cli.notion_sandbox_guard as guard
    real_write = guard.os.write
    slept = {{"done": False}}

    def _slow(fd, data):
        blob = bytes(data)
        if not slept["done"] and blob.startswith(b"{{"):
            slept["done"] = True
            with open(status, "w", encoding="utf-8") as handle:
                handle.write("writing")
            time.sleep(30)
        return real_write(fd, data)

    guard.os.write = _slow

code = module.main(
    ["--evidence-out", {str(evidence)!r}, "--execute"],
    client=Slow(),
    environ={{"NOTION_SANDBOX_TOKEN": module._SECRET}},
    clock=module._clock,
)
raise SystemExit(code)
"""


def _run_signal(tmp_path: Path, stop: str) -> tuple[int, dict[str, object]]:
    evidence = tmp_path / "evidence.json"
    status = tmp_path / "status"
    script = tmp_path / "child.py"
    script.write_text(_signal_child(status, evidence, stop), encoding="utf-8")
    env = os.environ.copy()
    env["SBX_STATUS"] = str(status)
    env["SBX_STOP"] = stop
    env.pop("NOTION_SANDBOX_TOKEN", None)
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=repo_root(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 20
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            if status.is_file():
                text = status.read_text(encoding="utf-8")
                if stop == "write" and text == "writing":
                    os.kill(proc.pid, signal.SIGINT)
                    break
                if stop != "write" and text.isdigit() and int(text) >= int(stop):
                    os.kill(proc.pid, signal.SIGINT)
                    break
            time.sleep(0.02)
        stdout, stderr = proc.communicate(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=5)
            stdout, stderr = "", ""
    assert proc.returncode == EXIT_API
    assert proc.returncode not in {-2, 130, -signal.SIGINT}
    raw = evidence.read_text(encoding="utf-8")
    assert raw
    assert not raw.startswith("{") or json.loads(raw)
    payload = json.loads(raw)
    assert _SECRET not in raw
    assert "Traceback" not in stderr
    assert stdout is not None
    return proc.returncode, payload


@pytest.mark.parametrize("stop", ["2", "5"])
def test_real_sigint_records_created_ids(tmp_path: Path, stop: str) -> None:
    _code, payload = _run_signal(tmp_path, stop)
    created = payload["created_pages"]
    assert isinstance(created, list)
    expected = [canonical_id(item) for item in _CHILD_IDS[: int(stop)]]
    assert [page["id"] for page in created] == expected
    assert payload["run_status"] == "INTERRUPTED"
    assert payload["redaction_self_check"] == "PASS"
    colours = ("Blue", "Green", "Purple", "Gold")
    index = int(stop) - 1
    if index == 0:
        parent = SANDBOX_PARENT_PAGE_ID
        title = "Sandbox Weekly Planner"
    else:
        parent = canonical_id(_CHILD_IDS[0])
        title = f"Sandbox Weekly Planner / {colours[index - 1]}"
    fingerprint = hashlib.sha256(f"{parent}\n{title}".encode()).hexdigest()
    assert payload["possible_orphans"] == [{"fingerprint": fingerprint, "parent_id": parent}]


class _UnboundForeign(FakeSandbox):
    """A foreign page the client never bound into the evidence lists."""

    def create_child_page(self, parent_id: str, title: str) -> PageView:
        self.creates.append((parent_id, title))
        return PageView(
            page_id=_CHILD_IDS[0],
            parent_id=parent_id,
            space_id=_WRONG_SPACE,
            url="https://www.notion.so/foreign-child",
            archived=False,
            created_by="bot-user",
            created_time=_WHEN,
        )


def test_unbound_foreign_create_is_kept_and_flagged(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _UnboundForeign()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert err == "sandbox stage failed\n"
    assert len(client.creates) == 1
    assert _recorded(payload) == [canonical_id(_CHILD_IDS[0])]
    assert payload["flagged_pages"] == [
        {"id": canonical_id(_CHILD_IDS[0]), "reason": "space_conflict"}
    ]


def test_unfresh_page_is_removed_from_the_recorded_ids() -> None:
    client = _StaleCreate()
    ctx = _bound_run(client)
    client.bind_created(ctx.created_ids, ctx.created)
    with pytest.raises(SandboxError, match="not new"):
        create_under(ctx, SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    lie = canonical_id(_LIE_ID)
    assert lie not in ctx.created_ids
    assert ctx.created == []
    assert ctx.rejected_pages == [{"id": lie, "reason": "not_new"}]


def test_temporary_evidence_fd_is_closed(
    evidence: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[int] = []
    closed: list[int] = []
    real_open = os.open
    real_close = os.close

    def _open(
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        if flags & os.O_CREAT and os.fspath(path).endswith(".tmp"):
            opened.append(fd)
        return fd

    def _close(fd: int) -> None:
        closed.append(fd)
        real_close(fd)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.open", _open)
    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.close", _close)
    code = main(
        ["--evidence-out", str(evidence)],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    assert code == EXIT_OK
    assert opened
    assert opened[0] in closed
    # The fd is reset to -1 after its close. The cleanup does not close it again.
    assert -1 not in closed


def test_interrupt_after_the_evidence_link_leaves_that_file(
    evidence: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: dict[str, bytes] = {}
    real_link = os.link

    def _link(
        src: str | os.PathLike[str],
        dst: str | os.PathLike[str],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        real_link(
            src,
            dst,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )
        saved["bytes"] = evidence.read_bytes()
        raise KeyboardInterrupt

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.link", _link)
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    assert code == EXIT_API
    assert evidence.read_bytes() == saved["bytes"]
    payload = json.loads(saved["bytes"])
    assert [page["id"] for page in payload["created_pages"]] == [
        canonical_id(item) for item in _CHILD_IDS
    ]
    assert payload.get("run_status") != "INTERRUPTED"


def test_interrupt_does_not_keep_a_symlink(
    evidence: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good = evidence.with_name("good.json")
    good.write_text('{"ok": true}\n', encoding="utf-8")
    real_write = os.write

    def _write(fd: int, data: bytes) -> int:
        if bytes(data).startswith(b"{"):
            evidence.symlink_to(good)
            raise KeyboardInterrupt
        return real_write(fd, data)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _write)
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    assert code == EXIT_API
    assert code != EXIT_USAGE
    assert evidence.is_symlink()
    assert good.read_text(encoding="utf-8") == '{"ok": true}\n'


def test_second_interrupt_retries_until_a_file_exists(
    evidence: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_write = os.write
    seen = {"n": 0}

    def _write(fd: int, data: bytes) -> int:
        if bytes(data).startswith(b"{"):
            seen["n"] += 1
            if seen["n"] < 3:
                raise KeyboardInterrupt
        return real_write(fd, data)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _write)
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    assert code == EXIT_API
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["run_status"] == "INTERRUPTED"
    assert [page["id"] for page in payload["created_pages"]] == [
        canonical_id(item) for item in _CHILD_IDS
    ]
    # Both stages finished before the write. The interrupt does not relabel them.
    assert _stage(payload, "build")["status"] == "PASS"
    assert _stage(payload, "variants")["status"] == "PASS"
    assert _stage(payload, "qa")["status"] == "NOT_RUN"
    live_counts = payload["write_counts"]
    assert isinstance(live_counts, dict)
    live = live_counts["live"]
    assert isinstance(live, dict)
    assert live["create_child_page"] == 5


def test_real_sigint_during_the_evidence_write_leaves_a_complete_file(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    _code, payload = _run_signal(tmp_path, "write")
    raw = evidence.read_bytes()
    assert len(raw) > 0
    json.loads(raw)
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert [page["id"] for page in created] == [canonical_id(item) for item in _CHILD_IDS]
    assert payload["run_status"] == "INTERRUPTED"
    assert payload["redaction_self_check"] == "PASS"
    assert payload["possible_orphans"] == []
    assert _stage(payload, "build")["status"] == "PASS"
    assert _stage(payload, "variants")["status"] == "PASS"


def test_short_upper_hex_is_not_folded() -> None:
    token = "AB" * 10
    text = "ab" * 10
    assert leaks(text, token) is False
    assert redact_text(text, token) == text


def test_percent_and_base64_tokens_are_not_folded_hex() -> None:
    token = "secret%5F" + ("a" * 43)
    text = token.lower()
    assert leaks(text, token) is False
    assert redact_text(text, token) == text
    digest = base64.b64encode(_SECRET.encode()).decode("ascii")
    lowered = digest.lower()
    assert leaks(lowered, digest) is False
    assert redact_text(lowered, digest) == lowered


class _BlankRecordedId(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        rows = self._evidence_rows
        if rows is not None and title != "":
            rows.append({"id": "", "parent_id": canonical_id(parent_id), "url": ""})
        raise KeyboardInterrupt


def test_blank_recorded_id_stays_out_of_the_interrupt_line(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    evidence = tmp_path / "evidence.json"
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=_BlankRecordedId(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert captured.err == "sandbox interrupted\n"
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["run_status"] == "INTERRUPTED"
    assert payload["created_pages"] == [{"id": "", "parent_id": SANDBOX_PARENT_PAGE_ID, "url": ""}]


def test_custom_sigint_handler_is_left_in_place(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"

    def _custom(_signum: int, _frame: object) -> None:
        return None

    previous = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _custom)
    try:
        code = main(
            ["--evidence-out", str(evidence)],
            client=FakeSandbox(),
            environ={"NOTION_SANDBOX_TOKEN": _SECRET},
            clock=_clock,
        )
        assert code == EXIT_OK
        assert signal.getsignal(signal.SIGINT) is _custom
    finally:
        signal.signal(signal.SIGINT, previous)


def test_interrupt_before_ready_exits_69(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    script = tmp_path / "child.py"
    test_file = Path(__file__).resolve()
    script.write_text(
        f"""
import importlib.util

spec = importlib.util.spec_from_file_location("sbx_tests", {str(test_file)!r})
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

def clock():
    raise KeyboardInterrupt

code = module.main(
    ["--evidence-out", {str(evidence)!r}],
    client=module.FakeSandbox(),
    environ={{"NOTION_SANDBOX_TOKEN": module._SECRET}},
    clock=clock,
)
raise SystemExit(code)
""",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=repo_root(),
        env={key: value for key, value in os.environ.items() if key != "NOTION_SANDBOX_TOKEN"},
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == EXIT_API
    assert "Traceback" not in proc.stderr
    assert evidence.exists() is False


def test_missing_stage_runner_is_not_a_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = tmp_path / "evidence.json"

    def _no_runners() -> dict[str, object]:
        return {}

    monkeypatch.setattr("money_machine.cli.notion_sandbox.stage_runners", _no_runners)
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    assert code == EXIT_OK
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert _stage(payload, "build")["available"] is False
    assert _stage(payload, "build")["status"] == "NOT_RUN"
    assert _stage(payload, "variants")["status"] == "NOT_RUN"
    assert payload["created_pages"] == []


class _TwoForeign(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page_id = _CHILD_IDS[len(self.creates)]
        self.creates.append((parent_id, title))
        return PageView(
            page_id=page_id,
            parent_id=parent_id,
            space_id=_WRONG_SPACE,
            url="https://www.notion.so/foreign",
            archived=False,
            created_by="bot-user",
            created_time=_WHEN,
        )


def test_each_foreign_page_is_flagged() -> None:
    ctx = _bound_run(_TwoForeign())
    for _index in range(2):
        with pytest.raises(SandboxError, match="not under"):
            create_under(ctx, SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    ids = [canonical_id(item) for item in _CHILD_IDS[:2]]
    assert [row["id"] for row in ctx.flagged_pages] == ids
    assert [row["reason"] for row in ctx.flagged_pages] == ["space_conflict", "space_conflict"]


class _ForgetThenUnfresh(FakeSandbox):
    def __init__(self) -> None:
        super().__init__()
        self.ctx: SandboxRun | None = None

    def read_page(self, page_id: str) -> PageView:
        page = super().read_page(page_id)
        ctx = self.ctx
        if ctx is not None and canonical_id(page_id) == canonical_id(_CHILD_IDS[0]):
            cid = canonical_id(page_id)
            if cid in ctx.created_ids:
                ctx.created_ids.remove(cid)
            ctx.created[:] = [row for row in ctx.created if row.get("id") != cid]
            return _echo(page, created_by="other-user")
        return page


def test_unfresh_reread_survives_a_missing_id() -> None:
    client = _ForgetThenUnfresh()
    ctx = _bound_run(client)
    client.ctx = ctx
    with pytest.raises(SandboxError, match="not new"):
        create_under(ctx, SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    cid = canonical_id(_CHILD_IDS[0])
    assert cid not in ctx.created_ids
    assert ctx.rejected_pages == [{"id": cid, "reason": "not_new"}]


class _SameUnfresh(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        self.creates.append((parent_id, title))
        return PageView(
            page_id=_CHILD_IDS[0],
            parent_id=parent_id,
            space_id=SANDBOX_SPACE_ID,
            url="https://www.notion.so/stale",
            archived=False,
            created_by="other-user",
            created_time=_WHEN,
        )


def test_the_same_unfresh_page_is_rejected_once() -> None:
    ctx = _bound_run(_SameUnfresh())
    for _index in range(2):
        with pytest.raises(SandboxError, match="not new"):
            create_under(ctx, SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    cid = canonical_id(_CHILD_IDS[0])
    assert ctx.rejected_pages == [{"id": cid, "reason": "not_new"}]
    assert ctx.created_ids == []


class _DecoyTail(FakeSandbox):
    def __init__(self) -> None:
        super().__init__()
        self.ctx: SandboxRun | None = None

    def read_page(self, page_id: str) -> PageView:
        page = super().read_page(page_id)
        ctx = self.ctx
        if ctx is None or canonical_id(page_id) != canonical_id(_CHILD_IDS[0]):
            return page
        if not any(row.get("id") == "decoy-id" for row in ctx.created):
            ctx.created.append({"id": "decoy-id", "parent_id": "decoy", "url": "decoy"})
        return page


def test_confirm_does_not_replace_a_different_tail() -> None:
    client = _DecoyTail()
    ctx = _bound_run(client)
    client.ctx = ctx
    create_under(ctx, SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    assert ctx.created[-1]["id"] == "decoy-id"
    assert canonical_id(_CHILD_IDS[0]) in ctx.created_ids


def test_symlink_at_the_link_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "evidence.json"

    def _link(
        src: str | os.PathLike[str],
        dst: str | os.PathLike[str],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        del src_dir_fd, follow_symlinks
        os.symlink(src, dst, dir_fd=dst_dir_fd)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.link", _link)
    with pytest.raises(SandboxError, match="changed") as caught:
        commit_evidence(path, {"note": "ok"}, None)
    assert caught.value.code == EXIT_API
    assert path.is_symlink() is False


def test_short_replacement_is_not_finished_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "evidence.json"

    def _short(
        src: str | os.PathLike[str],
        dst: str | os.PathLike[str],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        del src, src_dir_fd, follow_symlinks
        if dst_dir_fd is None:
            Path(dst).write_bytes(b"short")
            return
        out = os.open(os.fspath(dst), os.O_CREAT | os.O_WRONLY, 0o600, dir_fd=dst_dir_fd)
        try:
            os.write(out, b"short")
        finally:
            os.close(out)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.link", _short)
    with pytest.raises(SandboxError, match="changed") as caught:
        commit_evidence(path, {"note": "ok"}, None)
    assert caught.value.code == EXIT_API
    assert path.exists() is False


def test_absent_cafile_skips_load(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Paths:
        openssl_cafile = None
        openssl_capath = None

    monkeypatch.setattr(
        "money_machine.cli.notion_sandbox_live.ssl.get_default_verify_paths",
        lambda: _Paths(),
    )
    context = sandbox_tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.get_ca_certs() == []


def test_disk_error_closes_standard_input(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    script = tmp_path / "child.py"
    script.write_text(
        f"""
import errno
import os
from pathlib import Path

from money_machine.cli import notion_sandbox_guard as guard

real = guard.os.write

def _boom(fd, data):
    if bytes(data).startswith(b"{{"):
        raise OSError(errno.ENOSPC, "no space")
    return real(fd, data)

guard.os.write = _boom
os.close(0)
path = Path({str(evidence)!r})
try:
    guard.commit_evidence(path, {{"note": "ok"}}, None)
except guard.SandboxError as exc:
    print(type(exc).__name__, exc)
try:
    os.fstat(0)
    print("fd0=open")
except OSError as exc:
    print("fd0", exc.errno)
print("dest", path.exists())
""",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=repo_root(),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "fd0 9" in proc.stdout
    assert "fd0=open" not in proc.stdout
    assert "dest False" in proc.stdout
    assert evidence.exists() is False


def _mixed_signal_child(status: Path, evidence: Path) -> str:
    test_file = Path(__file__).resolve()
    return f"""
import importlib.util
import os
import time

status = {str(status)!r}
spec = importlib.util.spec_from_file_location("sbx_tests", {str(test_file)!r})
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

class Slow(module.FakeSandbox):
    def create_child_page(self, parent_id, title):
        page = super().create_child_page(parent_id, title)
        count = len(self.creates)
        with open(status, "w", encoding="utf-8") as handle:
            handle.write(str(count))
        if count >= 2:
            time.sleep(30)
        return page

import money_machine.cli.notion_sandbox_guard as guard
real_write = guard.os.write
slept = {{"done": False}}

def _slow(fd, data):
    blob = bytes(data)
    if not slept["done"] and blob.startswith(b"{{"):
        slept["done"] = True
        with open(status, "w", encoding="utf-8") as handle:
            handle.write("writing")
        time.sleep(0.3)
    return real_write(fd, data)

guard.os.write = _slow
code = module.main(
    ["--evidence-out", {str(evidence)!r}, "--execute"],
    client=Slow(),
    environ={{"NOTION_SANDBOX_TOKEN": module._SECRET}},
    clock=module._clock,
)
raise SystemExit(code)
"""


def test_real_sigint_preserves_a_passing_stage(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    status = tmp_path / "status"
    script = tmp_path / "child.py"
    script.write_text(_mixed_signal_child(status, evidence), encoding="utf-8")
    env = os.environ.copy()
    env.pop("NOTION_SANDBOX_TOKEN", None)
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=repo_root(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    sent = {"stage": False, "write": False}
    deadline = time.monotonic() + 20
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            if status.is_file():
                text = status.read_text(encoding="utf-8")
                if not sent["stage"] and text.isdigit() and int(text) >= 2:
                    os.kill(proc.pid, signal.SIGINT)
                    sent["stage"] = True
                elif sent["stage"] and text == "writing":
                    os.kill(proc.pid, signal.SIGINT)
                    sent["write"] = True
                    break
            time.sleep(0.02)
        stdout, stderr = proc.communicate(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=5)
    assert sent == {"stage": True, "write": True}
    assert proc.returncode == EXIT_API
    assert "Traceback" not in stderr
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert _stage(payload, "build")["status"] == "PASS"
    assert _stage(payload, "variants")["status"] == "INTERRUPTED"
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert [page["id"] for page in created] == [canonical_id(item) for item in _CHILD_IDS[:2]]
    assert payload["run_status"] == "INTERRUPTED"
    assert stdout is not None


def test_complete_file_during_the_second_interrupt_returns(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    script = tmp_path / "child.py"
    test_file = Path(__file__).resolve()
    script.write_text(
        f"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("sbx_tests", {str(test_file)!r})
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
from money_machine.cli import notion_sandbox as ns

path = Path({str(evidence)!r})
ns._HELD.path = path
ns._HELD.started = module._WHEN
ns._HELD.ready = True
ns._HELD.created = [{{"id": module.canonical_id(module._CHILD_IDS[0])}}]
ns._HELD.mode = "execute"
ns._HELD.git = "abc"
ns._HELD.control = {{}}
ns._HELD.counts = {{"create_child_page": 1}}
ns._HELD.stages = [{{"name": "build", "status": "INTERRUPTED"}}]
ns._HELD.bot_user_id = "bot-user"

def _finish(*args, **kwargs):
    path.write_text('{{"complete": true}}\\n', encoding="utf-8")
    raise KeyboardInterrupt

ns._finish = _finish
raise SystemExit(ns._publish_held())
""",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=repo_root(),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == EXIT_API
    assert "Traceback" not in proc.stderr
    assert evidence.read_text(encoding="utf-8") == '{"complete": true}\n'


def test_unpublished_path_is_an_interrupt(tmp_path: Path) -> None:
    script = tmp_path / "child.py"
    test_file = Path(__file__).resolve()
    script.write_text(
        f"""
import importlib.util

spec = importlib.util.spec_from_file_location("sbx_tests", {str(test_file)!r})
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
from money_machine.cli import notion_sandbox as ns

ns._HELD.path = None
ns._HELD.started = module._WHEN
ns._HELD.ready = True
ns._HELD.created = []
raise SystemExit(ns._publish_held())
""",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=repo_root(),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == EXIT_API
    assert "Traceback" not in proc.stderr


class _ParentIdMismatch(FakeSandbox):
    def read_page(self, page_id: str) -> PageView:
        self.reads.append(page_id)
        return PageView(
            page_id=SANDBOX_PARENT_PAGE_ID,
            parent_id="",
            space_id=SANDBOX_SPACE_ID,
            url="https://www.notion.so/parent",
            archived=False,
            created_by="bot-user",
            created_time=_WHEN,
        )


def test_parent_read_with_a_different_id_is_refused() -> None:
    ctx = _bound_run(_ParentIdMismatch())
    page = PageView(
        page_id=_CHILD_IDS[0],
        parent_id=_CHILD_IDS[1],
        space_id=SANDBOX_SPACE_ID,
        url="https://www.notion.so/child",
        archived=False,
        created_by="bot-user",
        created_time=_WHEN,
    )
    with pytest.raises(SandboxError, match="not under"):
        chain_reaches_sandbox(ctx, page)
    assert ctx.flagged_pages == [{"id": canonical_id(_CHILD_IDS[0]), "reason": "chain_id"}]


def test_empty_parent_does_not_flag_the_chain() -> None:
    client = FakeSandbox()
    ctx = _bound_run(client)
    page = PageView(
        page_id=_CHILD_IDS[0],
        parent_id="",
        space_id=SANDBOX_SPACE_ID,
        url="https://www.notion.so/loose",
        archived=False,
        created_by="bot-user",
        created_time=_WHEN,
    )
    with pytest.raises(SandboxError, match="not under"):
        chain_reaches_sandbox(ctx, page)
    assert ctx.flagged_pages == []
    assert client.reads == []


class _ReplayRequested(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        self.creates.append((parent_id, title))
        view = PageView(
            page_id=_CHILD_IDS[0],
            parent_id=parent_id,
            space_id=SANDBOX_SPACE_ID,
            url="https://www.notion.so/replay",
            archived=False,
            created_by="bot-user",
            created_time=_WHEN,
        )
        self.pages[canonical_id(_CHILD_IDS[0])] = view
        return view


def test_returning_the_requested_id_keeps_it() -> None:
    ctx = _bound_run(_ReplayRequested())
    created = create_under(ctx, SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    kept = canonical_id(_CHILD_IDS[0])
    assert canonical_id(created.page_id) == kept
    with pytest.raises(SandboxError, match="not new"):
        create_under(ctx, kept, "Sandbox Weekly Planner / Blue")
    assert kept in ctx.created_ids
    assert {"id": kept, "reason": "not_new"} in ctx.flagged_pages


class _EmptyCreatedId(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        self.creates.append((parent_id, title))
        return PageView(
            page_id="",
            parent_id=parent_id,
            space_id=SANDBOX_SPACE_ID,
            url="",
            archived=False,
            created_by="bot-user",
            created_time=_WHEN,
        )


def test_dashed_secret_in_the_live_path_is_not_sent(tmp_path: Path) -> None:
    script = tmp_path / "child.py"
    script.write_text(
        """
import json

from money_machine.cli.notion_sandbox_guard import SandboxError
from money_machine.cli.notion_sandbox_live import LiveSandboxClient

token = "secret_" + ("a" * 43)
broken = "/" + token[:12] + "-" + token[12:]
sent = []

def _opener(request, timeout):
    sent.append(getattr(request, "full_url", ""))
    class _Response:
        status = 200
        def read(self):
            return b"{}"
        def close(self):
            return None
    return _Response()

client = LiveSandboxClient(token, _opener)
try:
    client._send("GET", broken, None)
    print("returned", json.dumps(sent))
except SandboxError as exc:
    print("refused", json.dumps(sent), str(exc))
""",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=repo_root(),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("refused []")


def test_blank_id_already_recorded_is_kept() -> None:
    class _Empty(FakeSandbox):
        def create_child_page(self, parent_id: str, title: str) -> PageView:
            self.creates.append((parent_id, title))
            return PageView(
                page_id="",
                parent_id=parent_id,
                space_id=SANDBOX_SPACE_ID,
                url="",
                archived=False,
                created_by="bot-user",
                created_time=_WHEN,
            )

    ctx = _bound_run(_Empty())
    ctx.created_ids.append("")
    ctx.created.append({"id": "", "parent_id": "", "url": ""})
    with pytest.raises(SandboxError, match="not new"):
        create_under(ctx, SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    assert "" in ctx.created_ids


def test_empty_created_id_raises_not_new() -> None:
    ctx = _bound_run(_EmptyCreatedId())
    with pytest.raises(SandboxError, match="not new"):
        create_under(ctx, SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    assert ctx.created_ids == []
    assert ctx.created == []


def test_drop_keeps_an_earlier_id_and_ignores_a_missing_one(tmp_path: Path) -> None:
    script = tmp_path / "child.py"
    test_file = Path(__file__).resolve()
    script.write_text(
        f"""
import importlib.util

spec = importlib.util.spec_from_file_location("sbx_tests", {str(test_file)!r})
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
from money_machine.cli.notion_sandbox_pipeline import _drop_tail, _flag

ctx = module._bound_run(module.FakeSandbox())
missing = module.canonical_id(module._CHILD_IDS[0])
_drop_tail(ctx, missing, 0)
assert ctx.created_ids == []
kept = module.canonical_id(module._CHILD_IDS[1])
ctx.created_ids.append(kept)
ctx.created.append({{"id": kept, "parent_id": "p", "url": "u"}})
_drop_tail(ctx, kept, 1)
assert ctx.created_ids == [kept]
_flag(ctx, "", "space_conflict")
assert ctx.flagged_pages == []
print("ok")
""",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=repo_root(),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"


def _record_loads(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Record which compiled-in CA location is loaded. Nothing is loaded."""
    loads: list[dict[str, object]] = []

    def _load(
        _self: ssl.SSLContext,
        cafile: object = None,
        capath: object = None,
        cadata: object = None,
    ) -> None:
        del cadata
        loads.append({"cafile": cafile, "capath": capath})

    monkeypatch.setattr(ssl.SSLContext, "load_verify_locations", _load)
    return loads


@pytest.mark.parametrize(
    ("make_file", "make_dir", "expected"),
    [
        (True, True, "cafile"),
        (False, True, "capath"),
        (True, False, "cafile"),
        (False, False, None),
    ],
)
def test_tls_context_loads_the_compiled_in_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_file: bool,
    make_dir: bool,
    expected: str | None,
) -> None:
    """The CA file wins. A host with only the directory still gets CAs. Env is never read."""
    cafile = tmp_path / "cert.pem"
    capath = tmp_path / "certs"
    if make_file:
        cafile.write_text("not loaded by the recorder\n", encoding="utf-8")
    if make_dir:
        capath.mkdir()

    class _Paths:
        openssl_cafile = str(cafile)
        openssl_capath = str(capath)

    monkeypatch.setattr(
        "money_machine.cli.notion_sandbox_live.ssl.get_default_verify_paths",
        lambda: _Paths(),
    )
    loads = _record_loads(monkeypatch)
    monkeypatch.setenv("SSL_CERT_FILE", str(cafile))
    monkeypatch.setenv("SSL_CERT_DIR", str(capath))
    context = sandbox_tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    if expected == "cafile":
        assert loads == [{"cafile": str(cafile), "capath": None}]
    elif expected == "capath":
        assert loads == [{"cafile": None, "capath": str(capath)}]
    else:
        assert loads == []


def test_tls_context_with_non_text_paths_loads_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """None paths are skipped before os.path is asked about them."""

    class _Paths:
        openssl_cafile = None
        openssl_capath = None

    monkeypatch.setattr(
        "money_machine.cli.notion_sandbox_live.ssl.get_default_verify_paths",
        lambda: _Paths(),
    )
    loads = _record_loads(monkeypatch)
    context = sandbox_tls_context()
    assert context.check_hostname is True
    assert loads == []


def test_one_interrupt_during_the_evidence_write_keeps_passed_stages(
    evidence: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Clean execute, then one interrupt in the temp write. Build and variants stay PASS."""
    real_write = os.write
    seen = {"n": 0}

    def _write(fd: int, data: bytes) -> int:
        if bytes(data).startswith(b"{"):
            seen["n"] += 1
            if seen["n"] == 1:
                raise KeyboardInterrupt
        return real_write(fd, data)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _write)
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    assert code == EXIT_API
    assert seen["n"] == 2
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert [row["status"] for row in cast(list[dict[str, object]], payload["stages"])] == [
        "PASS",
        "PASS",
        "NOT_RUN",
        "NOT_RUN",
        "NOT_RUN",
        "NOT_RUN",
    ]
    assert payload["run_status"] == "INTERRUPTED"
    assert len(cast(list[object], payload["created_pages"])) == len(_CHILD_IDS)
    assert "sandbox interrupted" in capsys.readouterr().err


def test_interrupt_in_asyncio_teardown_keeps_passed_stages(
    evidence: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A signal after every stage returned, outside a runner await. Nothing is relabelled."""
    from money_machine.cli import notion_sandbox as sandbox_module

    real_run = asyncio.run

    def _run_then_interrupt(coroutine: object) -> object:
        real_run(cast("Coroutine[object, object, object]", coroutine))
        raise KeyboardInterrupt

    monkeypatch.setattr(sandbox_module.asyncio, "run", _run_then_interrupt)
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    assert code == EXIT_API
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert _stage(payload, "build")["status"] == "PASS"
    assert _stage(payload, "variants")["status"] == "PASS"
    assert payload["run_status"] == "INTERRUPTED"
    assert [page["id"] for page in cast(list[dict[str, str]], payload["created_pages"])] == [
        canonical_id(item) for item in _CHILD_IDS
    ]


def _row(name: str, available: bool, status: str) -> dict[str, object]:
    return {"available": available, "name": name, "planned": False, "status": status}


_TAIL = [
    _row("qa", False, "NOT_RUN"),
    _row("fact_ledger", False, "NOT_RUN"),
    _row("workflow_link", False, "NOT_RUN"),
    _row("w11", False, "NOT_RUN"),
]


@pytest.mark.parametrize(
    ("done", "expected"),
    [
        ([], [_row("build", True, "INTERRUPTED"), _row("variants", True, "NOT_RUN"), *_TAIL]),
        (
            [_row("build", True, "PASS")],
            [_row("build", True, "PASS"), _row("variants", True, "INTERRUPTED"), *_TAIL],
        ),
        (
            [_row("build", True, "INTERRUPTED")],
            [_row("build", True, "INTERRUPTED"), _row("variants", True, "NOT_RUN"), *_TAIL],
        ),
        (
            [_row("build", True, "PASS"), _row("variants", True, "PASS"), *_TAIL],
            [_row("build", True, "PASS"), _row("variants", True, "PASS"), *_TAIL],
        ),
        (
            [_row("build", True, "PASS"), _row("variants", True, "PASS")],
            [_row("build", True, "PASS"), _row("variants", True, "PASS"), *_TAIL],
        ),
    ],
)
def test_interrupted_rows_keep_finished_stages(
    done: list[dict[str, object]], expected: list[dict[str, object]]
) -> None:
    """Only the first unfinished available stage is INTERRUPTED. The input is not changed."""
    from money_machine.cli import notion_sandbox as sandbox_module

    before = [dict(row) for row in done]
    rows = sandbox_module._interrupted_rows(done)  # pyright: ignore[reportPrivateUsage]
    assert rows == expected
    assert done == before


@pytest.mark.parametrize("form", ["self", "pid"])
def test_proc_alias_of_a_real_directory_is_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    form: str,
) -> None:
    """/proc/self/root/<dir> and /proc/<pid>/root/<dir> resolve to a writable directory.

    lstat and the parent checks would accept them, so only the /proc rule refuses.
    """
    target = tmp_path / "sub"
    target.mkdir()
    owner = "self" if form == "self" else str(os.getpid())
    alias = Path("/proc") / owner / "root" / target.relative_to("/") / "ev.json"
    with pytest.raises(SandboxError, match="evidence path is refused"):
        open_evidence(alias)
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(alias, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert payload == {}
    assert client.reads == []
    assert client.creates == []
    assert list(target.iterdir()) == []


@pytest.mark.parametrize("hook", ["_remember", "_drop_recorded", "_drop_tail"])
def test_interrupt_while_aligning_keeps_the_created_id(
    monkeypatch: pytest.MonkeyPatch, hook: str
) -> None:
    """The client already recorded the id. An interrupt inside _align must not lose it."""
    from money_machine.cli import notion_sandbox_pipeline as pipeline_module

    client = FakeSandbox()
    ctx = _bound_run(client)
    client.bind_created(ctx.created_ids, ctx.created)
    page = client.create_child_page(SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    kept = canonical_id(_CHILD_IDS[0])
    assert ctx.created_ids == [kept]
    row = dict(ctx.created[0])

    def _stop(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(pipeline_module, hook, _stop)
    returned: str | None = None
    with contextlib.suppress(KeyboardInterrupt):
        returned = pipeline_module._align(ctx, page, 0)  # pyright: ignore[reportPrivateUsage]
    assert ctx.created_ids == [kept]
    assert ctx.created == [row]
    if hook == "_remember":
        assert returned is None
    else:
        assert returned == kept


_EDGE = datetime(2026, 10, 7, 12, 0, 37, tzinfo=UTC)


@pytest.mark.parametrize(
    ("created", "fresh"),
    [
        (datetime(2026, 10, 7, 11, 58, 0, tzinfo=UTC), True),
        (datetime(2026, 10, 7, 11, 57, 59, tzinfo=UTC), False),
        (datetime(2026, 10, 7, 12, 2, 37, tzinfo=UTC), True),
        (datetime(2026, 10, 7, 12, 2, 38, tzinfo=UTC), False),
        (datetime(2026, 10, 8, 12, 0, 0, tzinfo=UTC), False),
    ],
)
def test_created_time_bounds_are_exact(created: datetime, fresh: bool) -> None:
    """Clock 12:00:37Z. Earliest is the floored minute less two minutes, 11:58:00Z.

    Latest is the clock plus two minutes, 12:02:37Z. A day ahead is a provider lie.
    """
    from money_machine.cli import notion_sandbox_pipeline as pipeline_module

    client = FakeSandbox()
    ctx = replace(_bound_run(client), moment=_EDGE)
    page_id = canonical_id(_CHILD_IDS[0])
    ctx.created_ids.append(page_id)
    ctx.created.append({"id": page_id, "parent_id": "", "url": ""})
    page = PageView(
        page_id=page_id,
        parent_id=SANDBOX_PARENT_PAGE_ID,
        space_id=SANDBOX_SPACE_ID,
        url="https://www.notion.so/child",
        archived=False,
        created_by="bot-user",
        created_time=created,
    )
    if fresh:
        pipeline_module._fresh(ctx, page)  # pyright: ignore[reportPrivateUsage]
        assert ctx.created_ids == [page_id]
        assert ctx.rejected_pages == []
    else:
        with pytest.raises(SandboxError, match="not new"):
            pipeline_module._fresh(ctx, page)  # pyright: ignore[reportPrivateUsage]
        assert ctx.created_ids == []
        assert ctx.rejected_pages == [{"id": page_id, "reason": "not_new"}]


class _FutureCreated(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        return _echo(page, created_time=_WHEN + timedelta(days=1))


def test_future_created_time_is_refused_end_to_end(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A create response dated a day ahead is not new. One create, then exit 69."""
    client = _FutureCreated()
    code, payload, _out, _err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert len(client.creates) == 1
    assert _stage(payload, "build")["status"] == "FAILED"
    assert payload["created_pages"] == []
    assert payload["rejected_pages"] == [{"id": canonical_id(_CHILD_IDS[0]), "reason": "not_new"}]


# Round 5: literal-operand kills.


class _Liar:
    """Compares equal to everything. A type check is the only thing that refuses it."""

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    __hash__ = object.__hash__


class _TextSubclass(str):
    __slots__ = ()


def test_type_checks_refuse_lookalike_values() -> None:
    """A value that only compares like a string is not one."""
    bot = BotView(user_id="bot-user", user_type=_Liar(), space_id=SANDBOX_SPACE_ID)
    page = PageView(
        page_id=SANDBOX_PARENT_PAGE_ID,
        parent_id="",
        space_id=SANDBOX_SPACE_ID,
        url="",
        archived=False,
    )
    assert target_ok(replace(bot, user_type="bot"), page) is True
    assert target_ok(bot, page) is False
    assert token_from_environ({"NOTION_SANDBOX_TOKEN": _TextSubclass(_SECRET)}) is None
    assert qa_verdict([{"name": "qa", "status": _Liar()}]) == "NOT_RUN"


def test_unshaped_tokens_have_no_encoded_forms() -> None:
    """Only a shaped token gets url-encoded and base64 copies."""
    from money_machine.cli import notion_sandbox_guard as guard_module

    plain = "plain token value"
    digest = base64.b64encode(plain.encode("utf-8")).decode("ascii")
    assert guard_module._encoded_forms(plain) == ()  # pyright: ignore[reportPrivateUsage]
    assert guard_module._encoded_forms(None) == ()  # pyright: ignore[reportPrivateUsage]
    assert redact_text(f"x {digest} y", plain) == f"x {digest} y"
    assert leaks(f"x {digest} y", plain) is False


@pytest.mark.parametrize("token", ["true", "false", "null", " ", "\t"])
def test_json_literal_tokens_are_not_secrets(token: str) -> None:
    """A token that would rewrite the JSON document is neither replaced nor reported."""
    text = '{\n  "a": true,\n  "b": false,\n  "c": null\n}'
    assert redact_text(text, token) == text
    assert leaks(text, token) is False


def test_hex_token_absent_from_the_text_is_not_a_leak() -> None:
    token = "0123456789abcdef" * 2
    assert leaks('{"clean": "text"}', token) is False
    assert leaks(f"x {token.upper()} y", token) is True


def test_created_page_ids_skip_empty_and_non_text_ids() -> None:
    from money_machine.cli import notion_sandbox_guard as guard_module

    payload: dict[str, object] = {
        "created_pages": [{"id": ""}, {"id": 5}, "page", {"id": "a"}, {"id": "b"}]
    }
    assert guard_module._created_page_ids(payload) == "a, b"  # pyright: ignore[reportPrivateUsage]
    assert guard_module._created_page_ids({"created_pages": "a"}) == ""  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("extra", [1, 7])
def test_overlong_write_count_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, extra: int
) -> None:
    """``os.write`` never reports more bytes than it was given. A count that does is refused."""
    from money_machine.cli import notion_sandbox_guard as guard_module

    target = tmp_path / "out.bin"
    fd = os.open(target, os.O_CREAT | os.O_WRONLY, 0o600)

    def _overlong(_fd: int, data: object) -> int:
        return len(cast(memoryview, data)) + extra

    monkeypatch.setattr(guard_module.os, "write", _overlong)
    try:
        with pytest.raises(SandboxError, match="evidence write failed"):
            guard_module._write_all(fd, b"abc")  # pyright: ignore[reportPrivateUsage]
    finally:
        monkeypatch.undo()
        os.close(fd)


def test_link_replaced_by_a_same_size_symlink_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A symlink at the destination is refused even when its size matches the document."""
    from money_machine.cli import notion_sandbox_guard as guard_module

    path = tmp_path / "evidence.json"
    payload: dict[str, object] = {"result": "PASS"}
    text, _result = render_evidence(payload, _SECRET)
    size = len(text.encode("utf-8"))
    decoy = "x" * size
    real_link = os.link

    def _swap(
        source: object,
        destination: object,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        del source, src_dir_fd, follow_symlinks
        os.symlink(decoy, str(destination), dir_fd=dst_dir_fd)

    monkeypatch.setattr(guard_module.os, "link", _swap)
    try:
        with pytest.raises(SandboxError, match="evidence file changed during the run"):
            commit_evidence(path, payload, _SECRET)
    finally:
        monkeypatch.setattr(guard_module.os, "link", real_link)
    assert os.path.lexists(path) is False
    assert sorted(os.listdir(tmp_path)) == []


def test_repo_root_needs_both_markers_in_one_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A directory with only one marker is skipped while walking up from the module."""
    from money_machine.cli import notion_sandbox_guard as guard_module

    root = tmp_path / "root"
    (root / "docs" / "control").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    middle = root / "mid"
    middle.mkdir()
    (middle / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    inner = middle / "inner"
    (inner / "docs" / "control").mkdir(parents=True)
    module_file = inner / "pkg" / "notion_sandbox_guard.py"
    module_file.parent.mkdir()
    module_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(guard_module, "__file__", str(module_file))
    assert repo_root() == root.resolve()


@pytest.mark.parametrize(
    ("field", "value"),
    [("state_revision", "58"), ("current_session", "7"), ("head_sha", 7)],
)
def test_control_ids_refuse_each_mistyped_field(tmp_path: Path, field: str, value: object) -> None:
    from money_machine.cli.notion_sandbox_guard import control_ids

    state: dict[str, object] = {"state_revision": 58, "current_session": 7, "head_sha": "a" * 40}
    control = tmp_path / "docs" / "control"
    control.mkdir(parents=True)
    target = control / "IMPLEMENTATION_STATE.json"
    target.write_text(json.dumps(state), encoding="utf-8")
    assert control_ids(tmp_path)["current_session"] == 7
    state[field] = value
    target.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(SandboxError, match="control state is unreadable"):
        control_ids(tmp_path)


def test_evidence_argument_reads_only_the_named_flag() -> None:
    from money_machine.cli import notion_sandbox as sandbox_module

    find = sandbox_module._evidence_argument  # pyright: ignore[reportPrivateUsage]
    assert find(["--execute", "--evidence-out", "e.json"]) == Path("e.json")
    assert find(["--dry-run", "x.json"]) is None
    assert find(["--evidence-out=f.json", "--execute"]) == Path("f.json")
    assert find(["--evidence-out"]) is None


def test_with_ids_skips_empty_and_non_text_ids() -> None:
    from money_machine.cli import notion_sandbox as sandbox_module

    rows = cast(list[dict[str, str]], [{"id": None}, {"id": 5}, {"id": ""}, {"id": "a"}, {}])
    assert sandbox_module._with_ids("p", rows) == "p: a"  # pyright: ignore[reportPrivateUsage]
    assert sandbox_module._with_ids("p", []) == "p"  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("value", ["2026-10-07T12:00:00Z", 0])
def test_clock_returning_a_non_datetime_is_refused(
    evidence: Path, capsys: pytest.CaptureFixture[str], value: object
) -> None:
    client = FakeSandbox()

    def _odd() -> datetime:
        return cast(datetime, value)

    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_odd,
    )
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert captured.err == "clock must be timezone-aware\n"
    assert client.reads == []
    assert evidence.exists() is False


@pytest.mark.parametrize(("started", "ready"), [(None, True), (_WHEN, False)])
def test_publish_held_needs_a_start_and_a_ready_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    started: datetime | None,
    ready: bool,
) -> None:
    """Without a start time or before the run is ready there is no evidence to write."""
    from money_machine.cli import notion_sandbox as sandbox_module

    held = sandbox_module._HELD  # pyright: ignore[reportPrivateUsage]
    path = tmp_path / "evidence.json"
    monkeypatch.setattr(held, "path", path)
    monkeypatch.setattr(held, "started", started)
    monkeypatch.setattr(held, "ready", ready)
    monkeypatch.setattr(held, "created", [{"id": "a"}])
    code = sandbox_module._publish_held()  # pyright: ignore[reportPrivateUsage]
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert captured.err == "sandbox interrupted: a\n"
    assert os.listdir(tmp_path) == []


def test_refusal_without_an_evidence_path_is_usage(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    """A refused environment with no ``--evidence-out`` writes nothing and exits 64."""
    caplog.set_level(logging.DEBUG)
    client = FakeSandbox()
    code = main(
        ["--execute"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET, "SSL_CERT_FILE": "/tmp/ca.pem"},
        clock=_clock,
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert captured.err == "usage error\n"
    assert "Traceback" not in caplog.text
    assert client.reads == []


def _live_page(page_id: str, *, space: str = "") -> PageView:
    return PageView(
        page_id=page_id,
        parent_id=SANDBOX_PARENT_PAGE_ID,
        space_id=space,
        url="https://www.notion.so/x",
        archived=False,
    )


def test_live_publish_records_each_id_once() -> None:
    """Unbound publishes only track the id. Bound publishes append a new id once."""
    client = LiveSandboxClient(_SECRET, _Opener([]))
    page = _live_page(canonical_id(_CHILD_IDS[0]))
    client._publish(page)  # pyright: ignore[reportPrivateUsage]
    ids: list[str] = []
    rows: list[dict[str, str]] = []
    client.bind_created(ids, rows)
    client._publish(_live_page(""))  # pyright: ignore[reportPrivateUsage]
    assert ids == []
    client._publish(page)  # pyright: ignore[reportPrivateUsage]
    client._publish(page)  # pyright: ignore[reportPrivateUsage]
    assert ids == [canonical_id(_CHILD_IDS[0])]
    assert [row["id"] for row in rows] == ids


def test_dashed_plain_token_in_the_url_is_not_sent() -> None:
    """A dashed token that is not hex is caught on the url as written."""
    sent: list[str] = []

    def _open(request: urllib.request.Request, timeout: object = None) -> _Response:
        del timeout
        sent.append(request.full_url)
        return _Response(b"{}")

    token = "pages/" + canonical_id(_PARENT_RAW)[:13]
    assert "-" in token
    client = LiveSandboxClient(token, _open)
    with pytest.raises(SandboxError, match="notion api error"):
        client.read_page(SANDBOX_PARENT_PAGE_ID)
    assert sent == []


class _OkBody:
    status = 200

    def read(self) -> bytes:
        return json.dumps({"id": "bot-user", "type": "bot"}).encode("utf-8")

    def close(self) -> None:
        return None


def test_status_200_is_read() -> None:
    def _open(request: urllib.request.Request, timeout: object = None) -> _OkBody:
        del request, timeout
        return _OkBody()

    bot = LiveSandboxClient(_SECRET, _open).read_bot()
    assert bot.user_type == "bot"
    assert bot.user_id == "bot-user"


def test_parse_helpers_refuse_mistyped_fields() -> None:
    base: dict[str, object] = {"object": "page", "id": _PARENT_RAW}
    assert parse_bot({"id": "u", "type": 5}) is None
    assert parse_page([], fallback_space="", expected_id="") is None
    assert parse_page("page", fallback_space="", expected_id="") is None
    for key in ("archived", "is_archived", "in_trash"):
        assert parse_page({**base, key: "yes"}, fallback_space="", expected_id="") is None
    page = parse_page({**base, "url": ""}, fallback_space="", expected_id="")
    assert page is not None
    assert page.url == "https://www.notion.so/" + canonical_id(_PARENT_RAW).replace("-", "")
    with pytest.raises(SandboxError, match="notion api error"):
        explicit_space({"space_id": 5, "workspace_id": _SPACE_RAW})
    assert parse_created_time("") is None
    assert parse_created_time(7) is None


def test_proxy_map_keeps_only_text_pairs() -> None:
    handler = urllib.request.ProxyHandler({"https": "http://p:1"})
    setattr(handler, "proxies", {5: "x", "https": "http://p:1", "http": 7})  # noqa: B010
    director = urllib.request.OpenerDirector()
    director.add_handler(handler)
    assert proxy_map(director) == {"https": "http://p:1"}


def test_pipeline_helpers_ignore_blank_and_missing_ids() -> None:
    """Blank ids are never recorded or rejected. A missing id is not an error."""
    from money_machine.cli import notion_sandbox_pipeline as pipeline_module

    ctx = _bound_run(FakeSandbox())
    page = _live_page("")
    pipeline_module._remember(ctx, page, "")  # pyright: ignore[reportPrivateUsage]
    assert ctx.created_ids == []
    assert ctx.created == []
    pipeline_module._drop_recorded(ctx, canonical_id(_CHILD_IDS[0]))  # pyright: ignore[reportPrivateUsage]
    assert ctx.created_ids == []
    with pytest.raises(SandboxError, match="created page is not new"):
        pipeline_module._reject_unfresh(ctx, page)  # pyright: ignore[reportPrivateUsage]
    assert ctx.rejected_pages == []


def test_one_page_keeps_one_flag_per_reason() -> None:
    from money_machine.cli import notion_sandbox_pipeline as pipeline_module

    ctx = _bound_run(FakeSandbox())
    page_id = canonical_id(_CHILD_IDS[0])
    for reason in ("chain", "not_new", "chain"):
        pipeline_module._flag(ctx, page_id, reason)  # pyright: ignore[reportPrivateUsage]
    assert ctx.flagged_pages == [
        {"id": page_id, "reason": "chain"},
        {"id": page_id, "reason": "not_new"},
    ]


def _chain_page(page_id: str, parent_id: str, *, space: str = SANDBOX_SPACE_ID) -> PageView:
    return PageView(
        page_id=page_id,
        parent_id=parent_id,
        space_id=space,
        url="https://www.notion.so/x",
        archived=False,
    )


def test_chain_refuses_an_archived_sandbox_parent_handed_in() -> None:
    client = FakeSandbox()
    ctx = _bound_run(client)
    parent = replace(_chain_page(SANDBOX_PARENT_PAGE_ID, ""), archived=True)
    with pytest.raises(SandboxError, match="not under the requested parent"):
        chain_reaches_sandbox(ctx, parent)
    assert client.reads == []
    chain_reaches_sandbox(ctx, replace(parent, archived=False))


def test_chain_refuses_a_page_without_an_id() -> None:
    client = FakeSandbox()
    ctx = _bound_run(client)
    with pytest.raises(SandboxError, match="not under the requested parent"):
        chain_reaches_sandbox(ctx, _chain_page("", SANDBOX_PARENT_PAGE_ID))
    assert client.reads == []


def test_chain_stops_at_a_foreign_intermediate_page() -> None:
    """A foreign page between the child and the sandbox parent is refused at that page."""
    client = FakeSandbox()
    ctx = _bound_run(client)
    middle = canonical_id(_CHILD_IDS[1])
    child = canonical_id(_CHILD_IDS[0])
    client.pages[middle] = _chain_page(middle, SANDBOX_PARENT_PAGE_ID, space=_WRONG_SPACE)
    with pytest.raises(SandboxError, match="not under the requested parent"):
        chain_reaches_sandbox(ctx, _chain_page(child, middle))
    assert client.reads == [middle]
    assert ctx.flagged_pages == [{"id": child, "reason": "chain"}]


def test_chain_cycle_stops_on_the_repeat() -> None:
    """A parent cycle is refused when a page repeats, not after the step limit."""
    client = FakeSandbox()
    ctx = _bound_run(client)
    first = canonical_id(_CHILD_IDS[0])
    second = canonical_id(_CHILD_IDS[1])
    client.pages[first] = _chain_page(first, second)
    client.pages[second] = _chain_page(second, first)
    with pytest.raises(SandboxError, match="not under the requested parent"):
        chain_reaches_sandbox(ctx, client.pages[first])
    assert client.reads == [second, first]


class _ClearedTail(FakeSandbox):
    """The confirm read empties the evidence rows. The create still returns the page."""

    def __init__(self) -> None:
        super().__init__()
        self.ctx: SandboxRun | None = None

    def read_page(self, page_id: str) -> PageView:
        page = super().read_page(page_id)
        ctx = self.ctx
        if ctx is not None and canonical_id(page_id) == canonical_id(_CHILD_IDS[0]):
            ctx.created.clear()
        return page


def test_confirm_with_no_evidence_rows_does_not_add_one() -> None:
    client = _ClearedTail()
    ctx = _bound_run(client)
    client.ctx = ctx
    confirmed = create_under(ctx, SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    assert canonical_id(confirmed.page_id) == canonical_id(_CHILD_IDS[0])
    assert ctx.created == []


@pytest.mark.parametrize("missing", ["probe", "spec"])
def test_variants_need_a_probe_and_a_product_spec(missing: str) -> None:
    ctx = SandboxRun(
        spec=sandbox_product_spec(_WHEN),
        client=FakeSandbox(),
        checkpoint=Path("checkpoint.json"),
        moment=_WHEN,
        write_counts={},
        probe=FixtureNotionAdapter(),
        product_page_id=canonical_id(_CHILD_IDS[0]),
    )
    if missing == "probe":
        ctx.probe = None
    else:
        ctx.spec = object()

    async def _call() -> None:
        await stage_runners()["run_variants"](ctx)

    with pytest.raises(SandboxError, match="variants require the build stage"):
        asyncio.run(_call())


class _SignalAtSecondCreate(FakeSandbox):
    """A real SIGINT to this process during the second create."""

    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        if len(self.creates) == 2:
            os.kill(os.getpid(), signal.SIGINT)
        return page


def test_repeated_sigint_during_the_evidence_write_keeps_one_file(
    evidence: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reviewer S2: SIGINT at create 2, one in the first write, three in the publish."""
    real_write = os.write
    sent = {"n": 0, "writes": 0}

    def _write(fd: int, data: bytes) -> int:
        if bytes(data).startswith(b"{"):
            sent["writes"] += 1
            for _ in range(1 if sent["writes"] == 1 else 3):
                sent["n"] += 1
                os.kill(os.getpid(), signal.SIGINT)
        return real_write(fd, data)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _write)
    before = signal.getsignal(signal.SIGINT)
    try:
        code = main(
            ["--evidence-out", str(evidence), "--execute"],
            client=_SignalAtSecondCreate(),
            environ={"NOTION_SANDBOX_TOKEN": _SECRET},
            clock=_clock,
        )
    except KeyboardInterrupt:
        pytest.fail("a repeated SIGINT escaped main")
    finally:
        after = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, before)
    assert code == EXIT_API
    # Create-2 SIGINT installs SIG_IGN inside _raise_interrupt, so the
    # write-path kills are discarded and the first write finishes.
    assert sent["writes"] >= 1
    assert sent["n"] >= 1
    assert after is signal.SIG_IGN
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["run_status"] == "INTERRUPTED"
    assert [page["id"] for page in cast(list[dict[str, str]], payload["created_pages"])] == [
        canonical_id(item) for item in _CHILD_IDS[:2]
    ]
    # The second create is the first variant. Build finished and stays PASS.
    assert _stage(payload, "build")["status"] == "PASS"
    assert _stage(payload, "variants")["status"] == "INTERRUPTED"


def test_leading_double_slash_proc_path_is_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``//proc/...`` keeps a ``//`` root under abspath. Stock must still refuse it."""
    target = tmp_path / "sub"
    target.mkdir()
    alias = Path("//proc/self/root") / target.relative_to("/") / "ev.json"
    with pytest.raises(SandboxError, match="evidence path is refused"):
        open_evidence(alias)
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(alias, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert payload == {}
    assert client.reads == []
    assert client.creates == []
    assert list(target.iterdir()) == []
    assert alias.exists() is False


def test_symlink_to_proc_is_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A directory symlink to ``/proc`` must not skip the ``/proc`` refusal."""
    link = tmp_path / "proc"
    link.symlink_to("/proc")
    alias = link / "self" / "root" / tmp_path.relative_to("/") / "ev.json"
    with pytest.raises(SandboxError, match="evidence path is refused"):
        open_evidence(alias)
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(alias, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert payload == {}
    assert client.reads == []
    assert client.creates == []
    assert alias.exists() is False


def test_live_client_default_opener_is_callable() -> None:
    client = LiveSandboxClient(_SECRET)
    assert callable(client._opener)  # pyright: ignore[reportPrivateUsage]


def test_absent_injected_client_writes_evidence(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No injected client uses LiveSandboxClient. Sockets stay blocked."""
    code, payload, _out, err, _logs = _invoke(evidence, capsys, caplog, [])
    assert code == EXIT_API
    assert err == "notion api error\n"
    assert evidence.is_file()
    assert payload["error"] == "notion api error"
    assert payload["flagged_pages"] == []
    assert payload["possible_orphans"] == []
    assert payload["rejected_pages"] == []
    assert payload["created_pages"] == []


def test_production_client_dry_run_uses_sandbox_opener(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dry-run without an injected client must use ``sandbox_opener().open``."""
    opener = _Opener([_bot_body(), _page_body(_PARENT_RAW, parent=_PARENT_RAW, space=_SPACE_RAW)])

    class _Director:
        def open(
            self,
            request: urllib.request.Request,
            data: object = None,
            *,
            timeout: object = None,
        ) -> _Response:
            return opener(request, data, timeout=timeout)

    monkeypatch.setattr(
        "money_machine.cli.notion_sandbox_live.sandbox_opener",
        lambda: _Director(),
    )
    code, payload, _out, err, _logs = _invoke(evidence, capsys, caplog, [])
    assert code == EXIT_OK
    assert err == ""
    assert payload["mode"] == "dry-run"
    assert [call[0] for call in opener.calls] == ["GET", "GET"]
    assert payload["flagged_pages"] == []
    assert payload["possible_orphans"] == []
    assert payload["rejected_pages"] == []


def test_leftover_tmp_is_replaced(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    leftover = evidence.with_name(f".{evidence.name}.tmp")
    leftover.write_text("stale", encoding="utf-8")
    leftover.chmod(0o600)
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=FakeSandbox()
    )
    assert code == EXIT_OK
    assert err == ""
    assert leftover.exists() is False
    assert "leftover regular evidence tmp" in _logs
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert [page["id"] for page in created] == [canonical_id(item) for item in _CHILD_IDS]


def test_tmp_eexist_after_creates_exits_69_with_ids(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O_EXCL EEXIST after creates is not a usage error. Ids stay on stderr."""
    real_open = os.open
    wanted = evidence.with_name(f".{evidence.name}.tmp")

    def _open(
        path: str | os.PathLike[str],
        flags: int = 0,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        name = os.fspath(path)
        if (name == str(wanted) or name == wanted.name) and flags & os.O_EXCL:
            raise OSError(errno.EEXIST, "File exists")
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.open", _open)
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert code != EXIT_USAGE
    assert evidence.exists() is False
    kept = canonical_id(_CHILD_IDS[0])
    assert kept in err
    for page_id in _CHILD_IDS:
        assert canonical_id(page_id) in err
    assert client.creates
    assert payload == {}


def test_interrupt_during_tmp_unlink_keeps_ids(
    evidence: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second interrupt during the first tmp unlink must not become exit 64."""
    real_write = os.write
    real_unlink = os.unlink
    state = {"wrote": False, "unlinked": 0}

    def _write(fd: int, data: bytes) -> int:
        if bytes(data).startswith(b"{") and not state["wrote"]:
            state["wrote"] = True
            raise KeyboardInterrupt
        return real_write(fd, data)

    wanted = evidence.with_name(f".{evidence.name}.tmp")

    def _unlink(path: str | os.PathLike[str], *, dir_fd: int | None = None) -> None:
        name = os.fspath(path)
        if name == str(wanted) or name == wanted.name:
            state["unlinked"] += 1
            if state["unlinked"] == 1:
                raise KeyboardInterrupt
        real_unlink(path, dir_fd=dir_fd)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _write)
    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.unlink", _unlink)
    code = main(
        ["--evidence-out", str(evidence), "--execute"],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    assert code == EXIT_API
    assert code != EXIT_USAGE
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert [page["id"] for page in payload["created_pages"]] == [
        canonical_id(item) for item in _CHILD_IDS
    ]
    assert _stage(payload, "build")["status"] == "PASS"
    assert _stage(payload, "variants")["status"] == "PASS"


def test_symlink_to_proc_self_root_is_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``realpath('/proc/self/root')`` is ``/``. Device check must still refuse."""
    link = tmp_path / "l_root"
    link.symlink_to("/proc/self/root")
    alias = link / tmp_path.relative_to("/") / "e3.json"
    assert under_proc(alias) is True
    with pytest.raises(SandboxError, match="evidence path is refused"):
        open_evidence(alias)
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(alias, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert payload == {}
    assert client.reads == []
    assert client.creates == []
    assert alias.exists() is False


def test_symlink_to_proc_self_plus_root_dir_is_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """guard:354 LF1: a symlink to ``/proc/self`` plus ``/root/<dir>`` is still proc."""
    link = tmp_path / "self"
    link.symlink_to("/proc/self")
    alias = link / "root" / tmp_path.relative_to("/") / "ev.json"
    assert under_proc(alias) is True
    with pytest.raises(SandboxError, match="evidence path is refused"):
        open_evidence(alias)
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(alias, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert payload == {}
    assert client.reads == []
    assert client.creates == []
    assert alias.exists() is False


def test_under_proc_on_foreign_pid_root_does_not_raise() -> None:
    """guard:366 SWAP/LF0: ``/proc/1/root/x`` is True and must not raise PermissionError."""
    assert under_proc(Path("/proc/1/root/x")) is True
    assert under_proc(Path("/proc/1/root/ev.json")) is True


@pytest.mark.parametrize("kind", ["symlink", "dir", "fifo"])
def test_leftover_hostile_tmp_is_refused_before_any_call(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    kind: str,
) -> None:
    leftover = evidence.with_name(f".{evidence.name}.tmp")
    canary = evidence.with_name("canary")
    canary.write_text("keep", encoding="utf-8")
    if kind == "symlink":
        leftover.symlink_to(canary)
    elif kind == "dir":
        leftover.mkdir()
    else:
        os.mkfifo(leftover)
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert payload == {}
    assert client.reads == []
    assert client.creates == []
    assert evidence.exists() is False
    assert canary.read_text(encoding="utf-8") == "keep"


def test_leftover_tmp_symlink_after_creates_exits_69_without_writing_through_it(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """guard:473: leftover tmp symlink at commit is 69 and never followed."""
    leftover = evidence.with_name(f".{evidence.name}.tmp")
    canary = evidence.with_name("canary")
    canary.write_text("keep", encoding="utf-8")

    class _Plant(FakeSandbox):
        def create_child_page(self, parent_id: str, title: str) -> PageView:
            page = super().create_child_page(parent_id, title)
            if len(self.creates) == 5:
                leftover.symlink_to(canary)
            return page

    client = _Plant()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert code != EXIT_USAGE
    assert evidence.exists() is False
    assert leftover.is_symlink()
    assert canary.read_text(encoding="utf-8") == "keep"
    assert payload == {}
    for page_id in _CHILD_IDS:
        assert canonical_id(page_id) in err
    assert len(client.creates) == 5


def test_grandparent_swapped_to_proc_self_root_does_not_write(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A grandparent swapped after POST 3 must not write through procfs."""
    other = tmp_path / "other" / "parent"
    other.mkdir(parents=True)
    grand = tmp_path / "grand"
    parent = grand / "parent"
    parent.mkdir(parents=True)
    evidence = parent / "ev.json"

    class _Swap(FakeSandbox):
        def create_child_page(self, parent_id: str, title: str) -> PageView:
            page = super().create_child_page(parent_id, title)
            if len(self.creates) == 3 and grand.is_dir() and not grand.is_symlink():
                backup = grand.with_name("grand.bak")
                grand.rename(backup)
                grand.symlink_to(Path("/proc/self/root") / other.parent.relative_to("/"))
            return page

    client = _Swap()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert code != EXIT_OK
    assert "evidence path is refused" in err or "evidence write failed" in err
    assert payload == {}
    assert list(other.iterdir()) == []
    assert (tmp_path / "other" / "parent" / "ev.json").exists() is False
    assert len(client.creates) == 5
    for page_id in _CHILD_IDS:
        assert canonical_id(page_id) in err


def test_gap0_sigint_at_post2_prints_ids(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A KeyboardInterrupt inside redact_text at POST:2 must still print the ids."""
    from money_machine.cli import notion_sandbox as sandbox_module

    real_redact = sandbox_module.redact_text
    hits = {"n": 0, "after": 0}

    def _redact(text: str, token: str | None) -> str:
        if "Interrupt" in text or "Cancelled" in text:
            hits["n"] += 1
            os.kill(os.getpid(), signal.SIGINT)
            hits["after"] = hits.get("after", 0) + 1
        return real_redact(text, token)

    monkeypatch.setattr(sandbox_module, "redact_text", _redact)
    before = signal.getsignal(signal.SIGINT)
    try:
        code = main(
            ["--evidence-out", str(evidence), "--execute"],
            client=_SignalAtSecondCreate(),
            environ={"NOTION_SANDBOX_TOKEN": _SECRET},
            clock=_clock,
        )
    except KeyboardInterrupt:
        pytest.fail("KeyboardInterrupt escaped the id-print path")
    finally:
        signal.signal(signal.SIGINT, before)
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert hits["n"] >= 1
    assert hits.get("after", 0) >= 1
    assert canonical_id(_CHILD_IDS[0]) in captured.err
    assert canonical_id(_CHILD_IDS[1]) in captured.err


def test_double_sigint_at_50ms_exits_69(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A follow-up SIGINT 50 ms after POST:2 must not exit -2."""

    class _Burst(FakeSandbox):
        def create_child_page(self, parent_id: str, title: str) -> PageView:
            page = super().create_child_page(parent_id, title)
            if len(self.creates) == 2:
                threading.Timer(0.05, lambda: os.kill(os.getpid(), signal.SIGINT)).start()
                os.kill(os.getpid(), signal.SIGINT)
            return page

    before = signal.getsignal(signal.SIGINT)
    try:
        code = main(
            ["--evidence-out", str(evidence), "--execute"],
            client=_Burst(),
            environ={"NOTION_SANDBOX_TOKEN": _SECRET},
            clock=_clock,
        )
    except KeyboardInterrupt:
        pytest.fail("second SIGINT escaped main")
    finally:
        time.sleep(0.08)
        signal.signal(signal.SIGINT, before)
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert code != -2
    assert canonical_id(_CHILD_IDS[0]) in captured.err
    assert canonical_id(_CHILD_IDS[1]) in captured.err


@pytest.mark.parametrize("err", [errno.EACCES, errno.EROFS, errno.EPERM])
def test_write_errno_after_creates_exits_69_with_ids(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    err: int,
) -> None:
    real_open = os.open
    wanted = evidence.with_name(f".{evidence.name}.tmp")

    def _open(
        path: str | os.PathLike[str],
        flags: int = 0,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        name = os.fspath(path)
        if (name == str(wanted) or name == wanted.name) and flags & os.O_EXCL:
            raise OSError(err, "denied")
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.open", _open)
    client = FakeSandbox()
    code, payload, _out, err_text, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert code != EXIT_USAGE
    assert evidence.exists() is False
    assert payload == {}
    assert client.creates
    for page_id in _CHILD_IDS:
        assert canonical_id(page_id) in err_text


def test_evidence_path_appearing_mid_run_exits_69_with_ids(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Appear(FakeSandbox):
        def create_child_page(self, parent_id: str, title: str) -> PageView:
            page = super().create_child_page(parent_id, title)
            if len(self.creates) == 5:
                evidence.write_text("appeared", encoding="utf-8")
            return page

    client = _Appear()
    code, raw, _logs = _run(
        evidence,
        ["--evidence-out", str(evidence), "--execute"],
        client=client,
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        caplog=caplog,
    )
    captured = capsys.readouterr()
    err = captured.err
    assert code == EXIT_API
    assert code != EXIT_USAGE
    assert "evidence file changed" in err or "evidence write failed" in err
    assert raw == "appeared"
    assert evidence.read_text(encoding="utf-8") == "appeared"
    for page_id in _CHILD_IDS:
        assert canonical_id(page_id) in err


def test_malformed_space_id_on_a_created_page_is_refused(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    created = canonical_id(_CHILD_IDS[0])
    opener = _Opener(
        [
            _bot_body(),
            _page_body(_PARENT_RAW, parent=_PARENT_RAW),
            _page_body(_CHILD_IDS[0], parent=_PARENT_RAW, space="not-a-uuid"),
        ]
    )
    client = LiveSandboxClient(_SECRET, opener)
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert code != EXIT_OK
    assert [call[0] for call in opener.calls].count("POST") == 1
    assert _stage(payload, "build")["status"] == "FAILED"
    assert created not in json.dumps(payload.get("created_pages"))
    assert err == "sandbox stage failed\n"


def test_align_fails_fast_when_the_list_does_not_shrink(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from money_machine.cli import notion_sandbox_pipeline as pipeline_module

    client = FakeSandbox()
    ctx = _bound_run(client)
    page = client.create_child_page(SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    ctx.created_ids.append(canonical_id(_CHILD_IDS[1]))

    def _keep_tail(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(pipeline_module, "_drop_tail", _keep_tail)
    with pytest.raises(SandboxError, match="did not shrink"):
        pipeline_module._align(ctx, page, 0)  # pyright: ignore[reportPrivateUsage]


def test_scrub_hex_fails_fast_when_the_match_does_not_advance() -> None:
    from money_machine.cli import notion_sandbox_guard as guard_module

    class _Stuck(str):
        __slots__ = ()

        def lower(self) -> str:
            return self

        def find(self, _sub: str, _start: object = 0, _end: object = None) -> int:
            return 0

    with pytest.raises(SandboxError, match="did not advance"):
        guard_module._scrub_hex(_Stuck("abcdef"), "abcd")  # pyright: ignore[reportPrivateUsage]


def test_write_all_fails_fast_on_a_zero_byte_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from money_machine.cli import notion_sandbox_guard as guard_module

    target = tmp_path / "out.bin"
    fd = os.open(target, os.O_CREAT | os.O_WRONLY, 0o600)

    def _zero(_fd: int, _data: object) -> int:
        return 0

    monkeypatch.setattr(guard_module.os, "write", _zero)
    try:
        with pytest.raises(SandboxError, match="evidence write failed"):
            guard_module._write_all(fd, b"abc")  # pyright: ignore[reportPrivateUsage]
    finally:
        monkeypatch.undo()
        os.close(fd)


def test_dry_run_interrupt_during_write_keeps_build_not_run(
    evidence: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_write = os.write
    seen = {"n": 0}

    def _write(fd: int, data: bytes) -> int:
        if bytes(data).startswith(b"{"):
            seen["n"] += 1
            if seen["n"] == 1:
                raise KeyboardInterrupt
        return real_write(fd, data)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _write)
    code = main(
        ["--evidence-out", str(evidence)],
        client=FakeSandbox(),
        environ={"NOTION_SANDBOX_TOKEN": _SECRET},
        clock=_clock,
    )
    assert code == EXIT_API
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert _stage(payload, "build")["status"] == "NOT_RUN"
    assert payload["run_status"] == "INTERRUPTED"


def test_held_is_reset_between_main_calls(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    from money_machine.cli import notion_sandbox as sandbox_module

    sandbox_module._HELD.created = [{"id": "stale-id"}]  # pyright: ignore[reportPrivateUsage]
    sandbox_module._HELD.ready = True  # pyright: ignore[reportPrivateUsage]
    code, payload, _out, err, _logs = _invoke(evidence, capsys, caplog, [], client=FakeSandbox())
    assert code == EXIT_OK
    assert "stale-id" not in err
    assert payload["created_pages"] == []
    assert sandbox_module._HELD.created == []  # pyright: ignore[reportPrivateUsage]


def _mark_procfs(
    monkeypatch: pytest.MonkeyPatch,
    roots: tuple[Path, ...],
) -> None:
    """Treat ``roots`` as a procfs mount. Used in place of a user namespace."""
    from money_machine.cli import notion_sandbox_guard as guard_module

    real = guard_module._statfs_f_type  # pyright: ignore[reportPrivateUsage]
    abs_roots = tuple(Path(os.path.abspath(root)) for root in roots)

    def _ftype(path: Path) -> int | None:
        collapsed = Path(os.path.abspath(path))
        for root in abs_roots:
            if collapsed == root or root in collapsed.parents:
                return guard_module.PROC_SUPER_MAGIC
        return real(path)

    monkeypatch.setattr(guard_module, "_statfs_f_type", _ftype)


def test_tmp_kind_classifies_a_leftover_symlink(tmp_path: Path) -> None:
    from money_machine.cli import notion_sandbox_guard as guard_module

    leftover = tmp_path / ".ev.json.tmp"
    leftover.symlink_to(tmp_path / "missing-target")
    assert guard_module._tmp_kind(leftover) == "symlink"  # pyright: ignore[reportPrivateUsage]
    assert guard_module._tmp_kind(tmp_path / "absent") is None  # pyright: ignore[reportPrivateUsage]


def test_tmp_kind_classifies_dir_fifo_file_and_other(tmp_path: Path) -> None:
    from money_machine.cli import notion_sandbox_guard as guard_module

    directory = tmp_path / "dir.tmp"
    directory.mkdir()
    fifo = tmp_path / "fifo.tmp"
    os.mkfifo(fifo)
    regular = tmp_path / "file.tmp"
    regular.write_text("x", encoding="utf-8")
    assert guard_module._tmp_kind(directory) == "dir"  # pyright: ignore[reportPrivateUsage]
    assert guard_module._tmp_kind(fifo) == "fifo"  # pyright: ignore[reportPrivateUsage]
    assert guard_module._tmp_kind(regular) == "file"  # pyright: ignore[reportPrivateUsage]


def test_on_procfs_uses_filesystem_type_not_st_dev(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from money_machine.cli import notion_sandbox_guard as guard_module

    bind = tmp_path / "bind"
    bind.mkdir()
    assert guard_module._on_procfs(bind) is False  # pyright: ignore[reportPrivateUsage]
    _mark_procfs(monkeypatch, (bind,))
    assert guard_module._on_procfs(bind) is True  # pyright: ignore[reportPrivateUsage]
    assert under_proc(bind / "self" / "root" / "ev.json") is True


def test_bind_mounted_procfs_paths_are_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """B1: a bind-mounted /proc is detected by f_type, not by the /proc name."""
    bind = tmp_path / "bind"
    (bind / "self" / "root").mkdir(parents=True)
    (bind / "thread-self" / "root").mkdir(parents=True)
    _mark_procfs(monkeypatch, (bind,))
    cases = (
        bind / "self" / "root" / tmp_path.relative_to("/") / "ev.json",
        bind / "thread-self" / "root" / tmp_path.relative_to("/") / "ev.json",
    )
    for alias in cases:
        assert under_proc(alias) is True
        with pytest.raises(SandboxError, match="evidence path is refused"):
            open_evidence(alias)
        client = FakeSandbox()
        code, payload, _out, err, _logs = _invoke(
            alias, capsys, caplog, ["--execute"], client=client
        )
        assert code == EXIT_USAGE
        assert err == "evidence path is refused\n"
        assert payload == {}
        assert client.reads == []
        assert client.creates == []


def test_symlink_to_bind_mounted_procfs_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    bind = tmp_path / "bind"
    (bind / "self" / "root").mkdir(parents=True)
    _mark_procfs(monkeypatch, (bind,))
    link = tmp_path / "to_bind"
    link.symlink_to(bind / "self" / "root")
    alias = link / tmp_path.relative_to("/") / "ev.json"
    assert under_proc(alias) is True
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(alias, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert payload == {}
    assert client.reads == []
    assert client.creates == []


def test_second_procfs_instance_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """B3: a second procfs mount has a different st_dev and is still refused."""
    np_root = tmp_path / "np"
    (np_root / "self" / "root").mkdir(parents=True)
    (np_root / "1" / "root").mkdir(parents=True)
    _mark_procfs(monkeypatch, (np_root,))
    cases = (
        np_root / "self" / "root" / tmp_path.relative_to("/") / "ev.json",
        np_root / "1" / "root" / "ev.json",
    )
    for alias in cases:
        assert under_proc(alias) is True
        client = FakeSandbox()
        code, payload, _out, err, _logs = _invoke(
            alias, capsys, caplog, ["--execute"], client=client
        )
        assert code == EXIT_USAGE
        assert err == "evidence path is refused\n"
        assert payload == {}
        assert client.reads == []
        assert client.creates == []
    link = tmp_path / "to_np"
    link.symlink_to(np_root / "self" / "root")
    alias = link / tmp_path.relative_to("/") / "ev.json"
    assert under_proc(alias) is True
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(alias, capsys, caplog, [], client=client)
    assert code == EXIT_USAGE
    assert client.reads == []


def test_mountinfo_fstype_proc_is_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from money_machine.cli import notion_sandbox_guard as guard_module

    bind = tmp_path / "bind"
    bind.mkdir()
    mount = os.path.abspath(bind)

    def _no_statfs(_path: Path) -> int | None:
        return None

    monkeypatch.setattr(guard_module, "_statfs_f_type", _no_statfs)
    monkeypatch.setattr(
        guard_module,
        "_mountinfo_text",
        lambda: f"1 0 0:1 / {mount} rw - proc proc rw\n",
    )
    assert guard_module._on_procfs(bind) is True  # pyright: ignore[reportPrivateUsage]
    assert under_proc(bind / "self" / "root" / "ev.json") is True


def test_relative_symlink_to_proc_self_root_symlink_is_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """guard:405: a relative symlink to a /proc/self/root symlink is 64."""
    proc_link = tmp_path / "l_root"
    proc_link.symlink_to("/proc/self/root")
    rel = tmp_path / "rel"
    rel.symlink_to("l_root")
    alias = rel / tmp_path.relative_to("/") / "e3.json"
    assert under_proc(alias) is True
    with pytest.raises(SandboxError, match="evidence path is refused"):
        open_evidence(alias)
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(alias, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert payload == {}
    assert client.reads == []
    assert client.creates == []
    assert alias.exists() is False


def test_symlink_cycle_is_refused(tmp_path: Path) -> None:
    """A symlink cycle finishes and is refused, not walked forever."""
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.symlink_to("right")
    right.symlink_to("left")
    assert under_proc(left / "ev.json") is True
    assert under_proc(right / "ev.json") is True


def test_ancestor_symlink_to_ordinary_dir_is_accepted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """guard:457: a symlink ancestor to a normal directory is not refused."""
    real = tmp_path / "realdir"
    real.mkdir()
    (real / "subdir").mkdir()
    link = tmp_path / "linkdir"
    link.symlink_to(real)
    evidence = link / "subdir" / "ev.json"
    assert under_proc(evidence) is False
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(evidence, capsys, caplog, [], client=client)
    assert code == EXIT_OK
    assert err == ""
    assert payload["mode"] == "dry-run"
    assert evidence.is_file()
    assert client.creates == []


def test_dry_run_sigint_after_link_exits_69(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ns:421: SIGINT after the dry-run link is 69, not a traceback."""
    real_link = os.link

    def _link(
        src: str | os.PathLike[str],
        dst: str | os.PathLike[str],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        real_link(
            src,
            dst,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )
        os.kill(os.getpid(), signal.SIGINT)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.link", _link)
    before = signal.getsignal(signal.SIGINT)
    try:
        code = main(
            ["--evidence-out", str(evidence)],
            client=FakeSandbox(),
            environ={"NOTION_SANDBOX_TOKEN": _SECRET},
            clock=_clock,
        )
    except KeyboardInterrupt:
        pytest.fail("KeyboardInterrupt escaped the dry-run link")
    finally:
        signal.signal(signal.SIGINT, before)
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert code != 1
    assert "Traceback" not in captured.err
    assert "sandbox interrupted" in captured.err
    assert "evidence file changed" not in captured.err
    assert evidence.is_file()
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["mode"] == "dry-run"


def test_workspace_id_null_is_treated_as_absent(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """live:333 LF0: workspace_id null is an absent space, not a lie."""

    class _NullWorkspace(_DocOpener):
        def __call__(
            self,
            request: urllib.request.Request,
            data: object = None,
            *,
            timeout: object = None,
        ) -> _Response:
            response = super().__call__(request, data, timeout=timeout)
            raw = response.read()
            response.close()
            payload = json.loads(raw.decode("utf-8"))
            if type(payload) is dict and payload.get("object") == "page":
                payload["workspace_id"] = None
                raw = json.dumps(payload).encode("utf-8")
            return _Response(raw)

    opener = _NullWorkspace()
    client = LiveSandboxClient(_SECRET, opener)
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_OK
    assert err == ""
    assert len(opener.posts) == 5
    created = payload["created_pages"]
    assert isinstance(created, list)
    assert len(created) == 5


def test_raise_interrupt_sets_sig_ign_before_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from money_machine.cli import notion_sandbox as sandbox_module

    order: list[object] = []
    real = signal.signal

    def _track(sig: int, handler: object) -> object:
        order.append(handler)
        return real(sig, handler)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(sandbox_module.signal, "signal", _track)
    before = signal.getsignal(signal.SIGINT)
    hook_before = sys.unraisablehook
    try:
        with pytest.raises(KeyboardInterrupt):
            sandbox_module._raise_interrupt(signal.SIGINT, None)  # pyright: ignore[reportPrivateUsage]
        assert order
        assert order[0] is signal.SIG_IGN
        assert signal.getsignal(signal.SIGINT) is signal.SIG_IGN
    finally:
        signal.signal(signal.SIGINT, before)
        sys.unraisablehook = hook_before


def test_raise_interrupt_installs_race_hook_before_sig_ign(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ns:363-366: the race hook is in place before SIG_IGN can trip the race."""
    from money_machine.cli import notion_sandbox as sandbox_module

    seen: list[object] = []
    real = signal.signal

    def _track(sig: int, handler: object) -> object:
        seen.append(sys.unraisablehook)
        return real(sig, handler)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(sandbox_module.signal, "signal", _track)
    before = signal.getsignal(signal.SIGINT)
    hook_before = sys.unraisablehook
    try:
        with pytest.raises(KeyboardInterrupt):
            sandbox_module._raise_interrupt(signal.SIGINT, None)  # pyright: ignore[reportPrivateUsage]
        assert seen
        assert seen[0] is sandbox_module._ignore_sigint_race  # pyright: ignore[reportPrivateUsage]
    finally:
        signal.signal(signal.SIGINT, before)
        sys.unraisablehook = hook_before


def test_main_restores_unraisablehook_after_interrupt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ns:366: the process-wide hook is put back when main returns."""
    from money_machine.cli import notion_sandbox as sandbox_module

    class _Interrupting(FakeSandbox):
        def create_child_page(self, parent_id: str, title: str) -> PageView:
            sandbox_module._raise_interrupt(signal.SIGINT, None)  # pyright: ignore[reportPrivateUsage]
            raise AssertionError("unreachable")

    def _marker(_unraisable: object) -> None:
        return None

    before = signal.getsignal(signal.SIGINT)
    hook_before = sys.unraisablehook
    sys.unraisablehook = _marker
    try:
        evidence = tmp_path / "ev.json"
        code, _payload, _out, err, _logs = _invoke(
            evidence, capsys, caplog, ["--execute"], client=_Interrupting()
        )
        assert code == EXIT_API
        assert err.startswith("sandbox interrupted")
        assert sys.unraisablehook is _marker
    finally:
        signal.signal(signal.SIGINT, before)
        sys.unraisablehook = hook_before


def test_gap0_double_sigint_at_post2_keeps_ids_across_runs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """B5: gap-0 second SIGINT at POST:2 must keep ids on every measured run."""
    dropped = 0
    before = signal.getsignal(signal.SIGINT)
    try:
        for index in range(20):
            evidence = tmp_path / f"g{index}.json"

            class _Burst(FakeSandbox):
                def create_child_page(self, parent_id: str, title: str) -> PageView:
                    page = super().create_child_page(parent_id, title)
                    if len(self.creates) == 2:
                        os.kill(os.getpid(), signal.SIGINT)
                        os.kill(os.getpid(), signal.SIGINT)
                    return page

            try:
                code = main(
                    ["--evidence-out", str(evidence), "--execute"],
                    client=_Burst(),
                    environ={"NOTION_SANDBOX_TOKEN": _SECRET},
                    clock=_clock,
                )
            except KeyboardInterrupt:
                dropped += 1
                continue
            captured = capsys.readouterr()
            if code != EXIT_API:
                dropped += 1
                continue
            if (
                canonical_id(_CHILD_IDS[0]) not in captured.err
                or canonical_id(_CHILD_IDS[1]) not in captured.err
            ):
                dropped += 1
    finally:
        signal.signal(signal.SIGINT, before)
    assert dropped == 0


def test_dry_run_gap0_at_first_write_exits_69(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_write = os.write
    seen = {"n": 0}

    def _write(fd: int, data: bytes) -> int:
        if bytes(data).startswith(b"{"):
            seen["n"] += 1
            if seen["n"] == 1:
                os.kill(os.getpid(), signal.SIGINT)
                os.kill(os.getpid(), signal.SIGINT)
        return real_write(fd, data)

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.write", _write)
    before = signal.getsignal(signal.SIGINT)
    try:
        code = main(
            ["--evidence-out", str(evidence)],
            client=FakeSandbox(),
            environ={"NOTION_SANDBOX_TOKEN": _SECRET},
            clock=_clock,
        )
    except KeyboardInterrupt:
        pytest.fail("gap-0 SIGINT at WRITE:1 escaped main")
    finally:
        signal.signal(signal.SIGINT, before)
    captured = capsys.readouterr()
    assert code == EXIT_API
    assert code != -2
    assert "Traceback" not in captured.err


def test_link_enoent_after_creates_exits_69_with_ids(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _link(
        src: str | os.PathLike[str],
        dst: str | os.PathLike[str],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        del src, dst, src_dir_fd, dst_dir_fd, follow_symlinks
        raise OSError(errno.ENOENT, "missing")

    monkeypatch.setattr("money_machine.cli.notion_sandbox_guard.os.link", _link)
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_API
    assert code != EXIT_USAGE
    assert evidence.exists() is False
    assert payload == {}
    assert client.creates
    for page_id in _CHILD_IDS:
        assert canonical_id(page_id) in err


def test_missing_libc_refuses_before_any_post(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from money_machine.cli import notion_sandbox_guard as guard_module

    monkeypatch.setattr(guard_module, "_libc", lambda: None)
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert payload == {}
    assert client.reads == []
    assert client.creates == []
    assert evidence.exists() is False


def test_empty_mountinfo_refuses_before_any_post(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from money_machine.cli import notion_sandbox_guard as guard_module

    monkeypatch.setattr(guard_module, "_mountinfo_text", lambda: "")
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(
        evidence, capsys, caplog, ["--execute"], client=client
    )
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert payload == {}
    assert client.reads == []
    assert client.creates == []
    assert evidence.exists() is False


def test_literal_proc_is_refused_when_fstype_is_tmpfs(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """tmpfs over /proc still refuses the literal /proc path."""
    from money_machine.cli import notion_sandbox_guard as guard_module

    tmpfs_magic = 0x01021994
    real = guard_module._statfs_f_type  # pyright: ignore[reportPrivateUsage]

    def _ftype(path: Path) -> int | None:
        collapsed = Path(os.path.abspath(path))
        if collapsed == Path("/proc") or Path("/proc") in collapsed.parents:
            return tmpfs_magic
        return real(path)

    monkeypatch.setattr(guard_module, "_statfs_f_type", _ftype)
    alias = Path("/proc/ev_p60.json")
    assert under_proc(alias) is True
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(alias, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert payload == {}
    assert client.reads == []
    assert client.creates == []
    assert alias.exists() is False


def test_mountinfo_decodes_octal_escaped_space(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from money_machine.cli import notion_sandbox_guard as guard_module

    bind = tmp_path / "b sp"
    (bind / "self" / "root").mkdir(parents=True)
    mount = os.path.abspath(bind)
    escaped = mount.replace("\\", "\\134").replace(" ", "\\040")

    def _no_statfs(_path: Path) -> int | None:
        return None

    monkeypatch.setattr(guard_module, "_statfs_f_type", _no_statfs)
    monkeypatch.setattr(
        guard_module,
        "_mountinfo_text",
        lambda: f"1 0 0:1 / {escaped} rw - proc proc rw\n",
    )
    alias = bind / "self" / "root" / tmp_path.relative_to("/") / "e.json"
    assert guard_module._unescape_mount_field(escaped) == mount  # pyright: ignore[reportPrivateUsage]
    assert under_proc(alias) is True
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(alias, capsys, caplog, ["--execute"], client=client)
    assert code == EXIT_USAGE
    assert err == "evidence path is refused\n"
    assert payload == {}
    assert client.reads == []
    assert client.creates == []


def test_later_short_proc_mount_does_not_win(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later short proc line must not override a longer non-proc mount."""
    from money_machine.cli import notion_sandbox_guard as guard_module

    mount = os.path.abspath(tmp_path)
    real = guard_module._statfs_f_type  # pyright: ignore[reportPrivateUsage]

    def _skip_leaf(path: Path) -> int | None:
        collapsed = Path(os.path.abspath(path))
        if collapsed == Path(mount) or mount in str(collapsed):
            return None
        return real(path)

    monkeypatch.setattr(guard_module, "_statfs_f_type", _skip_leaf)
    monkeypatch.setattr(
        guard_module,
        "_mountinfo_text",
        lambda: f"1 0 0:1 / {mount} rw - ext4 /dev/sda rw\n2 0 0:2 / / rw - proc proc rw\n",
    )
    evidence = tmp_path / "ev.json"
    assert under_proc(evidence) is False
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(evidence, capsys, caplog, [], client=client)
    assert code == EXIT_OK
    assert err == ""
    assert payload["mode"] == "dry-run"
    assert evidence.is_file()
    assert client.creates == []


def test_relative_symlink_chain_of_16_is_accepted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    real = tmp_path / "real"
    (real / "sub").mkdir(parents=True)
    prev = "real"
    for index in range(16, 0, -1):
        link = tmp_path / f"s{index}"
        link.symlink_to(prev)
        prev = f"s{index}"
    evidence = tmp_path / "s1" / "sub" / "ev.json"
    assert under_proc(evidence) is False
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(evidence, capsys, caplog, [], client=client)
    assert code == EXIT_OK
    assert err == ""
    assert payload["mode"] == "dry-run"
    assert evidence.is_file()
    assert client.creates == []


@pytest.mark.parametrize("depth", [2, 8, 16])
def test_nested_relative_symlink_chain_is_accepted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    depth: int,
) -> None:
    """Each link sits inside the previous link's target: c/s1->x1, c/x1/s2->x2, ..."""
    base = tmp_path / "c"
    base.mkdir()
    real = base
    for index in range(1, depth + 1):
        (real / f"s{index}").symlink_to(f"x{index}")
        real = real / f"x{index}"
        real.mkdir()
    (real / "sub").mkdir()
    evidence = base.joinpath(*[f"s{index}" for index in range(1, depth + 1)], "sub", "ev.json")
    assert under_proc(evidence) is False
    client = FakeSandbox()
    code, payload, _out, err, _logs = _invoke(evidence, capsys, caplog, [], client=client)
    assert code == EXIT_OK
    assert err == ""
    assert payload["mode"] == "dry-run"
    assert evidence.is_file()
    assert (real / "sub" / "ev.json").is_file()
    assert client.creates == []


def test_symlink_self_loop_is_refused(tmp_path: Path) -> None:
    """A symlink to itself is refused by the target check, not walked forever."""
    loop = tmp_path / "loop"
    loop.symlink_to("loop")
    assert under_proc(loop / "ev.json") is True


def test_unique_walk_limit_refuses_an_overlong_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from money_machine.cli import notion_sandbox_guard as guard_module

    monkeypatch.setattr(guard_module, "_WALK_LIMIT", 8)
    real = tmp_path / "real"
    (real / "sub").mkdir(parents=True)
    prev = "real"
    for index in range(16, 0, -1):
        link = tmp_path / f"s{index}"
        link.symlink_to(prev)
        prev = f"s{index}"
    evidence = tmp_path / "s1" / "sub" / "ev.json"
    assert under_proc(evidence) is True


def test_fd_on_procfs_uses_fstatfs_not_proc_self_fd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from money_machine.cli import notion_sandbox_guard as guard_module

    seen: list[Path] = []

    def _no_fstatfs(_fd: int) -> int | None:
        return None

    def _track(path: Path) -> bool:
        seen.append(path)
        return False

    monkeypatch.setattr(guard_module, "_fstatfs_f_type", _no_fstatfs)
    monkeypatch.setattr(guard_module, "_mountinfo_is_proc", _track)
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        assert guard_module._fd_on_procfs(fd) is True  # pyright: ignore[reportPrivateUsage]
    finally:
        os.close(fd)
    assert seen == []


def test_publish_interrupted_ki_after_complete_file_returns_69(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ns:456: KeyboardInterrupt after the file is complete is 69, not a raise."""
    from money_machine.cli import notion_sandbox as sandbox_module

    path = tmp_path / "held.json"
    sandbox_module._reset_held()  # pyright: ignore[reportPrivateUsage]
    sandbox_module._remember_held(  # pyright: ignore[reportPrivateUsage]
        path,
        None,
        _WHEN,
        None,
        "dry-run",
        "a" * 40,
        {},
        empty_write_counts(),
    )

    def _write_then_interrupt(*_args: object, **_kwargs: object) -> int:
        path.write_text('{"ok": true}', encoding="utf-8")
        raise KeyboardInterrupt

    monkeypatch.setattr(sandbox_module, "_finish", _write_then_interrupt)
    before = signal.getsignal(signal.SIGINT)
    try:
        code = sandbox_module._publish_interrupted()  # pyright: ignore[reportPrivateUsage]
    except KeyboardInterrupt:
        pytest.fail("KeyboardInterrupt escaped the complete-file except")
    finally:
        signal.signal(signal.SIGINT, before)
        sandbox_module._reset_held()  # pyright: ignore[reportPrivateUsage]
    assert code == EXIT_API
    assert path.is_file()
