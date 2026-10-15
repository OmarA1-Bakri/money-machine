"""Link validation for exported delivery PDFs. No live HTTP."""

from __future__ import annotations

import hashlib
import inspect
import subprocess
import sys
from collections.abc import Callable

import pytest
from playwright.sync_api import sync_playwright

from money_machine.agents.implementations.merchandising import merchandise
from money_machine.assets.delivery_pdfs import render_gift_pdf, render_readme_pdf
from money_machine.assets.design_tokens import listing_token_payload, load_tokens
from money_machine.assets.link_validation import (
    AssetRepair,
    LinkObservation,
    LinkReport,
    LinkValidationRefusal,
    default_clock,
    default_link_checker,
    validate_pdf_links,
)
from money_machine.assets.pdf_objects import link_annotations
from tests.fixtures.merchandising import SECRET_LINK, consistent_request
from tests.unit.assets.gift_pdf_craft import (
    classic_pdf,
    deep_info_chain,
    embed_info_title,
    indirect_link,
    mail_link,
    metadata_packet,
    nested_kids_link,
    titled_page,
)

_STAMP = "2026-01-01T00:00:00Z"
_KNOWN = frozenset({"Sage Green", "Navy Blue", "Rose Gold"})
_LINKS = (
    ("Sage Green", "https://fixture.notion.site/Sage-Green"),
    ("Navy Blue", "https://fixture.notion.site/Navy-Blue"),
    ("Rose Gold", "https://fixture.notion.site/Rose-Gold"),
)
_ASSET = "readme"


def _clock() -> str:
    return _STAMP


def _checker(uri: str, variant: str) -> LinkObservation:
    return LinkObservation(
        variant=variant,
        public=True,
        duplicate_button=True,
        chain=(uri,),
    )


def _validate(
    pdf: bytes,
    *,
    accepted: tuple[tuple[str, str], ...] = _LINKS,
    known: frozenset[str] = _KNOWN,
    checker: Callable[[str, str], LinkObservation] | None = _checker,
    clock: Callable[[], str] | None = _clock,
    asset: str = _ASSET,
) -> LinkReport:
    kwargs: dict[str, object] = {
        "asset": asset,
        "accepted": accepted,
        "known_variants": known,
    }
    if checker is not None:
        kwargs["checker"] = checker
    if clock is not None:
        kwargs["clock"] = clock
    return validate_pdf_links(pdf, **kwargs)  # type: ignore[arg-type]


def _raise(pdf: bytes, **kwargs: object) -> LinkValidationRefusal:
    with pytest.raises(LinkValidationRefusal) as caught:
        _validate(pdf, **kwargs)  # type: ignore[arg-type]
    return caught.value


def _link_pdf(uris: tuple[str, ...]) -> bytes:
    objects: dict[int, bytes] = {
        1: b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        2: b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
    }
    refs = " ".join(f"{number} 0 R" for number in range(4, 4 + len(uris)))
    objects[3] = f"3 0 obj\n<< /Type /Page /Parent 2 0 R /Annots [{refs}] >>\nendobj\n".encode()
    for offset, uri in enumerate(uris):
        number = 4 + offset
        literal = uri.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        body = f"{number} 0 obj\n<< /Subtype /Link /A << /S /URI /URI ({literal}) >> >>\nendobj\n"
        objects[number] = body.encode("latin-1")
    return classic_pdf(objects)


def _one(uri: str, variant: str = "Sage Green") -> tuple[bytes, tuple[tuple[str, str], ...]]:
    accepted = ((variant, uri),)
    return _link_pdf((uri,)), accepted


def _ok_pdf() -> bytes:
    return _link_pdf(tuple(uri for _variant, uri in _LINKS))


def test_validated_uris_round_trip_exactly() -> None:
    pdf = _ok_pdf()
    report = _validate(pdf)
    assert report.repairs == ()
    records = report.records
    assert tuple(record.link for record in records) == tuple(uri for _variant, uri in _LINKS)
    digest = hashlib.sha256(pdf).hexdigest()
    for record, (_variant, uri) in zip(records, _LINKS, strict=True):
        assert record.link == uri
        assert record.variant == _variant
        assert record.resolves is True
        assert record.public is True
        assert record.duplicate_button is True
        assert record.checked_at == _STAMP
        assert record.pdf_sha256 == digest
        assert record.link_sha256 == hashlib.sha256(uri.encode()).hexdigest()


