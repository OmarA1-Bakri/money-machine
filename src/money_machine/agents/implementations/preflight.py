"""Fail-closed local draft preflight and durable handler."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast

from money_machine.agents.contracts.preflight import PreflightRequest, PreflightResponse
from money_machine.agents.implementations.creative_assets import (
    IMAGE_ROLES,
    RENDERER_VERSION,
    render_expected_delivery_pdf,
    render_expected_listing_image,
)
from money_machine.application.services.listing_service import (
    ListingService,
    copy_package_sha256,
    listing_claim_records,
    listing_package_sha256,
)
from money_machine.assets.pdf import pdf_page_count
from money_machine.assets.renderer import png_dimensions
from money_machine.assets.video import render_preview_video, validate_preview_video
from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.models.listing import ListingPackage, PreflightResult
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.value_objects import canonical_sha256
from money_machine.persistence.database import Database
from money_machine.persistence.unit_of_work import UnitOfWork


def _result_sha256(result: PreflightResult) -> str:
    return canonical_sha256(result.model_dump(mode="json", exclude={"result_sha256"}))


def _artifact_manifest(item: ArtifactReference) -> dict[str, object]:
    return {
        "path": item.relative_path.as_posix(),
        "media_type": item.media_type,
        "sha256": item.content_sha256,
        "byte_count": item.byte_count,
    }


class PreflightService:
    """Reopen every local artifact and deny incomplete or untruthful packages."""

    def __init__(self, artifact_root: Path) -> None:
        self._root = Path(os.path.abspath(artifact_root))
        self._root_fd = -1
        if not hasattr(os, "O_NOFOLLOW"):
            raise RuntimeError("preflight requires no-follow filesystem support")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptor = os.open(self._root.anchor, flags)
        try:
            for component in self._root.parts[1:]:
                next_descriptor = os.open(component, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_descriptor
        except OSError as error:
            os.close(descriptor)
            raise ValueError("artifact root contains a symlink or invalid component") from error
        self._root_fd = descriptor

    def close(self) -> None:
        """Release the directory capability after callers finish preflight."""

        if self._root_fd >= 0:
            os.close(self._root_fd)
            self._root_fd = -1

    def __del__(self) -> None:
        self.close()

    def _read_artifact(
        self,
        artifact: ArtifactReference,
        findings: list[str],
    ) -> bytes | None:
        relative = artifact.relative_path
        if (
            relative.is_absolute()
            or not relative.parts
            or any(component in {"", ".", ".."} for component in relative.parts)
        ):
            findings.append("NON_LOCAL_ARTIFACT_PATH")
            return None
        if self._root_fd < 0:
            raise RuntimeError("preflight service is closed")
        directory_fd = os.dup(self._root_fd)
        file_fd = -1
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            for component in relative.parts[:-1]:
                next_descriptor = os.open(component, directory_flags, dir_fd=directory_fd)
                os.close(directory_fd)
                directory_fd = next_descriptor
            file_fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
            metadata = os.fstat(file_fd)
            if not stat.S_ISREG(metadata.st_mode):
                findings.append("NON_LOCAL_ARTIFACT_PATH")
                return None
            chunks: list[bytes] = []
            while chunk := os.read(file_fd, 1024 * 1024):
                chunks.append(chunk)
            data = b"".join(chunks)
        except FileNotFoundError:
            findings.append("ARTIFACT_MISSING")
            return None
        except OSError:
            findings.append("NON_LOCAL_ARTIFACT_PATH")
            return None
        finally:
            if file_fd >= 0:
                os.close(file_fd)
            os.close(directory_fd)
        if (
            len(data) != artifact.byte_count
            or hashlib.sha256(data).hexdigest() != artifact.content_sha256
        ):
            findings.append("ARTIFACT_HASH_MISMATCH")
        if artifact.media_type.startswith("text/") or artifact.media_type in {
            "application/json",
            "application/pdf",
        }:
            lowered = data.lower()
            if b"http://" in lowered or b"https://" in lowered:
                findings.append("UNAPPROVED_REMOTE_LINK")
        return data

    @staticmethod
    def _expected_copy(
        package: ListingPackage,
        qa: ProductQAResult,
        spec: ProductSpec,
        build: BuildResult,
    ) -> ListingPackage:
        return ListingService().create(spec, build, qa)

    @staticmethod
    def _policy_findings(
        package: ListingPackage,
        qa: ProductQAResult,
        spec: ProductSpec,
        external_effect_mode: str,
        incremental_spend: Decimal | None,
        publication_receipt_present: bool,
    ) -> list[str]:
        findings: list[str] = []
        if not qa.passed:
            findings.append("PRODUCT_QA_FAILED")
        if qa.build_id != package.build_id:
            findings.append("QA_BUILD_MISMATCH")
        if spec.product_spec_id != package.product_spec_id:
            findings.append("PRODUCT_SPEC_MISMATCH")
        if external_effect_mode not in {"simulation", "draft"}:
            findings.append("EXTERNAL_EFFECT_MODE_DENIED")
        if incremental_spend is None:
            findings.append("INCREMENTAL_SPEND_UNKNOWN")
        elif incremental_spend != Decimal("0.00"):
            findings.append("INCREMENTAL_SPEND_NON_ZERO")
        if publication_receipt_present:
            findings.append("EXTERNAL_MUTATION_RECEIPT_PRESENT")
        if len(package.tags) != 13 or len(set(package.tags)) != 13:
            findings.append("TAG_COUNT_INVALID")
        if len(package.listing_images) != 10:
            findings.append("IMAGE_COUNT_INVALID")
        if package.delivery_document is None:
            findings.append("DELIVERY_PDF_MISSING")
        if package.package_manifest is None:
            findings.append("LINEAGE_MANIFEST_MISSING")
        if package.preview_video_status != "GENERATED" or package.preview_video is None:
            findings.append("VIDEO_REQUIRED")
        if listing_package_sha256(package) != package.package_sha256:
            findings.append("PACKAGE_HASH_MISMATCH")
        return findings

    def _copy_findings(
        self,
        package: ListingPackage,
        qa: ProductQAResult,
        spec: ProductSpec,
        build: BuildResult,
    ) -> list[str]:
        findings: list[str] = []
        if (
            qa.passed
            and qa.build_id == package.build_id
            and spec.product_spec_id == package.product_spec_id
        ):
            try:
                expected_copy = self._expected_copy(package, qa, spec, build)
            except ValueError:
                findings.append("UNSUPPORTED_CLAIM")
            else:
                fields = (
                    "listing_package_id",
                    "title",
                    "description",
                    "tags",
                    "feature_statements",
                    "buyer_fit_statements",
                )
                if any(
                    getattr(package, field) != getattr(expected_copy, field) for field in fields
                ):
                    findings.append("LISTING_COPY_MISMATCH")
        return findings

    def _image_findings(self, package: ListingPackage, spec: ProductSpec) -> list[str]:
        findings: list[str] = []
        paths = tuple(image.relative_path for image in package.listing_images)
        digests = tuple(image.content_sha256 for image in package.listing_images)
        if len(set(paths)) != len(paths):
            findings.append("IMAGE_PATH_DUPLICATE")
        if len(set(digests)) != len(digests):
            findings.append("IMAGE_DIGEST_DUPLICATE")
        for index, (role, image) in enumerate(
            zip(IMAGE_ROLES, package.listing_images, strict=False), start=1
        ):
            expected_path = (
                Path("listing") / package.listing_package_id / "images" / f"{index:02d}-{role}.png"
            )
            if image.relative_path != expected_path:
                findings.append("IMAGE_ROLE_MISMATCH")
            data = self._read_artifact(image, findings)
            if image.media_type != "image/png":
                findings.append("IMAGE_MEDIA_TYPE_INVALID")
            if data is not None:
                expected = render_expected_listing_image(
                    package,
                    spec,
                    role=role,
                    index=index,
                )
                if data != expected:
                    findings.append("IMAGE_RENDER_MISMATCH")
                try:
                    if png_dimensions(data) != (2000, 2000):
                        findings.append("IMAGE_DIMENSIONS_INVALID")
                except (OSError, ValueError):
                    findings.append("IMAGE_FORMAT_INVALID")
        return findings

    def _pdf_findings(
        self, package: ListingPackage, spec: ProductSpec, build: BuildResult
    ) -> list[str]:
        findings: list[str] = []
        if package.delivery_document is not None:
            data = self._read_artifact(package.delivery_document, findings)
            expected_path = (
                Path("listing") / package.listing_package_id / "delivery" / "README-access.pdf"
            )
            if package.delivery_document.relative_path != expected_path:
                findings.append("DELIVERY_ROLE_MISMATCH")
            if package.delivery_document.media_type != "application/pdf":
                findings.append("DELIVERY_MEDIA_TYPE_INVALID")
            if data is not None:
                if data != render_expected_delivery_pdf(package, spec, build):
                    findings.append("DELIVERY_RENDER_MISMATCH")
                try:
                    if pdf_page_count(data) != 2:
                        findings.append("DELIVERY_PDF_INVALID")
                except ValueError:
                    findings.append("DELIVERY_PDF_INVALID")
        return findings

    def _video_findings(
        self,
        package: ListingPackage,
        spec: ProductSpec,
        build: BuildResult,
    ) -> list[str]:
        findings: list[str] = []
        video = package.preview_video
        if video is None:
            return findings
        expected_path = Path("listing") / package.listing_package_id / "video" / "preview.mp4"
        if video.relative_path != expected_path:
            findings.append("VIDEO_ROLE_MISMATCH")
        if video.media_type != "video/mp4":
            findings.append("VIDEO_MEDIA_TYPE_INVALID")
        data = self._read_artifact(video, findings)
        if data is not None:
            try:
                validate_preview_video(data, package, spec, build)
            except ValueError:
                findings.append("VIDEO_RENDER_MISMATCH")
        return findings

    def _read_manifest(self, package: ListingPackage) -> tuple[object | None, list[str]]:
        findings: list[str] = []
        manifest_payload: object | None = None
        if package.package_manifest is not None:
            data = self._read_artifact(package.package_manifest, findings)
            if package.package_manifest.media_type != "application/json":
                findings.append("LINEAGE_MEDIA_TYPE_INVALID")
            if data is not None:
                try:
                    manifest_payload = cast(object, json.loads(data))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    findings.append("LINEAGE_MANIFEST_INVALID")
        return manifest_payload, findings

    @staticmethod
    def _expected_manifest(
        package: ListingPackage,
        spec: ProductSpec,
        build: BuildResult,
        findings: list[str],
    ) -> dict[str, object]:
        try:
            claims = listing_claim_records(spec, package)
        except ValueError:
            findings.append("UNSUPPORTED_CLAIM")
            claims = ()
        package_root = Path("listing") / package.listing_package_id
        artifacts: list[dict[str, object]] = []
        for index, role in enumerate(IMAGE_ROLES, start=1):
            data = render_expected_listing_image(package, spec, role=role, index=index)
            artifacts.append(
                {
                    "path": (package_root / "images" / f"{index:02d}-{role}.png").as_posix(),
                    "media_type": "image/png",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "byte_count": len(data),
                }
            )
        pdf_data = render_expected_delivery_pdf(package, spec, build)
        artifacts.append(
            {
                "path": (package_root / "delivery" / "README-access.pdf").as_posix(),
                "media_type": "application/pdf",
                "sha256": hashlib.sha256(pdf_data).hexdigest(),
                "byte_count": len(pdf_data),
            }
        )
        video_data = render_preview_video(package, spec, build)
        artifacts.append(
            {
                "path": (package_root / "video" / "preview.mp4").as_posix(),
                "media_type": "video/mp4",
                "sha256": hashlib.sha256(video_data).hexdigest(),
                "byte_count": len(video_data),
            }
        )
        return {
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
                "product_facts": [fact.model_dump(mode="json") for fact in spec.product_facts],
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
            "artifacts": artifacts,
            "preview_video_status": "GENERATED",
            "external_mutations": [],
            "incremental_spend": "0.00",
        }

    def _manifest_findings(
        self,
        package: ListingPackage,
        spec: ProductSpec,
        build: BuildResult,
    ) -> list[str]:
        manifest_payload, findings = self._read_manifest(package)
        if isinstance(manifest_payload, dict):
            expected_manifest = self._expected_manifest(package, spec, build, findings)
            manifest = cast(dict[str, object], manifest_payload)
            if manifest.get("copy_package_sha256") != expected_manifest["copy_package_sha256"]:
                findings.append("LINEAGE_COPY_HASH_MISMATCH")
            if manifest != expected_manifest:
                findings.append("LINEAGE_MANIFEST_MISMATCH")
        elif package.package_manifest is not None:
            findings.append("LINEAGE_MANIFEST_INVALID")
        return findings

    @staticmethod
    def _result(
        package: ListingPackage,
        findings: list[str],
        now: datetime | None,
        external_effect_mode: str,
    ) -> PreflightResult:
        ordered_findings = tuple(dict.fromkeys(findings))
        safe_mode: Literal["simulation", "draft"] = (
            "draft" if external_effect_mode == "draft" else "simulation"
        )
        draft = PreflightResult(
            preflight_result_id=f"preflight-{package.listing_package_id}",
            listing_package_id=package.listing_package_id,
            passed=not ordered_findings,
            findings=ordered_findings,
            checked_at=now or datetime.now(UTC),
            external_effect_mode=safe_mode,
            incremental_spend=Decimal("0.00"),
            publication_receipt_present=False,
            result_sha256="0" * 64,
        )
        return draft.model_copy(update={"result_sha256": _result_sha256(draft)})

    def evaluate(
        self,
        package: ListingPackage,
        qa: ProductQAResult,
        *,
        spec: ProductSpec,
        build: BuildResult,
        now: datetime | None = None,
        external_effect_mode: str = "simulation",
        incremental_spend: Decimal | None = Decimal("0.00"),
        publication_receipt_present: bool = False,
    ) -> PreflightResult:
        """Compose closed validators and deduplicate their stable findings."""

        findings = self._policy_findings(
            package,
            qa,
            spec,
            external_effect_mode,
            incremental_spend,
            publication_receipt_present,
        )
        if build.build_id != package.build_id or build.product_spec_id != package.product_spec_id:
            findings.append("BUILD_MISMATCH")
        findings.extend(self._copy_findings(package, qa, spec, build))
        findings.extend(self._image_findings(package, spec))
        findings.extend(self._pdf_findings(package, spec, build))
        findings.extend(self._video_findings(package, spec, build))
        findings.extend(self._manifest_findings(package, spec, build))
        return self._result(package, findings, now, external_effect_mode)


async def handle_preflight(request: PreflightRequest) -> PreflightResponse:
    service = PreflightService(request.artifact_root)
    try:
        result = service.evaluate(
            request.package,
            request.qa,
            spec=request.spec,
            build=request.build,
            now=request.checked_at,
            external_effect_mode=request.external_effect_mode,
            incremental_spend=request.incremental_spend,
            publication_receipt_present=request.publication_receipt_present,
        )
    finally:
        service.close()
    database = Database.from_url(request.database_url)
    try:
        async with UnitOfWork(database) as unit_of_work:
            await unit_of_work.listings.add_preflight(result)
    finally:
        await database.dispose()
    if result.passed:
        return PreflightResponse(result=result, event_name="DRAFT_READY", successor_job_type=None)
    blocker_codes = {
        "PRODUCT_QA_FAILED",
        "QA_BUILD_MISMATCH",
        "PRODUCT_SPEC_MISMATCH",
        "EXTERNAL_EFFECT_MODE_DENIED",
        "INCREMENTAL_SPEND_UNKNOWN",
        "INCREMENTAL_SPEND_NON_ZERO",
        "EXTERNAL_MUTATION_RECEIPT_PRESENT",
    }
    if blocker_codes.intersection(result.findings):
        return PreflightResponse(result=result, event_name="BLOCKED", successor_job_type=None)
    return PreflightResponse(
        result=result,
        event_name="REPAIR_REQUIRED",
        successor_job_type="REPAIR_LISTING_PACKAGE",
    )
