"""Fixture screenshots of each Notion variant. A11 stays DESIGNED.

Local HTML stands in for the variant pages. Chromium is the headless browser
the PDF path already launches. A live URL is handed to the fetcher, and the
default fetcher refuses before any navigation. The PNG is 8-bit RGB so the
listing-image and video screenshot inputs can read it. The committed listing
screenshots stay the golden inputs for those waves.
"""

from __future__ import annotations

import hashlib
import re
import struct
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

from playwright.sync_api import Page, Route, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from money_machine.assets.listing_images import network_allowed

VIEWPORT_WIDTH = 480
VIEWPORT_HEIGHT = 360
CROP_X = 0
CROP_Y = 0
CROP_WIDTH = 480
CROP_HEIGHT = 270
READY_SELECTOR = "html[data-mm-ready='loaded']"
READY_TIMEOUT_MS = 1000
SCREENSHOT_TEMPLATE_VERSION = "s08-w5-screenshot-1"
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
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_NOTION_HOST = re.compile(r"notion\.(?:so|site)", re.IGNORECASE)
_TOKEN = re.compile(
    r"(?:secret|token|api[_-]?key|bearer|ntn|sk)[_-][A-Za-z0-9]{6,}",
    re.IGNORECASE,
)
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_HEX_ID = re.compile(r"\b[0-9a-fA-F]{32}\b")


class ScreenshotRefusal(ValueError):
    """The variant screenshot was refused before a PNG was returned."""


@dataclass(frozen=True, slots=True)
class VariantPage:
    """One variant. A local file is the fixture. A live URL is parked."""

    name: str
    html_path: Path | None = None
    live_url: str | None = None


@dataclass(frozen=True, slots=True)
class ScreenshotLineage:
    """Record bound into the PNG. QA status is ``passed`` only when bytes return."""

    product_id: UUID
    spec_version: int
    build_version: int
    screenshot_sha256: str
    variant: str
    template_version: str
    viewport_width: int
    viewport_height: int
    crop_x: int
    crop_y: int
    crop_width: int
    crop_height: int
    qa_status: Literal["passed"]
    source: Literal["fixture", "injected"]


@dataclass(frozen=True, slots=True)
class CapturedScreenshot:
    """Raw RGB PNG, the same bytes with the lineage chunk, and the record."""

    png: bytes
    lineage_png: bytes
    lineage: ScreenshotLineage


def default_live_fetcher(url: str) -> str:
    """Parked live acquisition. An injected fetcher is the only other slot."""
    del url
    raise ScreenshotRefusal("live_acquisition")


def capture_variant_screenshots(
    pages: tuple[VariantPage, ...],
    *,
    build_version: int,
    product_id: UUID,
    spec_version: int,
    fetcher: Callable[[str], str] = default_live_fetcher,
) -> tuple[CapturedScreenshot, ...]:
    """Screenshot each variant page. The default fetcher never navigates."""
    if not pages:
        raise ScreenshotRefusal("missing_page")
    prepared: list[tuple[VariantPage, str]] = []
    for page in pages:
        if refuse_missing_page(page) is not None:
            raise ScreenshotRefusal("missing_page")
        if page.live_url is not None:
            prepared.append((page, fetcher(page.live_url)))
            continue
        path = page.html_path
        if path is None:
            raise ScreenshotRefusal("missing_page")
        prepared.append((page, Path(path).read_text(encoding="utf-8")))
    raws = _paint(tuple(html for _page, html in prepared))
    captured: list[CapturedScreenshot] = []
    for (page, _html), raw in zip(prepared, raws, strict=True):
        digest = hashlib.sha256(raw).hexdigest()
        source: Literal["fixture", "injected"] = "injected" if page.live_url else "fixture"
        text = _lineage_text(
            product_id=product_id,
            spec_version=spec_version,
            build_version=build_version,
            digest=digest,
            variant=page.name,
            source=source,
        )
        lineage = ScreenshotLineage(
            product_id=product_id,
            spec_version=spec_version,
            build_version=build_version,
            screenshot_sha256=digest,
            variant=page.name,
            template_version=SCREENSHOT_TEMPLATE_VERSION,
            viewport_width=VIEWPORT_WIDTH,
            viewport_height=VIEWPORT_HEIGHT,
            crop_x=CROP_X,
            crop_y=CROP_Y,
            crop_width=CROP_WIDTH,
            crop_height=CROP_HEIGHT,
            qa_status="passed",
            source=source,
        )
        captured.append(
            CapturedScreenshot(png=raw, lineage_png=_bind_lineage_png(raw, text), lineage=lineage)
        )
    return tuple(captured)


