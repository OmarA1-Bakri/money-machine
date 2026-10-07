"""Sandbox runner guards. Fake client only. Sockets stay closed."""

from __future__ import annotations

import ast
import base64
import io
import json
import logging
import os
import socket
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
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
    empty_write_counts,
    git_sha,
    leaks,
    override_env,
    parent_is_allowed,
    qa_verdict,
    redact_text,
    repo_root,
    stage_status,
    target_ok,
    token_from_environ,
    write_evidence,
)
from money_machine.cli.notion_sandbox_live import (
    NOTION_VERSION,
    LiveSandboxClient,
    asserted_body_parent,
    parse_page,
    proxy_map,
)
from money_machine.cli.notion_sandbox_pipeline import SandboxRun, create_under

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
        user_id: str = "bot-user",
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
            )
        return PageView(
            page_id=wanted,
            parent_id=_WRONG_PARENT,
            space_id=_WRONG_SPACE,
            url="https://www.notion.so/foreign",
            archived=False,
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
        )
        return PageView(
            page_id=page_id,
            parent_id=parent_id.replace("-", "").upper(),
            space_id=_SPACE_RAW,
            url=f"https://www.notion.so/{page_id.lower()}",
            archived=False,
        )


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
    counts = payload["write_counts"]
    assert isinstance(counts, dict)
    assert client.creates == []
    assert sum(counts.values()) == 0
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
    counts = payload["write_counts"]
    assert isinstance(counts, dict)
    assert client.reads == []
    assert client.creates == []
    assert sum(counts.values()) == 0
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
    counts = payload["write_counts"]
    assert isinstance(counts, dict)
    assert client.creates == []
    assert payload["created_pages"] == []
    assert sum(counts.values()) == 0
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
    counts = payload["write_counts"]
    assert isinstance(counts, dict)
    assert client.creates == []
    assert payload["created_pages"] == []
    assert sum(counts.values()) == 0
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
    assert payload["control_state_revision"] == 56
    assert payload["current_session"] == 7
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
    assert counts["create_child_page"] == 5
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
    assert "get_public_url" not in counts
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
    counts = payload["write_counts"]
    assert isinstance(counts, dict)
    assert payload["qa_verdict"] == "NOT_RUN"
    assert sum(counts.values()) == 0


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
        return PageView(page.page_id, _WRONG_PARENT, page.space_id, page.url, False)


class _LieReread(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        child = canonical_id(page.page_id)
        stored = self.pages[child]
        self.pages[child] = PageView(stored.page_id, _WRONG_PARENT, _WRONG_SPACE, stored.url, False)
        return page


class _WrongNest(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        if len(self.creates) == 2:
            child = canonical_id(page.page_id)
            stored = self.pages[child]
            self.pages[child] = PageView(
                stored.page_id,
                SANDBOX_PARENT_PAGE_ID,
                stored.space_id,
                stored.url,
                False,
            )
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
            return PageView(_LIE_ID, page.parent_id, page.space_id, page.url, False)
        return page

    def read_page(self, page_id: str) -> PageView:
        if canonical_id(page_id) == canonical_id(_LIE_ID) and self.pages:
            return next(iter(self.pages.values()))
        return super().read_page(page_id)


class _WrongSpaceReturn(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        if len(self.creates) == 1:
            return PageView(page.page_id, page.parent_id, _WRONG_SPACE, page.url, False)
        return page


class _BrokenAncestor(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        if len(self.creates) == 2:
            product = canonical_id(_CHILD_IDS[0])
            stored = self.pages[product]
            self.pages[product] = PageView(
                stored.page_id,
                _WRONG_PARENT,
                stored.space_id,
                stored.url,
                False,
            )
        return page


class _SecretUrl(FakeSandbox):
    def create_child_page(self, parent_id: str, title: str) -> PageView:
        page = super().create_child_page(parent_id, title)
        child = canonical_id(page.page_id)
        stored = self.pages[child]
        leaked = f"https://www.notion.so/{_SECRET}"
        self.pages[child] = PageView(
            stored.page_id,
            stored.parent_id,
            stored.space_id,
            leaked,
            False,
        )
        return PageView(page.page_id, page.parent_id, page.space_id, leaked, False)


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
    assert payload["created_pages"] == []
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
    assert payload["created_pages"] == []
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
    assert len(client.creates) == 1
    assert payload["created_pages"] == []
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
    exited = FakeSandbox(error=SystemExit(7))
    with pytest.raises(SystemExit) as caught:
        main(
            ["--evidence-out", str(evidence), "--execute"],
            client=exited,
            environ={"NOTION_SANDBOX_TOKEN": _SECRET},
            clock=_clock,
        )
    assert caught.value.code == 7
    assert exited.creates == []
    interrupted = FakeSandbox(error=KeyboardInterrupt(_SECRET))
    other = evidence.with_name("interrupt.json")
    with pytest.raises(KeyboardInterrupt) as blank:
        main(
            ["--evidence-out", str(other), "--execute"],
            client=interrupted,
            environ={"NOTION_SANDBOX_TOKEN": _SECRET},
            clock=_clock,
        )
    assert blank.value.args == ()
    assert _SECRET not in str(blank.value)
    assert interrupted.creates == []
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert _SECRET not in captured.err
    assert _SECRET not in caplog.text


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
    assert len(created) == 1
