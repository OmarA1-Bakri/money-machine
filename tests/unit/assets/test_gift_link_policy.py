"""Direct gift-link guards. These rows do not paint a PDF."""

from __future__ import annotations

import ast
import sys
import types
from pathlib import Path

import pytest

from money_machine.agents.implementations.merchandising import merchandise
from money_machine.assets.delivery_pdfs import DeliveryPdfRefusal, render_gift_pdf
from money_machine.assets.design_tokens import listing_token_payload, load_tokens
from money_machine.assets.gift_links import (
    refuse_gift_document_info,
    refuse_gift_link_annotations,
    refuse_paid_checkout,
)
from money_machine.assets.pdf_objects import document_strings, link_annotations
from money_machine.assets.pdf_reader import PdfDocument, PdfRef
from tests.fixtures.merchandising import consistent_request
from tests.unit.assets.gift_pdf_craft import (
    classic_pdf,
    deep_info_chain,
    embed_info_title,
    indirect_link,
    looping_kids,
    mail_link,
    metadata_packet,
    nested_kids_link,
    reference_chain,
    untyped_page,
)

_LINKS = Path(__file__).resolve().parents[3] / "src" / "money_machine" / "assets" / "gift_links.py"
_TITLE = "https://www.etsy.com/listing/123/planner"


@pytest.mark.parametrize("text", ("127.0.0.1", "0x7f.0.0.1"))
def test_dotted_address_is_refused(text: str) -> None:
    assert refuse_paid_checkout(text) == "paid_checkout"


@pytest.mark.parametrize(
    "text",
    ("0x7f.1", "0177.1", "1.2.3", "1.2.3.4", "192.168.0.1", "1.2.3.4/l/x"),
)
def test_other_numeric_forms_are_refused(text: str) -> None:
    assert refuse_paid_checkout(text) == "paid_checkout"


@pytest.mark.parametrize(
    "text",
    (".1.2.3.4", "Checklist .1.2.3.4", "Checklist at a.1.2.3.4"),
)
def test_unanchored_dotted_address_is_refused(text: str) -> None:
    assert refuse_paid_checkout(text) == "paid_checkout"


def test_two_part_decimals_stay() -> None:
    assert refuse_paid_checkout("4.9") is None
    assert refuse_paid_checkout("127.1") is None
    assert refuse_paid_checkout("0x7f000001") is None
    assert refuse_paid_checkout("2130706433") is None


def test_percent_encoding_is_refused() -> None:
    assert refuse_paid_checkout("x%2Ecom") == "paid_checkout"


@pytest.mark.parametrize("text", ("Checklist a:b", "a@b", "50%", "a\\b", "a/b"))
def test_excluded_character_is_not_a_folded_link(text: str) -> None:
    assert refuse_paid_checkout(text) is None


def test_fullwidth_fold_is_not_a_folded_link() -> None:
    assert refuse_paid_checkout("Checklist \uff46\uff4f\uff4f") is None
    assert refuse_paid_checkout("4\uff0e9") is None


def test_format_host_is_refused() -> None:
    assert refuse_paid_checkout("x\u200b.com") == "paid_checkout"


def test_scheme_is_refused() -> None:
    assert refuse_paid_checkout("ftp://1.2.3.4/x") == "paid_checkout"


def test_www_prefix_is_refused() -> None:
    assert refuse_paid_checkout("www.x") == "paid_checkout"


def test_checkout_word_is_refused() -> None:
    assert refuse_paid_checkout("Checklist checkout") == "paid_checkout"


def test_mail_address_is_not_a_folded_link() -> None:
    assert refuse_paid_checkout("mailto:a") is None


def test_mail_annotation_is_refused() -> None:
    assert refuse_gift_link_annotations(mail_link()) == "paid_checkout"


def test_indirect_annotation_is_refused() -> None:
    assert refuse_gift_link_annotations(indirect_link()) == "paid_checkout"


def test_nested_kids_annotation_is_refused() -> None:
    assert refuse_gift_link_annotations(nested_kids_link()) == "paid_checkout"


