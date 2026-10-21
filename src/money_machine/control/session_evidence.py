"""Pinned completion evidence for sessions 00 through 15.

Sessions 00-06 closed with every contract key true. Session 07 closed under
D-0032 with every contract key false. Sessions 08-15 are not activated, so
none of their keys is recorded true. This module does not edit
``IMPLEMENTATION_STATE.json``.
"""

from __future__ import annotations

from dataclasses import dataclass

from money_machine.control.state import SESSION_EVIDENCE_KEYS, SESSION_PROMPTS


@dataclass(frozen=True, slots=True)
class ClosedSessionEvidence:
    """One completion snapshot. ``state_commit`` holds the state file."""

    session: int
    state_commit: str
    state_revision: int
    evidence_closure_commit_sha: str
    head_sha: str
    completed_sessions: tuple[int, ...]
    next_session: int
    all_keys_true: bool


@dataclass(frozen=True, slots=True)
class OpenSessionEvidence:
    """A session that has not been activated."""

    session: int
    fixture_paths: tuple[str, ...]
    gap: str


CLOSED_SESSION_EVIDENCE: tuple[ClosedSessionEvidence, ...] = (
    ClosedSessionEvidence(
        0,
        "ef4a2039d976285d295e429cebbfdd9951bd7bf4",
        10,
        "50350b9937ad97dabf4be3762a00638d62aaa5b9",
        "50350b9937ad97dabf4be3762a00638d62aaa5b9",
        (0,),
        1,
        True,
    ),
    ClosedSessionEvidence(
        1,
        "6a772eebb11f1bec3b73a1cb509d2408d93b0107",
        15,
        "15b5df45c3a535548fe24698a590fc16c5757829",
        "15b5df45c3a535548fe24698a590fc16c5757829",
        (0, 1),
        2,
        True,
    ),
    ClosedSessionEvidence(
        2,
        "37206532766d3ba0539902ba8cd434fb67c3d36a",
        19,
        "e75b31745beef8d0368e9a21c437176edafb46a2",
        "e75b31745beef8d0368e9a21c437176edafb46a2",
        (0, 1, 2),
        3,
        True,
    ),
    ClosedSessionEvidence(
        3,
        "92964d765f1a71a8f82ef54b75cd4e69c7ac7118",
        22,
        "d19b8847ecd818d20ee599c54b80e754d85e16e6",
        "d19b8847ecd818d20ee599c54b80e754d85e16e6",
        (0, 1, 2, 3),
        4,
        True,
    ),
    ClosedSessionEvidence(
        4,
        "79d48adb01cf831907313fa5fe859f2dacde6f03",
        28,
        "14da7fe6e7893e79d6993720ae9413343931bfb0",
        "14da7fe6e7893e79d6993720ae9413343931bfb0",
        (0, 1, 2, 3, 4),
        5,
        True,
    ),
    ClosedSessionEvidence(
        5,
        "5e87f3fa3a2ec39e775c7a5986b1abf10f1e418a",
        31,
        "9b791d45f9461030f09eda8a46838afc5447416c",
        "9b791d45f9461030f09eda8a46838afc5447416c",
        (0, 1, 2, 3, 4, 5),
        6,
        True,
    ),
    ClosedSessionEvidence(
        6,
        "ac6afcfb97c8b59fd0215083e89a1b37d292282b",
        48,
        "0f94d585f23d79e5ac18479f01e14f67cbaad332",
        "0f94d585f23d79e5ac18479f01e14f67cbaad332",
        (0, 1, 2, 3, 4, 5, 6),
        7,
        True,
    ),
    ClosedSessionEvidence(
        7,
        "00b952a83bffcec8d442468223d64dd9b2d3e6df",
        64,
        "0f94d585f23d79e5ac18479f01e14f67cbaad332",
        "b782751fdb1b255c436ff7f6fa655e6d783b1e8c",
        (0, 1, 2, 3, 4, 5, 6, 7),
        8,
        False,
    ),
)

