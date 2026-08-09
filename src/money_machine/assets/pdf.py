"""Deterministic delivery-guide rendering with fpdf2."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from fpdf import FPDF


def render_delivery_pdf(
    *,
    title: str,
    hubs: tuple[str, ...],
    colours: tuple[str, ...],
    inventory: tuple[str, ...],
    support_information: str,
) -> bytes:
    """Return a stable two-page guide whose labels match ProductSpec fields."""

    pdf = FPDF(format="letter", unit="pt")
    pdf.set_compression(False)
    pdf.set_creation_date(datetime(2000, 1, 1, tzinfo=UTC))
    pdf.set_creator("Money Machine deterministic renderer")
    pdf.set_producer("Money Machine fpdf2")
    pdf.set_title(title)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.multi_cell(0, 24, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(12)
    pdf.set_font("Helvetica", size=12)
    for line in (
        "Setup in three steps",
        "1. Download this access guide.",
        "2. Open your delivered workspace files.",
        "3. Duplicate and personalize your copy.",
        f"Navigation hubs: {', '.join(hubs)}",
    ):
        pdf.multi_cell(0, 18, line, new_x="LMARGIN", new_y="NEXT")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 24, "Colour and variant access", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=12)
    for line in (
        f"Colour variants: {', '.join(colours)}",
        "Keep each variant as an isolated copy.",
        "Delivered local file inventory:",
        *inventory,
        support_information,
        "No paid checkout links are embedded in this document.",
    ):
        pdf.multi_cell(0, 18, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def pdf_page_count(data: bytes) -> int:
    if not data.startswith(b"%PDF-"):
        raise ValueError("invalid PDF")
    return len(re.findall(rb"/Type\s*/Page(?!s)", data))
