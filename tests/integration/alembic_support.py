"""Alembic helpers usable from tests and fixtures."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def run_alembic(command_name: str, revision: str, url: str, repository_root: Path) -> None:
    """Run one Alembic command against an explicit URL, off the event loop."""
    from alembic import command
    from alembic.config import Config

    def invoke() -> None:
        config = Config(str(repository_root / "alembic.ini"))
        config.set_main_option("script_location", str(repository_root / "migrations"))
        config.set_main_option("sqlalchemy.url", url)
        getattr(command, command_name)(config, revision)

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(invoke).result()


def upgrade(url: str, repository_root: Path, revision: str = "head") -> None:
    """Apply migrations up to a revision."""
    run_alembic("upgrade", revision, url, repository_root)


def downgrade(url: str, repository_root: Path, revision: str = "base") -> None:
    """Reverse migrations down to a revision."""
    run_alembic("downgrade", revision, url, repository_root)
