"""README and free-gift PDFs. A11 stays DESIGNED and unregistered.

Buyer-facing sentences are listing templates. The gift refuses URL-like copy on
a folded check-only string, then refuses link annotations and document info.
Painted text and lineage stay on the original bytes. Dates are pinned.
Lineage is appended after ``%%EOF``.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from html import escape
from typing import Literal
from uuid import UUID

from playwright.sync_api import Route, sync_playwright

from money_machine.agents.contracts.merchandising import (
    CitedText,
    ListingClaim,
    ListingCopy,
    ListingDraft,
    MerchandisingInput,
)
from money_machine.assets.design_tokens import DesignTokens, emit_css, load_tokens
from money_machine.assets.gift_links import (
    refuse_gift_document_info,
    refuse_gift_link_annotations,
    refuse_paid_checkout,
)
from money_machine.assets.listing_images import (
    extract_visible_text,
    merchandising_version,
    network_allowed,
)
from money_machine.assets.pdf_objects import embed_info_title
from money_machine.domain.services.claim_validation import validate_claims
from money_machine.domain.services.listing_text import TextSlot, render

PDF_TEMPLATE_VERSION = "s08-w3-pdf-1"
README_PAGE_COUNT = 2
GIFT_PAGE_COUNT = 1
_LINE_FIT = 500
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
_PINNED_PDF_DATE = b"D:20260101000000"
_PINNED_ISO_DATE = b"2026-01-01T00:00:00"
_PDF_DATE = re.compile(rb"D:\d{14}")
_ISO_DATE = re.compile(rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
_PDF_ID = re.compile(rb"/ID\s*\[\s*<[0-9A-Fa-f]+>\s*<[0-9A-Fa-f]+>\s*\]")
_PDF_PAGE = re.compile(rb"/Type\s*/Page(?!s)\b")
_ACCESS_MARK = "Access link: "


class DeliveryPdfRefusal(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DeliveryPdfLineage:
    product_id: UUID
    spec_version: int
    build_version: int
    merchandising_version: str
    template_version: str
    output_sha256: str
    page_count: int
    qa_status: Literal["passed"]
    role: Literal["readme", "free_gift"]


@dataclass(frozen=True, slots=True)
class RenderedDeliveryPdf:
    pdf: bytes
    lineage: DeliveryPdfLineage


def render_readme_pdf(
    copy: ListingCopy,
    request: MerchandisingInput,
    tokens: DesignTokens,
    *,
    build_version: int,
    injected_text: str = "",
) -> RenderedDeliveryPdf:
    """Paint the two-page README. Page 1 is setup; page 2 is access and support."""
    blocks = readme_blocks(copy.draft, request.rules.quantity)
    pages = (
        tuple(block.text for block in blocks[:4]),
        tuple(block.text for block in blocks[4:]),
    )
    return _render(
        copy,
        request,
        tokens,
        pages,
        blocks,
        build_version=build_version,
        expected_pages=README_PAGE_COUNT,
        role="readme",
        injected_text=injected_text,
        check_paid=False,
    )


def render_gift_pdf(
    copy: ListingCopy,
    request: MerchandisingInput,
    tokens: DesignTokens,
    *,
    build_version: int,
    injected_text: str = "",
    link_uri: str = "",
    info_title: str = "",
) -> RenderedDeliveryPdf:
    """Paint the one-page free gift. URL- or domain-like text is refused."""
    gift = _only(copy.draft, "free_gift")
    if refuse_gift_not_offered(gift.stated_value) is not None:
        raise DeliveryPdfRefusal("gift_not_offered")
    blocks = gift_blocks(copy.draft, request.rules.quantity)
    pages = (tuple(block.text for block in blocks),)
    return _render(
        copy,
        request,
        tokens,
        pages,
        blocks,
        build_version=build_version,
        expected_pages=GIFT_PAGE_COUNT,
        role="free_gift",
        injected_text=injected_text,
        check_paid=True,
        link_uri=link_uri,
        info_title=info_title,
    )


def readme_blocks(draft: ListingDraft, quantity: int) -> tuple[CitedText, ...]:
    access = _only(draft, "access")
    features = _many(draft, "feature")
    dashboard = _only(draft, "dashboard")
    variants = _many(draft, "variant")
    support = _only(draft, "support")
    shop = _only(draft, "shop")
    page_one = (
        _cite("pdf_setup_open", (access,), quantity),
        _cite("pdf_setup_duplicate", (access,), quantity),
        _cite("pdf_setup_resources", features, quantity),
        _cite("pdf_widgets", (dashboard,), quantity),
    )
    links = tuple(_cite("pdf_variant_link", (variant, access), quantity) for variant in variants)
    page_two = (
        *links,
        _cite("pdf_duplication", (access,), quantity),
        _cite("pdf_support", (support,), quantity),
        _cite("pdf_review_request", (shop,), quantity),
    )
    return page_one + page_two


def gift_blocks(draft: ListingDraft, quantity: int) -> tuple[CitedText, ...]:
    gift = _only(draft, "free_gift")
    blocks = [_cite("pdf_gift", (gift,), quantity)]
    if _community_offered(gift.stated_value):
        blocks.append(_cite("pdf_community", (gift,), quantity))
    return tuple(blocks)


def compose_delivery_html(
    tokens: DesignTokens,
    pages: tuple[tuple[str, ...], ...],
) -> str:
    load_tokens(tokens.model_dump())
    css = emit_css(tokens) + _pdf_css(tokens)
    body = "".join(_article(paragraphs) for paragraphs in _with_overflow_page(pages))
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<style>{css}</style></head><body>{body}</body></html>"
    )


def pdf_page_count(pdf: bytes) -> int:
    return len(_PDF_PAGE.findall(pdf))


def refuse_gift_not_offered(encoded: str) -> str | None:
    if encoded == "not_offered":
        return "gift_not_offered"
    return None


def _refuse_paid(text: str) -> None:
    if refuse_paid_checkout(text) is not None:
        raise DeliveryPdfRefusal("paid_checkout")
    return None


def _refuse_annotations(pdf: bytes) -> None:
    if refuse_gift_link_annotations(pdf) is not None:
        raise DeliveryPdfRefusal("paid_checkout")
    return None


def _refuse_document_info(pdf: bytes) -> None:
    if refuse_gift_document_info(pdf) is not None:
        raise DeliveryPdfRefusal("paid_checkout")
    return None


def _with_overflow_page(
    pages: tuple[tuple[str, ...], ...],
) -> tuple[tuple[str, ...], ...]:
    if any(len(text) > _LINE_FIT for paragraphs in pages for text in paragraphs):
        return (*pages, ())
    return pages


def refuse_page_count(pdf: bytes, expected: int) -> str | None:
    if pdf_page_count(pdf) != expected:
        return "page_count"
    return None


def refuse_unvalidated_copy(copy: ListingDraft, request: MerchandisingInput) -> str | None:
    if validate_claims(copy, request).passed:
        return None
    return "unsupported_claim"


def refuse_unclaimed_pdf_text(
    html: str,
    blocks: tuple[CitedText, ...],
    draft: ListingDraft,
    request: MerchandisingInput,
) -> str | None:
    texts = extract_visible_text(html)
    if texts == tuple(block.text for block in blocks):
        return None
    probed = draft.model_copy(update={"pdf_blocks": _blocks_for_visible(blocks, texts)})
    if validate_claims(probed, request).passed:
        return None
    return "unsupported_claim"


def _render(
    copy: ListingCopy,
    request: MerchandisingInput,
    tokens: DesignTokens,
    pages: tuple[tuple[str, ...], ...],
    blocks: tuple[CitedText, ...],
    *,
    build_version: int,
    expected_pages: int,
    role: Literal["readme", "free_gift"],
    injected_text: str,
    check_paid: bool,
    link_uri: str = "",
    info_title: str = "",
) -> RenderedDeliveryPdf:
    load_tokens(tokens.model_dump())
    if check_paid:
        _refuse_paid(_gift_copy(blocks, injected_text))
    probed = copy.draft.model_copy(update={"pdf_blocks": blocks})
    if refuse_unvalidated_copy(probed, request) is not None:
        raise DeliveryPdfRefusal("unsupported_claim")
    html = _inject_anchor(_inject(compose_delivery_html(tokens, pages), injected_text), link_uri)
    if refuse_unclaimed_pdf_text(html, blocks, probed, request) is not None:
        raise DeliveryPdfRefusal("unsupported_claim")
    pdf = _pin_metadata(_paint(html, tokens))
    if info_title:
        pdf = embed_info_title(pdf, info_title)
    if check_paid:
        _refuse_annotations(pdf)
        _refuse_document_info(pdf)
    if refuse_page_count(pdf, expected_pages) is not None:
        raise DeliveryPdfRefusal("page_count")
    return _bind(
        pdf,
        copy,
        request,
        build_version=build_version,
        page_count=expected_pages,
        role=role,
    )


def _cite(template_id: str, claims: tuple[ListingClaim, ...], quantity: int) -> CitedText:
    slots = tuple(TextSlot(claim.kind, claim.stated_value) for claim in claims)
    text = render(template_id, slots, quantity=quantity)
    return CitedText(
        template_id=template_id,
        text=text,
        claim_ids=tuple(claim.claim_id for claim in claims),
    )


def _only(draft: ListingDraft, kind: str) -> ListingClaim:
    found = _many(draft, kind)
    if len(found) != 1:
        raise DeliveryPdfRefusal("unsupported_claim")
    return found[0]


def _many(draft: ListingDraft, kind: str) -> tuple[ListingClaim, ...]:
    found = tuple(claim for claim in draft.claims if claim.kind == kind)
    if not found:
        raise DeliveryPdfRefusal("unsupported_claim")
    return found


def _community_offered(encoded: str) -> bool:
    return encoded.startswith("offered|") and encoded.count("|") == 2


def _blocks_for_visible(
    blocks: tuple[CitedText, ...],
    texts: tuple[str, ...],
) -> tuple[CitedText, ...]:
    if not blocks:
        raise DeliveryPdfRefusal("unsupported_claim")
    anchor = blocks[0]
    updated: list[CitedText] = []
    for index, text in enumerate(texts):
        if index < len(blocks):
            updated.append(blocks[index].model_copy(update={"text": text}))
            continue
        updated.append(
            CitedText(template_id=anchor.template_id, text=text, claim_ids=anchor.claim_ids)
        )
    return tuple(updated)


def _gift_copy(blocks: tuple[CitedText, ...], injected_text: str) -> str:
    parts = [block.text for block in blocks]
    if injected_text:
        parts.append(injected_text)
    return "\n".join(parts)


def _inject(html: str, text: str) -> str:
    if text == "":
        return html
    extra = f'<p class="mm-claim">{escape(text)}</p>'
    return html.replace("</article>", extra + "</article>", 1)


def _inject_anchor(html: str, uri: str) -> str:
    if uri == "":
        return html
    anchor = f'<a href="{escape(uri, quote=True)}">&nbsp;</a>'
    return html.replace("</article>", anchor + "</article>", 1)


def _article(paragraphs: tuple[str, ...]) -> str:
    body = "".join(_paragraph(text) for text in paragraphs)
    return f'<article class="mm-pdf-page">{body}</article>'


def _paragraph(text: str) -> str:
    marker = " mm-break" if len(text) > _LINE_FIT else ""
    return f'<p class="mm-claim{marker}">{_linked(text)}</p>'


def _linked(text: str) -> str:
    if _ACCESS_MARK not in text:
        return escape(text)
    before, after = text.split(_ACCESS_MARK, maxsplit=1)
    url = after[:-1] if after.endswith(".") else after
    tail = "." if after.endswith(".") else ""
    href = escape(url, quote=True)
    return f'{escape(before)}{escape(_ACCESS_MARK)}<a href="{href}">{escape(url)}</a>{escape(tail)}'


def _pdf_css(tokens: DesignTokens) -> str:
    pdf = tokens.pdf_pages
    if pdf is None:
        raise DeliveryPdfRefusal("missing_token")
    return (
        f"@page {{ size: {pdf.width_px}px {pdf.height_px}px; margin: 0; }}"
        "html,body{margin:0;padding:0;background:var(--mm-surface);color:var(--mm-text);"
        "font-family:var(--mm-font);font-size:var(--mm-body-size);line-height:var(--mm-line-height);}"
        ".mm-pdf-page{break-after:page;page-break-after:always;overflow:visible;}"
        ".mm-pdf-page:last-child{break-after:auto;page-break-after:auto;}"
        ".mm-claim{margin:0 0 16px;}"
        ".mm-break{break-before:page;page-break-before:always;}"
        "a{color:var(--mm-accent);}"
    )


def _paint(html: str, tokens: DesignTokens) -> bytes:
    pdf = tokens.pdf_pages
    if pdf is None:
        raise DeliveryPdfRefusal("missing_token")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=list(_LAUNCH_ARGS))
        try:
            context = browser.new_context(
                viewport={"width": pdf.width_px, "height": pdf.height_px},
                device_scale_factor=1,
                reduced_motion="reduce",
                color_scheme="light",
                java_script_enabled=True,
                bypass_csp=True,
                locale="en-US",
                timezone_id="UTC",
            )
            try:
                context.route("**/*", _guard)
                page = context.new_page()
                try:
                    page.set_content(html, wait_until="load")
                    page.evaluate("async () => { await document.fonts.ready; }")
                    return page.pdf(
                        width=f"{pdf.width_px}px",
                        height=f"{pdf.height_px}px",
                        print_background=True,
                        prefer_css_page_size=True,
                        display_header_footer=False,
                        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                    )
                finally:
                    page.close()
            finally:
                context.close()
        finally:
            browser.close()


def _guard(route: Route) -> None:
    if network_allowed(route.request.url):
        route.continue_()
        return
    route.abort()


def _pin_metadata(pdf: bytes) -> bytes:
    pinned = _PDF_DATE.sub(_PINNED_PDF_DATE, pdf)
    pinned = _ISO_DATE.sub(_PINNED_ISO_DATE, pinned)

    def _zero_id(match: re.Match[bytes]) -> bytes:
        return re.sub(rb"[0-9A-Fa-f]", b"0", match.group(0))

    return _PDF_ID.sub(_zero_id, pinned)


def _bind(
    pdf: bytes,
    copy: ListingCopy,
    request: MerchandisingInput,
    *,
    build_version: int,
    page_count: int,
    role: Literal["readme", "free_gift"],
) -> RenderedDeliveryPdf:
    version = merchandising_version(copy.draft)
    text = (
        f"product_id={request.spec.product_id}\n"
        f"spec_version={request.spec.version}\n"
        f"build_version={build_version}\n"
        f"merchandising_version={version}\n"
        f"template_version={PDF_TEMPLATE_VERSION}\n"
        f"page_count={page_count}\n"
        "qa_status=passed\n"
        f"role={role}\n"
    )
    bound = pdf + b"\n% mm-lineage\n" + text.encode("ascii")
    return RenderedDeliveryPdf(
        pdf=bound,
        lineage=DeliveryPdfLineage(
            product_id=request.spec.product_id,
            spec_version=request.spec.version,
            build_version=build_version,
            merchandising_version=version,
            template_version=PDF_TEMPLATE_VERSION,
            output_sha256=hashlib.sha256(bound).hexdigest(),
            page_count=page_count,
            qa_status="passed",
            role=role,
        ),
    )
