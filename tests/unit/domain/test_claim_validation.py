"""Claim-validator rejection classes and the tests that die if a rule is deleted."""

from __future__ import annotations

import ast
import sys
import types
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from money_machine.agents.contracts.merchandising import (
    DESCRIPTION_ROLES,
    ClaimKind,
    FactKey,
    ListingClaim,
    ListingDraft,
    MerchandisingInput,
    ProductFact,
)
from money_machine.agents.implementations.merchandising import DeterministicCopyGenerator
from money_machine.domain.services.claim_validation import ClaimValidation, validate_claims
from money_machine.domain.services.listing_text import TextSlot, render
from tests.fixtures.merchandising import consistent_request

_VALIDATOR = Path("src/money_machine/domain/services/claim_validation.py")
_RULES = (
    "reject_unknown_fact",
    "reject_invented_page_count",
    "reject_nonexistent_feature",
    "reject_variant_not_built",
    "reject_unsupported_automation",
    "reject_invented_review",
    "reject_invented_sales",
    "reject_invented_trust_bar",
    "reject_unsupported_social_proof",
    "reject_unmatched_statement",
    "reject_unbound_text",
    "reject_mixed_script",
    "reject_tag_count",
    "reject_section_count",
    "reject_price_mismatch",
)


def _request_and_draft() -> tuple[MerchandisingInput, ListingDraft]:
    request = consistent_request()
    draft = DeterministicCopyGenerator().generate(request, ())
    return request, draft


def _replace_stated(draft: ListingDraft, kind: ClaimKind, stated: str) -> ListingDraft:
    claims: list[ListingClaim] = []
    replaced = False
    for claim in draft.claims:
        if not replaced and claim.kind == kind:
            claims.append(claim.model_copy(update={"stated_value": stated}))
            replaced = True
        else:
            claims.append(claim)
    if not replaced:
        raise AssertionError(kind)
    return draft.model_copy(update={"claims": tuple(claims)})


def _retarget_fact(draft: ListingDraft, kind: ClaimKind, fact_id: UUID) -> ListingDraft:
    claims: list[ListingClaim] = []
    replaced = False
    for claim in draft.claims:
        if not replaced and claim.kind == kind:
            claims.append(claim.model_copy(update={"fact_id": fact_id}))
            replaced = True
        else:
            claims.append(claim)
    if not replaced:
        raise AssertionError(kind)
    return draft.model_copy(update={"claims": tuple(claims)})


def _add_claim(
    draft: ListingDraft,
    request: MerchandisingInput,
    kind: ClaimKind,
    stated: str,
    cite: FactKey,
) -> ListingDraft:
    fact = next(item for item in request.facts if item.fact_key == cite)
    claim = ListingClaim(
        claim_id=uuid4(),
        kind=kind,
        fact_id=fact.fact_id,
        stated_value=stated,
    )
    return draft.model_copy(update={"claims": (*draft.claims, claim)})


def _with_fact(
    request: MerchandisingInput,
    key: FactKey,
    value: str,
) -> MerchandisingInput:
    sample = request.facts[0]
    fact = ProductFact(
        fact_id=uuid4(),
        product_id=sample.product_id,
        spec_id=sample.spec_id,
        fact_key=key,
        fact_value=value,
    )
    return request.model_copy(update={"facts": (*request.facts, fact)})


def _retitle(draft: ListingDraft, text: str) -> ListingDraft:
    return draft.model_copy(update={"title": draft.title.model_copy(update={"text": text})})


def _failing_pair(rule: str) -> tuple[MerchandisingInput, ListingDraft]:
    request, draft = _request_and_draft()
    if rule == "reject_unknown_fact":
        return request, _retarget_fact(draft, "shop", uuid4())
    if rule == "reject_invented_page_count":
        return request, _replace_stated(draft, "page_count", "99")
    if rule == "reject_nonexistent_feature":
        return request, _replace_stated(draft, "feature", "Telepathy")
    if rule == "reject_variant_not_built":
        return request, _replace_stated(draft, "variant", "Midnight")
    if rule == "reject_unsupported_automation":
        return request, _add_claim(draft, request, "automation", "runs unattended", "shop_name")
    if rule == "reject_invented_review":
        return request, _add_claim(draft, request, "review", "five star rating", "shop_name")
    if rule == "reject_invented_sales":
        return request, _add_claim(draft, request, "sales_performance", "1000 sold", "shop_name")
    if rule == "reject_invented_trust_bar":
        return request, _add_claim(draft, request, "trust_bar", "trusted by editors", "shop_name")
    if rule == "reject_unsupported_social_proof":
        stated = "customers love this planner"
        return request, _add_claim(draft, request, "social_proof", stated, "shop_name")
    if rule == "reject_unmatched_statement":
        return request, _replace_stated(draft, "shop", "Other Shop")
    if rule == "reject_unbound_text":
        return request, _retitle(draft, "Includes an AI budget forecaster")
    if rule == "reject_mixed_script":
        return request, _retitle(draft, "\u041c" + draft.title.text[1:])
    if rule == "reject_tag_count":
        return request, draft.model_copy(update={"tags": draft.tags[:-1]})
    if rule == "reject_section_count":
        shortened = draft.description_sections[:-1]
        return request, draft.model_copy(update={"description_sections": shortened})
    if rule == "reject_price_mismatch":
        wrong = draft.price_sale.model_copy(update={"currency": "EUR"})
        return request, draft.model_copy(update={"price_sale": wrong})
    raise AssertionError(rule)


