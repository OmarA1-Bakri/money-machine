"""Sandbox runner guards. Fake client only. Sockets stay closed."""

from __future__ import annotations

import ast
import io
import json
import logging
import socket
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

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
    SandboxError,
    argv_refused,
    canonical_id,
    git_sha,
    leaks,
    override_env,
    parent_is_allowed,
    qa_verdict,
    redact_text,
    stage_status,
    target_ok,
    token_from_environ,
    write_evidence,
)
from money_machine.cli.notion_sandbox_live import LiveSandboxClient
from money_machine.cli.notion_sandbox_pipeline import SandboxRun, create_under

_SECRET = "secret_" + ("a" * 43)
_NTN = "ntn_" + ("b" * 43)
_SHORT = "secret_abc"
_SPACE_RAW = "89282FB0AF948106809E0003C027FA07"
_PARENT_RAW = "3ED82FB0AF9480DC8272F40B16376B81"
_WRONG_SPACE = "89282fb0-ffff-8106-809e-0003c027fa07"
_WRONG_PARENT = "3ed82fb0-ffff-80dc-8272-f40b16376b81"
_WHEN = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
_CHILD_IDS = (
    "AAAAAAAAAAAA4AAA8AAAAAAAAAAAAAA1",
    "AAAAAAAAAAAA4AAA8AAAAAAAAAAAAAA2",
    "AAAAAAAAAAAA4AAA8AAAAAAAAAAAAAA3",
    "AAAAAAAAAAAA4AAA8AAAAAAAAAAAAAA4",
    "AAAAAAAAAAAA4AAA8AAAAAAAAAAAAAA5",
)
_OVERRIDE_ENV = (
    "NOTION_PARENT_PAGE_ID",
    "NOTION_SANDBOX_PARENT",
    "NOTION_SANDBOX_PARENT_PAGE_ID",
    "NOTION_SANDBOX_SPACE_ID",
    "NOTION_SANDBOX_TOKEN_FILE",
    "NOTION_SPACE_ID",
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
        user_type: str = "bot",
        error: BaseException | None = None,
    ) -> None:
        self.space = space
        self.page_id = page_id
        self.page_space = space if page_space is None else page_space
        self.archived = archived
        self.user_type = user_type
        self.error = error
        self.write_counts: dict[str, int] = {}
        self.creates: list[tuple[str, str]] = []
        self.reads: list[str] = []

    def read_bot(self) -> BotView:
        self.reads.append("bot")
        if self.error is not None:
            raise self.error
        return BotView(user_id="bot-user", user_type=self.user_type, space_id=self.space)

    def read_page(self, page_id: str) -> PageView:
        self.reads.append(page_id)
        return PageView(
            page_id=self.page_id,
            parent_id="",
            space_id=self.page_space,
            url=f"https://www.notion.so/{_PARENT_RAW.lower()}",
            archived=self.archived,
        )

    def create_child_page(self, parent_id: str, title: str) -> PageView:
        self.creates.append((parent_id, title))
        index = len(self.creates) - 1
        page_id = _CHILD_IDS[index]
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
    client: FakeSandbox | None = None,
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
    client: FakeSandbox | None = None,
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
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    for client in (
        FakeSandbox(page_id=_WRONG_PARENT.replace("-", "").upper()),
        FakeSandbox(page_space=_WRONG_SPACE),
        FakeSandbox(archived=True),
        FakeSandbox(user_type="person"),
    ):
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
    assert sum(value for key, value in counts.items() if key != "create_child_page") > 0
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
    page = client.read_page(SANDBOX_PARENT_PAGE_ID)
    assert repr(client) == "LiveSandboxClient"
    assert bot.space_id == SANDBOX_SPACE_ID
    assert page.page_id == SANDBOX_PARENT_PAGE_ID
    assert page.space_id == SANDBOX_SPACE_ID
    assert [call[0] for call in opener.calls] == ["GET", "GET"]
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
    page = client.create_child_page(SANDBOX_PARENT_PAGE_ID, "Sandbox Weekly Planner")
    assert page.page_id == canonical_id(created)
    assert page.parent_id == SANDBOX_PARENT_PAGE_ID
    assert opener.calls[0][0] == "POST"
    assert sum(client.write_counts.values()) == 0
