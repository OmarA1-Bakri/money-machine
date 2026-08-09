"""Provider-neutral immutable artifact storage contracts."""

from pathlib import Path
from typing import Protocol

from money_machine.domain.models.asset import ArtifactReference


class ArtifactStoreError(RuntimeError):
    """Base error for local artifact storage failures."""


class UnsafeArtifactPathError(ArtifactStoreError, ValueError):
    """Raised when an artifact path can escape or alias the configured root."""


class ArtifactCollisionError(ArtifactStoreError):
    """Raised when immutable artifact bytes already exist at a requested path."""


class ArtifactStore(Protocol):
    """Minimal immutable byte-store interface used by deterministic builders."""

    @property
    def root(self) -> Path:
        """Return the configured storage root."""
        ...

    def put_bytes(
        self, relative_path: str | Path, data: bytes, media_type: str
    ) -> ArtifactReference:
        """Persist bytes atomically and return their immutable reference."""
        ...
