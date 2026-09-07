"""Listing, listing-version and preflight access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from money_machine.persistence.repositories._base import Repository
from money_machine.persistence.tables import EtsyListing, ListingVersion, PreflightResult


class ListingRepository(Repository[EtsyListing]):
    """Marketplace listings across their versions."""

    model = EtsyListing

    async def for_product(self, product_id: UUID) -> tuple[EtsyListing, ...]:
        """Every listing created for one product."""
        statement = select(EtsyListing).where(EtsyListing.product_id == product_id)
        return tuple((await self.session.execute(statement)).scalars().all())


class ListingVersionRepository(Repository[ListingVersion]):
    """Immutable listing package versions."""

    model = ListingVersion

    async def current(self, listing_id: UUID) -> ListingVersion | None:
        """The highest version recorded for one listing."""
        statement = (
            select(ListingVersion)
            .where(ListingVersion.listing_id == listing_id)
            .order_by(ListingVersion.listing_version.desc())
            .limit(1)
        )
        return (await self.session.execute(statement)).scalars().one_or_none()


class PreflightResultRepository(Repository[PreflightResult]):
    """Launch-readiness verdicts pinned to a package hash."""

    model = PreflightResult

    async def for_listing_version(self, listing_version_id: UUID) -> tuple[PreflightResult, ...]:
        """Every preflight verdict for one listing version."""
        statement = (
            select(PreflightResult)
            .where(PreflightResult.listing_version_id == listing_version_id)
            .order_by(PreflightResult.completed_at)
        )
        return tuple((await self.session.execute(statement)).scalars().all())