def test_indirect_kids_link_is_found() -> None:
    count, uris = link_annotations(nested_kids_link())
    assert count == 1
    assert uris == ("https://x.com",)


def test_letter_prefixed_dotted_address_stays() -> None:
    assert refuse_paid_checkout("v1.2.3.4") is None


def test_marked_last_octet_is_refused() -> None:
    assert refuse_paid_checkout("1.2.0x7f") == "paid_checkout"
    assert refuse_paid_checkout("1.0x10") == "paid_checkout"


def test_deep_info_chain_is_paid_checkout() -> None:
    pdf = deep_info_chain()
    with pytest.raises(ValueError, match="pdf reference"):
        document_strings(pdf)
    assert refuse_gift_document_info(pdf) == "paid_checkout"


def _deep_paint(_html: str, _tokens: object) -> bytes:
    return deep_info_chain()


def test_deep_info_chain_is_delivery_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("money_machine.assets.delivery_pdfs._paint", _deep_paint)
    request = consistent_request()
    with pytest.raises(DeliveryPdfRefusal, match="paid_checkout"):
        render_gift_pdf(
            merchandise(request),
            request,
            load_tokens(listing_token_payload()),
            build_version=4,
        )


def test_untyped_page_is_refused() -> None:
    assert refuse_gift_link_annotations(untyped_page()) == "paid_checkout"


def test_looping_page_kids_is_refused() -> None:
    assert refuse_gift_link_annotations(looping_kids()) == "paid_checkout"


def test_reference_chain_over_eight_is_refused() -> None:
    short = PdfDocument(reference_chain(7))
    found = short.deref(PdfRef(1, 0))
    assert isinstance(found, dict)
    long = PdfDocument(reference_chain(8))
    with pytest.raises(ValueError, match="pdf reference"):
        long.deref(PdfRef(1, 0))


def test_metadata_packet_is_refused() -> None:
    pdf = metadata_packet()
    found = document_strings(pdf)
    assert "Chromium" in found
    assert any("https://x.com" in value for value in found)
    assert refuse_gift_document_info(pdf) == "paid_checkout"


def _gift_obj(number: int, body: str) -> bytes:
    return f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")


def test_an_escaped_annots_key_is_paid_checkout() -> None:
    pdf = classic_pdf(
        {
            1: _gift_obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _gift_obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _gift_obj(3, "<< /Type /Page /Parent 2 0 R /Ann#6fts [4 0 R] >>"),
            4: _gift_obj(4, "<< /Subtype /Link /A << /S /URI /URI (https://x.com) >> >>"),
        }
    )
    assert refuse_gift_link_annotations(pdf) == "paid_checkout"


def test_an_escaped_subtype_link_is_paid_checkout() -> None:
    pdf = classic_pdf(
        {
            1: _gift_obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _gift_obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _gift_obj(3, "<< /Type /Page /Parent 2 0 R /Annots [4 0 R] >>"),
            4: _gift_obj(4, "<< /Sub#74ype /Link /A << /S /URI /URI (https://x.com) >> >>"),
        }
    )
    assert refuse_gift_link_annotations(pdf) == "paid_checkout"


def test_an_escaped_kids_key_is_walked() -> None:
    pdf = classic_pdf(
        {
            1: _gift_obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _gift_obj(2, "<< /Type /Pages /K#69ds [3 0 R] /Count 1 >>"),
            3: _gift_obj(3, "<< /Type /Page /Parent 2 0 R /Annots [4 0 R] >>"),
            4: _gift_obj(4, "<< /Subtype /Link /A << /S /URI /URI (https://x.com) >> >>"),
        }
    )
    count, uris = link_annotations(pdf)
    assert count == 1
    assert uris == ("https://x.com",)
    assert refuse_gift_link_annotations(pdf) == "paid_checkout"


