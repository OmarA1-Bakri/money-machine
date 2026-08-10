"""Explicit local database migration command."""

from pathlib import Path

import typer
from alembic import command
from alembic.config import Config

from money_machine.cli.support import emit, settings_or_exit

app = typer.Typer(no_args_is_help=True)


@app.command("migrate")
def migrate(json_output: bool = typer.Option(False, "--json")) -> None:
    del json_output
    settings = settings_or_exit()
    repo_root = Path(__file__).resolve().parents[4]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
    emit(
        {
            "status": "migrated",
            "revision": "head",
            "external_mutations": 0,
            "spend_usd": "0.00",
        }
    )
