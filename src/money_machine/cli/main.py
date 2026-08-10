"""Bounded local operator CLI for the first-product slice."""

from __future__ import annotations

import typer

from money_machine.cli.commands.artifacts import app as artifacts_app
from money_machine.cli.commands.database import app as database_app
from money_machine.cli.commands.research import app as research_app
from money_machine.cli.commands.scheduler import app as scheduler_app
from money_machine.cli.commands.worker import app as worker_app
from money_machine.cli.commands.workflow import app as workflow_app

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
app.add_typer(database_app, name="db")
app.add_typer(research_app, name="research")
app.add_typer(workflow_app, name="workflow")
app.add_typer(worker_app, name="worker")
app.add_typer(artifacts_app, name="artifacts")
app.add_typer(scheduler_app, name="scheduler")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
