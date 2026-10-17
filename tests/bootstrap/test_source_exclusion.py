"""The private source PDF is ignored and a stage request is refused."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from money_machine.deploy.source_exclusion import (
    SourceExclusionRefusal,
    record_source_exclusion,
    refuse_pdf_stage,
)

ROOT = Path(__file__).parents[2]
_PDF_NAME = "The-Hands-Off-Money-Machine-Playbook.pdf"


def test_the_private_source_pdf_is_excluded() -> None:
    recorded = record_source_exclusion(ROOT)

    assert recorded.name == _PDF_NAME
    assert recorded.ignored is True
    assert recorded.policy == "ignored_private_source"
    assert recorded.tracked_pdfs == ()


def test_staging_the_playbook_is_refused() -> None:
    with pytest.raises(SourceExclusionRefusal, match="stage"):
        refuse_pdf_stage(f"private/source/{_PDF_NAME}")


def test_a_non_pdf_path_is_not_a_stage_refusal() -> None:
    refuse_pdf_stage("docs/source/SOURCE_REGISTER.md")


def test_a_tracked_pdf_is_refused(tmp_path: Path) -> None:
    _repo(tmp_path)
    pdf = tmp_path / "notes.pdf"
    pdf.write_bytes(b"%PDF-1.1\n")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "-f", "--", "notes.pdf"],
        check=True,
        timeout=30,
    )

    with pytest.raises(SourceExclusionRefusal, match="tracked"):
        record_source_exclusion(tmp_path)


def test_a_missing_ignore_rule_is_refused(tmp_path: Path) -> None:
    _repo(tmp_path, ignore="*.md\n")

    with pytest.raises(SourceExclusionRefusal, match="ignored"):
        record_source_exclusion(tmp_path)


def test_a_trackable_register_policy_is_refused(tmp_path: Path) -> None:
    _repo(tmp_path, policy="registered_source")

    with pytest.raises(SourceExclusionRefusal, match="policy"):
        record_source_exclusion(tmp_path)


def _repo(
    path: Path,
    *,
    ignore: str = "*.pdf\nprivate/source/*\n",
    policy: str = "ignored_private_source",
) -> None:
    source = path / "docs" / "source"
    source.mkdir(parents=True)
    register = {
        "sources": [
            {
                "path": _PDF_NAME,
                "git_policy": policy,
                "required_in_clean_clone": False,
            }
        ]
    }
    (source / "CANONICAL_SOURCE_REGISTER.json").write_text(
        json.dumps(register) + "\n",
        encoding="utf-8",
    )
    (path / ".gitignore").write_text(ignore, encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "init", "-b", "fixture"], check=True, timeout=30)
