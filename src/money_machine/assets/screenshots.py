"""Local screenshot lineage helpers; no browser or network access is performed."""

from __future__ import annotations

import hashlib
from pathlib import Path

from money_machine.domain.models.asset import ArtifactReference


def reference_local_screenshot(path: Path, *, root: Path, build_id: str) -> ArtifactReference:
    """Reference a stable local PNG only when it is contained by the artifact root."""

    resolved_root = root.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
        raise ValueError("screenshot must be an existing local file inside artifact root")
    data = resolved.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    return ArtifactReference(
        artifact_id=f"screenshot-{build_id}-{digest[:16]}",
        relative_path=resolved.relative_to(resolved_root),
        media_type="image/png",
        byte_count=len(data),
        content_sha256=digest,
    )
