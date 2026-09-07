"""Incident and customer-issue access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from money_machine.persistence.repositories._base import Repository
from money_machine.persistence.tables import CustomerIssue, Incident


class IncidentRepository(Repository[Incident]):
    """Operational incidents and their repair state."""

    model = Incident

    async def open_for_shop(self, shop_id: UUID) -> tuple[Incident, ...]:
        """Every unresolved incident in one shop, oldest first."""
        statement = (
            select(Incident)
            .where(Incident.shop_id == shop_id, Incident.incident_state != "RESOLVED")
            .order_by(Incident.opened_at)
        )
        return tuple((await self.session.execute(statement)).scalars().all())


class CustomerIssueRepository(Repository[CustomerIssue]):
    """Buyer-reported issues. Only safe references and summaries are stored."""

    model = CustomerIssue

    async def unanswered(self, shop_id: UUID) -> tuple[CustomerIssue, ...]:
        """Issues that have not yet been answered."""
        statement = (
            select(CustomerIssue)
            .where(CustomerIssue.shop_id == shop_id, CustomerIssue.answered_at.is_(None))
            .order_by(CustomerIssue.received_at)
        )
        return tuple((await self.session.execute(statement)).scalars().all())
