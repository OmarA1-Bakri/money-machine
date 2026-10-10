"""A10 fixture-only merchandising: shape, corrections, and the gates this wave must not move."""

from __future__ import annotations

import ast
import json
import types
from pathlib import Path

import pytest

from money_machine.agents.base import AgentNotImplementedError
from money_machine.agents.contracts.merchandising import (
    DESCRIPTION_ROLES,
    IMAGE_ROLES,
    VIDEO_BEATS,
    ClaimCorrection,
    ListingCopy,
    ListingDraft,
    MerchandisingInput,
)
from money_machine.agents.implementations.merchandising import (
    MAX_CLAIM_ATTEMPTS,
    ClaimValidationClosed,
    DeterministicCopyGenerator,
    MerchandisingInputError,
    merchandise,
)
from money_machine.agents.registry import AgentRegistry
from money_machine.config.settings import AgentCommissioningState
from money_machine.domain.services.claim_validation import validate_claims
from money_machine.domain.services.listing_text import (
    TextSlot,
    etsy_tag,
    mixed_script,
    normalize_text,
    render,
)
from tests.fixtures.merchandising import SHOP_NAME, consistent_request

_AGENT = Path("src/money_machine/agents/implementations/merchandising.py")
_EXPECTED_TAGS = (
    "planners organizers",
    "sage green",
    "navy blue",
    "rose gold",
    "fieldnote shop",
    "daily planning",
    "goal tracking",
    "habit builder",
    "budget tracker",
    "meal planner",
    "fitness log",
    "tablet",
    "phone",
)


class _OnceBad:
    def __init__(self, bad: ListingDraft) -> None:
        self.bad = bad
        self.seen: list[tuple[ClaimCorrection, ...]] = []

    def generate(
        self,
        request: MerchandisingInput,
        corrections: tuple[ClaimCorrection, ...],
    ) -> ListingDraft:
        self.seen.append(corrections)
        if len(self.seen) == 1:
            return self.bad
        return DeterministicCopyGenerator().generate(request, corrections)


class _AlwaysBad:
    def __init__(self, bad: ListingDraft) -> None:
        self.bad = bad
        self.calls = 0

    def generate(
        self,
        request: MerchandisingInput,
        corrections: tuple[ClaimCorrection, ...],
    ) -> ListingDraft:
        del request, corrections
        self.calls += 1
        return self.bad


def _twelve_tags(request: MerchandisingInput) -> ListingDraft:
    draft = DeterministicCopyGenerator().generate(request, ())
    return draft.model_copy(update={"tags": draft.tags[:-1]})


def test_merchandise_returns_the_playbook_listing_shape() -> None:
    request = consistent_request()
    first = merchandise(request)
    second = merchandise(request)
    draft = first.draft
    assert first == second
    assert draft.title.text.startswith(request.spec.identity)
    assert tuple(section.role for section in draft.description_sections) == DESCRIPTION_ROLES
    assert len(draft.description_sections) == 8
    assert tuple(tag.text for tag in draft.tags) == _EXPECTED_TAGS
    assert len(draft.tags) == request.rules.tags == 13
    assert tuple(line.role for line in draft.image_strip) == IMAGE_ROLES
    assert tuple(beat.role for beat in draft.video_sequence) == VIDEO_BEATS
    assert draft.hero_copy.text.startswith(request.spec.identity)
    assert draft.price_sale.price == request.price
    assert draft.price_sale.anchor_price == request.anchor_price
    assert draft.price_sale.sale_configured is True
    assert draft.price_sale.quantity == request.rules.quantity == 999
    assert draft.price_sale.currency == "USD"
    fact_ids = {fact.fact_id for fact in request.facts}
    assert {claim.fact_id for claim in draft.claims} <= fact_ids
    included = next(section for section in draft.description_sections if section.role == "included")
    assert f"{request.page_count} pages" in included.text
    assert SHOP_NAME.casefold() in {tag.text for tag in draft.tags}
    outcome = validate_claims(draft, request)
    assert outcome.passed is True
    by_id = {claim.claim_id: claim for claim in draft.claims}
    surfaces = (
        draft.title,
        draft.hero_copy,
        *draft.description_sections,
        *draft.image_strip,
        *draft.video_sequence,
        *draft.tags,
    )
    for surface in surfaces:
        slots = tuple(
            TextSlot(by_id[claim_id].kind, by_id[claim_id].stated_value)
            for claim_id in surface.claim_ids
        )
        expected = render(surface.template_id, slots, quantity=request.rules.quantity)
        assert normalize_text(surface.text) == normalize_text(expected)


