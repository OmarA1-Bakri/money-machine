"""Etsy research adapters for market research observations.

This module provides adapters for extracting Etsy product listing data:
- EtsyFixtureAdapter: Loads synthetic search results from test fixtures (primary, safe for CI)
- EtsyBrowserAdapter: Playwright-based scraper (stub, NOT IMPLEMENTED)
- EtsyAPIAdapter: Direct Etsy API client (stub, NOT IMPLEMENTED)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field


class EtsyResearchObservation(BaseModel):
    """A single Etsy listing observation from market research.

    Captures thin evidence from search results without invented metrics.
    All fields are required for fixture path; live adapters may return None
    where data is unavailable.
    """

    search_phrase: str = Field(description="The search phrase that surfaced this listing")
    rank: int = Field(description="Position in search results (1-indexed)")
    title: str = Field(description="Listing title as displayed")
    current_price_cents: int = Field(description="Current price in cents (USD)")
    anchor_price_cents: int | None = Field(
        default=None,
        description="Crossed-out/original price in cents, if shown",
    )
    shop_name: str = Field(description="Etsy shop name")
    shop_sales_count: int | None = Field(
        default=None,
        description="Total shop sales if visible",
    )
    shop_age_years: int | None = Field(
        default=None,
        description="Approximate shop age in years if calculable",
    )
    badges: list[str] = Field(
        default_factory=list,
        description="Badges like 'Star Seller', 'Best Selling', 'Fast Shipping'",
    )
    urgency_signals: list[str] = Field(
        default_factory=list,
        description="Urgency/scarcity signals like 'Only 3 left', 'In 12 carts'",
    )
    review_count: int | None = Field(
        default=None,
        description="Number of reviews if visible",
    )
    identity_niche: str = Field(
        description="Identified product niche (e.g., 'productivity digital downloads')"
    )
    base_category: str = Field(description="Etsy base category (e.g., 'Office & School Supplies')")
    listing_url: str = Field(description="Full Etsy listing URL")
    evidence_timestamp: datetime = Field(description="UTC timestamp when observation was captured")

    class Config:
        frozen = True


class EtsyResearchAdapter(Protocol):
    """Protocol for Etsy research data sources."""

    def search(
        self,
        phrase: str,
        target_count: int = 30,
    ) -> list[EtsyResearchObservation]:
        """Execute a search and return observations.

        Args:
            phrase: Search phrase (e.g., "digital planner")
            target_count: Target number of observations to return

        Returns:
            List of observations, up to target_count

        Raises:
            NotImplementedError: For stub adapters not yet implemented
            ValueError: For invalid search phrase or target_count
        """
        ...


class EtsyFixtureAdapter:
    """Loads synthetic Etsy search results from test fixtures.
    
    Safe for CI; no external calls. Primary adapter for development and testing.
    Fixture data must be at tests/fixtures/etsy_search_results.json.
    """

    def __init__(self, fixture_path: Path | None = None) -> None:
        """Initialize fixture adapter.
        
        Args:
            fixture_path: Path to fixture JSON file. Defaults to
                tests/fixtures/etsy_search_results.json relative to repo root.
        """
        self.fixture_path = fixture_path

    def search(
        self,
        phrase: str,
        target_count: int = 30,
    ) -> list[EtsyResearchObservation]:
        """Load observations from fixture file.
        
        Args:
            phrase: Search phrase to look up in fixtures
            target_count: Maximum observations to return
            
        Returns:
            List of synthetic observations for the phrase
            
        Raises:
            FileNotFoundError: If fixture file doesn't exist
            KeyError: If phrase not found in fixtures
            ValueError: If fixture data is malformed
        """
        import json

        # Default fixture path relative to repo root
        if self.fixture_path is None:
            # Find repo root by looking for .git directory
            current = Path(__file__).resolve()
            while current != current.parent:
                if (current / ".git").exists():
                    self.fixture_path = current / "tests" / "fixtures" / "etsy_search_results.json"
                    break
                current = current.parent
            else:
                raise FileNotFoundError(
                    "Could not find repo root; provide fixture_path explicitly"
                )

        if not self.fixture_path.exists():
            raise FileNotFoundError(f"Fixture file not found: {self.fixture_path}")

        with self.fixture_path.open() as f:
            fixtures = json.load(f)

        if phrase not in fixtures:
            raise KeyError(f"Phrase '{phrase}' not found in fixtures")

        raw_observations = fixtures[phrase]
        if not isinstance(raw_observations, list):
            raise ValueError(f"Fixture data for '{phrase}' must be a list")

        observations = [
            EtsyResearchObservation(
                search_phrase=phrase,
                rank=obs["rank"],
                title=obs["title"],
                current_price_cents=obs["current_price_cents"],
                anchor_price_cents=obs.get("anchor_price_cents"),
                shop_name=obs["shop_name"],
                shop_sales_count=obs.get("shop_sales_count"),
                shop_age_years=obs.get("shop_age_years"),
                badges=obs.get("badges", []),
                urgency_signals=obs.get("urgency_signals", []),
                review_count=obs.get("review_count"),
                identity_niche=obs["identity_niche"],
                base_category=obs["base_category"],
                listing_url=obs["listing_url"],
                evidence_timestamp=datetime.fromisoformat(obs["search_timestamp"]),
            )
            for obs in raw_observations[:target_count]
        ]

        return observations


class EtsyBrowserAdapter:
    """Playwright-based Etsy search scraper.

    NOT IMPLEMENTED. Raises NotImplementedError on all methods.
    Future implementation will use Playwright to scrape Etsy search results.
    """

    def search(
        self,
        phrase: str,
        target_count: int = 30,
    ) -> list[EtsyResearchObservation]:
        """Browser-based scraping not yet implemented.

        Raises:
            NotImplementedError: Always; this adapter is a stub
        """
        raise NotImplementedError(
            "Browser adapter not yet implemented; use EtsyFixtureAdapter for development"
        )


class EtsyAPIAdapter:
    """Etsy API client for research data.

    NOT IMPLEMENTED. Raises NotImplementedError on all methods.
    Future implementation will use Etsy's official API endpoints.
    Requires API key and may incur costs.
    """

    def search(
        self,
        phrase: str,
        target_count: int = 30,
    ) -> list[EtsyResearchObservation]:
        """API-based search not yet implemented.

        Raises:
            NotImplementedError: Always; this adapter is a stub
        """
        raise NotImplementedError(
            "Etsy API adapter not yet implemented; use EtsyFixtureAdapter for development"
        )


def get_research_adapter(mode: str = "fixture") -> EtsyResearchAdapter:
    """Get an Etsy research adapter instance.

    Args:
        mode: Adapter mode - "fixture", "browser", or "api"

    Returns:
        Configured adapter instance

    Raises:
        ValueError: If mode is not recognized
    """
    if mode == "fixture":
        return EtsyFixtureAdapter()
    elif mode == "browser":
        return EtsyBrowserAdapter()
    elif mode == "api":
        return EtsyAPIAdapter()
    else:
        raise ValueError(f"Unknown adapter mode: {mode}. Must be 'fixture', 'browser', or 'api'")
