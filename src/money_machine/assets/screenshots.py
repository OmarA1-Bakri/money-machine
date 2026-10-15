"""Fixture screenshots of each Notion variant. A11 stays DESIGNED.

The only HTML painted by capture is the pinned variant template with escaped
fixture labels. A live fetcher may be called, and its return value is never
painted. Chromium runs with JavaScript disabled. The PNG is 8-bit RGB so the
listing-image and video screenshot inputs can read it. The committed listing
screenshots stay the golden inputs for those waves.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import struct
import tempfile
import unicodedata
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast
from urllib.parse import unquote, urlparse
from uuid import UUID

from playwright._impl._network import WebSocketRoute as WebSocketRouteImpl
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Route,
    WebSocketRoute,
    sync_playwright,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from money_machine.assets.screenshot_text import (
    ScreenshotRefusal,
    fill_template,
    refuse_fixture_value,
    refuse_rendered_text,
)

VIEWPORT_WIDTH = 480
VIEWPORT_HEIGHT = 360
CROP_X = 0
CROP_Y = 0
CROP_WIDTH = 480
CROP_HEIGHT = 270
READY_SELECTOR = "html[data-mm-ready='loaded']"
READY_TIMEOUT_MS = 1000
SCREENSHOT_TEMPLATE_VERSION = "s08-w5-screenshot-1"
_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "variant_pages" / "variant.html"
)
LAUNCH_ARGS = (
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
_STRUCTURE_JS = """() => {
  if (document.querySelector("input, textarea, canvas, iframe")) return "structure";
  for (const node of document.querySelectorAll("*")) {
    if (node.shadowRoot) return "structure";
    const before = getComputedStyle(node, "::before").content;
    if (before !== "none") return "structure";
    const after = getComputedStyle(node, "::after").content;
    if (after !== "none") return "structure";
  }
  return "";
}"""


@dataclass(frozen=True, slots=True)
class VariantPage:
    """One variant label. ``html_path`` and ``live_url`` are never painted."""

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
    """Screenshot each variant from the pinned template."""
    if not pages:
        raise ScreenshotRefusal("missing_page")
    template = _read_template()
    documents: list[str] = []
    for page in pages:
        if refuse_output_name(page.name) is not None:
            raise ScreenshotRefusal("output_name")
        fixture = refuse_fixture_value(page.name)
        if fixture is not None:
            raise ScreenshotRefusal(fixture)
        if refuse_missing_page(page) is not None:
            raise ScreenshotRefusal("missing_page")
        if page.html_path is not None:
            Path(page.html_path).read_bytes()
        if page.live_url is not None:
            fetcher(page.live_url)
        documents.append(fill_template(template, page.name))
    raws = _paint_documents(tuple(documents))
    captured: list[CapturedScreenshot] = []
    for page, raw in zip(pages, raws, strict=True):
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
    """Return ``missing_page`` when a claimed HTML file is not on disk."""
    if page.live_url is not None:
        return None
    path = page.html_path
    if path is not None and not Path(path).is_file():
        return "missing_page"
    return None


def refuse_unready(ready: bool) -> str | None:
    """Return ``not_ready`` when the readiness marker was not painted."""
    if ready:
        return None
    return "not_ready"


def refuse_output_name(name: str) -> str | None:
    """Return ``output_name`` for an empty slug or a name with a control character."""
    if any(unicodedata.category(char) == "Cc" for char in name):
        return "output_name"
    if _slug(name) == "":
        return "output_name"
    return None


def write_screenshot_inputs(
    captures: tuple[CapturedScreenshot, ...],
    directory: Path,
) -> tuple[dict[str, Path], frozenset[str]]:
    """Write this run's PNGs. The returned hashes are only this run."""
    if directory.is_symlink() or not directory.is_dir():
        raise ScreenshotRefusal("output_path")
    if any(directory.iterdir()):
        raise ScreenshotRefusal("output_path")
    ordered: list[tuple[str, CapturedScreenshot]] = []
    seen: set[str] = set()
    for shot in captures:
        if refuse_output_name(shot.lineage.variant) is not None:
            raise ScreenshotRefusal("output_name")
        slug = _slug(shot.lineage.variant)
        if slug in seen:
            raise ScreenshotRefusal("output_collision")
        seen.add(slug)
        ordered.append((slug, shot))
    staging = Path(tempfile.mkdtemp(prefix="mm-shot-", dir=directory.parent))
    try:
        for slug, shot in ordered:
            _write_exclusive(staging / f"{slug}.png", shot.png)
        os.rename(staging, directory)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    paths = {slug: directory / f"{slug}.png" for slug, _shot in ordered}
    digests = frozenset(shot.lineage.screenshot_sha256 for _slug, shot in ordered)
    return paths, digests


