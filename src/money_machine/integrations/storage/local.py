"""Local runtime store. Files stay under an absolute directory that is not a symlink."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from uuid import UUID

from money_machine.integrations.storage.interface import (
    StorageRole,
    StoredObject,
    object_uri,
    refuse_collision,
    refuse_mode,
    refuse_published,
    require_digest,
)

_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class LocalAssetStore:
    """Development store. Retrieval is an internal name, never a signed URL."""

    def __init__(self, root: Path, mode: str = "simulation") -> None:
        refuse_mode(mode)
        self.root = _require_root(root)

    def publish(
        self, *, product_id: UUID, spec_version: int, sha256: str, data: bytes
    ) -> StoredObject:
        """Write published bytes. The same bytes are idempotent."""
        return self._put("published", "fixture", product_id, spec_version, sha256, data)

    def put_temporary(
        self, *, product_id: UUID, spec_version: int, sha256: str, data: bytes
    ) -> StoredObject:
        """Write a temporary render."""
        return self._put("temporary", "temp", product_id, spec_version, sha256, data)

    def read(self, uri: str) -> bytes:
        """Return the stored bytes. A hostile URI is refused before the read."""
        path = self._path(uri)
        data = _file_bytes(path)
        digest = uri.rsplit("/", 1)[-1]
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("storage bytes")
        return data

    def internal_retrieval(self, uri: str) -> str:
        """Name a stored object for an in-process reader."""
        self.read(uri)
        return "internal:" + uri

    def signed_retrieval(self, uri: str) -> str:
        """Local development does not sign. S3 simulation does."""
        raise ValueError("storage signed")

    def discard(self, uri: str) -> None:
        """Delete a temporary object. A published URI is refused."""
        refuse_published(uri)
        path = self._path(uri)
        _file_bytes(path)
        path.unlink()

    def cleanup_temporary(
        self, *, product_id: UUID, spec_version: int, keep_sha256: str
    ) -> tuple[str, ...]:
        """Remove superseded temporary renders. The keep hash stays."""
        directory = self.root / "temporary" / str(product_id) / str(spec_version)
        if directory.is_symlink():
            raise ValueError("storage symlink")
        if not directory.is_dir():
            return ()
        removed: list[str] = []
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            if child.name == keep_sha256:
                continue
            self.discard(f"temp://{product_id}/{spec_version}/{child.name}")
            removed.append(child.name)
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
        path = self._path(uri)
        _ensure_parent(self.root, path.parent)
        return _place(path, data, uri, sha256, role)

    def _path(self, uri: str) -> Path:
        role, rest = _split(uri)
        if any(part in {"", ".", ".."} for part in rest.split("/")):
            raise ValueError("storage path")
        return self.root / role / rest


def _require_root(root: Path) -> Path:
    if not root.is_absolute():
        raise ValueError("storage root")
    try:
        descriptor = os.open(root, _DIRECTORY)
    except OSError as exc:
        raise ValueError("storage root") from exc
    os.close(descriptor)
    return root


def _ensure_parent(root: Path, parent: Path) -> None:
    current = root
    relative = parent.relative_to(root)
    for name in relative.parts:
        target = current / name
        try:
            os.mkdir(target)
        except FileExistsError:
            info = target.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise ValueError("storage symlink") from None
        current = target


def _write_exclusive(path: Path, data: bytes) -> None:
    """Create a new file. ``O_EXCL`` refuses an existing path, including a symlink."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    descriptor = os.open(path, flags, 0o644)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
    finally:
        os.close(descriptor)


def _place(path: Path, data: bytes, uri: str, sha256: str, role: StorageRole) -> StoredObject:
    if path.is_symlink():
        raise ValueError("storage symlink")
    try:
        _write_exclusive(path, data)
    except FileExistsError:
        existing = path.read_bytes()
        if existing == data:
            return _stored(uri, sha256, data, role)
        refuse_collision(existing, data)
        raise ValueError("storage place") from None
    return _stored(uri, sha256, data, role)


def _file_bytes(path: Path) -> bytes:
    if path.is_symlink():
        raise ValueError("storage symlink")
    if not path.is_file():
        raise ValueError("storage missing")
    return path.read_bytes()


def _split(uri: str) -> tuple[str, str]:
    if uri.startswith("fixture://"):
        return "published", uri.removeprefix("fixture://")
    if uri.startswith("temp://"):
        return "temporary", uri.removeprefix("temp://")
    raise ValueError("storage role")


def _stored(uri: str, sha256: str, data: bytes, role: StorageRole) -> StoredObject:
    return StoredObject(uri, sha256, len(data), role)
