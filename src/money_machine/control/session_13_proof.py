"""Earn the Session 13 implementation-matrix key.

The proof reads the matrix, refuses a live gap marked tested, and does not
open a socket. The other Session 13 keys stay unearned.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from money_machine.assets.implementation_matrix import (
    MatrixRefusal,
    MatrixStatus,
    build_matrix,
)

MATRIX_EVIDENCE_KEY = "implementation_matrix_recorded"
_CLOSURE_EVIDENCE_KEY = "evidence_closure_commit_recorded"
EARNED_EVIDENCE_KEYS = frozenset({MATRIX_EVIDENCE_KEY})
_SESSION_13_KEYS = frozenset(
    {
        MATRIX_EVIDENCE_KEY,
        "synthetic_paths_implemented",
        "failure_injection_implemented",
        "backup_restore_fixture_implemented",
        "control_files_and_checkpoint_current",
        _CLOSURE_EVIDENCE_KEY,
    }
)
_CONTROL_FILES = (
    Path("docs/control/IMPLEMENTATION_STATE.json"),
    Path("docs/control/IMPLEMENTATION_LOG.md"),
    Path("docs/control/DECISIONS.md"),
    Path("docs/control/TEST_EVIDENCE.md"),
    Path("docs/control/NEXT_SESSION.md"),
    Path("docs/control/SESSION_EVIDENCE.md"),
)
_CLOSURE_HEAD = "d81db61033561bdd40869ff1316f0c935c74cdf4"
_SESSION_13_PROMPT = "16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md"


class Session13ProofError(ValueError):
    """The Session 13 fixture did not earn its evidence key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def prove_session_13() -> frozenset[str]:
    """Return the earned Session 13 keys. A miss raises instead of returning them."""
    _prove_matrix()
    _prove_control_files()
    return EARNED_EVIDENCE_KEYS


def _prove_matrix() -> None:
    module = Path(__file__).resolve().parents[1] / "assets" / "implementation_matrix.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    folded = " ".join(imported)
    if any(token in folded for token in ("socket", "httpx", "urllib", "requests")):
        raise Session13ProofError("matrix_socket")
    try:
        rows = build_matrix()
    except MatrixRefusal as error:
        raise Session13ProofError(error.code) from error
    if not rows:
        raise Session13ProofError("matrix_empty")
    blocked = [
        row for row in rows if row.status is MatrixStatus.BLOCKED_BY_EXTERNAL_CREDENTIAL
    ]
    missing = [row for row in rows if row.status is MatrixStatus.MISSING]
    if not blocked or not missing:
        raise Session13ProofError("matrix_gap")
    if any(row.status is MatrixStatus.IMPLEMENTED_AND_TESTED for row in blocked):
        raise Session13ProofError("matrix_relabel")


def _prove_control_files() -> None:
    """The continuity files and the catalogue match the checked-in pointer."""
    root = Path(__file__).resolve().parents[3]
    for relative in _CONTROL_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise Session13ProofError("control_files")
    from money_machine.control.session_evidence import render_session_evidence

    catalogue = root / "docs/control/SESSION_EVIDENCE.md"
    if catalogue.read_text(encoding="utf-8") != render_session_evidence():
        raise Session13ProofError("control_checkpoint")
    decoded: object = json.loads(
        (root / "docs/control/IMPLEMENTATION_STATE.json").read_text(encoding="utf-8")
    )
    if not isinstance(decoded, dict):
        raise Session13ProofError("control_checkpoint")
    evidence = decoded.get("required_completion_evidence")
    recorded = set(evidence) if isinstance(evidence, dict) else set()
    values_are_bool = isinstance(evidence, dict) and all(
        isinstance(value, bool) for value in evidence.values()
    )
    if (
        decoded.get("current_session") != 13
        or decoded.get("session_status") != "incomplete"
        or decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or decoded.get("head_sha") != _CLOSURE_HEAD
        or recorded != set(_SESSION_13_KEYS)
        or not values_are_bool
        or not isinstance(evidence, dict)
        or len(evidence) != len(recorded)
        or decoded.get("next_session") != 13
        or decoded.get("completed_sessions") != list(range(13))
        or decoded.get("next_prompt") != _SESSION_13_PROMPT
        or evidence.get(_CLOSURE_EVIDENCE_KEY) is not False
    ):
        raise Session13ProofError("control_checkpoint")
