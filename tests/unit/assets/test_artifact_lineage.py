"""Fixture artifact lineage. No renderer, no network, no golden bytes."""

from __future__ import annotations

from uuid import UUID

import pytest

from money_machine.assets.artifact_lineage import (
    ArtifactLineage,
    ArtifactLineageRefusal,
    invalidate_product_change,
    record_lineage,
)

_PRODUCT = UUID("00000000-0000-4000-8000-000000000001")
_OTHER = UUID("00000000-0000-4000-8000-000000000002")
_SHOT = "a" * 64
_IMAGE = "b" * 64
_VIDEO = "c" * 64
_PDF = "d" * 64


def _shot(*, spec_version: int = 2, product_id: UUID = _PRODUCT, digest: str = _SHOT):
    return record_lineage(
        product_id=product_id,
        spec_version=spec_version,
        build_version=5,
        source_screenshots=(digest,),
        merchandising_version="merch-2",
        template_version="s08-w5-screenshot-1",
        content_sha256=digest,
        dimensions=(480, 270),
        page_count=None,
        kind="screenshot",
    )


def _image(*, spec_version: int = 2, sources: tuple[str, ...] = (_SHOT,)):
    return record_lineage(
        product_id=_PRODUCT,
        spec_version=spec_version,
        build_version=5,
        source_screenshots=sources,
        merchandising_version="merch-2",
        template_version="s08-w2-listing-1",
        content_sha256=_IMAGE,
        dimensions=(2000, 2000),
        page_count=None,
        kind="listing_image",
    )


def _video():
    return record_lineage(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=5,
        source_screenshots=(_IMAGE,),
        merchandising_version="merch-2",
        template_version="s08-w4-video-1",
        content_sha256=_VIDEO,
        dimensions=(160, 90),
        page_count=None,
        kind="walkthrough",
    )


def _pdf():
    return record_lineage(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=4,
        source_screenshots=(),
        merchandising_version="merch-2",
        template_version="s08-w3-pdf-1",
        content_sha256=_PDF,
        dimensions=None,
        page_count=2,
        kind="delivery_pdf",
    )


def _refuse(**kwargs: object) -> ArtifactLineageRefusal:
    with pytest.raises(ArtifactLineageRefusal) as caught:
        record_lineage(**kwargs)  # type: ignore[arg-type]
    return caught.value


def test_a_screenshot_record_stores_every_lineage_field() -> None:
    record = _shot()
    assert record.product_id == _PRODUCT
    assert record.spec_version == 2
    assert record.build_version == 5
    assert record.source_screenshots == (_SHOT,)
    assert record.merchandising_version == "merch-2"
    assert record.template_version == "s08-w5-screenshot-1"
    assert record.merchandising_version != record.template_version
    assert record.content_sha256 == _SHOT
    assert record.dimensions == (480, 270)
    assert record.page_count is None
    assert record.qa_status == "passed"
    assert record.kind == "screenshot"
    assert record.storage_uri == (f"fixture://{_PRODUCT}/spec/2/build/5/screenshot/{_SHOT}")


def test_a_pdf_record_stores_page_count() -> None:
    record = _pdf()
    assert record.page_count == 2
    assert record.dimensions is None
    assert record.source_screenshots == ()
    assert record.template_version == "s08-w3-pdf-1"
    assert record.storage_uri == (f"fixture://{_PRODUCT}/spec/2/build/4/delivery_pdf/{_PDF}")


@pytest.mark.parametrize(
    "uri",
    ("s3://bucket/x", "http://fixture.example/x", "https://fixture.example/x", "file:///tmp/x"),
)
def test_live_storage_is_refused(uri: str) -> None:
    record = _shot()
    with pytest.raises(ArtifactLineageRefusal) as caught:
        ArtifactLineage(
            product_id=record.product_id,
            spec_version=record.spec_version,
            build_version=record.build_version,
            source_screenshots=record.source_screenshots,
            merchandising_version=record.merchandising_version,
            template_version=record.template_version,
            content_sha256=record.content_sha256,
            dimensions=record.dimensions,
            page_count=record.page_count,
            qa_status="passed",
            storage_uri=uri,
            kind=record.kind,
        )
    assert caught.value.code == "live_storage"


