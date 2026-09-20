"""Etsy integration interface for market research and publishing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class EtsyListingSearchResult:
    """One listing observation from Etsy search results."""

    source_reference: str  # URL or unique identifier
    title: str
    price: Decimal | None
    anchor_price: Decimal | None  # Crossed-out price if present
    currency: str
    shop_reference: str
    shop_sales: int | None
    shop_opened_on: datetime | None
    identity_niche: str | None
    base_category: str | None
    badges: dict[str, bool]  # e.g. {"bestseller": True, "star_seller": False}
    urgency_signals: dict[str, str]  # e.g. {"in_carts": "20+ people have this in cart"}
    review_count: int | None
    review_average: Decimal | None
    observed_at: datetime


class EtsyResearchAdapter(Protocol):
    """Protocol for Etsy market research adapters."""

    async def search_listings(
        self, query: str, max_results: int = 50
    ) -> list[EtsyListingSearchResult]:
        """
        Search Etsy for listings matching the query.

        Args:
            query: Search phrase (e.g., "planner stickers")
            max_results: Maximum number of results to return

        Returns:
            List of listing observations with shop and pricing data

        Raises:
            NotImplementedError: If adapter is not commissioned for production use
        """
        ...
