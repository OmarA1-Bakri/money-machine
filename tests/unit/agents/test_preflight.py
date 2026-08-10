import base64
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from money_machine.agents.implementations.creative_assets import CreativeAssetService
from money_machine.agents.implementations.preflight import PreflightService
from money_machine.application.services.listing_service import (
    ListingService,
    listing_package_sha256,
)
from money_machine.assets.renderer import render_listing_png
from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.models.listing import ListingPackage
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import ProductFact, ProductSpec

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
SHA = "a" * 64


def spec() -> ProductSpec:
    return ProductSpec(
        product_spec_id="spec-1",
        candidate_id="candidate-1",
        identity_niche="adhd students",
        base_category="digital planner",
        target_buyer="People managing adhd students",
        promised_outcome="A structured digital planner workspace",
        hubs=("Home", "Courses", "Tasks", "Notes", "Reviews", "Archive"),
        colour_variants=("Ink", "Sand", "Sage"),
        features=("Linked course and task views",),
        product_facts=(
            ProductFact(
                claim="Configured with 6 hubs",
                category="HUB_INVENTORY",
                evidence_ids=("evidence-1",),
            ),
            ProductFact(
                claim="Includes Linked course and task views",
                category="FEATURE",
                evidence_ids=("evidence-1",),
            ),
            ProductFact(
                claim="Configured with 3 colour variants",
                category="COLOUR_VARIANTS",
                evidence_ids=("evidence-1",),
            ),
            ProductFact(
                claim="People managing adhd students",
                category="BUYER_FIT",
                evidence_ids=("evidence-1",),
            ),
            ProductFact(
                claim="A structured digital planner workspace",
                category="WORKFLOW_OUTCOME",
                evidence_ids=("evidence-1",),
            ),
        ),
        source_evidence_ids=("evidence-1",),
        spec_sha256=SHA,
    )


def build() -> BuildResult:
    artifact = ArtifactReference(
        artifact_id="artifact-1",
        relative_path=Path("products/spec-1/index.html"),
        media_type="text/html",
        byte_count=1,
        content_sha256=SHA,
    )
    return BuildResult(
        build_id="build-1",
        product_spec_id="spec-1",
        root_artifact_path="products/spec-1",
        artifacts=(artifact,),
        manifest_sha256=SHA,
        renderer_version="1",
    )


def qa(*, passed: bool = True) -> ProductQAResult:
    return ProductQAResult(
        qa_result_id="qa-1",
        build_id="build-1",
        passed=passed,
        findings=() if passed else ("broken",),
        checked_at=NOW,
        result_sha256=SHA,
    )


def rendered(tmp_path: Path):
    package = ListingService().create(spec(), build(), qa())
    return CreativeAssetService().render(package, tmp_path, spec=spec(), build=build())


def test_complete_local_package_passes_with_zero_effects(tmp_path: Path) -> None:
    package = rendered(tmp_path)
    result = PreflightService(tmp_path).evaluate(package, qa(), spec=spec(), build=build(), now=NOW)

    assert package.preview_video_status == "GENERATED"
    assert package.preview_video is not None
    assert package.preview_video.media_type == "video/mp4"
    assert (tmp_path / package.preview_video.relative_path).is_file()
    assert result.passed is True
    assert result.findings == ()
    assert result.external_effect_mode == "simulation"
    assert str(result.incremental_spend) == "0.00"
    assert result.publication_receipt_present is False


def test_preview_video_renderer_is_identity_bound_and_byte_stable() -> None:
    from money_machine.assets.video import render_preview_video

    package = ListingService().create(spec(), build(), qa())
    first = render_preview_video(package, spec(), build())
    assert first == render_preview_video(package, spec(), build())
    changed = package.model_copy(update={"listing_package_id": "listing-other"})
    assert render_preview_video(changed, spec(), build()) != first


def test_preflight_reopens_and_rehashes_artifacts(tmp_path: Path) -> None:
    package = rendered(tmp_path)
    assert package.delivery_document is not None
    (tmp_path / package.delivery_document.relative_path).write_bytes(b"tampered")

    result = PreflightService(tmp_path).evaluate(package, qa(), spec=spec(), build=build(), now=NOW)

    assert result.passed is False
    assert "ARTIFACT_HASH_MISMATCH" in result.findings


