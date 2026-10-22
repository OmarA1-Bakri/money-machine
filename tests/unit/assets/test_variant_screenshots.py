"""Fixture variant screenshots: template, crop, readiness, secrets, lineage."""

from __future__ import annotations

import hashlib
import html
import inspect
import struct
import subprocess
import sys
import threading
import unicodedata
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import UUID

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from money_machine.assets.listing_images import refuse_unknown_screenshot as refuse_unknown_image
from money_machine.assets.screenshot_text import (
    email_rule_matches,
    escape_fixture,
    fill_template,
    notion_host_rule_matches,
    token_rule_matches,
)
from money_machine.assets.screenshots import (
    LAUNCH_ARGS,
    SCREENSHOT_TEMPLATE_VERSION,
    CapturedScreenshot,
    ScreenshotLineage,
    ScreenshotRefusal,
    VariantPage,
    _bind_lineage_png,  # pyright: ignore[reportPrivateUsage]
    _paint_documents,  # pyright: ignore[reportPrivateUsage]
    _write_exclusive,  # pyright: ignore[reportPrivateUsage]
    capture_variant_screenshots,
    default_live_fetcher,
    open_screenshot_context,
    variant_template_path,
    write_screenshot_inputs,
)
from money_machine.assets.video import refuse_unknown_screenshot as refuse_unknown_video
from money_machine.assets.video_paint import decode_png_rgb
from tests.fixtures.listing_screenshots import fixture_screenshot_hashes, fixture_screenshot_paths
from tests.fixtures.merchandising import consistent_request

