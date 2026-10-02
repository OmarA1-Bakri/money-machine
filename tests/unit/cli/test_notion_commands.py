"""Notion connect, status, and test. Fakes only. No network and no live Notion."""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import sys
import traceback
from pathlib import Path

import pytest

from money_machine.cli.main import main
from money_machine.cli.notion import SANDBOX_STEPS, FakeNotionProbe

_SECRET = "secret_" + ("a" * 43)
# The sample body is 42 characters, short of the shape check, so one letter is added.
_MIXED = "ntn_Q7xK2mP9aZ4bR8cW1dY6eT3fU5gV0hNsJ2kL4oI8uEM"
_MIXED_BODY = _MIXED[4:]
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


class _NeedsArgument(BaseException):
    """BaseException whose constructor requires the token."""

    def __init__(self, secret: str) -> None:
        super().__init__(secret)


class _NeedsKeyboard(KeyboardInterrupt):
    """KeyboardInterrupt whose constructor requires the token."""

    def __init__(self, secret: str) -> None:
        super().__init__(secret)


class _NeedsGenerator(GeneratorExit):
    """GeneratorExit whose constructor requires the token."""

    def __init__(self, secret: str) -> None:
        super().__init__(secret)


def _base_error(kind: str) -> tuple[BaseException, type[BaseException], int | None]:
    if kind == "keyboard":
        return KeyboardInterrupt(_SECRET), KeyboardInterrupt, None
    if kind == "system":
        return SystemExit(_SECRET), SystemExit, 1
    if kind == "exit-2":
        return SystemExit(2), SystemExit, 2
    if kind == "exit-0":
        return SystemExit(0), SystemExit, 1
    if kind == "exit-false":
        return SystemExit(False), SystemExit, 1
    if kind == "subclass":
        return _TokenInterrupt(_SECRET), _TokenInterrupt, None
    if kind == "generator":
        return GeneratorExit(_SECRET), GeneratorExit, None
    if kind == "needs-arg":
        return _NeedsArgument(_SECRET), BaseException, None
    if kind == "group":
        return BaseExceptionGroup(_SECRET, [BaseException(_SECRET)]), BaseException, None
    if kind == "needs-keyboard":
        return _NeedsKeyboard(_SECRET), KeyboardInterrupt, None
    if kind == "needs-generator":
        return _NeedsGenerator(_SECRET), GeneratorExit, None
    raise AssertionError(kind)


def _exception_text(error: BaseException) -> str:
    chunks = ["".join(traceback.format_exception(error)), repr(error)]
    if error.__context__ is not None:
        chunks.append(repr(error.__context__))
        chunks.append("".join(traceback.format_exception(error.__context__)))
    if error.__cause__ is not None:
        chunks.append(repr(error.__cause__))
        chunks.append("".join(traceback.format_exception(error.__cause__)))
    nested = getattr(error, "exceptions", ())
    if isinstance(nested, tuple):
        for item in nested:
            if isinstance(item, BaseException):
                chunks.append(repr(item))
                chunks.append("".join(traceback.format_exception(item)))
    return "\n".join(chunks)


@pytest.mark.parametrize("command", ["connect", "test"])
@pytest.mark.parametrize(
    "kind",
    [
        "keyboard",
        "system",
        "exit-2",
        "exit-0",
        "exit-false",
        "subclass",
        "generator",
        "needs-arg",
        "group",
        "needs-keyboard",
        "needs-generator",
    ],
)
def test_probe_base_exception_traceback_has_no_token(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    command: str,
    kind: str,
) -> None:
    del notion_env
    error, expected_type, expected_code = _base_error(kind)
    probe = FakeNotionProbe(error=error)
    with pytest.raises(BaseException) as caught:
        _invoke(monkeypatch, capsys, caplog, command, token=_SECRET, probe=probe)
    assert type(caught.value) is expected_type
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert caught.value.__suppress_context__ is True
    if expected_code is not None:
        assert isinstance(caught.value, SystemExit)
        assert caught.value.code == expected_code
    text = _exception_text(caught.value)
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


def _separated_body(separator: str) -> str:
    body = "a" * 43
    parts = [body[index : index + 6] for index in range(0, len(body), 6)]
    return separator.join(parts)