def refuse_missing_page(page: VariantPage) -> str | None:
    """Return ``missing_page`` when the variant has neither a file nor a live URL."""
    if page.live_url is not None:
        return None
    path = page.html_path
    if path is None or not Path(path).is_file():
        return "missing_page"
    return None


def refuse_sensitive_text(text: str) -> str | None:
    """Return ``sensitive_data`` when rendered text is not fixture or sample data."""
    if _EMAIL.search(text) is not None:
        return "sensitive_data"
    if _NOTION_HOST.search(text) is not None:
        return "sensitive_data"
    if _TOKEN.search(text) is not None:
        return "sensitive_data"
    if _UUID.search(text) is not None:
        return "sensitive_data"
    if _HEX_ID.search(text) is not None:
        return "sensitive_data"
    return None


def refuse_unready(ready: bool) -> str | None:
    """Return ``not_ready`` when the readiness marker was not painted."""
    if ready:
        return None
    return "not_ready"


def write_screenshot_inputs(
    captures: tuple[CapturedScreenshot, ...],
    directory: Path,
) -> tuple[dict[str, Path], frozenset[str]]:
    """Write the raw PNGs. The hashes are the allow-list W2 and W4 already take."""
    paths: dict[str, Path] = {}
    digests: set[str] = set()
    for shot in captures:
        slug = _slug(shot.lineage.variant)
        path = directory / f"{slug}.png"
        path.write_bytes(shot.png)
        paths[slug] = path
        digests.add(shot.lineage.screenshot_sha256)
    return paths, frozenset(digests)


