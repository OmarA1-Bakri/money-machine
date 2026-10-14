"""Ten fixture listing images for A11. The agent stays DESIGNED and unregistered.

Visible text is the A10 image-strip line for that frame. ``validate_claims``
is the only authority for that text. Screenshots are caller-supplied fixture
files. Remote URLs are aborted. A spec-version change is bound into the PNG
so the file hash changes without painting a version string the claims do not
state.
"""

from __future__ import annotations

import base64
import hashlib
import json
import struct
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal, assert_never
from uuid import UUID

from playwright.sync_api import Route, sync_playwright

from money_machine.agents.contracts.merchandising import (
    IMAGE_ROLES,
    BuiltVariant,
    ImageRole,
    ListingCopy,
    ListingDraft,
    MerchandisingInput,
)
from money_machine.assets.design_tokens import DesignTokens, emit_css, load_tokens
from money_machine.domain.services.claim_validation import validate_claims

LISTING_TEMPLATE_VERSION = "s08-w2-listing-1"
LISTING_IMAGE_WIDTH = 800
LISTING_IMAGE_HEIGHT = 800
DEVICE_SCALE_FACTOR = 1
_LAUNCH_ARGS = (
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-extensions",
    "--hide-scrollbars",
    "--no-first-run",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-component-update",
    "--font-render-hinting=none",
    "--disable-font-subpixel-positioning",
    "--disable-lcd-text",
    "--force-color-profile=srgb",
    "--force-device-scale-factor=1",
    "--disable-skia-runtime-opts",
)
_BLANK_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xf0\x1f\x00\x05\x00"
    b"\x01\xff\x8b\xd1\x8e\x00\x00\x00\x00IEND\xaeB`\x82"
)


class ListingImageRefusal(ValueError):
    """The listing images were refused before a PNG was returned."""


@dataclass(frozen=True, slots=True)
class ListingImageLineage:
    """Per-image record. QA status is ``passed`` only when a PNG is returned."""

    product_id: UUID
    spec_version: int
    build_version: int
    source_screenshot_sha256: tuple[str, ...]
    merchandising_version: str
    template_version: str
    output_sha256: str
    width_px: int
    height_px: int
    qa_status: Literal["passed"]
    role: ImageRole


@dataclass(frozen=True, slots=True)
class RenderedListingImage:
    """One listing PNG and the lineage bound into its bytes."""

    png: bytes
    lineage: ListingImageLineage


def network_allowed(url: str) -> bool:
    """True for document, font, and file URLs. Remote http(s) stays blocked."""
    return url.startswith(("data:", "file:", "about:"))


def merchandising_version(draft: ListingDraft) -> str:
    """Stable hash of the A10 draft. Spec version is not part of this hash."""
    payload = draft.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def render_listing_images(
    copy: ListingCopy,
    request: MerchandisingInput,
    screenshots: Mapping[str, Path],
    allowed_screenshot_sha256: frozenset[str],
    tokens: DesignTokens,
    *,
    build_version: int,
    injected_text: str = "",
) -> tuple[RenderedListingImage, ...]:
    """Render the ten frames. ``injected_text`` is buyer-facing and must validate.

    Production callers leave ``injected_text`` empty. A non-empty value is painted
    only when claim validation accepts it, which the stock templates do not ask for.
    """
    load_tokens(tokens.model_dump())
    if refuse_missing_screenshot(screenshots) is not None:
        raise ListingImageRefusal("missing_screenshot")
    if refuse_unknown_screenshot(screenshots, allowed_screenshot_sha256) is not None:
        raise ListingImageRefusal("unknown_screenshot")
    if refuse_unvalidated_copy(copy.draft, request) is not None:
        raise ListingImageRefusal("unsupported_claim")
    documents = compose_listing_documents(
        copy,
        screenshots,
        tokens,
        request.variants,
        injected_text=injected_text,
    )
    if refuse_unclaimed_rendered_text(documents, copy.draft, request) is not None:
        raise ListingImageRefusal("unsupported_claim")
    pngs = _paint(tuple(html for _role, html, _embedded in documents))
    version = merchandising_version(copy.draft)
    rendered: list[RenderedListingImage] = []
    for (role, _html, embedded), png in zip(documents, pngs, strict=True):
        source_hash = hashlib.sha256(embedded).hexdigest()
        bound = _bind_lineage_png(
            png,
            _lineage_text(
                product_id=request.spec.product_id,
                spec_version=request.spec.version,
                build_version=build_version,
                source_hash=source_hash,
                merchandising=version,
                role=role,
            ),
        )
        width, height = struct.unpack(">II", bound[16:24])
        rendered.append(
            RenderedListingImage(
                png=bound,
                lineage=ListingImageLineage(
                    product_id=request.spec.product_id,
                    spec_version=request.spec.version,
                    build_version=build_version,
                    source_screenshot_sha256=(source_hash,),
                    merchandising_version=version,
                    template_version=LISTING_TEMPLATE_VERSION,
                    output_sha256=hashlib.sha256(bound).hexdigest(),
                    width_px=width,
                    height_px=height,
                    qa_status="passed",
                    role=role,
                ),
            )
        )
    return tuple(rendered)


