"""Sandbox runner guards. Fake client only. Sockets stay closed."""

from __future__ import annotations

import ast
import asyncio
import base64
import contextlib
import errno
import io
import json
import logging
import os
import socket
import stat
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from urllib.parse import quote

import pytest

from money_machine.cli.notion_sandbox import main, reraise
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
    assert payload["current_session"] == 7
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
    assert err == "sandbox interrupted\n"
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


@pytest.mark.parametrize("flag", ["archived", "in_trash"])
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
    assert created == []
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
        assert captured.err == "notion api error\n"
        assert "Traceback" not in captured.err
        assert "Traceback" not in caplog.text
        assert _SECRET not in captured.err
        assert _SECRET not in caplog.text
        body = path.read_text(encoding="utf-8")
        assert body != ""
        assert _SECRET not in body
        loaded = json.loads(body)
        assert loaded["error"] == "notion api error"
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
    assert created == []


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
    assert [page["id"] for page in created] == [canonical_id(_LIE_ID)]


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
    for name in ("SSL_CERT_FILE", "SSL_CERT_DIR"):
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
        os.unlink(evidence)
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
    def __init__(self, *, confirm_fails: bool = False) -> None:
        self.confirm_fails = confirm_fails
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
    assert err == "sandbox interrupted\n"
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
    assert err == "sandbox interrupted\n"
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
    assert _recorded(payload) == []


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
    assert _recorded(payload) == []


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
    assert under_proc(Path("/tmp/evidence.json")) is False


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


def test_system_exit_status_is_normalized() -> None:
    for status in (0, None, "no"):
        with pytest.raises(SystemExit) as caught:
            reraise(SystemExit(status))
        assert caught.value.code == 1


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


def test_explicit_space_skips_a_non_id() -> None:
    found = explicit_space({"space_id": "nope", "workspace_id": SANDBOX_SPACE_ID})
    assert found == SANDBOX_SPACE_ID


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


def test_commit_evidence_rejects_a_replaced_inode(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    fd = open_evidence(path)
    path.unlink()
    path.write_text("swapped", encoding="utf-8")
    with pytest.raises(SandboxError, match="changed") as caught:
        commit_evidence(fd, path, {"note": "ok"}, None)
    assert caught.value.code == EXIT_API


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


def test_reraise_preserves_interrupt_and_base_exceptions() -> None:
    with pytest.raises(KeyboardInterrupt) as interrupt:
        reraise(KeyboardInterrupt(_SECRET))
    assert str(interrupt.value) == ""
    with pytest.raises(BaseException) as base:
        reraise(BaseException(_SECRET))
    assert type(base.value) is BaseException
    assert str(base.value) == ""
    assert _SECRET not in str(base.value)


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
        fd = open_evidence(path)
        with pytest.raises(SandboxError) as caught:
            commit_evidence(fd, path, {"created_pages": created}, None)
        assert str(caught.value) == "evidence write failed"
        assert caught.value.code == EXIT_API


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
