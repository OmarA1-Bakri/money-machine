"""Notion connect, status, and test. Fakes only. No network and no live Notion."""

from __future__ import annotations

import json
import logging
import socket
import traceback
from pathlib import Path

import pytest

from money_machine.cli.main import main
from money_machine.cli.notion import SANDBOX_STEPS, FakeNotionProbe

_SECRET = "secret_" + ("a" * 43)
_NTN = "ntn_" + ("b" * 43)
_SHORT = "secret_" + ("a" * 42)
_URL = "https://evil.example/?token=" + _SECRET
_UNDERSCORE = "secret_" + ("a" * 42) + "_"
_UNICODE = "secret_" + ("a" * 42) + "é"


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
    [_SHORT, _URL, "not-a-token", _SECRET + "!", _UNDERSCORE, _UNICODE],
    ids=["short", "token-url", "plain", "suffix", "underscore", "unicode"],
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


class _LeakyError(Exception):
    def __str__(self) -> str:
        return _URL

    def __repr__(self) -> str:
        return _URL


def _api_error(kind: str) -> BaseException:
    if kind == "value":
        return ValueError(_SECRET)
    if kind == "os":
        return OSError(_SECRET)
    if kind == "key":
        return KeyError(_SECRET)
    if kind == "leaky":
        return _LeakyError()
    if kind == "token-url":
        return ValueError(_URL)
    raise AssertionError(kind)


@pytest.mark.parametrize("command", ["connect", "test"])
@pytest.mark.parametrize("kind", ["value", "os", "key", "leaky", "token-url"])
def test_fake_api_error_is_redacted(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    command: str,
    kind: str,
) -> None:
    del notion_env
    probe = FakeNotionProbe(error=_api_error(kind))
    code, out, err, logs = _invoke(monkeypatch, capsys, caplog, command, token=_SECRET, probe=probe)
    assert code == 69
    assert out == ""
    assert err == "notion api error\n"
    assert _SECRET not in out
    assert _SECRET not in err
    assert _SECRET not in logs
    assert _URL not in out
    assert _URL not in err
    assert _URL not in logs
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
    source = (Path(__file__).parents[3] / "src" / "money_machine" / "cli" / "notion.py").read_text(
        encoding="utf-8"
    )
    for name in ("notion_client", "socket", "urllib", "httpx", "requests", "playwright"):
        assert name not in source


class _TokenInterrupt(KeyboardInterrupt):
    """KeyboardInterrupt subclass whose message would leak the token."""


def _base_error(kind: str) -> BaseException:
    if kind == "keyboard":
        return KeyboardInterrupt(_SECRET)
    if kind == "system":
        return SystemExit(_SECRET)
    if kind == "subclass":
        return _TokenInterrupt(_SECRET)
    raise AssertionError(kind)


@pytest.mark.parametrize("command", ["connect", "test"])
@pytest.mark.parametrize("kind", ["keyboard", "system", "subclass"])
def test_probe_base_exception_traceback_has_no_token(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    command: str,
    kind: str,
) -> None:
    del notion_env
    error = _base_error(kind)
    probe = FakeNotionProbe(error=error)
    with pytest.raises(BaseException) as caught:
        _invoke(monkeypatch, capsys, caplog, command, token=_SECRET, probe=probe)
    assert type(caught.value) is type(error)
    assert caught.value.args == ()
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    text = "".join(traceback.format_exception(caught.value))
    captured = capsys.readouterr()
    assert _SECRET not in text
    assert _SECRET not in captured.out
    assert _SECRET not in captured.err
    assert _SECRET not in caplog.text


class _AlwaysEqual(tuple[str, ...]):
    def __eq__(self, other: object) -> bool:
        return True

    def __hash__(self) -> int:
        return 0


class _Page(str):
    def __eq__(self, other: object) -> bool:
        return other == "page"

    def __hash__(self) -> int:
        return hash("page")

    def __str__(self) -> str:
        return _SECRET

    def __repr__(self) -> str:
        return _SECRET


class _StepsProbe:
    def __init__(self, steps: object) -> None:
        self._steps = steps

    def connect(self, token: str) -> str:
        del token
        return "fixture"

    def run_sandbox(self, token: str) -> tuple[str, ...]:
        del token
        return self._steps  # type: ignore[return-value]


def test_equal_tuple_subclass_is_rejected(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    del notion_env
    probe = _StepsProbe(_AlwaysEqual(SANDBOX_STEPS))
    code, out, err, logs = _invoke(monkeypatch, capsys, caplog, "test", token=_SECRET, probe=probe)
    assert code == 69
    assert out == ""
    assert err == "notion api error\n"
    assert _SECRET not in out
    assert _SECRET not in err
    assert _SECRET not in logs


def test_token_str_subclass_step_is_rejected(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    del notion_env
    page = _Page("page")
    probe = _StepsProbe((page, "database", "publish", "unpublish", "archive"))
    code, out, err, logs = _invoke(monkeypatch, capsys, caplog, "test", token=_SECRET, probe=probe)
    assert code == 69
    assert out == ""
    assert err == "notion api error\n"
    assert _SECRET not in out
    assert _SECRET not in err
    assert _SECRET not in logs


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _offline(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise OSError("network disabled")

    monkeypatch.setattr(socket, "socket", _offline)
    monkeypatch.setattr(socket, "create_connection", _offline)


@pytest.mark.parametrize("command", ["connect", "test"])
def test_default_probe_uses_the_fixture(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    command: str,
) -> None:
    del notion_env
    _block_network(monkeypatch)
    code, out, err, logs = _invoke(monkeypatch, capsys, caplog, command, token=_SECRET, probe=None)
    assert code == 0
    assert err == ""
    assert _SECRET not in out
    assert _SECRET not in logs
    payload = json.loads(out)
    assert payload["mode"] == "fake"
    if command == "connect":
        assert payload["workspace"] == "fixture"
    else:
        assert payload["steps"] == ["page", "database", "publish", "unpublish", "archive"]


def test_main_does_not_echo_a_notion_exception(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    del notion_env

    def _boom(arguments: object) -> int:
        del arguments
        raise ValueError(_SECRET)

    monkeypatch.setattr("money_machine.cli.main.command_notion_connect", _boom)
    monkeypatch.setenv("NOTION_API_KEY", _SECRET)
    caplog.set_level(logging.DEBUG)
    code = main(["integrations", "notion", "connect"])
    captured = capsys.readouterr()
    assert code == 78
    assert captured.out == ""
    assert captured.err == "command failed: ValueError\n"
    assert _SECRET not in captured.out
    assert _SECRET not in captured.err
    assert _SECRET not in caplog.text


@pytest.mark.parametrize(
    "workspace",
    ["ws-" + _SECRET, _SECRET.upper(), "a" * 43, "fixt\u200bure", "fix+ture"],
    ids=["ws-token", "upper", "partial", "zero-width", "base64-mark"],
)
def test_workspace_token_variant_is_rejected(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    workspace: str,
) -> None:
    del notion_env
    probe = FakeNotionProbe(workspace=workspace)
    code, out, err, logs = _invoke(
        monkeypatch, capsys, caplog, "connect", token=_SECRET, probe=probe
    )
    assert code == 69
    assert out == ""
    assert err == "notion api error\n"
    assert _SECRET not in out
    assert _SECRET not in err
    assert _SECRET not in logs
    assert workspace not in out