def test_preflight_fails_closed_for_qa_or_policy_violations(tmp_path: Path) -> None:
    package = rendered(tmp_path)
    service = PreflightService(tmp_path)

    failed_qa = service.evaluate(package, qa(passed=False), spec=spec(), build=build(), now=NOW)
    invalid_mode = service.evaluate(
        package, qa(), spec=spec(), build=build(), now=NOW, external_effect_mode="live"
    )
    unknown_spend = service.evaluate(
        package, qa(), spec=spec(), build=build(), now=NOW, incremental_spend=None
    )
    receipt = service.evaluate(
        package, qa(), spec=spec(), build=build(), now=NOW, publication_receipt_present=True
    )

    assert "PRODUCT_QA_FAILED" in failed_qa.findings
    assert "EXTERNAL_EFFECT_MODE_DENIED" in invalid_mode.findings
    assert "INCREMENTAL_SPEND_UNKNOWN" in unknown_spend.findings
    assert "EXTERNAL_MUTATION_RECEIPT_PRESENT" in receipt.findings


def test_generated_video_is_reopened_and_missing_file_fails(tmp_path: Path) -> None:
    package = rendered(tmp_path)
    video = ArtifactReference(
        artifact_id="video-missing",
        relative_path=Path("listing/video/preview.mp4"),
        media_type="video/mp4",
        byte_count=10,
        content_sha256="b" * 64,
    )
    changed = package.model_copy(
        update={
            "preview_video": video,
            "preview_video_status": "GENERATED",
            "package_sha256": "0" * 64,
        }
    )
    changed = changed.model_copy(update={"package_sha256": listing_package_sha256(changed)})

    result = PreflightService(tmp_path).evaluate(changed, qa(), spec=spec(), build=build(), now=NOW)

    assert "ARTIFACT_MISSING" in result.findings


def test_generated_video_is_rehashed_and_tampering_fails(tmp_path: Path) -> None:
    package = rendered(tmp_path)
    video_path = tmp_path / "listing" / "video" / "preview.mp4"
    video_path.parent.mkdir(parents=True)
    original = b"local deterministic video bytes"
    video_path.write_bytes(original)
    video = ArtifactReference(
        artifact_id="video-local",
        relative_path=Path("listing/video/preview.mp4"),
        media_type="video/mp4",
        byte_count=len(original),
        content_sha256=hashlib.sha256(original).hexdigest(),
    )
    video_path.write_bytes(b"tampered")
    changed = package.model_copy(
        update={
            "preview_video": video,
            "preview_video_status": "GENERATED",
            "package_sha256": "0" * 64,
        }
    )
    changed = changed.model_copy(update={"package_sha256": listing_package_sha256(changed)})

    result = PreflightService(tmp_path).evaluate(changed, qa(), spec=spec(), build=build(), now=NOW)

    assert "ARTIFACT_HASH_MISMATCH" in result.findings


def test_preflight_validates_complete_manifest_identity(tmp_path: Path) -> None:
    package = rendered(tmp_path)
    assert package.package_manifest is not None
    manifest_path = tmp_path / package.package_manifest.relative_path
    payload = json.loads(manifest_path.read_text())
    payload["copy_package_sha256"] = "f" * 64
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    manifest_path.write_bytes(data)
    manifest = package.package_manifest.model_copy(
        update={"byte_count": len(data), "content_sha256": hashlib.sha256(data).hexdigest()}
    )
    changed = package.model_copy(update={"package_manifest": manifest, "package_sha256": "0" * 64})
    changed = changed.model_copy(update={"package_sha256": listing_package_sha256(changed)})

    result = PreflightService(tmp_path).evaluate(changed, qa(), spec=spec(), build=build(), now=NOW)

    assert "LINEAGE_COPY_HASH_MISMATCH" in result.findings


def test_preflight_rejects_unbound_copy_even_with_recomputed_package_hash(
    tmp_path: Path,
) -> None:
    package = rendered(tmp_path)
    changed = package.model_copy(
        update={
            "title": "Best Seller With Thousands of Reviews",
            "package_sha256": "0" * 64,
        }
    )
    changed = changed.model_copy(update={"package_sha256": listing_package_sha256(changed)})

    result = PreflightService(tmp_path).evaluate(changed, qa(), spec=spec(), build=build(), now=NOW)

    assert result.passed is False
    assert "LISTING_COPY_MISMATCH" in result.findings
    assert "UNSUPPORTED_CLAIM" in result.findings


