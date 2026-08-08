"""Verify that the canonical repository scaffold is complete and Git-persistable."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_STRUCTURE = (
    REPOSITORY_ROOT / "prompts/implementation/02_CANONICAL_REPOSITORY_STRUCTURE.md"
)
IGNORED_PRIVATE_FILES = frozenset({Path("private/source/The-Hands-Off-Money-Machine-Playbook.pdf")})


def parse_canonical_structure(document: Path) -> tuple[frozenset[Path], frozenset[Path]]:
    """Return the files and directories declared by the canonical text tree."""
    files: set[Path] = set()
    directories: set[Path] = set()
    directory_stack: list[str] = []
    in_tree = False

    for line in document.read_text(encoding="utf-8").splitlines():
        if line == "```text":
            in_tree = True
            continue
        if in_tree and line == "```":
            break
        if not in_tree:
            continue

        marker_positions = [
            position for marker in ("├── ", "└── ") if (position := line.find(marker)) >= 0
        ]
        if not marker_positions:
            continue

        marker_position = min(marker_positions)
        depth = marker_position // 4
        name = line[marker_position + 4 :].strip()
        if name == "...":
            continue

        parents = directory_stack[:depth]
        if name.endswith("/"):
            directory_name = name.removesuffix("/")
            path = Path(*parents, directory_name)
            directories.add(path)
            directory_stack = [*parents, directory_name]
        else:
            files.add(Path(*parents, name))

    return frozenset(files), frozenset(directories)


def scaffold_errors(root: Path = REPOSITORY_ROOT) -> list[str]:
    """Return deterministic descriptions of missing or non-persistable scaffold paths."""
    required_files, required_directories = parse_canonical_structure(CANONICAL_STRUCTURE)
    errors = [
        *(
            f"missing file: {path.as_posix()}"
            for path in sorted(required_files)
            if path not in IGNORED_PRIVATE_FILES and not (root / path).is_file()
        ),
        *(
            f"missing directory: {path.as_posix()}"
            for path in sorted(required_directories)
            if not (root / path).is_dir()
        ),
    ]

    ignore_rules = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    if not {"*.pdf", "private/source/*"} <= set(ignore_rules):
        errors.append("private scaffold PDF is not covered by strict-deny ignore rules")

    for path in sorted(required_directories):
        directory = root / path
        if directory.is_dir() and not any(directory.iterdir()):
            errors.append(f"empty directory cannot persist in Git: {path.as_posix()}")

    gitkeep_paths = sorted(
        path / ".gitkeep" for path in required_directories if (root / path / ".gitkeep").is_file()
    )
    if gitkeep_paths:
        ignored = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin"],
            cwd=root,
            check=False,
            capture_output=True,
            input="".join(f"{path.as_posix()}\n" for path in gitkeep_paths),
            text=True,
        )
        errors.extend(
            f"Git ignores scaffold marker: {path}" for path in ignored.stdout.splitlines()
        )

    return sorted(errors)


def main() -> int:
    """Print scaffold failures and return a nonzero status when validation fails."""
    errors = scaffold_errors()
    if errors:
        print("Canonical scaffold verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Canonical scaffold verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
