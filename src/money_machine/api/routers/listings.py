"""Read-only path-redacted listing-package route."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from money_machine.api.dependencies import get_unit_of_work
from money_machine.api.schemas import ArtifactSummary, ListingResponse
from money_machine.domain.models.asset import ArtifactReference
from money_machine.persistence.unit_of_work import UnitOfWork

router = APIRouter(prefix="/listings", tags=["listings"])


def _artifact(reference: ArtifactReference | None) -> ArtifactSummary | None:
    if reference is None:
        return None
    return ArtifactSummary(
        artifact_id=reference.artifact_id,
        relative_path=reference.relative_path.as_posix(),
        media_type=reference.media_type,
        byte_count=reference.byte_count,
        sha256=reference.content_sha256,
    )


@router.get("/{listing_package_id}", response_model=ListingResponse)
async def get_listing(
    listing_package_id: str,
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ListingResponse:
    package = await uow.listings.get_package(listing_package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="listing not found")
    images = tuple(_artifact(image) for image in package.listing_images)
    if any(image is None for image in images):
        raise RuntimeError("listing image cannot be absent")
    return ListingResponse(
        listing_package_id=package.listing_package_id,
        product_spec_id=package.product_spec_id,
        build_id=package.build_id,
        title=package.title,
        description=package.description,
        tags=package.tags,
        feature_statements=package.feature_statements,
        buyer_fit_statements=package.buyer_fit_statements,
        listing_images=tuple(image for image in images if image is not None),
        preview_video=_artifact(package.preview_video),
        preview_video_status=package.preview_video_status,
        delivery_document=_artifact(package.delivery_document),
        package_manifest=_artifact(package.package_manifest),
        package_sha256=package.package_sha256,
    )