def test_a_storage_uri_must_name_the_hash() -> None:
    record = _shot()
    wrong = record.storage_uri.replace(_SHOT, _IMAGE)
    with pytest.raises(ArtifactLineageRefusal) as caught:
        ArtifactLineage(
            product_id=record.product_id,
            spec_version=record.spec_version,
            build_version=record.build_version,
            source_screenshots=record.source_screenshots,
            merchandising_version=record.merchandising_version,
            template_version=record.template_version,
            content_sha256=record.content_sha256,
            dimensions=record.dimensions,
            page_count=record.page_count,
            qa_status="passed",
            storage_uri=wrong,
            kind=record.kind,
        )
    assert caught.value.code == "storage_uri"


def test_a_screenshot_without_dimensions_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=5,
        source_screenshots=(_SHOT,),
        merchandising_version="merch-2",
        template_version="s08-w5-screenshot-1",
        content_sha256=_SHOT,
        dimensions=None,
        page_count=None,
        kind="screenshot",
    )
    assert refusal.code == "measure"


def test_a_pdf_with_dimensions_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=4,
        source_screenshots=(),
        merchandising_version="merch-2",
        template_version="s08-w3-pdf-1",
        content_sha256=_PDF,
        dimensions=(1, 1),
        page_count=2,
        kind="delivery_pdf",
    )
    assert refusal.code == "pdf_measure"


def test_a_screenshot_must_name_its_own_hash() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=5,
        source_screenshots=(_IMAGE,),
        merchandising_version="merch-2",
        template_version="s08-w5-screenshot-1",
        content_sha256=_SHOT,
        dimensions=(480, 270),
        page_count=None,
        kind="screenshot",
    )
    assert refusal.code == "screenshot_source"


def test_a_listing_image_without_a_screenshot_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=5,
        source_screenshots=(),
        merchandising_version="merch-2",
        template_version="s08-w2-listing-1",
        content_sha256=_IMAGE,
        dimensions=(2000, 2000),
        page_count=None,
        kind="listing_image",
    )
    assert refusal.code == "listing_source"


def test_a_walkthrough_without_a_screenshot_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=5,
        source_screenshots=(),
        merchandising_version="merch-2",
        template_version="s08-w4-video-1",
        content_sha256=_VIDEO,
        dimensions=(160, 90),
        page_count=None,
        kind="walkthrough",
    )
    assert refusal.code == "walkthrough_source"


def test_a_source_hash_must_be_lowercase_hex() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=5,
        source_screenshots=("gg",),
        merchandising_version="merch-2",
        template_version="s08-w2-listing-1",
        content_sha256=_IMAGE,
        dimensions=(2000, 2000),
        page_count=None,
        kind="listing_image",
    )
    assert refusal.code == "sources"


def test_a_blank_merchandising_version_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=5,
        source_screenshots=(_SHOT,),
        merchandising_version="",
        template_version="s08-w5-screenshot-1",
        content_sha256=_SHOT,
        dimensions=(480, 270),
        page_count=None,
        kind="screenshot",
    )
    assert refusal.code == "merchandising_version"


def test_a_blank_template_version_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=5,
        source_screenshots=(_SHOT,),
        merchandising_version="merch-2",
        template_version="",
        content_sha256=_SHOT,
        dimensions=(480, 270),
        page_count=None,
        kind="screenshot",
    )
    assert refusal.code == "template_version"


def test_a_screenshot_with_a_page_count_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=5,
        source_screenshots=(_SHOT,),
        merchandising_version="merch-2",
        template_version="s08-w5-screenshot-1",
        content_sha256=_SHOT,
        dimensions=(480, 270),
        page_count=1,
        kind="screenshot",
    )
    assert refusal.code == "measure"


def test_a_screenshot_with_a_zero_dimension_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=5,
        source_screenshots=(_SHOT,),
        merchandising_version="merch-2",
        template_version="s08-w5-screenshot-1",
        content_sha256=_SHOT,
        dimensions=(0, 270),
        page_count=None,
        kind="screenshot",
    )
    assert refusal.code == "measure"


def test_a_pdf_without_a_page_count_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=4,
        source_screenshots=(),
        merchandising_version="merch-2",
        template_version="s08-w3-pdf-1",
        content_sha256=_PDF,
        dimensions=None,
        page_count=None,
        kind="delivery_pdf",
    )
    assert refusal.code == "pdf_measure"


def test_a_pdf_with_zero_pages_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=4,
        source_screenshots=(),
        merchandising_version="merch-2",
        template_version="s08-w3-pdf-1",
        content_sha256=_PDF,
        dimensions=None,
        page_count=0,
        kind="delivery_pdf",
    )
    assert refusal.code == "pdf_measure"