OPEN_SESSION_EVIDENCE: tuple[OpenSessionEvidence, ...] = (
    OpenSessionEvidence(
        8,
        (
            "src/money_machine/agents/implementations/merchandising.py",
            "src/money_machine/domain/services/claim_validation.py",
            "src/money_machine/assets/design_tokens.py",
            "src/money_machine/assets/screenshots.py",
            "src/money_machine/assets/link_validation.py",
            "src/money_machine/assets/asset_lineage.py",
            "src/money_machine/integrations/storage/local.py",
        ),
        "Contract exists and is not installed. Fixture modules are not a true key.",
    ),
    OpenSessionEvidence(
        9,
        (
            "src/money_machine/assets/etsy_preflight.py",
            "src/money_machine/assets/publishing_ramp_decision.py",
            "src/money_machine/assets/mutation_receipt.py",
        ),
        "No evidence contract. Preflight, ramp, and receipt fixtures do not publish.",
    ),
    OpenSessionEvidence(
        10,
        (
            "src/money_machine/assets/metrics_fixture.py",
            "src/money_machine/assets/maturity_clock.py",
            "src/money_machine/assets/portfolio_eligibility.py",
            "src/money_machine/assets/closed_loop_store.py",
        ),
        "No evidence contract. The ledger does not run the scheduler or deactivate a listing.",
    ),
    OpenSessionEvidence(
        11,
        ("src/money_machine/assets/support_intake.py",),
        "No evidence contract. Intake is in memory and sends nothing. A16 stays DESIGNED.",
    ),
    OpenSessionEvidence(
        12,
        (),
        "No evidence contract and no session module. The operator console is not built.",
    ),
    OpenSessionEvidence(
        13,
        (),
        "No evidence contract and no session module. End-to-end hardening is not recorded.",
    ),
    OpenSessionEvidence(
        14,
        (),
        "No evidence contract and no session module. Production deployment is not recorded.",
    ),
    OpenSessionEvidence(
        15,
        (),
        "No evidence contract and no session module. Live commissioning is not recorded.",
    ),
)


def _keys(session: int) -> tuple[str, ...]:
    contract = SESSION_EVIDENCE_KEYS.get(session)
    if contract is None:
        return ()
    return tuple(sorted(contract))


def render_session_evidence() -> str:
    """Return the human index. Key order is alphabetical and stable."""
    lines = [
        "# Session evidence",
        "",
        "The historical Session 07 operator-close pointer was state revision 64.",
        "`IMPLEMENTATION_STATE.json` is the current pointer and is not edited by this index. "
        "D-0039 permits an audited recovery to reopen Session 07 at revision 65; "
        "historical close snapshots remain unchanged.",
        "Sessions 00-06 closed with every contract key true.",
        "Session 07 closed under D-0032 with every contract key false.",
        "Sessions 08-15 are not activated, so none of their keys is recorded true.",
        "",
    ]
    for record in CLOSED_SESSION_EVIDENCE:
        value = "true" if record.all_keys_true else "false"
        lines.extend(
            [
                f"## Session {record.session:02d}",
                "",
                f"Prompt: `{SESSION_PROMPTS[record.session]}`.",
                f"State commit: `{record.state_commit}`.",
                f"State revision: {record.state_revision}.",
                f"Status: complete. Next session: {record.next_session}.",
                f"Completed sessions: {list(record.completed_sessions)}.",
                f"Evidence closure commit: `{record.evidence_closure_commit_sha}`.",
                f"Head SHA: `{record.head_sha}`.",
                "",
                "| Key | Recorded |",
                "|---|---|",
            ]
        )
        for key in _keys(record.session):
            lines.append(f"| `{key}` | {value} |")
        if not record.all_keys_true:
            lines.extend(
                [
                    "",
                    "D-0032 keeps these twelve keys false.",
                    "The close is the operator gate. It is not `validate_completion_transition`.",
                    "Activation of Session 08 stays refused while any of these keys is false.",
                ]
            )
        lines.append("")
    lines.extend(
        [
            "## Sessions 08-15",
            "",
            "These sessions are not activated. A fixture path is code on the trunk.",
            "It is not a recorded evidence key.",
            "",
        ]
    )
    for record in OPEN_SESSION_EVIDENCE:
        contract = "defined, not installed" if record.session in SESSION_EVIDENCE_KEYS else "absent"
        lines.extend(
            [
                f"## Session {record.session:02d}",
                "",
                f"Prompt: `{SESSION_PROMPTS[record.session]}`.",
                "Status: not activated.",
                f"Evidence contract: {contract}.",
                record.gap,
                "",
            ]
        )
        if record.fixture_paths:
            lines.append("Fixture paths:")
            lines.append("")
            for path in record.fixture_paths:
                lines.append(f"- `{path}`")
            lines.append("")
        else:
            lines.append("Fixture paths: none.")
            lines.append("")
        if record.session in SESSION_EVIDENCE_KEYS:
            lines.append("| Key | Recorded |")
            lines.append("|---|---|")
            for key in _keys(record.session):
                lines.append(f"| `{key}` | not installed |")
            lines.append("")
    return "\n".join(lines)
