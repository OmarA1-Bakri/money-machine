"""A trailer /Prev is refused. The offset is not followed."""

from __future__ import annotations

import pytest

from money_machine.assets.pdf_reader import PdfDocument
from tests.unit.assets.gift_pdf_craft import classic_pdf

_CATALOG = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"


def test_a_previous_xref_is_refused() -> None:
    pdf = classic_pdf(
        {1: _CATALOG},
        trailer_body="<< /Size 2 /Root 1 0 R /Prev 0 >>",
    )
    with pytest.raises(ValueError) as caught:
        PdfDocument(pdf)
    assert caught.value.args == ("pdf prev",)


def test_a_trailer_without_prev_parses() -> None:
    pdf = classic_pdf({1: _CATALOG})
    assert PdfDocument(pdf).trailer.get("Root") is not None
