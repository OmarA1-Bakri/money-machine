"""Materialize one durable DRAFT_READY workflow as an immutable local product package."""

from __future__ import annotations

import hashlib
import os
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import UUID

from money_machine.agents.registry import FirstProductResultStore
from money_machine.domain.enums import ProductState
from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.models.candidate import CandidateShortlist, QualificationScore
from money_machine.domain.models.listing import ListingPackage, PreflightResult
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_export import (
    ProductExportFile,
    ProductExportManifest,
    ProductExportReceipt,
    ProductExportResult,
    QualificationExport,
)
from money_machine.domain.models.product_spec import DedupeResult, ProductSpec
from money_machine.domain.models.research import ResearchPacket
from money_machine.domain.models.workflow import WorkflowRun
from money_machine.domain.value_objects import FrozenModel, canonical_json, canonical_sha256
from money_machine.integrations.storage.local import LocalArtifactStore
from money_machine.orchestration.workflows.product_experiment import FIRST_PRODUCT_STEP_OUTPUTS
from money_machine.persistence.database import Database
from money_machine.persistence.unit_of_work import UnitOfWork

_WORKFLOW_TYPE = "FIRST_PRODUCT_VERTICAL_SLICE"
type SourceKind = Literal["durable_result", "build_artifact", "listing_artifact", "derived"]
type ExportPayload = tuple[bytes, str, SourceKind, str]


