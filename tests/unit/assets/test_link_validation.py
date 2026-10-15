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
from money_machine.assets.pdf_reader import PdfDocument, PdfName, PdfObject
from tests.fixtures.merchandising import SECRET_LINK, consistent_request
from tests.unit.assets.gift_pdf_craft import (
    classic_pdf,
    deep_info_chain,
    embed_info_title,
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


def _literal(uri: str) -> str:
    escaped = uri.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"({escaped})"


def _action_dict(uri: str, *, typed: bool = True, s: str = "URI", extra: str = "") -> str:
    type_part = "/Type /Action " if typed else ""
    suffix = f" {extra}" if extra else ""
    return f"<< {type_part}/S /{s} /URI {_literal(uri)}{suffix} >>"


def _annot_dict(action: str, *, extra: str = "") -> str:
    suffix = f" {extra}" if extra else ""
    return (
        "<< /Type /Annot /Subtype /Link /Rect [0 0 1 1] /Border [0 0 0] /F 4"
        f"{suffix} /A {action} >>"
    )


def _obj(number: int, body: str) -> bytes:
    return f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")


def _page(
    parent: int,
    annots: str | None = None,
    *,
    resources: str = "<< >>",
    extra: str = "",
    annots_key: str = "Annots",
) -> str:
    """A page whose keys match the README generator, plus ``extra`` when set."""
    annots_part = f" /{annots_key} {annots}" if annots is not None else ""
    suffix = f" {extra}" if extra else ""
    return (
        f"<< /Type /Page /Resources {resources} /MediaBox [0 0 1 1]"
        f"{annots_part} /Contents << >> /Tabs /S /Parent {parent} 0 R{suffix} >>"
    )


def _link_pdf(uris: tuple[str, ...]) -> bytes:
    objects: dict[int, bytes] = {
        1: b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        2: b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
    }
    refs = " ".join(f"{number} 0 R" for number in range(4, 4 + len(uris)))
    objects[3] = _obj(3, _page(2, f"[{refs}]"))
    for offset, uri in enumerate(uris):
        number = 4 + offset
        objects[number] = _obj(number, _annot_dict(_action_dict(uri)))
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
    assert [job.index for job in refusal.repairs] == [index]
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


_GOOD = "https://fixture.notion.site/Sage-Green"


def _annot(
    body: str,
    *,
    catalog: str = "",
    objects: dict[int, bytes] | None = None,
    page_extra: str = "",
    resources: str = "<< >>",
    root: str | None = None,
) -> bytes:
    extra = f" {catalog}" if catalog else ""
    catalog_body = root if root is not None else f"<< /Type /Catalog /Pages 2 0 R{extra} >>"
    built = {
        1: f"1 0 obj\n{catalog_body}\nendobj\n".encode(),
        2: b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        3: _obj(3, _page(2, "[4 0 R]", resources=resources, extra=page_extra)),
        4: _obj(4, body),
    }
    if objects:
        built.update(objects)
    return classic_pdf(built)


def _good_annot(
    *,
    s: str = "URI",
    typed: bool = True,
    action_extra: str = "",
    extra: str = "",
) -> str:
    action = _action_dict(_GOOD, typed=typed, s=s, extra=action_extra)
    return _annot_dict(action, extra=extra)


def _accepted_good() -> tuple[tuple[str, str], ...]:
    return (("Sage Green", _GOOD),)


def test_a_launch_action_is_malformed() -> None:
    refusal = _raise(_annot(_good_annot(s="Launch")), accepted=_accepted_good())
    assert refusal.code == "malformed"
    assert refusal.repairs == (AssetRepair(_ASSET, "", "malformed"),)


def test_a_javascript_action_is_malformed() -> None:
    refusal = _raise(_annot(_good_annot(s="JavaScript")), accepted=_accepted_good())
    assert refusal.code == "malformed"


@pytest.mark.parametrize("action", ("SubmitForm", "ImportData", "GoToR"))
def test_a_non_uri_action_is_malformed(action: str) -> None:
    refusal = _raise(_annot(_good_annot(s=action)), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_an_annotation_uri_cannot_hide_the_action() -> None:
    body = _annot_dict(
        _action_dict("https://evil.example/x"),
        extra="/URI " + _literal(_GOOD),
    )
    refusal = _raise(_annot(body), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_an_action_next_is_malformed() -> None:
    body = _good_annot(action_extra=f"/Next << /S /URI /URI {_literal(_GOOD)} >>")
    refusal = _raise(_annot(body), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_link_additional_action_is_malformed() -> None:
    body = _good_annot(extra="/AA << /E << /S /JavaScript /JS (1) >> >>")
    refusal = _raise(_annot(body), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_link_uri_additional_action_is_malformed() -> None:
    """``/S /URI`` must not save an extra ``/AA`` key. JavaScript would."""
    body = _good_annot(extra=f"/AA << /E << /S /URI /URI {_literal(_GOOD)} >> >>")
    refusal = _raise(_annot(body), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_link_additional_action_without_an_s_is_malformed() -> None:
    body = _good_annot(extra="/AA << /E << /Foo true >> >>")
    refusal = _raise(_annot(body), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_an_extra_annotation_key_is_malformed() -> None:
    refusal = _raise(_annot(_good_annot(extra="/PA [0 0 1 1]")), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_link_missing_border_is_malformed() -> None:
    body = f"<< /Type /Annot /Subtype /Link /Rect [0 0 1 1] /F 4 /A {_action_dict(_GOOD)} >>"
    refusal = _raise(_annot(body), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_link_type_must_be_annot() -> None:
    body = (
        "<< /Type /XObject /Subtype /Link /Rect [0 0 1 1] /Border [0 0 0] /F 4 /A "
        f"{_action_dict(_GOOD)} >>"
    )
    refusal = _raise(_annot(body), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_an_action_type_must_be_action() -> None:
    action = f"<< /Type /Font /S /URI /URI {_literal(_GOOD)} >>"
    refusal = _raise(_annot(_annot_dict(action)), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_an_extra_action_key_is_malformed() -> None:
    refusal = _raise(_annot(_good_annot(action_extra="/NewWindow true")), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_hash_escaped_s_is_uri() -> None:
    report = _validate(_annot(_good_annot(s="U#52I")), accepted=_accepted_good())
    assert report.records[0].link == _GOOD


def test_an_action_without_type_is_accepted() -> None:
    report = _validate(_annot(_good_annot(typed=False)), accepted=_accepted_good())
    assert report.records[0].link == _GOOD


def test_an_indirect_uri_string_resolves_once() -> None:
    body = _annot_dict("<< /Type /Action /S /URI /URI 5 0 R >>")
    pdf = _annot(body, objects={5: _obj(5, _literal(_GOOD))})
    report = _validate(pdf, accepted=_accepted_good())
    assert report.records[0].link == _GOOD


def test_an_indirect_action_resolves_once() -> None:
    pdf = _annot(
        _annot_dict("5 0 R"),
        objects={5: _obj(5, _action_dict(_GOOD))},
    )
    report = _validate(pdf, accepted=_accepted_good())
    assert report.records[0].link == _GOOD


def test_a_double_indirect_uri_is_malformed() -> None:
    body = _annot_dict("<< /Type /Action /S /URI /URI 6 0 R >>")
    pdf = _annot(
        body,
        objects={
            6: b"6 0 obj\n7 0 R\nendobj\n",
            7: _obj(7, _literal(_GOOD)),
        },
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_an_indirect_stream_uri_is_malformed() -> None:
    payload = _GOOD.encode("ascii")
    stream = (
        f"5 0 obj\n<< /Length {len(payload)} >>\nstream\n".encode()
        + payload
        + b"\nendstream\nendobj\n"
    )
    body = _annot_dict("<< /Type /Action /S /URI /URI 5 0 R >>")
    refusal = _raise(_annot(body, objects={5: stream}), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_catalog_open_action_is_malformed() -> None:
    pdf = _annot(
        _good_annot(),
        catalog="/OpenAction << /S /URI /URI (https://evil.example/) >>",
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_catalog_additional_action_is_malformed() -> None:
    pdf = _annot(_good_annot(), catalog="/AA << /WC << /S /URI >> >>")
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_catalog_javascript_key_is_malformed() -> None:
    pdf = _annot(_good_annot(), catalog="/JavaScript << /Names [] >>")
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_catalog_launch_key_is_malformed() -> None:
    pdf = _annot(_good_annot(), catalog="/Launch << /F (x) >>")
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_names_tree_without_scripts_is_malformed() -> None:
    pdf = _annot(_good_annot(), catalog="/Names << /Dests [] >>")
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_names_javascript_is_malformed() -> None:
    pdf = _annot(
        _good_annot(),
        catalog="/Names 5 0 R",
        objects={5: _obj(5, "<< /JavaScript << /Names [] >> >>")},
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_catalog_acroform_is_malformed() -> None:
    pdf = _annot(_good_annot(), catalog="/AcroForm << /Fields [] >>")
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_catalog_embedded_file_is_malformed() -> None:
    pdf = _annot(
        _good_annot(),
        catalog="/Names 5 0 R",
        objects={5: _obj(5, "<< /EmbeddedFiles << /Names [] >> >>")},
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_an_extra_catalog_key_is_malformed() -> None:
    pdf = _annot(_good_annot(), catalog="/Outlines << /Type /Outlines >>")
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_catalog_missing_type_is_malformed() -> None:
    pdf = _annot(_good_annot(), root="<< /Pages 2 0 R >>")
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_page_launch_action_is_malformed() -> None:
    pdf = _annot(_good_annot(), resources="<< /XObject << /S /Launch >> >>")
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_an_unreferenced_launch_action_is_malformed() -> None:
    pdf = _annot(_good_annot(), objects={5: _obj(5, "<< /S /Launch >>")})
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_deep_page_nest_is_malformed() -> None:
    nested = "[" * 500 + "0" + "]" * 500
    pdf = _annot(_good_annot(), resources=nested)
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_deep_reference_chain_is_malformed() -> None:
    objects: dict[int, bytes] = {}
    for hop in range(1500):
        number = 10 + hop
        body = "<< >>" if hop == 1499 else f"<< /Next {number + 1} 0 R >>"
        objects[number] = _obj(number, body)
    pdf = _annot(_good_annot(), resources="<< /Next 10 0 R >>", objects=objects)
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_an_escaped_annots_key_is_not_hidden() -> None:
    evil = _annot_dict(_action_dict("https://evil.example/x"))
    pdf = classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _obj(2, "<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>"),
            3: _obj(3, _page(2, "[4 0 R]")),
            4: _obj(4, _good_annot()),
            5: _obj(5, _page(2, "[6 0 R]", annots_key="Ann#6fts")),
            6: _obj(6, evil),
        }
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "host"


def test_an_escaped_subtype_is_a_link() -> None:
    body = (
        "<< /Type /Annot /Sub#74ype /Link /Rect [0 0 1 1] /Border [0 0 0] /F 4 /A "
        f"{_action_dict(_GOOD)} >>"
    )
    report = _validate(_annot(body), accepted=_accepted_good())
    assert report.records[0].link == _GOOD


def test_an_escaped_kids_key_is_walked() -> None:
    pdf = classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _obj(2, "<< /Type /Pages /K#69ds [3 0 R] /Count 1 >>"),
            3: _obj(3, _page(2, "[4 0 R]")),
            4: _obj(4, _good_annot()),
        }
    )
    report = _validate(pdf, accepted=_accepted_good())
    assert report.records[0].link == _GOOD


def test_an_escaped_metadata_key_is_paid_checkout() -> None:
    payload = b"<?xpacket begin='x'?><dc:title>x%2Ecom</dc:title>"
    header = f"5 0 obj\n<< /Type /Metadata /Subtype /XML /Length {len(payload)} >>\n"
    stream = header.encode() + b"stream\n" + payload + b"\nendstream\nendobj\n"
    pdf = classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R /Metad#61ta 5 0 R >>"),
            2: _obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _obj(3, _page(2, "[4 0 R]")),
            4: _obj(4, _good_annot()),
            5: stream,
        }
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "paid_checkout"


def test_a_decoded_action_twin_is_malformed() -> None:
    good = _action_dict(_GOOD)
    body = (
        "<< /Type /Annot /Subtype /Link /Rect [0 0 1 1] /Border [0 0 0] /F 4 "
        f"/#41 << /S /Launch /F (calc.exe) >> /A {good} >>"
    )
    refusal = _raise(_annot(body), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_decoded_s_twin_is_malformed() -> None:
    action = f"<< /Type /Action /#53 /Launch /S /URI /URI {_literal(_GOOD)} >>"
    refusal = _raise(_annot(_annot_dict(action)), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_decoded_kids_twin_is_malformed() -> None:
    pdf = classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _obj(2, "<< /Type /Pages /Kids [3 0 R] /K#69ds [3 0 R] /Count 1 >>"),
            3: _obj(3, _page(2, "[4 0 R]")),
            4: _obj(4, _good_annot()),
        }
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_repeated_raw_action_key_is_malformed() -> None:
    good = _action_dict(_GOOD)
    body = (
        "<< /Type /Annot /Subtype /Link /Rect [0 0 1 1] /Border [0 0 0] /F 4 "
        f"/A {good} /A {good} >>"
    )
    refusal = _raise(_annot(body), accepted=_accepted_good())
    assert refusal.code == "malformed"


@pytest.mark.parametrize("entry", ("JavaScript", "EmbeddedFiles"))
def test_a_shared_names_reference_is_malformed(entry: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # The catalog key set already refuses these names. Widening it leaves the
    # direct /Names read as the refusal, including after /AAA has visited object 5.
    monkeypatch.setattr(
        "money_machine.assets.pdf_objects._CATALOG_ALLOW_EXTRA",
        frozenset({"AAA", "Names"}),
    )
    pdf = _annot(
        _good_annot(),
        catalog="/AAA 5 0 R /Names 5 0 R",
        objects={5: _obj(5, f"<< /{entry} << /Names [] >> >>")},
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def _beside(body: str) -> bytes:
    return classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _obj(3, _page(2, "[4 0 R 5 0 R]")),
            4: _obj(4, _good_annot()),
            5: _obj(5, body),
        }
    )


def _other_annot(subtype: str, action: str) -> str:
    return f"<< /Type /Annot /Subtype /{subtype} /Rect [0 0 1 1] /A {action} >>"


@pytest.mark.parametrize("subtype", ("Widget", "Screen", "RichMedia"))
def test_a_non_link_annotation_is_malformed(subtype: str) -> None:
    refusal = _raise(_beside(_other_annot(subtype, _action_dict(_GOOD))), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_widget_launch_is_malformed() -> None:
    body = _other_annot("Widget", "<< /S /Launch /F (calc.exe) >>")
    refusal = _raise(_beside(body), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_widget_javascript_is_malformed() -> None:
    body = _other_annot("Widget", "<< /S /JavaScript /JS (1) >>")
    refusal = _raise(_beside(body), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_an_outline_launch_is_malformed() -> None:
    pdf = _annot(
        _good_annot(),
        resources="<< /Outlines 5 0 R >>",
        objects={
            5: _obj(5, "<< /Type /Outlines /First 6 0 R /Count 1 >>"),
            6: _obj(6, "<< /Title (x) /Parent 5 0 R /A << /S /Launch /F (calc.exe) >> >>"),
        },
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_links_must_keep_accepted_order() -> None:
    uris = (_LINKS[1][1], _LINKS[0][1], _LINKS[2][1])
    refusal = _raise(_link_pdf(uris))
    assert refusal.code == "link_mismatch"
    assert [job.link for job in refusal.repairs] == [uris[0], uris[1]]


def test_a_dropped_middle_link_is_named() -> None:
    pdf = _link_pdf((_LINKS[0][1], _LINKS[2][1]))
    refusal = _raise(pdf)
    assert refusal.code == "link_mismatch"
    assert [job.link for job in refusal.repairs] == [_LINKS[1][1]]


def test_a_truncated_pdf_is_malformed() -> None:
    refusal = _raise(b"%PDF-1.4\n", accepted=(), clock=None)
    assert refusal.code == "malformed"
    assert refusal.repairs == (AssetRepair(_ASSET, "", "malformed"),)


def test_the_first_repair_names_the_refusal() -> None:
    first = "http://fixture.notion.site/Sage-Green"
    second = "https://x.com"
    pdf = _link_pdf((first, second))
    refusal = _raise(pdf, accepted=(("Sage Green", first), ("Navy Blue", second)))
    assert refusal.code == "not_https"
    assert [job.reason for job in refusal.repairs] == ["not_https", "host"]
    assert [job.index for job in refusal.repairs] == [0, 1]


def test_an_explicit_port_is_malformed() -> None:
    pdf, accepted = _one("https://fixture.notion.site:8443/a")
    refusal = _raise(pdf, accepted=accepted)
    assert refusal.code == "malformed"
    assert refusal.repairs[0].index == 0


def test_an_unparseable_port_is_malformed() -> None:
    pdf, accepted = _one("https://fixture.notion.site:99999/a")
    refusal = _raise(pdf, accepted=accepted)
    assert refusal.code == "malformed"


def test_a_repair_names_one_of_four_identical_uris() -> None:
    uri = _GOOD
    calls = {"n": 0}

    def _third(opened: str, variant: str) -> LinkObservation:
        calls["n"] += 1
        seen = _checker(opened, variant)
        if calls["n"] == 3:
            return LinkObservation(seen.variant, False, True, seen.chain)
        return seen

    pdf = _link_pdf((uri, uri, uri, uri))
    accepted = tuple(("Sage Green", uri) for _ in range(4))
    refusal = _raise(pdf, accepted=accepted, checker=_third)
    assert refusal.repairs == (AssetRepair(_ASSET, uri, "auth_wall", 2),)
    assert calls["n"] == 4


def test_a_refusal_does_not_ask_the_clock() -> None:
    pdf, accepted = _one("https://x.com")
    with pytest.raises(LinkValidationRefusal, match="host") as caught:
        validate_pdf_links(
            pdf,
            asset=_ASSET,
            accepted=accepted,
            known_variants=_KNOWN,
            checker=_checker,
        )
    assert caught.value.records[0].checked_at == ""
    assert caught.value.repairs == (AssetRepair(_ASSET, "https://x.com", "host", 0),)


def test_a_link_without_a_uri_is_malformed() -> None:
    pdf = classic_pdf(
        {
            1: b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
            2: b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
            3: _obj(3, _page(2, "[4 0 R]")),
            4: b"4 0 obj\n<< /Subtype /Link >>\nendobj\n",
        }
    )
    refusal = _raise(pdf, accepted=(), clock=None)
    assert refusal.code == "malformed"


def test_an_indirect_annotation_off_host_is_refused() -> None:
    pdf = classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _obj(3, _page(2, "4 0 R")),
            4: _obj(4, "[5 0 R]"),
            5: _obj(5, _annot_dict(_action_dict("https://x.com"))),
        }
    )
    accepted = (("Sage Green", "https://x.com"),)
    refusal = _raise(pdf, accepted=accepted, clock=_clock)
    assert refusal.code == "host"
    assert refusal.repairs == (AssetRepair(_ASSET, "https://x.com", "host", 0),)


def test_nested_kids_are_walked() -> None:
    pdf = classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _obj(2, "<< /Type /Pages /Kids 3 0 R /Count 1 >>"),
            3: _obj(3, "[4 0 R]"),
            4: _obj(4, "<< /Type /Pages /Parent 2 0 R /Kids 5 0 R /Count 1 >>"),
            5: _obj(5, "[6 0 R]"),
            6: _obj(6, _page(4, "[7 0 R]")),
            7: _obj(7, _annot_dict(_action_dict("https://x.com"))),
        }
    )
    accepted = (("Sage Green", "https://x.com"),)
    refusal = _raise(pdf, accepted=accepted)
    assert refusal.code == "host"
    assert link_annotations(nested_kids_link()) == (1, ("https://x.com",))


def test_mailto_is_malformed() -> None:
    pdf, accepted = _one("mailto:a")
    refusal = _raise(pdf, accepted=accepted)
    assert refusal.code == "malformed"
    assert refusal.repairs == (AssetRepair(_ASSET, "mailto:a", "malformed", 0),)


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
        AssetRepair(_ASSET, "https://fixture.notion.site/Sage-Green", "paid_checkout", 0),
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


def _aliased_root(first: str) -> bytes:
    """Trailer key ``first`` points at the catalog and is written before ``/Root``."""
    catalog = (
        "<< /Type /Catalog /Pages 2 0 R "
        "/OpenAction << /S /URI /URI (https://evil.example/) >> "
        "/AA << /WC << /S /URI /URI (https://evil.example/aa) >> >> "
        "/AcroForm << /Fields [] >> "
        "/Outlines << /Type /Outlines >> "
        "/Names 5 0 R >>"
    )
    objects = {
        1: _obj(1, catalog),
        2: _obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        3: _obj(3, _page(2, "[4 0 R]")),
        4: _obj(4, _good_annot()),
        5: _obj(5, "<< /JavaScript << /Names [] >> >>"),
    }
    trailer = f"<< /Size 6 /{first} 1 0 R /Root 1 0 R >>"
    return classic_pdf(objects, trailer_body=trailer)


def test_info_before_root_cannot_hide_the_catalog() -> None:
    refusal = _raise(_aliased_root("Info"), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_foo_before_root_cannot_hide_the_catalog() -> None:
    refusal = _raise(_aliased_root("Foo"), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_page_uri_additional_action_is_malformed() -> None:
    extra = "/AA << /O << /S /URI /URI (https://evil.example/) >> >>"
    refusal = _raise(_annot(_good_annot(), page_extra=extra), accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_page_additional_action_without_a_uri_is_malformed() -> None:
    refusal = _raise(
        _annot(_good_annot(), page_extra="/AA << /E true >>"),
        accepted=_accepted_good(),
    )
    assert refusal.code == "malformed"


def test_a_page_missing_tabs_is_malformed() -> None:
    bare = _page(2, "[4 0 R]").replace(" /Tabs /S", "")
    pdf = classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _obj(3, bare),
            4: _obj(4, _good_annot()),
        }
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_widget_uri_through_an_outline_is_refused() -> None:
    """An evil widget URI under an allowed ``/Resources`` key, not under ``/Annots``."""
    widget = _other_annot("Widget", _action_dict("https://evil.example/"))
    pdf = classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _obj(3, _page(2, "[4 0 R]", resources="<< /Outlines 5 0 R >>")),
            4: _obj(4, _good_annot()),
            5: _obj(5, widget),
        }
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "host"
    assert refusal.repairs == (AssetRepair(_ASSET, "https://evil.example/", "host"),)


def test_a_widget_after_an_outline_is_still_refused() -> None:
    """The same widget is also in ``/Annots``. Either the URI or the second role refuses it."""
    widget = _other_annot("Widget", _action_dict("https://evil.example/"))
    pdf = classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _obj(3, _page(2, "[4 0 R 5 0 R]", resources="<< /Outlines 5 0 R >>")),
            4: _obj(4, _good_annot()),
            5: _obj(5, widget),
        }
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code in {"host", "malformed"}


def test_a_reentered_action_is_refused() -> None:
    """The action object is reached from ``/XObject`` and again from the link ``/A``."""
    link = "<< /Type /Annot /Subtype /Link /Rect [0 0 1 1] /Border [0 0 0] /F 4 /A 5 0 R >>"
    pdf = classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _obj(3, _page(2, "[4 0 R]", resources="<< /XObject 5 0 R >>")),
            4: _obj(4, link),
            5: _obj(5, _action_dict(_GOOD)),
        }
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"
    assert isinstance(refusal.__cause__, ValueError)
    assert str(refusal.__cause__) == "pdf seen key"


def test_an_accepted_graph_uri_outside_the_link_passes() -> None:
    pdf = _annot(
        _good_annot(),
        objects={5: _obj(5, f"<< /S /URI /URI {_literal(_GOOD)} >>")},
    )
    report = _validate(pdf, accepted=_accepted_good())
    assert report.repairs == ()


def test_an_on_host_graph_uri_must_be_an_accepted_link() -> None:
    extra = "https://fixture.notion.site/not-listed"
    pdf = _annot(
        _good_annot(),
        objects={5: _obj(5, f"<< /S /URI /URI {_literal(extra)} >>")},
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "link_mismatch"
    assert refusal.repairs == (AssetRepair(_ASSET, extra, "link_mismatch"),)


def test_a_deep_kids_chain_is_malformed() -> None:
    objects: dict[int, bytes] = {1: _obj(1, "<< /Type /Catalog /Pages 10 0 R >>")}
    for hop in range(500):
        number = 10 + hop
        if hop == 499:
            body = "<< /Type /Page /Parent 10 0 R >>"
        else:
            body = f"<< /Kids [{number + 1} 0 R] >>"
        objects[number] = _obj(number, body)
    refusal = _raise(classic_pdf(objects), accepted=_accepted_good(), clock=None)
    assert refusal.code == "malformed"


def test_a_second_role_widget_is_malformed() -> None:
    """A good URI, so only the Annots role after ``/Outlines`` refuses the widget."""
    widget = _other_annot("Widget", _action_dict(_GOOD))
    resources = "<< /Outlines 5 0 R /Annots [5 0 R] >>"
    pdf = classic_pdf(
        {
            1: _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _obj(3, _page(2, "[4 0 R]", resources=resources)),
            4: _obj(4, _good_annot()),
            5: _obj(5, widget),
        }
    )
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


def test_a_deep_catalog_is_malformed() -> None:
    nested = "[" * 500 + "0" + "]" * 500
    pdf = _annot(_good_annot(), catalog=f"/Mark {nested}")
    refusal = _raise(pdf, accepted=_accepted_good())
    assert refusal.code == "malformed"


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
        AssetRepair(_ASSET, "https://fixture.notion.site/Lime", "unknown_variant", 0),
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
    assert refusal.repairs == (AssetRepair(_ASSET, uri, "auth_wall", 0),)


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
    except Exception as exc:
        if "Executable doesn't exist" not in str(exc):
            pytest.fail(f"Chromium failed to launch: {exc}")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        _launch_chromium()


def _assert_readme_link_shape(pdf: bytes, count: int) -> None:
    """The real README generator must keep the Chromium link shape."""
    doc = PdfDocument(pdf)
    root = doc.deref(doc.trailer.get("Root"))
    assert isinstance(root, dict)
    assert set(root) == {"Pages", "Type"}
    assert isinstance(root["Type"], PdfName)
    assert root["Type"].value == "Catalog"
    pages = doc.deref(root.get("Pages"))
    assert isinstance(pages, dict)
    kids = doc.deref(pages.get("Kids"))
    assert isinstance(kids, tuple)
    found: list[dict[str, PdfObject]] = []
    bare = 0
    bare_page = {"Type", "Resources", "MediaBox", "Contents", "Tabs", "Parent"}
    for kid in kids:
        page = doc.deref(kid)
        assert isinstance(page, dict)
        annots = page.get("Annots")
        if annots is None:
            assert set(page) == bare_page
            bare += 1
            continue
        assert set(page) == bare_page | {"Annots"}
        array = doc.deref(annots)
        assert isinstance(array, tuple)
        for item in array:
            annot = doc.deref(item)
            assert isinstance(annot, dict)
            found.append(annot)
    assert bare >= 1
    assert len(found) == count
    for annot in found:
        assert set(annot) == {"Type", "Subtype", "Rect", "Border", "F", "A"}
        assert isinstance(annot["Type"], PdfName)
        assert annot["Type"].value == "Annot"
        assert isinstance(annot["Subtype"], PdfName)
        assert annot["Subtype"].value == "Link"
        action = annot["A"]
        assert isinstance(action, dict)
        assert set(action) == {"Type", "S", "URI"}
        assert isinstance(action["Type"], PdfName)
        assert action["Type"].value == "Action"
        assert isinstance(action["S"], PdfName)
        assert action["S"].value == "URI"


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
    _assert_readme_link_shape(rendered.pdf, count)
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
    assert [job.index for job in refusal.repairs] == [0]


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
