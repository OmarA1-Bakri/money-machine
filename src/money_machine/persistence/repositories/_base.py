"""Shared repository behaviour: typed reads, bounded pages, optimistic versioning."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from money_machine.persistence.tables import Identified, Versioned

MAX_PAGE_SIZE: Final = 200
"""No repository returns an unbounded result set."""


class ConcurrentModificationError(RuntimeError):
    """Raised when an optimistic version check loses a race."""


def _as_concurrent_error(
    error: Exception,
    table: str,
    identifier: object,
) -> ConcurrentModificationError:
    """Present SQLAlchemy's stale-data failure as this layer's typed error."""
    return ConcurrentModificationError(f"{table} {identifier} was modified concurrently: {error}")


class Page[RowT]:
    """One bounded page of rows plus the total count of matching rows."""

    __slots__ = ("items", "limit", "offset", "total")

    def __init__(self, items: Sequence[RowT], total: int, limit: int, offset: int) -> None:
        self.items = tuple(items)
        self.total = total
        self.limit = limit
        self.offset = offset

    @property
    def has_more(self) -> bool:
        """Whether more rows match beyond this page."""
        return self.offset + len(self.items) < self.total


class Repository[ModelT: Identified]:
    """Typed data access for one table. Repositories never commit."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, instance: ModelT) -> ModelT:
        """Stage a new row. Nothing is written until the unit of work commits."""
        self.session.add(instance)
        return instance

    async def get(self, identifier: UUID) -> ModelT | None:
        """Fetch one row by primary key."""
        return await self.session.get(self.model, identifier)

    async def require(self, identifier: UUID) -> ModelT:
        """Fetch one row by primary key, refusing a missing row."""
        found = await self.get(identifier)
        if found is None:
            raise LookupError(f"{self.model.__tablename__} {identifier} does not exist")
        return found

    async def count(self, *criteria: Any) -> int:
        """Count matching rows."""
        statement = select(func.count()).select_from(self.model)
        if criteria:
            statement = statement.where(*criteria)
        return int((await self.session.execute(statement)).scalar_one())

    async def page(
        self,
        *criteria: Any,
        limit: int = 50,
        offset: int = 0,
        order_by: Any | None = None,
    ) -> Page[ModelT]:
        """Return one bounded page, with the total count of matching rows."""
        if limit < 1 or limit > MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}")
        if offset < 0:
            raise ValueError("offset must not be negative")
        statement: Select[tuple[ModelT]] = select(self.model)
        if criteria:
            statement = statement.where(*criteria)
        statement = statement.order_by(order_by if order_by is not None else self.model.id)
        rows = (await self.session.execute(statement.limit(limit).offset(offset))).scalars().all()
        return Page(rows, await self.count(*criteria), limit, offset)


class VersionedRepository[ModelT: Versioned](Repository[ModelT]):
    """A repository whose rows carry an integer ``version`` for optimistic concurrency."""

    async def update_versioned(
        self,
        instance: ModelT,
        expected_version: int,
        **changes: Any,
    ) -> ModelT:
        """Apply changes only if the row still holds ``expected_version``.

        The in-memory comparison catches a stale caller cheaply. The real guard is the
        mapper's ``version_id_col``: the emitted UPDATE carries ``WHERE version = :old``
        and SQLAlchemy increments the version itself, so a writer whose row was changed by
        another transaction raises instead of silently overwriting it.
        """
        current = instance.version
        # Read the identifier now: after a failed flush the instance's attributes are
        # expired, and touching one would re-query a session that must be rolled back.
        identifier = instance.id
        if current != expected_version:
            raise ConcurrentModificationError(
                f"{self.model.__tablename__} {identifier} moved from version "
                f"{expected_version} to {current}"
            )
        for field, value in changes.items():
            setattr(instance, field, value)
        try:
            await self.session.flush()
        except StaleDataError as error:
            raise _as_concurrent_error(error, self.model.__tablename__, identifier) from error
        return instance
