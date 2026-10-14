"""Gift PDFs refuse URL-like copy, link annotations, and document titles."""

from __future__ import annotations

import ast
import subprocess
import sys
import types
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from playwright.sync_api import sync_playwright

from money_machine.agents.contracts.merchandising import (
    FreeGiftConfig,
    ListingCopy,
    MerchandisingInput,
    encode_free_gift,
)
from money_machine.agents.implementations.merchandising import merchandise
from money_machine.assets.delivery_pdfs import (
    DeliveryPdfRefusal,
    pdf_page_count,
    refuse_gift_document_info,
    render_gift_pdf,
    render_readme_pdf,
)
from money_machine.assets.design_tokens import DesignTokens, listing_token_payload, load_tokens
from money_machine.assets.pdf_objects import page_texts
from tests.fixtures.merchandising import consistent_request
from tests.unit.assets.gift_pdf_craft import (
    embed_info_title,
    indirect_link,
    percent_packet,
    titled_page,
)
from tests.unit.assets.test_delivery_pdfs import DELIVERY_PDF_PATH, replace_fact

_BUILD = 4
_TITLE = "https://www.etsy.com/listing/123/planner"
_LINK_ROWS = (
    "Checklist at x.com/pay.",
    "Checklist at https:/x.com/cart.",
    "Checklist at gumroad.co/l/x",
    "Checklist at lemonsqueezy.com/buy/x",
    "Checklist at ko-fi.com/s/x",
    "Checklist at x.com/ch%65ckout",
    "Checklist at %63heckout",
    "Checklist at etsy.com/listing/123456/planner",
    "Checklist at etsy.me/x",
    "Checklist at bit.ly/x",
    "Checklist at paypal.me/x",
    "Checklist at x.com/buy",
    "Checklist at x.com/order",
    "Checklist at x.com/purchase",
    "Checklist at \uff50\uff41\uff59\uff0e\uff43\uff4f\uff4d",
    "Checklist at pay\u3002com",
    "Checklist at pay\uff61com",
    "Checklist at pay\uff0ecom",
    "Checklist at ch\uff0565ckout",
)
_CHARSET_ROWS = (
    "Checklist at x\u00b7com",
    "Checklist at x\u2027com",
    "Checklist at x\u30fbcom",
    "Checklist at x\uff65com",
    "Checklist at x\u0589com",
    "Checklist at x\u06d4com",
    "Checklist at x\u0701com",
    "Checklist at x\u0702com",
    "Checklist at x\u1362com",
    "Checklist at x\u2e33com",
    "Checklist at x\u2e3ccom",
    "Checklist at x\U00010a50com",
    "x.c\u00f3m",
    "Checklist at ETSY.COM",
    "Checklist /buy",
    "Checklist /order",
    "Notes 127.1/x",
)
_DOTTED_ROWS = (
    ".1.2.3.4",
    "Checklist .1.2.3.4",
    "Checklist at a.1.2.3.4",
)
_EXCLUDED_ROWS = (
    "Checklist a:b",
    "a@b",
    "50%",
    "a\\b",
    "a/b",
)
_FOLD_ROWS = (
    "Checklist \uff46\uff4f\uff4f",
    "4\uff0e9",
)
_CONCEALED_ROWS = (
    "Checklist at www.etsy.com/listing/123456/planner",
    "Checklist at w\u200bww.example",
)


@dataclass(frozen=True, slots=True)
class _Scene:
    request: MerchandisingInput
    copy: ListingCopy
    tokens: DesignTokens


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


@pytest.fixture(scope="module")
def scene(chromium_installed: None) -> _Scene:
    del chromium_installed
    request = consistent_request()
    copy = merchandise(request)
    return _Scene(request=request, copy=copy, tokens=load_tokens(listing_token_payload()))


def _named(scene: _Scene, name: str) -> tuple[MerchandisingInput, ListingCopy]:
    gift = FreeGiftConfig(offered=True, name=name)
    request = replace_fact(scene.request, "free_gift", encode_free_gift(gift))
    request = request.model_copy(update={"free_gift": gift})
    return request, merchandise(request)


def _spliced_claim(scene: _Scene, encoded: str) -> tuple[MerchandisingInput, ListingCopy]:
    """Reach the PDF gate when the contract or ``merchandise`` rejects the fact."""
    request = replace_fact(scene.request, "free_gift", encoded)
    claims = tuple(
        claim.model_copy(update={"stated_value": encoded}) if claim.kind == "free_gift" else claim
        for claim in scene.copy.draft.claims
    )
    draft = scene.copy.draft.model_copy(update={"claims": claims})
    return request, scene.copy.model_copy(update={"draft": draft})


def _concealed_name(
    scene: _Scene, name: str, community: str = "Planning circle"
) -> tuple[MerchandisingInput, ListingCopy]:
    gift = FreeGiftConfig(offered=True, name=name, community=community)
    return _spliced_claim(scene, encode_free_gift(gift))


