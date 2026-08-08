from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
PRIVATE_PDF = "The-Hands-Off-Money-Machine-Playbook.pdf"
WORKBOOK = ROOT / "hands-off-money-machine-full-implementation-workbook.md"
PROMPTS = ROOT / "prompts" / "implementation"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_registered_sources_remain_byte_identical() -> None:
    register = json.loads((ROOT / "docs/source/CANONICAL_SOURCE_REGISTER.json").read_text())
    assert register["schema_version"] == 1
    assert not (ROOT / "docs/source/POST_RENAME_SOURCE_RECEIPT.json").exists()
    assert "*.pdf" in (ROOT / ".gitignore").read_text().splitlines()
    receipt_path = ".omx/ultragoal/source-preservation-receipt.json"
    repository = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if repository.returncode == 0:
        ignored = subprocess.run(
            ["git", "check-ignore", receipt_path],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert ignored.stdout.strip() == receipt_path
    else:
        assert ".omx/" in (ROOT / ".gitignore").read_text().splitlines()
    for source in register["sources"]:
        path = ROOT / source["path"]
        if path.is_file():
            assert path.stat().st_size == source["bytes"]
            assert digest(path) == source["sha256"]
        else:
            assert source["path"] == PRIVATE_PDF
            assert source["required_in_clean_clone"] is False


def test_prompt_pack_matches_appendix_and_is_deterministic(tmp_path: Path) -> None:
    command = [
        sys.executable,
        str(ROOT / "scripts/extract_prompt_pack.py"),
        "--workbook",
        str(WORKBOOK),
        "--output",
        str(tmp_path),
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)
    assert "verified 21 prompt files" in first.stdout
    trace = json.loads((tmp_path / "TRACEABILITY.json").read_text())
    assert trace["file_count"] == 21
    assert (
        trace["appendix_manifest_sha256"]
        == "0a559cdda4d1cdb837883b02c8e2c8d7c7495176093245198b66fa1f91c0a475"
    )
    assert len(list(tmp_path.glob("*.md"))) == 21
    for entry in trace["files"]:
        generated = tmp_path / entry["name"]
        assert generated.stat().st_size == entry["bytes"]
        assert digest(generated) == entry["sha256"]
        assert generated.read_bytes().count(b"\n") == entry["lines"]
        assert entry["source_start_line"] <= entry["source_end_line"]
        assert generated.read_bytes() == (PROMPTS / entry["name"]).read_bytes()
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    subprocess.run(command, check=True, capture_output=True, text=True)
    after = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    assert after == before
    subprocess.run([*command, "--check"], check=True, capture_output=True, text=True)


def test_appendix_b_is_an_independent_canonical_register() -> None:
    source = WORKBOOK.read_bytes()
    appendix = source[source.index(b"# Appendix B") :]
    matches = re.finditer(
        rb"^\| `(?P<name>[^`]+)` \| `(?P<sha256>[0-9a-f]{64})` \| "
        rb"(?P<bytes>[0-9,]+) \| (?P<lines>[0-9,]+) \|$",
        appendix,
        re.MULTILINE,
    )
    rows = {
        match.group("name").decode(): {
            "sha256": match.group("sha256").decode(),
            "bytes": int(match.group("bytes").replace(b",", b"")),
            "lines": int(match.group("lines").replace(b",", b"")),
        }
        for match in matches
    }
    assert len(rows) == 22
    assert rows["MANIFEST.json"]["lines"] == 111
    for name, registered in rows.items():
        content = (PROMPTS / name).read_bytes()
        assert digest(PROMPTS / name) == registered["sha256"]
        assert len(content) == registered["bytes"]
        assert content.count(b"\n") == registered["lines"]


def test_canonical_source_verifier_reads_pdf_or_supports_clean_clone(tmp_path: Path) -> None:
    verifier = ROOT / "scripts/verify_canonical_sources.py"
    canonical_command = [sys.executable, str(verifier), "--root", str(ROOT), "--json"]
    if (ROOT / PRIVATE_PDF).is_file():
        result = subprocess.run(canonical_command, check=True, capture_output=True, text=True)
        proof = json.loads(result.stdout)
        assert proof["pdf_present"] is True
        assert proof["extracted_pages"] == 82
        assert proof["nonempty_pages"] == 82
        assert proof["text_bearing_pages"] == 82

    (tmp_path / "docs/source").mkdir(parents=True)
    for relative in (
        Path("docs/source/CANONICAL_SOURCE_REGISTER.json"),
        Path("docs/source/PDF_PAGE_COVERAGE.md"),
        Path("hands-off-money-machine-full-implementation-workbook.md"),
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    clean = subprocess.run(
        [
            sys.executable,
            str(verifier),
            "--root",
            str(tmp_path),
            "--allow-missing-private-pdf",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    clean_proof = json.loads(clean.stdout)
    assert clean_proof["pdf_present"] is False
    assert clean_proof["coverage_pages"] == 82


def test_every_appendix_file_has_one_copy_marker_pair() -> None:
    source = WORKBOOK.read_text()
    manifest = json.loads((PROMPTS / "MANIFEST.json").read_text())
    assert len(manifest["files"]) == 21
    for entry in manifest["files"]:
        name = re.escape(entry["name"])
        assert len(re.findall(rf"<!-- COPY START: {name} -->", source)) == 1
        assert len(re.findall(rf"<!-- COPY END: {name} -->", source)) == 1


def test_pdf_and_required_item_coverage_are_exhaustive() -> None:
    page_map = (ROOT / "docs/source/PDF_PAGE_COVERAGE.md").read_text()
    pages = [int(value) for value in re.findall(r"^\| (\d+) \|", page_map, re.MULTILINE)]
    assert pages == list(range(1, 83))

    chapter_map = (ROOT / "docs/playbook/CHAPTER_TO_CAPABILITY_MAP.md").read_text()
    observed_steps = set(re.findall(r"^\| ((?:12|13|14|15|16)\.\d+) \|", chapter_map, re.MULTILINE))
    expected_steps = {
        *(f"12.{n}" for n in range(1, 6)),
        *(f"13.{n}" for n in range(1, 7)),
        *(f"14.{n}" for n in range(1, 8)),
        *(f"15.{n}" for n in range(1, 9)),
        *(f"16.{n}" for n in range(1, 6)),
    }
    assert observed_steps == expected_steps

    prompt_map = (ROOT / "docs/playbook/PROMPT_LIBRARY_MAP.md").read_text()
    assert [int(value) for value in re.findall(r"^\| (\d+) \|", prompt_map, re.MULTILINE)] == list(
        range(1, 14)
    )
    workbook_map = (ROOT / "docs/playbook/WORKBOOK_DATA_MAP.md").read_text()
    assert [
        int(value) for value in re.findall(r"^\| (\d+) \|", workbook_map, re.MULTILINE)
    ] == list(range(1, 7))
