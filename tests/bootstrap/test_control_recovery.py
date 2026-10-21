"""Audited recovery exercises use disposable Git worktrees, never canonical state."""

from __future__ import annotations

# Fault injection exercises the shared atomic writer without changing its implementation.
# pyright: reportPrivateUsage=false
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from money_machine.control import recovery
from money_machine.control.state import ControlStateError

ROOT = Path(__file__).parents[2]
STATE = Path("docs/control/IMPLEMENTATION_STATE.json")


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    target = tmp_path / "repo"
    subprocess.run(
        ["git", "clone", "--shared", "--no-checkout", str(ROOT), str(target)],
        check=True,
        capture_output=True,
    )
    git(target, "sparse-checkout", "init", "--cone")
    git(target, "sparse-checkout", "set", "docs/control")
    git(target, "checkout", "-b", "build/full-automation", "HEAD")
    git(target, "config", "user.name", "Recovery Test")
    git(target, "config", "user.email", "recovery@example.invalid")
    return target


def run(repo: Path, *, apply: bool = False) -> dict[str, object]:
    return recovery.recover_session_seven(
        repo / STATE,
        repo_root=repo,
        expected_before_sha=recovery.LEGACY_STATE_SHA256,
        expected_head=git(repo, "rev-parse", "HEAD"),
        apply=apply,
    )


def test_dry_run_preserves_exact_state_and_creates_no_receipt(repo: Path) -> None:
    before = (repo / STATE).read_bytes()
    result = run(repo)
    assert result["applied"] is False
    candidate = result["candidate"]
    assert isinstance(candidate, dict)
    assert candidate["state_revision"] == 65
    assert candidate["session_status"] == "incomplete"
    assert candidate["next_session"] == 7
    assert candidate["completed_sessions"] == list(range(7))
    assert candidate["repo_root"] == str(repo)
    assert candidate["head_sha"] == candidate["evidence_closure_commit_sha"]
    assert (
        candidate["required_completion_evidence"]
        == json.loads(before)["required_completion_evidence"]
    )
    assert candidate["commissioned_agents"] == []
    assert (repo / STATE).read_bytes() == before
    assert not (repo / ".git/control-recovery").exists()


def test_apply_preserves_provenance_and_is_idempotent(repo: Path) -> None:
    before = (repo / STATE).read_bytes()
    result = run(repo, apply=True)
    assert result["applied"] is True
    after = (repo / STATE).read_bytes()
    candidate = json.loads(after)
    assert candidate["notes"] == json.loads(before)["notes"]
    intent = json.loads(Path(str(result["receipt_path"])).read_text())
    assert intent["before_sha256"] == hashlib.sha256(before).hexdigest()
    assert intent["operator_close"]["head_sha"] == json.loads(before)["head_sha"]
    assert run(repo, apply=True)["reconciled"] is True
    assert (repo / STATE).read_bytes() == after


