import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from money_machine.agents.implementations.creative_assets import CreativeAssetService
from money_machine.application.services.listing_service import ListingService
from money_machine.assets.design_tokens import DEFAULT_TOKENS, contrast_ratio
from money_machine.assets.pdf import pdf_page_count
from money_machine.assets.renderer import png_dimensions
from money_machine.assets.video import validate_preview_video
from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import ProductFact, ProductSpec

SHA = "a" * 64
type Pathish = str | bytes | os.PathLike[str] | os.PathLike[bytes]


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


def qa() -> ProductQAResult:
    return ProductQAResult(
        qa_result_id="qa-1",
        build_id="build-1",
        passed=True,
        findings=(),
        checked_at=datetime(2026, 8, 9, tzinfo=UTC),
        result_sha256=SHA,
    )


def test_listing_asset_render_is_complete_local_and_deterministic(tmp_path: Path) -> None:
    package = ListingService().create(spec(), build(), qa())
    first = CreativeAssetService().render(package, tmp_path / "one", spec=spec(), build=build())
    second = CreativeAssetService().render(package, tmp_path / "two", spec=spec(), build=build())

    assert len(first.listing_images) == 10
    assert [item.content_sha256 for item in first.listing_images] == [
        item.content_sha256 for item in second.listing_images
    ]
    assert len(set(item.content_sha256 for item in first.listing_images)) == 10
    for image in first.listing_images:
        path = tmp_path / "one" / image.relative_path
        assert path.is_file()
        assert png_dimensions(path.read_bytes()) == (2000, 2000)
        assert image.media_type == "image/png"
    assert first.delivery_document is not None
    pdf_path = tmp_path / "one" / first.delivery_document.relative_path
    assert pdf_path.is_file()
    pdf_data = pdf_path.read_bytes()
    assert pdf_page_count(pdf_data) == 2
    assert b"Navigation hubs:" in pdf_data
    assert b"Colour variants:" in pdf_data
    assert all(hub.encode() in pdf_data for hub in spec().hubs)
    assert all(colour.encode() in pdf_data for colour in spec().colour_variants)
    assert build().artifacts[0].relative_path.as_posix().encode() in pdf_data
    assert first.preview_video is not None
    assert first.preview_video_status == "GENERATED"
    video_path = tmp_path / "one" / first.preview_video.relative_path
    assert video_path.is_file()
    assert first.preview_video.media_type == "video/mp4"
    validate_preview_video(video_path.read_bytes(), first, spec(), build())
    assert first.package_manifest is not None
    assert not any(
        "http://" in path.read_text(errors="ignore") for path in (tmp_path / "one").rglob("*.*")
    )
    manifest = json.loads((tmp_path / "one" / first.package_manifest.relative_path).read_text())
    assert manifest["product_context"]["hubs"] == list(spec().hubs)
    assert manifest["product_context"]["colour_variants"] == list(spec().colour_variants)
    assert manifest["claims"]
    assert all(item["source"] in {"PRODUCT_FACT", "STRUCTURAL_COPY"} for item in manifest["claims"])
    recorded_claims = {item["claim"] for item in manifest["claims"]}
    assert first.title in recorded_claims
    assert set(first.feature_statements).issubset(recorded_claims)
    assert spec().target_buyer in recorded_claims
    assert spec().promised_outcome in recorded_claims
    assert manifest["preview_video_status"] == "GENERATED"
    assert manifest["artifacts"][-1]["path"] == first.preview_video.relative_path.as_posix()