def test_blank_or_long_tag_cannot_become_listing_copy() -> None:
    request = consistent_request()
    draft = DeterministicCopyGenerator().generate(request, ())
    blank = draft.tags[-1].model_copy(update={"text": "   "})
    long = draft.tags[-1].model_copy(update={"text": "a" * 21})
    with pytest.raises(ValueError, match="non-empty"):
        ListingCopy(
            draft=draft.model_copy(update={"tags": (*draft.tags[:-1], blank)}),
            rules=request.rules,
        )
    with pytest.raises(ValueError, match="at most 20"):
        ListingCopy(
            draft=draft.model_copy(update={"tags": (*draft.tags[:-1], long)}),
            rules=request.rules,
        )


def test_off_by_one_tags_cannot_become_listing_copy() -> None:
    request = consistent_request()
    draft = _twelve_tags(request)
    outcome = validate_claims(draft, request)
    assert outcome.passed is False
    assert outcome.corrections[0].rejection_class == "tag_count"
    with pytest.raises(ValueError, match="exactly 13"):
        ListingCopy(draft=draft, rules=request.rules)


def test_bad_draft_is_corrected_and_the_regeneration_passes() -> None:
    request = consistent_request()
    scripted = _OnceBad(_twelve_tags(request))
    copy = merchandise(request, scripted)
    assert len(scripted.seen) == 2
    assert scripted.seen[0] == ()
    correction = scripted.seen[1][0]
    assert correction.rejection_class == "tag_count"
    assert "exactly 13" in correction.correction
    assert "got 12" in correction.correction
    assert len(copy.draft.tags) == 13
    assert validate_claims(copy.draft, request).passed is True


def test_exhausted_retries_fail_closed() -> None:
    request = consistent_request()
    scripted = _AlwaysBad(_twelve_tags(request))
    with pytest.raises(ClaimValidationClosed) as caught:
        merchandise(request, scripted)
    assert scripted.calls == MAX_CLAIM_ATTEMPTS == 3
    assert caught.value.attempts == 3
    assert caught.value.corrections[0].rejection_class == "tag_count"
    assert "got 12" in caught.value.corrections[0].correction


class _DropRaise(ast.NodeTransformer):
    def __init__(self) -> None:
        self.replaced = 0

    def visit_Raise(self, node: ast.Raise) -> ast.AST:
        exc = node.exc
        if (
            isinstance(exc, ast.Call)
            and isinstance(exc.func, ast.Name)
            and exc.func.id == "ClaimValidationClosed"
        ):
            self.replaced += 1
            return ast.Return(value=ast.Name(id="draft", ctx=ast.Load()))
        return node


def test_deleting_the_fail_closed_raise_returns_the_bad_draft() -> None:
    request = consistent_request()
    real = _AlwaysBad(_twelve_tags(request))
    with pytest.raises(ClaimValidationClosed):
        merchandise(request, real)

    drop = _DropRaise()
    tree = drop.visit(ast.parse(_AGENT.read_text(encoding="utf-8")))
    assert drop.replaced == 1
    ast.fix_missing_locations(tree)
    module = types.ModuleType("merchandising_mutant")
    module.__file__ = str(_AGENT)
    exec(compile(tree, str(_AGENT), "exec"), module.__dict__)
    mutant = _AlwaysBad(_twelve_tags(request))
    returned = module.__dict__["merchandise"](request, mutant)
    assert isinstance(returned, ListingDraft)
    assert len(returned.tags) == 12
    assert mutant.calls == MAX_CLAIM_ATTEMPTS


def test_inconsistent_hubs_are_refused_before_generation() -> None:
    request = consistent_request()
    broken = request.model_copy(update={"hubs": tuple(reversed(request.hubs))})

    class _Unused:
        def generate(
            self,
            request: MerchandisingInput,
            corrections: tuple[ClaimCorrection, ...],
        ) -> ListingDraft:
            del request, corrections
            raise AssertionError("generator must not run")

    with pytest.raises(MerchandisingInputError, match="hubs"):
        merchandise(broken, _Unused())


def _with_fact_value(request: MerchandisingInput, key: str, value: str) -> MerchandisingInput:
    facts = tuple(
        fact.model_copy(update={"fact_value": value}) if fact.fact_key == key else fact
        for fact in request.facts
    )
    return request.model_copy(update={"facts": facts})


