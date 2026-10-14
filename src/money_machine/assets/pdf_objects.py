"""Gift-PDF surfaces read by walking objects, not by searching bytes.

Link annotations are ``/Annot`` ``/Link`` ``/URI`` values. Document info strings
and catalog XMP are the metadata surface. ``/OpenAction``, ``/AA``, and outlines
are not walked.
"""

from __future__ import annotations

import re
import zlib

from money_machine.assets.pdf_reader import (
    CMap,
    PdfDocument,
    PdfName,
    PdfObject,
    PdfReader,
    PdfRef,
    PdfStream,
    PdfText,
    token_boundary,
)


def _name_is(value: PdfObject | None, expected: str) -> bool:
    return isinstance(value, PdfName) and value.value == expected


def _dict(value: PdfObject | None) -> dict[str, PdfObject]:
    if isinstance(value, dict):
        return value
    return {}


def _pages(doc: PdfDocument, node: PdfObject | None) -> tuple[dict[str, PdfObject], ...]:
    found = doc.deref(node)
    page = _dict(found)
    if _name_is(page.get("Type"), "Page"):
        return (page,)
    kids = page.get("Kids")
    if not isinstance(kids, tuple):
        return ()
    return tuple(item for kid in kids for item in _pages(doc, kid))


def _text_of(value: PdfObject | None) -> str | None:
    if isinstance(value, PdfText):
        return value.text
    return None


def link_annotations(pdf: bytes) -> tuple[int, tuple[str, ...]]:
    """Count ``/Link`` annotations and return each ``/URI`` string."""
    doc = PdfDocument(pdf)
    root = _dict(doc.deref(doc.trailer.get("Root")))
    count = 0
    uris: list[str] = []
    for page in _pages(doc, root.get("Pages")):
        annots = page.get("Annots")
        if not isinstance(annots, tuple):
            continue
        for item in annots:
            annot = _dict(doc.deref(item))
            if not _name_is(annot.get("Subtype"), "Link"):
                continue
            count += 1
            action = _dict(doc.deref(annot.get("A")))
            uri = _text_of(annot.get("URI"))
            if uri is None:
                uri = _text_of(action.get("URI"))
            if uri is not None:
                uris.append(uri)
    return count, tuple(uris)


def document_strings(pdf: bytes) -> tuple[str, ...]:
    """Info-dictionary strings and the catalog XMP packet, when one is present."""
    doc = PdfDocument(pdf)
    found: list[str] = []
    info = _dict(doc.deref(doc.trailer.get("Info")))
    for value in info.values():
        text = _text_of(doc.deref(value))
        if text is not None:
            found.append(text)
    root = _dict(doc.deref(doc.trailer.get("Root")))
    metadata = doc.deref(root.get("Metadata"))
    if isinstance(metadata, PdfStream):
        found.append(metadata.data.decode("utf-8", errors="replace"))
    return tuple(found)


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
        current = _dict(doc.deref(node))
        if "Resources" in current:
            resources = _dict(doc.deref(current.get("Resources")))
            break
        node = current.get("Parent")
    fonts = _dict(doc.deref(resources.get("Font")))
    decoded: dict[str, CMap] = {}
    for name, ref in fonts.items():
        font = _dict(doc.deref(ref))
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


def page_texts(pdf: bytes) -> tuple[str, ...]:
    """Painted text of each page, in page-tree order."""
    doc = PdfDocument(pdf)
    root = _dict(doc.deref(doc.trailer.get("Root")))
    pages = _pages(doc, root.get("Pages"))
    return tuple(_operators(_page_bytes(doc, page), _fonts(doc, page)) for page in pages)


def _pdf_literal(value: str) -> bytes:
    escaped = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"({escaped})".encode("ascii")


def embed_info_title(pdf: bytes, title: str) -> bytes:
    """Point ``/Info`` at a title that exists only inside a compressed object stream."""
    doc = PdfDocument(pdf)
    root = doc.trailer.get("Root")
    if not isinstance(root, PdfRef):
        raise ValueError("pdf root")
    info_num = max(doc.entries, default=0) + 1
    stream_num = info_num + 1
    xref_num = info_num + 2
    header = f"{info_num} 0\n".encode("ascii")
    body = b"<< /Title " + _pdf_literal(title) + b" >>"
    compressed = zlib.compress(header + body)
    base = pdf if pdf.endswith(b"\n") else pdf + b"\n"
    stream_at = len(base)
    stream = (
        (
            f"{stream_num} 0 obj\n<< /Type /ObjStm /N 1 /First {len(header)} "
            f"/Filter /FlateDecode /Length {len(compressed)} >>\nstream\n"
        ).encode("ascii")
        + compressed
        + b"\nendstream\nendobj\n"
    )
    base += stream
    xref_at = len(base)
    blob = bytearray()

    def _add(kind: int, left: int, right: int) -> None:
        blob.append(kind)
        blob.extend(left.to_bytes(4, "big"))
        blob.extend(right.to_bytes(2, "big"))

    _add(0, 0, 65535)
    for number in range(1, info_num):
        entry = doc.entries.get(number)
        if entry is None:
            _add(0, 0, 65535)
        elif entry.kind == "plain":
            _add(1, entry.a, entry.b)
        else:
            _add(2, entry.a, entry.b)
    _add(2, stream_num, 0)
    _add(1, stream_at, 0)
    _add(1, xref_at, 0)
    size = xref_num + 1
    header_text = (
        f"{xref_num} 0 obj\n<< /Type /XRef /Size {size} /W [1 4 2] "
        f"/Root {root.number} {root.generation} R /Info {info_num} 0 R "
        f"/Length {len(blob)} >>\nstream\n"
    )
    base += header_text.encode("ascii") + bytes(blob) + b"\nendstream\nendobj\n"
    base += f"startxref\n{xref_at}\n%%EOF\n".encode("ascii")
    return base
