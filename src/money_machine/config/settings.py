"""Typed, fail-closed local operator settings."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Environment contract for local database and artifact operations only."""

    database_url: str
    config_root: Path
    artifact_root: Path
    worker_id: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        values = os.environ if environ is None else environ
        database_url = (
            values.get("MONEY_MACHINE_DATABASE_URL") or values.get("DATABASE_URL") or ""
        ).strip()
        if not database_url:
            raise ValueError("database URL is required")
        if not database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("database URL must use postgresql+asyncpg")

        repo_root = Path(__file__).resolve().parents[3]
        config_root = Path(values.get("MONEY_MACHINE_CONFIG_ROOT", repo_root / "config")).resolve()
        if not config_root.is_dir():
            raise ValueError("config root must be an existing directory")
        artifact_root = Path(
            values.get("MONEY_MACHINE_ARTIFACT_ROOT", repo_root / "runtime" / "artifacts")
        ).resolve()
        worker_id = values.get("MONEY_MACHINE_WORKER_ID", "local-operator-worker").strip()
        if not worker_id:
            raise ValueError("worker ID must not be empty")
        periodic = values.get("MONEY_MACHINE_PERIODIC_SCHEDULER_ENABLED", "false").casefold()
        if periodic not in {"", "0", "false", "no", "off", "disabled"}:
            raise ValueError("periodic scheduling is disabled for the first-product slice")
        return cls(
            database_url=database_url,
            config_root=config_root,
            artifact_root=artifact_root,
            worker_id=worker_id,
        )
