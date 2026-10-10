"""Claim-validator rejection classes and the tests that die if a rule is deleted."""

from __future__ import annotations

import ast
import sys
import types
from collections.abc import Callable
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
    }[rule]
    assert classes == {expected}
    assert all(item.correction.startswith(expected) for item in outcome.corrections)


def test_twelve_and_fourteen_tags_are_rejected() -> None:
    request, draft = _request_and_draft()
    short = draft.model_copy(update={"tags": draft.tags[:-1]})
    long = draft.model_copy(update={"tags": (*draft.tags, draft.tags[0])})
    assert len(short.tags) == 12
    assert len(long.tags) == 14
    for copy in (short, long):
        outcome = validate_claims(copy, request)
        assert outcome.passed is False
        assert {item.rejection_class for item in outcome.corrections} == {"tag_count"}


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


@pytest.mark.parametrize("padded", ["modern digital ", "modern  digital"])
def test_normalized_tag_duplicate_is_rejected_and_casefold_accepts_it(padded: str) -> None:
    request, draft = _request_and_draft()
    assert draft.tags[0].text == "modern digital"
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
