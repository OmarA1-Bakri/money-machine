#!/usr/bin/env python3
"""Extract the canonical implementation prompt pack from the workbook."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import TypedDict, cast

EXPECTED_WORKBOOK_SHA256 = "4dbecbb8ad6fdd9fe2323eb164ffd2d7c99143cf5de20de5ec98a1bdf90d7f2b"
INTEGRITY_ROW = re.compile(
    rb"^\| `(?P<name>[^`]+)` \| `(?P<sha256>[0-9a-f]{64})` \| "
    rb"(?P<bytes>[0-9,]+) \| (?P<lines>[0-9,]+) \|$",
    re.MULTILINE,
)


class ManifestEntry(TypedDict):
    name: str
    bytes: int
    sha256: str


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_block(source: bytes, name: str) -> tuple[bytes, int, int]:
    start_marker = f"<!-- COPY START: {name} -->".encode()
    end_marker = f"<!-- COPY END: {name} -->".encode()
    if source.count(start_marker) != 1 or source.count(end_marker) != 1:
        raise ValueError(f"{name}: expected exactly one matching marker pair")
    start = source.index(start_marker)
    content_start = start + len(start_marker)
    if source[content_start : content_start + 2] != b"\n\n":
        raise ValueError(f"{name}: COPY START must be followed by one blank line")
    content_start += 2
    end = source.index(end_marker)
    if source[end - 2 : end] != b"\n\n":
        raise ValueError(f"{name}: COPY END must be preceded by one blank line")
    content_end = end - 1
    if content_start >= content_end:
        raise ValueError(f"{name}: empty or reversed COPY block")
    content = source[content_start:content_end]
    start_line = source[:content_start].count(b"\n") + 1
    end_line = start_line + content.count(b"\n") - 1
    return content, start_line, end_line


def parse_integrity_register(source: bytes) -> dict[str, dict[str, object]]:
    """Parse Appendix B's independent canonical byte/hash/line assertions."""
    marker = b"# Appendix B \xe2\x80\x94 Workbook Integrity Register"
    if source.count(marker) != 1:
        raise ValueError("expected exactly one Appendix B integrity register")
    appendix = source[source.index(marker) :]
    rows: dict[str, dict[str, object]] = {}
    for match in INTEGRITY_ROW.finditer(appendix):
        name = match.group("name").decode()
        if name in rows:
            raise ValueError(f"Appendix B contains duplicate row: {name}")
        rows[name] = {
            "sha256": match.group("sha256").decode(),
            "bytes": int(match.group("bytes").replace(b",", b"")),
            "lines": int(match.group("lines").replace(b",", b"")),
        }
    if len(rows) != 22:
        raise ValueError("Appendix B must register 21 prompt files and MANIFEST.json")
    return rows


def validate_registered_content(name: str, content: bytes, registered: dict[str, object]) -> None:
    actual = {
        "sha256": sha256(content),
        "bytes": len(content),
        "lines": content.count(b"\n"),
    }
    if actual != registered:
        raise ValueError(f"{name}: extracted hash/bytes/lines differ from Appendix B")


def build(workbook: Path, output_dir: Path, check: bool) -> dict[str, object]:
    source = workbook.read_bytes()
    if sha256(source) != EXPECTED_WORKBOOK_SHA256:
        raise ValueError("workbook SHA-256 does not match the registered canonical source")
    manifest_bytes, _, _ = extract_block(source, "MANIFEST.json")
    integrity = parse_integrity_register(source)
    validate_registered_content("MANIFEST.json", manifest_bytes, integrity["MANIFEST.json"])
    manifest_value: object = json.loads(manifest_bytes)
    if not isinstance(manifest_value, dict):
        raise ValueError("Appendix A manifest must be a JSON object")
    manifest = cast(dict[str, object], manifest_value)
    entries_value = manifest.get("files")
    if not isinstance(entries_value, list) or len(entries_value) != 21:
        raise ValueError("Appendix A must list exactly 21 prompt files")
    entries: list[ManifestEntry] = []
    for entry_value in entries_value:
        if not isinstance(entry_value, dict):
            raise ValueError("Appendix A contains a non-object file entry")
        entry_object = cast(dict[str, object], entry_value)
        if not (
            isinstance(entry_object.get("name"), str)
            and isinstance(entry_object.get("bytes"), int)
            and isinstance(entry_object.get("sha256"), str)
        ):
            raise ValueError("Appendix A contains an invalid file entry")
        entries.append(cast(ManifestEntry, entry_object))
    manifest_names = {entry["name"] for entry in entries}
    if set(integrity) != manifest_names | {"MANIFEST.json"}:
        raise ValueError("Appendix A and Appendix B register different files")

    trace_files: list[dict[str, object]] = []
    expected_names: set[str] = set()
    for entry in entries:
        name = entry["name"]
        if not isinstance(name, str) or not name.endswith(".md") or "/" in name:
            raise ValueError(f"unsafe manifest filename: {name!r}")
        if name in expected_names:
            raise ValueError(f"duplicate manifest filename: {name}")
        expected_names.add(name)
        content, start_line, end_line = extract_block(source, name)
        digest = sha256(content)
        if len(content) != entry["bytes"] or digest != entry["sha256"]:
            raise ValueError(f"{name}: extracted bytes/hash differ from Appendix A")
        validate_registered_content(name, content, integrity[name])
        trace_files.append(
            {
                "name": name,
                "source_start_line": start_line,
                "source_end_line": end_line,
                "lines": integrity[name]["lines"],
                "bytes": len(content),
                "sha256": digest,
            }
        )
        destination = output_dir / name
        if check:
            if not destination.is_file() or destination.read_bytes() != content:
                raise ValueError(f"{name}: generated file is missing or stale")
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)

    trace: dict[str, object] = {
        "source": str(workbook),
        "source_sha256": EXPECTED_WORKBOOK_SHA256,
        "appendix_manifest_sha256": sha256(manifest_bytes),
        "file_count": len(trace_files),
        "files": trace_files,
    }
    generated = {
        "MANIFEST.json": manifest_bytes,
        "TRACEABILITY.json": (json.dumps(trace, indent=2) + "\n").encode(),
    }
    for name, content in generated.items():
        destination = output_dir / name
        if check:
            if not destination.is_file() or destination.read_bytes() != content:
                raise ValueError(f"{name}: generated metadata is missing or stale")
        else:
            destination.write_bytes(content)

    actual_markdown = {path.name for path in output_dir.glob("*.md")}
    if actual_markdown != expected_names:
        raise ValueError("output directory contains a missing or unexpected Markdown prompt")
    return trace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workbook",
        type=Path,
        default=Path("hands-off-money-machine-full-implementation-workbook.md"),
    )
    parser.add_argument("--output", type=Path, default=Path("prompts/implementation"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    trace = build(args.workbook, args.output, args.check)
    print(f"verified {trace['file_count']} prompt files against Appendix A")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
