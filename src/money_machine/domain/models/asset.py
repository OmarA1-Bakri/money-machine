"""Local artifact contracts."""

from pathlib import Path

from pydantic import Field

from money_machine.domain.value_objects import FrozenModel, NonEmptyStr, Sha256


class ArtifactReference(FrozenModel):
    """Content-addressed reference to one local artifact."""

    artifact_id: NonEmptyStr
    relative_path: Path
    media_type: NonEmptyStr
    byte_count: int = Field(ge=0)
    content_sha256: Sha256
