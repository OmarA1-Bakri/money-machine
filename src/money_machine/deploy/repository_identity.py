"""Record the canonical repository without changing its visibility.

D-0008 keeps ``OmarA1-Bakri/money-machine`` public. The checklist line that
asks for a private repository is reconciled by that decision. The Windows
and WSL roots are the paths already written in D-0001. This module does
not call GitHub and does not record a credential.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

_SLUG = "OmarA1-Bakri/money-machine"
_WSL_ROOT = "/mnt/d/Money Machine"
_WINDOWS_ROOT = "D:\\Money Machine"
_PATH_DOCS = (
    Path("docs/control/DECISIONS.md"),
    Path("docs/source/SOURCE_REGISTER.md"),
)


class RepositoryIdentityRefusal(ValueError):
    """The remote, the recorded paths, or a visibility change is refused."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CanonicalRepository:
    """The checkout's remote and the two documented roots."""

    remote: str
    exists: bool
    visibility: str
    privacy_change_refused: bool
    wsl_root: str
    windows_root: str


def record_canonical_repository(root: Path | None = None) -> CanonicalRepository:
    """Read the local origin and the documented roots. Visibility stays public."""
    repo = Path(__file__).resolve().parents[3] if root is None else root
    if _remote_slug(repo) != _SLUG:
        raise RepositoryIdentityRefusal("remote")
    state = _state(repo)
    if state.get("repo_root") != _WSL_ROOT or state.get("windows_repo_root") != _WINDOWS_ROOT:
        raise RepositoryIdentityRefusal("paths")
    if not _paths_documented(repo):
        raise RepositoryIdentityRefusal("documented")
    return CanonicalRepository(
        remote=_SLUG,
        exists=True,
        visibility="public",
        privacy_change_refused=True,
        wsl_root=_WSL_ROOT,
        windows_root=_WINDOWS_ROOT,
    )


def refuse_private_visibility(requested: str) -> None:
    """A request to make the repository private is not applied."""
    if requested == "private":
        raise RepositoryIdentityRefusal("visibility")


def _remote_slug(repo: Path) -> str:
    """Return ``owner/name`` from the origin URL. Userinfo is discarded."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except (subprocess.CalledProcessError, OSError) as error:
        raise RepositoryIdentityRefusal("remote") from error
    slug = _slug(completed.stdout.strip())
    if slug != _SLUG:
        raise RepositoryIdentityRefusal("remote")
    return slug


def _slug(url: str) -> str:
    """Keep only the repository path. A token in the URL is not returned."""
    stripped = url.strip()
    if "://" in stripped:
        stripped = stripped.split("://", 1)[1]
    if "@" in stripped:
        stripped = stripped.split("@", 1)[1]
    stripped = stripped.removesuffix(".git").rstrip("/")
    host = "github.com/"
    colon = "github.com:"
    if stripped.startswith(host):
        return stripped[len(host) :]
    if stripped.startswith(colon):
        return stripped[len(colon) :]
    return stripped


def _state(repo: Path) -> dict[str, object]:
    path = repo / "docs" / "control" / "IMPLEMENTATION_STATE.json"
    if not path.is_file():
        raise RepositoryIdentityRefusal("paths")
    decoded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise RepositoryIdentityRefusal("paths")
    return decoded


def _paths_documented(repo: Path) -> bool:
    """Both roots are written in the naming decision and the source register."""
    for relative in _PATH_DOCS:
        path = repo / relative
        if not path.is_file():
            return False
        text = path.read_text(encoding="utf-8")
        if _WSL_ROOT not in text or _WINDOWS_ROOT not in text:
            return False
    return True
