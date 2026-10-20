"""Pinned completion evidence for sessions 00 through 15.

Sessions 00-06 closed with every contract key true. Session 07's close
commit under D-0032 has every contract key false. D-0036 records the live
pointer separately. Sessions 08, 09, and 10 are complete. Session 10 is
revision 83 and every one of its keys is true (D-0055). Session 11 is
complete at revision 90. Every Session 11 key is true (D-0063). Session 12
is complete at revision 97. Every Session 12 key is true (D-0071).
Session 13 is complete at revision 104. Every Session 13 key is true
(D-0079). Session 14 is complete at revision 111. Every Session 14 key
is true (D-0087). Session 15 is complete at revision 119.
``deployed_state_checked``, ``provider_connections_fail_closed``,
``standing_authority_recorded``, ``linked_workflow_fixture``,
``acceptance_matrix_recorded``, ``control_files_and_checkpoint_current``,
and ``evidence_closure_commit_recorded`` are true (D-0090 through D-0096).
A live account is not connected. The exit string is not written.
This module does not edit ``IMPLEMENTATION_STATE.json``.
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
    """A session that is not complete. ``activated`` means its keys are installed."""

    session: int
    fixture_paths: tuple[str, ...]
    gap: str
    activated: bool = False
    true_keys: frozenset[str] = frozenset()


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
    ClosedSessionEvidence(
        8,
        "4a07fd69259a7265c5780fb584b2a89cacd9b258",
        69,
        "01b7dd84ef98442ff26a5239e8c7de742739d844",
        "01b7dd84ef98442ff26a5239e8c7de742739d844",
        (0, 1, 2, 3, 4, 5, 6, 7, 8),
        9,
        True,
    ),
    ClosedSessionEvidence(
        9,
        "379446ac8fefa71a4752eb32cc15fd41471060e9",
        76,
        "cfb36462994ecba833f31ba869f2aba627f6060d",
        "cfb36462994ecba833f31ba869f2aba627f6060d",
        (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
        10,
        True,
    ),
    ClosedSessionEvidence(
        10,
        "b612dffe87e63e46ea88c74e0f858dd72e8a5b36",
        83,
        "f16c7ed0598daf3f4627955b52585f253ae1b918",
        "f16c7ed0598daf3f4627955b52585f253ae1b918",
        (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
        11,
        True,
    ),
)

OPEN_SESSION_EVIDENCE: tuple[OpenSessionEvidence, ...] = (
    OpenSessionEvidence(
        11,
        ("src/money_machine/assets/support_intake.py",),
        (
            "Every Session 11 key is earned. Session 12 is complete. Session 13 "
            "is complete. Session 14 is incomplete. The target, the package, and "
            "the release plan are recorded. A live deploy is not recorded. "
            "A16 stays DESIGNED."
        ),
        True,
        frozenset(
            {
                "control_files_and_checkpoint_current",
                "draft_reply_implemented",
                "evidence_closure_commit_recorded",
                "incident_routing_implemented",
                "repair_resolution_implemented",
                "support_intake_implemented",
            }
        ),
    ),
    OpenSessionEvidence(
        12,
        (
            "src/money_machine/assets/operator_console.py",
            "src/money_machine/assets/operator_views.py",
            "src/money_machine/assets/telemetry_redaction.py",
            "src/money_machine/assets/operator_actions.py",
        ),
        (
            "Every Session 12 key is earned. Session 13 is complete. Session 14 "
            "is incomplete. The target, the package, and the release plan are "
            "recorded. A live deploy is not recorded. Exit 78 stays HELD."
        ),
        True,
        frozenset(
            {
                "console_read_model_implemented",
                "control_files_and_checkpoint_current",
                "evidence_closure_commit_recorded",
                "exception_views_implemented",
                "operator_actions_fail_closed",
                "telemetry_redaction_implemented",
            }
        ),
    ),
    OpenSessionEvidence(
        13,
        (
            "src/money_machine/assets/implementation_matrix.py",
            "src/money_machine/assets/synthetic_paths.py",
            "src/money_machine/assets/failure_injection.py",
            "src/money_machine/assets/backup_restore.py",
        ),
        (
            "Every Session 13 key is earned. Session 14 is incomplete. The target, "
            "the package, and the release plan are recorded. A live deploy is not "
            "recorded. Exit 78 stays HELD."
        ),
        True,
        frozenset(
            {
                "implementation_matrix_recorded",
                "synthetic_paths_implemented",
                "failure_injection_implemented",
                "backup_restore_fixture_implemented",
                "control_files_and_checkpoint_current",
                "evidence_closure_commit_recorded",
            }
        ),
    ),
    OpenSessionEvidence(
        14,
        (
            "src/money_machine/deploy/target.py",
            "src/money_machine/deploy/packaging.py",
            "src/money_machine/deploy/release.py",
            "src/money_machine/deploy/controls.py",
            "src/money_machine/deploy/checkpoint.py",
        ),
        ("Session 15 is not activated. A live deploy is not recorded."),
        True,
        frozenset(
            {
                "deployment_target_recorded",
                "production_packaging_defined",
                "release_rollback_implemented",
                "service_controls_fail_closed",
                "control_files_and_checkpoint_current",
                "evidence_closure_commit_recorded",
            }
        ),
    ),
    OpenSessionEvidence(
        15,
        (
            "src/money_machine/config/settings.py",
            "src/money_machine/integrations/etsy/fixture_adapter.py",
            "src/money_machine/integrations/notion/fixture_adapter.py",
            "src/money_machine/assets/acceptance_matrix.py",
            "src/money_machine/deploy/closure.py",
            "src/money_machine/deploy/continuity.py",
            "src/money_machine/assets/linked_workflow.py",
            "src/money_machine/config/standing_authority.py",
            "src/money_machine/deploy/checkpoint.py",
            "src/money_machine/deploy/deployed_state.py",
            "src/money_machine/deploy/repository_identity.py",
            "src/money_machine/deploy/bootstrap.py",
            "src/money_machine/deploy/production_compose.py",
            "src/money_machine/deploy/prompt_pack.py",
            "src/money_machine/deploy/source_exclusion.py",
            "src/money_machine/integrations/provider_connections.py",
        ),
        "The exit string is not written. A live account is not connected.",
        True,
        frozenset(
            {
                "acceptance_matrix_recorded",
                "control_files_and_checkpoint_current",
                "deployed_state_checked",
                "evidence_closure_commit_recorded",
                "linked_workflow_fixture",
                "provider_connections_fail_closed",
                "standing_authority_recorded",
            }
        ),
    ),
)


def _keys(session: int) -> tuple[str, ...]:
    contract = SESSION_EVIDENCE_KEYS.get(session)
    if contract is None:
        return ()
    return tuple(sorted(contract))


def _open_status(record: OpenSessionEvidence) -> str:
    """An open row is complete only when every installed key is true."""
    contract = SESSION_EVIDENCE_KEYS.get(record.session)
    if not record.activated:
        return "Status: not activated."
    if contract is not None and record.true_keys == frozenset(contract):
        return "Status: complete."
    return "Status: incomplete."


def render_session_evidence() -> str:
    """Return the human index. Key order is alphabetical and stable."""
    lines = [
        "# Session evidence",
        "",
        "The checked-in pointer is Session 15 at state revision 119.",
        "`current_session` is 15. `session_status` is complete.",
        "All seven Session 15 keys are true. A live account is not connected.",
        "Session 10 is complete and every one of its keys is true.",
        "Session 09 is complete and every one of its keys is true.",
        "Session 08 is complete and every one of its keys is true.",
        "Sessions 00-06 closed with every contract key true.",
        "Session 07's close commit keeps every contract key false under D-0032.",
        "D-0036 recorded the twelve Session 07 keys true. The closure commit is",
        "`5a48a4c9c04c74019e382a62b2c3c0abfd5b9cfb`. `head_sha` stays the close tip.",
        "Session 10 is complete. Every key is true.",
        "Session 11 is complete. Every key is true.",
        "Session 12 is complete. Every key is true.",
        "Session 13 is complete. Every key is true.",
        "Session 14 is complete. Session 15 is complete.",
        "All seven Session 15 keys are true. A live account is not connected.",
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
                    "D-0032 keeps these twelve keys false on this close commit.",
                    "The close is the operator gate. It is not `validate_completion_transition`.",
                    "D-0036 records the live keys later. This table is the close commit.",
                ]
            )
        lines.append("")
    lines.extend(
        [
            "## Sessions 11-15",
            "",
            "Session 10 is complete. Every key is true.",
            "Session 11 is complete. Every key is true.",
            "Session 12 is complete. Every key is true.",
            "Session 13 is complete. Every key is true.",
            "Session 14 is complete. Session 15 is complete.",
            "All seven Session 15 keys are true. A live account is not connected.",
            "A fixture path is code on the trunk. It is not, by itself, a true evidence key.",
            "",
        ]
    )
    for record in OPEN_SESSION_EVIDENCE:
        lines.extend(
            [
                f"## Session {record.session:02d}",
                "",
                f"Prompt: `{SESSION_PROMPTS[record.session]}`.",
                _open_status(record),
                (
                    "Evidence contract: installed."
                    if record.activated
                    else (
                        "Evidence contract: installed, not activated."
                        if record.session in SESSION_EVIDENCE_KEYS
                        else "Evidence contract: absent."
                    )
                ),
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
                if key in record.true_keys:
                    recorded = "true"
                elif record.activated:
                    recorded = "false"
                else:
                    recorded = "not installed"
                lines.append(f"| `{key}` | {recorded} |")
            lines.append("")
    return "\n".join(lines)
