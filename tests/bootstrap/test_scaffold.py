"""Focused tests for the canonical repository scaffold."""

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
STRICT_DENY_PROBES = (
    "token.txt",
    "access_token.json",
    "oauth-token.json",
    "Cookies",
    "browser_profile/profile.json",
    "browser_profile/Default/Cookies",
    ".browser-profile/profile.json",
    "chrome-profile/Default/Cookies",
    "screenshot.png",
    "receipt.json",
    "customer.json",
    "provider-payload.json",
)


def test_canonical_scaffold_is_complete_and_persistable() -> None:
    result = subprocess.run(
        [sys.executable, str(REPOSITORY_ROOT / "scripts/verify_scaffold.py")],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "Canonical scaffold verification passed.\n"


def test_root_private_runtime_probes_are_ignored_without_hiding_curated_paths(
    tmp_path: Path,
) -> None:
    probe_repository = tmp_path / "repository"
    probe_repository.mkdir()
    (probe_repository / ".gitignore").write_text(
        (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=probe_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=probe_repository,
        check=False,
        capture_output=True,
        input="".join(f"{path}\n" for path in STRICT_DENY_PROBES),
        text=True,
    )

    assert ignored.returncode == 0
    assert ignored.stdout.splitlines() == list(STRICT_DENY_PROBES)

    curated = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=probe_repository,
        check=False,
        capture_output=True,
        input="docs/source/receipt.json\nconfig/customer.json\n",
        text=True,
    )

    assert curated.returncode == 1
    assert curated.stdout == ""


def test_bootstrap_scripts_install_both_frozen_dependency_sets() -> None:
    bash_script = (REPOSITORY_ROOT / "scripts/bootstrap.sh").read_text(encoding="utf-8")
    powershell_script = (REPOSITORY_ROOT / "scripts/bootstrap.ps1").read_text(encoding="utf-8")

    for script in (bash_script, powershell_script):
        assert "uv sync --frozen" in script
        assert "pnpm install --frozen-lockfile" in script
