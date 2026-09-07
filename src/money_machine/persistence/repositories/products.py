"""Product, specification and dedupe access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from money_machine.persistence.repositories._base import Repository
from money_machine.persistence.tables import DedupeResult, Product, ProductSpec


class ProductRepository(Repository[Product]):
    """Products, soft deactivated rather than deleted."""

    model = Product

    async def active_for_shop(self, shop_id: UUID) -> tuple[Product, ...]:
        """Every active product in one shop."""
        statement = (
            select(Product)
            .where(Product.shop_id == shop_id, Product.active)
            .order_by(Product.created_at)
        )
        return tuple((await self.session.execute(statement)).scalars().all())


class ProductSpecRepository(Repository[ProductSpec]):
    """Immutable specification versions."""

    model = ProductSpec

    async def current(self, product_id: UUID) -> ProductSpec | None:
        """The highest specification version for one product."""
        statement = (
            select(ProductSpec)
            .where(ProductSpec.product_id == product_id)
            .order_by(ProductSpec.version.desc())
            .limit(1)
        )
        return (await self.session.execute(statement)).scalars().one_or_none()

    async def by_fingerprint(self, fingerprint: str) -> tuple[ProductSpec, ...]:
        """Every specification sharing one concept fingerprint, for dedupe."""
        statement = select(ProductSpec).where(ProductSpec.concept_fingerprint == fingerprint)
        return tuple((await self.session.execute(statement)).scalars().all())


class DedupeResultRepository(Repository[DedupeResult]):
    """Dedupe verdicts and the catalogue each one compared."""

    model = DedupeResult

    async def for_spec(self, spec_id: UUID) -> tuple[DedupeResult, ...]:
        """Every dedupe verdict recorded against one specification."""
        statement = (
            select(DedupeResult)
            .where(DedupeResult.spec_id == spec_id)
            .order_by(DedupeResult.completed_at)
        )
        return tuple((await self.session.execute(statement)).scalars().all())
