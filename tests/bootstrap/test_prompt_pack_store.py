"""The implementation prompt pack is stored and a rewrite is refused."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from money_machine.deploy.prompt_pack import (
    PromptPackRefusal,
    record_prompt_pack,
    refuse_prompt_rewrite,
)

ROOT = Path(__file__).parents[2]


def test_the_prompt_pack_is_stored() -> None:
    recorded = record_prompt_pack(ROOT)

    assert recorded.file_count == 21
    assert recorded.stored is True
    assert recorded.tracked is True
    assert recorded.names[0] == "00_READ_ME_FIRST.md"
    assert recorded.names[-1] == "20_FINAL_ACCEPTANCE_CHECKLIST.md"
    assert "The-Hands-Off-Money-Machine-Playbook.pdf" not in recorded.names


def test_a_prompt_rewrite_is_refused() -> None:
    with pytest.raises(PromptPackRefusal, match="rewrite"):
        refuse_prompt_rewrite("prompts/implementation/00_READ_ME_FIRST.md")


def test_a_product_path_is_not_a_prompt_rewrite() -> None:
    refuse_prompt_rewrite("src/money_machine/deploy/prompt_pack.py")


def test_a_missing_prompt_is_refused(tmp_path: Path) -> None:
    _pack(tmp_path, present=False)

    with pytest.raises(PromptPackRefusal, match="missing"):
        record_prompt_pack(tmp_path)


def test_a_changed_prompt_is_refused(tmp_path: Path) -> None:
    _pack(tmp_path)
    prompt = tmp_path / "prompts" / "implementation" / "00_READ_ME_FIRST.md"
    prompt.write_bytes(b"changed\n")

    with pytest.raises(PromptPackRefusal, match="hash"):
        record_prompt_pack(tmp_path)


def test_an_untracked_prompt_is_refused(tmp_path: Path) -> None:
    _pack(tmp_path, track=False)

    with pytest.raises(PromptPackRefusal, match="tracked"):
        record_prompt_pack(tmp_path)


def _pack(path: Path, *, present: bool = True, track: bool = True) -> None:
    pack = path / "prompts" / "implementation"
    pack.mkdir(parents=True)
    body = b"stored prompt\n"
    digest = hashlib.sha256(body).hexdigest()
    files = [{"name": "00_READ_ME_FIRST.md", "bytes": len(body), "sha256": digest}]
    (pack / "MANIFEST.json").write_text(
        json.dumps({"files": files}) + "\n",
        encoding="utf-8",
    )
    (pack / "TRACEABILITY.json").write_text(
        json.dumps({"file_count": 1, "files": files}) + "\n",
        encoding="utf-8",
    )
    if present:
        (pack / "00_READ_ME_FIRST.md").write_bytes(body)
    subprocess.run(["git", "-C", str(path), "init", "-b", "fixture"], check=True, timeout=30)
    if track:
        subprocess.run(["git", "-C", str(path), "add", "--", "."], check=True, timeout=30)