def _paint(documents: tuple[str, ...]) -> tuple[bytes, ...]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=list(_LAUNCH_ARGS))
        try:
            context = browser.new_context(
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                screen={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                device_scale_factor=1,
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
                        if refuse_unready(_marker_ready(page)) is not None:
                            raise ScreenshotRefusal("not_ready")
                        rendered = page.inner_text("body")
                        if refuse_sensitive_text(rendered) is not None:
                            raise ScreenshotRefusal("sensitive_data")
                        painted.append(_canonical_rgb(_clip(page)))
                    finally:
                        page.close()
                return tuple(painted)
            finally:
                context.close()
        finally:
            browser.close()


def _marker_ready(page: Page) -> bool:
    try:
        page.wait_for_selector(READY_SELECTOR, state="attached", timeout=READY_TIMEOUT_MS)
    except PlaywrightTimeout:
        return False
    value = page.evaluate("() => document.documentElement.getAttribute('data-mm-ready')")
    return value == "loaded"


def _clip(page: Page) -> bytes:
    return page.screenshot(
        type="png",
        animations="disabled",
        caret="hide",
        scale="css",
        full_page=False,
        omit_background=False,
        clip={"x": CROP_X, "y": CROP_Y, "width": CROP_WIDTH, "height": CROP_HEIGHT},
    )


def _guard(route: Route) -> None:
    if network_allowed(route.request.url):
        route.continue_()
        return
    route.abort()


def _lineage_text(
    *,
    product_id: UUID,
    spec_version: int,
    build_version: int,
    digest: str,
    variant: str,
    source: str,
) -> str:
    return (
        f"product_id={product_id}\n"
        f"spec_version={spec_version}\n"
        f"build_version={build_version}\n"
        f"screenshot_sha256={digest}\n"
        f"variant={variant}\n"
        f"template_version={SCREENSHOT_TEMPLATE_VERSION}\n"
        f"viewport={VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}\n"
        f"crop={CROP_X},{CROP_Y},{CROP_WIDTH},{CROP_HEIGHT}\n"
        f"source={source}\n"
        "qa_status=passed\n"
    )


def _bind_lineage_png(png: bytes, text: str) -> bytes:
    """Insert a tEXt chunk before IEND. The text is not a visible text node."""
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ScreenshotRefusal("png")
    try:
        payload = b"mm-lineage\x00" + text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ScreenshotRefusal("lineage") from exc
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
        raise ScreenshotRefusal("png")
    return bytes(out)


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _canonical_rgb(data: bytes) -> bytes:
    """Re-encode as filter-0 RGB so the hash is the pixels, not ancillary chunks."""
    width, height, rgb = _decode_rgb(data)
    return _encode_rgb(width, height, rgb)


def _decode_rgb(data: bytes) -> tuple[int, int, bytes]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ScreenshotRefusal("png")
    pos = 8
    width = 0
    height = 0
    colour = 0
    idat = bytearray()
    saw_header = False
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        pos += 8
        end = pos + length
        if end + 4 > len(data):
            raise ScreenshotRefusal("png")
        chunk = data[pos:end]
        pos = end + 4
        if kind == b"IHDR":
            if len(chunk) != 13:
                raise ScreenshotRefusal("png")
            width, height, bit, colour, comp, filt, inter = struct.unpack(">IIBBBBB", chunk)
            if bit != 8 or colour not in (2, 6) or comp != 0 or filt != 0 or inter != 0:
                raise ScreenshotRefusal("png")
            if width < 1 or height < 1:
                raise ScreenshotRefusal("png")
            saw_header = True
        elif kind == b"IDAT":
            idat.extend(chunk)
        elif kind == b"IEND":
            break
    if not saw_header or not idat:
        raise ScreenshotRefusal("png")
    channels = 3 if colour == 2 else 4
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    if len(raw) != height * (stride + 1):
        raise ScreenshotRefusal("png")
    rows: list[bytes] = []
    prev = bytearray(stride)
    cursor = 0
    for _row in range(height):
        filter_type = raw[cursor]
        cursor += 1
        row = bytearray(raw[cursor : cursor + stride])
        cursor += stride
        if filter_type == 1:
            _add_left(row, channels)
        elif filter_type == 2:
            _add_up(row, prev)
        elif filter_type == 3:
            _add_average(row, prev, channels)
        elif filter_type == 4:
            _add_paeth(row, prev, channels)
        elif filter_type != 0:
            raise ScreenshotRefusal("png")
        rows.append(bytes(row))
        prev = row
    if colour == 2:
        return width, height, b"".join(rows)
    rgb = bytearray()
    for row in rows:
        for pixel in range(width):
            start = pixel * 4
            rgb.extend(row[start : start + 3])
    return width, height, bytes(rgb)


def _encode_rgb(width: int, height: int, rgb: bytes) -> bytes:
    if len(rgb) != width * height * 3:
        raise ScreenshotRefusal("png")
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(rgb[y * stride : (y + 1) * stride])
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", header),
            _png_chunk(b"IDAT", zlib.compress(bytes(raw), level=9)),
            _png_chunk(b"IEND", b""),
        )
    )


def _add_left(row: bytearray, channels: int) -> None:
    for index in range(len(row)):
        left = row[index - channels] if index >= channels else 0
        row[index] = (row[index] + left) & 255


def _add_up(row: bytearray, prev: bytearray) -> None:
    for index in range(len(row)):
        row[index] = (row[index] + prev[index]) & 255


def _add_average(row: bytearray, prev: bytearray, channels: int) -> None:
    for index in range(len(row)):
        left = row[index - channels] if index >= channels else 0
        row[index] = (row[index] + ((left + prev[index]) // 2)) & 255


def _add_paeth(row: bytearray, prev: bytearray, channels: int) -> None:
    for index in range(len(row)):
        left = row[index - channels] if index >= channels else 0
        up = prev[index]
        upper_left = prev[index - channels] if index >= channels else 0
        row[index] = (row[index] + _paeth(left, up, upper_left)) & 255


def _paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_distance:
        return left
    if up_distance <= upper_distance:
        return up
    return upper_left


def _slug(name: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in name)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")