class _DropCall(ast.NodeTransformer):
    """Delete one ``corrections.extend(reject_*(...))`` statement."""

    def __init__(self, callee: str) -> None:
        self.callee = callee
        self.dropped = 0

    def visit_Expr(self, node: ast.Expr) -> ast.AST | None:
        call = node.value
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "extend"
            and len(call.args) == 1
            and isinstance(call.args[0], ast.Call)
            and isinstance(call.args[0].func, ast.Name)
            and call.args[0].func.id == self.callee
        ):
            self.dropped += 1
            return None
        return self.generic_visit(node)


def _load_mutant(transform: ast.NodeTransformer, label: str) -> Callable[..., object]:
    tree = transform.visit(ast.parse(_VALIDATOR.read_text(encoding="utf-8")))
    ast.fix_missing_locations(tree)
    name = f"claim_mutant_{label}"
    module = types.ModuleType(name)
    module.__file__ = str(_VALIDATOR)
    sys.modules[name] = module
    exec(compile(tree, str(_VALIDATOR), "exec"), module.__dict__)
    validate = module.__dict__["validate_claims"]
    if not callable(validate):
        raise AssertionError(label)
    return validate


def _mutant_validate(rule: str) -> Callable[..., object]:
    drop = _DropCall(rule)
    validate = _load_mutant(drop, rule)
    if drop.dropped != 1:
        raise AssertionError(f"{rule} dropped {drop.dropped}")
    return validate


def test_matching_draft_passes() -> None:
    request, draft = _request_and_draft()
    outcome = validate_claims(draft, request)
    assert outcome.passed is True
    assert outcome.corrections == ()
    assert len(draft.tags) == 13
    assert tuple(section.role for section in draft.description_sections) == DESCRIPTION_ROLES


def test_claim_requires_a_fact_reference() -> None:
    with pytest.raises(ValidationError):
        ListingClaim(claim_id=uuid4(), kind="shop", stated_value="Fieldnote Shop")


@pytest.mark.parametrize("rule", _RULES)
def test_each_rejection_class_has_a_failing_input(rule: str) -> None:
    request, draft = _failing_pair(rule)
    outcome = validate_claims(draft, request)
    assert outcome.passed is False
    classes = {item.rejection_class for item in outcome.corrections}
    expected = {
        "reject_unknown_fact": "unknown_fact",
        "reject_invented_page_count": "invented_page_count",
        "reject_nonexistent_feature": "nonexistent_feature",
        "reject_variant_not_built": "variant_not_built",
        "reject_unsupported_automation": "unsupported_automation",
        "reject_invented_review": "invented_review",
        "reject_invented_sales": "invented_sales",
        "reject_invented_trust_bar": "invented_trust_bar",
        "reject_unsupported_social_proof": "unsupported_social_proof",
        "reject_unmatched_statement": "unknown_fact",
        "reject_unbound_text": "unbound_text",
        "reject_mixed_script": "unbound_text",
        "reject_tag_count": "tag_count",
        "reject_section_count": "section_count",
        "reject_price_mismatch": "unknown_fact",
    }[rule]
    assert classes == {expected}
    assert all(item.correction.startswith(expected) for item in outcome.corrections)


@pytest.mark.parametrize(
    "update",
    (
        {"currency": "EUR"},
        {"price": Decimal("1")},
        {"anchor_price": Decimal("99.99")},
    ),
)
def test_price_sale_field_mismatch_is_rejected(update: dict[str, object]) -> None:
    request, draft = _request_and_draft()
    copy = draft.model_copy(update={"price_sale": draft.price_sale.model_copy(update=update)})
    outcome = validate_claims(copy, request)
    assert outcome.passed is False
    assert {item.rejection_class for item in outcome.corrections} == {"unknown_fact"}
    assert all(item.correction.startswith("unknown_fact") for item in outcome.corrections)


def _fourteen_unique_tags(
    draft: ListingDraft,
    request: MerchandisingInput,
) -> tuple[MerchandisingInput, ListingDraft]:
    hubs = next(fact for fact in request.facts if fact.fact_key == "hubs")
    extra_name = "Desk Calendar"
    facts = tuple(
        fact.model_copy(update={"fact_value": f"{fact.fact_value}|{extra_name}"})
        if fact.fact_key == "hubs"
        else fact
        for fact in request.facts
    )
    request = request.model_copy(update={"facts": facts})
    claim = ListingClaim(
        claim_id=uuid4(),
        kind="hub",
        fact_id=hubs.fact_id,
        stated_value=extra_name,
    )
    extra = draft.tags[0].model_copy(
        update={"text": "desk calendar", "claim_ids": (claim.claim_id,)}
    )
    tags = (*draft.tags, extra)
    assert len(tags) == 14
    assert len({tag.text for tag in tags}) == 14
    copy = draft.model_copy(update={"tags": tags, "claims": (*draft.claims, claim)})
    return request, copy


