"""Write a bounded, metadata-only resume checkpoint for agent sessions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

MAX_CHECKPOINT_BYTES = 8192


def _git(repo: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ("git", *arguments),
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str | None) -> str | None:
    return None if value is None else _sha256_bytes(value.encode("utf-8"))


def _file_sha256(path: Path | None) -> str | None:
    if path is None:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_checkpoint(arguments: argparse.Namespace) -> dict[str, object]:
    repo = arguments.repo.resolve()
    dirty_status = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    dirty_entries = [
        entry for entry in dirty_status.split(b"\0") if len(entry) >= 3 and entry[2:3] == b" "
    ]
    branch_result = subprocess.run(
        ("git", "symbolic-ref", "--quiet", "--short", "HEAD"),
        cwd=repo,
        check=False,
        capture_output=True,
    )
    branch = branch_result.stdout.decode().strip() or "DETACHED"
    head = _git(repo, "rev-parse", "HEAD").decode().strip()
    checkpoint: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "active_worktree": str(repo),
        "branch": branch,
        "head": head,
        "dirty_path_count": len(dirty_entries),
        "dirty_paths_sha256": _sha256_bytes(dirty_status),
        "active_session": arguments.session,
        "active_gate": arguments.gate,
        "candidate_manifest_sha256": _file_sha256(arguments.candidate_manifest),
        "running_command_sha256": _sha256_text(arguments.running_command),
        "next_command_sha256": _sha256_text(arguments.next_command),
    }
    return checkpoint


def write_atomic(path: Path, payload: bytes) -> None:
    if len(payload) > MAX_CHECKPOINT_BYTES:
        raise ValueError(f"checkpoint exceeds {MAX_CHECKPOINT_BYTES} bytes")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path(".omx/state/resume-checkpoint.json"))
    parser.add_argument("--session")
    parser.add_argument("--gate")
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--running-command")
    parser.add_argument("--next-command")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    checkpoint = build_checkpoint(arguments)
    payload = (json.dumps(checkpoint, sort_keys=True, separators=(",", ":")) + "\n").encode()
    write_atomic(arguments.output, payload)
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