class ProductExportService:
    """Project exact durable results and verified local bytes into one review package."""

    def __init__(self, database: Database, artifact_root: Path) -> None:
        self._database = database
        self._artifact_root = Path(os.path.abspath(artifact_root))
        self._results = FirstProductResultStore(database)

    async def export(self, workflow_run_id: UUID) -> ProductExportReceipt:
        workflow, scores, durable_artifacts = await self._load_export_context(workflow_run_id)
        if workflow.workflow_type != _WORKFLOW_TYPE:
            raise ValueError("workflow is not FIRST_PRODUCT_VERTICAL_SLICE")
        if workflow.state is not ProductState.DRAFT_READY:
            raise ValueError("workflow is not DRAFT_READY")

        packet = await self._results.load_result(
            workflow_run_id, "ADMIT_RESEARCH_PACKET", ResearchPacket
        )
        shortlist = await self._results.load_result(
            workflow_run_id, "QUALIFY_CANDIDATES", CandidateShortlist
        )
        spec = await self._results.load_result(workflow_run_id, "CREATE_PRODUCT_SPEC", ProductSpec)
        dedupe = await self._results.load_result(
            workflow_run_id, "CHECK_CATALOGUE_DEDUPE", DedupeResult
        )
        build = await self._results.load_result(workflow_run_id, "BUILD_PRODUCT", BuildResult)
        qa = await self._results.load_result(workflow_run_id, "RUN_PRODUCT_QA", ProductQAResult)
        listing = await self._results.load_result(
            workflow_run_id, "CREATE_LISTING_PACKAGE", ListingPackage
        )
        preflight = await self._results.load_result(
            workflow_run_id, "RUN_PREFLIGHT", PreflightResult
        )

        self._validate_business_contract(
            workflow_packet_id=workflow.packet_id,
            packet=packet,
            scores=scores,
            shortlist=shortlist,
            spec=spec,
            dedupe=dedupe,
            build=build,
            qa=qa,
            listing=listing,
            preflight=preflight,
            durable_artifacts=durable_artifacts,
            workflow_run_id=workflow_run_id,
        )
        return self._materialize(
            workflow_run_id=workflow_run_id,
            packet=packet,
            shortlist=shortlist,
            spec=spec,
            dedupe=dedupe,
            build=build,
            qa=qa,
            listing=listing,
            preflight=preflight,
        )

    async def _load_export_context(
        self, workflow_run_id: UUID
    ) -> tuple[WorkflowRun, tuple[QualificationScore, ...], tuple[ArtifactReference, ...]]:
        async with UnitOfWork(self._database) as uow:
            workflow = await uow.workflows.get(workflow_run_id)
            if workflow is None:
                raise ValueError("workflow does not exist")
            scores = await uow.research.list_scores(workflow.packet_id)
            artifacts = await uow.artifacts.list_for_workflow(workflow_run_id)
        return workflow, scores, artifacts

    def _validate_business_contract(
        self,
        *,
        workflow_packet_id: str,
        packet: ResearchPacket,
        scores: tuple[QualificationScore, ...],
        shortlist: CandidateShortlist,
        spec: ProductSpec,
        dedupe: DedupeResult,
        build: BuildResult,
        qa: ProductQAResult,
        listing: ListingPackage,
        preflight: PreflightResult,
        durable_artifacts: tuple[ArtifactReference, ...],
        workflow_run_id: UUID,
    ) -> None:
        if packet.packet_id != workflow_packet_id or shortlist.packet_id != packet.packet_id:
            raise ValueError("export packet lineage mismatch")
        if _canonical_model_set(scores) != _canonical_model_set(shortlist.candidates):
            raise ValueError("persisted qualification scores do not match shortlist")
        if len(shortlist.candidates) != 5:
            raise ValueError("export requires exactly five shortlisted candidates")
        primary, _ = _selected_scores(shortlist)
        if primary.total < 30:
            raise ValueError("export selection does not meet qualification threshold")
        if spec.candidate_id != primary.candidate_id:
            raise ValueError("ProductSpec does not match selected candidate")
        spec.ensure_truth_contract()
        if not dedupe.passed or dedupe.product_spec_id != spec.product_spec_id:
            raise ValueError("export requires passing catalogue dedupe")
        expected_build_root = self._artifact_root / str(workflow_run_id) / "product"
        if Path(build.root_artifact_path) != expected_build_root:
            raise ValueError("build root does not match configured workflow artifact root")
        if build.product_spec_id != spec.product_spec_id:
            raise ValueError("build does not match ProductSpec")
        if not qa.passed or qa.build_id != build.build_id:
            raise ValueError("export requires passing product QA")
        if (
            listing.product_spec_id != spec.product_spec_id
            or listing.build_id != build.build_id
            or len(listing.tags) != 13
            or len(listing.listing_images) != 10
            or len({item.content_sha256 for item in listing.listing_images}) != 10
            or listing.preview_video_status != "GENERATED"
            or listing.preview_video is None
            or listing.delivery_document is None
            or listing.package_manifest is None
        ):
            raise ValueError("listing package is not complete or lineage-bound")
        if (
            not preflight.passed
            or preflight.listing_package_id != listing.listing_package_id
            or preflight.incremental_spend != Decimal("0.00")
            or preflight.publication_receipt_present
        ):
            raise ValueError("export requires passing zero-effect preflight")
        expected_artifacts = (
            *build.artifacts,
            *listing.listing_images,
            listing.preview_video,
            listing.delivery_document,
            listing.package_manifest,
        )
        if _canonical_model_set(durable_artifacts) != _canonical_model_set(expected_artifacts):
            raise ValueError("durable artifact inventory does not match typed results")

    def _materialize(
        self,
        *,
        workflow_run_id: UUID,
        packet: ResearchPacket,
        shortlist: CandidateShortlist,
        spec: ProductSpec,
        dedupe: DedupeResult,
        build: BuildResult,
        qa: ProductQAResult,
        listing: ListingPackage,
        preflight: PreflightResult,
    ) -> ProductExportReceipt:
        primary, backup = _selected_scores(shortlist)
        source_store = LocalArtifactStore(self._artifact_root)
        prefix = PurePosixPath("products") / spec.product_spec_id
        payloads: dict[str, ExportPayload] = {}

        def add(
            relative_path: str,
            data: bytes,
            media_type: str,
            source_kind: SourceKind,
            source_id: str,
        ) -> None:
            if relative_path in payloads:
                raise ValueError(f"duplicate export path: {relative_path}")
            payloads[relative_path] = (data, media_type, source_kind, source_id)

        add(
            "research/packet.json",
            canonical_json(packet),
            "application/json",
            "durable_result",
            packet.packet_id,
        )
        add(
            "shortlist.json",
            canonical_json(shortlist),
            "application/json",
            "durable_result",
            shortlist.shortlist_id,
        )
        qualification = QualificationExport(
            packet_id=packet.packet_id,
            shortlist_id=shortlist.shortlist_id,
            scores=shortlist.candidates,
        )
        add(
            "qualification.json",
            canonical_json(qualification),
            "application/json",
            "derived",
            shortlist.shortlist_id,
        )
        add(
            "primary.json",
            canonical_json(primary),
            "application/json",
            "durable_result",
            primary.candidate_id,
        )
        if backup is not None:
            add(
                "backup.json",
                canonical_json(backup),
                "application/json",
                "durable_result",
                backup.candidate_id,
            )
        for path, model, identity in (
            ("product-spec.json", spec, spec.product_spec_id),
            ("dedupe-result.json", dedupe, dedupe.dedupe_result_id),
            ("qa-result.json", qa, qa.qa_result_id),
            ("listing/listing-package.json", listing, listing.listing_package_id),
            ("preflight-result.json", preflight, preflight.preflight_result_id),
        ):
            add(path, canonical_json(model), "application/json", "durable_result", identity)

        workflow_prefix = PurePosixPath(str(workflow_run_id))
        for artifact in build.artifacts:
            source = workflow_prefix / "product" / artifact.relative_path.as_posix()
            data = source_store.get_bytes(
                source,
                expected_sha256=artifact.content_sha256,
                expected_byte_count=artifact.byte_count,
            )
            destination = f"product/{artifact.relative_path.as_posix()}"
            add(
                destination,
                data,
                artifact.media_type,
                "build_artifact",
                artifact.artifact_id,
            )
            if artifact.relative_path.parent.as_posix() == "assets" and artifact.media_type == (
                "text/css"
            ):
                add(
                    f"variants/{artifact.relative_path.name}",
                    data,
                    artifact.media_type,
                    "build_artifact",
                    artifact.artifact_id,
                )
        build_manifest = source_store.get_bytes(
            workflow_prefix / "product" / "manifest.json",
            expected_sha256=build.manifest_sha256,
        )
        add(
            "product/manifest.json",
            build_manifest,
            "application/json",
            "build_artifact",
            build.build_id,
        )
        if len([path for path in payloads if path.startswith("variants/")]) != len(
            spec.colour_variants
        ):
            raise ValueError("export variant inventory does not match ProductSpec")

        for index, artifact in enumerate(listing.listing_images, start=1):
            data = _read_listing_artifact(source_store, artifact, workflow_prefix, listing)
            add(
                f"images/{index:02d}-{artifact.relative_path.name}",
                data,
                artifact.media_type,
                "listing_artifact",
                artifact.artifact_id,
            )
        if listing.preview_video is None:
            raise ValueError("listing preview video is absent")
        video_data = _read_listing_artifact(
            source_store, listing.preview_video, workflow_prefix, listing
        )
        add(
            "video/preview.mp4",
            video_data,
            listing.preview_video.media_type,
            "listing_artifact",
            listing.preview_video.artifact_id,
        )
        if listing.delivery_document is None:
            raise ValueError("listing access document is absent")
        access_data = _read_listing_artifact(
            source_store, listing.delivery_document, workflow_prefix, listing
        )
        add(
            "access/README-access.pdf",
            access_data,
            listing.delivery_document.media_type,
            "listing_artifact",
            listing.delivery_document.artifact_id,
        )
        if listing.package_manifest is None:
            raise ValueError("listing package manifest is absent")
        listing_manifest_data = _read_listing_artifact(
            source_store, listing.package_manifest, workflow_prefix, listing
        )
        add(
            "listing/source-manifest.json",
            listing_manifest_data,
            listing.package_manifest.media_type,
            "listing_artifact",
            listing.package_manifest.artifact_id,
        )
        source_store.close()
        review = _product_review(
            workflow_run_id=workflow_run_id,
            spec=spec,
            shortlist=shortlist,
            primary=primary,
            backup=backup,
            listing=listing,
            build=build,
            qa=qa,
            preflight=preflight,
        )
        add(
            "PRODUCT_REVIEW.md",
            review,
            "text/markdown",
            "derived",
            spec.product_spec_id,
        )

        files = tuple(
            ProductExportFile(
                relative_path=path,
                media_type=media_type,
                byte_count=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                source_kind=source_kind,
                source_id=source_id,
            )
            for path, (data, media_type, source_kind, source_id) in sorted(payloads.items())
        )
        manifest = ProductExportManifest(
            product_id=spec.product_spec_id,
            product_spec_id=spec.product_spec_id,
            workflow_run_id=workflow_run_id,
            packet_id=packet.packet_id,
            terminal_state="DRAFT_READY",
            results=_result_bindings(
                packet, shortlist, spec, dedupe, build, qa, listing, preflight
            ),
            research_rows=len(packet.observations),
            candidates_scored=5,
            candidates_shortlisted=5,
            hubs=len(spec.hubs),
            variants=len(spec.colour_variants),
            tags=13,
            images=10,
            videos=1,
            access_pdfs=1,
            files=files,
            external_mutations=0,
            spend_usd=Decimal("0.00"),
        )
        manifest_bytes = canonical_json(manifest)
        manifest_path = PurePosixPath("manifest.json")
        expected_export_paths = {*payloads, "manifest.json"}
        export_store = LocalArtifactStore(self._artifact_root / prefix)
        _validate_export_inventory(export_store, expected_export_paths)
        replayed = _verify_committed_replay(export_store, manifest_path, manifest_bytes, payloads)
        if not replayed:
            for path, (data, media_type, _, _) in sorted(payloads.items()):
                export_store.put_bytes(path, data, media_type)
            _validate_export_inventory(
                export_store,
                expected_export_paths,
                required_paths=set(payloads),
            )
            export_store.put_bytes(manifest_path, manifest_bytes, "application/json")
            _validate_export_inventory(
                export_store,
                expected_export_paths,
                required_paths=expected_export_paths,
            )
            if not _verify_committed_replay(export_store, manifest_path, manifest_bytes, payloads):
                raise ValueError("export commit marker is absent after materialization")
        _validate_export_inventory(
            export_store,
            expected_export_paths,
            required_paths=expected_export_paths,
        )
        export_store.close()
        return ProductExportReceipt(
            product_id=spec.product_spec_id,
            workflow_run_id=workflow_run_id,
            artifact_path=str(self._artifact_root / prefix),
            manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            file_count=len(files) + 1,
            replayed=replayed,
            external_mutations=0,
            spend_usd=Decimal("0.00"),
        )