def test_twelve_and_fourteen_tags_are_rejected() -> None:
    request, draft = _request_and_draft()
    short = draft.model_copy(update={"tags": draft.tags[:-1]})
    long_request, long = _fourteen_unique_tags(draft, request)
    assert len(short.tags) == 12
    assert len(long.tags) == 14
    short_outcome = validate_claims(short, request)
    long_outcome = validate_claims(long, long_request)
    assert short_outcome.passed is False
    assert long_outcome.passed is False
    assert {item.rejection_class for item in short_outcome.corrections} == {"tag_count"}
    assert {item.rejection_class for item in long_outcome.corrections} == {"tag_count"}


def test_seven_and_nine_sections_are_rejected() -> None:
    request, draft = _request_and_draft()
    short = draft.model_copy(update={"description_sections": draft.description_sections[:-1]})
    long = draft.model_copy(
        update={
            "description_sections": (*draft.description_sections, draft.description_sections[0])
        }
    )
    assert len(short.description_sections) == 7
    assert len(long.description_sections) == 9
    for copy in (short, long):
        outcome = validate_claims(copy, request)
        assert outcome.passed is False
        assert {item.rejection_class for item in outcome.corrections} == {"section_count"}


def test_prose_page_count_is_rejected_when_the_claim_matches() -> None:
    request, draft = _request_and_draft()
    included = draft.description_sections[1]
    assert included.role == "included"
    rewritten = included.model_copy(
        update={"text": included.text.replace(f"{request.page_count} pages", "99 pages", 1)}
    )
    sections = (draft.description_sections[0], rewritten, *draft.description_sections[2:])
    copy = draft.model_copy(update={"description_sections": sections})
    outcome = validate_claims(copy, request)
    assert outcome.passed is False
    assert any(item.rejection_class == "invented_page_count" for item in outcome.corrections)
    assert any("99" in item.correction for item in outcome.corrections)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Fully automated delivery", "unsupported_automation"),
        ("Five star reviews", "invented_review"),
        ("A bestseller with 1000 sold", "invented_sales"),
        ("Trusted by editors", "invented_trust_bar"),
        ("Customers love this", "unsupported_social_proof"),
    ],
)
def test_prose_without_a_matching_fact_is_rejected(title: str, expected: str) -> None:
    request, draft = _request_and_draft()
    copy = draft.model_copy(update={"title": draft.title.model_copy(update={"text": title})})
    outcome = validate_claims(copy, request)
    assert outcome.passed is False
    assert any(item.rejection_class == expected for item in outcome.corrections)


@pytest.mark.parametrize(
    ("kind", "key", "value"),
    [
        ("automation", "automation", "not automated"),
        ("review", "reviews", "recorded review note"),
        ("sales_performance", "sales_count", "0 orders on file"),
        ("trust_bar", "trust_bar", "no trust bar configured"),
        ("social_proof", "social_proof", "customers love the build"),
    ],
)
def test_exact_fact_statement_is_accepted(kind: ClaimKind, key: FactKey, value: str) -> None:
    request, draft = _request_and_draft()
    request = _with_fact(request, key, value)
    fact = next(item for item in request.facts if item.fact_key == key)
    claim = ListingClaim(
        claim_id=uuid4(),
        kind=kind,
        fact_id=fact.fact_id,
        stated_value=value,
    )
    copy = draft.model_copy(update={"claims": (*draft.claims, claim)})
    outcome = validate_claims(copy, request)
    assert outcome.passed is True
    assert outcome.corrections == ()


_WRONG_VALUE = (
    ("automation", "automation", "not automated", "Fully automated, runs unattended."),
    ("review", "reviews", "recorded review note", "Over 10,000 five-star reviews."),
    ("sales_performance", "sales_count", "0 orders on file", "Etsy bestseller: 50,000 units sold."),
    (
        "trust_bar",
        "trust_bar",
        "no trust bar configured",
        "Trusted by Google. As seen in Forbes. Money-back.",
    ),
    (
        "social_proof",
        "social_proof",
        "customers love the build",
        "Thousands of customers love this planner.",
    ),
)


def _wrong_value_copy(
    kind: ClaimKind,
    key: FactKey,
    fact_value: str,
    stated: str,
) -> tuple[MerchandisingInput, ListingDraft]:
    request, draft = _request_and_draft()
    request = _with_fact(request, key, fact_value)
    fact = next(item for item in request.facts if item.fact_key == key)
    claim = ListingClaim(
        claim_id=uuid4(),
        kind=kind,
        fact_id=fact.fact_id,
        stated_value=stated,
    )
    return request, draft.model_copy(update={"claims": (*draft.claims, claim)})


class _AllowTrue(ast.NodeTransformer):
    """Force the value check in ``_kind_matches`` to succeed."""

    def __init__(self) -> None:
        self.hits = 0

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "allowed"
        ):
            node.value = ast.Constant(value=True)
            self.hits += 1
        return node


class _DropFactKey(ast.NodeTransformer):
    """Delete the fact-key guard inside ``_kind_matches``."""

    def __init__(self) -> None:
        self.hits = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name != "_kind_matches":
            return self.generic_visit(node)
        kept: list[ast.stmt] = []
        for stmt in node.body:
            test = stmt.test if isinstance(stmt, ast.If) else None
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Attribute)
                and test.left.attr == "fact_key"
            ):
                self.hits += 1
                continue
            kept.append(stmt)
        node.body = kept
        return node


