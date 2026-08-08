#!/usr/bin/env python3
"""Verify canonical source identities and copyright-safe PDF page coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

REGISTER = Path("docs/source/CANONICAL_SOURCE_REGISTER.json")
COVERAGE = Path("docs/source/PDF_PAGE_COVERAGE.md")
PRIVATE_PDF = "The-Hands-Off-Money-Machine-Playbook.pdf"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class PdfProof:
    pages: int
    nonempty_pages: int
    text_bearing_pages: int


class SourceEntry(TypedDict, total=False):
    path: str
    role: str
    sha256: str
    bytes: int
    kind: str
    pages: int
    lines: int
    required_in_clean_clone: bool
    git_policy: str


class ClassicPdf:
    """Small, strict reader for the canonical classic-xref PDF."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        matches = list(re.finditer(rb"startxref\s+(\d+)\s+%%EOF", data))
        if not matches:
            raise ValueError("PDF has no terminal startxref")
        self.xref_offset = int(matches[-1].group(1))
        self.offsets = self._parse_xref()

    def _parse_xref(self) -> dict[int, int]:
        position = self.xref_offset
        if self.data[position : position + 5] != b"xref\n":
            raise ValueError("PDF must use a canonical classic xref table")
        position += 5
        offsets: dict[int, int] = {}
        while self.data[position : position + 7] != b"trailer":
            header_end = self.data.index(b"\n", position)
            header = self.data[position:header_end].strip().split()
            if len(header) != 2:
                raise ValueError("malformed xref subsection")
            first, count = (int(value) for value in header)
            position = header_end + 1
            for object_number in range(first, first + count):
                line_end = self.data.index(b"\n", position)
                line = self.data[position:line_end].strip().split()
                position = line_end + 1
                if len(line) != 3:
                    raise ValueError("malformed xref entry")
                if line[2] == b"n":
                    offsets[object_number] = int(line[0])
        if not offsets:
            raise ValueError("PDF xref contains no in-use objects")
        return offsets

    def object(self, object_number: int) -> bytes:
        try:
            start = self.offsets[object_number]
        except KeyError as error:
            raise ValueError(f"missing PDF object {object_number}") from error
        later = [offset for offset in self.offsets.values() if offset > start]
        end = min(later, default=self.xref_offset)
        value = self.data[start:end]
        if not value.startswith(f"{object_number} 0 obj".encode()):
            raise ValueError(f"xref mismatch for PDF object {object_number}")
        return value

    def root_pages(self) -> int:
        trailer_start = self.data.index(b"trailer", self.xref_offset)
        trailer = self.data[trailer_start:]
        root_match = re.search(rb"/Root\s+(\d+)\s+0\s+R", trailer)
        if root_match is None:
            raise ValueError("PDF trailer has no root catalog")
        catalog = self.object(int(root_match.group(1)))
        pages_match = re.search(rb"/Pages\s+(\d+)\s+0\s+R", catalog)
        if pages_match is None:
            raise ValueError("PDF catalog has no page tree")
        return int(pages_match.group(1))

    def page_objects(self, object_number: int) -> list[int]:
        value = self.object(object_number)
        if re.search(rb"/Type\s*/Page(?!s)\b", value):
            return [object_number]
        if not re.search(rb"/Type\s*/Pages\b", value):
            raise ValueError(f"page tree object {object_number} has no page type")
        kids_match = re.search(rb"/Kids\s*\[(.*?)\]", value, re.DOTALL)
        if kids_match is None:
            raise ValueError(f"page tree object {object_number} has no kids")
        children = [int(item) for item in re.findall(rb"(\d+)\s+0\s+R", kids_match.group(1))]
        if not children:
            raise ValueError(f"page tree object {object_number} has no child references")
        pages: list[int] = []
        for child in children:
            pages.extend(self.page_objects(child))
        return pages

    def decoded_stream(self, object_number: int) -> bytes:
        value = self.object(object_number)
        stream_match = re.search(rb"stream\r?\n", value)
        if stream_match is None:
            raise ValueError(f"content object {object_number} has no stream")
        header = value[: stream_match.start()]
        length_match = re.search(rb"/Length\s+(\d+)\b", header)
        if length_match is None:
            raise ValueError(f"content object {object_number} has no direct length")
        length = int(length_match.group(1))
        encoded = value[stream_match.end() : stream_match.end() + length]
        if len(encoded) != length:
            raise ValueError(f"content object {object_number} is truncated")
        if b"/FlateDecode" in header:
            try:
                return zlib.decompress(encoded)
            except zlib.error as error:
                raise ValueError(
                    f"content object {object_number} has invalid deflate data"
                ) from error
        if b"/Filter" in header:
            raise ValueError(f"content object {object_number} uses an unsupported filter")
        return encoded


