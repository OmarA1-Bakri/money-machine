"""S3-shaped store that never opens a socket.

``draft`` and ``live`` are refused. Objects live in memory under the same
versioned key the local store uses.
"""

from __future__ import annotations

from uuid import UUID

from money_machine.integrations.storage.interface import (
    StorageRole,
    StoredObject,
    object_uri,
    refuse_collision,
    refuse_mode,
    refuse_published,
    refuse_signature,
    require_digest,
    signature,
)


class SimS3AssetStore:
    """Production-shaped keys in simulation. Retrieval is a local token."""

    def __init__(self, mode: str = "simulation") -> None:
        refuse_mode(mode)
        self._objects: dict[str, bytes] = {}
        self._roles: dict[str, StorageRole] = {}

    def publish(
        self, *, product_id: UUID, spec_version: int, sha256: str, data: bytes
    ) -> StoredObject:
        """Store published bytes under ``s3://simulation/``."""
        return self._put("published", "s3", product_id, spec_version, sha256, data)

    def put_temporary(
        self, *, product_id: UUID, spec_version: int, sha256: str, data: bytes
    ) -> StoredObject:
        """Store a temporary render under ``s3://temporary/``."""
        return self._put("temporary", "s3temp", product_id, spec_version, sha256, data)

    def read(self, uri: str) -> bytes:
        """Return stored bytes. The URI is not fetched."""
        data = self._objects.get(uri)
        if data is None:
            raise ValueError("storage missing")
        return data

    def signed_retrieval(self, uri: str) -> str:
        """Token for a published object. A missing object has no token."""
        if uri not in self._objects:
            raise ValueError("storage missing")
        if self._roles.get(uri) != "published":
            raise ValueError("storage role")
        return signature(uri)

    def read_signed(self, token: str, uri: str) -> bytes:
        """Read with a token bound to this URI."""
        refuse_signature(token, uri)
        return self.read(uri)

    def internal_retrieval(self, uri: str) -> str:
        """S3 simulation does not hand out an internal filesystem name."""
        raise ValueError("storage internal")

    def discard(self, uri: str) -> None:
        """Delete a temporary object. A published URI is refused."""
        refuse_published(uri)
        if not uri.startswith("s3://temporary/"):
            raise ValueError("storage role")
        if uri not in self._objects:
            raise ValueError("storage missing")
        del self._objects[uri]
        del self._roles[uri]

    def cleanup_temporary(
        self, *, product_id: UUID, spec_version: int, keep_sha256: str
    ) -> tuple[str, ...]:
        """Remove superseded temporary keys. Published keys are not in this prefix."""
        prefix = f"s3://temporary/{product_id}/{spec_version}/"
        removed: list[str] = []
        for uri in tuple(sorted(self._objects)):
            if not uri.startswith(prefix):
                continue
            digest = uri.rsplit("/", 1)[-1]
            if digest == keep_sha256:
                continue
            self.discard(uri)
            removed.append(digest)
        return tuple(removed)

    def _put(
        self,
        role: StorageRole,
        scheme: str,
        product_id: UUID,
        spec_version: int,
        sha256: str,
        data: bytes,
    ) -> StoredObject:
        require_digest(data, sha256)
        uri = object_uri(scheme, product_id, spec_version, sha256)
        existing = self._objects.get(uri)
        if existing is not None:
            if existing == data:
                return StoredObject(uri, sha256, len(data), role)
            refuse_collision(existing, data)
        self._objects[uri] = data
        self._roles[uri] = role
        return StoredObject(uri, sha256, len(data), role)