class _CasefoldTags(ast.NodeTransformer):
    """Compare tags with casefold only, so trailing space stays distinct."""

    def __init__(self) -> None:
        self.hits = 0
        self._inside = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name != "reject_tag_count":
            return self.generic_visit(node)
        self._inside = True
        visited = self.generic_visit(node)
        self._inside = False
        return visited

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if (
            self._inside
            and isinstance(node.func, ast.Name)
            and node.func.id == "normalize_tag"
            and len(node.args) == 1
        ):
            self.hits += 1
            return ast.Call(
                func=ast.Attribute(value=node.args[0], attr="casefold", ctx=ast.Load()),
                args=[],
                keywords=[],
            )
        return self.generic_visit(node)


class _LenSections(ast.NodeTransformer):
    """Accept any eight sections, including a reordered pair."""

    def __init__(self) -> None:
        self.hits = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name != "reject_section_count":
            return self.generic_visit(node)
        self.generic_visit(node)
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        if (
            isinstance(node.left, ast.Name)
            and node.left.id == "roles"
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Eq)
        ):
            self.hits += 1
            node.left = ast.Call(
                func=ast.Name(id="len", ctx=ast.Load()), args=[node.left], keywords=[]
            )
            node.comparators = [
                ast.Call(
                    func=ast.Name(id="len", ctx=ast.Load()),
                    args=[node.comparators[0]],
                    keywords=[],
                )
            ]
        return node


def test_partial_dashboard_output_is_rejected() -> None:
    request, draft = _request_and_draft()
    copy = _replace_stated(draft, "dashboard", "Today panel")
    outcome = validate_claims(copy, request)
    assert outcome.passed is False
    assert any(item.rejection_class == "unknown_fact" for item in outcome.corrections)


@pytest.mark.parametrize("rule", _RULES)
def test_deleting_a_validator_rule_accepts_its_failing_input(rule: str) -> None:
    request, draft = _failing_pair(rule)
    real = validate_claims(draft, request)
    assert real.passed is False
    mutant = _mutant_validate(rule)
    forged = cast(ClaimValidation, mutant(draft, request))
    assert forged.passed is True
    assert forged.corrections == ()


@pytest.mark.parametrize(("kind", "key", "fact_value", "stated"), _WRONG_VALUE)
def test_right_key_wrong_value_is_rejected_and_allowed_true_accepts_it(
    kind: ClaimKind,
    key: FactKey,
    fact_value: str,
    stated: str,
) -> None:
    request, draft = _wrong_value_copy(kind, key, fact_value, stated)
    real = validate_claims(draft, request)
    expected = {
        "automation": "unsupported_automation",
        "review": "invented_review",
        "sales_performance": "invented_sales",
        "trust_bar": "invented_trust_bar",
        "social_proof": "unsupported_social_proof",
    }[kind]
    assert real.passed is False
    assert {item.rejection_class for item in real.corrections} == {expected}
    allow = _AllowTrue()
    mutant = _load_mutant(allow, f"allowed_true_{kind}")
    assert allow.hits == 2
    forged = cast(ClaimValidation, mutant(draft, request))
    assert forged.passed is True
    assert forged.corrections == ()


def test_shop_value_cited_as_automation_needs_the_key_check() -> None:
    request, draft = _request_and_draft()
    shop = next(item for item in request.facts if item.fact_key == "shop_name")
    claim = ListingClaim(
        claim_id=uuid4(),
        kind="automation",
        fact_id=shop.fact_id,
        stated_value=shop.fact_value,
    )
    copy = draft.model_copy(update={"claims": (*draft.claims, claim)})
    real = validate_claims(copy, request)
    assert real.passed is False
    assert {item.rejection_class for item in real.corrections} == {"unsupported_automation"}
    drop = _DropFactKey()
    mutant = _load_mutant(drop, "drop_fact_key")
    assert drop.hits == 1
    forged = cast(ClaimValidation, mutant(copy, request))
    assert forged.passed is True


def test_hub_value_outside_the_fact_list_is_rejected() -> None:
    request, draft = _request_and_draft()
    copy = _replace_stated(draft, "hub", "Not A Hub")
    outcome = validate_claims(copy, request)
    assert outcome.passed is False
    assert {item.rejection_class for item in outcome.corrections} == {"unknown_fact"}


def test_reordered_sections_fail_and_a_length_check_accepts_them() -> None:
    request, draft = _request_and_draft()
    sections = draft.description_sections
    swapped = (sections[1], sections[0], *sections[2:])
    copy = draft.model_copy(update={"description_sections": swapped})
    real = validate_claims(copy, request)
    assert real.passed is False
    assert {item.rejection_class for item in real.corrections} == {"section_count"}
    length = _LenSections()
    mutant = _load_mutant(length, "len_sections")
    assert length.hits == 1
    forged = cast(ClaimValidation, mutant(copy, request))
    assert forged.passed is True


@pytest.mark.parametrize("padded", ["planners organizers ", "planners  organizers"])
def test_normalized_tag_duplicate_is_rejected_and_casefold_accepts_it(padded: str) -> None:
    request, draft = _request_and_draft()
    assert draft.tags[0].text == "planners organizers"
    twin = draft.tags[0].model_copy(update={"text": padded})
    copy = draft.model_copy(update={"tags": (draft.tags[0], twin, *draft.tags[2:])})
    real = validate_claims(copy, request)
    assert real.passed is False
    assert {item.rejection_class for item in real.corrections} == {"tag_count"}
    fold = _CasefoldTags()
    mutant = _load_mutant(fold, "casefold_tags")
    assert fold.hits == 1
    forged = cast(ClaimValidation, mutant(copy, request))
    assert forged.passed is True


