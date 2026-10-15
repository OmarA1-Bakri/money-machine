"""A trailer /Prev is refused. The offset is not followed."""

from __future__ import annotations

import pytest

from money_machine.assets.pdf_reader import PdfDocument, PdfName, PdfRef
from tests.unit.assets.gift_pdf_craft import classic_pdf

_CATALOG = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
_PAGES = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 /Mark /Original >>\nendobj\n"
_PAGE = b"3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n"


def _assert_prev(pdf: bytes) -> None:
    with pytest.raises(ValueError) as caught:
        PdfDocument(pdf)
    assert caught.value.args == ("pdf prev",)


def _xref_row(kind: int, left: int, right: int) -> bytes:
    return bytes([kind]) + left.to_bytes(4, "big") + right.to_bytes(2, "big")


def _xref_stream_pdf(dict_tail: str) -> bytes:
    """An xref stream whose dictionary carries ``dict_tail``."""
    header = b"%PDF-1.5\n"
    catalog_at = len(header)
    body = header + _CATALOG
    stream_at = len(body)
    blob = _xref_row(0, 0, 65535) + _xref_row(1, catalog_at, 0) + _xref_row(1, stream_at, 0)
    text = (
        f"2 0 obj\n<< /Type /XRef /Size 3 /W [1 4 2] /Root 1 0 R {dict_tail} "
        f"/Length {len(blob)} >>\nstream\n"
    )
    pdf = body + text.encode("ascii") + blob + b"\nendstream\nendobj\n"
    return pdf + f"startxref\n{stream_at}\n%%EOF\n".encode("ascii")


def test_a_previous_xref_is_refused() -> None:
    pdf = classic_pdf(
        {1: _CATALOG},
        trailer_body="<< /Size 2 /Root 1 0 R /Prev 0 >>",
    )
    _assert_prev(pdf)


def test_an_xref_stream_prev_is_refused() -> None:
    _assert_prev(_xref_stream_pdf("/Prev 0"))


def test_a_hex_escaped_prev_in_a_classic_trailer_is_refused() -> None:
    pdf = classic_pdf(
        {1: _CATALOG},
        trailer_body="<< /Size 2 /Root 1 0 R /Pr#65v 0 >>",
    )
    _assert_prev(pdf)


def test_a_hex_escaped_prev_in_an_xref_stream_is_refused() -> None:
    _assert_prev(_xref_stream_pdf("/Pr#65v 0"))


@pytest.mark.parametrize("value", ["null", "(x)"])
def test_a_non_integer_prev_is_refused(value: str) -> None:
    pdf = classic_pdf(
        {1: _CATALOG},
        trailer_body=f"<< /Size 2 /Root 1 0 R /Prev {value} >>",
    )
    _assert_prev(pdf)


def test_an_xref_stream_is_not_followed_for_pages() -> None:
    objects = {1: _CATALOG, 2: _PAGES, 3: _PAGE}
    plain = PdfDocument(classic_pdf(objects))
    base = classic_pdf(
        objects,
        trailer_body="<< /Size 4 /Root 1 0 R /XRefStm 0000000000 >>",
    )
    fake = b"4 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 9 /Mark /Replaced >>\nendobj\n"
    fake_at = len(base)
    stream_at = fake_at + len(fake)
    base = base.replace(b"/XRefStm 0000000000", f"/XRefStm {stream_at:010d}".encode("ascii"), 1)
    blob = _xref_row(0, 0, 65535)
    for number in (1, 2, 3):
        entry = plain.entries[number]
        offset = fake_at if number == 2 else entry.a
        blob += _xref_row(1, offset, 0)
    stream = (
        (
            f"5 0 obj\n<< /Type /XRef /Size 4 /W [1 4 2] /Pages 4 0 R "
            f"/Length {len(blob)} >>\nstream\n"
        ).encode("ascii")
        + blob
        + b"\nendstream\nendobj\n"
    )
    pdf = base + fake + stream
    doc = PdfDocument(pdf)
    root = doc.trailer.get("Root")
    assert isinstance(root, PdfRef)
    catalog = doc.get(root.number)
    assert isinstance(catalog, dict)
    pages_ref = catalog.get("Pages")
    assert isinstance(pages_ref, PdfRef)
    pages = doc.get(pages_ref.number)
    assert isinstance(pages, dict)
    assert pages.get("Count") == 1
    mark = pages.get("Mark")
    assert isinstance(mark, PdfName)
    assert mark.value == "Original"


def test_a_trailer_without_prev_parses() -> None:
    pdf = classic_pdf({1: _CATALOG, 2: _PAGES, 3: _PAGE})
    doc = PdfDocument(pdf)
    assert doc.trailer.get("Root") is not None
    assert "Prev" not in doc.trailer
