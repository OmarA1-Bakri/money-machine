"""Deterministic, root-confined local listing asset factory and handler."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from contextlib import suppress
from pathlib import Path

from money_machine.agents.contracts.creative_assets import (
    CreativeAssetRequest,
    CreativeAssetResponse,
)
from money_machine.application.services.listing_service import (
    copy_package_sha256,
    listing_claim_records,
    listing_package_sha256,
)
from money_machine.assets.pdf import render_delivery_pdf
from money_machine.assets.renderer import render_listing_png
from money_machine.assets.video import video_status
from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.models.listing import ListingPackage
from money_machine.domain.models.product import BuildResult
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.persistence.database import Database
from money_machine.persistence.unit_of_work import UnitOfWork

IMAGE_ROLES = (
    "hero",
    "walkthrough-overview",
    "hub-one",
    "hub-two",
    "hub-three",
    "hub-four",
    "hub-five",
    "colour-options",
    "devices",
    "how-it-works",
)
RENDERER_VERSION = "listing-pillow-fpdf2-v2"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _reference(relative_path: Path, data: bytes, media_type: str) -> ArtifactReference:
    digest = hashlib.sha256(data).hexdigest()
    return ArtifactReference(
        artifact_id=f"asset-{digest[:24]}",
        relative_path=relative_path,
        media_type=media_type,
        byte_count=len(data),
        content_sha256=digest,
    )


def _artifact_manifest(item: ArtifactReference) -> dict[str, object]:
    return {
        "path": item.relative_path.as_posix(),
        "media_type": item.media_type,
        "sha256": item.content_sha256,
        "byte_count": item.byte_count,
    }


class _ArtifactWriter:
    """Write only through pinned, no-follow directory capabilities."""

    def __init__(self, destination: Path) -> None:
        if not hasattr(os, "O_NOFOLLOW"):
            raise RuntimeError("asset rendering requires no-follow filesystem support")
        absolute = Path(os.path.abspath(destination))
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptor = os.open(absolute.anchor, flags)
        try:
            for component in absolute.parts[1:]:
                try:
                    next_descriptor = os.open(component, flags, dir_fd=descriptor)
                except FileNotFoundError:
                    os.mkdir(component, dir_fd=descriptor)
                    next_descriptor = os.open(component, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_descriptor
        except OSError as error:
            os.close(descriptor)
            raise ValueError("asset destination contains a symlink or invalid component") from error
        self._root_fd = descriptor

    def close(self) -> None:
        if self._root_fd >= 0:
            os.close(self._root_fd)
            self._root_fd = -1

    def _directory(self, relative: Path) -> int:
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise ValueError("artifact path must be root-confined")
        descriptor = os.dup(self._root_fd)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            for component in relative.parts:
                try:
                    next_descriptor = os.open(component, flags, dir_fd=descriptor)
                except FileNotFoundError:
                    os.mkdir(component, dir_fd=descriptor)
                    next_descriptor = os.open(component, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_descriptor
        except OSError as error:
            os.close(descriptor)
            raise ValueError("artifact path contains a symlink or invalid component") from error
        return descriptor

    @staticmethod
    def _target_matches(parent_fd: int, name: str, data: bytes) -> bool:
        target_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            if not stat.S_ISREG(os.fstat(target_fd).st_mode):
                raise ValueError("artifact target must be a regular file")
            chunks: list[bytes] = []
            while chunk := os.read(target_fd, 1024 * 1024):
                chunks.append(chunk)
            return b"".join(chunks) == data
        finally:
            os.close(target_fd)

    def write(self, relative: Path, data: bytes) -> None:
        if (
            relative.is_absolute()
            or not relative.name
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise ValueError("artifact path must be root-confined")
        parent_fd = self._directory(relative.parent)
        temporary_name = f".{relative.name}.{hashlib.sha256(data).hexdigest()[:16]}.tmp"
        temporary_created = False
        try:
            try:
                matches = self._target_matches(parent_fd, relative.name, data)
            except FileNotFoundError:
                pass
            else:
                if matches:
                    return
                raise ValueError(f"artifact collision at {relative.as_posix()}")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
            file_fd = os.open(temporary_name, flags, 0o600, dir_fd=parent_fd)
            temporary_created = True
            try:
                view = memoryview(data)
                while view:
                    written = os.write(file_fd, view)
                    view = view[written:]
                os.fsync(file_fd)
            finally:
                os.close(file_fd)
            try:
                os.link(
                    temporary_name,
                    relative.name,
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileExistsError:
                if not self._target_matches(parent_fd, relative.name, data):
                    raise ValueError(f"artifact collision at {relative.as_posix()}") from None
            os.unlink(temporary_name, dir_fd=parent_fd)
            temporary_created = False
            os.fsync(parent_fd)
        finally:
            if temporary_created:
                with suppress(FileNotFoundError):
                    os.unlink(temporary_name, dir_fd=parent_fd)
                    os.fsync(parent_fd)
            os.close(parent_fd)


def _image_detail(role: str, index: int, spec: ProductSpec) -> str:
    if role.startswith("hub-"):
        return spec.hubs[(index - 3) % len(spec.hubs)]
    if role == "colour-options":
        return ", ".join(spec.colour_variants)
    if role == "devices":
        return f"Local files for {spec.target_buyer}"
    if role == "how-it-works":
        return spec.promised_outcome
    return spec.product_facts[(index - 1) % len(spec.product_facts)]


def render_expected_listing_image(
    package: ListingPackage,
    spec: ProductSpec,
    *,
    role: str,
    index: int,
) -> bytes:
    """Reconstruct the renderer-bound bytes for one declared semantic role."""

    return render_listing_png(
        role,
        index=index,
        title=package.title,
        detail=_image_detail(role, index, spec),
    )


def render_expected_delivery_pdf(
    package: ListingPackage,
    spec: ProductSpec,
    build: BuildResult,
) -> bytes:
    """Reconstruct the spec- and build-bound delivery guide bytes."""

    inventory = tuple(
        f"{artifact.relative_path.as_posix()} ({artifact.media_type})"
        for artifact in build.artifacts
    )
    return render_delivery_pdf(
        title=package.title,
        hubs=spec.hubs,
        colours=spec.colour_variants,
        inventory=inventory,
        support_information="Support information and a duplication reminder are included.",
    )


class CreativeAssetService:
    """Render ten Pillow PNGs, one fpdf2 PDF, and complete local lineage."""

    def render(
        self,
        package: ListingPackage,
        destination: Path,
        *,
        spec: ProductSpec,
        build: BuildResult,
    ) -> ListingPackage:
        if not _SAFE_ID.fullmatch(package.listing_package_id) or package.listing_package_id in {
            ".",
            "..",
        }:
            raise ValueError("listing package id must be a path-safe slug")
        if spec.product_spec_id != package.product_spec_id:
            raise ValueError("ProductSpec does not match listing package")
        if build.build_id != package.build_id or build.product_spec_id != package.product_spec_id:
            raise ValueError("build does not match listing package")
        if not spec.product_facts:
            raise ValueError("ProductSpec must contain admitted product facts")
        claims = listing_claim_records(spec, package)
        package_root = Path("listing") / package.listing_package_id
        writer = _ArtifactWriter(destination)
        try:
            images: list[ArtifactReference] = []
            for index, role in enumerate(IMAGE_ROLES, start=1):
                relative = package_root / "images" / f"{index:02d}-{role}.png"
                data = render_expected_listing_image(package, spec, role=role, index=index)
                writer.write(relative, data)
                images.append(_reference(relative, data, "image/png"))

            pdf_relative = package_root / "delivery" / "README-access.pdf"
            pdf_data = render_expected_delivery_pdf(package, spec, build)
            writer.write(pdf_relative, pdf_data)
            delivery = _reference(pdf_relative, pdf_data, "application/pdf")

            manifest_relative = package_root / "manifest.json"
            manifest_payload = {
                "schema_version": 1,
                "listing_package_id": package.listing_package_id,
                "product_spec_id": package.product_spec_id,
                "build_id": package.build_id,
                "copy_package_sha256": copy_package_sha256(package),
                "renderer_version": RENDERER_VERSION,
                "build_inventory": [_artifact_manifest(item) for item in build.artifacts],
                "dimensions": [2000, 2000],
                "image_roles": list(IMAGE_ROLES),
                "product_context": {
                    "identity_niche": spec.identity_niche,
                    "base_category": spec.base_category,
                    "target_buyer": spec.target_buyer,
                    "promised_outcome": spec.promised_outcome,
                    "hubs": list(spec.hubs),
                    "colour_variants": list(spec.colour_variants),
                    "product_facts": list(spec.product_facts),
                },
                "claims": [
                    {
                        "claim": record.claim,
                        "source": record.source,
                        "fact_index": record.fact_index,
                        "fact_category": record.fact_category,
                        "evidence_ids": list(record.evidence_ids),
                    }
                    for record in claims
                ],
                "artifacts": [
                    {
                        "path": item.relative_path.as_posix(),
                        "media_type": item.media_type,
                        "sha256": item.content_sha256,
                        "byte_count": item.byte_count,
                    }
                    for item in (*images, delivery)
                ],
                "preview_video_status": video_status(),
                "external_mutations": [],
                "incremental_spend": "0.00",
            }
            manifest_data = json.dumps(
                manifest_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
            writer.write(manifest_relative, manifest_data)
            manifest = _reference(manifest_relative, manifest_data, "application/json")

            rendered = package.model_copy(
                update={
                    "listing_images": tuple(images),
                    "delivery_document": delivery,
                    "package_manifest": manifest,
                    "preview_video": None,
                    "preview_video_status": video_status(),
                    "package_sha256": "0" * 64,
                }
            )
            return rendered.model_copy(update={"package_sha256": listing_package_sha256(rendered)})
        finally:
            writer.close()


async def handle_creative_assets(request: CreativeAssetRequest) -> CreativeAssetResponse:
    if not request.qa.passed or request.qa.build_id != request.package.build_id:
        raise ValueError("product QA must pass before listing assets are persisted")
    package = CreativeAssetService().render(
        request.package,
        request.destination,
        spec=request.spec,
        build=request.build,
    )
    database = Database.from_url(request.database_url)
    try:
        async with UnitOfWork(database) as unit_of_work:
            await unit_of_work.listings.add_package(package)
    finally:
        await database.dispose()
    return CreativeAssetResponse(package=package)