def test_blank_and_overlong_tags_are_rejected() -> None:
    request, draft = _request_and_draft()
    blank = draft.tags[-1].model_copy(update={"text": "   "})
    long = draft.tags[-1].model_copy(update={"text": "a" * 21})
    for replacement in (blank, long):
        copy = draft.model_copy(update={"tags": (*draft.tags[:-1], replacement)})
        outcome = validate_claims(copy, request)
        assert outcome.passed is False
        assert any(item.rejection_class == "tag_count" for item in outcome.corrections)


def test_passing_automation_fact_does_not_license_other_prose() -> None:
    request, draft = _request_and_draft()
    request = _with_fact(request, "automation", "not automated")
    fact = next(item for item in request.facts if item.fact_key == "automation")
    claim = ListingClaim(
        claim_id=uuid4(),
        kind="automation",
        fact_id=fact.fact_id,
        stated_value=fact.fact_value,
    )
    copy = _retitle(draft, "Fully automated, runs unattended.")
    copy = copy.model_copy(update={"claims": (*copy.claims, claim)})
    outcome = validate_claims(copy, request)
    assert outcome.passed is False
    classes = {item.rejection_class for item in outcome.corrections}
    assert "unsupported_automation" in classes
    assert "unbound_text" in classes


_SUBSTRING = (
    ("automation", "automation", "not automated", "automated", "unsupported_automation"),
    ("review", "reviews", "recorded review note", "review", "invented_review"),
    ("sales_performance", "sales_count", "0 orders on file", "orders", "invented_sales"),
    ("trust_bar", "trust_bar", "no trust bar configured", "trust", "invented_trust_bar"),
    (
        "social_proof",
        "social_proof",
        "customers love the build",
        "love",
        "unsupported_social_proof",
    ),
)


class _Scoped(ast.NodeTransformer):
    def __init__(self, function: str) -> None:
        self.function = function
        self.hits = 0
        self._inside = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name != self.function:
            return node
        self._inside = True
        visited = self.generic_visit(node)
        self._inside = False
        return visited


class _EqToIn(_Scoped):
    """Change ``stated == fact`` into ``stated in fact``."""

    def __init__(self) -> None:
        super().__init__("_kind_matches")

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        if (
            self._inside
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Eq)
            and isinstance(node.left, ast.Attribute)
            and node.left.attr == "stated_value"
        ):
            self.hits += 1
            node.ops = [ast.In()]
        return node


class _FactItemsToValue(_Scoped):
    """Change ``stated in fact_items(...)`` into ``stated in cited.fact_value``."""

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        comparator = node.comparators[0] if node.comparators else None
        if (
            self._inside
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.In)
            and isinstance(comparator, ast.Call)
            and isinstance(comparator.func, ast.Name)
            and comparator.func.id == "fact_items"
        ):
            self.hits += 1
            node.comparators = [
                ast.Attribute(
                    value=ast.Name(id="cited", ctx=ast.Load()),
                    attr="fact_value",
                    ctx=ast.Load(),
                )
            ]
        return node


class _TemplateContained(_Scoped):
    """Accept a surface when the rendered template is only contained in it."""

    def __init__(self) -> None:
        super().__init__("reject_unbound_text")

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        if not self._inside or not _is_norm_eq(node):
            return node
        self.hits += 1
        return ast.Compare(left=node.comparators[0], ops=[ast.In()], comparators=[node.left])


class _TemplatePrefix(_Scoped):
    """Accept a surface when it merely starts with the rendered template."""

    def __init__(self) -> None:
        super().__init__("reject_unbound_text")

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        if not self._inside or not _is_norm_eq(node):
            return node
        self.hits += 1
        return ast.Call(
            func=ast.Attribute(value=node.left, attr="startswith", ctx=ast.Load()),
            args=[node.comparators[0]],
            keywords=[],
        )


class _NonePasses(_Scoped):
    """Treat a template that cannot be rendered as a pass."""

    def __init__(self) -> None:
        super().__init__("reject_unbound_text")

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        first = node.values[0] if node.values else None
        second = node.values[1] if len(node.values) > 1 else None
        if (
            self._inside
            and isinstance(node.op, ast.And)
            and isinstance(first, ast.Compare)
            and len(first.ops) == 1
            and isinstance(first.ops[0], ast.IsNot)
            and isinstance(second, ast.Compare)
            and _is_norm_eq(second)
        ):
            self.hits += 1
            first.ops = [ast.Is()]
            node.op = ast.Or()
            return node
        return self.generic_visit(node)


class _CountAtLeast(_Scoped):
    """Accept 14 tags when the count check is ``>=`` rather than ``==``."""

    def __init__(self) -> None:
        super().__init__("reject_tag_count")

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        if (
            self._inside
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Eq)
            and isinstance(node.left, ast.Call)
            and isinstance(node.left.func, ast.Name)
            and node.left.func.id == "len"
        ):
            self.hits += 1
            node.ops = [ast.GtE()]
        return node