@pytest.mark.parametrize("index", (0, 1, 2))
def test_swapping_one_link_is_refused(index: int) -> None:
    uris = [uri for _variant, uri in _LINKS]
    uris[index] = uris[index] + "X"
    refusal = _raise(_link_pdf(tuple(uris)))
    assert refusal.code == "link_mismatch"
    assert [job.link for job in refusal.repairs] == [uris[index]]
    kept = {uri for _variant, uri in _LINKS}
    assert kept.isdisjoint({job.link for job in refusal.repairs})


def test_swapping_one_link_only_in_case_is_refused() -> None:
    uris = [uri for _variant, uri in _LINKS]
    uris[1] = uris[1].swapcase()
    refusal = _raise(_link_pdf(tuple(uris)))
    assert refusal.code == "link_mismatch"
    assert [job.link for job in refusal.repairs] == [uris[1]]


def test_a_pdf_with_no_links_is_refused() -> None:
    refusal = _raise(titled_page("Notes"), accepted=(), clock=None)
    assert refusal.code == "missing_links"
    assert refusal.repairs == (AssetRepair(_ASSET, "", "missing_links"),)


def test_a_link_without_a_uri_is_malformed() -> None:
    pdf = classic_pdf(
        {
            1: b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
            2: b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
            3: b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Annots [4 0 R] >>\nendobj\n",
            4: b"4 0 obj\n<< /Subtype /Link >>\nendobj\n",
        }
    )
    refusal = _raise(pdf, accepted=(), clock=None)
    assert refusal.code == "malformed"


def test_an_indirect_annotation_off_host_is_refused() -> None:
    accepted = (("Sage Green", "https://x.com"),)
    refusal = _raise(indirect_link(), accepted=accepted, clock=_clock)
    assert refusal.code == "host"
    assert refusal.repairs == (AssetRepair(_ASSET, "https://x.com", "host"),)


def test_nested_kids_are_walked() -> None:
    accepted = (("Sage Green", "https://x.com"),)
    refusal = _raise(nested_kids_link(), accepted=accepted)
    assert refusal.code == "host"
    assert link_annotations(nested_kids_link()) == (1, ("https://x.com",))


def test_mailto_is_malformed() -> None:
    refusal = _raise(mail_link(), accepted=(("Sage Green", "mailto:a"),))
    assert refusal.code == "malformed"
    assert refusal.repairs == (AssetRepair(_ASSET, "mailto:a", "malformed"),)


def test_http_is_refused() -> None:
    pdf, accepted = _one("http://fixture.notion.site/Sage-Green")
    refusal = _raise(pdf, accepted=accepted)
    assert refusal.code == "not_https"


def test_userinfo_is_malformed() -> None:
    pdf, accepted = _one("https://user:pass@fixture.notion.site/Sage-Green")
    refusal = _raise(pdf, accepted=accepted)
    assert refusal.code == "malformed"


def test_a_space_in_the_uri_is_malformed() -> None:
    pdf, accepted = _one("https://fixture.notion.site/Sage Green")
    refusal = _raise(pdf, accepted=accepted)
    assert refusal.code == "malformed"


def test_a_latin1_uri_is_refused_before_fold() -> None:
    pdf, accepted = _one("https://fixture.notion.site/Zo\u00eb")
    refusal = _raise(pdf, accepted=accepted)
    assert refusal.code == "paid_checkout"


def test_a_latin1_variant_is_refused_before_fold() -> None:
    pdf, accepted = _one("https://fixture.notion.site/Sage-Green", "Zo\u00eb")
    refusal = _raise(pdf, accepted=accepted, known=_KNOWN | {"Zo\u00eb"})
    assert refusal.code == "paid_checkout"
    assert refusal.repairs == (
        AssetRepair(_ASSET, "https://fixture.notion.site/Sage-Green", "paid_checkout"),
    )


def test_a_bare_percent_is_refused() -> None:
    pdf, accepted = _one("https://fixture.notion.site/50%")
    refusal = _raise(pdf, accepted=accepted)
    assert refusal.code == "paid_checkout"


def test_a_percent_triplet_in_the_path_is_refused() -> None:
    pdf, accepted = _one("https://fixture.notion.site/x%2Ecom")
    refusal = _raise(pdf, accepted=accepted)
    assert refusal.code == "paid_checkout"
    assert refusal.repairs[0].link == "https://fixture.notion.site/x%2Ecom"