def test_an_escaped_metadata_key_is_paid_checkout() -> None:
    payload = b"<?xpacket begin='x'?><dc:title>x%2Ecom</dc:title>"
    header = f"5 0 obj\n<< /Type /Metadata /Subtype /XML /Length {len(payload)} >>\n"
    stream = header.encode() + b"stream\n" + payload + b"\nendstream\nendobj\n"
    pdf = classic_pdf(
        {
            1: _gift_obj(1, "<< /Type /Catalog /Pages 2 0 R /Metad#61ta 5 0 R >>"),
            2: _gift_obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _gift_obj(3, "<< /Type /Page /Parent 2 0 R >>"),
            5: stream,
        }
    )
    assert refuse_gift_document_info(pdf) == "paid_checkout"


def test_a_deep_kids_chain_is_malformed() -> None:
    objects = {1: _gift_obj(1, "<< /Type /Catalog /Pages 10 0 R >>")}
    for hop in range(500):
        number = 10 + hop
        if hop == 499:
            body = "<< /Type /Page /Parent 10 0 R >>"
        else:
            body = f"<< /Kids [{number + 1} 0 R] >>"
        objects[number] = _gift_obj(number, body)
    assert refuse_gift_link_annotations(classic_pdf(objects)) == "malformed"


def test_a_deep_nest_is_paid_checkout() -> None:
    nested = "[" * 500 + "0" + "]" * 500
    pdf = classic_pdf(
        {
            1: _gift_obj(1, "<< /Type /Catalog /Pages 2 0 R >>"),
            2: _gift_obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            3: _gift_obj(3, f"<< /Type /Page /Parent 2 0 R /Resources {nested} >>"),
        }
    )
    assert refuse_gift_link_annotations(pdf) == "paid_checkout"


class _DropCount(ast.NodeTransformer):
    def __init__(self) -> None:
        self.dropped = 0
        self._on = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name != "refuse_gift_link_annotations":
            return node
        self._on = True
        updated = self.generic_visit(node)
        self._on = False
        return updated

    def visit_If(self, node: ast.If) -> ast.AST | None:
        if self._on and isinstance(node.test, ast.Name) and node.test.id == "count":
            self.dropped += 1
            return None
        return self.generic_visit(node)


class _DropCall(ast.NodeTransformer):
    def __init__(self, function: str, callee: str) -> None:
        self.function = function
        self.callee = callee
        self.dropped = 0
        self._on = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name != self.function:
            return node
        self._on = True
        updated = self.generic_visit(node)
        self._on = False
        return updated

    def visit_If(self, node: ast.If) -> ast.AST | None:
        call = node.test.left if isinstance(node.test, ast.Compare) else None
        if (
            self._on
            and isinstance(node.test, ast.Compare)
            and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.IsNot)
            and isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == self.callee
        ):
            self.dropped += 1
            return ast.Pass()
        return self.generic_visit(node)


def _compiled(transform: ast.NodeTransformer, module_name: str) -> types.ModuleType:
    tree = transform.visit(ast.parse(_LINKS.read_text(encoding="utf-8")))
    dropped = getattr(transform, "dropped", 0)
    if dropped != 1 or not isinstance(tree, ast.Module):
        raise AssertionError(f"{module_name} dropped {dropped}")
    ast.fix_missing_locations(tree)
    module = types.ModuleType(module_name)
    module.__file__ = str(_LINKS)
    sys.modules[module_name] = module
    exec(compile(tree, str(_LINKS), "exec"), module.__dict__)
    return module


def test_gift_link_annotation_mutant_accepts() -> None:
    pdf = mail_link()
    assert refuse_gift_link_annotations(pdf) == "paid_checkout"
    module = _compiled(_DropCount(), "gift_links_without_count")
    refuse = module.__dict__["refuse_gift_link_annotations"]
    assert callable(refuse)
    assert refuse(pdf) is None


def test_gift_document_title_mutant_accepts() -> None:
    embedded = embed_info_title(mail_link(), _TITLE)
    assert _TITLE.encode("ascii") not in embedded
    assert refuse_gift_document_info(embedded) == "paid_checkout"
    module = _compiled(
        _DropCall("refuse_gift_document_info", "refuse_paid_checkout"),
        "gift_links_without_info",
    )
    refuse = module.__dict__["refuse_gift_document_info"]
    assert callable(refuse)
    assert refuse(embedded) is None
