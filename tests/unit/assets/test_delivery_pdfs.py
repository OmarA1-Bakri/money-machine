"""README and free-gift PDFs: page counts, claim text, paid links, stable bytes."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import types
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from money_machine.agents.contracts.merchandising import (
    FreeGiftConfig,
    ListingCopy,
    MerchandisingInput,
    NotificationDashboardBehaviour,
    encode_dashboard,
    encode_free_gift,
)
from money_machine.agents.implementations.merchandising import merchandise
from money_machine.assets.delivery_pdfs import (
    PDF_TEMPLATE_VERSION,
    DeliveryPdfRefusal,
    RenderedDeliveryPdf,
    compose_delivery_html,
    gift_blocks,
    pdf_page_count,
    readme_blocks,
    refuse_unvalidated_copy,
    render_gift_pdf,
    render_readme_pdf,
)
from money_machine.assets.design_tokens import DesignTokens, listing_token_payload, load_tokens
from money_machine.assets.listing_images import network_allowed
from money_machine.assets.pdf_objects import link_annotations, page_texts
from money_machine.domain.services.claim_validation import validate_claims
from money_machine.domain.services.listing_text import TextSlot, render
from tests.fixtures.merchandising import SECRET_LINK, consistent_request

DELIVERY_PDF_PATH = (
    Path(__file__).resolve().parents[3] / "src" / "money_machine" / "assets" / "delivery_pdfs.py"
)
_BUILD = 4


@dataclass(frozen=True, slots=True)
class _Scene:
    request: MerchandisingInput
    copy: ListingCopy
    tokens: DesignTokens


class _DropRefusal(ast.NodeTransformer):
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


def drop_refusal(callee: str, function: str) -> Callable[..., object]:
    drop = _DropRefusal(callee)
    tree = drop.visit(ast.parse(DELIVERY_PDF_PATH.read_text(encoding="utf-8")))
    if drop.dropped != 1 or not isinstance(tree, ast.Module):
        raise AssertionError(f"{callee} dropped {drop.dropped}")
    ast.fix_missing_locations(tree)
    name = f"pdf_mutant_{callee}"
    module = types.ModuleType(name)
    module.__file__ = str(DELIVERY_PDF_PATH)
    sys.modules[name] = module
    exec(compile(tree, str(DELIVERY_PDF_PATH), "exec"), module.__dict__)
    render = module.__dict__[function]
    if not callable(render):
        raise AssertionError(callee)
    return render


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
    return _Scene(request=request, copy=copy, tokens=load_tokens(listing_token_payload()))


def _readme(
    scene: _Scene,
    *,
    request: MerchandisingInput | None = None,
    copy: ListingCopy | None = None,
    injected_text: str = "",
) -> RenderedDeliveryPdf:
    return render_readme_pdf(
        scene.copy if copy is None else copy,
        scene.request if request is None else request,
        scene.tokens,
        build_version=_BUILD,
        injected_text=injected_text,
    )


def _gift(
    scene: _Scene,
    *,
    request: MerchandisingInput | None = None,
    copy: ListingCopy | None = None,
    injected_text: str = "",
) -> RenderedDeliveryPdf:
    return render_gift_pdf(
        scene.copy if copy is None else copy,
        scene.request if request is None else request,
        scene.tokens,
        build_version=_BUILD,
        injected_text=injected_text,
    )


def _accepted(render: Callable[..., object], scene: _Scene, **kwargs: object) -> object:
    result = render(
        kwargs.get("copy", scene.copy),
        kwargs.get("request", scene.request),
        scene.tokens,
        build_version=_BUILD,
        injected_text=kwargs.get("injected_text", ""),
    )
    pdf = getattr(result, "pdf", None)
    if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF"):
        raise AssertionError("mutant did not return a pdf")
    return result


def replace_fact(request: MerchandisingInput, key: str, value: str) -> MerchandisingInput:
    facts = tuple(
        fact.model_copy(update={"fact_value": value}) if fact.fact_key == key else fact
        for fact in request.facts
    )
    return request.model_copy(update={"facts": facts})


def _draft_hash(copy: ListingCopy) -> str:
    payload = copy.draft.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _expected_lineage(
    *,
    product_id: object,
    spec_version: int,
    merchandising: str,
    page_count: int,
    role: str,
) -> bytes:
    text = (
        f"product_id={product_id}\n"
        f"spec_version={spec_version}\n"
        "build_version=4\n"
        f"merchandising_version={merchandising}\n"
        "template_version=s08-w3-pdf-1\n"
        f"page_count={page_count}\n"
        "qa_status=passed\n"
        f"role={role}\n"
    )
    return text.encode("ascii")


def test_readme_is_two_pages_with_setup_and_access(scene: _Scene) -> None:
    blocks = readme_blocks(scene.copy.draft, scene.request.rules.quantity)
    page_one = blocks[:4]
    page_two = blocks[4:]
    assert page_one[0].text == f"Step 1. Open your template at {SECRET_LINK}."
    assert page_one[1].text == f"Step 2. Duplicate the template at {SECRET_LINK}."
    assert page_one[2].text.startswith("Step 3. Use the included resources: ")
    assert "Hyperlinked navigation" in page_one[2].text
    assert page_one[3].text == "Widgets: Today panel, Reminder list."
    names = tuple(variant.name for variant in scene.request.variants)
    assert tuple(block.text for block in page_two[: len(names)]) == tuple(
        f"Variant {name}. Access link: {SECRET_LINK}." for name in names
    )
    assert page_two[-3].text == f"Duplicate the template. Access link: {SECRET_LINK}."
    assert page_two[-2].text == "Support channel: Email inbox."
    assert page_two[-1].text == "Please leave a review for Fieldnote Shop."
    assert all("Free gift" not in block.text for block in blocks)
    html = compose_delivery_html(
        scene.tokens,
        (tuple(block.text for block in page_one), tuple(block.text for block in page_two)),
    )
    assert html.count('class="mm-pdf-page"') == 2
    assert f'href="{SECRET_LINK}"' in html
    rendered = _readme(scene)
    version = _draft_hash(scene.copy)
    expected = _expected_lineage(
        product_id=scene.request.spec.product_id,
        spec_version=scene.request.spec.version,
        merchandising=version,
        page_count=2,
        role="readme",
    )
    assert pdf_page_count(rendered.pdf) == 2
    assert rendered.lineage.page_count == 2
    assert rendered.lineage.role == "readme"
    assert rendered.lineage.template_version == PDF_TEMPLATE_VERSION == "s08-w3-pdf-1"
    assert rendered.lineage.qa_status == "passed"
    assert rendered.lineage.build_version == 4
    assert rendered.lineage.merchandising_version == version
    assert rendered.lineage.product_id == scene.request.spec.product_id
    assert rendered.lineage.spec_version == scene.request.spec.version
    assert rendered.lineage.output_sha256 == hashlib.sha256(rendered.pdf).hexdigest()
    assert expected in rendered.pdf
    assert b"D:20260101000000" in rendered.pdf


def test_gift_is_one_page_without_a_paid_link(scene: _Scene) -> None:
    blocks = gift_blocks(scene.copy.draft, scene.request.rules.quantity)
    assert tuple(block.text for block in blocks) == (
        "Free gift: Starter checklist.",
        "Free community: Planning circle.",
    )
    html = compose_delivery_html(scene.tokens, (tuple(block.text for block in blocks),))
    assert "checkout" not in html.casefold()
    assert html.count('class="mm-pdf-page"') == 1
    rendered = _gift(scene)
    version = _draft_hash(scene.copy)
    expected = _expected_lineage(
        product_id=scene.request.spec.product_id,
        spec_version=scene.request.spec.version,
        merchandising=version,
        page_count=1,
        role="free_gift",
    )
    assert pdf_page_count(rendered.pdf) == 1
    assert link_annotations(rendered.pdf) == (0, ())
    assert rendered.lineage.page_count == 1
    assert rendered.lineage.role == "free_gift"
    assert rendered.lineage.merchandising_version == version
    assert rendered.lineage.output_sha256 == hashlib.sha256(rendered.pdf).hexdigest()
    assert expected in rendered.pdf
    assert page_texts(rendered.pdf) == (
        "Free gift: Starter checklist.Free community: Planning circle.",
    )


def test_gift_community_is_optional(scene: _Scene) -> None:
    gift = FreeGiftConfig(offered=True, name="Starter checklist")
    request = replace_fact(scene.request, "free_gift", encode_free_gift(gift))
    request = request.model_copy(update={"free_gift": gift})
    copy = merchandise(request)
    blocks = gift_blocks(copy.draft, request.rules.quantity)
    assert tuple(block.text for block in blocks) == ("Free gift: Starter checklist.",)
    rendered = render_gift_pdf(copy, request, scene.tokens, build_version=_BUILD)
    assert pdf_page_count(rendered.pdf) == 1


def test_the_same_inputs_render_the_same_pdf(scene: _Scene) -> None:
    first = _readme(scene)
    second = _readme(scene)
    assert first.pdf == second.pdf
    assert first.lineage.output_sha256 == second.lineage.output_sha256
    gift = _gift(scene)
    assert gift.pdf == _gift(scene).pdf


def test_a_changed_spec_version_changes_the_pdf_hash(scene: _Scene) -> None:
    first = _readme(scene)
    bumped = scene.request.model_copy(
        update={
            "spec": scene.request.spec.model_copy(
                update={"version": scene.request.spec.version + 1}
            )
        }
    )
    second = _readme(scene, request=bumped)
    assert second.lineage.spec_version == scene.request.spec.version + 1
    assert second.lineage.merchandising_version == _draft_hash(scene.copy)
    assert second.lineage.merchandising_version == first.lineage.merchandising_version
    assert second.pdf != first.pdf
    assert second.lineage.output_sha256 != first.lineage.output_sha256
    assert (
        _expected_lineage(
            product_id=bumped.spec.product_id,
            spec_version=bumped.spec.version,
            merchandising=_draft_hash(scene.copy),
            page_count=2,
            role="readme",
        )
        in second.pdf
    )


def test_unclaimed_text_is_refused(scene: _Scene) -> None:
    with pytest.raises(DeliveryPdfRefusal, match="unsupported_claim"):
        _readme(scene, injected_text="Bestseller 500 sold")


def test_unclaimed_textdrop_refusal_accepts(scene: _Scene) -> None:
    accepted = _accepted(
        drop_refusal("refuse_unclaimed_pdf_text", "render_readme_pdf"),
        scene,
        injected_text="Bestseller 500 sold",
    )
    assert getattr(accepted, "pdf", b"").startswith(b"%PDF")


def _bad_tag_copy(scene: _Scene) -> ListingCopy:
    first = scene.copy.draft.tags[0]
    tags = (first.model_copy(update={"text": "500 sold"}), *scene.copy.draft.tags[1:])
    draft = scene.copy.draft.model_copy(update={"tags": tags})
    copy = scene.copy.model_copy(update={"draft": draft})
    assert validate_claims(draft, scene.request).passed is False
    return copy


def test_invalid_copy_is_refused(scene: _Scene) -> None:
    copy = _bad_tag_copy(scene)
    assert copy.draft.pdf_blocks == ()
    assert refuse_unvalidated_copy(copy.draft, scene.request) == "unsupported_claim"
    with pytest.raises(DeliveryPdfRefusal, match="unsupported_claim"):
        _readme(scene, copy=copy)


def test_invalid_copydrop_refusal_accepts(scene: _Scene) -> None:
    accepted = _accepted(
        drop_refusal("refuse_unvalidated_copy", "render_readme_pdf"),
        scene,
        copy=_bad_tag_copy(scene),
    )
    assert getattr(accepted, "pdf", b"").startswith(b"%PDF")


def _checkout_pair(scene: _Scene) -> tuple[MerchandisingInput, ListingCopy]:
    value = "offered|Starter checklist|https://pay.example/checkout"
    request = replace_fact(scene.request, "free_gift", value)
    claims = []
    support = None
    for claim in scene.copy.draft.claims:
        if claim.kind == "free_gift":
            claim = claim.model_copy(update={"stated_value": value})
        if claim.kind == "support":
            support = claim
        claims.append(claim)
    if support is None:
        raise AssertionError("support")
    text = render(
        "support",
        (TextSlot("support", support.stated_value), TextSlot("free_gift", value)),
        quantity=request.rules.quantity,
    )
    sections = tuple(
        section.model_copy(update={"text": text}) if section.role == "support" else section
        for section in scene.copy.draft.description_sections
    )
    draft = scene.copy.draft.model_copy(
        update={"claims": tuple(claims), "description_sections": sections}
    )
    copy = scene.copy.model_copy(update={"draft": draft})
    assert validate_claims(draft, request).passed is True
    return request, copy


def test_paid_checkout_is_refused(scene: _Scene) -> None:
    request, copy = _checkout_pair(scene)
    blocks = gift_blocks(copy.draft, request.rules.quantity)
    assert any("https://pay.example/checkout" in block.text for block in blocks)
    with pytest.raises(DeliveryPdfRefusal, match="paid_checkout"):
        render_gift_pdf(copy, request, scene.tokens, build_version=_BUILD)


def test_paid_checkoutdrop_refusal_accepts(scene: _Scene) -> None:
    request, copy = _checkout_pair(scene)
    accepted = _accepted(
        drop_refusal("refuse_paid_checkout", "render_gift_pdf"),
        scene,
        copy=copy,
        request=request,
    )
    assert getattr(accepted, "pdf", b"").startswith(b"%PDF")


def _long_readme(scene: _Scene) -> tuple[MerchandisingInput, ListingCopy]:
    output = "Panel" + (" x" * 260)
    dashboard = NotificationDashboardBehaviour(present=True, outputs=(output,))
    request = replace_fact(scene.request, "dashboard_outputs", encode_dashboard(dashboard))
    request = request.model_copy(update={"notification_dashboard": dashboard})
    copy = merchandise(request)
    assert validate_claims(copy.draft, request).passed is True
    widgets = readme_blocks(copy.draft, request.rules.quantity)[3].text
    assert len(widgets) > 500
    return request, copy


def _long_gift(scene: _Scene) -> tuple[MerchandisingInput, ListingCopy]:
    community = "Circle" + (" x" * 260)
    gift = FreeGiftConfig(offered=True, name="Starter checklist", community=community)
    request = replace_fact(scene.request, "free_gift", encode_free_gift(gift))
    request = request.model_copy(update={"free_gift": gift})
    copy = merchandise(request)
    assert len(gift_blocks(copy.draft, request.rules.quantity)[1].text) > 500
    return request, copy


def test_readme_page_count_is_refused(scene: _Scene) -> None:
    request, copy = _long_readme(scene)
    with pytest.raises(DeliveryPdfRefusal, match="page_count"):
        render_readme_pdf(copy, request, scene.tokens, build_version=_BUILD)


def test_readme_page_countdrop_refusal_accepts(scene: _Scene) -> None:
    request, copy = _long_readme(scene)
    accepted = _accepted(
        drop_refusal("refuse_page_count", "render_readme_pdf"),
        scene,
        copy=copy,
        request=request,
    )
    pdf = getattr(accepted, "pdf", b"")
    assert isinstance(pdf, bytes)
    assert pdf_page_count(pdf) != 2


def test_gift_page_count_is_refused(scene: _Scene) -> None:
    request, copy = _long_gift(scene)
    with pytest.raises(DeliveryPdfRefusal, match="page_count"):
        render_gift_pdf(copy, request, scene.tokens, build_version=_BUILD)


def test_gift_page_countdrop_refusal_accepts(scene: _Scene) -> None:
    request, copy = _long_gift(scene)
    accepted = _accepted(
        drop_refusal("refuse_page_count", "render_gift_pdf"),
        scene,
        copy=copy,
        request=request,
    )
    pdf = getattr(accepted, "pdf", b"")
    assert isinstance(pdf, bytes)
    assert pdf_page_count(pdf) != 1


def test_gift_not_offered_is_refused(scene: _Scene) -> None:
    gift = FreeGiftConfig(offered=False)
    request = replace_fact(scene.request, "free_gift", encode_free_gift(gift))
    request = request.model_copy(update={"free_gift": gift})
    copy = merchandise(request)
    with pytest.raises(DeliveryPdfRefusal, match="gift_not_offered"):
        render_gift_pdf(copy, request, scene.tokens, build_version=_BUILD)


def test_gift_not_offereddrop_refusal_accepts(scene: _Scene) -> None:
    gift = FreeGiftConfig(offered=False)
    request = replace_fact(scene.request, "free_gift", encode_free_gift(gift))
    request = request.model_copy(update={"free_gift": gift})
    copy = merchandise(request)
    accepted = _accepted(
        drop_refusal("refuse_gift_not_offered", "render_gift_pdf"),
        scene,
        copy=copy,
        request=request,
    )
    assert getattr(accepted, "pdf", b"").startswith(b"%PDF")


def test_pdf_network_stays_on_local_urls() -> None:
    assert network_allowed("https://pay.example/checkout") is False
    assert network_allowed("data:font/ttf;base64,AAAA") is True
