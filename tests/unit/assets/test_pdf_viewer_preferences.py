"""Only the measured inert Chromium catalog extension is admissible."""

import pytest
from playwright.sync_api import sync_playwright

from money_machine.assets.pdf_objects import delivery_link_uris
from money_machine.assets.pdf_reader import PdfDocument
from tests.unit.assets.gift_pdf_craft import classic_pdf


def preference_pdf(preferences: str) -> bytes:
    bodies = {
        1: f"<< /Type /Catalog /Pages 2 0 R /ViewerPreferences {preferences} >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: "<< /Type /Page /Resources << /ExtGState << >> /Font << >> "
        "/ProcSet [/PDF /Text /ImageB /ImageC /ImageI] >> /MediaBox [0 0 1 1] "
        "/Contents << >> /Tabs /S /Parent 2 0 R >>",
        4: "<< /Type /ViewerPreferences /DisplayDocTitle true >>",
    }
    return classic_pdf(
        {number: f"{number} 0 obj\n{body}\nendobj\n".encode() for number, body in bodies.items()}
    )


def test_measured_viewer_preferences_are_accepted() -> None:
    assert (
        delivery_link_uris(preference_pdf("<< /Type /ViewerPreferences /DisplayDocTitle true >>"))
        == ()
    )


@pytest.mark.parametrize(
    "preferences",
    [
        "4 0 R",
        "null",
        "true",
        "[]",
        "<< >>",
        "<< /DisplayDocTitle true >>",
        "<< /Type /Other /DisplayDocTitle true >>",
        "<< /Type /ViewerPreferences /DisplayDocTitle false >>",
        "<< /Type /ViewerPreferences /DisplayDocTitle 1 >>",
        "<< /Type /ViewerPreferences /DisplayDocTitle 4 0 R >>",
        "<< /Type /ViewerPreferences /DisplayDocTitle true /HideToolbar true >>",
        "<< /Type /ViewerPreferences /DisplayDocTitle true /OpenAction 4 0 R >>",
        "<< /Type /ViewerPreferences /DisplayDocTitle true /S /JavaScript >>",
    ],
)
def test_unmeasured_preference_shapes_are_refused(preferences: str) -> None:
    with pytest.raises(ValueError):
        delivery_link_uris(preference_pdf(preferences))


def test_actual_full_chromium_catalog_is_accepted() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=playwright.chromium.executable_path,
            args=["--no-sandbox"],
        )
        try:
            page = browser.new_page()
            page.set_content("<html><body>Delivery format compatibility</body></html>")
            pdf = page.pdf()
        finally:
            browser.close()
    document = PdfDocument(pdf)
    root = document.deref(document.trailer["Root"])
    assert isinstance(root, dict) and "ViewerPreferences" in root
    assert delivery_link_uris(pdf) == ()
