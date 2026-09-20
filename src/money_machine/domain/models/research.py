"""Research domain models for market observations and candidate analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class ListingObservation:
    """One competitor listing observation with pricing and niche data."""

    source_reference: str
    title: str
    price: Decimal | None
    anchor_price: Decimal | None
    currency: str
    identity_niche: str | None
    base_category: str | None
    facts: dict[str, object]  # badges, urgency signals, reviews
    observed_at: datetime


@dataclass(frozen=True)
class ShopObservation:
    """One competitor shop observation with young-and-fast signals."""

    source_reference: str
    shop_reference: str
    shop_sales: int | None
    shop_opened_on: datetime | None
    badges: dict[str, bool]
    observed_at: datetime


@dataclass(frozen=True)
class ResearchReport:
    """Summary of one market research run with shortlist candidates."""

    research_run_id: UUID
    workflow_id: UUID
    job_id: UUID
    source_policy_version: str
    query_terms: list[str]
    observation_count: int
    listing_count: int
    shop_count: int
    listing_observations: list[ListingObservation]
    shop_observations: list[ShopObservation]
    shortlist: "ShortlistAnalysis"
    completed_at: datetime


@dataclass(frozen=True)
class CandidateProfile:
    """One shortlisted identityxcategory candidate with evidence."""

    identity: str
    base_category: str
    price_range: tuple[Decimal, Decimal]  # (min, max) observed prices
    observation_count: int
    shop_count: int
    young_fast_shop_count: int  # Shops < 12 months with > 400 sales
    risk_notes: str


@dataclass(frozen=True)
class ShortlistAnalysis:
    """Analysis results with top 5 candidates for qualification."""

    research_run_id: UUID
    workflow_id: UUID
    candidates: list[CandidateProfile]  # Top 5 by observation count + young-fast signals
    total_niches_found: int
    total_categories_found: int
    analyzed_at: datetime
