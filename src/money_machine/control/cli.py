"""Command-line interface for controlled state transitions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from money_machine.control.state import ControlStateError, apply_completion_transition


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="money-machine-control")
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply_completion = subparsers.add_parser(
        "apply-completion",
        help="validate and atomically apply a proposed Session 00 completion",
    )
    apply_completion.add_argument(
        "--state",
        type=Path,
        default=Path("docs/control/IMPLEMENTATION_STATE.json"),
        help="current implementation state (default: docs/control/IMPLEMENTATION_STATE.json)",
    )
    apply_completion.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="proposed completed state; this file is never modified",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the control-state command."""
    arguments = _parser().parse_args(argv)
    if arguments.command != "apply-completion":
        raise AssertionError("argparse accepted an unknown command")

    state_path: Path = arguments.state
    candidate_path: Path = arguments.candidate
    try:
        applied = apply_completion_transition(state_path, candidate_path)
    except ControlStateError as error:
        print(f"control state transition rejected: {error}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "applied": True,
                "session": applied["current_session"],
                "state_revision": applied["state_revision"],
                "state_path": str(state_path),
            },
            sort_keys=True,
        )
    )
    return 0
