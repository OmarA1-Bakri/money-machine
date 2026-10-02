"""Notion connect, status, and test.

Session 06 prompt heading ``### 9. Live connection path``. The probe is
injected. The default probe is in-process and does not open a network
connection, a browser, or a live Notion workspace. The token is checked for
shape and is never printed or logged.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import NoReturn, Protocol

from money_machine.config.runtime import load_runtime_settings

LOGGER = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_BAD_TOKEN = 64
EXIT_API = 69
EXIT_MISSING = 78

_TOKEN_RE = re.compile(r"(?:secret_|ntn_)[A-Za-z0-9]{43,}")
# Workspace names stay inside this set. Zero-width marks and base64 punctuation
# fall outside it. Hex, reversed, rot13, base64, and sha copies are a non-goal,
# as are 11-character fragments and non-contiguous fragments: only an injected
# probe can produce the encoded copies, and this check does not scan them.
_WORKSPACE_RE = re.compile(r"[A-Za-z0-9 _.-]{1,100}")
_BODY_WINDOW = 12
_SEPARATORS = "-._ "
SANDBOX_STEPS = ("page", "database", "publish", "unpublish", "archive")


class NotionProbe(Protocol):
    """Injected connection boundary. Tests pass a fake."""

    def connect(self, token: str) -> str:
        """Return a workspace name that does not contain the token."""
        ...

    def run_sandbox(self, token: str) -> tuple[str, ...]:
        """Return the safe sandbox step names."""
        ...


class FakeNotionProbe:
    """In-process probe. It performs no I/O and stores no token."""

    def __init__(
        self,
        *,
        error: BaseException | None = None,
        workspace: str = "fixture",
        steps: tuple[str, ...] = SANDBOX_STEPS,
    ) -> None:
        self._error = error
        self._workspace = workspace
        self._steps = steps
        self.calls: list[str] = []

    def connect(self, token: str) -> str:
        self.calls.append("connect")
        del token
        if self._error is not None:
            raise self._error
        return self._workspace

    def run_sandbox(self, token: str) -> tuple[str, ...]:
        self.calls.append("test")
        del token
        if self._error is not None:
            raise self._error
        return self._steps


def token_shape_ok(token: str) -> bool:
    """A Notion token is ``secret_`` or ``ntn_`` plus 43 or more ASCII alphanumerics."""
    return re.fullmatch(_TOKEN_RE, token) is not None


def _probe(arguments: object) -> NotionProbe:
    probe = getattr(arguments, "notion_probe", None)
    if probe is None:
        return FakeNotionProbe()
    return probe


def _token() -> str | None:
    provider = load_runtime_settings().provider("notion")
    if provider is None or provider.api_key is None:
        return None
    return provider.api_key.reveal()


def _fail(message: str, code: int) -> int:
    LOGGER.info("%s", message)
    print(message, file=sys.stderr)
    return code


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True))


def _require_token() -> str | int:
    token = _token()
    if token is None:
        return _fail("notion is not configured", EXIT_MISSING)
    if not token_shape_ok(token):
        return _fail("notion token shape is invalid", EXIT_BAD_TOKEN)
    return token


def _token_body(token: str) -> str:
    folded = token.casefold()
    for prefix in ("secret_", "ntn_"):
        if folded.startswith(prefix):
            return token[len(prefix) :]
    return token


def _bad_workspace(workspace: object, token: str) -> bool:
    if type(workspace) is not str:
        return True
    if re.fullmatch(_WORKSPACE_RE, workspace) is None:
        return True
    folded = workspace.casefold()
    if "secret_" in folded or "ntn_" in folded:
        return True
    stripped = "".join(character for character in folded if character not in _SEPARATORS)
    body = _token_body(token).casefold()
    if len(body) < _BODY_WINDOW:
        return False
    window = _BODY_WINDOW
    return any(body[start : start + window] in stripped for start in range(len(body) - window + 1))


def _bad_steps(steps: object) -> bool:
    if type(steps) is not tuple:
        return True
    if any(type(item) is not str for item in steps):
        return True
    return steps != SANDBOX_STEPS


def _keyboard_interrupt_in(exc: BaseException) -> bool:
    if isinstance(exc, KeyboardInterrupt):
        return True
    nested = getattr(exc, "exceptions", None)
    if not isinstance(nested, tuple):
        return False
    return any(isinstance(item, BaseException) and _keyboard_interrupt_in(item) for item in nested)


def _reraise_without_token(exc: BaseException) -> NoReturn:
    """Re-raise a token-free interrupt. Context and cause do not keep the original.

    A no-arg constructor that embeds the token is a boundary. ``type(exc)()``
    would rebuild that message, and this helper does not scan it.
    """
    if isinstance(exc, SystemExit):
        status = exc.code
        if type(status) is not int or status == 0:
            status = 1
        blank: BaseException = SystemExit(status)
    else:
        try:
            blank = type(exc)()
        except Exception:
            if _keyboard_interrupt_in(exc):
                blank = KeyboardInterrupt()
            elif isinstance(exc, GeneratorExit):
                blank = GeneratorExit()
            else:
                blank = BaseException()
    try:
        raise blank from None
    except BaseException as surfaced:
        surfaced.__context__ = None
        surfaced.__cause__ = None
        surfaced.__suppress_context__ = True
        raise


def command_notion_connect(arguments: object) -> int:
    """Check the token shape and the fake probe. Never print the token."""
    prepared = _require_token()
    if isinstance(prepared, int):
        return prepared
    try:
        workspace = _probe(arguments).connect(prepared)
    except Exception:
        return _fail("notion api error", EXIT_API)
    except BaseException as exc:
        _reraise_without_token(exc)
    if _bad_workspace(workspace, prepared):
        return _fail("notion api error", EXIT_API)
    LOGGER.info("notion connect ok")
    _emit(
        {
            "command": "connect",
            "connected": True,
            "mode": "fake",
            "workspace": workspace,
        }
    )
    return EXIT_OK


def command_notion_status(arguments: object) -> int:
    """Report that a well-shaped token is configured. Never print the token."""
    del arguments
    prepared = _require_token()
    if isinstance(prepared, int):
        return prepared
    LOGGER.info("notion status ok")
    _emit(
        {
            "command": "status",
            "configured": True,
            "mode": "fake",
            "token_shape": "valid",
        }
    )
    return EXIT_OK


def command_notion_test(arguments: object) -> int:
    """Run the sandbox steps on the fake probe. Never print the token."""
    prepared = _require_token()
    if isinstance(prepared, int):
        return prepared
    try:
        steps = _probe(arguments).run_sandbox(prepared)
    except Exception:
        return _fail("notion api error", EXIT_API)
    except BaseException as exc:
        _reraise_without_token(exc)
    if _bad_steps(steps):
        return _fail("notion api error", EXIT_API)
    LOGGER.info("notion test ok")
    _emit({"command": "test", "mode": "fake", "steps": list(SANDBOX_STEPS)})
    return EXIT_OK
