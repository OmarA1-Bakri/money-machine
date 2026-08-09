"""Async PostgreSQL engine and session factory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from money_machine.domain.value_objects import canonical_json, canonical_sha256


@dataclass(frozen=True, slots=True)
class Database:
    """One durable async database boundary."""

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    @classmethod
    def from_url(cls, url: str) -> Database:
        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError("database URL must use postgresql+asyncpg")
        engine = create_async_engine(url, pool_pre_ping=True)
        return cls(
            engine=engine,
            session_factory=async_sessionmaker(engine, expire_on_commit=False),
        )

    async def dispose(self) -> None:
        await self.engine.dispose()


class JsonModelRepository[ModelT: BaseModel]:
    """Internal typed JSON repository; application code sees domain-specific wrappers."""

    def __init__(
        self,
        session: AsyncSession,
        table: Table,
        identity_column: str,
        model_type: type[ModelT],
    ) -> None:
        self._session = session
        self._table = table
        self._identity_column = identity_column
        self._model_type = model_type

    async def add(
        self,
        model: ModelT,
        *,
        identity: str | UUID,
        extra_values: dict[str, object] | None = None,
    ) -> None:
        payload_bytes = canonical_json(model)
        payload_hash = canonical_sha256(model)
        values: dict[str, object] = {
            self._identity_column: identity,
            "payload": json.loads(payload_bytes),
            "payload_sha256": payload_hash,
        }
        if extra_values:
            values.update(extra_values)
        inserted_hash = (
            await self._session.execute(
                pg_insert(self._table)
                .values(**values)
                .on_conflict_do_nothing(index_elements=[self._table.c[self._identity_column]])
                .returning(self._table.c.payload_sha256)
            )
        ).scalar_one_or_none()
        if inserted_hash is not None:
            return
        existing_hash = await self._session.scalar(
            select(self._table.c.payload_sha256).where(
                self._table.c[self._identity_column] == identity
            )
        )
        if existing_hash != payload_hash:
            raise ValueError(f"identity collision for {identity}")

    async def get(self, identity: str | UUID) -> ModelT | None:
        result = await self._session.execute(
            select(self._table.c.payload).where(self._table.c[self._identity_column] == identity)
        )
        payload = result.scalar_one_or_none()
        return (
            None
            if payload is None
            else self._model_type.model_validate_json(json.dumps(payload, separators=(",", ":")))
        )