def refuse_missing_screenshot(screenshots: Mapping[str, Path]) -> str | None:
    """Return ``missing_screenshot`` when a frame has no file."""
    for role in IMAGE_ROLES:
        path = screenshots.get(role)
        if path is None or not Path(path).is_file():
            return "missing_screenshot"
    return None


def refuse_unknown_screenshot(
    screenshots: Mapping[str, Path],
    allowed_screenshot_sha256: frozenset[str],
) -> str | None:
    """Return ``unknown_screenshot`` when a file is outside the allow-list.

    A missing file belongs to the other check, so it is skipped here.
    """
    for role in IMAGE_ROLES:
        path = screenshots.get(role)
        if path is None or not Path(path).is_file():
            continue
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if digest not in allowed_screenshot_sha256:
            return "unknown_screenshot"
    return None


def refuse_unvalidated_copy(copy: ListingDraft, request: MerchandisingInput) -> str | None:
    """Return ``unsupported_claim`` when the A10 copy fails claim validation."""
    if validate_claims(copy, request).passed:
        return None
    return "unsupported_claim"


def refuse_unclaimed_rendered_text(
    documents: tuple[tuple[ImageRole, str, bytes], ...],
    copy: ListingDraft,
    request: MerchandisingInput,
) -> str | None:
    """Refuse visible text that is not the validated image-strip line.

    A string that matches the line was already accepted with the copy. Any other
    string is substituted onto that frame and kept only when ``validate_claims``
    accepts the substitution. The third item is the embedded screenshot.
    """
    lines = {line.role: line.text for line in copy.image_strip}
    if tuple(role for role, _html, _embedded in documents) != IMAGE_ROLES:
        return "unsupported_claim"
    for role, html, _embedded in documents:
        texts = extract_visible_text(html)
        for text in texts:
            if text == lines[role]:
                continue
            if _probe_holds(text, role, copy, request):
                continue
            return "unsupported_claim"
        if lines[role] not in texts:
            return "unsupported_claim"
    return None


def compose_listing_documents(
    copy: ListingCopy,
    screenshots: Mapping[str, Path],
    tokens: DesignTokens,
    variants: tuple[BuiltVariant, ...],
    *,
    injected_text: str = "",
) -> tuple[tuple[ImageRole, str, bytes], ...]:
    """Build the ten HTML documents. Text nodes are the image-strip lines.

    Each document carries the screenshot bytes embedded in that frame. Lineage
    hashes those bytes, so a hub frame cannot show a different file than the
    hash it records.
    """
    load_tokens(tokens.model_dump())
    css = emit_css(tokens) + _frame_css()
    lines = {line.role: line for line in copy.draft.image_strip}
    colours = tuple(variant.colour for variant in variants)
    documents: list[tuple[ImageRole, str, bytes]] = []
    for role in IMAGE_ROLES:
        line = lines[role]
        embedded = _screenshot_bytes(screenshots.get(role))
        image = base64.b64encode(embedded).decode("ascii")
        body = _body(role, line.text, image, colours, injected_text)
        documents.append((role, _document(css, body), embedded))
    return tuple(documents)


def extract_visible_text(document: str) -> tuple[str, ...]:
    """Text nodes a buyer can read. Style and script contents are ignored."""
    parser = _VisibleText()
    parser.feed(document)
    parser.close()
    return tuple(parser.texts)


def _probe_holds(
    text: str, role: ImageRole, copy: ListingDraft, request: MerchandisingInput
) -> bool:
    strip = tuple(
        line.model_copy(update={"text": text}) if line.role == role else line
        for line in copy.image_strip
    )
    probed = copy.model_copy(update={"image_strip": strip})
    return validate_claims(probed, request).passed


def _screenshot_bytes(path: Path | None) -> bytes:
    if path is None or not Path(path).is_file():
        return _BLANK_PNG
    return Path(path).read_bytes()


