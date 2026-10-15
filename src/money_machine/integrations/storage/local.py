"""Local runtime store. Every open walks from a directory handle.

The root is opened once. Each component is opened with ``openat`` and
``O_NOFOLLOW | O_DIRECTORY``. The final file is created, read, or unlinked
relative to that directory handle. A URI must be ``pid/spec/<64-hex>``
before any walk.
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import os
import re
import stat
from pathlib import Path
from uuid import UUID, uuid4

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
_READ = os.O_RDONLY | os.O_NOFOLLOW
_CREATE = os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_SPEC = re.compile(r"[1-9][0-9]*")
_HEX = re.compile(r"[0-9a-f]{64}")
_DOTS = frozenset({"", ".", ".."})


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
        role, product, spec, digest = _key(uri)
        parent = _open_dir(self.root, (role, product, spec))
        try:
            data = _read_optional(parent, digest)
        finally:
            os.close(parent)
        if data is None:
            raise ValueError("storage missing")
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
        role, product, spec, digest = _key(uri)
        parent = _open_dir(self.root, (role, product, spec))
        try:
            _unlink_object(parent, digest)
        finally:
            os.close(parent)

    def cleanup_temporary(
        self, *, product_id: UUID, spec_version: int, keep_sha256: str
    ) -> tuple[str, ...]:
        """Remove superseded temporary renders. The keep hash stays."""
        if _HEX.fullmatch(keep_sha256) is None:
            raise ValueError("storage hash")
        try:
            parent = _open_dir(self.root, ("temporary", str(product_id), str(spec_version)))
        except ValueError as exc:
            if exc.args == ("storage missing",):
                return ()
            raise
        try:
            removed: list[str] = []
            for name in _names(parent):
                if name == keep_sha256 or _HEX.fullmatch(name) is None:
                    continue
                _unlink_object(parent, name)
                removed.append(name)
            return tuple(removed)
        finally:
            os.close(parent)

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
        key_role, product, spec, digest = _key(uri)
        if key_role != role:
            raise ValueError("storage role")
        _ensure_dirs(self.root, (role, product, spec))
        parent = _open_dir(self.root, (role, product, spec))
        try:
            return _place_in(parent, digest, data, uri, role)
        finally:
            os.close(parent)


def _require_root(root: Path) -> Path:
    if not root.is_absolute():
        raise ValueError("storage root")
    try:
        descriptor = os.open(root, _DIRECTORY)
    except OSError as exc:
        raise ValueError("storage root") from exc
    os.close(descriptor)
    return root


def _key(uri: str) -> tuple[str, str, str, str]:
    """Refuse a URI that is not ``role/pid/spec/<64-hex>`` before any walk."""
    role, rest = _split(uri)
    if rest.startswith("/"):
        raise ValueError("storage path slash")
    if "\\" in rest:
        raise ValueError("storage path backslash")
    parts = rest.split("/")
    if len(parts) != 3:
        raise ValueError("storage path length")
    product, spec, digest = parts
    if any(part in _DOTS for part in parts):
        raise ValueError("storage path dots")
    if _UUID.fullmatch(product) is None:
        raise ValueError("storage path")
    if _SPEC.fullmatch(spec) is None:
        raise ValueError("storage path")
    if _HEX.fullmatch(digest) is None:
        raise ValueError("storage path")
    return role, product, spec, digest


def _open_dir(root: Path, parts: tuple[str, ...]) -> int:
    current = _open_root(root)
    for name in parts:
        if name in _DOTS:
            os.close(current)
            raise ValueError("storage path")
        try:
            nxt = os.open(name, _DIRECTORY, dir_fd=current)
        except OSError as exc:
            os.close(current)
            raise _mapped(exc) from exc
        os.close(current)
        current = nxt
    return current


def _open_root(root: Path) -> int:
    try:
        return os.open(root, _DIRECTORY)
    except OSError as exc:
        raise ValueError("storage root") from exc


def _ensure_dirs(root: Path, parts: tuple[str, ...]) -> None:
    current = _open_root(root)
    try:
        for name in parts:
            if name in _DOTS:
                raise ValueError("storage path")
            with contextlib.suppress(FileExistsError):
                os.mkdir(name, dir_fd=current)
            try:
                nxt = os.open(name, _DIRECTORY, dir_fd=current)
            except OSError as exc:
                raise _mapped(exc) from exc
            os.close(current)
            current = nxt
    except (OSError, ValueError):
        os.close(current)
        raise
    os.close(current)


def _place_in(parent: int, digest: str, data: bytes, uri: str, role: StorageRole) -> StoredObject:
    existing = _read_optional(parent, digest)
    if existing is not None:
        if existing == data:
            return _stored(uri, digest, data, role)
        refuse_collision(existing, data)
    temp = "." + uuid4().hex
    try:
        descriptor = os.open(temp, _CREATE, 0o644, dir_fd=parent)
    except OSError as exc:
        raise _mapped(exc) from exc
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written == 0:
                raise OSError(errno.EIO, "short write")
            view = view[written:]
        os.fsync(descriptor)
        try:
            os.link(temp, digest, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        except FileExistsError:
            current = _read_optional(parent, digest)
            if current == data:
                return _stored(uri, digest, data, role)
            refuse_collision(current if current is not None else b"", data)
        os.fsync(parent)
        return _stored(uri, digest, data, role)
    finally:
        os.close(descriptor)
        _unlink_temp(parent, temp)


def _read_optional(parent: int, name: str) -> bytes | None:
    try:
        descriptor = os.open(name, _READ, dir_fd=parent)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise _mapped(exc) from exc
    try:
        chunks: list[bytes] = []
        while True:
            block = os.read(descriptor, 1 << 20)
            if not block:
                return b"".join(chunks)
            chunks.append(block)
    finally:
        os.close(descriptor)


def _unlink_object(parent: int, name: str) -> None:
    if _HEX.fullmatch(name) is None:
        raise ValueError("storage path")
    try:
        info = os.lstat(name, dir_fd=parent)
    except FileNotFoundError as exc:
        raise ValueError("storage missing") from exc
    except OSError as exc:
        raise _mapped(exc) from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ValueError("storage symlink")
    os.unlink(name, dir_fd=parent)


def _unlink_temp(parent: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=parent)
    except FileNotFoundError:
        return


def _names(parent: int) -> list[str]:
    return sorted(os.listdir(f"/proc/self/fd/{parent}"))


def _mapped(exc: OSError) -> ValueError:
    if exc.errno == errno.ENOENT:
        return ValueError("storage missing")
    return ValueError("storage symlink")


def _split(uri: str) -> tuple[str, str]:
    if uri.startswith("fixture://"):
        return "published", uri.removeprefix("fixture://")
    if uri.startswith("temp://"):
        return "temporary", uri.removeprefix("temp://")
    raise ValueError("storage role")


def _stored(uri: str, sha256: str, data: bytes, role: StorageRole) -> StoredObject:
    return StoredObject(uri, sha256, len(data), role)