def _canonical_model_set(models: tuple[FrozenModel, ...]) -> tuple[bytes, ...]:
    return tuple(sorted(canonical_json(item) for item in models))


def _selected_scores(
    shortlist: CandidateShortlist,
) -> tuple[QualificationScore, QualificationScore | None]:
    if shortlist.selected_candidate_id is None:
        raise ValueError("export requires a selected candidate")
    primary = next(
        item
        for item in shortlist.candidates
        if item.candidate_id == shortlist.selected_candidate_id
    )
    backup = (
        next(
            item
            for item in shortlist.candidates
            if item.candidate_id == shortlist.backup_candidate_id
        )
        if shortlist.backup_candidate_id is not None
        else None
    )
    return primary, backup


def _read_listing_artifact(
    store: LocalArtifactStore,
    artifact: ArtifactReference,
    workflow_prefix: PurePosixPath,
    listing: ListingPackage,
) -> bytes:
    expected_prefix = PurePosixPath("listing") / listing.listing_package_id
    relative = PurePosixPath(artifact.relative_path.as_posix())
    if not relative.is_relative_to(expected_prefix):
        raise ValueError("listing artifact is outside the typed package root")
    return store.get_bytes(
        workflow_prefix / relative,
        expected_sha256=artifact.content_sha256,
        expected_byte_count=artifact.byte_count,
    )


