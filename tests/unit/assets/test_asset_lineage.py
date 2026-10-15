"""Fixture lineage invalidation. Each staleness check has its own kill."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from money_machine.assets.asset_lineage import BoundAsset, bind_asset, split_current
from money_machine.assets.delivery_pdfs import DeliveryPdfLineage
from money_machine.assets.listing_images import ListingImageLineage
from money_machine.assets.screenshots import ScreenshotLineage
from money_machine.assets.video import WalkthroughLineage

_PRODUCT = UUID("00000000-0000-4000-8000-000000000001")
_OTHER = UUID("00000000-0000-4000-8000-000000000002")


def _shot(digest: str, *, spec: int = 2, product: UUID = _PRODUCT) -> BoundAsset:
    return bind_asset(
        ScreenshotLineage(
            product_id=product,
            spec_version=spec,
            build_version=4,
            screenshot_sha256=digest,
            variant="Sage Green",
            template_version="t1",
            viewport_width=10,
            viewport_height=10,
            crop_x=0,
            crop_y=0,
            crop_width=8,
            crop_height=6,
            qa_status="passed",
            source="fixture",
        )
    )


def _listing(
    digest: str,
    sources: tuple[str, ...],
    *,
    spec: int = 2,
    product: UUID = _PRODUCT,
) -> BoundAsset:
    return bind_asset(
        ListingImageLineage(
            product_id=product,
            spec_version=spec,
            build_version=4,
            source_screenshot_sha256=sources,
            merchandising_version="m1",
            template_version="t1",
            output_sha256=digest,
            width_px=20,
            height_px=10,
            qa_status="passed",
            role="hero",
        )
    )


def _root() -> BoundAsset:
    """Stale for spec and for QA, so deleting either check still marks it."""
    return replace(_shot("aa", spec=1), qa_status="stale")


def test_bind_asset_projects_each_kind() -> None:
    shot = _shot("aa")
    assert shot.kind == "screenshot"
    assert shot.source_screenshot_sha256 == ()
    assert shot.merchandising_version == ""
    assert shot.width_px == 8
    assert shot.height_px == 6
    assert shot.page_count is None
    assert shot.storage_uri == f"fixture://{_PRODUCT}/2/aa"
    assert shot.qa_status == "passed"

    image = _listing("bb", ("aa",))
    assert image.kind == "listing_image"
    assert image.source_screenshot_sha256 == ("aa",)
    assert image.merchandising_version == "m1"
    assert image.width_px == 20
    assert image.page_count is None

    video = bind_asset(
        WalkthroughLineage(
            product_id=_PRODUCT,
            spec_version=2,
            build_version=4,
            source_screenshot_sha256=("aa",),
            merchandising_version="m1",
            template_version="t1",
            output_sha256="cc",
            width_px=30,
            height_px=20,
            fps=30,
            scene_order=("dashboard",),
            scene_frames=(60,),
            qa_status="passed",
        )
    )
    assert video.kind == "walkthrough"
    assert video.page_count is None
    assert video.storage_uri == f"fixture://{_PRODUCT}/2/cc"

    pdf = bind_asset(
        DeliveryPdfLineage(
            product_id=_PRODUCT,
            spec_version=2,
            build_version=4,
            merchandising_version="m1",
            template_version="t1",
            output_sha256="dd",
            page_count=2,
            qa_status="passed",
            role="readme",
        )
    )
    assert pdf.kind == "delivery_pdf"
    assert pdf.width_px is None
    assert pdf.height_px is None
    assert pdf.page_count == 2
    assert pdf.source_screenshot_sha256 == ()
    assert pdf.storage_uri == f"fixture://{_PRODUCT}/2/dd"


def test_a_matching_asset_stays_current_beside_another_stale_screenshot() -> None:
    good = _shot("bb")
    image = _listing("cc", ("bb",))
    current, stale = split_current(
        (_root(), good, image),
        product_id=_PRODUCT,
        spec_version=2,
    )
    assert current == (good, image)
    assert current[0] is good
    assert tuple(asset.output_sha256 for asset in stale) == ("aa",)


def test_a_spec_bump_is_stale() -> None:
    asset = _shot("aa", spec=1)
    current, stale = split_current((asset,), product_id=_PRODUCT, spec_version=2)
    assert current == ()
    assert stale[0].qa_status == "stale"
    assert stale[0].output_sha256 == "aa"
    assert stale[0].storage_uri == asset.storage_uri


def test_another_product_is_omitted() -> None:
    mine = _shot("aa")
    current, stale = split_current(
        (mine, _shot("bb", product=_OTHER)),
        product_id=_PRODUCT,
        spec_version=2,
    )
    assert current == (mine,)
    assert stale == ()


def test_a_qa_status_other_than_passed_is_stale() -> None:
    asset = replace(_shot("aa"), qa_status="stale")
    current, stale = split_current((asset,), product_id=_PRODUCT, spec_version=2)
    assert current == ()
    assert stale[0].output_sha256 == "aa"


def test_a_stale_source_marks_the_dependent() -> None:
    image = _listing("bb", ("aa",))
    current, stale = split_current((_root(), image), product_id=_PRODUCT, spec_version=2)
    assert current == ()
    assert tuple(asset.output_sha256 for asset in stale) == ("aa", "bb")


def test_a_dependent_listed_before_its_source_is_stale() -> None:
    image = _listing("bb", ("aa",))
    current, stale = split_current((image, _root()), product_id=_PRODUCT, spec_version=2)
    assert current == ()
    assert tuple(asset.output_sha256 for asset in stale) == ("bb", "aa")
