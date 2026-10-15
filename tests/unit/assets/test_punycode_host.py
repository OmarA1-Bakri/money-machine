"""A punycode Notion label is not a secret host. No live HTTP."""

from __future__ import annotations

import pytest

from money_machine.assets.link_validation import (
    LinkObservation,
    LinkValidationRefusal,
    validate_pdf_links,
)
from money_machine.integrations.notion.errors import SchemaBuilderError
from money_machine.integrations.notion.publishing import build_published_page
from tests.unit.assets.gift_pdf_craft import classic_pdf

_PLAIN = "https://fixture.notion.site/Sage-Green"
_PUNY = "https://xn--fixture.notion.site/Sage-Green"
_STAMP = "2026-01-01T00:00:00Z"
_KNOWN = frozenset({"Sage Green"})


def _obj(number: int, body: str) -> bytes:
    return f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")


def _pdf(uri: str) -> bytes:
    action = f"<< /Type /Action /S /URI /URI ({uri}) >>"
    annot = f"<< /Type /Annot /Subtype /Link /Rect [0 0 1 1] /Border [0 0 0] /F 4 /A {action} >>"
    page = (
        "<< /Type /Page /Resources << /ExtGState << >> /Font << >> "
        "/ProcSet [/PDF /Text /ImageB /ImageC /ImageI] >> /MediaBox [0 0 1 1] "
        "/Annots [4 0 R] /Contents << >> /Tabs /S /Parent 2 0 R >>"
    )
    return classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _obj(3, page),
            4: _obj(4, annot),
        }
    )


def _checker_must_not_run(uri: str, variant: str) -> LinkObservation:
    raise AssertionError(uri, variant)


def test_a_punycode_notion_host_is_refused() -> None:
    with pytest.raises(LinkValidationRefusal) as caught:
        validate_pdf_links(
            _pdf(_PUNY),
            asset="readme",
            accepted=(("Sage Green", _PUNY),),
            known_variants=_KNOWN,
            checker=_checker_must_not_run,
            clock=lambda: _STAMP,
        )
    assert caught.value.code == "host"
    assert [job.link for job in caught.value.repairs] == [_PUNY]


def _publish_secret(link: str) -> None:
    build_published_page(
        "a" * 32,
        "workspace",
        True,
        True,
        False,
        link,
        True,
        ("b" * 32,),
        ("c" * 32,),
    )


def test_a_unicode_homoglyph_host_is_refused() -> None:
    with pytest.raises(SchemaBuilderError, match="host is not allowed"):
        _publish_secret("https://f\u00edxture.notion.site/Home")


def test_a_fullwidth_host_is_refused() -> None:
    with pytest.raises(SchemaBuilderError, match="host is not allowed"):
        _publish_secret("https://\uff46ixture.notion.site/Home")


def test_a_unicode_host_in_a_pdf_is_refused() -> None:
    uri = "https://f\u00edxture.notion.site/Sage-Green"
    with pytest.raises(LinkValidationRefusal) as caught:
        validate_pdf_links(
            _pdf(uri),
            asset="readme",
            accepted=(("Sage Green", uri),),
            known_variants=_KNOWN,
            checker=_checker_must_not_run,
            clock=lambda: _STAMP,
        )
    assert caught.value.code == "host"


def test_a_plain_notion_host_is_allowed() -> None:
    report = validate_pdf_links(
        _pdf(_PLAIN),
        asset="readme",
        accepted=(("Sage Green", _PLAIN),),
        known_variants=_KNOWN,
        checker=lambda uri, variant: LinkObservation(variant, True, True, (uri,)),
        clock=lambda: _STAMP,
    )
    assert report.records[0].resolves is True
    assert report.records[0].link == _PLAIN