def test_a_spec_version_below_one_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=0,
        build_version=5,
        source_screenshots=(_SHOT,),
        merchandising_version="merch-2",
        template_version="s08-w5-screenshot-1",
        content_sha256=_SHOT,
        dimensions=(480, 270),
        page_count=None,
        kind="screenshot",
    )
    assert refusal.code == "spec_version"


def test_a_build_version_below_one_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=0,
        source_screenshots=(_SHOT,),
        merchandising_version="merch-2",
        template_version="s08-w5-screenshot-1",
        content_sha256=_SHOT,
        dimensions=(480, 270),
        page_count=None,
        kind="screenshot",
    )
    assert refusal.code == "build_version"


def test_a_qa_status_must_be_passed_or_stale() -> None:
    record = _shot()
    with pytest.raises(ArtifactLineageRefusal) as caught:
        ArtifactLineage(
            product_id=record.product_id,
            spec_version=record.spec_version,
            build_version=record.build_version,
            source_screenshots=record.source_screenshots,
            merchandising_version=record.merchandising_version,
            template_version=record.template_version,
            content_sha256=record.content_sha256,
            dimensions=record.dimensions,
            page_count=record.page_count,
            qa_status="held",  # type: ignore[arg-type]
            storage_uri=record.storage_uri,
            kind=record.kind,
        )
    assert caught.value.code == "qa_status"


def test_a_short_hash_is_refused() -> None:
    refusal = _refuse(
        product_id=_PRODUCT,
        spec_version=2,
        build_version=5,
        source_screenshots=("aa",),
        merchandising_version="merch-2",
        template_version="s08-w5-screenshot-1",
        content_sha256="aa",
        dimensions=(480, 270),
        page_count=None,
        kind="screenshot",
    )
    assert refusal.code == "hash"


def test_an_older_spec_is_stale() -> None:
    older = _shot(spec_version=1)
    current = _shot(spec_version=2)
    result = invalidate_product_change((older, current), {}, product_id=_PRODUCT, spec_version=2)
    assert result[0].qa_status == "stale"
    assert result[0].content_sha256 == older.content_sha256
    assert result[0].spec_version == 1


def test_the_current_spec_stays_passed() -> None:
    current = _shot(spec_version=2)
    result = invalidate_product_change((current,), {}, product_id=_PRODUCT, spec_version=2)
    assert result[0].qa_status == "passed"
    assert result[0].storage_uri == current.storage_uri


def test_another_product_stays_passed() -> None:
    other = _shot(spec_version=1, product_id=_OTHER)
    result = invalidate_product_change((other,), {}, product_id=_PRODUCT, spec_version=2)
    assert result[0].qa_status == "passed"
    assert result[0].product_id == _OTHER


def test_an_already_stale_asset_marks_its_dependent() -> None:
    shot = _shot()
    image = _image()
    stale_shot = ArtifactLineage(
        product_id=shot.product_id,
        spec_version=shot.spec_version,
        build_version=shot.build_version,
        source_screenshots=shot.source_screenshots,
        merchandising_version=shot.merchandising_version,
        template_version=shot.template_version,
        content_sha256=shot.content_sha256,
        dimensions=shot.dimensions,
        page_count=shot.page_count,
        qa_status="stale",
        storage_uri=shot.storage_uri,
        kind=shot.kind,
    )
    result = invalidate_product_change(
        (stale_shot, image),
        {image.storage_uri: (stale_shot.storage_uri,)},
        product_id=_PRODUCT,
        spec_version=2,
    )
    assert result[0].qa_status == "stale"
    assert result[1].qa_status == "stale"
    assert result[1].content_sha256 == _IMAGE


def test_a_transitive_dependent_is_stale() -> None:
    older = _shot(spec_version=1)
    image = _image()
    video = _video()
    dependencies = {
        image.storage_uri: (older.storage_uri,),
        video.storage_uri: (image.storage_uri,),
    }
    result = invalidate_product_change(
        (older, video, image),
        dependencies,
        product_id=_PRODUCT,
        spec_version=2,
    )
    assert [item.qa_status for item in result] == ["stale", "stale", "stale"]
    assert result[1].content_sha256 == _VIDEO
    assert result[1].spec_version == 2
    assert result[2].source_screenshots == (_SHOT,)