@pytest.mark.parametrize(
    "name",
    (*_LINK_ROWS, *_CHARSET_ROWS, *_DOTTED_ROWS, *_EXCLUDED_ROWS, *_FOLD_ROWS),
)
def test_gift_domain_text_is_refused(scene: _Scene, name: str) -> None:
    request, copy = _named(scene, name)
    with pytest.raises(DeliveryPdfRefusal, match="paid_checkout"):
        render_gift_pdf(copy, request, scene.tokens, build_version=_BUILD)


@pytest.mark.parametrize("name", _CONCEALED_ROWS)
def test_concealed_gift_domain_text_is_refused(scene: _Scene, name: str) -> None:
    request, copy = _concealed_name(scene, name)
    with pytest.raises(DeliveryPdfRefusal, match="paid_checkout"):
        render_gift_pdf(copy, request, scene.tokens, build_version=_BUILD)


@pytest.mark.parametrize(
    ("name", "kept"),
    (
        ("Starter 4.9 kit", "4.9"),
        ("Notes e.g. habits", "e.g."),
        ("127.1", "127.1"),
        ("x . com", "x . com"),
        ("x[.]com", "x[.]com"),
        ("x dot com", "x dot com"),
        ("x.c0m", "x.c0m"),
        ("0x7f000001", "0x7f000001"),
        ("2130706433", "2130706433"),
    ),
)
def test_quantities_and_examples_render(scene: _Scene, name: str, kept: str) -> None:
    request, copy = _named(scene, name)
    rendered = render_gift_pdf(copy, request, scene.tokens, build_version=_BUILD)
    assert pdf_page_count(rendered.pdf) == 1
    assert kept in page_texts(rendered.pdf)[0]


@pytest.mark.parametrize(
    ("name", "community"),
    (
        ("Jos\u00e9", "Planning circle"),
        ("Zo\u00eb", "Planning circle"),
        ("Starter checklist", "Jos\u00e9"),
        ("Starter checklist", "Zo\u00eb"),
    ),
)
def test_non_ascii_gift_text_is_refused(scene: _Scene, name: str, community: str) -> None:
    gift = FreeGiftConfig(offered=True, name=name, community=community)
    request = replace_fact(scene.request, "free_gift", encode_free_gift(gift))
    request = request.model_copy(update={"free_gift": gift})
    copy = merchandise(request)
    with pytest.raises(DeliveryPdfRefusal, match="paid_checkout"):
        render_gift_pdf(copy, request, scene.tokens, build_version=_BUILD)


@pytest.mark.parametrize(
    "encoded",
    (
        "offered|\u043f\u0440\u0438\u043c\u0435\u0440.\u0440\u0444|Planning circle",
        "offered|Starter checklist|\u043f\u0440\u0438\u043c\u0435\u0440.\u0440\u0444",
        "offered|Starter checklist|Checklist checkout",
    ),
)
def test_spliced_gift_text_is_refused(scene: _Scene, encoded: str) -> None:
    request, copy = _spliced_claim(scene, encoded)
    with pytest.raises(DeliveryPdfRefusal, match="paid_checkout"):
        render_gift_pdf(copy, request, scene.tokens, build_version=_BUILD)


def _painted(pdf: bytes) -> Callable[..., bytes]:
    def paint(*_args: object) -> bytes:
        return pdf

    return paint