@pytest.mark.parametrize("extra", ("AI budget forecaster", "Rated 5 stars by 300 buyers"))
def test_appended_feature_fact_is_refused(extra: str) -> None:
    request = consistent_request()
    current = next(fact.fact_value for fact in request.facts if fact.fact_key == "features")
    broken = _with_fact_value(request, "features", f"{current}|{extra}")
    with pytest.raises(MerchandisingInputError, match="features"):
        merchandise(broken)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("identity", "Bestseller Planner 10,000 sold"),
        ("identity", "A 200-Page Digital Planner"),
        ("buyer_problem", "As seen on Forbes"),
    ),
)
def test_freeform_fact_cannot_carry_a_class_claim(field: str, value: str) -> None:
    request = consistent_request()
    spec = request.spec.model_copy(update={field: value})
    broken = _with_fact_value(request, field, value).model_copy(update={"spec": spec})
    with pytest.raises(MerchandisingInputError, match="class claim"):
        merchandise(broken)


def test_secret_link_and_devices_must_be_clean() -> None:
    request = consistent_request()
    cases = (
        ("secret_links", "http://fixture.notion.site", "secret_links"),
        ("secret_links", "https://a.example|https://b.example", "secret_links"),
        ("supported_devices", "Tablet|", "supported_devices"),
        ("supported_devices", "", "supported_devices"),
    )
    for key, value, match in cases:
        broken = _with_fact_value(request, key, value)
        with pytest.raises(MerchandisingInputError, match=match):
            merchandise(broken)


def test_oversized_tag_is_refused_and_class_claims_are_not_tags() -> None:
    assert etsy_tag("Automatic bank sync: not included") == ""
    request = consistent_request()
    draft = DeterministicCopyGenerator().generate(request, ())
    by_id = {claim.claim_id: claim for claim in draft.claims}
    forbidden = {"automation", "review", "sales_performance", "trust_bar", "social_proof"}
    for tag in draft.tags:
        claim = by_id[tag.claim_ids[0]]
        assert claim.kind not in forbidden
        assert tag.text == etsy_tag(claim.stated_value)
        assert tag.text != ""


def test_non_latin_shop_token_is_not_mixed_script() -> None:
    assert mixed_script("Made for planners. Shop Магазин.") is False
    assert mixed_script("\u041codern planner") is True
    request = consistent_request()
    broken = _with_fact_value(request, "shop_name", "Магазин").model_copy(
        update={"shop_name": "Магазин"}
    )
    copy = merchandise(broken)
    audience = next(
        section for section in copy.draft.description_sections if section.role == "audience"
    )
    assert "Магазин" in audience.text
    assert mixed_script(audience.text) is False
    assert validate_claims(copy.draft, broken).passed is True


def test_inconsistent_page_count_is_refused_before_generation() -> None:
    request = consistent_request()
    facts = []
    for fact in request.facts:
        if fact.fact_key == "page_count":
            facts.append(fact.model_copy(update={"fact_value": "41"}))
        else:
            facts.append(fact)
    broken = request.model_copy(update={"facts": tuple(facts)})

    class _Unused:
        def generate(
            self,
            request: MerchandisingInput,
            corrections: tuple[ClaimCorrection, ...],
        ) -> ListingDraft:
            del request, corrections
            raise AssertionError("generator must not run")

    with pytest.raises(MerchandisingInputError, match="page_count"):
        merchandise(broken, _Unused())


def test_a10_stays_designed_and_unregistered() -> None:
    registry = AgentRegistry.from_yaml(Path("."))
    for agent_id in ("A07", "A08", "A09", "A10"):
        definition = registry.get(agent_id)
        assert definition.commissioning_state is AgentCommissioningState.DESIGNED
    with pytest.raises(AgentNotImplementedError, match="A10"):
        registry.get_implementation("A10")
    prompt = Path("src/money_machine/agents/prompts/A10_merchandising.md").read_text(
        encoding="utf-8"
    )
    assert "Uncommissioned scaffold only" in prompt


def test_modules_do_not_import_a_network_provider() -> None:
    paths = (
        _AGENT,
        Path("src/money_machine/domain/services/claim_validation.py"),
        Path("src/money_machine/domain/services/listing_text.py"),
        Path("src/money_machine/agents/contracts/merchandising.py"),
    )
    banned = ("openai", "httpx", "notion", "etsy", "requests", "llm")
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules.append(node.module)
        folded = " ".join(modules).casefold()
        assert all(token not in folded for token in banned)


def test_state_commissioning_and_exit_78_are_unchanged() -> None:
    state = json.loads(Path("docs/control/IMPLEMENTATION_STATE.json").read_text(encoding="utf-8"))
    assert state["current_session"] == 7
    assert state["state_revision"] == 64
    assert state["session_status"] == "complete"
    assert state["next_session"] == 8
    assert state["commissioned_agents"] == []
    evidence = state["required_completion_evidence"]
    assert evidence
    assert all(value is False for value in evidence.values())
    worker = Path("src/money_machine/orchestration/worker.py").read_text(encoding="utf-8")
    assert "Exit 78 held" in worker
