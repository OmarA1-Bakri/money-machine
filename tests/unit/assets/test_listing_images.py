"""Ten fixture listing images: claim text, screenshot allow-list, stable hashes."""

from __future__ import annotations

import ast
import hashlib
import struct
import subprocess
import sys
import types
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from money_machine.agents.contracts.merchandising import (
    IMAGE_ROLES,
    ListingCopy,
    MerchandisingInput,
)
from money_machine.agents.implementations.merchandising import merchandise
from money_machine.assets.design_tokens import (
    DesignTokens,
    TokenValidationError,
    listing_token_payload,
    load_tokens,
)
from money_machine.assets.listing_images import (
    LISTING_IMAGE_HEIGHT,
    LISTING_IMAGE_WIDTH,
    LISTING_TEMPLATE_VERSION,
    ListingImageLineage,
    ListingImageRefusal,
    RenderedListingImage,
    compose_listing_documents,
    extract_visible_text,
    merchandising_version,
    network_allowed,
    render_listing_images,
)
from money_machine.domain.services.claim_validation import validate_claims
from tests.fixtures.listing_screenshots import fixture_screenshot_hashes, fixture_screenshot_paths
from tests.fixtures.merchandising import PAGE_COUNT, consistent_request

_LISTING = (
    Path(__file__).resolve().parents[3] / "src" / "money_machine" / "assets" / "listing_images.py"
)
_BUILD = 4
_HUB_ROLES = ("hub_1", "hub_2", "hub_3", "hub_4", "hub_5")


@dataclass(frozen=True, slots=True)
class _Scene:
    request: MerchandisingInput
    copy: ListingCopy
    tokens: DesignTokens
    paths: dict[str, Path]
    allowed: frozenset[str]


class _DropRefusal(ast.NodeTransformer):
    """Delete ``if refuse_*(...) is not None``."""

    def __init__(self, callee: str) -> None:
        self.callee = callee
        self.dropped = 0

    def visit_If(self, node: ast.If) -> ast.AST | None:
        call = node.test.left if isinstance(node.test, ast.Compare) else None
        if (
            isinstance(node.test, ast.Compare)
            and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.IsNot)
            and isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == self.callee
        ):
            self.dropped += 1
            return None
        return self.generic_visit(node)


class _DropCall(ast.NodeTransformer):
    """Delete a bare ``load_tokens(...)`` statement."""

    def __init__(self, callee: str) -> None:
        self.callee = callee
        self.dropped = 0

    def visit_Expr(self, node: ast.Expr) -> ast.AST | None:
        call = node.value
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == self.callee
        ):
            self.dropped += 1
            return None
        return self.generic_visit(node)


def _exec_mutant(transform: ast.NodeTransformer, label: str) -> Callable[..., object]:
    tree = transform.visit(ast.parse(_LISTING.read_text(encoding="utf-8")))
    dropped = getattr(transform, "dropped", None)
    if dropped != 1 or not isinstance(tree, ast.Module):
        raise AssertionError(f"{label} dropped {dropped}")
    ast.fix_missing_locations(tree)
    name = f"listing_mutant_{label}"
    module = types.ModuleType(name)
    module.__file__ = str(_LISTING)
    sys.modules[name] = module
    exec(compile(tree, str(_LISTING), "exec"), module.__dict__)
    render = module.__dict__["render_listing_images"]
    if not callable(render):
        raise AssertionError(label)
    return render


def _mutant_render(callee: str) -> Callable[..., object]:
    return _exec_mutant(_DropRefusal(callee), callee)


def _launch_chromium() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        browser.close()


@pytest.fixture(scope="module", autouse=True)
def chromium_installed() -> None:
    """Install Playwright's Chromium only when this machine cannot launch it."""
    try:
        _launch_chromium()
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        _launch_chromium()


@pytest.fixture(scope="module")
def scene(chromium_installed: None) -> _Scene:
    del chromium_installed
    request = consistent_request()
    copy = merchandise(request)
    assert validate_claims(copy.draft, request).passed is True
    paths = fixture_screenshot_paths()
    allowed = fixture_screenshot_hashes()
    assert len(paths) == 10
    assert len(allowed) == 10
    return _Scene(
        request=request,
        copy=copy,
        tokens=load_tokens(listing_token_payload()),
        paths=paths,
        allowed=allowed,
    )


