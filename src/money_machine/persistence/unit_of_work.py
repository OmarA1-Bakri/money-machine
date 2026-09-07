"""Transactional unit of work over the repository set."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from money_machine.persistence.repositories.agents import (
    AgentDefinitionRepository,
    AgentRunRepository,
)
from money_machine.persistence.repositories.artifacts import ArtifactRepository, ReceiptRepository
from money_machine.persistence.repositories.events import EventRepository, IdempotencyRepository
from money_machine.persistence.repositories.jobs import JobRepository
from money_machine.persistence.repositories.products import ProductRepository, ProductSpecRepository
from money_machine.persistence.repositories.shops import ShopRepository
from money_machine.persistence.repositories.workflows import WorkflowRunRepository


class UnitOfWork:
    """One transaction spanning every repository.

    Nothing commits until :meth:`commit` is called, and leaving the context without a
    commit rolls back. Repositories never commit on their own.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.shops = ShopRepository(session)
        self.workflows = WorkflowRunRepository(session)
        self.jobs = JobRepository(session)
        self.events = EventRepository(session)
        self.idempotency = IdempotencyRepository(session)
        self.agent_definitions = AgentDefinitionRepository(session)
        self.agent_runs = AgentRunRepository(session)
        self.artifacts = ArtifactRepository(session)
        self.receipts = ReceiptRepository(session)
        self.products = ProductRepository(session)
        self.product_specs = ProductSpecRepository(session)

    async def commit(self) -> None:
        """Commit the transaction."""
        await self.session.commit()

    async def rollback(self) -> None:
        """Discard the transaction."""
        await self.session.rollback()

    async def flush(self) -> None:
        """Send pending statements without committing, to surface constraint errors."""
        await self.session.flush()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc, traceback
        if exc_type is not None:
            await self.rollback()


@asynccontextmanager
async def unit_of_work(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[UnitOfWork]:
    """Open a unit of work bound to a fresh session."""
    session = factory()
    try:
        async with UnitOfWork(session) as work:
            yield work
    finally:
        await session.close()
