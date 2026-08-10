"""Bounded local worker commands."""

import typer

from money_machine.agents.runtime import FirstProductRuntime
from money_machine.cli.support import emit, run, settings_or_exit
from money_machine.config.settings import Settings
from money_machine.persistence.database import Database

app = typer.Typer(no_args_is_help=True)


def _runtime(database: Database, settings: Settings) -> FirstProductRuntime:
    return FirstProductRuntime(
        database,
        artifact_root=settings.artifact_root,
        config_root=settings.config_root,
        worker_id=settings.worker_id,
    )


@app.command("run-once")
def run_once(json_output: bool = typer.Option(False, "--json")) -> None:
    del json_output
    settings = settings_or_exit()

    async def execute() -> dict[str, object]:
        database = Database.from_url(settings.database_url)
        try:
            result = await _runtime(database, settings).run_once()
            return {
                "status": result.status,
                "job_id": None if result.job_id is None else str(result.job_id),
                "error_code": result.error_code,
                "external_mutations": 0,
                "spend_usd": "0.00",
            }
        finally:
            await database.dispose()

    payload = run(execute())
    emit(payload)
    if payload["status"] == "failed":
        raise typer.Exit(1)


@app.command("drain")
def drain(
    max_jobs: int = typer.Option(20, "--max-jobs", min=1),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    del json_output
    settings = settings_or_exit()

    async def execute() -> dict[str, object]:
        database = Database.from_url(settings.database_url)
        try:
            results = await _runtime(database, settings).drain(max_jobs=max_jobs)
            return {
                "processed_count": sum(result.status == "processed" for result in results),
                "results": [
                    {
                        "status": result.status,
                        "job_id": None if result.job_id is None else str(result.job_id),
                        "error_code": result.error_code,
                    }
                    for result in results
                ],
                "final_status": results[-1].status,
                "external_mutations": 0,
                "spend_usd": "0.00",
            }
        finally:
            await database.dispose()

    payload = run(execute())
    emit(payload)
    if payload["final_status"] == "failed":
        raise typer.Exit(1)
