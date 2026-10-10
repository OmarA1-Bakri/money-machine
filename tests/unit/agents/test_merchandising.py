"""A10 fixture-only merchandising: shape, corrections, and the gates this wave must not move."""

from __future__ import annotations

import ast
import json
import sys
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
    encode_dashboard,
    encode_free_gift,
    encode_support,
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
from tests.fixtures.products import create_fixture_product_spec

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


def _wrong_price_sale(request: MerchandisingInput) -> ListingDraft:
    draft = DeterministicCopyGenerator().generate(request, ())
    return draft.model_copy(
        update={"price_sale": draft.price_sale.model_copy(update={"currency": "EUR"})}
    )


def test_injected_price_sale_mismatch_fails_closed() -> None:
    request = consistent_request()
    scripted = _AlwaysBad(_wrong_price_sale(request))
    with pytest.raises(ClaimValidationClosed) as caught:
        merchandise(request, scripted)
    assert scripted.calls == MAX_CLAIM_ATTEMPTS == 3
    assert {item.rejection_class for item in caught.value.corrections} == {"unknown_fact"}
    assert all("price_sale" in item.correction for item in caught.value.corrections)


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


class _MustNotGenerate:
    def generate(
        self,
        request: MerchandisingInput,
        corrections: tuple[ClaimCorrection, ...],
    ) -> ListingDraft:
        del request, corrections
        raise AssertionError("generator must not run")


def _refuse(request: MerchandisingInput) -> None:
    with pytest.raises(MerchandisingInputError, match="class claim"):
        merchandise(request, _MustNotGenerate())


def _bound(kind: str, value: str) -> MerchandisingInput:
    if kind == "base_category":
        return consistent_request(create_fixture_product_spec(base_category=value))
    if kind == "identity":
        return consistent_request(create_fixture_product_spec(identity=value))
    if kind == "buyer_problem":
        return consistent_request(create_fixture_product_spec(buyer_problem=value))
    if kind == "feature":
        features = (
            "Hyperlinked navigation",
            "Interactive checkboxes",
            "Monthly calendar views",
            "Weekly spread templates",
            value,
        )
        return consistent_request(create_fixture_product_spec(features=features))
    if kind == "hub":
        hubs = (
            value,
            "Goal Tracking",
            "Habit Builder",
            "Budget Tracker",
            "Meal Planner",
            "Fitness Log",
        )
        return consistent_request(create_fixture_product_spec(hubs=hubs))
    if kind == "colour":
        return consistent_request(
            create_fixture_product_spec(colour_variants=("Sage Green", "Navy Blue", value))
        )
    raise AssertionError(kind)


_PAGE_FACTS = (
    ("base_category", "200pp Planners"),
    ("feature", "200pp of printable spreads"),
    ("hub", "300pp Fitness Log"),
    ("base_category", "300 printable pages"),
    ("base_category", "<b>200</b> pages"),
    ("identity", "One hundred pages Planner"),
    ("identity", "Two Hundred Page Planner"),
    ("buyer_problem", "Over one hundred pages of spreads"),
    ("feature", "One hundred printable pages"),
    ("colour", "Hundred Page Rose"),
    ("base_category", "200 pp"),
    ("feature", "plus 100 bonus pages"),
    ("base_category", "200\u00a0pages"),
    ("feature", "200+ pages"),
    ("base_category", "**200** pages"),
    ("identity", "One-Hundred-Page Planner"),
    ("identity", "Forty-Two-Page"),
    ("identity", "Two Hundred-Page Planner"),
    ("buyer_problem", "Hundred-Page Planner"),
    ("identity", "Four Page Planner"),
    ("feature", "12-page starter kit"),
)


@pytest.mark.parametrize(("kind", "value"), _PAGE_FACTS)
def test_each_page_count_shape_in_a_fact_is_refused(kind: str, value: str) -> None:
    _refuse(_bound(kind, value))


_FORMAT_MARKS = ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad")


@pytest.mark.parametrize("mark", _FORMAT_MARKS)
def test_each_format_character_in_a_fact_is_refused(mark: str) -> None:
    _refuse(_bound("buyer_problem", f"Get Re{mark}views of planning"))


@pytest.mark.parametrize(
    ("kind", "value"),
    (
        ("hub", "Rated 5 st\u200bars by buyers"),
        ("feature", "Fully auto\u200bmated bank sync"),
        ("hub", "Best\u00adseller planner kit"),
        ("identity", "Top-rated"),
        ("identity", "Top-Rated Planner"),
        ("base_category", "5k downloads"),
        ("buyer_problem", "Featured in Vogue and Forbes"),
        ("buyer_problem", "Loved by 5,000 teachers"),
        ("base_category", "Hands-free"),
        ("identity", "Bestsel\u2060ler"),
        ("feature", "auto\u200bmated"),
    ),
)
def test_class_paraphrase_in_a_fact_is_refused(kind: str, value: str) -> None:
    _refuse(_bound(kind, value))


