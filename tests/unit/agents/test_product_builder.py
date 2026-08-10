from __future__ import annotations

import json
from pathlib import Path

import pytest

from money_machine.domain.models.product_spec import ProductFact, ProductSpec
from money_machine.integrations.notion.fixture_adapter import LocalNotionAdapter


def _spec() -> ProductSpec:
    return ProductSpec(
        product_spec_id="spec-001",
        candidate_id="candidate-001",
        identity_niche="Budget Moms",
        base_category="Planner",
        target_buyer="People managing Budget Moms",
        promised_outcome="A structured Planner workspace",
        hubs=("Home", "Tasks", "Events", "Habits", "Finance", "Meals", "Quick Notes"),
        colour_variants=("Sage Calm", "Ocean Focus", "Warm Sand"),
        features=("weekly priorities", "monthly calendar", "quick notes"),
        product_facts=(
            ProductFact(
                claim="Configured with 7 hubs",
                category="HUB_INVENTORY",
                evidence_ids=("evidence-001",),
            ),
            ProductFact(
                claim="Configured with 3 colour variants",
                category="COLOUR_VARIANTS",
                evidence_ids=("evidence-002",),
            ),
            ProductFact(
                claim="Includes weekly priorities",
                category="FEATURE",
                evidence_ids=("evidence-001",),
            ),
            ProductFact(
                claim="Includes monthly calendar",
                category="FEATURE",
                evidence_ids=("evidence-001",),
            ),
            ProductFact(
                claim="Includes quick notes",
                category="FEATURE",
                evidence_ids=("evidence-001",),
            ),
            ProductFact(
                claim="People managing Budget Moms",
                category="BUYER_FIT",
                evidence_ids=("evidence-001", "evidence-002"),
            ),
            ProductFact(
                claim="A structured Planner workspace",
                category="WORKFLOW_OUTCOME",
                evidence_ids=("evidence-001", "evidence-002"),
            ),
        ),
        source_evidence_ids=("evidence-001", "evidence-002"),
        spec_sha256="1" * 64,
    )


def test_builder_creates_complete_manifest_backed_bundle(tmp_path: Path) -> None:
    result = LocalNotionAdapter().build(_spec(), tmp_path / "product")
    root = Path(result.root_artifact_path)

    expected_paths = {
        "README.md",
        "home.html",
        "manifest.json",
        "product.json",
        "hubs/events.html",
        "hubs/finance.html",
        "hubs/habits.html",
        "hubs/home.html",
        "hubs/meals.html",
        "hubs/quick-notes.html",
        "hubs/tasks.html",
        "assets/ocean-focus.css",
        "assets/sage-calm.css",
        "assets/warm-sand.css",
    }
    assert {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()} == (
        expected_paths
    )
    assert {artifact.relative_path.as_posix() for artifact in result.artifacts} == (
        expected_paths - {"manifest.json"}
    )

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["renderer_version"] == "local-notion-v1"
    assert [entry["path"] for entry in manifest["artifacts"]] == sorted(
        expected_paths - {"manifest.json"}
    )
    assert all(
        set(entry) == {"byte_count", "media_type", "path", "sha256"}
        for entry in manifest["artifacts"]
    )

    home = (root / "home.html").read_text(encoding="utf-8")
    assert 'data-build-progress="6/6"' in home
    expected_hubs = ("tasks", "events", "habits", "finance", "meals", "quick-notes")
    assert all(f'href="hubs/{slug}.html"' in home for slug in expected_hubs)
    assert "People managing Budget Moms" in home
    assert "A structured Planner workspace" in home

    for path in root.rglob("*"):
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            assert "{{" not in content
            assert "TODO" not in content.upper()


def test_r5_behavior_contract_builder_is_deterministic_and_substantive(tmp_path: Path) -> None:
    try:
        first = LocalNotionAdapter().build(_spec(), tmp_path / "first")
        second = LocalNotionAdapter().build(_spec(), tmp_path / "second")
    except Exception as error:  # skeleton-stage assertion, removed by real behavior
        pytest.fail(f"builder behavior is not implemented: {error}")

    first_root = Path(first.root_artifact_path)
    assert first.build_id == second.build_id
    assert (first_root / "manifest.json").is_file()
    assert (first_root / "README.md").read_text(encoding="utf-8").startswith("# ")


def test_builder_is_byte_identical_and_idempotent_on_replay(tmp_path: Path) -> None:
    adapter = LocalNotionAdapter()
    first = adapter.build(_spec(), tmp_path / "first")
    replay = adapter.build(_spec(), tmp_path / "replay")
    repeated = adapter.build(_spec(), tmp_path / "first")

    first_root = Path(first.root_artifact_path)
    replay_root = Path(replay.root_artifact_path)
    first_bytes = {
        path.relative_to(first_root).as_posix(): path.read_bytes()
        for path in first_root.rglob("*")
        if path.is_file()
    }
    replay_bytes = {
        path.relative_to(replay_root).as_posix(): path.read_bytes()
        for path in replay_root.rglob("*")
        if path.is_file()
    }
    assert first_bytes == replay_bytes
    assert first.build_id == replay.build_id == repeated.build_id
    assert first.manifest_sha256 == replay.manifest_sha256 == repeated.manifest_sha256
    assert first.artifacts == replay.artifacts == repeated.artifacts


def test_hub_and_variant_slugs_must_be_unique(tmp_path: Path) -> None:
    duplicated = _spec().model_copy(
        update={
            "hubs": ("Home", "Tasks", "TASKS", "Habits", "Finance", "Meals"),
            "colour_variants": ("Sage Calm", "sage-calm", "Warm Sand"),
        }
    )

    try:
        LocalNotionAdapter().build(duplicated, tmp_path / "product")
    except ValueError as error:
        assert str(error) == "hub slugs must be unique"
    else:
        raise AssertionError("duplicate hub slugs were accepted")


def test_builder_escapes_untrusted_spec_text_and_emits_no_active_remote_content(
    tmp_path: Path,
) -> None:
    injected = _spec().model_copy(
        update={
            "target_buyer": '<script src="https://example.invalid/x.js"></script>',
            "promised_outcome": '<style>@import url("https://example.invalid/x.css")</style>',
        }
    )

    result = LocalNotionAdapter().build(injected, tmp_path / "product")
    rendered = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path(result.root_artifact_path).rglob("*")
        if path.suffix in {".html", ".md"}
    )

    assert "<script" not in rendered
    assert "<style" not in rendered
    assert "&lt;script" in rendered
    assert '<script src="https://example.invalid' not in rendered
    assert '<style>@import url("https://example.invalid' not in rendered


def test_builder_fails_closed_when_jinja_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import money_machine.integrations.notion.fixture_adapter as adapter_module

    def unavailable(template_root: Path) -> object:
        raise ModuleNotFoundError(str(template_root))

    monkeypatch.setattr(adapter_module, "_load_jinja_environment", unavailable)

    with pytest.raises(ModuleNotFoundError):
        LocalNotionAdapter()
