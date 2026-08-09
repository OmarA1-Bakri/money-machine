from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO, NoReturn, TypedDict, cast

import pytest

from money_machine.control import locking as control_locking
from money_machine.control import state as control_state
from money_machine.control.locking import ControlLockError, exclusive_control_lock
from money_machine.control.state import ControlStateError

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
CONTROL_FILES = {
    "IMPLEMENTATION_STATE.json",
    "IMPLEMENTATION_LOG.md",
    "DECISIONS.md",
    "TEST_EVIDENCE.md",
    "NEXT_SESSION.md",
}
CONTROL_LOCK_FILE = "IMPLEMENTATION_STATE.json.lock"
CONTROL_LOCK_IGNORE_RULE = f"/docs/control/{CONTROL_LOCK_FILE}"
BRANCH = "build/full-automation"
BOOTSTRAP_SUBJECT = "chore(bootstrap): initialise money machine autonomous monorepo"
OUTER_GATES_BLOCKER = "SESSION_00_OUTER_GATES_PENDING"
CLOSURE_EVIDENCE_KEY = "evidence_closure_commit_recorded"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


class ControlState(TypedDict):
    repo_root: str
    branch: str
    session_status: str
    state_revision: int
    current_session: int
    completed_sessions: list[int]
    next_session: int
    next_prompt: str
    bootstrap_commit_sha: str | None
    evidence_closure_commit_sha: str | None
    last_verified_commit: str | None
    head_sha: str | None
    services: dict[str, str]
    commissioned_agents: list[str]
    tests: dict[str, str]
    environment_versions: dict[str, str]
    blockers: list[dict[str, str]]
    required_completion_evidence: dict[str, bool]
    transition_contract: dict[str, bool | int]
    updated_at: str


@dataclass(frozen=True)
class GitTransition:
    repo: Path
    state_path: Path
    candidate_path: Path
    candidate: ControlState
    bootstrap: str
    closure: str


Mutation = Callable[[ControlState], None]


def load_state(path: Path = STATE_PATH) -> ControlState:
    return cast(ControlState, json.loads(path.read_text(encoding="utf-8")))


