"""The canonical repository is recorded. A private-visibility change is refused."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from money_machine.deploy.repository_identity import (
    RepositoryIdentityRefusal,
    record_canonical_repository,
    refuse_private_visibility,
)

ROOT = Path(__file__).parents[2]


def test_the_canonical_repository_is_public_and_the_paths_are_documented() -> None:
    recorded = record_canonical_repository(ROOT)

    assert recorded.remote == "OmarA1-Bakri/money-machine"
    assert recorded.exists is True
    assert recorded.visibility == "public"
    assert recorded.privacy_change_refused is True
    assert recorded.wsl_root == "/mnt/d/Money Machine"
    assert recorded.windows_root == "D:\\Money Machine"
    assert "://" not in recorded.remote
    assert "@" not in recorded.remote


def test_a_private_visibility_change_is_refused() -> None:
    with pytest.raises(RepositoryIdentityRefusal, match="visibility"):
        refuse_private_visibility("private")


def test_a_public_visibility_request_is_not_a_change() -> None:
    refuse_private_visibility("public")


def test_a_foreign_remote_is_refused(tmp_path: Path) -> None:
    _repo(tmp_path, remote="https://github.com/example/other.git")

    with pytest.raises(RepositoryIdentityRefusal, match="remote"):
        record_canonical_repository(tmp_path)


def test_a_token_in_the_origin_url_is_not_the_recorded_remote(tmp_path: Path) -> None:
    _repo(
        tmp_path,
        remote="https://x-access-token:secret@github.com/OmarA1-Bakri/money-machine.git",
    )

    recorded = record_canonical_repository(tmp_path)

    assert recorded.remote == "OmarA1-Bakri/money-machine"
    assert "secret" not in recorded.remote


def test_undocumented_paths_are_refused(tmp_path: Path) -> None:
    _repo(tmp_path, remote="https://github.com/OmarA1-Bakri/money-machine.git")
    decisions = tmp_path / "docs" / "control" / "DECISIONS.md"
    decisions.write_text("no roots\n", encoding="utf-8")

    with pytest.raises(RepositoryIdentityRefusal, match="documented"):
        record_canonical_repository(tmp_path)


def _repo(path: Path, *, remote: str) -> None:
    control = path / "docs" / "control"
    source = path / "docs" / "source"
    control.mkdir(parents=True)
    source.mkdir(parents=True)
    state = {
        "repo_root": "/mnt/d/Money Machine",
        "windows_repo_root": "D:\\Money Machine",
    }
    (control / "IMPLEMENTATION_STATE.json").write_text(
        json.dumps(state) + "\n",
        encoding="utf-8",
    )
    cited = "D:\\Money Machine and /mnt/d/Money Machine\n"
    (control / "DECISIONS.md").write_text(cited, encoding="utf-8")
    (source / "SOURCE_REGISTER.md").write_text(cited, encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "init", "-b", "fixture"], check=True, timeout=30)
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", remote],
        check=True,
        timeout=30,
    )