_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "variant_pages"
_TEMPLATE_SHA256 = "f38abcd419f3ff5dfb23264e2f63ad2c597e255cc1728b1cb4fe48237b505866"
_PNG_SHA256 = "2efb97e6c323fe81f763181f2d773d167a49b6f5ca29452e8778a5e9a60d836b"
_BUILD = 5
_PRODUCT = UUID("00000000-0000-4000-8000-0000000000b1")
_VARIANTS = ("Sage Green", "Navy Blue", "Rose Gold")
_LIVE = "https://www.notion.so/private-variant-page"
_HOSTILE = """<!DOCTYPE html>
<html data-mm-ready="loaded">
<body style="margin:0;background:#ff00ff"><p>Sample fixture Sage Green</p></body>
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
_DELAYED_EMAIL = """<!DOCTYPE html>
<html data-mm-ready="loaded">
<body style="margin:0;background:#112233">
<div id="swatch" style="width:4px;height:4px;background:#00ff00"></div>
<p style="margin:12px">Sample fixture</p>
<script>
document.getElementById("swatch").style.background = "#ff00ff";
setTimeout(function () {
  var node = document.createElement("p");
  node.textContent = "person@example.com";
  document.body.appendChild(node);
  document.getElementById("swatch").style.background = "#ff00ff";
}, 60);
</script>
</body>
</html>
"""
_BEFORE = """<!DOCTYPE html>
<html data-mm-ready="loaded">
<head><style>body::before { content: "BEFORE"; }</style></head>
<body style="margin:0;background:#112233">
<div style="width:4px;height:4px;background:#00ff00"></div>
<p style="margin:12px">Sample fixture</p>
</body>
</html>
"""
_AFTER = """<!DOCTYPE html>
<html data-mm-ready="loaded">
<head><style>body::after { content: "AFTER"; }</style></head>
<body style="margin:0;background:#112233">
<div style="width:4px;height:4px;background:#00ff00"></div>
<p style="margin:12px">Sample fixture</p>
</body>
</html>
"""
_CONTROLS = """<!DOCTYPE html>
<html data-mm-ready="loaded">
<body style="margin:0;background:#112233">
<input><textarea></textarea><canvas></canvas><iframe></iframe>
<p>Sample fixture</p>
</body>
</html>
"""
_SHADOW = """<!DOCTYPE html>
<html data-mm-ready="loaded">
<body style="margin:0;background:#112233">
<div style="width:4px;height:4px;background:#00ff00"></div>
<p style="margin:12px">Sample fixture</p>
<div><template shadowrootmode="open"><span>inside</span></template></div>
</body>
</html>
"""
_NETWORK_PAGE = """<!DOCTYPE html>
<html><body>
<img src="/img.png">
<link rel="stylesheet" href="/app.css">
<iframe src="/frame"></iframe>
<script>
fetch("/fetch");
navigator.sendBeacon("/beacon", "x");
new WebSocket("ws://" + location.host + "/ws");
navigator.serviceWorker.register("/sw.js");
</script>
</body></html>
"""


def _launch_chromium() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        browser.close()


@pytest.fixture(scope="module", autouse=True)
def _browser() -> None:  # pyright: ignore[reportUnusedFunction]
    try:
        _launch_chromium()
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        _launch_chromium()


def _pages() -> tuple[VariantPage, ...]:
    return tuple(VariantPage(name=name) for name in _VARIANTS)


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


def _shot(name: str, payload: bytes = b"png") -> CapturedScreenshot:
    digest = hashlib.sha256(payload).hexdigest()
    lineage = ScreenshotLineage(
        product_id=_PRODUCT,
        spec_version=1,
        build_version=_BUILD,
        screenshot_sha256=digest,
        variant=name,
        template_version=SCREENSHOT_TEMPLATE_VERSION,
        viewport_width=480,
        viewport_height=360,
        crop_x=0,
        crop_y=0,
        crop_width=480,
        crop_height=270,
        qa_status="passed",
        source="fixture",
    )
    return CapturedScreenshot(png=payload, lineage_png=payload, lineage=lineage)


def _template() -> str:
    return (_ROOT / "variant.html").read_text(encoding="utf-8")


def test_the_variant_template_is_pinned() -> None:
    files = sorted(path.name for path in _ROOT.iterdir())
    assert files == ["variant.html"]
    digest = hashlib.sha256((_ROOT / "variant.html").read_bytes()).hexdigest()
    assert digest == _TEMPLATE_SHA256
    assert variant_template_path() == _ROOT / "variant.html"


def test_viewport_is_clipped_and_has_no_chrome() -> None:
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


def test_the_canonical_png_hash_is_pinned() -> None:
    shot = _capture((VariantPage(name="Sage Green"),))[0]
    assert hashlib.sha256(shot.png).hexdigest() == _PNG_SHA256


def test_the_same_fixture_has_the_same_hash() -> None:
    first = _capture()
    second = _capture()
    assert tuple(shot.png for shot in first) == tuple(shot.png for shot in second)
    hashes = [hashlib.sha256(shot.png).hexdigest() for shot in first]
    assert len(set(hashes)) == 3


def test_capture_protocol_failure_recreates_and_revalidates_page(monkeypatch) -> None:
    import money_machine.assets.screenshots as module

    original = module._clip  # pyright: ignore[reportPrivateUsage]
    pages = []
    checks = []
    validate = module.refuse_rendered_text

    def checked(text):
        checks.append(text)
        return validate(text)

    def failed_once(page):
        pages.append(page)
        if len(pages) == 1:
            raise PlaywrightError(
                "Page.screenshot: Protocol error (Page.captureScreenshot): "
                "Unable to capture screenshot\n"
                "Call log:\n  - fonts loaded"
            )
        return original(page)

    monkeypatch.setattr(module, "_clip", failed_once)
    monkeypatch.setattr(module, "refuse_rendered_text", checked)
    shot = _capture((VariantPage(name="Sage Green"),))[0]
    assert hashlib.sha256(shot.png).hexdigest() == _PNG_SHA256
    assert len(pages) == len(checks) == 2 and pages[0] is not pages[1]
    assert all(page.is_closed() for page in pages)


@pytest.mark.parametrize(
    ("message", "expected_calls"),
    [
        (
            "Page.screenshot: Protocol error (Page.captureScreenshot): "
            "Unable to capture screenshot",
            2,
        ),
        ("Page.screenshot: Target page, context or browser has been closed", 1),
        ("Page.screenshot: Timeout 30000ms exceeded", 1),
    ],
)
def test_capture_persistent_or_other_browser_error_propagates(monkeypatch, message, expected_calls):
    import money_machine.assets.screenshots as module

    pages = []

    def fail(page):
        pages.append(page)
        raise PlaywrightError(message)

    monkeypatch.setattr(module, "_clip", fail)
    with pytest.raises(PlaywrightError, match=r"Page\.screenshot"):
        _capture((VariantPage(name="Sage Green"),))
    assert len(pages) == expected_calls and all(page.is_closed() for page in pages)


def test_capture_second_page_cannot_bypass_sensitive_text_refusal(monkeypatch) -> None:
    import money_machine.assets.screenshots as module

    clips, validations = [], []

    def fail(page):
        clips.append(page)
        raise PlaywrightError(
            "Page.screenshot: Protocol error (Page.captureScreenshot): Unable to capture screenshot"
        )

    def refuse_second(text):
        validations.append(text)
        return "sensitive_data" if len(validations) == 2 else None

    monkeypatch.setattr(module, "_clip", fail)
    monkeypatch.setattr(module, "refuse_rendered_text", refuse_second)
    with pytest.raises(ScreenshotRefusal, match="sensitive_data"):
        _capture((VariantPage(name="Sage Green"),))
    assert len(clips) == 1 and len(validations) == 2


def test_a_missing_readiness_marker_is_refused() -> None:
    html_doc = "<!DOCTYPE html><html><body><p>Sample fixture</p></body></html>"
    with pytest.raises(ScreenshotRefusal, match="not_ready"):
        _paint_documents((html_doc,))


def test_a_delayed_email_script_cannot_paint() -> None:
    png = _paint_documents((_DELAYED_EMAIL,))[0]
    _width, _height, rgb = decode_png_rgb(png)
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
def test_rendered_secrets_are_refused(body: str) -> None:
    html_doc = "<!DOCTYPE html><html data-mm-ready='loaded'><body><p>" + body + "</p></body></html>"
    with pytest.raises(ScreenshotRefusal, match="sensitive_data"):
        _paint_documents((html_doc,))


def test_rendered_fullwidth_at_is_refused() -> None:
    html_doc = (
        "<!DOCTYPE html><html data-mm-ready='loaded'><body>"
        "<p>user\uff20example.com</p></body></html>"
    )
    with pytest.raises(ScreenshotRefusal, match="sensitive_data"):
        _paint_documents((html_doc,))


def test_a_secret_that_is_not_painted_is_allowed() -> None:
    png = _paint_documents((_HIDDEN_EMAIL,))[0]
    assert png.startswith(b"\x89PNG")


def test_generated_before_content_is_refused() -> None:
    with pytest.raises(ScreenshotRefusal, match="structure"):
        _paint_documents((_BEFORE,))


def test_generated_after_content_is_refused() -> None:
    with pytest.raises(ScreenshotRefusal, match="structure"):
        _paint_documents((_AFTER,))


def test_form_canvas_and_iframe_are_refused() -> None:
    with pytest.raises(ScreenshotRefusal, match="structure"):
        _paint_documents((_CONTROLS,))


def test_a_declarative_shadow_root_is_refused() -> None:
    with pytest.raises(ScreenshotRefusal, match="structure"):
        _paint_documents((_SHADOW,))


def _service_worker_hits(*, allow: bool) -> list[str]:
    hits: list[str] = []
    page_html = _NETWORK_PAGE.encode()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            hits.append(self.path)
            body = page_html if self.path == "/" else b""
            self.send_response(200)
            self.send_header("content-type", "text/html")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            hits.append(self.path)
            self.send_response(204)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        doc = f"http://127.0.0.1:{port}/"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=list(LAUNCH_ARGS))
            try:
                if allow:
                    context = open_screenshot_context(
                        browser,
                        javascript=True,
                        allowed_http=(doc,),
                        service_workers="allow",
                    )
                else:
                    context = open_screenshot_context(browser, javascript=True, allowed_http=(doc,))
                try:
                    page = context.new_page()
                    page.goto(doc, wait_until="domcontentloaded", timeout=4000)
                    page.wait_for_timeout(500)
                finally:
                    context.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
    return hits


def test_the_fixture_context_makes_no_network_requests() -> None:
    assert _service_worker_hits(allow=False) == ["/"]


def test_allowing_service_workers_fetches_the_worker_script() -> None:
    assert "/sw.js" in _service_worker_hits(allow=True)


def test_lineage_hash_and_build_version_are_independent() -> None:
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
    fetcher = inspect.signature(capture_variant_screenshots).parameters["fetcher"].default
    assert fetcher is default_live_fetcher
    with pytest.raises(ScreenshotRefusal, match="live_acquisition"):
        default_live_fetcher(_LIVE)
    page = VariantPage(name="Sage Green", live_url=_LIVE)
    with pytest.raises(ScreenshotRefusal, match="live_acquisition"):
        _capture((page,))


def test_fetcher_html_is_not_painted() -> None:
    seen: list[str] = []

    def _fetch(url: str) -> str:
        seen.append(url)
        return _HOSTILE

    page = VariantPage(name="Sage Green", live_url=_LIVE)
    shot = _capture((page,), fetcher=_fetch)[0]
    plain = _capture((VariantPage(name="Sage Green"),))[0]
    assert seen == [_LIVE]
    assert shot.lineage.source == "injected"
    assert shot.png == plain.png


def test_an_html_path_is_not_painted(tmp_path: Path) -> None:
    path = tmp_path / "hostile.html"
    path.write_text(_HOSTILE, encoding="utf-8")
    shot = _capture((VariantPage(name="Sage Green", html_path=path),))[0]
    plain = _capture((VariantPage(name="Sage Green"),))[0]
    assert shot.png == plain.png


def test_no_pages_are_refused() -> None:
    with pytest.raises(ScreenshotRefusal, match="missing_page"):
        _capture(())


def test_a_missing_page_is_screenshot_refusal(tmp_path: Path) -> None:
    page = VariantPage(name="Sage Green", html_path=tmp_path / "missing.html")
    with pytest.raises(ScreenshotRefusal, match="missing_page"):
        _capture((page,))


def test_a_newline_in_the_variant_name_is_refused() -> None:
    page = VariantPage(name="Navy\nbuild_version=99")
    with pytest.raises(ScreenshotRefusal, match="output_name"):
        _capture((page,))


def _refuse_name(name: str, code: str) -> None:
    with pytest.raises(ScreenshotRefusal, match=code):
        _capture((VariantPage(name=name),))


def _refuse_rendered(body: str, code: str) -> None:
    html_doc = "<!DOCTYPE html><html data-mm-ready='loaded'><body><p>" + body + "</p></body></html>"
    with pytest.raises(ScreenshotRefusal, match=code):
        _paint_documents((html_doc,))


def test_notion_so_case_is_refused() -> None:
    _refuse_name("NOTION.SO", "sensitive_data")


def test_fullwidth_at_is_refused() -> None:
    _refuse_rendered("user\uff20example.com", "sensitive_data")


def test_a_zero_width_space_in_an_email_is_refused() -> None:
    _refuse_rendered("ceo\u200b@acme-corp.com", "sensitive_data")


def test_a_soft_hyphen_in_an_email_is_refused() -> None:
    _refuse_rendered("ceo\u00ad@acme-corp.com", "sensitive_data")


def test_a_fullwidth_dot_host_is_refused() -> None:
    _refuse_rendered("notion\uff0eso", "sensitive_data")


def test_a_cyrillic_o_host_is_refused() -> None:
    _refuse_rendered("n\u043etion.so", "sensitive_data")


def test_a_bidi_reversed_host_is_refused() -> None:
    _refuse_rendered("\u202eos.noiton", "sensitive_data")


def test_a_cyrillic_i_host_is_refused() -> None:
    _refuse_name("not\u0456on.so", "fixture_charset")


def test_a_greek_omicron_host_is_refused() -> None:
    _refuse_name("n\u03bftion.so", "fixture_charset")


def test_a_combining_grapheme_joiner_is_refused() -> None:
    _refuse_name("not\u034fion.so", "fixture_charset")


def test_fullwidth_notion_so_is_refused_before_fold() -> None:
    value = "\uff4e\uff4f\uff54\uff49\uff4f\uff4e\uff0e\uff53\uff4f"
    assert notion_host_rule_matches(unicodedata.normalize("NFKC", value)) is True
    _refuse_name(value, "fixture_charset")


def test_an_ascii_email_is_refused() -> None:
    _refuse_name("ceo@acme-corp.com", "sensitive_data")


def test_secret_token_at_notion_is_refused() -> None:
    value = "secret_token@notion.so"
    assert token_rule_matches(value) is False
    assert email_rule_matches(value) is True
    assert notion_host_rule_matches(value) is True
    _refuse_name(value, "sensitive_data")


def test_a_bare_ntn_is_refused() -> None:
    _refuse_name("ntnabcdefghij", "sensitive_data")


def test_a_bearer_token_with_a_space_is_refused() -> None:
    _refuse_name("Bearer abcdefghij", "sensitive_data")


def test_a_fullwidth_less_than_is_refused() -> None:
    _refuse_name("\uff1ctemplate", "fixture_charset")


def test_a_latin1_zoe_is_refused() -> None:
    """U+00EB is inside Latin-1 and above 127. A ``> 255`` check would accept it."""
    _refuse_name("Zo\u00eb", "fixture_charset")


def test_an_ampersand_in_a_fixture_value_is_refused() -> None:
    _refuse_name("A & B", "fixture_markup")


def test_an_apostrophe_in_a_fixture_value_is_refused() -> None:
    _refuse_name("O'Brien", "fixture_markup")


def test_a_github_token_is_refused() -> None:
    _refuse_name("ghp_abcdefghijklmnop", "sensitive_data")


def test_an_aws_access_key_is_refused() -> None:
    _refuse_name("AKIAAAAAAAAAAAAAAAAA", "sensitive_data")


def test_a_slack_bot_token_is_refused() -> None:
    _refuse_name("xoxb-1234567890", "sensitive_data")


def test_a_template_needs_two_label_slots() -> None:
    with pytest.raises(ScreenshotRefusal, match="template"):
        fill_template("<p>{{label}}</p>", "Sage Green")
    with pytest.raises(ScreenshotRefusal, match="template"):
        fill_template("{{label}}{{label}}{{label}}", "Sage Green")


def test_lineage_text_is_ascii() -> None:
    png = next(iter(fixture_screenshot_paths().values())).read_bytes()
    with pytest.raises(ScreenshotRefusal, match="lineage"):
        _bind_lineage_png(png, "variant=\u0456")


def test_markup_in_a_fixture_value_is_refused_and_escaped() -> None:
    values = (
        '<template shadowrootmode="open">x</template>',
        '<iframe srcdoc="<p>x</p>"></iframe>',
    )
    template = _template()
    for value in values:
        with pytest.raises(ScreenshotRefusal, match="fixture_markup"):
            _capture((VariantPage(name=value),))
        assert escape_fixture(value) == html.escape(value, quote=True)
        filled = fill_template(template, value)
        assert "<template" not in filled
        assert "<iframe" not in filled


def test_an_attribute_quote_breakout_is_refused_and_escaped() -> None:
    value = 'x" data-breakout="yes'
    with pytest.raises(ScreenshotRefusal, match="fixture_markup"):
        _capture((VariantPage(name=value),))
    escaped = escape_fixture(value)
    assert escaped == html.escape(value, quote=True)
    assert '"' not in escaped
    filled = fill_template(_template(), value)
    assert filled.count(escaped) == 2


def test_an_empty_output_name_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ScreenshotRefusal, match="output_name"):
        write_screenshot_inputs((_shot(""),), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_name_that_slugs_to_empty_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ScreenshotRefusal, match="output_name"):
        write_screenshot_inputs((_shot("---"),), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_duplicate_names_are_refused(tmp_path: Path) -> None:
    shots = (_shot("Sage Green", b"a"), _shot("Sage Green", b"b"))
    with pytest.raises(ScreenshotRefusal, match="output_collision"):
        write_screenshot_inputs(shots, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_colliding_slugs_are_refused_before_write(tmp_path: Path) -> None:
    shots = (_shot("Navy Blue", b"a"), _shot("navy-blue", b"b"))
    with pytest.raises(ScreenshotRefusal, match="output_collision"):
        write_screenshot_inputs(shots, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_newline_name_is_refused_before_write(tmp_path: Path) -> None:
    with pytest.raises(ScreenshotRefusal, match="output_name"):
        write_screenshot_inputs((_shot("Navy\nbuild_version=99"),), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_symlink_to_an_empty_directory_is_refused(tmp_path: Path) -> None:
    victim = tmp_path / "victim"
    victim.mkdir()
    link = tmp_path / "out"
    link.symlink_to(victim, target_is_directory=True)
    with pytest.raises(ScreenshotRefusal, match="output_path"):
        write_screenshot_inputs((_shot("Sage Green"),), link)
    assert list(victim.iterdir()) == []


def test_the_output_directory_is_replaced(tmp_path: Path) -> None:
    before = tmp_path.stat().st_ino
    write_screenshot_inputs((_shot("Sage Green", b"one"),), tmp_path)
    assert tmp_path.stat().st_ino != before
    assert (tmp_path / "sage-green.png").read_bytes() == b"one"


def test_a_symlink_directory_is_refused(tmp_path: Path) -> None:
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_text("safe", encoding="utf-8")
    link = tmp_path / "out"
    link.symlink_to(victim, target_is_directory=True)
    with pytest.raises(ScreenshotRefusal, match="output_path"):
        write_screenshot_inputs((_shot("Sage Green"),), link)
    assert (victim / "keep.txt").read_text(encoding="utf-8") == "safe"
    assert not (victim / "sage-green.png").exists()


def test_a_symlink_output_is_not_followed(tmp_path: Path) -> None:
    victim = tmp_path / "victim.png"
    victim.write_bytes(b"victim")
    out = tmp_path / "out"
    out.mkdir()
    (out / "sage-green.png").symlink_to(victim)
    with pytest.raises(ScreenshotRefusal, match="output_path"):
        write_screenshot_inputs((_shot("Sage Green"),), out)
    assert victim.read_bytes() == b"victim"


def test_an_existing_file_is_not_truncated(tmp_path: Path) -> None:
    target = tmp_path / "sage-green.png"
    target.write_bytes(b"old")
    with pytest.raises(FileExistsError):
        _write_exclusive(target, b"new")
    assert target.read_bytes() == b"old"


def test_a_symlink_file_is_not_followed(tmp_path: Path) -> None:
    victim = tmp_path / "victim.png"
    victim.write_bytes(b"victim")
    link = tmp_path / "sage-green.png"
    link.symlink_to(victim)
    with pytest.raises(FileExistsError):
        _write_exclusive(link, b"new")
    assert victim.read_bytes() == b"victim"


def test_a_stale_file_is_left_in_place(tmp_path: Path) -> None:
    stale = tmp_path / "stale.png"
    stale.write_bytes(b"stale")
    with pytest.raises(ScreenshotRefusal, match="output_path"):
        write_screenshot_inputs((_shot("Sage Green"),), tmp_path)
    assert stale.read_bytes() == b"stale"


def test_the_allowlist_is_only_this_run(tmp_path: Path) -> None:
    shot = _shot("Sage Green", b"one")
    _paths, digests = write_screenshot_inputs((shot,), tmp_path)
    assert digests == frozenset({shot.lineage.screenshot_sha256})
    assert (tmp_path / "sage-green.png").read_bytes() == b"one"


def test_captures_satisfy_the_image_and_video_screenshot_inputs(tmp_path: Path) -> None:
    shots = _capture()
    _written, digests = write_screenshot_inputs(shots, tmp_path)
    assert digests == {shot.lineage.screenshot_sha256 for shot in shots}
    paths = fixture_screenshot_paths()
    paths["colour_options"] = tmp_path / "sage-green.png"
    allowed = fixture_screenshot_hashes() | digests
    assert refuse_unknown_image(paths, allowed) is None
    assert refuse_unknown_video(paths, allowed) is None
    decode_png_rgb((tmp_path / "sage-green.png").read_bytes())