@pytest.mark.parametrize(
    ("field", "claim"),
    (
        ("promised_outcome", "Track guaranteed profits"),
        ("promised_outcome", "Manage passive income"),
        ("promised_outcome", "Access recurring revenue"),
        ("target_buyer", "Creators planning guaranteed profits"),
    ),
)
def test_commercial_claims_fail_every_listing_asset_and_preflight_boundary(
    tmp_path: Path,
    field: str,
    claim: str,
) -> None:
    original = spec()
    safe_package = rendered(tmp_path)
    replaced = original.promised_outcome if field == "promised_outcome" else original.target_buyer
    unsupported = original.model_copy(
        update={
            field: claim,
            "product_facts": tuple(
                fact.model_copy(update={"claim": claim}) if fact.claim == replaced else fact
                for fact in original.product_facts
            ),
        }
    )

    with pytest.raises(ValueError, match="product fact"):
        ListingService().create(unsupported, build(), qa())
    with pytest.raises(ValueError):
        CreativeAssetService().render(
            safe_package,
            tmp_path / "invalid",
            spec=unsupported,
            build=build(),
        )
    result = PreflightService(tmp_path).evaluate(
        safe_package,
        qa(),
        spec=unsupported,
        build=build(),
        now=NOW,
    )
    assert result.passed is False
    assert "UNSUPPORTED_CLAIM" in result.findings


def _box(kind: bytes, payload: bytes) -> bytes:
    return (len(payload) + 8).to_bytes(4, "big") + kind + payload


def _container_shell_mp4() -> bytes:
    return b"".join(
        (
            _box(b"ftyp", b"isom\x00\x00\x00\x00isom"),
            _box(b"moov", b"\x00"),
            _box(b"mdat", b"\x00"),
        )
    )


def _ebml_element(identifier: bytes, payload: bytes) -> bytes:
    assert len(payload) < 127
    return identifier + bytes((0x80 | len(payload),)) + payload


def _container_shell_webm() -> bytes:
    header = _ebml_element(b"\x1a\x45\xdf\xa3", b"\x42\x86\x81\x01")
    cluster = _ebml_element(b"\x1f\x43\xb6\x75", b"\x00")
    return header + _ebml_element(b"\x18\x53\x80\x67", cluster)


def _declared_shell_mp4() -> bytes:
    handler = b"\x00" * 8 + b"vide" + b"\x00" * 12
    movie = _box(b"trak", _box(b"mdia", _box(b"hdlr", handler)))
    return b"".join(
        (
            _box(b"ftyp", b"isom\x00\x00\x00\x00isom"),
            _box(b"moov", movie),
            _box(b"mdat", b"\x00"),
        )
    )


def _declared_shell_webm() -> bytes:
    header = _ebml_element(b"\x1a\x45\xdf\xa3", b"\x42\x86\x81\x01")
    track_type = _ebml_element(b"\x83", b"\x01")
    track_entry = _ebml_element(b"\xae", track_type)
    tracks = _ebml_element(b"\x16\x54\xae\x6b", track_entry)
    cluster = _ebml_element(b"\x1f\x43\xb6\x75", b"\x00")
    return header + _ebml_element(b"\x18\x53\x80\x67", tracks + cluster)


