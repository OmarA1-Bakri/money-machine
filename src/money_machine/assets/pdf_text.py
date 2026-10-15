"""Painted page text. Link checks live in ``pdf_objects``."""

from __future__ import annotations

import re

from money_machine.assets.pdf_objects import read_dict, read_pages
from money_machine.assets.pdf_reader import (
    CMap,
    PdfDocument,
    PdfName,
    PdfObject,
    PdfReader,
    PdfStream,
    PdfText,
    token_boundary,
)


def page_texts(pdf: bytes) -> tuple[str, ...]:
    """Painted text of each page, in page-tree order."""
    doc = PdfDocument(pdf)
    root = read_dict(doc.deref(doc.trailer.get("Root")))
    pages = read_pages(doc, root.get("Pages"))
    return tuple(_operators(_page_bytes(doc, page), _fonts(doc, page)) for page in pages)


def _cmap(data: bytes) -> CMap:
    text = data.decode("latin-1")
    width = 2
    space = re.search(r"begincodespacerange(.*?)endcodespacerange", text, re.S)
    if space is not None:
        codes = re.findall(r"<([0-9A-Fa-f]+)>", space.group(1))
        if codes:
            width = max(1, len(codes[0]) // 2)
    mapping: dict[int, str] = {}
    for block in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
        for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            mapping[int(src, 16)] = bytes.fromhex(dst).decode("utf-16-be", errors="replace")
    for block in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
        pairs = re.findall(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(?:<([0-9A-Fa-f]+)>|\[(.*?)\])",
            block,
            re.S,
        )
        for src, end, single, array in pairs:
            if single:
                target = bytes.fromhex(single)
                for code in range(int(src, 16), int(end, 16) + 1):
                    mapping[code] = target.decode("utf-16-be", errors="replace")
                    last = int.from_bytes(target[-2:], "big") + 1
                    target = target[:-2] + last.to_bytes(2, "big")
                continue
            code = int(src, 16)
            for dst in re.findall(r"<([0-9A-Fa-f]+)>", array):
                mapping[code] = bytes.fromhex(dst).decode("utf-16-be", errors="replace")
                code += 1
    return CMap(width, mapping)


def _fonts(doc: PdfDocument, page: dict[str, PdfObject]) -> dict[str, CMap]:
    node: PdfObject | None = page
    resources: dict[str, PdfObject] = {}
    for _ in range(6):
        current = read_dict(doc.deref(node))
        if "Resources" in current:
            resources = read_dict(doc.deref(current.get("Resources")))
            break
        node = current.get("Parent")
    fonts = read_dict(doc.deref(resources.get("Font")))
    decoded: dict[str, CMap] = {}
    for name, ref in fonts.items():
        font = read_dict(doc.deref(ref))
        tounicode = doc.deref(font.get("ToUnicode"))
        if isinstance(tounicode, PdfStream):
            decoded[name] = _cmap(tounicode.data)
    return decoded


def _page_bytes(doc: PdfDocument, page: dict[str, PdfObject]) -> bytes:
    contents = doc.deref(page.get("Contents"))
    if isinstance(contents, PdfStream):
        return contents.data
    if not isinstance(contents, tuple):
        return b""
    parts = [
        item.data for item in (doc.deref(part) for part in contents) if isinstance(item, PdfStream)
    ]
    return b"\n".join(parts)


def _show(value: PdfObject, cmap: CMap | None) -> str:
    if not isinstance(value, PdfText):
        return ""
    if value.hex_digits is None or cmap is None:
        return value.text
    step = cmap.width * 2
    chars: list[str] = []
    digits = value.hex_digits
    for index in range(0, len(digits), step):
        chars.append(cmap.codes.get(int(digits[index : index + step], 16), ""))
    return "".join(chars)


def _operators(content: bytes, fonts: dict[str, CMap]) -> str:
    reader = PdfReader(content)
    stack: list[PdfObject] = []
    pieces: list[str] = []
    current: CMap | None = None
    while reader.i < reader.n:
        reader.skip()
        if reader.i >= reader.n:
            break
        byte = reader.data[reader.i]
        if token_boundary(byte) or chr(byte).isdigit() or byte in b"+-.":
            stack.append(reader.value())
            continue
        word = reader.word().decode("latin-1")
        if word == "Tj" and stack:
            pieces.append(_show(stack.pop(), current))
        elif word == "TJ" and stack:
            array = stack.pop()
            if isinstance(array, tuple):
                pieces.extend(_show(item, current) for item in array)
        elif word == "'" and stack:
            pieces.append(_show(stack.pop(), current))
        elif word == "Tf" and len(stack) >= 2:
            stack.pop()
            name = stack.pop()
            if isinstance(name, PdfName):
                current = fonts.get(name.value)
        else:
            stack.clear()
    return "".join(pieces)
