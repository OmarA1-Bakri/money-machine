"""Gift-PDF surfaces read by walking objects, not by searching bytes.

``link_annotations`` counts ``/Link`` annotations and returns ``/URI`` strings.
``delivery_link_uris`` is the same page walk for link validation. A link
annotation may only carry ``Type``, ``Subtype``, ``Rect``, ``Border``, ``F``,
and ``A``. The action may only carry ``Type``, ``S``, and ``URI``, ``/S``
must be ``/URI``, and the URI must be a direct string. A catalog
``/OpenAction``, ``/AA``, ``/AcroForm``, ``/Names /JavaScript``, or
``/Names /EmbeddedFiles`` is refused. Outlines are not walked.
"""

from __future__ import annotations

import re

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


def _pages(
    doc: PdfDocument,
    node: PdfObject | None,
    seen: frozenset[int] = frozenset(),
) -> tuple[dict[str, PdfObject], ...]:
    if isinstance(node, PdfRef):
        if node.number in seen:
            raise ValueError("pdf page")
        seen = seen | {node.number}
    found = doc.deref(node)
    page = _dict(found)
    if _name_is(page.get("Type"), "Page"):
        return (page,)
    kids = doc.deref(page.get("Kids"))
    if not isinstance(kids, tuple):
        raise ValueError("pdf page")
    return tuple(item for kid in kids for item in _pages(doc, kid, seen))


def _text_of(value: PdfObject | None) -> str | None:
    if isinstance(value, PdfText):
        return value.text
    return None


def link_annotations(pdf: bytes) -> tuple[int, tuple[str, ...]]:
    """Count ``/Link`` annotations and return each ``/URI`` string.

    The gift check uses this count. It does not refuse catalog actions.
    """
    doc = PdfDocument(pdf)
    root = _dict(doc.deref(doc.trailer.get("Root")))
    count = 0
    uris: list[str] = []
    for page in _pages(doc, root.get("Pages")):
        annots = doc.deref(page.get("Annots"))
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


_LINK_KEYS = frozenset({"Type", "Subtype", "Rect", "Border", "F", "A"})
_ACTION_KEYS = frozenset({"Type", "S", "URI"})


def delivery_link_uris(pdf: bytes) -> tuple[str, ...]:
    """Return each link URI from the page walk, or raise ``ValueError``.

    Annotation and action keys must be the Chromium set. ``/S`` must be
    ``/URI`` and the URI must be a direct string. A catalog ``/OpenAction``,
    ``/AA``, ``/AcroForm``, ``/Names /JavaScript``, or
    ``/Names /EmbeddedFiles`` is refused.
    """
    doc = PdfDocument(pdf)
    root = _dict(doc.deref(doc.trailer.get("Root")))
    if "OpenAction" in root or "AA" in root:
        raise ValueError("pdf catalog")
    if "AcroForm" in root:
        raise ValueError("pdf catalog")
    names = _dict(doc.deref(root.get("Names")))
    if "JavaScript" in names:
        raise ValueError("pdf catalog")
    if "EmbeddedFiles" in names:
        raise ValueError("pdf catalog")
    uris: list[str] = []
    for page in _pages(doc, root.get("Pages")):
        annots = doc.deref(page.get("Annots"))
        if not isinstance(annots, tuple):
            continue
        for item in annots:
            annot = _dict(doc.deref(item))
            if not _name_is(annot.get("Subtype"), "Link"):
                continue
            uris.append(_uri_action(doc, annot))
    return tuple(uris)


def _uri_action(doc: PdfDocument, annot: dict[str, PdfObject]) -> str:
    if not set(annot).issubset(_LINK_KEYS):
        raise ValueError("pdf link")
    action = _dict(doc.deref(annot.get("A")))
    if not set(action).issubset(_ACTION_KEYS):
        raise ValueError("pdf link")
    if not _name_is(action.get("S"), "URI"):
        raise ValueError("pdf link")
    uri = _text_of(action.get("URI"))
    if uri is None:
        raise ValueError("pdf link")
    return uri


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