def _in_field(field: str, value: str) -> MerchandisingInput:
    """Put one value in one of the eight fact fields the copy shows."""
    if field in {"identity", "buyer_problem", "feature", "hub", "colour"}:
        return _bound(field, value)
    request = consistent_request()
    if field == "dashboard":
        dashboard = request.notification_dashboard.model_copy(
            update={"outputs": (value, "Reminder list")}
        )
        return _with_fact_value(
            request, "dashboard_outputs", encode_dashboard(dashboard)
        ).model_copy(update={"notification_dashboard": dashboard})
    if field == "support":
        support = request.support.model_copy(update={"channel": value})
        return _with_fact_value(request, "support", encode_support(support)).model_copy(
            update={"support": support}
        )
    if field == "gift":
        gift = request.free_gift.model_copy(update={"name": value})
        return _with_fact_value(request, "free_gift", encode_free_gift(gift)).model_copy(
            update={"free_gift": gift}
        )
    raise AssertionError(field)


_EIGHT_FIELDS = (
    "identity",
    "buyer_problem",
    "hub",
    "feature",
    "colour",
    "dashboard",
    "support",
    "gift",
)


def _refuse_hidden_everywhere(marks: tuple[str, ...]) -> None:
    for mark in marks:
        for field in _EIGHT_FIELDS:
            _refuse(_in_field(field, f"Bestsel{mark}ler"))
            _refuse(_in_field(field, f"Dai{mark}ly Notes"))
        hidden = _with_fact_value(
            consistent_request(), "secret_links", f"https://fixture.notion.site/pl{mark}anner"
        )
        with pytest.raises(MerchandisingInputError, match="not one https link"):
            merchandise(hidden, _MustNotGenerate())


def test_comparison_drops_every_ignorable_character() -> None:
    for mark in ("\u034f", "\ufe0f", "\U000e0100", "\u180b", "\u17b4", "\u3164", "\U000e0001"):
        assert normalize_text(f"Bestsel{mark}ler") == "bestseller"


def test_combining_grapheme_joiner_is_refused() -> None:
    _refuse_hidden_everywhere(("\u034f",))


def test_variation_selectors_are_refused() -> None:
    _refuse_hidden_everywhere(("\ufe00", "\ufe07", "\ufe0f"))


def test_variation_selector_supplement_is_refused() -> None:
    _refuse_hidden_everywhere(("\U000e0100", "\U000e0150", "\U000e01ef"))


def test_mongolian_free_variation_selectors_are_refused() -> None:
    _refuse_hidden_everywhere(("\u180b", "\u180c", "\u180d", "\u180f"))


def test_khmer_inherent_vowels_are_refused() -> None:
    _refuse_hidden_everywhere(("\u17b4", "\u17b5"))


def test_hangul_fillers_are_refused() -> None:
    _refuse_hidden_everywhere(("\u115f", "\u1160", "\u3164", "\uffa0"))


def test_tag_block_and_reserved_ignorables_are_refused() -> None:
    _refuse_hidden_everywhere(("\U000e0000", "\U000e0001", "\U000e0080", "\U000e0fff"))


@pytest.mark.parametrize(
    "value",
    ("500 reviews", "1,000+ reviews", "4.9 average rating", "Rating 4.9", "1,000+ orders"),
)
@pytest.mark.parametrize("field", ("identity", "buyer_problem", "hub", "feature"))
def test_review_and_order_counts_are_refused(field: str, value: str) -> None:
    _refuse(_bound(field, value))


@pytest.mark.parametrize(
    ("kind", "value"),
    (
        ("identity", "Travel Planner"),
        ("identity", "Gravel Bike Log"),
        ("identity", "Brave Habits Planner"),
        ("hub", "Travel Log"),
        ("identity", "Room #1 Inventory"),
        ("identity", "Goal #1"),
        ("identity", "Join 30 Day Challenge"),
        ("identity", "Automatic Savings Planner"),
        ("feature", "One page per day"),
        ("identity", "One Page Summary"),
        ("feature", "4 page weekly layout"),
        ("identity", "Book Review Journal"),
        ("identity", "Star Chart Planner"),
    ),
)
def test_names_without_a_claim_publish(kind: str, value: str) -> None:
    request = _bound(kind, value)
    copy = merchandise(request)
    shown = " ".join(
        (copy.draft.title.text, *(section.text for section in copy.draft.description_sections))
    )
    assert value in shown
    assert validate_claims(copy.draft, request).passed is True


