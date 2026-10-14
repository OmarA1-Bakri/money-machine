"""Crafted gift PDFs for link, metadata, and object-stream checks."""

from __future__ import annotations

import zlib

from money_machine.assets.pdf_reader import PdfDocument, PdfRef


def classic_pdf(objects: dict[int, bytes], *, info: int | None = None) -> bytes:
    """Build a classic cross-reference PDF. Object 1 is the catalog."""
    if not objects or min(objects) < 1:
        raise ValueError("pdf objects")
    highest = max(objects)
    chunks = [b"%PDF-1.4\n"]
    offsets = [0] * (highest + 1)
    for number in range(1, highest + 1):
        body = objects.get(number)
        if body is None:
            continue
        offsets[number] = sum(len(chunk) for chunk in chunks)
        chunks.append(body if body.endswith(b"\n") else body + b"\n")
    xref_at = sum(len(chunk) for chunk in chunks)
    rows = [f"xref\n0 {highest + 1}\n", "0000000000 65535 f \n"]
    for number in range(1, highest + 1):
        if number not in objects:
            rows.append("0000000000 65535 f \n")
            continue
        rows.append(f"{offsets[number]:010d} 00000 n \n")
    info_part = f" /Info {info} 0 R" if info is not None else ""
    trailer = (
        f"trailer\n<< /Size {highest + 1} /Root 1 0 R{info_part} >>\nstartxref\n{xref_at}\n%%EOF\n"
    )
    return b"".join(chunks) + "".join(rows).encode("ascii") + trailer.encode("ascii")


def _dict_object(number: int, body: str) -> bytes:
    return f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")


def _stream_object(number: int, payload: bytes) -> bytes:
    header = f"{number} 0 obj\n<< /Type /Metadata /Subtype /XML /Length {len(payload)} >>\n"
    return header.encode("ascii") + b"stream\n" + payload + b"\nendstream\nendobj\n"


def titled_page(title: str) -> bytes:
    """One page whose info title is ``title`` and which has no annotations."""
    literal = _pdf_literal(title).decode("ascii")
    return classic_pdf(
        {
            1: _dict_object(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _dict_object(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _dict_object(3, "<< /Type /Page /Parent 2 0 R >>"),
            4: _dict_object(4, f"<< /Title {literal} >>"),
        },
        info=4,
    )


def percent_packet() -> bytes:
    """Info title and XMP both carry ``x%2Ecom``. The page has no annotations."""
    packet = b"<?xpacket begin='x'?><dc:title>x%2Ecom</dc:title>"
    return classic_pdf(
        {
            1: _dict_object(1, "<< /Type /Catalog /Pages 2 0 R /Metadata 5 0 R >>"),
            2: _dict_object(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _dict_object(3, "<< /Type /Page /Parent 2 0 R >>"),
            4: _dict_object(4, "<< /Title (x%2Ecom) >>"),
            5: _stream_object(5, packet),
        },
        info=4,
    )


def untyped_page() -> bytes:
    """A page dictionary with no ``/Type /Page``."""
    return classic_pdf(
        {
            1: _dict_object(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _dict_object(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _dict_object(3, "<< /Parent 2 0 R >>"),
        }
    )


def looping_kids() -> bytes:
    """A page tree whose ``/Kids`` array contains its own page node."""
    return classic_pdf(
        {
            1: _dict_object(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _dict_object(2, "<< /Type /Pages /Kids [2 0 R] /Count 1 >>"),
        }
    )


def reference_chain(length: int) -> bytes:
    """Object 1 is the first of ``length`` references. The next object is a dictionary."""
    objects = {
        number: f"{number} 0 obj\n{number + 1} 0 R\nendobj\n".encode("ascii")
        for number in range(1, length + 1)
    }
    objects[length + 1] = _dict_object(length + 1, "<< /Done true >>")
    return classic_pdf(objects)


def mail_link() -> bytes:
    """A ``/Link`` whose URI is ``mailto:a`` and whose array is direct."""
    return classic_pdf(
        {
            1: _dict_object(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _dict_object(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _dict_object(3, "<< /Type /Page /Parent 2 0 R /Annots [4 0 R] >>"),
            4: _dict_object(4, "<< /Subtype /Link /A << /S /URI /URI (mailto:a) >> >>"),
        }
    )


def indirect_link() -> bytes:
    """A ``/Link`` to ``https://x.com`` behind an indirect ``/Annots`` array."""
    return classic_pdf(
        {
            1: _dict_object(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _dict_object(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _dict_object(3, "<< /Type /Page /Parent 2 0 R /Annots 4 0 R >>"),
            4: _dict_object(4, "[5 0 R]"),
            5: _dict_object(5, "<< /Subtype /Link /A << /S /URI /URI (https://x.com) >> >>"),
        }
    )


def nested_kids_link() -> bytes:
    """A ``/Link`` to ``https://x.com`` behind nested indirect ``/Kids`` arrays."""
    return classic_pdf(
        {
            1: _dict_object(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _dict_object(2, "<< /Type /Pages /Kids 3 0 R /Count 1 >>"),
            3: _dict_object(3, "[4 0 R]"),
            4: _dict_object(4, "<< /Type /Pages /Parent 2 0 R /Kids 5 0 R /Count 1 >>"),
            5: _dict_object(5, "[6 0 R]"),
            6: _dict_object(6, "<< /Type /Page /Parent 4 0 R /Annots [7 0 R] >>"),
            7: _dict_object(7, "<< /Subtype /Link /A << /S /URI /URI (https://x.com) >> >>"),
        }
    )


def metadata_packet() -> bytes:
    """XMP carrying ``https://x.com``. The info dictionary does not."""
    packet = b"<?xpacket begin='x'?><dc:description>https://x.com</dc:description>"
    return classic_pdf(
        {
            1: _dict_object(1, "<< /Type /Catalog /Metadata 3 0 R >>"),
            2: _dict_object(2, "<< /Creator (Chromium) >>"),
            3: _stream_object(3, packet),
        },
        info=2,
    )


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
