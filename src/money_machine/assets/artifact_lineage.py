"""Fixture artifact lineage. Action 8 storage stays parked.

Each record stores the action 7 fields. A later ProductSpec version marks
this product's older assets stale, and then every asset that depends on a
stale one. The URI is fixture-only. Nothing here deletes a file or opens a
socket.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Literal, assert_never
from uuid import UUID

_HEX = re.compile(r"^[0-9a-f]{64}$")
AssetKind = Literal["screenshot", "listing_image", "delivery_pdf", "walkthrough"]
_PIXEL_KINDS = ("screenshot", "listing_image", "walkthrough")


class ArtifactLineageRefusal(ValueError):
    """The lineage record was refused before it was stored."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ArtifactLineage:
    """One asset's lineage. ``qa_status`` becomes ``stale`` only by invalidation."""

    product_id: UUID
    spec_version: int
    build_version: int
    source_screenshots: tuple[str, ...]
    merchandising_version: str
    template_version: str
    content_sha256: str
    dimensions: tuple[int, int] | None
    page_count: int | None
    qa_status: Literal["passed", "stale"]
    storage_uri: str
    kind: AssetKind

    def __post_init__(self) -> None:
        if self.qa_status not in ("passed", "stale"):
            raise ArtifactLineageRefusal("qa_status")
        if self.spec_version < 1:
            raise ArtifactLineageRefusal("spec_version")
        if self.build_version < 1:
            raise ArtifactLineageRefusal("build_version")
        if self.merchandising_version == "":
            raise ArtifactLineageRefusal("merchandising_version")
        if self.template_version == "":
            raise ArtifactLineageRefusal("template_version")
        if _HEX.fullmatch(self.content_sha256) is None:
            raise ArtifactLineageRefusal("hash")
        if any(_HEX.fullmatch(item) is None for item in self.source_screenshots):
            raise ArtifactLineageRefusal("sources")
        _refuse_measure(self.kind, self.dimensions, self.page_count)
        _refuse_sources(self.kind, self.source_screenshots, self.content_sha256)
        _refuse_live_storage(self.storage_uri)
        expected = fixture_storage_uri(
            product_id=self.product_id,
            spec_version=self.spec_version,
            build_version=self.build_version,
            kind=self.kind,
            content_sha256=self.content_sha256,
        )
        if self.storage_uri != expected:
            raise ArtifactLineageRefusal("storage_uri")


def fixture_storage_uri(
    *,
    product_id: UUID,
    spec_version: int,
    build_version: int,
    kind: AssetKind,
    content_sha256: str,
) -> str:
    """Canonical fixture URI. Live schemes are not produced here."""
    return (
        f"fixture://{product_id}/spec/{spec_version}/build/{build_version}/{kind}/{content_sha256}"
    )


def record_lineage(
    *,
    product_id: UUID,
    spec_version: int,
    build_version: int,
    source_screenshots: tuple[str, ...],
    merchandising_version: str,
    template_version: str,
    content_sha256: str,
    dimensions: tuple[int, int] | None,
    page_count: int | None,
    kind: AssetKind,
) -> ArtifactLineage:
    """Store one passed asset. The URI is derived from the coordinates."""
    return ArtifactLineage(
        product_id=product_id,
        spec_version=spec_version,
        build_version=build_version,
        source_screenshots=source_screenshots,
        merchandising_version=merchandising_version,
        template_version=template_version,
        content_sha256=content_sha256,
        dimensions=dimensions,
        page_count=page_count,
        qa_status="passed",
        storage_uri=fixture_storage_uri(
            product_id=product_id,
            spec_version=spec_version,
            build_version=build_version,
            kind=kind,
            content_sha256=content_sha256,
        ),
        kind=kind,
    )


def invalidate_product_change(
    assets: tuple[ArtifactLineage, ...],
    dependencies: Mapping[str, tuple[str, ...]],
    *,
    product_id: UUID,
    spec_version: int,
) -> tuple[ArtifactLineage, ...]:
    """Mark this product's older spec stale, then every dependent of a stale asset.

    ``dependencies`` maps a storage URI to the storage URIs it was built from.
    Another product is left as it was. No bytes are deleted.
    """
    stale = {
        asset.storage_uri
        for asset in assets
        if asset.qa_status == "stale"
        or (asset.product_id == product_id and asset.spec_version < spec_version)
    }
    growing = True
    while growing:
        growing = False
        for asset in assets:
            if asset.storage_uri in stale:
                continue
            deps = dependencies.get(asset.storage_uri, ())
            if any(dep in stale for dep in deps):
                stale.add(asset.storage_uri)
                growing = True
    return tuple(
        replace(asset, qa_status="stale") if asset.storage_uri in stale else asset
        for asset in assets
    )


def _refuse_live_storage(uri: str) -> None:
    """Refuse a live scheme. Each scheme is its own check."""
    if uri.startswith("s3://"):
        raise ArtifactLineageRefusal("live_storage")
    if uri.startswith("http://"):
        raise ArtifactLineageRefusal("live_storage")
    if uri.startswith("https://"):
        raise ArtifactLineageRefusal("live_storage")
    if uri.startswith("file://"):
        raise ArtifactLineageRefusal("live_storage")


def _refuse_measure(
    kind: AssetKind,
    dimensions: tuple[int, int] | None,
    page_count: int | None,
) -> None:
    if kind in _PIXEL_KINDS:
        if dimensions is None:
            raise ArtifactLineageRefusal("measure")
        if page_count is not None:
            raise ArtifactLineageRefusal("measure")
        width, height = dimensions
        if width < 1 or height < 1:
            raise ArtifactLineageRefusal("measure")
        return
    if kind == "delivery_pdf":
        if dimensions is not None:
            raise ArtifactLineageRefusal("pdf_measure")
        if page_count is None:
            raise ArtifactLineageRefusal("pdf_measure")
        if page_count < 1:
            raise ArtifactLineageRefusal("pdf_measure")
        return
    assert_never(kind)


def _refuse_sources(kind: AssetKind, sources: tuple[str, ...], digest: str) -> None:
    if kind == "screenshot" and sources != (digest,):
        raise ArtifactLineageRefusal("screenshot_source")
    if kind == "listing_image" and len(sources) == 0:
        raise ArtifactLineageRefusal("listing_source")
    if kind == "walkthrough" and len(sources) == 0:
        raise ArtifactLineageRefusal("walkthrough_source")
    if kind == "delivery_pdf":
        return
    if kind in ("screenshot", "listing_image", "walkthrough"):
        return
    assert_never(kind)