def test_review_and_star_nouns_are_allowed() -> None:
    journal = consistent_request(create_fixture_product_spec(identity="Book Review Journal"))
    journal_copy = merchandise(journal)
    assert journal_copy.draft.title.text.startswith("Book Review Journal")
    assert validate_claims(journal_copy.draft, journal).passed is True
    chart = consistent_request(create_fixture_product_spec(identity="Star Chart Planner"))
    chart_copy = merchandise(chart)
    assert chart_copy.draft.title.text.startswith("Star Chart Planner")
    assert validate_claims(chart_copy.draft, chart).passed is True
    hubs = (
        "Book Reviews",
        "Goal Tracking",
        "Habit Builder",
        "Budget Tracker",
        "Meal Planner",
        "Fitness Log",
    )
    reviewed = consistent_request(create_fixture_product_spec(hubs=hubs))
    reviewed_copy = merchandise(reviewed)
    assert any(
        "Book Reviews" in section.text for section in reviewed_copy.draft.description_sections
    )
    assert validate_claims(reviewed_copy.draft, reviewed).passed is True


@pytest.mark.parametrize(
    "identity",
    ("Top-rated", "Top-Rated Planner", "Rated 5 stars", "five-star reviews"),
)
def test_rating_language_in_a_name_is_refused(identity: str) -> None:
    _refuse(_bound("identity", identity))


def test_lookalike_tokens_are_refused() -> None:
    _refuse(_bound("identity", "\u0422\u043e\u0440 seller"))
    request = consistent_request()
    shop = "fieldnote \u0455\u04bb\u043e\u0440"
    broken = _with_fact_value(request, "shop_name", shop).model_copy(update={"shop_name": shop})
    _refuse(broken)


def test_secret_link_stays_on_the_notion_domain() -> None:
    request = consistent_request()
    refused = (
        "https://evil.example/checkout?ref=paid",
        "https://notion.site.evil.example/pay",
        "https://fixture.notion.site\u200b",
    )
    for value in refused:
        broken = _with_fact_value(request, "secret_links", value)
        with pytest.raises(MerchandisingInputError, match="secret_links"):
            merchandise(broken, _MustNotGenerate())
    notes = "https://notes.notion.so/fixture"
    copy = merchandise(_with_fact_value(request, "secret_links", notes))
    how = next(
        section for section in copy.draft.description_sections if section.role == "how_it_works"
    )
    assert notes in how.text
    _refuse(_bound("identity", "See https://evil.example/now"))
    _refuse(_bound("feature", "Visit www.evil.example today"))


@pytest.mark.parametrize(
    "phrase",
    (
        "Automated \u2717",
        "Automated \u2718",
        "Money-back \u2717",
        "Bank sync \u2717",
        "Auto-sync: \u2014",
        "5\u2605 reviews: \u2014",
        "Bestseller \u2718",
        "Customers love it \u2717",
    ),
)
def test_a_symbol_refuses_the_whole_tag(phrase: str) -> None:
    assert etsy_tag(phrase) == ""


@pytest.mark.parametrize(
    "phrase",
    ("-Bank sync", "- Bank sync", "Bank sync -", "Bank sync /", "+Bank sync", "|Bank sync"),
)
def test_an_end_separator_refuses_the_whole_tag(phrase: str) -> None:
    assert etsy_tag(phrase) == ""


def test_an_inner_hyphen_still_joins_tag_words() -> None:
    assert etsy_tag("Low-Spend Budget") == "low spend budget"
    assert etsy_tag("Planners & Organizers") == "planners organizers"


def test_dash_negated_feature_is_not_published_as_a_tag() -> None:
    features = (
        "Hyperlinked navigation",
        "Interactive checkboxes",
        "Monthly calendar views",
        "Weekly spread templates",
        "-Bank sync",
    )
    request = consistent_request(create_fixture_product_spec(features=features))
    copy = merchandise(request)
    assert "bank sync" not in {tag.text for tag in copy.draft.tags}
    assert tuple(tag.text for tag in copy.draft.tags) == _EXPECTED_TAGS


def test_negated_feature_is_not_published_as_a_short_tag() -> None:
    features = (
        "Hyperlinked navigation",
        "Interactive checkboxes",
        "Monthly calendar views",
        "Weekly spread templates",
        "Bank sync \u2717",
    )
    request = consistent_request(create_fixture_product_spec(features=features))
    copy = merchandise(request)
    assert tuple(tag.text for tag in copy.draft.tags) == _EXPECTED_TAGS
    section = next(item for item in copy.draft.description_sections if item.role == "features")
    assert "Bank sync \u2717" in section.text


