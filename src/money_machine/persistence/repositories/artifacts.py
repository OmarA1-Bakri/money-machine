"""Local artifact metadata persistence."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.value_objects import canonical_json
from money_machine.persistence.tables import artifacts


class ArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, artifact: ArtifactReference, *, workflow_run_id: UUID | None) -> None:
        inserted = (
            await self._session.execute(
                pg_insert(artifacts)
                .values(
                    artifact_id=artifact.artifact_id,
                    workflow_run_id=workflow_run_id,
                    relative_path=artifact.relative_path.as_posix(),
                    media_type=artifact.media_type,
                    byte_count=artifact.byte_count,
                    sha256=artifact.content_sha256,
                    payload=json.loads(canonical_json(artifact)),
                )
                .on_conflict_do_nothing()
                .returning(artifacts.c.artifact_id)
            )
        ).scalar_one_or_none()
        if inserted is not None:
            return
        row = (
            await self._session.execute(
                select(artifacts.c.payload, artifacts.c.workflow_run_id).where(
                    artifacts.c.artifact_id == artifact.artifact_id
                )
            )
        ).one_or_none()
        existing = (
            None
            if row is None
            else ArtifactReference.model_validate_json(
                json.dumps(row.payload, separators=(",", ":"))
            )
        )
        if existing != artifact or row is None or row.workflow_run_id != workflow_run_id:
            raise ValueError(f"identity collision for {artifact.artifact_id}")

    async def get(self, artifact_id: str) -> ArtifactReference | None:
        result = await self._session.execute(
            select(artifacts.c.payload).where(artifacts.c.artifact_id == artifact_id)
        )
        payload = result.scalar_one_or_none()
        return (
            None if payload is None else ArtifactReference.model_validate_json(json.dumps(payload))
        )

    async def list_for_workflow(self, workflow_run_id: UUID) -> tuple[ArtifactReference, ...]:
        payloads = (
            await self._session.execute(
                select(artifacts.c.payload)
                .where(artifacts.c.workflow_run_id == workflow_run_id)
                .order_by(artifacts.c.relative_path, artifacts.c.artifact_id)
            )
        ).scalars()
        return tuple(
            ArtifactReference.model_validate_json(json.dumps(payload)) for payload in payloads
        )