def _render(
    scene: _Scene,
    *,
    request: MerchandisingInput | None = None,
    copy: ListingCopy | None = None,
    paths: Mapping[str, Path] | None = None,
    allowed: frozenset[str] | None = None,
    tokens: DesignTokens | None = None,
    injected_text: str = "",
) -> tuple[RenderedListingImage, ...]:
    return render_listing_images(
        scene.copy if copy is None else copy,
        scene.request if request is None else request,
        scene.paths if paths is None else paths,
        scene.allowed if allowed is None else allowed,
        scene.tokens if tokens is None else tokens,
        build_version=_BUILD,
        injected_text=injected_text,
    )


def _png_size(png: bytes) -> tuple[int, int]:
    if png[:8] != b"\x89PNG\r\n\x1a\n" or png[12:16] != b"IHDR":
        raise AssertionError("png header")
    return struct.unpack(">II", png[16:24])


def _bad_tag_copy(copy: ListingCopy) -> ListingCopy:
    first = copy.draft.tags[0]
    updated = first.model_copy(update={"text": "500 sold"})
    draft = copy.draft.model_copy(update={"tags": (updated, *copy.draft.tags[1:])})
    return copy.model_copy(update={"draft": draft})


def _white_tokens() -> DesignTokens:
    payload = listing_token_payload()
    palette = payload["palette"]
    if not isinstance(palette, dict):
        raise AssertionError("palette")
    replaced = dict(palette)
    replaced["text"] = "#FFFFFF"
    replaced["background"] = "#FFFFFF"
    payload["palette"] = replaced
    return DesignTokens.model_validate(payload)


def _accepted(render: Callable[..., object], scene: _Scene, **kwargs: object) -> tuple[object, ...]:
    result = render(
        kwargs.get("copy", scene.copy),
        kwargs.get("request", scene.request),
        kwargs.get("paths", scene.paths),
        kwargs.get("allowed", scene.allowed),
        kwargs.get("tokens", scene.tokens),
        build_version=_BUILD,
        injected_text=kwargs.get("injected_text", ""),
    )
    if not isinstance(result, tuple) or len(result) != 10:
        raise AssertionError("mutant did not return ten images")
    for item in result:
        png = getattr(item, "png", None)
        if not isinstance(png, bytes) or not png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise AssertionError("mutant image is not a png")
    return result


@pytest.fixture(scope="module")
def rendered(scene: _Scene) -> tuple[RenderedListingImage, ...]:
    return _render(scene)


def test_network_stays_on_local_urls() -> None:
    assert network_allowed("data:font/ttf;base64,AAAA") is True
    assert network_allowed("file:///tmp/listing.png") is True
    assert network_allowed("about:blank") is True
    assert network_allowed("https://fixture.notion.site") is False
    assert network_allowed("http://example.test/font.ttf") is False


def test_documents_show_only_the_validated_image_line(scene: _Scene) -> None:
    documents = compose_listing_documents(scene.copy, scene.paths, scene.tokens)
    assert tuple(role for role, _html in documents) == IMAGE_ROLES
    lines = {line.role: line.text for line in scene.copy.draft.image_strip}
    request = scene.request
    assert lines["overview"] == f"{PAGE_COUNT} pages in {request.spec.identity}."
    for role, hub in zip(_HUB_ROLES, request.hubs[:5], strict=True):
        assert lines[role] == f"Hub: {hub}."
    for role, html in documents:
        assert extract_visible_text(html) == (lines[role],)
        assert f'class="mm-frame {_frame_class(role)}"' in html
        assert "https://" not in html.split("<article", maxsplit=1)[0]
    colour = dict(documents)["colour_options"]
    assert colour.count('class="mm-swatch"') == 3
    assert "mm-phone" in dict(documents)["devices"]
    assert "mm-tablet" in dict(documents)["devices"]
    assert "<circle" in dict(documents)["how_it_works"]


def _frame_class(role: str) -> str:
    if role.startswith("hub_"):
        return "mm-hub-slide"
    classes = {
        "colour_options": "mm-colour-options",
        "how_it_works": "mm-how-it-works",
        "devices": "mm-device-compatibility",
    }
    return classes.get(role, f"mm-{role}")


