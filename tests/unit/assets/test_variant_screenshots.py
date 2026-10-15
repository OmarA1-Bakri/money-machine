"""Fixture variant screenshots: viewport, crop, readiness, secrets, lineage."""

from __future__ import annotations

import hashlib
import struct
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest
from playwright.sync_api import sync_playwright

from money_machine.assets.listing_images import refuse_unknown_screenshot as refuse_unknown_image
from money_machine.assets.screenshots import (
    CapturedScreenshot,
    VariantPage,
    capture_variant_screenshots,
    default_live_fetcher,
    write_screenshot_inputs,
)
from money_machine.assets.video import refuse_unknown_screenshot as refuse_unknown_video
from money_machine.assets.video_paint import decode_png_rgb
from tests.fixtures.listing_screenshots import fixture_screenshot_hashes, fixture_screenshot_paths
from tests.fixtures.merchandising import consistent_request

_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "variant_pages"
_BUILD = 5
_PRODUCT = UUID("00000000-0000-4000-8000-0000000000b1")
_VARIANTS = ("Sage Green", "Navy Blue", "Rose Gold")
_FILES = {
    "Sage Green": _ROOT / "sage-green.html",
    "Navy Blue": _ROOT / "navy-blue.html",
    "Rose Gold": _ROOT / "rose-gold.html",
}
_LIVE = "https://www.notion.so/private-variant-page"
_DELAYED_EMAIL = """<!DOCTYPE html>
<html>
<body style="margin:0;background:#112233">
<script>
setTimeout(function () {
  document.documentElement.setAttribute("data-mm-ready", "loaded");
  var node = document.createElement("p");
  node.textContent = ["person", "example.com"].join("@");
  document.body.appendChild(node);
}, 40);
</script>
</body>
</html>
"""
_HIDDEN_EMAIL = """<!DOCTYPE html>
<html data-mm-ready="loaded">
<body style="margin:0;background:#112233;width:480px;height:400px">
<div style="width:4px;height:4px;background:#00ff00"></div>
<p style="margin:12px">Sample fixture only</p>
<!-- person@example.com -->
<script>const hidden = "person@example.com";</script>
</body>
</html>
"""


def _launch_chromium() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        browser.close()


@pytest.fixture(scope="module", autouse=True)
def chromium_installed() -> None:
    try:
        _launch_chromium()
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        _launch_chromium()


def _pages() -> tuple[VariantPage, ...]:
    return tuple(VariantPage(name=name, html_path=_FILES[name]) for name in _VARIANTS)


def _capture(
    pages: tuple[VariantPage, ...] | None = None,
    *,
    fetcher: Callable[[str], str] | None = None,
) -> tuple[CapturedScreenshot, ...]:
    spec_version = consistent_request().spec.version
    chosen = _pages() if pages is None else pages
    if fetcher is None:
        return capture_variant_screenshots(
            chosen,
            build_version=_BUILD,
            product_id=_PRODUCT,
            spec_version=spec_version,
        )
    return capture_variant_screenshots(
        chosen,
        build_version=_BUILD,
        product_id=_PRODUCT,
        spec_version=spec_version,
        fetcher=fetcher,
    )


def _ihdr(png: bytes) -> tuple[int, int, int]:
    assert png[12:16] == b"IHDR"
    width, height, _bit, colour = struct.unpack(">IIBB", png[16:26])
    return width, height, colour


def _lineage_chunk(png: bytes) -> str:
    """Walk PNG chunks. This parser does not call the screenshot module."""
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    found: str | None = None
    while offset + 12 <= len(png):
        length = struct.unpack(">I", png[offset : offset + 4])[0]
        tag = png[offset + 4 : offset + 8]
        end = offset + 12 + length
        assert end <= len(png)
        data = png[offset + 8 : offset + 8 + length]
        if tag == b"tEXt" and data.startswith(b"mm-lineage\x00"):
            found = data.split(b"\x00", 1)[1].decode("ascii")
        offset = end
        if tag == b"IEND":
            break
    if found is None:
        raise AssertionError("lineage")
    return found


def _strip_lineage(png: bytes) -> bytes:
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    out = bytearray(png[:8])
    while offset + 12 <= len(png):
        length = struct.unpack(">I", png[offset : offset + 4])[0]
        tag = png[offset + 4 : offset + 8]
        end = offset + 12 + length
        data = png[offset + 8 : offset + 8 + length]
        if not (tag == b"tEXt" and data.startswith(b"mm-lineage\x00")):
            out.extend(png[offset:end])
        offset = end
        if tag == b"IEND":
            break
    return bytes(out)


