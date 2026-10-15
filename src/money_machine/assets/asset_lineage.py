"""Project rendered assets into one lineage record and drop stale dependents.

The storage URI is a fixture name. Object storage is a later wave. A product
change is a new ``spec_version`` for one ``product_id``. Stale identity is
``(spec_version, output_sha256)``, so two specs can share one output hash.
A source hash is resolved against that same spec. An unknown source is stale.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal
from uuid import UUID

from money_machine.assets.delivery_pdfs import DeliveryPdfLineage
from money_machine.assets.listing_images import ListingImageLineage
from money_machine.assets.screenshots import ScreenshotLineage
from money_machine.assets.video import WalkthroughLineage

type RenderedLineage = (
    ScreenshotLineage | ListingImageLineage | WalkthroughLineage | DeliveryPdfLineage
)
type AssetKind = Literal["screenshot", "listing_image", "walkthrough", "delivery_pdf"]


@dataclass(frozen=True, slots=True)
class BoundAsset:
    """One rendered asset. ``qa_status`` is ``stale`` only after a product change."""

    product_id: UUID
    spec_version: int
    build_version: int
    source_screenshot_sha256: tuple[str, ...]
    merchandising_version: str
    template_version: str
    output_sha256: str
    width_px: int | None
    height_px: int | None
    page_count: int | None
    qa_status: Literal["passed", "stale"]
    storage_uri: str
    kind: AssetKind


def fixture_storage_uri(product_id: UUID, spec_version: int, output_sha256: str) -> str:
    """Name the bytes. This is not a network address."""
    return f"fixture://{product_id}/{spec_version}/{output_sha256}"


def bind_asset(lineage: RenderedLineage) -> BoundAsset:
    """Copy one renderer record into the shared lineage shape."""
    if isinstance(lineage, ScreenshotLineage):
        return _bound(
            kind="screenshot",
            product_id=lineage.product_id,
            spec_version=lineage.spec_version,
            build_version=lineage.build_version,
            source_screenshot_sha256=(),
            merchandising_version="",
            template_version=lineage.template_version,
            output_sha256=lineage.screenshot_sha256,
            width_px=lineage.crop_width,
            height_px=lineage.crop_height,
            page_count=None,
            qa_status=lineage.qa_status,
        )
    if isinstance(lineage, ListingImageLineage):
        return _bound(
            kind="listing_image",
            product_id=lineage.product_id,
            spec_version=lineage.spec_version,
            build_version=lineage.build_version,
            source_screenshot_sha256=lineage.source_screenshot_sha256,
            merchandising_version=lineage.merchandising_version,
            template_version=lineage.template_version,
            output_sha256=lineage.output_sha256,
            width_px=lineage.width_px,
            height_px=lineage.height_px,
            page_count=None,
            qa_status=lineage.qa_status,
        )
    if isinstance(lineage, WalkthroughLineage):
        return _bound(
            kind="walkthrough",
            product_id=lineage.product_id,
            spec_version=lineage.spec_version,
            build_version=lineage.build_version,
            source_screenshot_sha256=lineage.source_screenshot_sha256,
            merchandising_version=lineage.merchandising_version,
            template_version=lineage.template_version,
            output_sha256=lineage.output_sha256,
            width_px=lineage.width_px,
            height_px=lineage.height_px,
            page_count=None,
            qa_status=lineage.qa_status,
        )
    return _bound(
        kind="delivery_pdf",
        product_id=lineage.product_id,
        spec_version=lineage.spec_version,
        build_version=lineage.build_version,
        source_screenshot_sha256=(),
        merchandising_version=lineage.merchandising_version,
        template_version=lineage.template_version,
        output_sha256=lineage.output_sha256,
        width_px=None,
        height_px=None,
        page_count=lineage.page_count,
        qa_status=lineage.qa_status,
    )


def split_current(
    assets: tuple[BoundAsset, ...],
    *,
    product_id: UUID,
    spec_version: int,
) -> tuple[tuple[BoundAsset, ...], tuple[BoundAsset, ...]]:
    """Return current assets, then stale ones, for this product and spec.

    Other products are omitted. The walk repeats so a dependent listed before
    its source still becomes stale.
    """
    owned = tuple(asset for asset in assets if asset.product_id == product_id)
    known = {(asset.spec_version, asset.output_sha256) for asset in owned}
    stale_ids: set[tuple[int, str]] = set()
    pending = list(owned)
    progressed = True
    while progressed:
        progressed = False
        rest: list[BoundAsset] = []
        for asset in pending:
            if _is_stale(
                asset,
                spec_version=spec_version,
                stale_ids=stale_ids,
                known=known,
            ):
                stale_ids.add((asset.spec_version, asset.output_sha256))
                progressed = True
                continue
            rest.append(asset)
        pending = rest
    current = tuple(
        asset for asset in owned if (asset.spec_version, asset.output_sha256) not in stale_ids
    )
    stale = tuple(
        replace(asset, qa_status="stale")
        for asset in owned
        if (asset.spec_version, asset.output_sha256) in stale_ids
    )
    return current, stale


def _is_stale(
    asset: BoundAsset,
    *,
    spec_version: int,
    stale_ids: set[tuple[int, str]],
    known: set[tuple[int, str]],
) -> bool:
    if asset.spec_version != spec_version:
        return True
    if asset.qa_status != "passed":
        return True
    return any(
        _source_stale(src, spec_version=asset.spec_version, stale_ids=stale_ids, known=known)
        for src in asset.source_screenshot_sha256
    )


def _source_stale(
    src: str,
    *,
    spec_version: int,
    stale_ids: set[tuple[int, str]],
    known: set[tuple[int, str]],
) -> bool:
    """A source is stale when this spec has no such asset, or that asset is stale."""
    identity = (spec_version, src)
    if identity not in known:
        return True
    return identity in stale_ids


def _bound(
    *,
    kind: AssetKind,
    product_id: UUID,
    spec_version: int,
    build_version: int,
    source_screenshot_sha256: tuple[str, ...],
    merchandising_version: str,
    template_version: str,
    output_sha256: str,
    width_px: int | None,
    height_px: int | None,
    page_count: int | None,
    qa_status: Literal["passed"],
) -> BoundAsset:
    return BoundAsset(
        product_id=product_id,
        spec_version=spec_version,
        build_version=build_version,
        source_screenshot_sha256=source_screenshot_sha256,
        merchandising_version=merchandising_version,
        template_version=template_version,
        output_sha256=output_sha256,
        width_px=width_px,
        height_px=height_px,
        page_count=page_count,
        qa_status=qa_status,
        storage_uri=fixture_storage_uri(product_id, spec_version, output_sha256),
        kind=kind,
    )