def _is_norm_eq(node: ast.Compare) -> bool:
    if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
        return False
    if len(node.comparators) != 1:
        return False
    return _is_normalize(node.left) and _is_normalize(node.comparators[0])


def _is_normalize(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "normalize_text"
        and len(node.args) == 1
    )


@pytest.mark.parametrize(("kind", "key", "fact_value", "stated", "expected"), _SUBSTRING)
def test_right_key_substring_is_rejected_and_in_accepts_it(
    kind: ClaimKind,
    key: FactKey,
    fact_value: str,
    stated: str,
    expected: str,
) -> None:
    request, draft = _wrong_value_copy(kind, key, fact_value, stated)
    real = validate_claims(draft, request)
    assert real.passed is False
    assert {item.rejection_class for item in real.corrections} == {expected}
    mutant_tree = _EqToIn()
    mutant = _load_mutant(mutant_tree, f"eq_in_{kind}")
    assert mutant_tree.hits == 1
    forged = cast(ClaimValidation, mutant(draft, request))
    assert forged.passed is True
    assert forged.corrections == ()


@pytest.mark.parametrize(
    ("kind", "cite", "stated", "expected"),
    (
        ("feature", "features", "Hyperlinked", "nonexistent_feature"),
        ("variant", "colour_names", "Sage", "variant_not_built"),
    ),
)
def test_list_substring_needs_item_membership(
    kind: ClaimKind,
    cite: FactKey,
    stated: str,
    expected: str,
) -> None:
    request, draft = _request_and_draft()
    copy = _add_claim(draft, request, kind, stated, cite)
    real = validate_claims(copy, request)
    assert real.passed is False
    assert {item.rejection_class for item in real.corrections} == {expected}
    mutant_tree = _FactItemsToValue("_kind_matches")
    mutant = _load_mutant(mutant_tree, f"items_{kind}")
    assert mutant_tree.hits == 1
    forged = cast(ClaimValidation, mutant(copy, request))
    assert forged.passed is True


def test_hub_substring_needs_item_membership() -> None:
    request, draft = _request_and_draft()
    copy = _add_claim(draft, request, "hub", "Daily", "hubs")
    real = validate_claims(copy, request)
    assert real.passed is False
    assert {item.rejection_class for item in real.corrections} == {"unknown_fact"}
    mutant_tree = _FactItemsToValue("_statement_matches")
    mutant = _load_mutant(mutant_tree, "items_hub")
    assert mutant_tree.hits == 1
    forged = cast(ClaimValidation, mutant(copy, request))
    assert forged.passed is True


def test_appended_text_is_rejected_and_containment_accepts_it() -> None:
    request, draft = _request_and_draft()
    appended = _retitle(draft, f"{draft.title.text} extra")
    real = validate_claims(appended, request)
    assert real.passed is False
    assert {item.rejection_class for item in real.corrections} == {"unbound_text"}
    for label, transform in (("contained", _TemplateContained()), ("prefix", _TemplatePrefix())):
        mutant = _load_mutant(transform, label)
        assert transform.hits == 1
        forged = cast(ClaimValidation, mutant(appended, request))
        assert forged.passed is True
        assert forged.corrections == ()


def test_unknown_template_is_rejected_and_none_accepts_it() -> None:
    request, draft = _request_and_draft()
    title = draft.title.model_copy(update={"template_id": "not-a-template"})
    copy = draft.model_copy(update={"title": title})
    real = validate_claims(copy, request)
    assert real.passed is False
    assert {item.rejection_class for item in real.corrections} == {"unbound_text"}
    mutant_tree = _NonePasses()
    mutant = _load_mutant(mutant_tree, "none_passes")
    assert mutant_tree.hits == 1
    forged = cast(ClaimValidation, mutant(copy, request))
    assert forged.passed is True
    assert forged.corrections == ()


def test_swapped_template_is_unbound() -> None:
    request, draft = _request_and_draft()
    title = draft.title.model_copy(update={"template_id": "hero"})
    copy = draft.model_copy(update={"title": title})
    outcome = validate_claims(copy, request)
    assert outcome.passed is False
    assert {item.rejection_class for item in outcome.corrections} == {"unbound_text"}


def test_fourteen_unique_tags_kill_the_at_least_count() -> None:
    request, draft = _request_and_draft()
    long_request, long = _fourteen_unique_tags(draft, request)
    real = validate_claims(long, long_request)
    assert real.passed is False
    assert {item.rejection_class for item in real.corrections} == {"tag_count"}
    mutant_tree = _CountAtLeast()
    mutant = _load_mutant(mutant_tree, "tag_ge")
    assert mutant_tree.hits == 1
    forged = cast(ClaimValidation, mutant(long, long_request))
    assert forged.passed is True
    assert forged.corrections == ()


def _rendered_text(
    claim_ids: tuple[UUID, ...],
    template_id: str,
    draft: ListingDraft,
    quantity: int,
) -> str:
    by_id = {claim.claim_id: claim for claim in draft.claims}
    slots = tuple(
        TextSlot(by_id[claim_id].kind, by_id[claim_id].stated_value) for claim_id in claim_ids
    )
    return render(template_id, slots, quantity=quantity)