def test_lost_final_receipt_replays_without_double_increment(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = recovery._atomic_write_json

    def fail_final(path: Path, document: dict[str, object]) -> None:
        if path.name.endswith(".applied.json"):
            raise OSError("injected crash after state replacement")
        original(path, document)

    with monkeypatch.context() as patch:
        patch.setattr(recovery, "_atomic_write_json", fail_final)
        with pytest.raises(ControlStateError, match="recovery write"):
            run(repo, apply=True)
    before_replay = (repo / STATE).read_bytes()
    assert json.loads(before_replay)["state_revision"] == 65
    assert run(repo, apply=True)["reconciled"] is True
    assert (repo / STATE).read_bytes() == before_replay


@pytest.mark.parametrize("change", ["evidence", "commission", "revision", "bytes"])
def test_modified_legacy_state_is_refused(repo: Path, change: str) -> None:
    path = repo / STATE
    document = json.loads(path.read_text())
    if change == "evidence":
        document["required_completion_evidence"]["shared_databases_built"] = True
    elif change == "commission":
        document["commissioned_agents"] = ["A08"]
    elif change == "revision":
        document["state_revision"] = 66
    else:
        path.write_bytes(path.read_bytes() + b" ")
    if change != "bytes":
        path.write_text(json.dumps(document))
    with pytest.raises(ControlStateError):
        run(repo, apply=True)


def test_apply_requires_explicit_hashes(repo: Path) -> None:
    with pytest.raises(ControlStateError, match="expected"):
        recovery.recover_session_seven(repo / STATE, repo_root=repo, apply=True)


def test_stale_head_and_wrong_before_hash_refused(repo: Path) -> None:
    for head, before in [
        ("0" * 40, recovery.LEGACY_STATE_SHA256),
        (git(repo, "rev-parse", "HEAD"), "0" * 64),
    ]:
        with pytest.raises(ControlStateError):
            recovery.recover_session_seven(
                repo / STATE,
                repo_root=repo,
                apply=True,
                expected_head=head,
                expected_before_sha=before,
            )


def test_dirty_authority_and_untracked_file_refused(repo: Path) -> None:
    authority = repo / "docs/control/DECISIONS.md"
    authority.write_text(authority.read_text() + "\nmodified\n")
    with pytest.raises(ControlStateError):
        run(repo, apply=True)
    git(repo, "restore", "docs/control/DECISIONS.md")
    (repo / "unexpected.txt").write_text("unexpected")
    with pytest.raises(ControlStateError):
        run(repo, apply=True)


def test_wrong_branch_and_foreign_root_refused(repo: Path, tmp_path: Path) -> None:
    git(repo, "checkout", "-b", "other")
    with pytest.raises(ControlStateError, match="branch"):
        run(repo, apply=True)
    with pytest.raises(ControlStateError):
        recovery.recover_session_seven(repo / STATE, repo_root=tmp_path)


def test_state_and_parent_symlinks_refused(repo: Path, tmp_path: Path) -> None:
    link = tmp_path / "linked-state.json"
    link.symlink_to(repo / STATE)
    with pytest.raises(ControlStateError, match="symlink"):
        recovery.recover_session_seven(link, repo_root=repo)
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(repo, target_is_directory=True)
    with pytest.raises(ControlStateError, match="symlink"):
        recovery.recover_session_seven(linked_root / STATE, repo_root=linked_root)


def test_committed_missing_authority_refused(repo: Path) -> None:
    authority = repo / "docs/control/DECISIONS.md"
    authority.write_text(authority.read_text().split("## D-0039")[0])
    git(repo, "add", "docs/control/DECISIONS.md")
    git(repo, "commit", "-m", "test missing authority")
    with pytest.raises(ControlStateError, match="authority"):
        run(repo, apply=True)


def test_tampered_receipt_refused(repo: Path) -> None:
    result = run(repo, apply=True)
    receipt = Path(str(result["receipt_path"]))
    document = json.loads(receipt.read_text())
    document["candidate"]["commissioned_agents"] = ["A08"]
    receipt.write_text(json.dumps(document))
    with pytest.raises(ControlStateError):
        run(repo, apply=True)


def test_intent_failure_never_replaces_state(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = (repo / STATE).read_bytes()

    def fail_intent(path: Path, document: dict[str, object]) -> None:
        raise OSError("intent persistence refused")

    with monkeypatch.context() as patch:
        patch.setattr(recovery, "_atomic_write_json", fail_intent)
        with pytest.raises(ControlStateError, match="recovery write"):
            run(repo, apply=True)
    assert (repo / STATE).read_bytes() == before
    # mkdir succeeded but no intent exists: retry must not become permanently stuck.
    assert (repo / ".git/control-recovery").is_dir()
    assert run(repo, apply=True)["applied"] is True
    assert json.loads((repo / STATE).read_bytes())["state_revision"] == 65


def test_crash_before_state_replays_same_intent(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = recovery._atomic_write_json
    before = (repo / STATE).read_bytes()

    def fail_state(path: Path, document: dict[str, object]) -> None:
        if path == repo / STATE:
            raise OSError("injected crash before replacement")
        original(path, document)

    with monkeypatch.context() as patch:
        patch.setattr(recovery, "_atomic_write_json", fail_state)
        with pytest.raises(ControlStateError, match="recovery write"):
            run(repo, apply=True)
    assert (repo / STATE).read_bytes() == before
    assert run(repo, apply=True)["reconciled"] is True
    assert json.loads((repo / STATE).read_bytes())["state_revision"] == 65


def test_foreign_history_rejects_real_legacy_document(repo: Path) -> None:
    git(repo, "checkout", "--orphan", "foreign")
    git(repo, "commit", "-m", "orphan with copied authority")
    git(repo, "branch", "-D", "build/full-automation")
    git(repo, "branch", "-m", "build/full-automation")
    with pytest.raises(ControlStateError, match="Git verification failed"):
        run(repo, apply=True)


def test_cli_defaults_to_preview_and_requires_apply_pins(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from money_machine.control.cli import main

    before = (repo / STATE).read_bytes()
    arguments = ["recover-session-seven", "--state", str(repo / STATE), "--repo-root", str(repo)]
    assert main(arguments) == 0
    assert json.loads(capsys.readouterr().out)["applied"] is False
    assert main([*arguments, "--apply"]) == 2
    assert "explicit expected" in capsys.readouterr().err
    assert (repo / STATE).read_bytes() == before