_REAL_MP4 = base64.b64decode(
    "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAMVbW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAACgAAQAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAj90cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAACgAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAABAAAAAQAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAAAoAAAAAAABAAAAAAG3bWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAAAyAAAAAgBVxAAAAAAALWhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAABYm1pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAASJzdGJsAAAAvnN0c2QAAAAAAAAAAQAAAK5hdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAABAAEABIAAAASAAAAAAAAAABFUxhdmM2MC4zMS4xMDIgbGlieDI2NAAAAAAAAAAAAAAAGP//AAAANGF2Y0MBZAAK/+EAF2dkAAqs2V7ARAAAAwAEAAADAMg8SJZYAQAGaOvjyyLA/fj4AAAAABBwYXNwAAAAAQAAAAEAAAAUYnRydAAAAAAAAinoAAIp6AAAABhzdHRzAAAAAAAAAAEAAAABAAACAAAAABxzdHNjAAAAAAAAAAEAAAABAAAAAQAAAAEAAAAUc3RzegAAAAAAAALFAAAAAQAAABRzdGNvAAAAAAAAAAEAAANFAAAAYnVkdGEAAABabWV0YQAAAAAAAAAhaGRscgAAAAAAAAAAbWRpcmFwcGwAAAAAAAAAAAAAAAAtaWxzdAAAACWpdG9vAAAAHWRhdGEAAAABAAAAAExhdmY2MC4xNi4xMDAAAAAIZnJlZQAAAs1tZGF0AAACrgYF//+q3EXpvebZSLeWLNgg2SPu73gyNjQgLSBjb3JlIDE2NCByMzEwOCAzMWUxOWY5IC0gSC4yNjQvTVBFRy00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMtMjAyMyAtIGh0dHA6Ly93d3cudmlkZW9sYW4ub3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTEgcmVmPTMgZGVibG9jaz0xOjA6MCBhbmFseXNlPTB4MzoweDExMyBtZT1oZXggc3VibWU9NyBwc3k9MSBwc3lfcmQ9MS4wMDowLjAwIG1peGVkX3JlZj0xIG1lX3JhbmdlPTE2IGNocm9tYV9tZT0xIHRyZWxsaXM9MSA4eDhkY3Q9MSBjcW09MCBkZWFkem9uZT0yMSwxMSBmYXN0X3Bza2lwPTEgY2hyb21hX3FwX29mZnNldD0tMiB0aHJlYWRzPTEgbG9va2FoZWFkX3RocmVhZHM9MSBzbGljZWRfdGhyZWFkcz0wIG5yPTAgZGVjaW1hdGU9MSBpbnRlcmxhY2VkPTAgYmx1cmF5X2NvbXBhdD0wIGNvbnN0cmFpbmVkX2ludHJhPTAgYmZyYW1lcz0zIGJfcHlyYW1pZD0yIGJfYWRhcHQ9MSBiX2JpYXM9MCBkaXJlY3Q9MSB3ZWlnaHRiPTEgb3Blbl9nb3A9MCB3ZWlnaHRwPTIga2V5aW50PTI1MCBrZXlpbnRfbWluPTI1IHNjZW5lY3V0PTQwIGludHJhX3JlZnJlc2g9MCByY19sb29rYWhlYWQ9NDAgcmM9Y3JmIG1idHJlZT0xIGNyZj0yMy4wIHFjb21wPTAuNjAgcXBtaW49MCBxcG1heD02OSBxcHN0ZXA9NCBpcF9yYXRpbz0xLjQwIGFxPTE6MS4wMACAAAAAD2WIhAAr//72c3wKa22xgQ=="
)
_REAL_WEBM = base64.b64decode(
    "GkXfo59ChoEBQveBAULygQRC84EIQoKEd2VibUKHgQJChYECGFOAZwEAAAAAAAHiEU2bdLpNu4tTq4QVSalmU6yBoU27i1OrhBZUrmtTrIHYTbuMU6uEElTDZ1OsggEeTbuMU6uEHFO7a1OsggHM7AEAAAAAAABZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVSalmsirXsYMPQkBNgI1MYXZmNjAuMTYuMTAwV0GNTGF2ZjYwLjE2LjEwMESJiEBEAAAAAAAAFlSua8GuAQAAAAAAADjXgQFzxYjuQDLf3VhrF5yBACK1nIN1bmSIgQCGhVZfVlA4g4EBI+ODhAJiWgDgibCBELqBEJqBAhJUw2f8c3OgY8CAZ8iaRaOHRU5DT0RFUkSHjUxhdmY2MC4xNi4xMDBzc9ZjwItjxYjuQDLf3VhrF2fIoUWjh0VOQ09ERVJEh5RMYXZjNjAuMzEuMTAyIGxpYnZweGfIoUWjiERVUkFUSU9ORIeTMDA6MDA6MDAuMDQwMDAwMDAwAB9DtnWo54EAo6OBAACAEAIAnQEqEAAQAABHCIWFiIWEiAICAAwNYAD+/6tQgBxTu2uRu4+zgQC3iveBAfGCAZ/wgQM="
)


def _with_generated_video(
    package: ListingPackage,
    root: Path,
    *,
    data: bytes,
    media_type: str,
) -> ListingPackage:
    assert package.package_manifest is not None
    assert package.preview_video is not None
    relative = package.preview_video.relative_path
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    video = ArtifactReference(
        artifact_id=f"video-{hashlib.sha256(data).hexdigest()[:24]}",
        relative_path=relative,
        media_type=media_type,
        byte_count=len(data),
        content_sha256=hashlib.sha256(data).hexdigest(),
    )
    manifest_path = root / package.package_manifest.relative_path
    payload = json.loads(manifest_path.read_text())
    payload["artifacts"][-1] = {
        "path": relative.as_posix(),
        "media_type": media_type,
        "sha256": video.content_sha256,
        "byte_count": len(data),
    }
    payload["preview_video_status"] = "GENERATED"
    manifest_data = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    manifest_path.write_bytes(manifest_data)
    manifest = package.package_manifest.model_copy(
        update={
            "byte_count": len(manifest_data),
            "content_sha256": hashlib.sha256(manifest_data).hexdigest(),
        }
    )
    changed = package.model_copy(
        update={
            "preview_video": video,
            "preview_video_status": "GENERATED",
            "package_manifest": manifest,
            "package_sha256": "0" * 64,
        }
    )
    return changed.model_copy(update={"package_sha256": listing_package_sha256(changed)})


