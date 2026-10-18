"""Record the stored implementation prompt pack.

The pack lives at ``prompts/implementation``. ``MANIFEST.json`` and
``TRACEABILITY.json`` name the same twenty-one prompt files. This module
checks that each file is present, hash-matched, and tracked. It does not
rewrite a prompt file.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

_PACK = Path("prompts/implementation")
_MANIFEST = "MANIFEST.json"
_TRACE = "TRACEABILITY.json"


class PromptPackRefusal(ValueError):
    """The stored pack is missing, mismatched, untracked, or a rewrite is refused."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StoredPromptPack:
    """The prompt files that git already stores."""

    file_count: int
    stored: bool
    tracked: bool
    names: tuple[str, ...]


def record_prompt_pack(root: Path | None = None) -> StoredPromptPack:
    """Read the manifest and the git index. Prompt files are not written."""
    repo = Path(__file__).resolve().parents[3] if root is None else root
    manifest = _rows(_load(repo, _MANIFEST), "files")
    trace = _load(repo, _TRACE)
    traced = _rows(trace, "files")
    if trace.get("file_count") != len(manifest) or len(traced) != len(manifest) or not manifest:
        raise PromptPackRefusal("count")
    by_name = {_prompt(item)[0]: _prompt(item) for item in traced}
    names: list[str] = []
    for item in manifest:
        name, size, digest = _prompt(item)
        if name in names or by_name.get(name) != (name, size, digest):
            raise PromptPackRefusal("name")
        path = repo / _PACK / name
        if not path.is_file():
            raise PromptPackRefusal("missing")
        data = path.read_bytes()
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise PromptPackRefusal("hash")
        names.append(name)
    relative = (
        str(_PACK / _MANIFEST),
        str(_PACK / _TRACE),
        *(str(_PACK / name) for name in names),
    )
    if not _tracked(repo, relative):
        raise PromptPackRefusal("tracked")
    return StoredPromptPack(
        file_count=len(names),
        stored=True,
        tracked=True,
        names=tuple(names),
    )


def refuse_prompt_rewrite(requested: str) -> None:
    """A request to rewrite a stored prompt is not applied."""
    normalized = requested.replace("\\", "/").lstrip("./")
    if normalized.startswith("prompts/implementation/"):
        raise PromptPackRefusal("rewrite")


def _load(repo: Path, name: str) -> dict[str, object]:
    path = repo / _PACK / name
    if not path.is_file():
        raise PromptPackRefusal("manifest")
    decoded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise PromptPackRefusal("manifest")
    return decoded


def _rows(document: dict[str, object], key: str) -> list[object]:
    rows = document.get(key)
    if not isinstance(rows, list):
        raise PromptPackRefusal("manifest")
    return rows


def _prompt(item: object) -> tuple[str, int, str]:
    if not isinstance(item, dict):
        raise PromptPackRefusal("manifest")
    name = item.get("name")
    size = item.get("bytes")
    digest = item.get("sha256")
    if not isinstance(name, str) or not name.endswith(".md") or "/" in name or "\\" in name:
        raise PromptPackRefusal("name")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise PromptPackRefusal("manifest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise PromptPackRefusal("manifest")
    return name, size, digest


def _tracked(repo: Path, relative: tuple[str, ...]) -> bool:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "-z", "--", *relative],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except (subprocess.CalledProcessError, OSError) as error:
        raise PromptPackRefusal("tracked") from error
    found = {name for name in completed.stdout.split("\0") if name}
    return found == set(relative)
