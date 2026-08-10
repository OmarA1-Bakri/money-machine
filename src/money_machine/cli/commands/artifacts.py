"""Explicit local artifact inspection with confinement checks."""

from __future__ import annotations

import hashlib
from uuid import UUID

import typer

from money_machine.cli.support import emit, fail, run, settings_or_exit
from money_machine.persistence.database import Database
from money_machine.persistence.unit_of_work import UnitOfWork

app = typer.Typer(no_args_is_help=True)


@app.command("inspect")
def inspect_artifacts(
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
                if await uow.workflows.get(run_id) is None:
                    raise ValueError("workflow does not exist")
                durable = await uow.artifacts.list_for_workflow(run_id)
            lexical_root = settings.artifact_root / str(run_id)
            if lexical_root.is_symlink():
                raise ValueError("artifact root is not confined")
            root = lexical_root.resolve()
            if root.parent != settings.artifact_root.resolve():
                raise ValueError("artifact root is not confined")
            files: list[dict[str, object]] = []
            if root.is_dir():
                for path in sorted(root.rglob("*")):
                    if path.is_symlink():
                        raise ValueError("artifact tree contains a symlink")
                    if path.is_file():
                        data = path.read_bytes()
                        files.append(
                            {
                                "relative_path": path.relative_to(root).as_posix(),
                                "byte_count": len(data),
                                "sha256": hashlib.sha256(data).hexdigest(),
                            }
                        )
            return {
                "workflow_run_id": str(run_id),
                "local_root": str(root),
                "durable_artifact_count": len(durable),
                "file_count": len(files),
                "durable_artifacts": [
                    {
                        "artifact_id": item.artifact_id,
                        "relative_path": item.relative_path.as_posix(),
                        "media_type": item.media_type,
                        "byte_count": item.byte_count,
                        "sha256": item.content_sha256,
                    }
                    for item in durable
                ],
                "files": files,
                "external_mutations": 0,
                "spend_usd": "0.00",
            }
        finally:
            await database.dispose()

    emit(run(execute()))