def verify_pdf(path: Path, expected_pages: int) -> PdfProof:
    pdf = ClassicPdf(path.read_bytes())
    pages = pdf.page_objects(pdf.root_pages())
    if len(pages) != expected_pages or len(set(pages)) != expected_pages:
        raise ValueError(f"PDF page tree is not an ordered unique set of {expected_pages} pages")
    nonempty = 0
    text_bearing = 0
    for page_object in pages:
        page = pdf.object(page_object)
        contents_match = re.search(rb"/Contents\s+(\d+)\s+0\s+R", page)
        if contents_match is None:
            raise ValueError(f"page object {page_object} has no single content stream")
        content = pdf.decoded_stream(int(contents_match.group(1)))
        if content.strip():
            nonempty += 1
        if b"BT" in content and re.search(rb"(?:^|\s)(?:Tj|TJ)(?=\s|$)", content):
            text_bearing += 1
    if nonempty != expected_pages or text_bearing != expected_pages:
        raise ValueError("PDF does not have nonempty text-bearing content on every ordered page")
    return PdfProof(len(pages), nonempty, text_bearing)


def verify(root: Path, allow_missing_private_pdf: bool) -> dict[str, object]:
    register_value: object = json.loads((root / REGISTER).read_text(encoding="utf-8"))
    if not isinstance(register_value, dict):
        raise ValueError("canonical source register must be a JSON object")
    register = cast(dict[str, object], register_value)
    sources_value = register.get("sources")
    if (
        register.get("schema_version") != 1
        or not isinstance(sources_value, list)
        or len(sources_value) != 2
    ):
        raise ValueError("canonical source register must contain exactly two schema-v1 sources")
    sources: list[SourceEntry] = []
    for source_value in sources_value:
        if not isinstance(source_value, dict):
            raise ValueError("canonical source register contains a non-object source")
        source_object = cast(dict[str, object], source_value)
        if not (
            isinstance(source_object.get("path"), str)
            and isinstance(source_object.get("sha256"), str)
            and isinstance(source_object.get("bytes"), int)
        ):
            raise ValueError("canonical source register contains an invalid source")
        sources.append(cast(SourceEntry, source_object))
    registered = {entry["path"]: entry for entry in sources}
    if set(registered) != {PRIVATE_PDF, "hands-off-money-machine-full-implementation-workbook.md"}:
        raise ValueError("canonical source register contains an unexpected source set")

    workbook_entry = registered["hands-off-money-machine-full-implementation-workbook.md"]
    workbook = root / str(workbook_entry["path"])
    if not workbook.is_file():
        raise ValueError("registered implementation workbook is missing")
    if workbook.stat().st_size != int(workbook_entry["bytes"]) or sha256(workbook) != str(
        workbook_entry["sha256"]
    ):
        raise ValueError("implementation workbook identity does not match its registration")
    if workbook.read_bytes().count(b"\n") != int(workbook_entry["lines"]):
        raise ValueError("implementation workbook line count does not match its registration")

    pdf_entry = registered[PRIVATE_PDF]
    pdf = root / PRIVATE_PDF
    proof: PdfProof | None = None
    if pdf.is_file():
        if pdf.stat().st_size != int(pdf_entry["bytes"]) or sha256(pdf) != str(pdf_entry["sha256"]):
            raise ValueError("private PDF identity does not match its registration")
        proof = verify_pdf(pdf, int(pdf_entry["pages"]))
    elif not allow_missing_private_pdf:
        raise ValueError(
            "private PDF is missing; use --allow-missing-private-pdf only in a clean clone"
        )
    elif pdf_entry.get("required_in_clean_clone") is not False:
        raise ValueError("missing private PDF is not registered as clean-clone optional")

    coverage = (root / COVERAGE).read_text(encoding="utf-8")
    pages = [int(value) for value in re.findall(r"^\| (\d+) \|", coverage, re.MULTILINE)]
    expected_pages = list(range(1, int(pdf_entry["pages"]) + 1))
    if pages != expected_pages:
        raise ValueError("PDF coverage map is not continuous and ordered from 1 through 82")

    return {
        "status": "verified",
        "pdf_present": pdf.is_file(),
        "registered_sources": len(registered),
        "coverage_pages": len(pages),
        "extracted_pages": proof.pages if proof else None,
        "nonempty_pages": proof.nonempty_pages if proof else None,
        "text_bearing_pages": proof.text_bearing_pages if proof else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--allow-missing-private-pdf", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify(args.root.resolve(), args.allow_missing_private_pdf)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        mode = "canonical PDF" if result["pdf_present"] else "clean-clone register"
        print(f"verified {mode}: {result['coverage_pages']} ordered coverage pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