def _fields(text: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def _write(tmp_path: Path, name: str, html: str) -> VariantPage:
    path = tmp_path / name
    path.write_text(html, encoding="utf-8")
    return VariantPage(name="Sample", html_path=path)


def test_viewport_is_clipped_and_has_no_chrome(chromium_installed: None) -> None:
    del chromium_installed
    shot = _capture()[0]
    width, height, colour = _ihdr(shot.png)
    assert (width, height, colour) == (480, 270, 2)
    parsed = _fields(_lineage_chunk(shot.lineage_png))
    assert parsed["viewport"] == "480x360"
    assert parsed["crop"] == "0,0,480,270"
    _decoded_width, _decoded_height, rgb = decode_png_rgb(shot.png)
    assert rgb[0:3] == b"\x00\xff\x00"
    pixels = [rgb[index : index + 3] for index in range(0, len(rgb), 3)]
    assert b"\xff\x00\x00" not in pixels


def test_the_same_fixture_has_the_same_hash(chromium_installed: None) -> None:
    del chromium_installed
    first = _capture()
    second = _capture()
    assert tuple(shot.png for shot in first) == tuple(shot.png for shot in second)
    hashes = [hashlib.sha256(shot.png).hexdigest() for shot in first]
    assert len(set(hashes)) == 3


def test_a_missing_readiness_marker_is_refused(tmp_path: Path, chromium_installed: None) -> None:
    del chromium_installed
    page = _write(
        tmp_path,
        "blank.html",
        "<!DOCTYPE html><html><body><p>Sample fixture</p></body></html>",
    )
    with pytest.raises(ValueError, match="not_ready"):
        _capture((page,))


def test_a_late_marker_is_waited_for(tmp_path: Path, chromium_installed: None) -> None:
    del chromium_installed
    page = _write(
        tmp_path,
        "late.html",
        """<!DOCTYPE html><html><body style="margin:0;background:#112233">
        <script>setTimeout(function () {
          document.documentElement.setAttribute("data-mm-ready", "loaded");
          document.body.insertAdjacentHTML("afterbegin",
            "<div style='width:4px;height:4px;background:#00ff00'></div>");
        }, 40);</script></body></html>""",
    )
    shot = _capture((page,))[0]
    _width, _height, rgb = decode_png_rgb(shot.png)
    assert rgb[0:3] == b"\x00\xff\x00"


@pytest.mark.parametrize(
    "body",
    [
        "person@example.com",
        "See https://www.notion.so/workspace",
        "Open https://fixture.notion.site/page",
        "ntn_abcdefghij",
        "123e4567-e89b-12d3-a456-426614174000",
        "0123456789abcdef0123456789abcdef",
    ],
)
def test_rendered_secrets_are_refused(tmp_path: Path, chromium_installed: None, body: str) -> None:
    del chromium_installed
    page = _write(
        tmp_path,
        "secret.html",
        "<!DOCTYPE html><html data-mm-ready='loaded'><body><p>" + body + "</p></body></html>",
    )
    with pytest.raises(ValueError, match="sensitive_data"):
        _capture((page,))


def test_a_secret_that_is_not_painted_is_allowed(tmp_path: Path, chromium_installed: None) -> None:
    del chromium_installed
    page = _write(tmp_path, "hidden.html", _HIDDEN_EMAIL)
    shot = _capture((page,))[0]
    assert hashlib.sha256(shot.png).hexdigest() == shot.lineage.screenshot_sha256


def test_a_secret_assembled_into_the_dom_is_refused(
    tmp_path: Path, chromium_installed: None
) -> None:
    del chromium_installed
    page = _write(tmp_path, "assembled.html", _DELAYED_EMAIL)
    with pytest.raises(ValueError, match="sensitive_data"):
        _capture((page,))


def test_lineage_hash_and_build_version_are_independent(chromium_installed: None) -> None:
    del chromium_installed
    shot = _capture()[0]
    parsed = _fields(_lineage_chunk(shot.lineage_png))
    digest = hashlib.sha256(shot.png).hexdigest()
    assert parsed["screenshot_sha256"] == digest
    assert parsed["build_version"] == "5"
    assert parsed["product_id"] == str(_PRODUCT)
    assert parsed["source"] == "fixture"
    assert _strip_lineage(shot.lineage_png) == shot.png
    assert shot.lineage.screenshot_sha256 == digest
    assert shot.lineage.build_version == 5
    assert shot.lineage.qa_status == "passed"


def test_live_fetch_defaults_to_refusal() -> None:
    import inspect

    fetcher = inspect.signature(capture_variant_screenshots).parameters["fetcher"].default
    assert fetcher is default_live_fetcher
    with pytest.raises(ValueError, match="live_acquisition"):
        default_live_fetcher(_LIVE)
    page = VariantPage(name="Sage Green", live_url=_LIVE)
    with pytest.raises(ValueError, match="live_acquisition"):
        _capture((page,))


def test_an_injected_fetcher_is_what_a_live_url_calls(
    chromium_installed: None,
) -> None:
    del chromium_installed
    html = _FILES["Sage Green"].read_text(encoding="utf-8")
    seen: list[str] = []

    def _fetch(url: str) -> str:
        seen.append(url)
        return html

    page = VariantPage(name="Sage Green", live_url=_LIVE)
    shot = _capture((page,), fetcher=_fetch)[0]
    assert seen == [_LIVE]
    assert shot.lineage.source == "injected"
    assert shot.lineage.screenshot_sha256 == hashlib.sha256(shot.png).hexdigest()


def test_captures_satisfy_the_image_and_video_screenshot_inputs(
    tmp_path: Path, chromium_installed: None
) -> None:
    del chromium_installed
    shots = _capture()
    _written, digests = write_screenshot_inputs(shots, tmp_path)
    paths = fixture_screenshot_paths()
    paths["colour_options"] = tmp_path / "sage-green.png"
    allowed = fixture_screenshot_hashes() | digests
    assert refuse_unknown_image(paths, allowed) is None
    assert refuse_unknown_video(paths, allowed) is None
    decode_png_rgb((tmp_path / "sage-green.png").read_bytes())
