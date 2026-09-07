"""Artifact, lineage and receipt access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from money_machine.persistence.repositories._base import Repository
from money_machine.persistence.tables import Artifact, ArtifactLineage, Receipt


class ArtifactRepository(Repository[Artifact]):
    """Immutable artifact records addressed by content hash."""

    model = Artifact

    async def by_hash(self, digest: str, logical_role: str) -> Artifact | None:
        """Fetch one artifact by content hash and logical role."""
        statement = select(Artifact).where(
            Artifact.sha256 == digest,
            Artifact.logical_role == logical_role,
        )
        return (await self.session.execute(statement)).scalars().one_or_none()

    async def parents_of(self, artifact_id: UUID) -> tuple[UUID, ...]:
        """The parent artifact identifiers one artifact was derived from."""
        statement = select(ArtifactLineage.parent_artifact_id).where(
            ArtifactLineage.artifact_id == artifact_id
        )
        return tuple((await self.session.execute(statement)).scalars().all())

    async def link_parent(self, artifact_id: UUID, parent_artifact_id: UUID) -> ArtifactLineage:
        """Record that one artifact derives from another."""
        edge = ArtifactLineage(artifact_id=artifact_id, parent_artifact_id=parent_artifact_id)
        self.session.add(edge)
        await self.session.flush()
        return edge


class ReceiptRepository(Repository[Receipt]):
    """Append-only receipts for external effects."""

    model = Receipt

    async def for_key(self, idempotency_key: str) -> tuple[Receipt, ...]:
        """Every receipt recorded under one idempotency key."""
        statement = (
            select(Receipt)
            .where(Receipt.idempotency_key == idempotency_key)
            .order_by(Receipt.recorded_at)
        )
        return tuple((await self.session.execute(statement)).scalars().all())
