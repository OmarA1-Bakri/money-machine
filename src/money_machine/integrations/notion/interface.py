"""Provider-neutral product bundle construction interface and identity."""

import hashlib
from pathlib import Path
from typing import Protocol

from money_machine.domain.models.product import BuildResult
from money_machine.domain.models.product_spec import ProductSpec


class NotionWriteDeniedError(RuntimeError):
    """Raised when a non-fixture Notion path attempts a write."""


class ProductBundleBuilder(Protocol):
    """Build a Notion-compatible bundle without requiring a live provider."""

    def build(self, spec: ProductSpec, destination: Path) -> BuildResult:
        """Build a deterministic product bundle at ``destination``."""
        ...


def deterministic_build_id(
    product_spec_id: str, manifest_sha256: str, renderer_version: str
) -> str:
    """Return the canonical identity for one immutable rendered bundle."""

    identity = f"{product_spec_id}\0{manifest_sha256}\0{renderer_version}".encode()
    return f"build-{hashlib.sha256(identity).hexdigest()}"