@pytest.mark.parametrize(
    ("data", "media_type"),
    (
        (b"this is not an mp4 container", "video/mp4"),
        (b"\x00\x00\x00\x18ftypisom", "video/mp4"),
        (b"this is not a webm container", "video/webm"),
        (b"\x1a\x45\xdf\xa3\x81", "video/webm"),
    ),
)
def test_generated_video_rejects_random_and_truncated_containers(
    tmp_path: Path,
    data: bytes,
    media_type: str,
) -> None:
    package = _with_generated_video(rendered(tmp_path), tmp_path, data=data, media_type=media_type)

    result = PreflightService(tmp_path).evaluate(package, qa(), spec=spec(), build=build(), now=NOW)

    assert result.passed is False
    assert "VIDEO_RENDER_MISMATCH" in result.findings


@pytest.mark.parametrize(
    ("data", "media_type"),
    ((_container_shell_mp4(), "video/mp4"), (_container_shell_webm(), "video/webm")),
)
def test_generated_video_rejects_container_shells_without_video_tracks(
    tmp_path: Path,
    data: bytes,
    media_type: str,
) -> None:
    package = _with_generated_video(rendered(tmp_path), tmp_path, data=data, media_type=media_type)

    result = PreflightService(tmp_path).evaluate(package, qa(), spec=spec(), build=build(), now=NOW)

    assert result.passed is False
    assert "VIDEO_RENDER_MISMATCH" in result.findings


@pytest.mark.parametrize(
    ("data", "media_type"),
    ((_declared_shell_mp4(), "video/mp4"), (_declared_shell_webm(), "video/webm")),
)
def test_generated_video_rejects_declared_stream_shells(
    tmp_path: Path,
    data: bytes,
    media_type: str,
) -> None:
    package = _with_generated_video(rendered(tmp_path), tmp_path, data=data, media_type=media_type)

    result = PreflightService(tmp_path).evaluate(package, qa(), spec=spec(), build=build(), now=NOW)

    assert result.passed is False
    assert "VIDEO_RENDER_MISMATCH" in result.findings


@pytest.mark.parametrize(
    ("data", "media_type"),
    ((_REAL_MP4, "video/mp4"), (_REAL_WEBM, "video/webm")),
)
def test_generated_video_rejects_foreign_real_video_streams(
    tmp_path: Path,
    data: bytes,
    media_type: str,
) -> None:
    package = _with_generated_video(rendered(tmp_path), tmp_path, data=data, media_type=media_type)

    result = PreflightService(tmp_path).evaluate(package, qa(), spec=spec(), build=build(), now=NOW)

    assert result.passed is False
    assert "VIDEO_RENDER_MISMATCH" in result.findings


def test_preflight_rejects_symlink_artifact_root(tmp_path: Path) -> None:
    target = tmp_path / "target"
    rendered(target)
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        PreflightService(alias)


def _resign_manifest(
    package: ListingPackage,
    root: Path,
    *,
    images: tuple[ArtifactReference, ...],
) -> ListingPackage:
    assert package.package_manifest is not None
    manifest_path = root / package.package_manifest.relative_path
    payload = json.loads(manifest_path.read_text())
    payload["artifacts"][:10] = [
        {
            "path": item.relative_path.as_posix(),
            "media_type": item.media_type,
            "sha256": item.content_sha256,
            "byte_count": item.byte_count,
        }
        for item in images
    ]
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    manifest_path.write_bytes(data)
    manifest = package.package_manifest.model_copy(
        update={"byte_count": len(data), "content_sha256": hashlib.sha256(data).hexdigest()}
    )
    changed = package.model_copy(
        update={"listing_images": images, "package_manifest": manifest, "package_sha256": "0" * 64}
    )
    return changed.model_copy(update={"package_sha256": listing_package_sha256(changed)})


