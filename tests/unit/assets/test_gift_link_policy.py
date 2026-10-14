"""Direct gift-link guards. These rows do not paint a PDF."""

from __future__ import annotations

import ast
import sys
import types
from pathlib import Path

import pytest

from money_machine.assets.gift_links import (
    refuse_gift_document_info,
    refuse_gift_link_annotations,
    refuse_paid_checkout,
)
from money_machine.assets.pdf_objects import document_strings
from tests.unit.assets.gift_pdf_craft import (
    embed_info_title,
    indirect_link,
    mail_link,
    metadata_packet,
    nested_kids_link,
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


def test_two_part_decimals_stay() -> None:
    assert refuse_paid_checkout("4.9") is None
    assert refuse_paid_checkout("127.1") is None


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


def test_metadata_packet_is_refused() -> None:
    pdf = metadata_packet()
    found = document_strings(pdf)
    assert "Chromium" in found
    assert any("https://x.com" in value for value in found)
    assert refuse_gift_document_info(pdf) == "paid_checkout"


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