def _result_bindings(
    packet: ResearchPacket,
    shortlist: CandidateShortlist,
    spec: ProductSpec,
    dedupe: DedupeResult,
    build: BuildResult,
    qa: ProductQAResult,
    listing: ListingPackage,
    preflight: PreflightResult,
) -> tuple[ProductExportResult, ...]:
    identities: tuple[tuple[str, FrozenModel, str], ...] = (
        ("ADMIT_RESEARCH_PACKET", packet, packet.packet_id),
        ("QUALIFY_CANDIDATES", shortlist, shortlist.shortlist_id),
        ("CREATE_PRODUCT_SPEC", spec, spec.product_spec_id),
        ("CHECK_CATALOGUE_DEDUPE", dedupe, dedupe.dedupe_result_id),
        ("BUILD_PRODUCT", build, build.build_id),
        ("RUN_PRODUCT_QA", qa, qa.qa_result_id),
        ("CREATE_LISTING_PACKAGE", listing, listing.listing_package_id),
        ("RUN_PREFLIGHT", preflight, preflight.preflight_result_id),
    )
    return tuple(
        ProductExportResult(
            step=step,
            result_type=FIRST_PRODUCT_STEP_OUTPUTS[step].result_type,
            result_id=identity,
            sha256=canonical_sha256(result),
        )
        for step, result, identity in identities
    )


