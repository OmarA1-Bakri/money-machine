"""Database-backed read dependencies for the operator API."""

from collections.abc import AsyncIterator

from fastapi import Request

from money_machine.persistence.database import Database
from money_machine.persistence.unit_of_work import UnitOfWork


def get_database(request: Request) -> Database:
    database = getattr(request.app.state, "database", None)
    if not isinstance(database, Database):
        raise RuntimeError("API database is not initialized")
    return database


async def get_unit_of_work(request: Request) -> AsyncIterator[UnitOfWork]:
    async with UnitOfWork(get_database(request)) as uow:
        yield uow