def test_concealed_dashboard_and_support_are_refused() -> None:
    request = consistent_request()
    dashboard = request.notification_dashboard.model_copy(
        update={"outputs": ("Bestsel\u2060ler", "Reminder list")}
    )
    encoded = encode_dashboard(dashboard)
    hidden_dashboard = _with_fact_value(request, "dashboard_outputs", encoded).model_copy(
        update={"notification_dashboard": dashboard}
    )
    _refuse(hidden_dashboard)
    support = request.support.model_copy(update={"channel": "Trusted\u200b by Google"})
    hidden_support = _with_fact_value(request, "support", encode_support(support)).model_copy(
        update={"support": support}
    )
    _refuse(hidden_support)


class _DropColourGuard(ast.NodeTransformer):
    def __init__(self) -> None:
        self.hits = 0

    def visit_If(self, node: ast.If) -> ast.AST:
        test = node.test
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "colours"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.NotEq)
        ):
            self.hits += 1
            return ast.Pass()
        return self.generic_visit(node)


class _FactSourcedTrue(ast.NodeTransformer):
    def __init__(self) -> None:
        self.hits = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name == "_fact_sourced":
            self.hits += 1
            node.body = [ast.Return(value=ast.Constant(value=True))]
            return node
        return self.generic_visit(node)


class _DropFactGate(ast.NodeTransformer):
    def __init__(self) -> None:
        self.hits = 0

    def visit_If(self, node: ast.If) -> ast.AST:
        if _calls(node.test, "fact_text_problem"):
            self.hits += 1
            return ast.Pass()
        return self.generic_visit(node)


def _calls(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == name
        for child in ast.walk(node)
    )


def _load_module(tree: ast.AST, label: str) -> types.ModuleType:
    if not isinstance(tree, ast.Module):
        raise AssertionError(label)
    ast.fix_missing_locations(tree)
    module = types.ModuleType(label)
    module.__file__ = str(_AGENT)
    sys.modules[label] = module
    exec(compile(tree, str(_AGENT), "exec"), module.__dict__)
    return module


def test_midnight_black_needs_both_variant_guards() -> None:
    request = consistent_request()
    facts = tuple(
        fact.model_copy(update={"fact_value": f"{fact.fact_value}|Midnight Black"})
        if fact.fact_key == "colour_names"
        else fact
        for fact in request.facts
    )
    broken = request.model_copy(update={"facts": facts})
    with pytest.raises(MerchandisingInputError, match="colour"):
        merchandise(broken, _MustNotGenerate())

    colour_drop = _DropColourGuard()
    module = _load_module(
        colour_drop.visit(ast.parse(_AGENT.read_text(encoding="utf-8"))), "colour_guard"
    )
    assert colour_drop.hits == 1
    sourced = _FactSourcedTrue()
    validator_tree = sourced.visit(
        ast.parse(
            Path("src/money_machine/domain/services/claim_validation.py").read_text(
                encoding="utf-8"
            )
        )
    )
    assert sourced.hits == 1
    if not isinstance(validator_tree, ast.Module):
        raise AssertionError("sourced_true")
    ast.fix_missing_locations(validator_tree)
    validator = types.ModuleType("sourced_true")
    validator.__file__ = "src/money_machine/domain/services/claim_validation.py"
    sys.modules[validator.__name__] = validator
    exec(compile(validator_tree, validator.__file__, "exec"), validator.__dict__)
    module.__dict__["validate_claims"] = validator.__dict__["validate_claims"]
    copy = module.__dict__["merchandise"](broken)
    assert isinstance(copy, ListingCopy)
    shown = " ".join(section.text for section in copy.draft.description_sections)
    assert "Midnight Black" in shown
    assert any(tag.text == "midnight black" for tag in copy.draft.tags)


def test_deleting_the_fact_gate_generates_a_page_count() -> None:
    request = _bound("base_category", "200pp Planners")
    with pytest.raises(MerchandisingInputError, match="class claim"):
        merchandise(request, _MustNotGenerate())
    drop = _DropFactGate()
    module = _load_module(drop.visit(ast.parse(_AGENT.read_text(encoding="utf-8"))), "fact_gate")
    assert drop.hits == 1

    class _Called:
        def __init__(self) -> None:
            self.calls = 0

        def generate(
            self,
            request: MerchandisingInput,
            corrections: tuple[ClaimCorrection, ...],
        ) -> ListingDraft:
            self.calls += 1
            return module.__dict__["DeterministicCopyGenerator"]().generate(request, corrections)

    spy = _Called()
    with pytest.raises(module.__dict__["ClaimValidationClosed"]):
        module.__dict__["merchandise"](request, spy)
    assert spy.calls == MAX_CLAIM_ATTEMPTS
