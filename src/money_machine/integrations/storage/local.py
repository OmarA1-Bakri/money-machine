"""Fail-closed local immutable artifact storage."""

from __future__ import annotations

import hashlib
import os
import secrets
import stat
from contextlib import suppress
from pathlib import Path, PurePosixPath

from money_machine.domain.models.asset import ArtifactReference
from money_machine.integrations.storage.interface import (
    ArtifactCollisionError,
    UnsafeArtifactPathError,
)


class LocalArtifactStore:
    """Store immutable artifacts below one local filesystem root."""

    def __init__(self, root: Path) -> None:
        self._root_descriptor = -1
        absolute_root = Path(os.path.abspath(root))
        try:
            root_descriptor = _open_or_create_absolute_directory(absolute_root)
        except OSError as error:
            raise UnsafeArtifactPathError("artifact root contains an unsafe component") from error
        self._root = absolute_root
        self._root_descriptor = root_descriptor
        root_stat = os.fstat(root_descriptor)
        self._root_identity = (root_stat.st_dev, root_stat.st_ino)

    def close(self) -> None:
        """Release the persistent root descriptor."""

        if self._root_descriptor >= 0:
            os.close(self._root_descriptor)
            self._root_descriptor = -1

    def __del__(self) -> None:
        with suppress(OSError):
            self.close()

    @property
    def root(self) -> Path:
        """Return the canonical configured root."""

        return self._root

    def put_bytes(
        self, relative_path: str | Path, data: bytes, media_type: str
    ) -> ArtifactReference:
        """Atomically store bytes without permitting mutation or root escape."""

        canonical_path = _canonical_relative_path(relative_path)
        digest = hashlib.sha256(data).hexdigest()
        reference = _reference(canonical_path, media_type, data, digest)
        parent_fd, filename = self._open_parent(canonical_path)
        temporary_name = f".{filename}.{secrets.token_hex(12)}.tmp"
        temporary_created = False
        try:
            existing_fd = _open_regular_file(filename, parent_fd)
            if existing_fd is not None:
                try:
                    if _sha256_descriptor(existing_fd) != digest:
                        raise ArtifactCollisionError(
                            f"immutable artifact collision: {canonical_path}"
                        )
                    return reference
                finally:
                    os.close(existing_fd)

            descriptor = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent_fd,
            )
            temporary_created = True
            try:
                _write_all(descriptor, data)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

            try:
                os.link(
                    temporary_name,
                    filename,
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileExistsError:
                existing_fd = _open_regular_file(filename, parent_fd)
                if existing_fd is None:
                    raise UnsafeArtifactPathError(
                        "artifact destination must be a regular file"
                    ) from None
                try:
                    if _sha256_descriptor(existing_fd) != digest:
                        raise ArtifactCollisionError(
                            f"immutable artifact collision: {canonical_path}"
                        ) from None
                finally:
                    os.close(existing_fd)
            os.fsync(parent_fd)
        finally:
            if temporary_created:
                with suppress(FileNotFoundError):
                    os.unlink(temporary_name, dir_fd=parent_fd)
            os.close(parent_fd)

        return reference

    def _open_root(self) -> int:
        if self._root_descriptor < 0:
            raise UnsafeArtifactPathError("artifact store is closed")
        try:
            lexical_descriptor = _open_existing_absolute_directory(self._root)
        except OSError as error:
            raise UnsafeArtifactPathError("artifact root was replaced or is unsafe") from error
        try:
            root_stat = os.fstat(lexical_descriptor)
            if (root_stat.st_dev, root_stat.st_ino) != self._root_identity:
                raise UnsafeArtifactPathError("artifact root identity changed")
        finally:
            os.close(lexical_descriptor)
        return os.dup(self._root_descriptor)

    def _open_parent(self, relative_path: PurePosixPath) -> tuple[int, str]:
        descriptor = self._open_root()
        try:
            for part in relative_path.parts[:-1]:
                with suppress(FileExistsError):
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
                try:
                    child = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=descriptor,
                    )
                except OSError as error:
                    raise UnsafeArtifactPathError(
                        "artifact path contains an unsafe directory"
                    ) from error
                os.close(descriptor)
                descriptor = child
            return descriptor, relative_path.name
        except BaseException:
            os.close(descriptor)
            raise


def _canonical_relative_path(value: str | Path) -> PurePosixPath:
    raw = str(value)
    path = PurePosixPath(raw)
    if (
        not raw
        or raw in {".", ".."}
        or "\\" in raw
        or raw.startswith("./")
        or "//" in raw
        or path.is_absolute()
        or ":" in path.parts[0]
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != raw
    ):
        raise UnsafeArtifactPathError("artifact path must be canonical POSIX-relative")
    return path


def _sha256_descriptor(descriptor: int) -> str:
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    while chunk := os.read(descriptor, 1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def _open_regular_file(name: str, parent_fd: int) -> int | None:
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise UnsafeArtifactPathError("artifact destination is unsafe") from error
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise UnsafeArtifactPathError("artifact destination must be a regular file")
    return descriptor


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        view = view[written:]


def _reference(
    relative_path: PurePosixPath, media_type: str, data: bytes, content_sha256: str
) -> ArtifactReference:
    identity = f"{relative_path.as_posix()}\0{media_type}\0{content_sha256}".encode()
    return ArtifactReference(
        artifact_id=f"artifact-{hashlib.sha256(identity).hexdigest()}",
        relative_path=Path(relative_path.as_posix()),
        media_type=media_type,
        byte_count=len(data),
        content_sha256=content_sha256,
    )


def _open_or_create_absolute_directory(path: Path) -> int:
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            try:
                child = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                with suppress(FileExistsError):
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
                child = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_existing_absolute_directory(path: Path) -> int:
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise
