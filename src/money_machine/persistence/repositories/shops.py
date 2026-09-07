"""Shop and integration-account access."""

from __future__ import annotations

from sqlalchemy import select

from money_machine.persistence.repositories._base import Repository
from money_machine.persistence.tables import IntegrationAccount, Shop


class ShopRepository(Repository[Shop]):
    """Shops, addressed by their unique name."""

    model = Shop

    async def by_name(self, name: str) -> Shop | None:
        """Fetch one shop by its unique name."""
        statement = select(Shop).where(Shop.name == name)
        return (await self.session.execute(statement)).scalars().one_or_none()

    async def active(self) -> tuple[Shop, ...]:
        """Every shop that has not been soft deactivated."""
        statement = select(Shop).where(Shop.active).order_by(Shop.name)
        return tuple((await self.session.execute(statement)).scalars().all())


class IntegrationAccountRepository(Repository[IntegrationAccount]):
    """Provider readiness records. Credential values are never stored or returned."""

    model = IntegrationAccount

    async def for_shop(self, shop_id: object) -> tuple[IntegrationAccount, ...]:
        """Every provider readiness record for one shop, in provider order."""
        statement = (
            select(IntegrationAccount)
            .where(IntegrationAccount.shop_id == shop_id)
            .order_by(IntegrationAccount.provider)
        )
        return tuple((await self.session.execute(statement)).scalars().all())