def variant_template_path() -> Path:
    """Return the only HTML file capture substitutes into."""
    return _TEMPLATE_PATH


def _read_template() -> str:
    path = variant_template_path()
    if not path.is_file():
        raise ScreenshotRefusal("missing_page")
    return path.read_text(encoding="utf-8")


def _paint_documents(documents: tuple[str, ...]) -> tuple[bytes, ...]:
    """Paint already-built HTML. Capture itself only fills the pinned template."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=list(LAUNCH_ARGS))
        try:
            context = open_screenshot_context(browser, javascript=False)
            try:
                return tuple(_paint_page(context, document) for document in documents)
            finally:
                context.close()
        finally:
            browser.close()


def open_screenshot_context(
    browser: Browser,
    *,
    javascript: bool,
    allowed_http: tuple[str, ...] = (),
) -> BrowserContext:
    context = browser.new_context(
        viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
        screen={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
        device_scale_factor=1,
        reduced_motion="reduce",
        color_scheme="light",
        java_script_enabled=javascript,
        service_workers="block",
        bypass_csp=True,
        locale="en-US",
        timezone_id="UTC",
        has_touch=False,
        is_mobile=False,
    )
    _install_routes(context, frozenset(allowed_http))
    return context


def _install_routes(context: BrowserContext, allowed_http: frozenset[str]) -> None:
    def _guard(route: Route) -> None:
        url = route.request.url
        if url.startswith(("about:", "data:")) or _file_allowed(url):
            route.continue_()
            return
        if _http_allowed(url, route.request.resource_type, allowed_http):
            route.continue_()
            return
        route.abort()

    context.route("**/*", _guard)
    context.route_web_socket("**", _close_web_socket)


def _close_web_socket(socket: WebSocketRoute) -> None:
    """Close the page socket without waiting. ``WebSocketRoute.close`` deadlocks."""
    impl = cast(WebSocketRouteImpl, socket._impl_obj)  # pyright: ignore[reportPrivateUsage]
    impl._channel.send_may_fail(  # pyright: ignore[reportPrivateUsage]
        "closePage",
        None,
        {"code": 1000, "reason": "", "wasClean": True},
    )


def _file_allowed(url: str) -> bool:
    if not url.startswith("file:"):
        return False
    parsed = urlparse(url)
    try:
        return Path(unquote(parsed.path)).resolve() == variant_template_path().resolve()
    except OSError:
        return False


def _http_allowed(url: str, _resource_type: str, allowed_http: frozenset[str]) -> bool:
    return url in allowed_http


def _paint_page(context: BrowserContext, document: str) -> bytes:
    page = context.new_page()
    try:
        page.set_content(document, wait_until="load")
        if refuse_unready(_marker_ready(page)) is not None:
            raise ScreenshotRefusal("not_ready")
        if refuse_page_structure(page) is not None:
            raise ScreenshotRefusal("structure")
        if refuse_rendered_text(page.inner_text("body")) is not None:
            raise ScreenshotRefusal("sensitive_data")
        return _canonical_rgb(_clip(page))
    finally:
        page.close()


def refuse_page_structure(page: Page) -> str | None:
    """Return ``structure`` for form controls, frames, shadow roots, or generated content."""
    found = page.evaluate(_STRUCTURE_JS)
    if found:
        return "structure"
    return None


def _marker_ready(page: Page) -> bool:
    try:
        page.wait_for_selector(READY_SELECTOR, state="attached", timeout=READY_TIMEOUT_MS)
    except PlaywrightTimeout:
        return False
    return True


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


def _write_exclusive(path: Path, payload: bytes) -> None:
    """Create a new file.

    ``O_EXCL`` refuses an existing path. On Linux that includes a symlink,
    and the open does not follow it. ``O_NOFOLLOW`` does not change that
    outcome while ``O_EXCL`` is set, so it is not combined here.
    """
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    descriptor = os.open(path, flags, 0o644)
    try:
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)


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
