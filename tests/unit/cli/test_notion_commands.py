"""Notion connect, status, and test. Fakes only. No network and no live Notion."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from money_machine.cli.main import main
from money_machine.cli.notion import FakeNotionProbe

_SECRET = "secret_" + ("a" * 43)
_NTN = "ntn_" + ("b" * 43)
_SHORT = "secret_" + ("a" * 42)
_URL = "https://evil.example/?token=" + _SECRET


@pytest.fixture
def notion_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("MONEY_MACHINE_NOTION_API_KEY", raising=False)


def _invoke(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    command: str,
    *,
    token: str | None,
    probe: object | None = None,
) -> tuple[int, str, str, str]:
    if token is None:
        monkeypatch.delenv("NOTION_API_KEY", raising=False)
    else:
        monkeypatch.setenv("NOTION_API_KEY", token)
    caplog.set_level(logging.DEBUG)
    code = main(["integrations", "notion", command], notion_probe=probe)
    captured = capsys.readouterr()
    return code, captured.out, captured.err, caplog.text


@pytest.mark.parametrize(
    ("command", "token", "workspace"),
    [
        ("connect", _SECRET, "workspace-a"),
        ("connect", _SECRET + "c", "workspace-a"),
        ("status", _NTN, "fixture"),
        ("test", _SECRET, "fixture"),
    ],
    ids=["connect", "connect-44", "status", "test"],
)
def test_notion_commands_succeed(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    command: str,
    token: str,
    workspace: str,
) -> None:
    del notion_env
    probe = FakeNotionProbe(workspace=workspace)
    code, out, err, logs = _invoke(monkeypatch, capsys, caplog, command, token=token, probe=probe)
    assert code == 0
    assert err == ""
    assert token not in out
    assert token not in logs
    payload = json.loads(out)
    assert payload["command"] == command
    assert payload["mode"] == "fake"
    if command == "connect":
        assert payload["connected"] is True
        assert payload["workspace"] == "workspace-a"
        assert probe.calls == ["connect"]
    elif command == "status":
        assert payload == {
            "command": "status",
            "configured": True,
            "mode": "fake",
            "token_shape": "valid",
        }
        assert probe.calls == []
    else:
        assert payload["steps"] == ["page", "database", "publish", "unpublish", "archive"]
        assert probe.calls == ["test"]


@pytest.mark.parametrize("command", ["connect", "status", "test"])
def test_notion_commands_fail_when_config_is_missing(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    command: str,
) -> None:
    del notion_env
    code, out, err, logs = _invoke(monkeypatch, capsys, caplog, command, token=None)
    assert code == 78
    assert out == ""
    assert err == "notion is not configured\n"
    assert "notion is not configured" in logs


@pytest.mark.parametrize("command", ["connect", "status", "test"])
@pytest.mark.parametrize(
    "token",
    [_SHORT, _URL, "not-a-token", _SECRET + "!"],
    ids=["short", "token-url", "plain", "suffix"],
)
def test_bad_token_shape_is_redacted(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    command: str,
    token: str,
) -> None:
    del notion_env
    code, out, err, logs = _invoke(monkeypatch, capsys, caplog, command, token=token)
    assert code == 64
    assert out == ""
    assert err == "notion token shape is invalid\n"
    assert token not in out
    assert token not in err
    assert token not in logs
    assert _SECRET not in out
    assert _SECRET not in err
    assert _SECRET not in logs


@pytest.mark.parametrize("command", ["connect", "test"])
def test_fake_api_error_is_redacted(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    command: str,
) -> None:
    del notion_env
    probe = FakeNotionProbe(error=RuntimeError(_SECRET))
    code, out, err, logs = _invoke(monkeypatch, capsys, caplog, command, token=_SECRET, probe=probe)
    assert code == 69
    assert out == ""
    assert err == "notion api error\n"
    assert _SECRET not in out
    assert _SECRET not in err
    assert _SECRET not in logs
    assert probe.calls == ["connect" if command == "connect" else "test"]


def test_incomplete_sandbox_steps_fail(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    del notion_env
    probe = FakeNotionProbe(steps=("page",))
    code, out, err, logs = _invoke(monkeypatch, capsys, caplog, "test", token=_SECRET, probe=probe)
    assert code == 69
    assert out == ""
    assert err == "notion api error\n"
    assert _SECRET not in logs


def test_probe_workspace_that_echoes_the_token_is_redacted(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    del notion_env
    probe = FakeNotionProbe(workspace=_SECRET)
    code, out, err, logs = _invoke(
        monkeypatch, capsys, caplog, "connect", token=_SECRET, probe=probe
    )
    assert code == 69
    assert _SECRET not in out
    assert _SECRET not in err
    assert _SECRET not in logs


@pytest.mark.parametrize("workspace", [1, ""], ids=["non-string", "empty"])
def test_unsafe_workspace_is_an_api_error(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    workspace: object,
) -> None:
    del notion_env

    class _Probe:
        def connect(self, token: str) -> str:
            del token
            return workspace  # type: ignore[return-value]

        def run_sandbox(self, token: str) -> tuple[str, ...]:
            del token
            return ("page",)

    code, out, err, logs = _invoke(
        monkeypatch, capsys, caplog, "connect", token=_SECRET, probe=_Probe()
    )
    assert code == 69
    assert out == ""
    assert _SECRET not in err
    assert _SECRET not in logs


def test_notion_cli_does_not_import_a_client() -> None:
    source = Path("src/money_machine/cli/notion.py").read_text(encoding="utf-8")
    assert "notion_client" not in source
    assert "socket" not in source
    assert "urllib" not in source