def _resign_delivery(
    package: ListingPackage,
    root: Path,
    *,
    data: bytes,
) -> ListingPackage:
    assert package.delivery_document is not None
    assert package.package_manifest is not None
    delivery_path = root / package.delivery_document.relative_path
    delivery_path.write_bytes(data)
    delivery = package.delivery_document.model_copy(
        update={"byte_count": len(data), "content_sha256": hashlib.sha256(data).hexdigest()}
    )
    manifest_path = root / package.package_manifest.relative_path
    payload = json.loads(manifest_path.read_text())
    payload["artifacts"][10] = {
        "path": delivery.relative_path.as_posix(),
        "media_type": delivery.media_type,
        "sha256": delivery.content_sha256,
        "byte_count": delivery.byte_count,
    }
    manifest_data = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    manifest_path.write_bytes(manifest_data)
    manifest = package.package_manifest.model_copy(
        update={
            "byte_count": len(manifest_data),
            "content_sha256": hashlib.sha256(manifest_data).hexdigest(),
        }
    )
    changed = package.model_copy(
        update={
            "delivery_document": delivery,
            "package_manifest": manifest,
            "package_sha256": "0" * 64,
        }
    )
    return changed.model_copy(update={"package_sha256": listing_package_sha256(changed)})


def test_preflight_rejects_foreign_pdf_after_all_self_hashes_are_recomputed(
    tmp_path: Path,
) -> None:
    package = rendered(tmp_path)
    fake = b"%PDF-1.4\n/Type /Page\n/Type /Page\n%%EOF\n"
    changed = _resign_delivery(package, tmp_path, data=fake)

    result = PreflightService(tmp_path).evaluate(changed, qa(), spec=spec(), build=build(), now=NOW)

    assert result.passed is False
    assert "DELIVERY_RENDER_MISMATCH" in result.findings


def test_preflight_rejects_duplicate_image_references_after_resigning(tmp_path: Path) -> None:
    package = rendered(tmp_path)
    changed = _resign_manifest(package, tmp_path, images=(package.listing_images[0],) * 10)

    result = PreflightService(tmp_path).evaluate(changed, qa(), spec=spec(), build=build(), now=NOW)

    assert result.passed is False
    assert "IMAGE_PATH_DUPLICATE" in result.findings
    assert "IMAGE_DIGEST_DUPLICATE" in result.findings


def test_preflight_rejects_role_path_swap_after_resigning(tmp_path: Path) -> None:
    package = rendered(tmp_path)
    images = list(package.listing_images)
    images[0], images[1] = images[1], images[0]
    changed = _resign_manifest(package, tmp_path, images=tuple(images))

    result = PreflightService(tmp_path).evaluate(changed, qa(), spec=spec(), build=build(), now=NOW)

    assert result.passed is False
    assert "IMAGE_ROLE_MISMATCH" in result.findings


def test_preflight_rejects_foreign_valid_png_after_resigning(tmp_path: Path) -> None:
    package = rendered(tmp_path)
    original = package.listing_images[0]
    foreign = render_listing_png("hero", index=1, title="Foreign package", detail="Foreign")
    (tmp_path / original.relative_path).write_bytes(foreign)
    replacement = original.model_copy(
        update={"byte_count": len(foreign), "content_sha256": hashlib.sha256(foreign).hexdigest()}
    )
    changed = _resign_manifest(
        package,
        tmp_path,
        images=(replacement, *package.listing_images[1:]),
    )

    result = PreflightService(tmp_path).evaluate(changed, qa(), spec=spec(), build=build(), now=NOW)

    assert result.passed is False
    assert "IMAGE_RENDER_MISMATCH" in result.findings


def test_preflight_fd_read_rejects_symlink_swap_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = rendered(tmp_path)
    victim = tmp_path / package.listing_images[0].relative_path
    outside = tmp_path / "outside.png"
    outside.write_bytes(victim.read_bytes())
    original_resolve = Path.resolve
    original_open = os.open
    swapped = False

    def swap() -> None:
        nonlocal swapped
        if not swapped:
            victim.unlink()
            victim.symlink_to(outside)
            swapped = True

    def racing_resolve(path: Path, *args: Any, **kwargs: Any) -> Path:
        resolved = original_resolve(path, *args, **kwargs)
        if path == victim:
            swap()
        return resolved

    def racing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if dir_fd is not None and os.fspath(path) == victim.name and not flags & os.O_DIRECTORY:
            swap()
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(Path, "resolve", racing_resolve)
    monkeypatch.setattr(os, "open", racing_open)

    result = PreflightService(tmp_path).evaluate(package, qa(), spec=spec(), build=build(), now=NOW)

    assert swapped is True
    assert result.passed is False
    assert "NON_LOCAL_ARTIFACT_PATH" in result.findings