def _rerender(draft: ListingDraft, request: MerchandisingInput) -> ListingDraft:
    quantity = request.rules.quantity
    return draft.model_copy(
        update={
            "title": draft.title.model_copy(
                update={
                    "text": _rendered_text(
                        draft.title.claim_ids, draft.title.template_id, draft, quantity
                    )
                }
            ),
            "hero_copy": draft.hero_copy.model_copy(
                update={
                    "text": _rendered_text(
                        draft.hero_copy.claim_ids, draft.hero_copy.template_id, draft, quantity
                    )
                }
            ),
            "description_sections": tuple(
                item.model_copy(
                    update={
                        "text": _rendered_text(item.claim_ids, item.template_id, draft, quantity)
                    }
                )
                for item in draft.description_sections
            ),
            "image_strip": tuple(
                item.model_copy(
                    update={
                        "text": _rendered_text(item.claim_ids, item.template_id, draft, quantity)
                    }
                )
                for item in draft.image_strip
            ),
            "video_sequence": tuple(
                item.model_copy(
                    update={
                        "text": _rendered_text(item.claim_ids, item.template_id, draft, quantity)
                    }
                )
                for item in draft.video_sequence
            ),
            "tags": tuple(
                item.model_copy(
                    update={
                        "text": _rendered_text(item.claim_ids, item.template_id, draft, quantity)
                    }
                )
                for item in draft.tags
            ),
        }
    )


@pytest.mark.parametrize(
    ("field", "kind", "value", "expected"),
    (
        ("identity", "identity", "Bestseller Planner 10,000 sold", "invented_sales"),
        ("identity", "identity", "A 200-Page Digital Planner", "invented_page_count"),
        ("buyer_problem", "buyer_problem", "As seen on Forbes", "invented_trust_bar"),
    ),
)
def test_freeform_value_does_not_license_its_class(
    field: FactKey,
    kind: ClaimKind,
    value: str,
    expected: str,
) -> None:
    request, draft = _request_and_draft()
    spec = request.spec.model_copy(update={field: value})
    facts = tuple(
        fact.model_copy(update={"fact_value": value}) if fact.fact_key == field else fact
        for fact in request.facts
    )
    request = request.model_copy(update={"spec": spec, "facts": facts})
    copy = _rerender(_replace_stated(draft, kind, value), request)
    outcome = validate_claims(copy, request)
    assert outcome.passed is False
    assert expected in {item.rejection_class for item in outcome.corrections}


def test_shortened_automation_tag_is_unbound() -> None:
    request, draft = _request_and_draft()
    phrase = "Automatic bank sync: not included"
    request = _with_fact(request, "automation", phrase)
    fact = next(item for item in request.facts if item.fact_key == "automation")
    claim = ListingClaim(
        claim_id=uuid4(),
        kind="automation",
        fact_id=fact.fact_id,
        stated_value=phrase,
    )
    tag = draft.tags[-1].model_copy(
        update={"text": "automatic bank sync", "claim_ids": (claim.claim_id,)}
    )
    copy = draft.model_copy(
        update={"claims": (*draft.claims, claim), "tags": (*draft.tags[:-1], tag)}
    )
    outcome = validate_claims(copy, request)
    assert outcome.passed is False
    assert {item.rejection_class for item in outcome.corrections} == {"unbound_text"}


class _DropTemplateBinding(ast.NodeTransformer):
    """Render whenever a surface cites claims, ignoring its required template."""

    def __init__(self) -> None:
        self.hits = 0
        self._inside = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name != "reject_unbound_text":
            return node
        self._inside = True
        visited = self.generic_visit(node)
        self._inside = False
        return visited

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        second = node.values[1] if len(node.values) > 1 else None
        if (
            self._inside
            and isinstance(node.op, ast.And)
            and isinstance(second, ast.Compare)
            and len(second.ops) == 1
            and isinstance(second.ops[0], ast.Eq)
            and isinstance(second.left, ast.Name)
            and second.left.id == "template_id"
        ):
            self.hits += 1
            return node.values[0]
        return self.generic_visit(node)


def test_wrong_template_on_matching_slots_is_refused() -> None:
    request, draft = _request_and_draft()
    identity = next(claim for claim in draft.claims if claim.kind == "identity")
    problem = next(claim for claim in draft.claims if claim.kind == "buyer_problem")
    category = next(claim for claim in draft.claims if claim.kind == "category")
    quantity = request.rules.quantity
    hero = render(
        "hero",
        (
            TextSlot("identity", identity.stated_value),
            TextSlot("buyer_problem", problem.stated_value),
        ),
        quantity=quantity,
    )
    hook = render(
        "hook",
        (
            TextSlot("identity", identity.stated_value),
            TextSlot("category", category.stated_value),
            TextSlot("buyer_problem", problem.stated_value),
        ),
        quantity=quantity,
    )
    title = draft.title.model_copy(
        update={
            "template_id": "hero",
            "claim_ids": (identity.claim_id, problem.claim_id),
            "text": hero,
        }
    )
    sections = tuple(
        section.model_copy(
            update={
                "template_id": "hook",
                "claim_ids": (identity.claim_id, category.claim_id, problem.claim_id),
                "text": hook,
            }
        )
        if section.role == "offer"
        else section
        for section in draft.description_sections
    )
    copy = draft.model_copy(update={"title": title, "description_sections": sections})
    offer = next(section for section in copy.description_sections if section.role == "offer")
    assert "Price" not in offer.text
    assert copy.title.text == hero
    real = validate_claims(copy, request)
    assert real.passed is False
    assert {item.rejection_class for item in real.corrections} == {"unbound_text"}
    mutant_tree = _DropTemplateBinding()
    mutant = _load_mutant(mutant_tree, "template_binding")
    assert mutant_tree.hits == 1
    forged = cast(ClaimValidation, mutant(copy, request))
    assert forged.passed is True
    assert forged.corrections == ()


