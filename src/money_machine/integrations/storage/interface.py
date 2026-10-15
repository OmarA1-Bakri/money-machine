"""Versioned artifact keys. Callers pass bytes; nothing here opens a socket."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

type StorageRole = Literal["temporary", "published"]

_HEX = "0123456789abcdef"


@dataclass(frozen=True, slots=True)
class StoredObject:
    """One stored object. The URI is the versioned key."""

    storage_uri: str
    sha256: str
    byte_count: int
    role: StorageRole


def refuse_mode(mode: str) -> None:
    """Simulation is the only mode. Each other mode has its own line."""
    if mode == "draft":
        raise ValueError("storage live")
    if mode == "live":
        raise ValueError("storage live")
    if mode == "simulation":
        return
    raise ValueError("storage mode")


def refuse_spec(spec_version: int) -> None:
    """A spec is a positive int. ``True`` is refused on its own line."""
    if isinstance(spec_version, bool):
        raise ValueError("storage spec")
    if spec_version < 1:
        raise ValueError("storage spec")


def require_digest(data: bytes, sha256: str) -> None:
    """The claimed hash is 64 lowercase hex characters and matches ``data``."""
    if len(sha256) != 64:
        raise ValueError("storage hash")
    if any(char not in _HEX for char in sha256):
        raise ValueError("storage hash")
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError("storage digest")


def refuse_collision(existing: bytes, data: bytes) -> None:
    """Different bytes at a key that already exists."""
    if existing != data:
        raise ValueError("storage collision")


def object_uri(scheme: str, product_id: UUID, spec_version: int, sha256: str) -> str:
    """Build the versioned URI. ``require_digest`` has already checked the hash."""
    refuse_spec(spec_version)
    prefix = _prefix(scheme)
    return f"{prefix}{product_id}/{spec_version}/{sha256}"


def _prefix(scheme: str) -> str:
    if scheme == "fixture":
        return "fixture://"
    if scheme == "temp":
        return "temp://"
    if scheme == "s3":
        return "s3://simulation/"
    if scheme == "s3temp":
        return "s3://temporary/"
    raise ValueError("storage scheme")


def signature(uri: str) -> str:
    """Local token. This key is not a provider credential."""
    digest = hmac.new(b"simulation", uri.encode(), hashlib.sha256).hexdigest()
    return "sim-signed:" + digest


def refuse_signature(token: str, uri: str) -> None:
    """The token must be the signature of this URI and no other."""
    if not hmac.compare_digest(token, signature(uri)):
        raise ValueError("storage signature")


def refuse_published(uri: str) -> None:
    """Published keys are evidence. Each scheme has its own line."""
    if uri.startswith("fixture://"):
        raise ValueError("storage published")
    if uri.startswith("s3://simulation/"):
        raise ValueError("storage published")
