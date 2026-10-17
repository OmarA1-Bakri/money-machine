"""Close Session 15 without a successor session.

There is no session 16 prompt. ``next_session`` stays 15. The status is
``complete``. A release subject, a version tag, and the exit string are
not this closure.
"""

from __future__ import annotations

from dataclasses import dataclass

_PROMPT = "18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md"
_RELEASE_SUBJECT = "chore(release): commission hands-off money machine"
_TAG = "v1.0.0"
_EXIT_STRING = "HANDS_OFF_MONEY_MACHINE_COMMISSIONED"


class ClosureRefusal(ValueError):
    """The candidate advances a missing session or claims a release."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TerminalClosure:
    """Session 15 is complete. No release is tagged."""

    session: int
    status: str
    next_session: int
    release_tagged: bool
    exit_string_present: bool


def record_terminal_closure(
    *,
    status: str,
    next_session: int | None,
    next_prompt: str,
    closure_recorded: bool,
) -> TerminalClosure:
    """Accept only a complete Session 15 whose next session stays 15."""
    if status != "complete":
        raise ClosureRefusal("status")
    if next_session != 15:
        raise ClosureRefusal("next_session")
    if next_prompt != _PROMPT:
        raise ClosureRefusal("prompt")
    if closure_recorded is not True:
        raise ClosureRefusal("closure_key")
    return TerminalClosure(
        session=15,
        status="complete",
        next_session=15,
        release_tagged=False,
        exit_string_present=False,
    )


def refuse_release_claim(subject: str) -> None:
    """A release subject, a tag, or the exit string is not the closure commit."""
    if subject == _RELEASE_SUBJECT or _TAG in subject or _EXIT_STRING in subject:
        raise ClosureRefusal("release")