def test_object_stream_info_percent_is_refused() -> None:
    uri = "https://fixture.notion.site/Sage-Green"
    pdf = embed_info_title(_link_pdf((uri,)), "x%2Ecom")
    refusal = _raise(pdf, accepted=(("Sage Green", uri),))
    assert refusal.code == "paid_checkout"
    assert refusal.repairs == (AssetRepair(_ASSET, "x%2Ecom", "paid_checkout"),)


def test_xmp_percent_surface_is_refused() -> None:
    refusal = _raise(metadata_packet(), accepted=(), clock=None)
    assert refusal.code == "paid_checkout"
    assert len(refusal.repairs) == 1
    assert "https://x.com" in refusal.repairs[0].link


def test_a_deep_info_chain_is_refused() -> None:
    refusal = _raise(deep_info_chain(), accepted=(), clock=None)
    assert refusal.code == "paid_checkout"
    assert refusal.repairs == (AssetRepair(_ASSET, "", "paid_checkout"),)


def test_an_unknown_variant_is_refused_without_opening() -> None:
    seen: list[str] = []

    def _opened(uri: str, variant: str) -> LinkObservation:
        seen.append(uri)
        return _checker(uri, variant)

    pdf, accepted = _one("https://fixture.notion.site/Lime", "Lime")
    refusal = _raise(pdf, accepted=accepted, checker=_opened)
    assert refusal.code == "unknown_variant"
    assert seen == []
    assert refusal.repairs == (
        AssetRepair(_ASSET, "https://fixture.notion.site/Lime", "unknown_variant"),
    )


def test_a_redirect_to_another_host_is_refused() -> None:
    uri = _LINKS[0][1]

    def _away(opened: str, variant: str) -> LinkObservation:
        return LinkObservation(
            variant=variant,
            public=True,
            duplicate_button=True,
            chain=(opened, "https://evil.example/a"),
        )

    pdf, accepted = _one(uri)
    refusal = _raise(pdf, accepted=accepted, checker=_away)
    assert refusal.code == "redirect_host"
    assert [job.link for job in refusal.repairs] == [uri]


def test_a_chain_that_skips_the_opened_uri_is_refused() -> None:
    uri = _LINKS[0][1]

    def _shifted(opened: str, variant: str) -> LinkObservation:
        return LinkObservation(variant, True, True, (opened + "/other", opened))

    pdf, accepted = _one(uri)
    refusal = _raise(pdf, accepted=accepted, checker=_shifted)
    assert refusal.code == "redirect_host"
    assert [job.link for job in refusal.repairs] == [uri]


def test_a_same_host_hop_is_allowed() -> None:
    uri = _LINKS[0][1]

    def _stay(opened: str, variant: str) -> LinkObservation:
        return LinkObservation(
            variant=variant,
            public=True,
            duplicate_button=True,
            chain=(opened, opened + "/page"),
        )

    pdf, accepted = _one(uri)
    report = _validate(pdf, accepted=accepted, checker=_stay)
    records = report.records
    assert records[0].resolves is True
    assert records[0].link == uri


def test_the_wrong_variant_is_refused() -> None:
    uri = _LINKS[0][1]

    def _other(opened: str, variant: str) -> LinkObservation:
        del variant
        return _checker(opened, "Navy Blue")

    pdf, accepted = _one(uri)
    refusal = _raise(pdf, accepted=accepted, checker=_other)
    assert refusal.code == "wrong_variant"
    assert refusal.records[0].resolves is False
    assert refusal.records[0].link == uri


def test_an_auth_wall_is_refused() -> None:
    uri = _LINKS[0][1]

    def _closed(opened: str, variant: str) -> LinkObservation:
        seen = _checker(opened, variant)
        return LinkObservation(seen.variant, False, True, seen.chain)

    pdf, accepted = _one(uri)
    refusal = _raise(pdf, accepted=accepted, checker=_closed)
    assert refusal.code == "auth_wall"
    assert refusal.records[0].public is False
    assert refusal.repairs == (AssetRepair(_ASSET, uri, "auth_wall"),)


def test_a_missing_duplicate_button_is_refused() -> None:
    uri = _LINKS[0][1]

    def _plain(opened: str, variant: str) -> LinkObservation:
        seen = _checker(opened, variant)
        return LinkObservation(seen.variant, True, False, seen.chain)

    pdf, accepted = _one(uri)
    refusal = _raise(pdf, accepted=accepted, checker=_plain)
    assert refusal.code == "duplicate_button"
    assert refusal.records[0].duplicate_button is False
    assert refusal.records[0].public is True


