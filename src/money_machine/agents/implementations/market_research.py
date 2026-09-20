"""A03 Market Research Agent - collect and analyze Etsy market observations."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import yaml

from money_machine.domain.models.research import (
    CandidateProfile,
    ListingObservation,
    ResearchReport,
    ShopObservation,
    ShortlistAnalysis,
)
from money_machine.integrations.etsy.fixture_adapter import FixtureEtsyAdapter
from money_machine.integrations.etsy.interface import (
    EtsyListingSearchResult,
    EtsyResearchAdapter,
)
from money_machine.persistence.repositories.research import (
    ProductCandidateRepository,
    ResearchRunRepository,
)
from money_machine.persistence.tables import (
    MarketListingObservation,
    MarketShopObservation,
    ProductCandidate,
    ResearchRun,
)
from money_machine.persistence.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from money_machine.persistence.tables import Job

logger = logging.getLogger(__name__)


class MarketResearchAgent:
    """
    A03 Market Research Agent.

    Executes market research searches, collects observations,
    and generates shortlist candidates for qualification.
    """

    def __init__(
        self,
        adapter: EtsyResearchAdapter | None = None,
        config_path: Path | None = None,
    ) -> None:
        """
        Initialize the market research agent.

        Args:
            adapter: Etsy research adapter (defaults to fixture adapter)
            config_path: Path to research.yaml config (defaults to config/research.yaml)
        """
        self.adapter = adapter or FixtureEtsyAdapter()
        self.config_path = config_path or Path("config/research.yaml")
        self._config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Load research configuration from YAML."""
        if not self.config_path.exists():
            raise ValueError(f"Research config not found: {self.config_path}")

        with open(self.config_path, encoding="utf-8") as file:
            config = yaml.safe_load(file)

        if not config or "research" not in config:
            raise ValueError(
                f"Invalid research config: missing 'research' key in {self.config_path}"
            )

        return config["research"]

    def _validate_seed_phrases(self) -> list[str]:
        """
        Validate and return seed phrases from configuration.

        Raises:
            ValueError: If no seed phrases are configured
        """
        seed_phrases: list[str] = self._config.get("seed_phrases", [])
        if not seed_phrases:
            raise ValueError("No seed phrases configured for market research")

        return seed_phrases

    async def execute(
        self,
        workflow_id: UUID,
        job: Job,
        uow: UnitOfWork,
    ) -> ResearchReport:
        """
        Execute market research for the workflow.

        Args:
            workflow_id: Workflow this research belongs to
            job: Market research job being executed
            uow: Unit of work for database persistence

        Returns:
            ResearchReport with observations and shortlist

        Raises:
            ValueError: If seed phrases are missing or adapter is unavailable
            NotImplementedError: If non-fixture adapter is used while uncommissioned
        """
        # Fail-closed: only fixture adapter is allowed for uncommissioned agent
        if not isinstance(self.adapter, FixtureEtsyAdapter):
            raise NotImplementedError(
                "Only fixture adapter supported in wave 01. "
                "Browser and API adapters require commissioning approval."
            )

        seed_phrases = self._validate_seed_phrases()
        target_count: int = self._config.get("target_observation_count", 30)
        max_per_query: int = self._config.get("max_results_per_query", 50)
        source_policy_version: str = self._config.get("source_policy_version", "v1.0")

        logger.info(
            f"Starting market research for workflow {workflow_id} "
            f"with {len(seed_phrases)} seed phrases"
        )

        # Create research run record
        research_run = ResearchRun(
            id=None,  # type: ignore[arg-type]
            workflow_id=workflow_id,
            job_id=job.id,  # type: ignore[arg-type]
            source_policy_version=source_policy_version,
            query_terms=seed_phrases,
            observation_count=0,
            completed_at=None,
            created_at=datetime.now(UTC),
        )

        async with uow:
            research_run_repo = ResearchRunRepository(uow.session)
            research_run = research_run_repo.add(research_run)
            await uow.commit()

        # Collect observations from all seed phrases
        all_listing_results: list[EtsyListingSearchResult] = []
        seen_references: set[str] = set()

        for phrase in seed_phrases:
            try:
                results = await self.adapter.search_listings(phrase, max_results=max_per_query)
                logger.info(f"Query '{phrase}' returned {len(results)} results")

                # Dedupe by source reference
                for result in results:
                    if result.source_reference not in seen_references:
                        all_listing_results.append(result)
                        seen_references.add(result.source_reference)

                # Stop if we've hit target
                if len(all_listing_results) >= target_count:
                    break

            except Exception as e:
                logger.warning(f"Search failed for phrase '{phrase}': {e}")
                continue

        logger.info(f"Collected {len(all_listing_results)} unique observations")

        # Persist observations
        listing_observations: list[ListingObservation] = []
        shop_observations: list[ShopObservation] = []
        shop_references_seen = set()

        async with uow:
            for result in all_listing_results:
                # Create listing observation
                listing_obs = MarketListingObservation(
                    id=None,  # type: ignore[arg-type]
                    research_run_id=research_run.id,  # type: ignore[arg-type]
                    source_reference=result.source_reference,
                    title=result.title,
                    price=result.price,
                    anchor_price=result.anchor_price,
                    currency=result.currency,
                    identity_niche=result.identity_niche,
                    base_category=result.base_category,
                    facts={
                        "badges": result.badges,
                        "urgency_signals": result.urgency_signals,
                        "review_count": result.review_count,
                        "review_average": float(result.review_average)
                        if result.review_average
                        else None,
                    },
                    observed_at=result.observed_at,
                )
                uow.session.add(listing_obs)

                listing_observations.append(
                    ListingObservation(
                        source_reference=result.source_reference,
                        title=result.title,
                        price=result.price,
                        anchor_price=result.anchor_price,
                        currency=result.currency,
                        identity_niche=result.identity_niche,
                        base_category=result.base_category,
                        facts=listing_obs.facts,
                        observed_at=result.observed_at,
                    )
                )

                # Create shop observation (dedupe by shop reference)
                if result.shop_reference not in shop_references_seen:
                    shop_obs = MarketShopObservation(
                        id=None,  # type: ignore[arg-type]
                        research_run_id=research_run.id,  # type: ignore[arg-type]
                        source_reference=result.source_reference,
                        shop_reference=result.shop_reference,
                        shop_sales=result.shop_sales,
                        shop_opened_on=result.shop_opened_on,
                        badges=result.badges,
                        observed_at=result.observed_at,
                    )
                    uow.session.add(shop_obs)
                    shop_references_seen.add(result.shop_reference)

                    shop_observations.append(
                        ShopObservation(
                            source_reference=result.source_reference,
                            shop_reference=result.shop_reference,
                            shop_sales=result.shop_sales,
                            shop_opened_on=result.shop_opened_on,
                            badges=result.badges,
                            observed_at=result.observed_at,
                        )
                    )

            # Update research run with completion
            research_run.observation_count = len(listing_observations)
            research_run.completed_at = datetime.now(UTC)
            uow.session.add(research_run)

            await uow.commit()

        logger.info(
            f"Persisted {len(listing_observations)} listing observations "
            f"and {len(shop_observations)} shop observations"
        )

        # Generate shortlist analysis
        shortlist = await self._generate_shortlist(
            research_run_id=research_run.id,  # type: ignore[arg-type]
            workflow_id=workflow_id,
            listing_observations=listing_observations,
            shop_observations=shop_observations,
            uow=uow,
        )

        logger.info(f"Generated shortlist with {len(shortlist.candidates)} candidates")

        return ResearchReport(
            research_run_id=research_run.id,  # type: ignore[arg-type]
            workflow_id=workflow_id,
            job_id=job.id,  # type: ignore[arg-type]
            source_policy_version=source_policy_version,
            query_terms=seed_phrases,
            observation_count=len(listing_observations),
            listing_observations=listing_observations,
            shop_observations=shop_observations,
            completed_at=research_run.completed_at,  # type: ignore[arg-type]
        )

    async def _generate_shortlist(
        self,
        research_run_id: UUID,
        workflow_id: UUID,
        listing_observations: list[ListingObservation],
        shop_observations: list[ShopObservation],
        uow: UnitOfWork,
    ) -> ShortlistAnalysis:
        """
        Analyze observations and generate top 5 candidates.

        Candidates are ranked by:
        1. Number of observations (popularity signal)
        2. Young-and-fast shop presence
        3. Price band diversity
        """
        # Group by identity x category
        niche_category_groups: dict[tuple[str, str], list[ListingObservation]] = defaultdict(list)

        for obs in listing_observations:
            if obs.identity_niche and obs.base_category:
                key = (obs.identity_niche, obs.base_category)
                niche_category_groups[key].append(obs)

        # Build shop lookup for young-and-fast analysis
        shop_lookup = {shop.shop_reference: shop for shop in shop_observations}
        young_shop_age_days = self._config.get("young_shop_age_days", 365)
        fast_shop_sales_threshold = self._config.get("fast_shop_sales_threshold", 400)

        cutoff_date = datetime.now(UTC) - timedelta(days=young_shop_age_days)

        # Score each niche x category combination
        candidate_scores: list[tuple[CandidateProfile, float]] = []

        for (identity, category), observations in niche_category_groups.items():
            # Extract price range
            prices = [obs.price for obs in observations if obs.price is not None]
            if not prices:
                continue

            price_range = (min(prices), max(prices))

            # Count shops and young-fast shops
            shop_refs = {
                obs.source_reference.split("/")[-1] for obs in observations
            }  # Simplified shop extraction
            shops = [shop_lookup.get(ref) for ref in shop_refs if ref in shop_lookup]
            shop_count = len([s for s in shops if s is not None])

            young_fast_count = sum(
                1
                for shop in shops
                if shop
                and shop.shop_opened_on
                and shop.shop_opened_on >= cutoff_date
                and shop.shop_sales
                and shop.shop_sales >= fast_shop_sales_threshold
            )

            # Generate risk note based on observations
            risk_notes = []
            if young_fast_count == 0:
                risk_notes.append("No young-and-fast shops observed")
            if price_range[1] > Decimal("15.00"):
                risk_notes.append("High price point may reduce impulse purchases")
            if len(observations) < 5:
                risk_notes.append("Limited market evidence (< 5 observations)")

            risk_note = "; ".join(risk_notes) if risk_notes else "No significant risks identified"

            # Score: observation count + young-fast bonus
            score = len(observations) + (young_fast_count * 2)

            candidate_scores.append(
                (
                    CandidateProfile(
                        identity=identity,
                        base_category=category,
                        price_range=price_range,
                        observation_count=len(observations),
                        shop_count=shop_count,
                        young_fast_shop_count=young_fast_count,
                        risk_notes=risk_note,
                    ),
                    score,
                )
            )

        # Select top 5 candidates
        candidate_scores.sort(key=lambda x: x[1], reverse=True)
        shortlist_size = self._config.get("shortlist_size", 5)
        top_candidates = [profile for profile, _ in candidate_scores[:shortlist_size]]

        # Persist candidates
        async with uow:
            candidate_repo = ProductCandidateRepository(uow.session)
            for candidate in top_candidates:
                db_candidate = ProductCandidate(
                    id=None,  # type: ignore[arg-type]
                    workflow_id=workflow_id,
                    research_run_id=research_run_id,
                    identity=candidate.identity,
                    base_category=candidate.base_category,
                    impulse_priced_score=None,  # Scored by A05
                    tangible_score=None,
                    honest_promise_score=None,
                    trendy_but_tricky_score=None,
                    total_score=None,
                    maximum_score=None,
                    selection=None,
                    created_at=datetime.now(UTC),
                )
                candidate_repo.add(db_candidate)

            await uow.commit()

        total_niches = len({identity for identity, _ in niche_category_groups})
        total_categories = len({category for _, category in niche_category_groups})

        return ShortlistAnalysis(
            research_run_id=research_run_id,
            workflow_id=workflow_id,
            candidates=top_candidates,
            total_niches_found=total_niches,
            total_categories_found=total_categories,
            analyzed_at=datetime.now(UTC),
        )
