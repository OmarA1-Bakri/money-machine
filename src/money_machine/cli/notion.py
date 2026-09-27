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
from typing import Protocol

from money_machine.config.runtime import load_runtime_settings

LOGGER = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_BAD_TOKEN = 64
EXIT_API = 69
EXIT_MISSING = 78

_TOKEN_RE = re.compile(r"(?:secret_|ntn_)[A-Za-z0-9]{43,}")
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


def _leaks(value: object, token: str) -> bool:
    if isinstance(value, str):
        return value == "" or token in value
    if isinstance(value, tuple):
        return any(_leaks(item, token) for item in value)
    return True


def command_notion_connect(arguments: object) -> int:
    """Check the token shape and the fake probe. Never print the token."""
    prepared = _require_token()
    if isinstance(prepared, int):
        return prepared
    try:
        workspace = _probe(arguments).connect(prepared)
    except Exception:
        return _fail("notion api error", EXIT_API)
    if _leaks(workspace, prepared):
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
    if steps != SANDBOX_STEPS or _leaks(steps, prepared):
        return _fail("notion api error", EXIT_API)
    LOGGER.info("notion test ok")
    _emit({"command": "test", "mode": "fake", "steps": list(steps)})
    return EXIT_OK
