"""Append one metadata-only agent task metric record."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
from datetime import UTC, datetime
from pathlib import Path

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
MAX_RECORD_BYTES = 4096


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be nonnegative")
    return parsed


def identifier(value: str) -> str:
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "identifier must be 1-128 characters using letters, digits, '.', '_', ':', '/', or '-'"
        )
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".omx/logs/task-metrics.jsonl"))
    parser.add_argument("--task-id", required=True, type=identifier)
    parser.add_argument("--status", required=True, choices=("complete", "blocked", "failed"))
    parser.add_argument("--model", type=identifier)
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high", "xhigh", "max", "ultra"),
    )
    parser.add_argument("--elapsed-seconds", type=float, required=True)
    parser.add_argument("--input-tokens", type=nonnegative_int)
    parser.add_argument("--output-tokens", type=nonnegative_int)
    for name in (
        "agent-turns",
        "repeated-file-reads",
        "failed-tool-calls",
        "redundant-tool-calls",
        "rework-commits",
        "total-commits",
        "focused-test-runs",
        "affected-test-runs",
        "full-test-runs",
        "review-cycles",
    ):
        parser.add_argument(f"--{name}", type=nonnegative_int, required=True)
    return parser.parse_args()


def build_record(arguments: argparse.Namespace) -> dict[str, object]:
    if arguments.elapsed_seconds < 0:
        raise ValueError("elapsed seconds must be nonnegative")
    tokens: dict[str, int] | None = None
    if arguments.input_tokens is not None or arguments.output_tokens is not None:
        if arguments.input_tokens is None or arguments.output_tokens is None:
            raise ValueError("input and output token counts must be supplied together")
        tokens = {
            "input": arguments.input_tokens,
            "output": arguments.output_tokens,
            "total": arguments.input_tokens + arguments.output_tokens,
        }
    rework_rate = (
        arguments.rework_commits / arguments.total_commits if arguments.total_commits else 0.0
    )
    return {
        "schema_version": 1,
        "recorded_at": datetime.now(UTC).isoformat(),
        "task_id": arguments.task_id,
        "status": arguments.status,
        "model": arguments.model,
        "reasoning_effort": arguments.reasoning_effort,
        "elapsed_seconds": arguments.elapsed_seconds,
        "tokens": tokens,
        "agent_turns": arguments.agent_turns,
        "repeated_file_reads": arguments.repeated_file_reads,
        "failed_tool_calls": arguments.failed_tool_calls,
        "redundant_tool_calls": arguments.redundant_tool_calls,
        "rework_commits": arguments.rework_commits,
        "total_commits": arguments.total_commits,
        "rework_rate": rework_rate,
        "test_runs": {
            "focused": arguments.focused_test_runs,
            "affected": arguments.affected_test_runs,
            "full": arguments.full_test_runs,
        },
        "review_cycles": arguments.review_cycles,
    }


def append_record(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(line) > MAX_RECORD_BYTES:
        raise ValueError(f"metric record exceeds {MAX_RECORD_BYTES} bytes")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as destination:
        if not stat.S_ISREG(os.fstat(destination.fileno()).st_mode):
            raise ValueError("metrics output must be a regular file")
        os.fchmod(destination.fileno(), 0o600)
        destination.write(line.decode("utf-8"))
        destination.flush()
        os.fsync(destination.fileno())


def main() -> int:
    arguments = parse_args()
    append_record(arguments.output, build_record(arguments))
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