def test_asset_paths_reject_traversal_and_symlink_without_escape(tmp_path: Path) -> None:
    package = ListingService().create(spec(), build(), qa())
    escaped = package.model_copy(update={"listing_package_id": "../../escaped"})

    with pytest.raises(ValueError, match="path-safe"):
        CreativeAssetService().render(escaped, tmp_path / "root", spec=spec(), build=build())
    assert not (tmp_path / "escaped").exists()

    root = tmp_path / "root"
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "listing").mkdir(parents=True)
    (root / "listing" / package.listing_package_id).symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        CreativeAssetService().render(package, root, spec=spec(), build=build())
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("collision_kind", ("different", "identical"))
def test_artifact_writer_target_creation_race_verifies_colliding_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    collision_kind: str,
) -> None:
    package = ListingService().create(spec(), build(), qa())
    root = tmp_path / "root"
    original_link = os.link
    raced = False

    def create_collision(
        src: Pathish,
        dst: Pathish,
        src_dir_fd: int | None,
        dst_dir_fd: int | None,
    ) -> None:
        nonlocal raced
        if not raced:
            assert src_dir_fd is not None
            assert dst_dir_fd is not None
            collision_data = b"attacker"
            if collision_kind == "identical":
                source_fd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=src_dir_fd)
                try:
                    chunks: list[bytes] = []
                    while chunk := os.read(source_fd, 1024 * 1024):
                        chunks.append(chunk)
                    collision_data = b"".join(chunks)
                finally:
                    os.close(source_fd)
            collision_fd = os.open(
                dst,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=dst_dir_fd,
            )
            try:
                os.write(collision_fd, collision_data)
                os.fsync(collision_fd)
            finally:
                os.close(collision_fd)
            raced = True

    def racing_link(
        src: Pathish,
        dst: Pathish,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        create_collision(src, dst, src_dir_fd, dst_dir_fd)
        return original_link(
            src,
            dst,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(os, "link", racing_link)
    if collision_kind == "different":
        with pytest.raises(ValueError, match="artifact collision"):
            CreativeAssetService().render(package, root, spec=spec(), build=build())
    else:
        CreativeAssetService().render(package, root, spec=spec(), build=build())

    assert raced is True
    collision = root / "listing" / package.listing_package_id / "images" / "01-hero.png"
    if collision_kind == "different":
        assert collision.read_bytes() == b"attacker"
    else:
        assert png_dimensions(collision.read_bytes()) == (2000, 2000)


@pytest.mark.parametrize("swap_point", ("open", "rename"))
def test_asset_writer_parent_swap_never_creates_an_outside_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swap_point: str,
) -> None:
    package = ListingService().create(spec(), build(), qa())
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    outside.mkdir()
    original_open = os.open
    original_link = os.link
    original_replace = os.replace
    original_rename = os.rename
    swapped = False

    def swap_parent(temporary_name: str | None = None) -> None:
        nonlocal swapped
        if swapped:
            return
        images = root / "listing" / package.listing_package_id / "images"
        backup = images.with_name("images-pinned")
        original_rename(images, backup)
        images.symlink_to(outside, target_is_directory=True)
        if temporary_name is not None:
            (outside / temporary_name).write_bytes(b"attacker-controlled")
        swapped = True

    def racing_open(
        path: Pathish,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        name = os.fsdecode(path)
        if swap_point == "open" and name.endswith(".tmp"):
            swap_parent()
        return original_open(path, flags, mode, dir_fd=dir_fd)

    def racing_replace(
        src: Pathish,
        dst: Pathish,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        if swap_point == "rename":
            swap_parent(Path(os.fsdecode(src)).name)
        return original_replace(
            src,
            dst,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    def racing_link(
        src: Pathish,
        dst: Pathish,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        if swap_point == "rename":
            swap_parent(os.fsdecode(src))
        return original_link(
            src,
            dst,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )

    def racing_rename(
        src: Pathish,
        dst: Pathish,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        if swap_point == "rename":
            swap_parent(os.fsdecode(src))
        return original_rename(
            src,
            dst,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(os, "open", racing_open)
    monkeypatch.setattr(os, "link", racing_link)
    monkeypatch.setattr(os, "replace", racing_replace)
    monkeypatch.setattr(os, "rename", racing_rename)

    with pytest.raises((OSError, ValueError)):
        CreativeAssetService().render(package, root, spec=spec(), build=build())

    assert swapped is True
    assert list(outside.glob("*.png")) == []


@pytest.mark.parametrize(
    ("text", "background"),
    (
        (DEFAULT_TOKENS.foreground, DEFAULT_TOKENS.background),
        (DEFAULT_TOKENS.foreground, DEFAULT_TOKENS.card),
        ("#FFFFFF", DEFAULT_TOKENS.accent),
        ("#FFFFFF", DEFAULT_TOKENS.secondary),
    ),
)
def test_every_rendered_text_pair_meets_exact_configured_contrast(
    text: str,
    background: str,
) -> None:
    assert contrast_ratio(text, background) >= DEFAULT_TOKENS.min_contrast_ratio
