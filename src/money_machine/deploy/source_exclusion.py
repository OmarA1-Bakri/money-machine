"""Keep the private source PDF out of git.

D-0002 names the playbook as strict-deny Git content. The canonical
register records ``ignored_private_source``. This module asks git whether
that path is ignored and whether any PDF is already tracked. It does not
read the PDF and it does not run ``git add``.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

_PDF_NAME = "The-Hands-Off-Money-Machine-Playbook.pdf"
_PRIVATE_PATH = f"private/source/{_PDF_NAME}"
_REGISTER = Path("docs/source/CANONICAL_SOURCE_REGISTER.json")
_POLICY = "ignored_private_source"


class SourceExclusionRefusal(ValueError):
    """The register, the ignore rule, or a tracked PDF is refused."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SourceExclusion:
    """The playbook is ignored and no PDF is tracked."""

    name: str
    ignored: bool
    policy: str
    tracked_pdfs: tuple[str, ...]


def record_source_exclusion(root: Path | None = None) -> SourceExclusion:
    """Read the register and the git index. PDF bytes are not opened."""
    repo = Path(__file__).resolve().parents[3] if root is None else root
    if _policy(repo) != _POLICY:
        raise SourceExclusionRefusal("policy")
    if not _ignored(repo, _PDF_NAME) or not _ignored(repo, _PRIVATE_PATH):
        raise SourceExclusionRefusal("ignored")
    tracked = _tracked_pdfs(repo)
    if tracked:
        raise SourceExclusionRefusal("tracked")
    return SourceExclusion(
        name=_PDF_NAME,
        ignored=True,
        policy=_POLICY,
        tracked_pdfs=(),
    )


def refuse_pdf_stage(requested: str) -> None:
    """A PDF path is not staged. This function does not call git."""
    name = requested.replace("\\", "/").rsplit("/", 1)[-1]
    if name.casefold().endswith(".pdf"):
        raise SourceExclusionRefusal("stage")


def _policy(repo: Path) -> str:
    path = repo / _REGISTER
    if not path.is_file():
        raise SourceExclusionRefusal("register")
    decoded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise SourceExclusionRefusal("register")
    sources = decoded.get("sources")
    if not isinstance(sources, list):
        raise SourceExclusionRefusal("register")
    for item in sources:
        if not isinstance(item, dict) or item.get("path") != _PDF_NAME:
            continue
        if item.get("git_policy") != _POLICY or item.get("required_in_clean_clone") is not False:
            raise SourceExclusionRefusal("policy")
        return _POLICY
    raise SourceExclusionRefusal("register")


def _ignored(repo: Path, relative: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "check-ignore", "-q", "--", relative],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except OSError as error:
        raise SourceExclusionRefusal("ignored") from error
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise SourceExclusionRefusal("ignored")


def _tracked_pdfs(repo: Path) -> tuple[str, ...]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "-z"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except (subprocess.CalledProcessError, OSError) as error:
        raise SourceExclusionRefusal("tracked") from error
    names = tuple(
        name
        for name in completed.stdout.split("\0")
        if name.casefold().endswith(".pdf")
    )
    return names
