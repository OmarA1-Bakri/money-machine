"""First-product workflow start and read-only status commands."""

from __future__ import annotations

from uuid import UUID

import typer

from money_machine.agents.runtime import FirstProductRuntime
from money_machine.cli.support import emit, fail, run, settings_or_exit
from money_machine.orchestration.idempotency import workflow_identity
from money_machine.persistence.database import Database
from money_machine.persistence.unit_of_work import UnitOfWork

app = typer.Typer(no_args_is_help=True)


@app.command("start")
def start(
    workflow_kind: str = typer.Argument(...),
    packet_id: str = typer.Option(..., "--packet-id"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    del json_output
    if workflow_kind != "first-product":
        fail("UNKNOWN_WORKFLOW", "only first-product is commissioned")
    settings = settings_or_exit()

    async def execute() -> dict[str, object]:
        database = Database.from_url(settings.database_url)
        try:
            expected_id = workflow_identity(packet_id)
            async with UnitOfWork(database) as uow:
                if await uow.research.get_packet(packet_id) is None:
                    raise ValueError("research packet does not exist")
                replayed = await uow.workflows.get(expected_id) is not None
            runtime = FirstProductRuntime(
                database,
                artifact_root=settings.artifact_root,
                config_root=settings.config_root,
                worker_id=settings.worker_id,
            )
            workflow_id = await runtime.start(packet_id)
            async with UnitOfWork(database) as uow:
                workflow = await uow.workflows.get(workflow_id)
            if workflow is None:
                raise RuntimeError("workflow was not persisted")
            return {
                "workflow_run_id": str(workflow.workflow_run_id),
                "workflow_type": workflow.workflow_type,
                "packet_id": workflow.packet_id,
                "state": workflow.state.value,
                "replayed": replayed,
                "external_mutations": 0,
                "spend_usd": "0.00",
            }
        finally:
            await database.dispose()

    emit(run(execute()))


@app.command("status")
def status(
    workflow_run_id: str = typer.Argument(...),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    del json_output
    settings = settings_or_exit()
    try:
        run_id = UUID(workflow_run_id)
    except ValueError:
        fail("INVALID_WORKFLOW_ID", "workflow_run_id must be a UUID")

    async def execute() -> dict[str, object]:
        database = Database.from_url(settings.database_url)
        try:
            async with UnitOfWork(database) as uow:
                workflow = await uow.workflows.get(run_id)
                if workflow is None:
                    raise ValueError("workflow does not exist")
                jobs = await uow.jobs.list_for_workflow(run_id)
                events = await uow.events.list_for_workflow(run_id)
            return {
                "workflow_run_id": str(workflow.workflow_run_id),
                "workflow_type": workflow.workflow_type,
                "packet_id": workflow.packet_id,
                "state": workflow.state.value,
                "terminal_blocker": (
                    None
                    if workflow.terminal_blocker is None
                    else workflow.terminal_blocker.model_dump(mode="json")
                ),
                "jobs": [
                    {
                        "job_id": str(job.job_id),
                        "job_type": job.job_type,
                        "state": job.state.value,
                        "retry_class": job.retry_class.value,
                        "max_attempts": job.max_attempts,
                    }
                    for job in jobs
                ],
                "events": [
                    {
                        "event_id": str(event.event_id),
                        "job_id": None if event.job_id is None else str(event.job_id),
                        "name": event.name.value,
                        "occurred_at": event.occurred_at.isoformat(),
                        "payload_sha256": event.payload_sha256,
                    }
                    for event in events
                ],
                "external_mutations": 0,
                "spend_usd": "0.00",
            }
        finally:
            await database.dispose()

    emit(run(execute()))