def test_one_failed_link_does_not_repair_the_others() -> None:
    def _middle(uri: str, variant: str) -> LinkObservation:
        seen = _checker(uri, variant)
        if variant == "Navy Blue":
            return LinkObservation(seen.variant, False, True, seen.chain)
        return seen

    refusal = _raise(_ok_pdf(), checker=_middle)
    assert [job.link for job in refusal.repairs] == [_LINKS[1][1]]
    assert refusal.records[0].public is True
    assert refusal.records[2].public is True
    assert refusal.records[1].public is False


def test_a_missing_accepted_link_is_named() -> None:
    pdf = _link_pdf((_LINKS[0][1], _LINKS[1][1]))
    refusal = _raise(pdf)
    assert [job.link for job in refusal.repairs] == [_LINKS[2][1]]
    assert refusal.code == "link_mismatch"


def test_the_checker_defaults_to_refusal() -> None:
    checker = inspect.signature(validate_pdf_links).parameters["checker"].default
    assert checker is default_link_checker
    pdf, accepted = _one(_LINKS[0][1])
    with pytest.raises(LinkValidationRefusal, match="live_link_check"):
        validate_pdf_links(
            pdf,
            asset=_ASSET,
            accepted=accepted,
            known_variants=_KNOWN,
            clock=_clock,
        )


def test_the_clock_defaults_to_refusal() -> None:
    clock = inspect.signature(validate_pdf_links).parameters["clock"].default
    assert clock is default_clock
    pdf, accepted = _one(_LINKS[0][1])
    with pytest.raises(LinkValidationRefusal, match="live_clock"):
        validate_pdf_links(
            pdf,
            asset=_ASSET,
            accepted=accepted,
            known_variants=_KNOWN,
            checker=_checker,
        )


def _launch_chromium() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        browser.close()


@pytest.fixture(scope="module")
def chromium_installed() -> None:
    try:
        _launch_chromium()
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        _launch_chromium()


def test_the_readme_uris_round_trip_exactly(chromium_installed: None) -> None:
    """Chromium stores an origin href with a trailing slash.

    The painted string is ``SECRET_LINK``. The annotation is that string plus
    ``/``. Validation against the painted string fails. Validation against the
    annotation string passes. Replacing one annotation, same length, fails.
    """
    del chromium_installed
    request = consistent_request()
    copy = merchandise(request)
    tokens = load_tokens(listing_token_payload())
    rendered = render_readme_pdf(copy, request, tokens, build_version=4)
    count, uris = link_annotations(rendered.pdf)
    names = tuple(variant.name for variant in request.variants)
    exported = f"{SECRET_LINK}/"
    assert count == len(names) + 1
    assert uris == (exported,) * count
    painted = (*((name, SECRET_LINK) for name in names), ("", SECRET_LINK))
    mismatch = _raise(rendered.pdf, accepted=painted, asset="readme")
    assert mismatch.code == "link_mismatch"
    assert [job.link for job in mismatch.repairs] == [exported] * count
    accepted = (*((name, exported) for name in names), ("", exported))
    report = _validate(rendered.pdf, accepted=accepted, asset="readme")
    records = report.records
    assert tuple(record.link for record in records) == uris
    assert all(record.link == exported for record in records)
    assert records[-1].variant == ""
    assert records[-1].duplicate_button is True
    swapped_uri = exported.replace("fixture", "fixturX", 1)
    needle = f"({exported})".encode()
    assert rendered.pdf.count(needle) == count
    swapped = rendered.pdf.replace(needle, f"({swapped_uri})".encode(), 1)
    refusal = _raise(swapped, accepted=accepted, asset="readme")
    assert refusal.code == "link_mismatch"
    assert [job.link for job in refusal.repairs] == [swapped_uri]


def test_the_gift_pdf_has_no_links(chromium_installed: None) -> None:
    del chromium_installed
    request = consistent_request()
    copy = merchandise(request)
    tokens = load_tokens(listing_token_payload())
    rendered = render_gift_pdf(copy, request, tokens, build_version=4)
    assert link_annotations(rendered.pdf) == (0, ())
    refusal = _raise(rendered.pdf, accepted=(), asset="free_gift", clock=None)
    assert refusal.code == "missing_links"
    assert refusal.repairs == (AssetRepair("free_gift", "", "missing_links"),)