@pytest.mark.parametrize(
    "workspace",
    [
        "ws-" + _SECRET,
        _SECRET.upper(),
        _SECRET[:40],
        "a" * 42,
        "a" * 21,
        "a" * 12,
        _separated_body("-"),
        _separated_body("."),
        _separated_body("_"),
        _separated_body(" "),
        "secret_shop",
        "SeCrEt_shop",
        "ntn_shop",
        "NtN_shop",
        "fixt\u200bure",
        "fix+ture",
        "w" * 101,
    ],
    ids=[
        "ws-token",
        "upper",
        "partial",
        "body-42",
        "half",
        "body-12",
        "dash",
        "dot",
        "underscore",
        "space",
        "lower",
        "mixed",
        "ntn-lower",
        "ntn-mixed",
        "zero-width",
        "base64-mark",
        "len-101",
    ],
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


@pytest.mark.parametrize(
    "workspace",
    ["a" * 11, "w" * 100],
    ids=["body-11", "len-100"],
)
def test_bounded_workspace_names_connect(
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
    assert code == 0
    assert err == ""
    payload = json.loads(out)
    assert payload["workspace"] == workspace
    assert _SECRET not in out
    assert _SECRET not in err
    assert _SECRET not in logs


def test_workspace_str_subclass_is_rejected(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    del notion_env

    class _Name(str):
        def __str__(self) -> str:
            return _SECRET

    probe = FakeNotionProbe(workspace=_Name("fixture"))
    code, out, err, logs = _invoke(
        monkeypatch, capsys, caplog, "connect", token=_SECRET, probe=probe
    )
    assert code == 69
    assert out == ""
    assert err == "notion api error\n"
    assert _SECRET not in out
    assert _SECRET not in err
    assert _SECRET not in logs


_MIXED_WORKSPACES = (
    _MIXED_BODY,
    _MIXED_BODY[:12],
    _MIXED_BODY[-12:],
    _MIXED_BODY[16:28],
    "shop secret_x",
    "x NTN_y",
)


@pytest.mark.parametrize(
    "workspace",
    _MIXED_WORKSPACES,
    ids=["body", "head", "tail", "middle", "shop-secret", "ntn-mid"],
)
def test_mixed_token_workspace_is_rejected(
    notion_env: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    workspace: str,
) -> None:
    del notion_env
    probe = FakeNotionProbe(workspace=workspace)
    code, out, err, logs = _invoke(
        monkeypatch, capsys, caplog, "connect", token=_MIXED, probe=probe
    )
    assert code == 69
    assert out == ""
    assert err == "notion api error\n"
    assert _MIXED not in out
    assert _MIXED not in err
    assert _MIXED not in logs
    assert workspace not in out
    assert workspace not in err


_INTERRUPT_SCRIPT = """
import os
import sys

from money_machine.cli.main import main
from money_machine.cli.notion import FakeNotionProbe

token = os.environ["NOTION_API_KEY"]
kind = os.environ["MM_KIND"]
command = os.environ["MM_COMMAND"]


class _ValueKeyboard(KeyboardInterrupt):
    def __init__(self, secret: str | None = None) -> None:
        if secret is None:
            raise ValueError("constructor")
        super().__init__(secret)


if kind == "value-keyboard":
    error = _ValueKeyboard(token)
elif kind == "group-keyboard":
    error = BaseExceptionGroup("group", (KeyboardInterrupt(token),))
else:
    raise AssertionError(kind)

probe = FakeNotionProbe(error=error)
sys.exit(main(["integrations", "notion", command], notion_probe=probe))
"""


def _shell_status(code: int) -> int:
    """Map a signal death to the status a shell reports. Signal 2 is 130."""
    if code < 0:
        return 128 - code
    return code


@pytest.mark.parametrize("command", ["connect", "test"])
@pytest.mark.parametrize("kind", ["value-keyboard", "group-keyboard"])
def test_keyboard_interrupt_still_exits_130(notion_env: None, command: str, kind: str) -> None:
    del notion_env
    result = subprocess.run(
        [sys.executable, "-c", _INTERRUPT_SCRIPT],
        capture_output=True,
        text=True,
        env={
            "APP_ENV": "test",
            "NOTION_API_KEY": _SECRET,
            "MM_KIND": kind,
            "MM_COMMAND": command,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PATH": os.environ.get("PATH", ""),
        },
        check=False,
    )
    assert _shell_status(result.returncode) == 130
    assert _SECRET not in result.stdout
    assert _SECRET not in result.stderr