class _DropTagKind(ast.NodeTransformer):
    """Stop refusing a tag whose cited claim is not a tag kind."""

    def __init__(self) -> None:
        self.hits = 0

    def visit_If(self, node: ast.If) -> ast.AST:
        if _calls(node.test, "_tag_kind_allowed"):
            self.hits += 1
            return ast.Pass()
        return self.generic_visit(node)


def test_class_claim_tag_is_refused_and_dropping_the_kind_accepts_it() -> None:
    mutant_tree = _DropTagKind()
    mutant = _load_mutant(mutant_tree, "tag_kind")
    assert mutant_tree.hits == 1
    cases: tuple[tuple[ClaimKind, FactKey, str], ...] = (
        ("automation", "automation", "not automated"),
        ("review", "reviews", "recorded review note"),
        ("sales_performance", "sales_count", "0 orders on file"),
        ("trust_bar", "trust_bar", "no trust bar"),
        ("social_proof", "social_proof", "loved by buyers"),
    )
    for kind, key, phrase in cases:
        request, draft = _request_and_draft()
        request = _with_fact(request, key, phrase)
        fact = next(item for item in request.facts if item.fact_key == key)
        claim = ListingClaim(
            claim_id=uuid4(),
            kind=kind,
            fact_id=fact.fact_id,
            stated_value=phrase,
        )
        tag = draft.tags[-1].model_copy(update={"text": phrase, "claim_ids": (claim.claim_id,)})
        copy = draft.model_copy(
            update={"claims": (*draft.claims, claim), "tags": (*draft.tags[:-1], tag)}
        )
        real = validate_claims(copy, request)
        assert real.passed is False
        assert {item.rejection_class for item in real.corrections} == {"unbound_text"}
        forged = cast(ClaimValidation, mutant(copy, request))
        assert forged.passed is True
        assert forged.corrections == ()


class _FactListSubset(ast.NodeTransformer):
    """Treat a longer fact list as sourced when it merely contains the built values."""

    def __init__(self) -> None:
        self.hits = 0
        self._inside = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        entered = node.name == "_fact_sourced"
        previous = self._inside
        if entered:
            self._inside = True
        visited = self.generic_visit(node)
        self._inside = previous
        return visited

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        if (
            self._inside
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Eq)
            and isinstance(node.left, ast.Call)
            and isinstance(node.left.func, ast.Name)
            and node.left.func.id == "fact_items"
        ):
            self.hits += 1
            return ast.Compare(
                left=ast.Call(
                    func=ast.Name(id="set", ctx=ast.Load()),
                    args=[node.comparators[0]],
                    keywords=[],
                ),
                ops=[ast.LtE()],
                comparators=[
                    ast.Call(
                        func=ast.Name(id="set", ctx=ast.Load()),
                        args=[node.left],
                        keywords=[],
                    )
                ],
            )
        return node


def test_extra_colour_fact_is_rejected_and_a_subset_accepts_it() -> None:
    request, draft = _request_and_draft()
    facts = tuple(
        fact.model_copy(update={"fact_value": f"{fact.fact_value}|Midnight Black"})
        if fact.fact_key == "colour_names"
        else fact
        for fact in request.facts
    )
    request = request.model_copy(update={"facts": facts})
    real = validate_claims(draft, request)
    assert real.passed is False
    assert {item.rejection_class for item in real.corrections} == {"variant_not_built"}
    mutant_tree = _FactListSubset()
    mutant = _load_mutant(mutant_tree, "colour_subset")
    assert mutant_tree.hits == 1
    forged = cast(ClaimValidation, mutant(draft, request))
    assert forged.passed is True
    assert forged.corrections == ()


class _LicenseEveryPage(ast.NodeTransformer):
    """Treat every page phrase as licensed."""

    def __init__(self) -> None:
        self.hits = 0

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "licensed"
        ):
            self.hits += 1
            node.value = ast.Constant(value=True)
        return node


def test_rendered_page_phrase_needs_the_citation_check() -> None:
    request, draft = _request_and_draft()
    value = "A 200 page planner"
    spec = request.spec.model_copy(update={"identity": value})
    facts = tuple(
        fact.model_copy(update={"fact_value": value}) if fact.fact_key == "identity" else fact
        for fact in request.facts
    )
    request = request.model_copy(update={"spec": spec, "facts": facts})
    copy = _rerender(_replace_stated(draft, "identity", value), request)
    real = validate_claims(copy, request)
    assert real.passed is False
    assert "invented_page_count" in {item.rejection_class for item in real.corrections}
    mutant_tree = _LicenseEveryPage()
    mutant = _load_mutant(mutant_tree, "license_pages")
    assert mutant_tree.hits == 1
    forged = cast(ClaimValidation, mutant(copy, request))
    assert forged.passed is True
    assert forged.corrections == ()


def _calls(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == name
        for child in ast.walk(node)
    )
