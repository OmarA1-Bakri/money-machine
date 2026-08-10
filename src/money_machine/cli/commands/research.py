"""Strict local research-packet import."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from money_machine.application.services.research_service import ResearchService
from money_machine.cli.support import emit, run, settings_or_exit
from money_machine.persistence.database import Database
from money_machine.persistence.unit_of_work import UnitOfWork

app = typer.Typer(no_args_is_help=True)


@app.command("import")
def import_packet(
    packet: Annotated[
        Path,
        typer.Option("--packet", exists=True, dir_okay=False, readable=True),
    ],
    validate_only: Annotated[bool, typer.Option("--validate-only")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    del json_output
    settings = settings_or_exit()
    imported = ResearchService().import_packet(packet, now=datetime.now(UTC))

    async def persist() -> None:
        database = Database.from_url(settings.database_url)
        try:
            async with UnitOfWork(database) as uow:
                await uow.research.add_packet(imported)
        finally:
            await database.dispose()

    if not validate_only:
        run(persist())
    emit(
        {
            "packet_id": imported.packet_id,
            "packet_sha256": imported.packet_sha256,
            "row_count": len(imported.observations),
            "persisted": not validate_only,
            "external_mutations": 0,
            "spend_usd": "0.00",
        }
    )
