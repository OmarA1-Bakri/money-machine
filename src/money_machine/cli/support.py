"""Shared local CLI composition and machine-readable output."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from typing import Any, NoReturn

import typer
from alembic.util.exc import CommandError
from sqlalchemy.exc import SQLAlchemyError

from money_machine.config.settings import Settings


def emit(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


def fail(code: str, message: str, *, exit_code: int = 2) -> NoReturn:
    emit({"error": {"code": code, "message": message}})
    raise typer.Exit(exit_code)


def settings_or_exit() -> Settings:
    try:
        return Settings.from_env()
    except ValueError as exc:
        fail("CONFIGURATION_ERROR", str(exc))


def call[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except typer.Exit:
        raise
    except CommandError:
        fail("MIGRATION_ERROR", "database migration failed", exit_code=1)
    except SQLAlchemyError:
        fail("DATABASE_ERROR", "database operation failed", exit_code=1)
    except (OSError, RuntimeError, ValueError) as exc:
        fail(type(exc).__name__.upper(), str(exc), exit_code=1)


def run[T](awaitable: Coroutine[Any, Any, T]) -> T:
    try:
        return asyncio.run(awaitable)
    except typer.Exit:
        raise
    except SQLAlchemyError:
        fail("DATABASE_ERROR", "database operation failed", exit_code=1)
    except (OSError, RuntimeError, ValueError) as exc:
        fail(type(exc).__name__.upper(), str(exc), exit_code=1)
