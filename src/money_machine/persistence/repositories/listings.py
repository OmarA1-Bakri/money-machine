"""Listing package and preflight repositories."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.models.listing import ListingPackage, PreflightResult
from money_machine.persistence.database import JsonModelRepository
from money_machine.persistence.tables import listing_packages, preflight_results


class ListingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._packages = JsonModelRepository(
            session, listing_packages, "listing_package_id", ListingPackage
        )
        self._preflight = JsonModelRepository(
            session, preflight_results, "preflight_result_id", PreflightResult
        )

    async def add_package(self, package: ListingPackage) -> None:
        await self._packages.add(
            package,
            identity=package.listing_package_id,
            extra_values={
                "product_spec_id": package.product_spec_id,
                "build_id": package.build_id,
            },
        )

    async def get_package(self, listing_package_id: str) -> ListingPackage | None:
        return await self._packages.get(listing_package_id)

    async def add_preflight(self, result: PreflightResult) -> None:
        await self._preflight.add(
            result,
            identity=result.preflight_result_id,
            extra_values={"listing_package_id": result.listing_package_id},
        )

    async def get_preflight(self, preflight_result_id: str) -> PreflightResult | None:
        return await self._preflight.get(preflight_result_id)
