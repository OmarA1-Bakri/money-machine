"""Inspect the deployment checkpoint against the continuity files.

The catalogue must match the renderer. A completed Session 14 records the
closure key. A completed Session 15 records it and stays session 15. The
exit string is not a current checkpoint. No socket is opened.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CONTROL_FILES = (
    Path("docs/control/IMPLEMENTATION_STATE.json"),
    Path("docs/control/IMPLEMENTATION_LOG.md"),
    Path("docs/control/DECISIONS.md"),
    Path("docs/control/TEST_EVIDENCE.md"),
    Path("docs/control/NEXT_SESSION.md"),
    Path("docs/control/SESSION_EVIDENCE.md"),
)
DEPLOY_MODULES = (
    Path("src/money_machine/deploy/target.py"),
    Path("src/money_machine/deploy/packaging.py"),
    Path("src/money_machine/deploy/release.py"),
    Path("src/money_machine/deploy/controls.py"),
)
_CLOSURE_KEY = "evidence_closure_commit_recorded"
_EXIT_STRING = "SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE"
_BOOTSTRAP = "1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d"
_PROMPT = "17_SESSION_14_DEPLOYMENT.md"
_CLOSED_PROMPT = "18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md"
_WORKER = Path("src/money_machine/orchestration/worker.py")
_DECISION = "D-0085"


class CheckpointRefusal(ValueError):
    """The continuity files do not match the deployment checkpoint."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DeploymentCheckpoint:
    """The current deployment pointer. Session 15 starts with every key false."""

    revision: int
    updated_at: str
    head_sha: str
    true_keys: tuple[str, ...]
    catalogue_matches: bool
    closure_recorded: bool
    exit_string_present: bool


def inspect_deployment_checkpoint(
    root: Path | None = None,
    *,
    expected_revision: int,
    expected_updated_at: str,
    expected_true_keys: frozenset[str],
    closure_head: str,
) -> DeploymentCheckpoint:
    """Read the six continuity files and the four deploy modules.

    ``expected_true_keys`` includes the closure key only when Session 14 is
    complete. An empty set matches activated Session 15, whose keys are
    false. The state file must not contain the exit string. A decision
    line that names it must also say it is not written.
    """
    closed = _CLOSURE_KEY in expected_true_keys
    repo = Path(__file__).resolve().parents[3] if root is None else root
    _require_files(repo)
    _refuse_exit_string(repo)
    if "Exit 78 held" not in (repo / _WORKER).read_text(encoding="utf-8"):
        raise CheckpointRefusal("exit_78")
    if _DECISION not in (repo / "docs/control/DECISIONS.md").read_text(encoding="utf-8"):
        raise CheckpointRefusal("decision")
    catalogue_matches = _catalogue_matches(repo)
    state = _state(repo)
    evidence = _evidence(state)
    true_keys = tuple(sorted(key for key, value in evidence.items() if value is True))
    if set(true_keys) != set(expected_true_keys):
        raise CheckpointRefusal("keys")
    if evidence[_CLOSURE_KEY] is not closed:
        raise CheckpointRefusal("closure")
    if not _pointer_matches(
        state,
        expected_revision,
        expected_updated_at,
        closure_head,
        closed=closed,
    ):
        raise CheckpointRefusal("pointer")
    return DeploymentCheckpoint(
        revision=expected_revision,
        updated_at=expected_updated_at,
        head_sha=closure_head,
        true_keys=true_keys,
        catalogue_matches=catalogue_matches,
        closure_recorded=closed,
        exit_string_present=False,
    )


def _require_files(repo: Path) -> None:
    for relative in CONTROL_FILES + DEPLOY_MODULES:
        path = repo / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise CheckpointRefusal("control_files")


def _refuse_exit_string(repo: Path) -> None:
    """Refuse a completion claim. A decision that names the string as unwritten is not one."""
    state_text = (repo / "docs/control/IMPLEMENTATION_STATE.json").read_text(encoding="utf-8")
    if _EXIT_STRING in state_text:
        raise CheckpointRefusal("exit_string")
    decisions = (repo / "docs/control/DECISIONS.md").read_text(encoding="utf-8")
    for line in decisions.splitlines():
        if _EXIT_STRING in line and "not" not in line.casefold():
            raise CheckpointRefusal("exit_string")


def _catalogue_matches(repo: Path) -> bool:
    # Imported here because session_evidence imports state, and state imports the proof.
    from money_machine.control.session_evidence import render_session_evidence

    catalogue = repo / "docs/control/SESSION_EVIDENCE.md"
    if catalogue.read_text(encoding="utf-8") != render_session_evidence():
        raise CheckpointRefusal("catalogue")
    return True


def _state(repo: Path) -> dict[str, object]:
    decoded: object = json.loads(
        (repo / "docs/control/IMPLEMENTATION_STATE.json").read_text(encoding="utf-8")
    )
    if not isinstance(decoded, dict):
        raise CheckpointRefusal("pointer")
    return decoded


def _evidence(state: dict[str, object]) -> dict[str, bool]:
    evidence = state.get("required_completion_evidence")
    if not isinstance(evidence, dict):
        raise CheckpointRefusal("keys")
    parsed: dict[str, bool] = {}
    for key, value in evidence.items():
        if not isinstance(key, str) or not isinstance(value, bool):
            raise CheckpointRefusal("keys")
        parsed[key] = value
    return parsed


def _pointer_matches(
    state: dict[str, object],
    expected_revision: int,
    expected_updated_at: str,
    closure_head: str,
    *,
    closed: bool,
) -> bool:
    completed = state.get("completed_sessions")
    commissioned = state.get("commissioned_agents")
    session = state.get("current_session")
    if session == 15 and closed:
        expected_session = 15
        status = "complete"
        nxt = 15
        prompt = _CLOSED_PROMPT
        finished = list(range(16))
    elif closed:
        expected_session = 14
        status = "complete"
        nxt = 15
        prompt = _CLOSED_PROMPT
        finished = list(range(15))
    elif session == 15:
        expected_session = 15
        status = "incomplete"
        nxt = 15
        prompt = _CLOSED_PROMPT
        finished = list(range(15))
    else:
        expected_session = 14
        status = "incomplete"
        nxt = 14
        prompt = _PROMPT
        finished = list(range(14))
    return (
        session == expected_session
        and state.get("session_status") == status
        and state.get("state_revision") == expected_revision
        and state.get("updated_at") == expected_updated_at
        and state.get("head_sha") == closure_head
        and state.get("evidence_closure_commit_sha") == closure_head
        and state.get("last_verified_commit") == _BOOTSTRAP
        and state.get("next_session") == nxt
        and state.get("next_prompt") == prompt
        and completed == finished
        and commissioned == []
    )
