"""The prompt-integrity review is a standing gate, not a convention (D-0026)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
PROCEDURE = ROOT / "docs/PROMPT_INTEGRITY_REVIEW.md"
REVIEWS = ROOT / "docs/control/reviews"
STATE = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
WORKBOOK = ROOT / "hands-off-money-machine-full-implementation-workbook.md"
PROMPTS = ROOT / "prompts" / "implementation"
FIRST_GOVERNED_SESSION = 2
"""Sessions 00 and 01 closed before D-0026; the gate is not retroactive."""

RECORD_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}-session-(\d{2})-prompt-integrity\.md$")


def load_state() -> dict[str, object]:
    return json.loads(STATE.read_text(encoding="utf-8"))


def session_prompt(session: int) -> Path:
    matches = sorted(PROMPTS.glob(f"*_SESSION_{session:02d}_*.md"))
    assert len(matches) == 1, f"session {session:02d} must name exactly one prompt"
    return matches[0]


def recorded_sessions() -> dict[int, Path]:
    if not REVIEWS.is_dir():
        return {}
    records: dict[int, Path] = {}
    for path in REVIEWS.iterdir():
        match = RECORD_PATTERN.match(path.name)
        if match is not None:
            records[int(match.group(1))] = path
    return records


def governed_sessions() -> list[int]:
    state = load_state()
    completed = [int(item) for item in state["completed_sessions"]]  # type: ignore[union-attr]
    active = int(state["current_session"])  # type: ignore[arg-type]
    return sorted({*completed, active} - set(range(FIRST_GOVERNED_SESSION)))


def test_the_standing_instruction_is_published_and_referenced() -> None:
    procedure = PROCEDURE.read_text(encoding="utf-8")
    for requirement in (
        "adversarial review",
        "corrective addendum",
        "prompt-integrity",
        "SHA-256",
    ):
        assert requirement in procedure

    for source in (ROOT / "AGENTS.md", ROOT / "CLAUDE.md", ROOT / "docs/DEVELOPMENT-GOVERNANCE.md"):
        assert "docs/PROMPT_INTEGRITY_REVIEW.md" in source.read_text(encoding="utf-8"), source.name


def test_every_governed_session_has_a_prompt_integrity_record() -> None:
    records = recorded_sessions()
    missing = [session for session in governed_sessions() if session not in records]
    assert not missing, (
        "each session from "
        f"{FIRST_GOVERNED_SESSION:02d} onward must record a prompt-integrity review before "
        f"execution; missing: {missing}"
    )


def test_each_record_verifies_its_prompt_hash_and_states_an_addendum() -> None:
    workbook = WORKBOOK.read_text(encoding="utf-8")
    for session, path in sorted(recorded_sessions().items()):
        record = path.read_text(encoding="utf-8")
        prompt = session_prompt(session)
        digest = hashlib.sha256(prompt.read_bytes()).hexdigest()

        assert prompt.name in record, path.name
        assert digest in record, f"{path.name} must record the verified prompt hash"
        assert digest in workbook, f"{prompt.name} does not match the workbook appendix hash"
        assert "Corrective addendum" in record, f"{path.name} must carry the corrective addendum"


def test_prompt_files_are_never_amended_in_place() -> None:
    """Amendments live in the review record; the extracted prompts stay byte-identical."""
    for prompt in sorted(PROMPTS.glob("*_SESSION_*.md")):
        digest = hashlib.sha256(prompt.read_bytes()).hexdigest()
        assert digest in WORKBOOK.read_text(encoding="utf-8"), prompt.name