def load_document(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def write_state(path: Path, state: ControlState) -> None:
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def write_document(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def incomplete_session_zero_fixture() -> ControlState:
    state = copy.deepcopy(load_state())
    state.update(
        {
            "session_status": "incomplete",
            "current_session": 0,
            "completed_sessions": [],
            "next_session": 0,
            "next_prompt": "03_SESSION_00_DISCOVERY_AND_REPO_BOOTSTRAP.md",
            "head_sha": None,
            "bootstrap_commit_sha": None,
            "evidence_closure_commit_sha": None,
            "last_verified_commit": None,
            "updated_at": "2026-08-08T00:00:00Z",
        }
    )
    state["blockers"] = [
        blocker for blocker in state["blockers"] if blocker["code"] != OUTER_GATES_BLOCKER
    ]
    state["blockers"].append(
        {
            "code": OUTER_GATES_BLOCKER,
            "scope": "session completion",
            "detail": "Fixture awaits the evidence-closure transition.",
        }
    )
    return state


def git(repo: Path, *arguments: str, stdin: str | None = None) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        input=stdin,
    ).stdout.strip()


def completed_candidate(state: ControlState, bootstrap: str, closure: str) -> ControlState:
    candidate = copy.deepcopy(state)
    candidate.update(
        {
            "state_revision": state["state_revision"] + 1,
            "session_status": "complete",
            "completed_sessions": [0],
            "next_session": 1,
            "next_prompt": "04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md",
            "bootstrap_commit_sha": bootstrap,
            "evidence_closure_commit_sha": closure,
            "last_verified_commit": bootstrap,
            "head_sha": closure,
            "updated_at": "2026-08-09T00:00:00Z",
        }
    )
    candidate["required_completion_evidence"] = {
        key: True for key in candidate["required_completion_evidence"]
    }
    candidate["blockers"] = [
        blocker for blocker in candidate["blockers"] if blocker["code"] != OUTER_GATES_BLOCKER
    ]
    return candidate


def run_transition(state_path: Path, candidate_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "money_machine.control",
            "apply-completion",
            "--state",
            str(state_path),
            "--candidate",
            str(candidate_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def transition_command(state_path: Path, candidate_path: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "money_machine.control",
        "apply-completion",
        "--state",
        str(state_path),
        "--candidate",
        str(candidate_path),
    ]


def prepare_transition(tmp_path: Path) -> GitTransition:
    repo = tmp_path / "repository"
    state_path = repo / "docs/control/IMPLEMENTATION_STATE.json"
    state_path.parent.mkdir(parents=True)
    state = incomplete_session_zero_fixture()
    state["repo_root"] = str(repo)
    state["branch"] = BRANCH
    write_state(state_path, state)
    evidence_path = repo / "evidence.txt"
    evidence_path.write_text("reviewed evidence\n", encoding="utf-8")
    (repo / ".gitignore").write_text(
        (ROOT / ".gitignore").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    git(repo, "init", "-b", BRANCH)
    git(repo, "config", "user.name", "Control Test")
    git(repo, "config", "user.email", "control-test@example.invalid")
    git(repo, "add", ".gitignore", "docs/control/IMPLEMENTATION_STATE.json", "evidence.txt")
    git(repo, "commit", "-m", BOOTSTRAP_SUBJECT)
    bootstrap = git(repo, "rev-parse", "HEAD")

    state.update(
        {
            "head_sha": bootstrap,
            "bootstrap_commit_sha": bootstrap,
            "last_verified_commit": bootstrap,
            "evidence_closure_commit_sha": None,
        }
    )
    state["required_completion_evidence"] = {
        key: key != CLOSURE_EVIDENCE_KEY for key in state["required_completion_evidence"]
    }
    write_state(state_path, state)
    git(repo, "add", "docs/control/IMPLEMENTATION_STATE.json")
    git(repo, "commit", "-m", "chore(control): close bootstrap evidence")
    closure = git(repo, "rev-parse", "HEAD")

    candidate = completed_candidate(state, bootstrap, closure)
    candidate_path = tmp_path / "candidate.json"
    write_state(candidate_path, candidate)
    return GitTransition(repo, state_path, candidate_path, candidate, bootstrap, closure)


def test_git_timeout_is_reported_as_control_state_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_timeout(*args: object, **kwargs: object) -> NoReturn:
        raise subprocess.TimeoutExpired(cmd=("git", "status"), timeout=1)

    monkeypatch.setattr(control_state.subprocess, "run", raise_timeout)

    with pytest.raises(ControlStateError, match=r"^git command timed out$"):
        control_state._run_git(ROOT, "status")  # pyright: ignore[reportPrivateUsage]


def test_git_invocation_uses_timeout_and_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    received_command: tuple[str, ...] | None = None
    received_options: dict[str, object] | None = None

    def record_run(command: tuple[str, ...], **options: object) -> subprocess.CompletedProcess[str]:
        nonlocal received_command, received_options
        received_command = command
        received_options = options
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(control_state.subprocess, "run", record_run)

    assert (
        control_state._run_git(  # pyright: ignore[reportPrivateUsage]
            ROOT, "status", "--short"
        )
        == "ok\n"
    )
    assert received_command == ("git", "status", "--short")
    assert received_options is not None
    assert received_options["cwd"] == ROOT
    assert received_options["timeout"] == control_state.CONTROL_GIT_TIMEOUT_SECONDS
    assert received_options["text"] is True
    assert received_options["encoding"] == "utf-8"
    assert received_options["capture_output"] is True
    assert received_options["check"] is False


def test_atomic_write_closes_descriptor_once_when_fdopen_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "state.json"
    target.write_text("{}\n", encoding="utf-8")
    descriptor_seen: int | None = None
    close_calls: list[int] = []
    real_close = os.close

    def fail_fdopen(descriptor: int, mode: str) -> NoReturn:
        nonlocal descriptor_seen
        descriptor_seen = descriptor
        raise OSError(f"fdopen failed in {mode}")

    def record_close(descriptor: int) -> None:
        close_calls.append(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(control_state.os, "fdopen", fail_fdopen)
    monkeypatch.setattr(control_state.os, "close", record_close)

    with pytest.raises(OSError, match="fdopen failed"):
        control_state._atomic_write_json(  # pyright: ignore[reportPrivateUsage]
            target, {"state_revision": 1}
        )

    assert descriptor_seen is not None
    if close_calls != [descriptor_seen]:
        real_close(descriptor_seen)
    assert close_calls == [descriptor_seen]
    assert not list(tmp_path.glob(".state.json.*.tmp"))


def test_atomic_write_closes_owned_descriptor_and_removes_temp_on_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "state.json"
    target.write_text("{}\n", encoding="utf-8")
    real_close = os.close
    streams: list[FailingWriteStream] = []

    class FailingWriteStream:
        def __init__(self, descriptor: int) -> None:
            self.descriptor = descriptor
            self.close_count = 0

        def __enter__(self) -> FailingWriteStream:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: object,
        ) -> None:
            self.close()

        def fileno(self) -> int:
            return self.descriptor

        def write(self, payload: bytes) -> NoReturn:
            raise OSError(f"write failed for {len(payload)} bytes")

        def flush(self) -> None:
            raise AssertionError("flush must not run after a failed write")

        def close(self) -> None:
            self.close_count += 1
            real_close(self.descriptor)

    def failing_stream(descriptor: int, mode: str) -> IO[bytes]:
        assert mode == "wb"
        stream = FailingWriteStream(descriptor)
        streams.append(stream)
        return cast(IO[bytes], stream)

    monkeypatch.setattr(control_state.os, "fdopen", failing_stream)

    with pytest.raises(OSError, match="write failed"):
        control_state._atomic_write_json(  # pyright: ignore[reportPrivateUsage]
            target, {"state_revision": 1}
        )

    assert len(streams) == 1
    assert streams[0].close_count == 1
    assert not list(tmp_path.glob(".state.json.*.tmp"))


def test_atomic_write_succeeds_without_fchmod(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "state.json"
    target.write_text("{}\n", encoding="utf-8")
    descriptor_seen: int | None = None
    real_mkstemp = control_state.tempfile.mkstemp

    def record_mkstemp(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | os.PathLike[str] | None = None,
        text: bool = False,
    ) -> tuple[int, str]:
        nonlocal descriptor_seen
        descriptor, temporary_name = real_mkstemp(
            suffix=suffix,
            prefix=prefix,
            dir=dir,
            text=text,
        )
        descriptor_seen = descriptor
        return descriptor, temporary_name

    monkeypatch.setattr(control_state.tempfile, "mkstemp", record_mkstemp)
    monkeypatch.delattr(control_state.os, "fchmod")

    try:
        control_state._atomic_write_json(  # pyright: ignore[reportPrivateUsage]
            target, {"state_revision": 1}
        )
    finally:
        if descriptor_seen is not None:
            try:
                os.fstat(descriptor_seen)
            except OSError:
                pass
            else:
                os.close(descriptor_seen)

    assert json.loads(target.read_text(encoding="utf-8")) == {"state_revision": 1}
    assert not list(tmp_path.glob(".state.json.*.tmp"))


@pytest.mark.skipif(os.name != "posix", reason="the process barrier wrapper requires POSIX PATH")
def test_canonical_and_symlink_alias_transitions_allow_exactly_one_writer(
    tmp_path: Path,
) -> None:
    transition = prepare_transition(tmp_path)
    wrapper_dir = tmp_path / "git-wrapper"
    wrapper_dir.mkdir()
    barrier_dir = tmp_path / "status-barrier"
    wrapper_path = wrapper_dir / "git"
    real_git = shutil.which("git")
    assert real_git is not None
    wrapper_path.write_text(
        f"#!{sys.executable}\n"
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "import time\n"
        "from pathlib import Path\n"
        "arguments = sys.argv[1:]\n"
        "if 'status' in arguments and '--porcelain=v1' in arguments:\n"
        "    real_git = os.environ['CONTROL_TEST_REAL_GIT']\n"
        "    result = subprocess.run([real_git, *arguments], capture_output=True)\n"
        "    barrier = Path(os.environ['CONTROL_TEST_BARRIER'])\n"
        "    barrier.mkdir(parents=True, exist_ok=True)\n"
        "    owner = os.getppid()\n"
        "    counter = barrier / f'counter-{{owner}}'\n"
        "    phase = int(counter.read_text() or '0') + 1 if counter.exists() else 1\n"
        "    counter.write_text(str(phase))\n"
        "    (barrier / f'phase-{{phase}}-{{owner}}').touch()\n"
        "    deadline = time.monotonic() + 0.75\n"
        "    while time.monotonic() < deadline:\n"
        "        if len(list(barrier.glob(f'phase-{{phase}}-*'))) >= 2:\n"
        "            break\n"
        "        time.sleep(0.01)\n"
        "    sys.stdout.buffer.write(result.stdout)\n"
        "    sys.stderr.buffer.write(result.stderr)\n"
        "    raise SystemExit(result.returncode)\n"
        "os.execv(os.environ['CONTROL_TEST_REAL_GIT'], "
        "[os.environ['CONTROL_TEST_REAL_GIT'], *arguments])\n",
        encoding="utf-8",
    )
    wrapper_path.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{wrapper_dir}{os.pathsep}{environment['PATH']}"
    environment["CONTROL_TEST_BARRIER"] = str(barrier_dir)
    environment["CONTROL_TEST_REAL_GIT"] = real_git
    alias_path = transition.state_path.with_name("state-alias.json")
    alias_path.symlink_to(transition.state_path)
    commands = [
        transition_command(transition.state_path, transition.candidate_path),
        transition_command(alias_path, transition.candidate_path),
    ]

    processes = [
        subprocess.Popen(
            command,
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for command in commands
    ]
    results = [process.communicate(timeout=15) for process in processes]

    assert sorted(process.returncode for process in processes) == [0, 2], results
    assert load_state(transition.state_path) == transition.candidate
    assert (
        load_state(transition.state_path)["state_revision"]
        == transition.candidate["state_revision"]
    )
    assert not list(transition.state_path.parent.glob(".IMPLEMENTATION_STATE.json.*.tmp"))


def test_transition_sidecar_is_durable_ignored_and_the_only_extra_control_file(
    tmp_path: Path,
) -> None:
    transition = prepare_transition(tmp_path)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 0, result.stderr
    lock_path = transition.state_path.with_name(CONTROL_LOCK_FILE)
    assert lock_path.read_bytes() == b"\0"
    assert {path.name for path in transition.state_path.parent.iterdir() if path.is_file()} == {
        transition.state_path.name,
        CONTROL_LOCK_FILE,
    }
    assert (
        CONTROL_LOCK_IGNORE_RULE in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    )
    relative_lock_path = str(lock_path.relative_to(transition.repo))
    assert git(transition.repo, "check-ignore", relative_lock_path) == relative_lock_path
    assert git(transition.repo, "status", "--short", "--untracked-files=all").splitlines() == [
        "M docs/control/IMPLEMENTATION_STATE.json"
    ]


class FakeMsvcrt:
    LK_LOCK = 1
    LK_UNLCK = 2

    def __init__(self, failure_mode: int | None = None) -> None:
        self.failure_mode = failure_mode
        self.calls: list[tuple[int, int, int, int]] = []

    def locking(self, descriptor: int, mode: int, size: int) -> None:
        self.calls.append((descriptor, mode, size, os.lseek(descriptor, 0, os.SEEK_CUR)))
        if mode == self.failure_mode:
            raise OSError("simulated msvcrt failure")


def test_windows_locking_acquires_and_releases_byte_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_msvcrt = FakeMsvcrt()
    monkeypatch.setattr(control_locking.sys, "platform", "win32")
    monkeypatch.setattr(control_locking, "msvcrt", fake_msvcrt, raising=False)
    lock_path = tmp_path / "state.json.lock"

    with exclusive_control_lock(lock_path):
        assert lock_path.read_bytes() == b"\0"

    assert [(mode, size, position) for _, mode, size, position in fake_msvcrt.calls] == [
        (fake_msvcrt.LK_LOCK, 1, 0),
        (fake_msvcrt.LK_UNLCK, 1, 0),
    ]


def test_windows_locking_reports_acquisition_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_msvcrt = FakeMsvcrt(failure_mode=FakeMsvcrt.LK_LOCK)
    monkeypatch.setattr(control_locking.sys, "platform", "win32")
    monkeypatch.setattr(control_locking, "msvcrt", fake_msvcrt, raising=False)

    with (
        pytest.raises(ControlLockError, match="cannot acquire control lock"),
        exclusive_control_lock(tmp_path / "state.json.lock"),
    ):
        pytest.fail("lock body must not run after acquisition failure")


def test_windows_locking_reports_release_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_msvcrt = FakeMsvcrt(failure_mode=FakeMsvcrt.LK_UNLCK)
    monkeypatch.setattr(control_locking.sys, "platform", "win32")
    monkeypatch.setattr(control_locking, "msvcrt", fake_msvcrt, raising=False)

    with (
        pytest.raises(ControlLockError, match="cannot release control lock"),
        exclusive_control_lock(tmp_path / "state.json.lock"),
    ):
        pass


def test_control_files_are_exactly_the_five_continuity_files() -> None:
    control_files = {path.name for path in (ROOT / "docs/control").iterdir() if path.is_file()}

    assert control_files - {CONTROL_LOCK_FILE} == CONTROL_FILES
    assert control_files <= CONTROL_FILES | {CONTROL_LOCK_FILE}


def test_checked_in_state_is_a_valid_session_zero_continuity_shape() -> None:
    state = load_state()
    required = {
        "programme",
        "version",
        "repo_root",
        "windows_repo_root",
        "branch",
        "head_sha",
        "current_session",
        "completed_sessions",
        "services",
        "commissioned_agents",
        "tests",
        "environment_versions",
        "blockers",
        "next_session",
        "updated_at",
        "required_completion_evidence",
        "transition_contract",
    }
    assert required <= state.keys()
    assert state["current_session"] == 0
    if state["session_status"] == "incomplete":
        assert state["completed_sessions"] == []
        assert state["next_session"] == 0
        assert not all(state["required_completion_evidence"].values())
    else:
        assert state["session_status"] == "complete"
        assert state["completed_sessions"] == [0]
        assert state["next_session"] == 1
        assert state["next_prompt"] == "04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md"
        assert all(state["required_completion_evidence"].values())
        bootstrap = state["bootstrap_commit_sha"]
        closure = state["evidence_closure_commit_sha"]
        assert FULL_SHA.fullmatch(bootstrap or "")
        assert FULL_SHA.fullmatch(closure or "")
        assert bootstrap != closure
        assert state["last_verified_commit"] == bootstrap
        assert state["head_sha"] == closure


def test_real_entrypoint_atomically_applies_git_backed_transition(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["applied"] is True
    assert load_state(transition.state_path) == transition.candidate
    assert git(transition.repo, "rev-parse", "HEAD") == transition.closure
    assert git(
        transition.repo, "status", "--porcelain", "--", "docs/control/IMPLEMENTATION_STATE.json"
    )
    assert not list(transition.state_path.parent.glob(".IMPLEMENTATION_STATE.json.*.tmp"))


@pytest.mark.parametrize(
    "fabricated_evidence",
    [
        "implementation_review_approved",
        "adversarial_review_clear",
        "bootstrap_commit_recorded",
        "api_health_live",
    ],
)
def test_rejects_candidate_fabricating_pre_transition_evidence_without_writing(
    tmp_path: Path,
    fabricated_evidence: str,
) -> None:
    transition = prepare_transition(tmp_path)
    previous = load_state(transition.state_path)
    previous["required_completion_evidence"][fabricated_evidence] = False
    write_state(transition.state_path, previous)
    original = transition.state_path.read_bytes()

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "pre-transition evidence must be complete except" in result.stderr
    assert transition.state_path.read_bytes() == original


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("services", {"api": "fabricated_green"}),
        ("tests", {"all": "fabricated_green"}),
        ("environment_versions", {"python": "fabricated"}),
        ("transition_contract", {"unsupported_completion_is_rejected": False}),
        ("commissioned_agents", ["fabricated-agent"]),
    ],
)
def test_rejects_candidate_rewriting_continuity_evidence_without_writing(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    candidate = cast(dict[str, object], transition.candidate)
    candidate[field] = replacement
    write_state(transition.candidate_path, transition.candidate)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert f"{field} cannot change" in result.stderr
    assert transition.state_path.read_bytes() == original


@pytest.mark.parametrize("mutation", ["remove", "rewrite", "add"])
def test_rejects_unauthorized_blocker_changes_without_writing(
    tmp_path: Path,
    mutation: str,
) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    blockers = transition.candidate["blockers"]
    if mutation == "remove":
        blockers.clear()
    elif mutation == "rewrite":
        blockers[0]["detail"] = "fabricated resolution"
    else:
        blockers.append({"code": "FABRICATED_BLOCKER", "scope": "session", "detail": "unsupported"})
    write_state(transition.candidate_path, transition.candidate)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "may remove only the Session 00 outer-gates blocker" in result.stderr
    assert transition.state_path.read_bytes() == original


@pytest.mark.parametrize(
    ("field", "invalid_value", "expected"),
    [
        ("bootstrap_commit_sha", "not-a-sha", "bootstrap_commit_sha must be"),
        ("last_verified_commit", "b" * 40, "last_verified_commit must identify"),
        ("head_sha", "b" * 40, "head_sha must identify the bootstrap"),
        (
            "evidence_closure_commit_sha",
            "b" * 40,
            "pre-transition evidence_closure_commit_sha must be null",
        ),
    ],
)
def test_rejects_invalid_pre_transition_commit_semantics_without_writing(
    tmp_path: Path,
    field: str,
    invalid_value: str,
    expected: str,
) -> None:
    transition = prepare_transition(tmp_path)
    previous = load_state(transition.state_path)
    previous[field] = invalid_value
    transition.candidate[field] = invalid_value
    if field == "evidence_closure_commit_sha":
        transition.candidate[field] = transition.closure
    write_state(transition.state_path, previous)
    write_state(transition.candidate_path, transition.candidate)
    original = transition.state_path.read_bytes()

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert expected in result.stderr
    assert transition.state_path.read_bytes() == original


def test_rejects_closure_commit_document_mismatch_without_writing(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    previous = load_state(transition.state_path)
    previous["tests"]["closure_document_probe"] = "present_only_after_closure"
    transition.candidate["tests"] = copy.deepcopy(previous["tests"])
    write_state(transition.state_path, previous)
    git(
        transition.repo,
        "update-index",
        "--assume-unchanged",
        "docs/control/IMPLEMENTATION_STATE.json",
    )
    write_state(transition.candidate_path, transition.candidate)
    original = transition.state_path.read_bytes()

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "evidence-closure commit must contain the exact pre-transition state" in result.stderr
    assert transition.state_path.read_bytes() == original


def mark_api_health_incomplete(candidate: ControlState) -> None:
    candidate["required_completion_evidence"]["api_health_live"] = False


def remove_evidence_key(candidate: ControlState) -> None:
    del candidate["required_completion_evidence"]["api_health_live"]


def duplicate_completed_session(candidate: ControlState) -> None:
    candidate["completed_sessions"] = [0, 0]


def skip_next_session(candidate: ControlState) -> None:
    candidate["next_session"] = 2


def reuse_bootstrap_commit(candidate: ControlState) -> None:
    candidate["evidence_closure_commit_sha"] = candidate["bootstrap_commit_sha"]
    candidate["head_sha"] = candidate["bootstrap_commit_sha"]


def skip_state_revision(candidate: ControlState) -> None:
    candidate["state_revision"] = 9


def use_unsupported_completion(candidate: ControlState) -> None:
    candidate["session_status"] = "commissioned"


def use_wrong_session_one_prompt(candidate: ControlState) -> None:
    candidate["next_prompt"] = "04_SESSION_01_WRONG_PROMPT.md"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (mark_api_health_incomplete, "cannot change except"),
        (remove_evidence_key, "evidence keys"),
        (duplicate_completed_session, "completed_sessions"),
        (skip_next_session, "next session"),
        (reuse_bootstrap_commit, "must be distinct"),
        (skip_state_revision, "revision"),
        (use_unsupported_completion, "unsupported completion"),
        (use_wrong_session_one_prompt, "canonical Session 01 prompt"),
    ],
)
def test_real_entrypoint_rejects_invalid_transition_without_writing(
    tmp_path: Path,
    mutation: Mutation,
    expected: str,
) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    mutation(transition.candidate)
    write_state(transition.candidate_path, transition.candidate)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert expected in result.stderr
    assert transition.state_path.read_bytes() == original
    assert not list(transition.state_path.parent.glob(".IMPLEMENTATION_STATE.json.*.tmp"))


def test_rejects_candidate_reusing_previous_updated_at_without_writing(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    transition.candidate["updated_at"] = load_state(transition.state_path)["updated_at"]
    write_state(transition.candidate_path, transition.candidate)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "updated_at must change" in result.stderr
    assert transition.state_path.read_bytes() == original


def test_rejects_nonexistent_commit_object(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    nonexistent = "c" * 40
    transition.candidate["evidence_closure_commit_sha"] = nonexistent
    transition.candidate["head_sha"] = nonexistent
    write_state(transition.candidate_path, transition.candidate)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "Git verification failed" in result.stderr
    assert transition.state_path.read_bytes() == original


def test_rejects_bootstrap_commit_that_is_not_closure_ancestor(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    tree = git(transition.repo, "rev-parse", f"{transition.closure}^{{tree}}")
    unrelated = git(
        transition.repo,
        "commit-tree",
        tree,
        stdin=f"{BOOTSTRAP_SUBJECT}\n",
    )
    previous = load_state(transition.state_path)
    previous["bootstrap_commit_sha"] = unrelated
    previous["last_verified_commit"] = unrelated
    previous["head_sha"] = unrelated
    transition.candidate["bootstrap_commit_sha"] = unrelated
    transition.candidate["last_verified_commit"] = unrelated
    write_state(transition.state_path, previous)
    git(
        transition.repo,
        "update-index",
        "--assume-unchanged",
        "docs/control/IMPLEMENTATION_STATE.json",
    )
    write_state(transition.candidate_path, transition.candidate)
    original = transition.state_path.read_bytes()

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "must be an ancestor" in result.stderr
    assert transition.state_path.read_bytes() == original


def test_rejects_dirty_tracked_state_before_application(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    with transition.state_path.open("a", encoding="utf-8") as stream:
        stream.write("\n")
    dirty = transition.state_path.read_bytes()

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "must be clean" in result.stderr
    assert transition.state_path.read_bytes() == dirty


def test_rejects_dirty_non_state_tracked_file_before_application(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    evidence_path = transition.repo / "evidence.txt"
    evidence_path.write_text("locally changed evidence\n", encoding="utf-8")
    original = transition.state_path.read_bytes()

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "all tracked repository files must be clean" in result.stderr
    assert transition.state_path.read_bytes() == original


def test_rejects_candidates_missing_any_continuity_field_without_writing(
    tmp_path: Path,
) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    baseline = load_document(transition.candidate_path)
    continuity_fields = (
        "windows_repo_root",
        "services",
        "commissioned_agents",
        "tests",
        "blockers",
        "environment_versions",
        "transition_contract",
    )

    for field in continuity_fields:
        candidate = copy.deepcopy(baseline)
        del candidate[field]
        write_document(transition.candidate_path, candidate)

        result = run_transition(transition.state_path, transition.candidate_path)

        assert result.returncode == 2
        assert f"missing required fields: {field}" in result.stderr
        assert transition.state_path.read_bytes() == original


def test_rejects_invalid_nested_continuity_types_without_writing(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    baseline = load_document(transition.candidate_path)
    invalid_values: tuple[tuple[str, object, str], ...] = (
        ("services", {"api": 200}, "services must map string keys to string values"),
        ("commissioned_agents", [7], "commissioned_agents must be a list of strings"),
        ("tests", {"python": True}, "tests must map string keys to string values"),
        (
            "environment_versions",
            {"python": 3.12},
            "environment_versions must map string keys to string values",
        ),
        ("blockers", [{"code": "X", "scope": "all"}], "blockers must be a list"),
        (
            "transition_contract",
            {"completion_requires_next_session": "1"},
            "transition_contract must map strings to booleans or integers",
        ),
    )

    for field, invalid, expected in invalid_values:
        candidate = copy.deepcopy(baseline)
        candidate[field] = invalid
        write_document(transition.candidate_path, candidate)

        result = run_transition(transition.state_path, transition.candidate_path)

        assert result.returncode == 2
        assert expected in result.stderr
        assert transition.state_path.read_bytes() == original
