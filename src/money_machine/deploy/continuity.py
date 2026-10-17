"""Read the continuity files and refuse a commissioning claim.

The six control files and the four deploy modules must match the pointer.
The closure key stays false. A handover page does not earn the key.
No socket is opened.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from money_machine.deploy.checkpoint import (
    CONTROL_FILES,
    CheckpointRefusal,
    inspect_deployment_checkpoint,
)

_STAMPED = (
    Path("docs/control/IMPLEMENTATION_LOG.md"),
    Path("docs/control/DECISIONS.md"),
    Path("docs/control/TEST_EVIDENCE.md"),
)
_NARRATIVE = (
    *_STAMPED,
    Path("docs/control/NEXT_SESSION.md"),
)
_EXIT_STRINGS = (
    "HANDS_OFF_MONEY_MACHINE_COMMISSIONED",
    "SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE",
)
_CLOSURE_KEY = "evidence_closure_commit_recorded"


class ContinuityRefusal(ValueError):
    """The continuity files are stale, closed, or contain the exit string."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ControlCheckpoint:
    """The files that were read. The closure key is not among the true keys."""

    revision: int
    updated_at: str
    head_sha: str
    true_keys: tuple[str, ...]
    closure_recorded: bool
    exit_string_present: bool
    files_read: tuple[str, ...]


def record_control_checkpoint(
    root: Path | None = None,
    *,
    expected_revision: int,
    expected_updated_at: str,
    expected_true_keys: frozenset[str],
    closure_head: str,
) -> ControlCheckpoint:
    """Read the continuity files. A closure key or a handover page is refused."""
    if _CLOSURE_KEY in expected_true_keys:
        raise ContinuityRefusal("closure")
    repo = Path(__file__).resolve().parents[3] if root is None else root
    try:
        checkpoint = inspect_deployment_checkpoint(
            repo,
            expected_revision=expected_revision,
            expected_updated_at=expected_updated_at,
            expected_true_keys=expected_true_keys,
            closure_head=closure_head,
        )
    except CheckpointRefusal as error:
        raise ContinuityRefusal(error.code) from error
    if checkpoint.closure_recorded:
        raise ContinuityRefusal("closure")
    if checkpoint.exit_string_present:
        raise ContinuityRefusal("exit_string")
    narratives_cite(repo, expected_revision, expected_updated_at)
    return ControlCheckpoint(
        revision=checkpoint.revision,
        updated_at=checkpoint.updated_at,
        head_sha=checkpoint.head_sha,
        true_keys=checkpoint.true_keys,
        closure_recorded=False,
        exit_string_present=False,
        files_read=tuple(path.as_posix() for path in CONTROL_FILES),
    )


def narratives_cite(root: Path, revision: int, updated_at: str) -> None:
    """Each narrative file cites the pointer and does not claim commissioning."""
    for relative in _NARRATIVE:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise ContinuityRefusal("control_files")
        text = path.read_text(encoding="utf-8")
        if str(revision) not in text or (relative in _STAMPED and updated_at not in text):
            raise ContinuityRefusal("stale")
        for line in text.splitlines():
            if any(token in line for token in _EXIT_STRINGS) and "not" not in line.casefold():
                raise ContinuityRefusal("exit_string")


def refuse_commissioning_page(page: str) -> None:
    """A handover page does not earn the continuity key."""
    del page
    raise ContinuityRefusal("page")