def _body(role: ImageRole, text: str, image: str, colours: tuple[str, ...], injected: str) -> str:
    claim = f'<p class="mm-claim">{escape(text)}</p>'
    extra = f'<p class="mm-claim">{escape(injected)}</p>' if injected else ""
    shot = f'<img alt="" src="data:image/png;base64,{image}">'
    icon = (
        '<svg class="mm-icon" viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M12 3 L21 12 L12 21 L3 12 Z"></path></svg>'
    )
    steps = (
        '<svg class="mm-steps" viewBox="0 0 280 48" aria-hidden="true">'
        '<line x1="28" y1="24" x2="252" y2="24"></line>'
        '<circle cx="28" cy="24" r="10"></circle>'
        '<circle cx="140" cy="24" r="10"></circle>'
        '<circle cx="252" cy="24" r="10"></circle></svg>'
    )
    if role == "hero":
        layout, inner = "mm-hero", f'{icon}{claim}<div class="mm-device-frame">{shot}</div>{extra}'
    elif role == "overview":
        layout, inner = "mm-overview", f'<div class="mm-card">{shot}</div>{claim}{extra}'
    elif role in ("hub_1", "hub_2", "hub_3", "hub_4", "hub_5"):
        layout, inner = "mm-hub-slide", f"{shot}{claim}{extra}"
    elif role == "colour_options":
        row = "".join(
            f'<span class="mm-swatch" style="background:{escape(colour)}"></span>'
            for colour in colours
        )
        layout, inner = (
            "mm-colour-options",
            f'<div class="mm-swatches">{row}</div>{shot}{claim}{extra}',
        )
    elif role == "devices":
        layout = "mm-device-compatibility"
        inner = (
            f'<div class="mm-phone mm-device-frame">{shot}</div>'
            f'<div class="mm-tablet mm-device-frame">{shot}</div>{claim}{extra}'
        )
    elif role == "how_it_works":
        layout = "mm-how-it-works"
        inner = f'{steps}{claim}<div class="mm-device-frame">{shot}</div>{extra}'
    else:
        assert_never(role)
    return f'<article class="mm-frame {layout}">{inner}</article>'


def _document(css: str, body: str) -> str:
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<style>{css}</style></head><body>{body}</body></html>"
    )


def _frame_css() -> str:
    width = LISTING_IMAGE_WIDTH
    height = LISTING_IMAGE_HEIGHT
    return (
        f"html,body{{width:{width}px;height:{height}px;overflow:hidden;}}"
        f".mm-frame{{width:{width}px;height:{height}px;overflow:hidden;"
        "position:relative;background:var(--mm-background);box-sizing:border-box;}}"
    )


def _lineage_text(
    *,
    product_id: UUID,
    spec_version: int,
    build_version: int,
    source_hash: str,
    merchandising: str,
    role: ImageRole,
) -> str:
    return (
        f"product_id={product_id}\n"
        f"spec_version={spec_version}\n"
        f"build_version={build_version}\n"
        f"screenshots={source_hash}\n"
        f"merchandising_version={merchandising}\n"
        f"template_version={LISTING_TEMPLATE_VERSION}\n"
        f"role={role}\n"
    )


def _bind_lineage_png(png: bytes, text: str) -> bytes:
    """Insert a tEXt chunk before IEND. The text is not a visible text node."""
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ListingImageRefusal("png")
    payload = b"mm-lineage\x00" + text.encode("ascii")
    chunk = _png_chunk(b"tEXt", payload)
    offset = 8
    out = bytearray(png[:8])
    inserted = False
    while offset + 12 <= len(png):
        length = struct.unpack(">I", png[offset : offset + 4])[0]
        tag = png[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(png):
            break
        if tag == b"IEND" and not inserted:
            out.extend(chunk)
            inserted = True
        out.extend(png[offset:end])
        offset = end
        if tag == b"IEND":
            break
    if not inserted or offset != len(png):
        raise ListingImageRefusal("png")
    return bytes(out)


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _paint(documents: tuple[str, ...]) -> tuple[bytes, ...]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=list(_LAUNCH_ARGS))
        try:
            context = browser.new_context(
                viewport={"width": LISTING_IMAGE_WIDTH, "height": LISTING_IMAGE_HEIGHT},
                screen={"width": LISTING_IMAGE_WIDTH, "height": LISTING_IMAGE_HEIGHT},
                device_scale_factor=DEVICE_SCALE_FACTOR,
                reduced_motion="reduce",
                color_scheme="light",
                java_script_enabled=True,
                bypass_csp=True,
                locale="en-US",
                timezone_id="UTC",
                has_touch=False,
                is_mobile=False,
            )
            try:
                context.route("**/*", _guard)
                painted: list[bytes] = []
                for document in documents:
                    page = context.new_page()
                    try:
                        page.set_content(document, wait_until="load")
                        page.evaluate("async () => { await document.fonts.ready; }")
                        painted.append(
                            page.screenshot(
                                type="png",
                                animations="disabled",
                                caret="hide",
                                scale="css",
                                full_page=False,
                                omit_background=False,
                                clip={
                                    "x": 0,
                                    "y": 0,
                                    "width": LISTING_IMAGE_WIDTH,
                                    "height": LISTING_IMAGE_HEIGHT,
                                },
                            )
                        )
                    finally:
                        page.close()
                return tuple(painted)
            finally:
                context.close()
        finally:
            browser.close()


def _guard(route: Route) -> None:
    if network_allowed(route.request.url):
        route.continue_()
        return
    route.abort()


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._buf: list[str] = []
        self.texts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"style", "script"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script"} and self._skip:
            self._skip -= 1
            return
        if tag in {"p", "div", "span", "li", "h1", "article"}:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            self._buf.append(data)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        text = "".join(self._buf).strip()
        self._buf = []
        if text:
            self.texts.append(text)
