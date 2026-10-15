"""A same-host hop that leaves https is a redirect. No live HTTP."""

from __future__ import annotations

import pytest

from money_machine.assets.link_validation import (
    LinkObservation,
    LinkValidationRefusal,
    validate_pdf_links,
)
from tests.unit.assets.gift_pdf_craft import classic_pdf

_URI = "https://fixture.notion.site/Sage-Green"
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


def _check(chain: tuple[str, ...]) -> LinkObservation:
    return LinkObservation("Sage Green", True, True, chain)


def test_a_same_host_http_hop_is_refused() -> None:
    downgrade = "http://fixture.notion.site/Sage-Green"
    with pytest.raises(LinkValidationRefusal) as caught:
        validate_pdf_links(
            _pdf(_URI),
            asset="readme",
            accepted=(("Sage Green", _URI),),
            known_variants=_KNOWN,
            checker=lambda _uri, _variant: _check((_URI, downgrade)),
            clock=lambda: _STAMP,
        )
    assert caught.value.code == "redirect_host"
    assert [job.link for job in caught.value.repairs] == [_URI]


def test_a_same_host_ws_or_ftp_hop_is_refused() -> None:
    for scheme in ("ws", "ftp"):
        hop = f"{scheme}://fixture.notion.site/Sage-Green"
        with pytest.raises(LinkValidationRefusal) as caught:
            validate_pdf_links(
                _pdf(_URI),
                asset="readme",
                accepted=(("Sage Green", _URI),),
                known_variants=_KNOWN,
                checker=lambda _uri, _variant, hop=hop: _check((_URI, hop)),
                clock=lambda: _STAMP,
            )
        assert caught.value.code == "redirect_host"
        assert [job.link for job in caught.value.repairs] == [_URI]


def test_a_mid_chain_http_hop_is_refused() -> None:
    mid = "http://fixture.notion.site/mid"
    final = "https://fixture.notion.site/Sage-Green"
    with pytest.raises(LinkValidationRefusal) as caught:
        validate_pdf_links(
            _pdf(_URI),
            asset="readme",
            accepted=(("Sage Green", _URI),),
            known_variants=_KNOWN,
            checker=lambda _uri, _variant: _check((_URI, mid, final)),
            clock=lambda: _STAMP,
        )
    assert caught.value.code == "redirect_host"
    assert [job.link for job in caught.value.repairs] == [_URI]


def test_a_same_host_https_hop_is_allowed() -> None:
    report = validate_pdf_links(
        _pdf(_URI),
        asset="readme",
        accepted=(("Sage Green", _URI),),
        known_variants=_KNOWN,
        checker=lambda _uri, _variant: _check((_URI, _URI + "/page")),
        clock=lambda: _STAMP,
    )
    assert report.records[0].resolves is True
    assert report.records[0].link == _URI