def test_painted_percent_text_is_refused(scene: _Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("money_machine.assets.delivery_pdfs._paint", _painted(percent_packet()))
    with pytest.raises(DeliveryPdfRefusal, match="paid_checkout"):
        render_gift_pdf(scene.copy, scene.request, scene.tokens, build_version=_BUILD)


def test_painted_link_is_refused(scene: _Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("money_machine.assets.delivery_pdfs._paint", _painted(indirect_link()))
    with pytest.raises(DeliveryPdfRefusal, match="paid_checkout"):
        render_gift_pdf(scene.copy, scene.request, scene.tokens, build_version=_BUILD)


def test_painted_title_is_refused(scene: _Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "money_machine.assets.delivery_pdfs._paint",
        _painted(titled_page("https://x.com")),
    )
    with pytest.raises(DeliveryPdfRefusal, match="paid_checkout"):
        render_gift_pdf(scene.copy, scene.request, scene.tokens, build_version=_BUILD)


def test_injected_gift_line_is_refused(scene: _Scene) -> None:
    with pytest.raises(DeliveryPdfRefusal, match="paid_checkout"):
        render_gift_pdf(
            scene.copy,
            scene.request,
            scene.tokens,
            build_version=_BUILD,
            injected_text="ftp://1.2.3.4/x",
        )


def _tuple_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return False
    return node.func.id == "tuple"


class _SwapPages(ast.NodeTransformer):
    def __init__(self) -> None:
        self.swapped = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name != "render_readme_pdf":
            return node
        for index, stmt in enumerate(node.body):
            value = stmt.value if isinstance(stmt, ast.Assign) else None
            if not (
                isinstance(value, ast.Tuple)
                and len(value.elts) == 2
                and all(_tuple_call(item) for item in value.elts)
            ):
                continue
            value.elts.reverse()
            reorder = ast.parse("blocks = blocks[4:] + blocks[:4]").body[0]
            node.body.insert(index + 1, reorder)
            self.swapped += 1
            break
        return node


def _swapped_readme() -> Callable[..., object]:
    module = types.ModuleType("swapped_readme_pdfs")
    module.__file__ = str(DELIVERY_PDF_PATH)
    swap = _SwapPages()
    tree = swap.visit(ast.parse(DELIVERY_PDF_PATH.read_text(encoding="utf-8")))
    if swap.swapped != 1 or not isinstance(tree, ast.Module):
        raise AssertionError(f"page tuples swapped {swap.swapped}")
    ast.fix_missing_locations(tree)
    sys.modules[module.__name__] = module
    exec(compile(tree, str(DELIVERY_PDF_PATH), "exec"), module.__dict__)
    render = module.__dict__["render_readme_pdf"]
    if not callable(render):
        raise AssertionError("render_readme_pdf")
    return render


def test_readme_pages_place_setup_before_access(scene: _Scene) -> None:
    rendered = render_readme_pdf(scene.copy, scene.request, scene.tokens, build_version=_BUILD)
    pages = page_texts(rendered.pdf)
    assert len(pages) == 2
    assert "Step 1. Open your template" in pages[0]
    assert "Step 3. Use the included resources" in pages[0]
    assert "Widgets: Today panel, Reminder list." in pages[0]
    assert "Please leave a review" not in pages[0]
    assert "Access link:" not in pages[0]
    assert "Variant " not in pages[0]
    assert "Access link:" in pages[1]
    assert "Duplicate the template. Access link" in pages[1]
    assert "Support channel: Email inbox." in pages[1]
    assert "Please leave a review for Fieldnote Shop." in pages[1]
    assert "Step 1." not in pages[1]


def test_readme_page_swap_mutant_accepts(scene: _Scene) -> None:
    render = _swapped_readme()
    result = render(scene.copy, scene.request, scene.tokens, build_version=_BUILD)
    pdf = getattr(result, "pdf", b"")
    assert isinstance(pdf, bytes)
    pages = page_texts(pdf)
    assert "Please leave a review for Fieldnote Shop." in pages[0]
    assert "Step 1. Open your template" in pages[1]


class _MoveFirstLink(ast.NodeTransformer):
    def __init__(self) -> None:
        self.moved = 0

    def visit_Slice(self, node: ast.Slice) -> ast.AST:
        if isinstance(node.upper, ast.Constant) and node.upper.value == 4:
            node.upper.value = 5
            self.moved += 1
        if isinstance(node.lower, ast.Constant) and node.lower.value == 4:
            node.lower.value = 5
            self.moved += 1
        return node


def _moved_readme() -> Callable[..., object]:
    module = types.ModuleType("moved_readme_pdfs")
    module.__file__ = str(DELIVERY_PDF_PATH)
    move = _MoveFirstLink()
    tree = move.visit(ast.parse(DELIVERY_PDF_PATH.read_text(encoding="utf-8")))
    if move.moved != 2 or not isinstance(tree, ast.Module):
        raise AssertionError(f"page slices moved {move.moved}")
    ast.fix_missing_locations(tree)
    sys.modules[module.__name__] = module
    exec(compile(tree, str(DELIVERY_PDF_PATH), "exec"), module.__dict__)
    render = module.__dict__["render_readme_pdf"]
    if not callable(render):
        raise AssertionError("render_readme_pdf")
    return render


def test_readme_first_variant_on_page_one_mutant_accepts(scene: _Scene) -> None:
    render = _moved_readme()
    result = render(scene.copy, scene.request, scene.tokens, build_version=_BUILD)
    pdf = getattr(result, "pdf", b"")
    assert isinstance(pdf, bytes) and pdf.startswith(b"%PDF")
    pages = page_texts(pdf)
    assert "Variant " in pages[0]
    assert "Access link:" in pages[0]
    assert "Step 1. Open your template" in pages[0]


def test_object_stream_title_is_not_a_byte_search(scene: _Scene) -> None:
    rendered = render_gift_pdf(scene.copy, scene.request, scene.tokens, build_version=_BUILD)
    embedded = embed_info_title(rendered.pdf, _TITLE)
    assert _TITLE.encode("ascii") not in embedded
    assert refuse_gift_document_info(embedded) == "paid_checkout"