def test_all_ten_images_render_with_lineage(
    scene: _Scene, rendered: tuple[RenderedListingImage, ...]
) -> None:
    request = scene.request
    assert tuple(image.lineage.role for image in rendered) == IMAGE_ROLES
    version = merchandising_version(scene.copy.draft)
    hashes = [image.lineage.output_sha256 for image in rendered]
    assert len(set(hashes)) == 10
    for image in rendered:
        record = image.lineage
        assert isinstance(record, ListingImageLineage)
        assert record.product_id == request.spec.product_id
        assert record.spec_version == request.spec.version
        assert record.build_version == _BUILD
        assert record.merchandising_version == version
        assert record.template_version == LISTING_TEMPLATE_VERSION
        assert record.qa_status == "passed"
        assert record.width_px == LISTING_IMAGE_WIDTH
        assert record.height_px == LISTING_IMAGE_HEIGHT
        assert _png_size(image.png) == (LISTING_IMAGE_WIDTH, LISTING_IMAGE_HEIGHT)
        assert hashlib.sha256(image.png).hexdigest() == record.output_sha256
        source = hashlib.sha256(scene.paths[record.role].read_bytes()).hexdigest()
        assert record.source_screenshot_sha256 == (source,)
        assert f"spec_version={record.spec_version}\n".encode() in image.png
        assert b"mm-lineage" in image.png


def test_the_same_inputs_render_the_same_png(
    scene: _Scene, rendered: tuple[RenderedListingImage, ...]
) -> None:
    again = _render(scene)
    assert tuple(image.png for image in again) == tuple(image.png for image in rendered)
    assert tuple(image.lineage.output_sha256 for image in again) == tuple(
        image.lineage.output_sha256 for image in rendered
    )


def test_a_changed_spec_version_changes_lineage_and_hash(
    scene: _Scene,
    rendered: tuple[RenderedListingImage, ...],
) -> None:
    request = scene.request
    bumped = request.model_copy(
        update={"spec": request.spec.model_copy(update={"version": request.spec.version + 1})}
    )
    again = _render(scene, request=bumped)
    assert merchandising_version(scene.copy.draft) == rendered[0].lineage.merchandising_version
    for original, updated in zip(rendered, again, strict=True):
        assert updated.lineage.spec_version == original.lineage.spec_version + 1
        assert updated.lineage.merchandising_version == original.lineage.merchandising_version
        assert updated.lineage.source_screenshot_sha256 == original.lineage.source_screenshot_sha256
        assert updated.lineage.product_id == original.lineage.product_id
        assert updated.lineage.output_sha256 != original.lineage.output_sha256
        assert updated.png != original.png


def test_unsupported_copy_is_refused_and_the_mutant_accepts(scene: _Scene) -> None:
    bad = _bad_tag_copy(scene.copy)
    assert validate_claims(bad.draft, scene.request).passed is False
    with pytest.raises(ListingImageRefusal, match="unsupported_claim"):
        _render(scene, copy=bad)
    accepted = _accepted(_mutant_render("refuse_unvalidated_copy"), scene, copy=bad)
    assert len(accepted) == 10


def test_unclaimed_text_is_refused_and_the_mutant_accepts(scene: _Scene) -> None:
    stray = "Bestseller 500 sold"
    with pytest.raises(ListingImageRefusal, match="unsupported_claim"):
        _render(scene, injected_text=stray)
    accepted = _accepted(
        _mutant_render("refuse_unclaimed_rendered_text"),
        scene,
        injected_text=stray,
    )
    assert len(accepted) == 10


def test_a_missing_screenshot_is_refused_and_the_mutant_accepts(
    scene: _Scene, tmp_path: Path
) -> None:
    paths = dict(scene.paths)
    paths["hero"] = tmp_path / "missing.png"
    with pytest.raises(ListingImageRefusal, match="missing_screenshot"):
        _render(scene, paths=paths)
    accepted = _accepted(_mutant_render("refuse_missing_screenshot"), scene, paths=paths)
    assert len(accepted) == 10


def test_an_unknown_screenshot_is_refused_and_the_mutant_accepts(
    scene: _Scene, tmp_path: Path
) -> None:
    alien = tmp_path / "alien.png"
    alien.write_bytes(b"\x89PNG-not-an-allow-listed-fixture-screenshot")
    paths = dict(scene.paths)
    paths["devices"] = alien
    with pytest.raises(ListingImageRefusal, match="unknown_screenshot"):
        _render(scene, paths=paths)
    accepted = _accepted(_mutant_render("refuse_unknown_screenshot"), scene, paths=paths)
    assert len(accepted) == 10


def test_render_refuses_low_contrast_and_the_mutant_paints(scene: _Scene) -> None:
    tokens = _white_tokens()
    with pytest.raises(TokenValidationError, match="low_contrast"):
        _render(scene, tokens=tokens)
    accepted = _accepted(
        _exec_mutant(_DropCall("load_tokens"), "load_tokens"), scene, tokens=tokens
    )
    assert len(accepted) == 10
