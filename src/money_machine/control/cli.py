"""Command-line interface for controlled state transitions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from money_machine.control.recovery import recover_session_seven
from money_machine.control.state import (
    ControlStateError,
    apply_activation_transition,
    apply_completion_transition,
)

_COMMANDS = {
    "apply-completion": (
        apply_completion_transition,
        "validate and atomically apply a proposed session completion",
        "proposed completed state; this file is never modified",
    ),
    "activate": (
        apply_activation_transition,
        "validate and atomically activate the recorded next session",
        "proposed activated state; this file is never modified",
    ),
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="money-machine-control")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text, candidate_help) in _COMMANDS.items():
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument(
            "--state",
            type=Path,
            default=Path("docs/control/IMPLEMENTATION_STATE.json"),
            help="current implementation state (default: docs/control/IMPLEMENTATION_STATE.json)",
        )
        command.add_argument(
            "--candidate",
            type=Path,
            required=True,
            help=candidate_help,
        )
    recovery = subparsers.add_parser(
        "recover-session-seven", help="preview audited D-0039 recovery"
    )
    recovery.add_argument(
        "--state", type=Path, default=Path("docs/control/IMPLEMENTATION_STATE.json")
    )
    recovery.add_argument("--repo-root", type=Path, default=Path.cwd())
    recovery.add_argument("--expected-before-sha")
    recovery.add_argument("--expected-head")
    recovery.add_argument("--apply", action="store_true", help="apply the hash-bound recovery")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the control-state command."""
    arguments = _parser().parse_args(argv)
    command: str = arguments.command
    if command == "recover-session-seven":
        try:
            result = recover_session_seven(
                arguments.state,
                repo_root=arguments.repo_root,
                expected_before_sha=arguments.expected_before_sha,
                expected_head=arguments.expected_head,
                apply=arguments.apply,
            )
        except ControlStateError as error:
            print(f"control state transition rejected: {error}", file=sys.stderr)
            return 2
        print(json.dumps(result, sort_keys=True))
        return 0
    if command not in _COMMANDS:
        raise AssertionError("argparse accepted an unknown command")
    transition = _COMMANDS[command][0]

    state_path: Path = arguments.state
    candidate_path: Path = arguments.candidate
    try:
        applied = transition(state_path, candidate_path)
    except ControlStateError as error:
        print(f"control state transition rejected: {error}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "applied": True,
                "command": command,
                "session": applied["current_session"],
                "state_revision": applied["state_revision"],
                "state_path": str(state_path),
            },
            sort_keys=True,
        )
    )
    return 0
