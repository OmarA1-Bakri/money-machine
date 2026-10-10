"""Probe strings are rejected on every buyer-facing surface."""

from __future__ import annotations

import pytest

from money_machine.agents.contracts.merchandising import ListingDraft, MerchandisingInput
from money_machine.agents.implementations.merchandising import DeterministicCopyGenerator
from money_machine.domain.services.claim_validation import validate_claims
from tests.fixtures.merchandising import consistent_request


def _request_and_draft() -> tuple[MerchandisingInput, ListingDraft]:
    request = consistent_request()
    return request, DeterministicCopyGenerator().generate(request, ())


_SURFACES = ("title", "section", "hero", "image", "video", "tag")
_PROBES = (
    "Includes an AI budget forecaster",
    "Includes an AI budget forecaster and Google Calendar sync.",
    "Features: Telepathy.",
    "Also available in Midnight Black.",
    "Variants: Sage Green, Navy Blue, Rose Gold, Midnight.",
    "AI Forecaster Planner",
    "Midnight Black Planner",
    "Includes 300 bonus templates and lifetime coaching.",
    "Includes AI assistant.",
    "ai assistant",
    "120-page",
    "200pp",
    "200+ pages",
    "One hundred pages",
    "two hundred pages",
    "A 200-page planner",
    "200 printable pages",
    "plus 100 bonus pages",
    "200 pp",
    "<b>200</b> pages",
    "200\u00a0pages",
    "**200** pages",
    "200-Page Planner",
    "Fully automated, runs unattended.",
    "Fully automated bank sync, runs unattended.",
    "Autofills your budget every month.",
    "Hands-free: set it and forget it.",
    "Recurring tasks update themselves.",
    "Auto\u2011fills",
    "\u0430utomated",
    "Over 10,000 five-star reviews.",
    "10,000 five-star reviews",
    "\u2605\u2605\u2605\u2605\u2605 rated 4.9/5",
    "Top-rated and highly reviewed.",
    "4.9 out of 5.",
    "Buyers rave about it.",
    "Rated five stars in 300 reviews!",
    "Etsy bestseller: 50,000 units sold.",
    "Bestseller: 10,000 sold.",
    "Best-selling planner on Etsy",
    "#1 top seller.",
    "Over 1,000+ sold.",
    "Sold 1,000 copies.",
    "10k downloads",
    "5k downloads",
    "B\u0435stseller",
    "Trusted by Google. As seen in Forbes. Money-back.",
    "Trusted by 50,000 teachers. As seen in Vogue.",
    "As seen on Forbes",
    "Featured in Vogue.",
    "Money back guarantee",
    "Money-back",
    "100% satisfaction guaranteed.",
    "Trusted-by 500 teams.",
    "Thousands of customers love this planner.",
    "1,000+ happy customers",
    "10,000+ happy customers",
    "Loved by thousands.",
    "Join 10,000 planners.",
    "Customers rave.",
    "A community of five thousand.",
    "Join 10,000+ happy planners",
)


def _paint(draft: ListingDraft, surface: str, text: str) -> ListingDraft:
    if surface == "title":
        return draft.model_copy(update={"title": draft.title.model_copy(update={"text": text})})
    if surface == "hero":
        updated = draft.hero_copy.model_copy(update={"text": text})
        return draft.model_copy(update={"hero_copy": updated})
    if surface == "section":
        section = draft.description_sections[4].model_copy(update={"text": text})
        sections = (
            *draft.description_sections[:4],
            section,
            *draft.description_sections[5:],
        )
        return draft.model_copy(update={"description_sections": sections})
    if surface == "image":
        line = draft.image_strip[0].model_copy(update={"text": text})
        return draft.model_copy(update={"image_strip": (line, *draft.image_strip[1:])})
    if surface == "video":
        beat = draft.video_sequence[0].model_copy(update={"text": text})
        return draft.model_copy(update={"video_sequence": (beat, *draft.video_sequence[1:])})
    if surface == "tag":
        tag = draft.tags[0].model_copy(update={"text": text})
        return draft.model_copy(update={"tags": (tag, *draft.tags[1:])})
    raise AssertionError(surface)


@pytest.mark.parametrize("surface", _SURFACES)
@pytest.mark.parametrize("probe", _PROBES)
def test_probe_string_is_rejected(surface: str, probe: str) -> None:
    request, draft = _request_and_draft()
    copy = _paint(draft, surface, probe)
    outcome = validate_claims(copy, request)
    assert outcome.passed is False