def _verify_committed_replay(
    store: LocalArtifactStore,
    manifest_path: PurePosixPath,
    manifest_bytes: bytes,
    payloads: dict[str, ExportPayload],
) -> bool:
    try:
        stored_manifest = store.get_bytes(manifest_path)
    except FileNotFoundError:
        return False
    if stored_manifest != manifest_bytes:
        raise ValueError("export manifest collision")
    for path, (expected, _, _, _) in sorted(payloads.items()):
        stored = store.get_bytes(
            path,
            expected_sha256=hashlib.sha256(expected).hexdigest(),
            expected_byte_count=len(expected),
        )
        if stored != expected:
            raise ValueError(f"export artifact collision at {path}")
    return True


def _validate_export_inventory(
    store: LocalArtifactStore,
    expected_paths: set[str],
    *,
    required_paths: set[str] | None = None,
) -> None:
    actual_paths = {path.as_posix() for path in store.list_files()}
    unexpected_paths = sorted(actual_paths - expected_paths)
    if unexpected_paths:
        raise ValueError(f"export contains unexpected files: {', '.join(unexpected_paths)}")
    missing_paths = sorted((required_paths or set()) - actual_paths)
    if missing_paths:
        raise ValueError(f"export is missing required files: {', '.join(missing_paths)}")


def _product_review(
    *,
    workflow_run_id: UUID,
    spec: ProductSpec,
    shortlist: CandidateShortlist,
    primary: QualificationScore,
    backup: QualificationScore | None,
    listing: ListingPackage,
    build: BuildResult,
    qa: ProductQAResult,
    preflight: PreflightResult,
) -> bytes:
    lines = (
        "# Product Review",
        "",
        f"- Workflow ID: `{workflow_run_id}`",
        f"- Product identity: `{spec.product_spec_id}`",
        f"- Concept: {spec.identity_niche} / {spec.base_category}",
        f"- Target buyer: {spec.target_buyer}",
        f"- Promised outcome: {spec.promised_outcome}",
        f"- Primary: `{primary.candidate_id}` ({primary.total}/40)",
        *(
            (f"- Backup: `{backup.candidate_id}` ({backup.total}/40)",)
            if backup is not None
            else ()
        ),
        f"- Shortlisted candidates: {len(shortlist.candidates)}",
        f"- Hubs: {len(spec.hubs)}",
        f"- Variants: {len(spec.colour_variants)}",
        f"- Listing title: {listing.title}",
        f"- Tags: {len(listing.tags)}",
        f"- Images: {len(listing.listing_images)}",
        "- Videos: 1",
        "- Access PDFs: 1",
        f"- Build manifest SHA-256: `{build.manifest_sha256}`",
        f"- Product QA: {'PASS' if qa.passed else 'FAIL'}",
        f"- Preflight: {'PASS' if preflight.passed else 'FAIL'}",
        "- External mutations: 0",
        "- Spend: USD 0.00",
        "",
    )
    return "\n".join(lines).encode("utf-8")


__all__ = ["ProductExportService"]
