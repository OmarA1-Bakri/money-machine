"""Explicit, non-periodic scheduler command."""

from datetime import UTC, datetime

import typer

from money_machine.cli.support import emit, run, settings_or_exit
from money_machine.orchestration.idempotency import workflow_identity
from money_machine.orchestration.scheduler import Scheduler, ScheduleRecord
from money_machine.persistence.database import Database
from money_machine.persistence.unit_of_work import UnitOfWork

app = typer.Typer(no_args_is_help=True)


@app.command("run-once")
def run_once(
    packet_id: str = typer.Option(..., "--packet-id"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    del json_output
    settings = settings_or_exit()

    async def execute() -> dict[str, object]:
        database = Database.from_url(settings.database_url)
        try:
            async with UnitOfWork(database) as uow:
                if await uow.research.get_packet(packet_id) is None:
                    raise ValueError("research packet does not exist")
            now = datetime.now(UTC)
            enqueued = await Scheduler(
                database,
                schedule=ScheduleRecord(packet_id=packet_id, due_at=now, enabled=True),
            ).enqueue_due(now)
            return {
                "enqueued": enqueued,
                "workflow_run_id": str(workflow_identity(packet_id)),
                "periodic_enabled": False,
                "external_mutations": 0,
                "spend_usd": "0.00",
            }
        finally:
            await database.dispose()

    emit(run(execute()))
