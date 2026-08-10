from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

import money_machine.application.services.product_service as product_service_module
from money_machine.application.services.product_service import ProductQAService
from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.models.product import BuildResult
from money_machine.domain.models.product_spec import ProductFact, ProductSpec
from money_machine.domain.value_objects import canonical_json
from money_machine.integrations.notion.fixture_adapter import LocalNotionAdapter
from money_machine.integrations.notion.interface import deterministic_build_id

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)


def _spec() -> ProductSpec:
    return ProductSpec(
        product_spec_id="spec-qa",
        candidate_id="candidate-qa",
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
                evidence_ids=("evidence-qa",),
            ),
            ProductFact(
                claim="Configured with 3 colour variants",
                category="COLOUR_VARIANTS",
                evidence_ids=("evidence-qa",),
            ),
            ProductFact(
                claim="Includes weekly priorities",
                category="FEATURE",
                evidence_ids=("evidence-qa",),
            ),
            ProductFact(
                claim="Includes monthly calendar",
                category="FEATURE",
                evidence_ids=("evidence-qa",),
            ),
            ProductFact(
                claim="Includes quick notes",
                category="FEATURE",
                evidence_ids=("evidence-qa",),
            ),
            ProductFact(
                claim="People managing Budget Moms",
                category="BUYER_FIT",
                evidence_ids=("evidence-qa",),
            ),
            ProductFact(
                claim="A structured Planner workspace",
                category="WORKFLOW_OUTCOME",
                evidence_ids=("evidence-qa",),
            ),
        ),
        source_evidence_ids=("evidence-qa",),
        spec_sha256="2" * 64,
    )


def _build(tmp_path: Path) -> BuildResult:
    return LocalNotionAdapter().build(_spec(), tmp_path / "product")


def _qa() -> ProductQAService:
    return ProductQAService(clock=lambda: NOW)


def _append(path: Path, text: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def _rewrite_manifest(
    build: BuildResult,
    root: Path,
    mutate: Callable[[dict[str, object]], None],
) -> BuildResult:
    raw_manifest: object = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert isinstance(raw_manifest, dict)
    manifest = cast(dict[str, object], raw_manifest)
    mutate(manifest)
    manifest_bytes = canonical_json(manifest) + b"\n"
    (root / "manifest.json").write_bytes(manifest_bytes)
    raw_artifacts = manifest["artifacts"]
    assert isinstance(raw_artifacts, list)
    artifacts = cast(list[dict[str, object]], raw_artifacts)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    return build.model_copy(
        update={
            "build_id": deterministic_build_id(
                build.product_spec_id, manifest_sha256, build.renderer_version
            ),
            "manifest_sha256": manifest_sha256,
            "artifacts": tuple(
                artifact
                for artifact in build.artifacts
                if any(
                    entry.get("path") == artifact.relative_path.as_posix() for entry in artifacts
                )
            ),
        }
    )


def _coherent_replace(build: BuildResult, relative_path: str, text: str) -> BuildResult:
    root = Path(build.root_artifact_path)
    data = text.encode("utf-8")
    (root / relative_path).write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    original = next(
        artifact
        for artifact in build.artifacts
        if artifact.relative_path.as_posix() == relative_path
    )
    identity = f"{relative_path}\0{original.media_type}\0{digest}".encode()
    replacement = ArtifactReference(
        artifact_id=f"artifact-{hashlib.sha256(identity).hexdigest()}",
        relative_path=Path(relative_path),
        media_type=original.media_type,
        byte_count=len(data),
        content_sha256=digest,
    )

    def update_entry(manifest: dict[str, object]) -> None:
        raw_artifacts = manifest["artifacts"]
        assert isinstance(raw_artifacts, list)
        entries = cast(list[dict[str, object]], raw_artifacts)
        entry = next(item for item in entries if item["path"] == relative_path)
        entry["byte_count"] = len(data)
        entry["sha256"] = digest

    updated = build.model_copy(
        update={
            "artifacts": tuple(
                replacement if artifact == original else artifact for artifact in build.artifacts
            )
        }
    )
    return _rewrite_manifest(updated, root, update_entry)


def _coherent_add_artifact(
    build: BuildResult, relative_path: str, data: bytes, media_type: str
) -> BuildResult:
    root = Path(build.root_artifact_path)
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    identity = f"{relative_path}\0{media_type}\0{digest}".encode()
    reference = ArtifactReference(
        artifact_id=f"artifact-{hashlib.sha256(identity).hexdigest()}",
        relative_path=Path(relative_path),
        media_type=media_type,
        byte_count=len(data),
        content_sha256=digest,
    )

    def append_entry(manifest: dict[str, object]) -> None:
        raw_artifacts = manifest["artifacts"]
        assert isinstance(raw_artifacts, list)
        entries = cast(list[dict[str, object]], raw_artifacts)
        entries.append(
            {
                "path": relative_path,
                "media_type": media_type,
                "byte_count": len(data),
                "sha256": digest,
            }
        )
        entries.sort(key=lambda entry: cast(str, entry["path"]))

    expanded = build.model_copy(update={"artifacts": (*build.artifacts, reference)})
    return _rewrite_manifest(expanded, root, append_entry)


def _coherent_change_media_type(
    build: BuildResult, relative_path: str, media_type: str
) -> BuildResult:
    root = Path(build.root_artifact_path)
    original = next(
        artifact
        for artifact in build.artifacts
        if artifact.relative_path.as_posix() == relative_path
    )
    identity = f"{relative_path}\0{media_type}\0{original.content_sha256}".encode()
    replacement = original.model_copy(
        update={
            "artifact_id": f"artifact-{hashlib.sha256(identity).hexdigest()}",
            "media_type": media_type,
        }
    )

    def update_entry(manifest: dict[str, object]) -> None:
        raw_artifacts = manifest["artifacts"]
        assert isinstance(raw_artifacts, list)
        entries = cast(list[dict[str, object]], raw_artifacts)
        entry = next(item for item in entries if item["path"] == relative_path)
        entry["media_type"] = media_type

    changed = build.model_copy(
        update={
            "artifacts": tuple(
                replacement if artifact == original else artifact for artifact in build.artifacts
            )
        }
    )
    return _rewrite_manifest(changed, root, update_entry)


def test_product_qa_passes_a_complete_bundle_deterministically(tmp_path: Path) -> None:
    build = _build(tmp_path)

    first = _qa().evaluate(build)
    replay = _qa().evaluate(build)

    assert first == replay
    assert first.passed is True
    assert first.findings == ()
    assert first.checked_at == NOW


@pytest.mark.parametrize(
    ("corruption", "expected_code"),
    [
        ("missing_hub", "HUB_MISSING:quick-notes"),
        ("broken_link", "BROKEN_INTERNAL_LINK:home.html->hubs/missing.html"),
        ("duplicate_slug", "DUPLICATE_HUB_SLUG:tasks"),
        ("placeholder", "PLACEHOLDER_TEXT:home.html"),
        ("absent_fact", "FACT_MISSING:Includes weekly priorities"),
        ("variant_drift", "VARIANT_DRIFT:assets/warm-sand.css"),
        ("modified_artifact", "ARTIFACT_HASH_MISMATCH:README.md"),
        ("absolute_path", "ABSOLUTE_ARTIFACT_PATH:/tmp/escape.txt"),
        ("network_url", "UNEXPECTED_NETWORK_URL:home.html->https://example.com"),
    ],
)
def test_product_qa_reports_exact_corruption_codes(
    tmp_path: Path, corruption: str, expected_code: str
) -> None:
    build = _build(tmp_path)
    root = Path(build.root_artifact_path)

    if corruption == "missing_hub":
        (root / "hubs/quick-notes.html").unlink()
    elif corruption == "broken_link":
        _append(root / "home.html", '<a href="hubs/missing.html">missing</a>')
    elif corruption == "duplicate_slug":
        product = json.loads((root / "product.json").read_text(encoding="utf-8"))
        product["hubs"] = [
            "Home",
            "Tasks",
            "TASKS",
            "Habits",
            "Finance",
            "Meals",
            "Quick Notes",
        ]
        (root / "product.json").write_text(json.dumps(product), encoding="utf-8")
    elif corruption == "placeholder":
        _append(root / "home.html", "{{ unfinished }}")
    elif corruption == "absent_fact":
        home = (root / "home.html").read_text(encoding="utf-8")
        (root / "home.html").write_text(
            home.replace("Includes weekly priorities", "offline package"), encoding="utf-8"
        )
    elif corruption == "variant_drift":
        _append(root / "assets/warm-sand.css", "\n.unexpected { display: none; }\n")
    elif corruption == "modified_artifact":
        _append(root / "README.md", "\nchanged\n")
    elif corruption == "absolute_path":
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        manifest["artifacts"][0]["path"] = "/tmp/escape.txt"
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    elif corruption == "network_url":
        _append(root / "home.html", '<a href="https://example.com">network</a>')

    result = _qa().evaluate(build)

    assert result.passed is False
    assert expected_code in result.findings
    assert result.findings == tuple(sorted(set(result.findings)))


def test_product_qa_does_not_follow_symlinks(tmp_path: Path) -> None:
    build = _build(tmp_path)
    root = Path(build.root_artifact_path)
    target = root / "README.md"
    target.unlink()
    target.symlink_to(tmp_path / "outside.md")

    result = _qa().evaluate(build)

    assert "SYMLINK_ARTIFACT:README.md" in result.findings


def test_product_qa_does_not_follow_symlinked_directories(tmp_path: Path) -> None:
    build = _build(tmp_path)
    root = Path(build.root_artifact_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    hub = root / "hubs/tasks.html"
    outside_hub = outside / "tasks.html"
    outside_hub.write_bytes(hub.read_bytes())
    for path in (root / "hubs").iterdir():
        path.unlink()
    (root / "hubs").rmdir()
    (root / "hubs").symlink_to(outside, target_is_directory=True)

    result = _qa().evaluate(build)

    assert "SYMLINK_ARTIFACT:hubs/tasks.html" in result.findings


def test_product_qa_rejects_coherent_required_file_omission(tmp_path: Path) -> None:
    build = _build(tmp_path)
    root = Path(build.root_artifact_path)
    (root / "README.md").unlink()

    def omit_readme(manifest: dict[str, object]) -> None:
        raw_artifacts = manifest["artifacts"]
        assert isinstance(raw_artifacts, list)
        artifacts = cast(list[dict[str, object]], raw_artifacts)
        manifest["artifacts"] = [entry for entry in artifacts if entry["path"] != "README.md"]

    coherent_build = _rewrite_manifest(build, root, omit_readme)
    result = _qa().evaluate(coherent_build)

    assert result.passed is False
    assert "REQUIRED_ARTIFACT_MISSING:README.md" in result.findings


def _remove_h1(text: str) -> str:
    return text.replace("<h1", "<div").replace("</h1>", "</div>")


def _empty_tasks_link(text: str) -> str:
    return text.replace(">Tasks</a>", "></a>")


def _add_unsupported_claim(text: str) -> str:
    return text + "<p>Guaranteed overnight success.</p>"


def _skip_heading_level(text: str) -> str:
    return text.replace("<h2>Designed for", "<h4>Designed for")


def _use_ambiguous_link_name(text: str) -> str:
    return text.replace(">Tasks</a>", ">click here</a>")


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("product_spec_id", "different-spec", "MANIFEST_PRODUCT_SPEC_MISMATCH"),
        ("renderer_version", "different-renderer", "MANIFEST_RENDERER_MISMATCH"),
    ],
)
def test_product_qa_binds_manifest_identity(
    tmp_path: Path, field: str, value: str, expected: str
) -> None:
    build = _build(tmp_path)
    root = Path(build.root_artifact_path)
    coherent_build = _rewrite_manifest(
        build, root, lambda manifest: manifest.__setitem__(field, value)
    )

    result = _qa().evaluate(coherent_build)

    assert expected in result.findings


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ('<style>@import url("https://example.invalid/x.css")</style>', "ACTIVE_CONTENT"),
        (
            '<div style="background:url(https://example.invalid/x.png)">x</div>',
            "UNEXPECTED_NETWORK_URL",
        ),
        (
            '<form action="https://example.invalid/submit"><button>Go</button></form>',
            "ACTIVE_CONTENT",
        ),
        (
            '<img srcset="local.png 1x, https://example.invalid/x.png 2x" alt="x">',
            "UNEXPECTED_NETWORK_URL",
        ),
        ('<meta http-equiv="refresh" content="0;url=https://example.invalid">', "ACTIVE_CONTENT"),
        ('<a href="javascript:alert(1)">run</a>', "UNSAFE_URL_SCHEME"),
    ],
)
def test_product_qa_rejects_active_content_and_remote_url_surfaces(
    tmp_path: Path, payload: str, expected: str
) -> None:
    build = _build(tmp_path)
    _append(Path(build.root_artifact_path) / "home.html", payload)

    result = _qa().evaluate(build)

    assert any(expected in finding for finding in result.findings)


@pytest.mark.parametrize(
    "payload",
    [
        '@import url("https://example.invalid/theme.css");',
        ".remote { background: url(//example.invalid/pixel.png); }",
    ],
)
def test_product_qa_rejects_remote_css_urls(tmp_path: Path, payload: str) -> None:
    build = _build(tmp_path)
    _append(Path(build.root_artifact_path) / "assets/sage-calm.css", payload)

    result = _qa().evaluate(build)

    assert any(
        "UNEXPECTED_NETWORK_URL:assets/sage-calm.css" in finding for finding in result.findings
    )


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            _remove_h1,
            "ACCESSIBLE_HEADING_MISSING",
        ),
        (_empty_tasks_link, "EMPTY_LINK_LABEL"),
        (_add_unsupported_claim, "UNSUPPORTED_CLAIM"),
    ],
)
def test_product_qa_enforces_accessibility_and_supported_claims(
    tmp_path: Path, mutation: Callable[[str], str], expected: str
) -> None:
    build = _build(tmp_path)
    home = Path(build.root_artifact_path) / "home.html"
    home.write_text(mutation(home.read_text(encoding="utf-8")), encoding="utf-8")

    result = _qa().evaluate(build)

    assert any(expected in finding for finding in result.findings)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("<body onload=\"fetch('https://example.invalid/pixel')\">", "ACTIVE_ATTRIBUTE"),
        ('<a href="home.html" ping="https://example.invalid/ping">Home</a>', "ACTIVE_ATTRIBUTE"),
        ('<html manifest="https://example.invalid/app.manifest">', "ACTIVE_ATTRIBUTE"),
        ('<svg><a href="https://example.invalid/x">Remote</a></svg>', "ACTIVE_TAG"),
        ('<math href="https://example.invalid/x">x</math>', "ACTIVE_TAG"),
        ('<a href="jav&#x61;script:alert(1)">Run report</a>', "UNSAFE_URL_SCHEME"),
    ],
)
def test_product_qa_rejects_coherent_executable_attributes_and_obfuscated_urls(
    tmp_path: Path, payload: str, expected: str
) -> None:
    build = _build(tmp_path)
    home_path = Path(build.root_artifact_path) / "home.html"
    coherent = _coherent_replace(build, "home.html", home_path.read_text() + payload)

    result = _qa().evaluate(coherent)

    assert any(expected in finding for finding in result.findings)


@pytest.mark.parametrize(
    "claim",
    [
        "Users double sales in 7 days.",
        "The market's most popular planner.",
        "Guaranteed demand from new customers.",
        "Compatible with every productivity platform.",
    ],
)
def test_product_qa_rejects_coherent_claims_not_bound_to_product_facts(
    tmp_path: Path, claim: str
) -> None:
    build = _build(tmp_path)
    home_path = Path(build.root_artifact_path) / "home.html"
    coherent = _coherent_replace(build, "home.html", home_path.read_text() + f"<p>{claim}</p>")

    result = _qa().evaluate(coherent)

    assert "UNSUPPORTED_CLAIM:home.html" in result.findings


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            _skip_heading_level,
            "HEADING_HIERARCHY_INVALID",
        ),
        (
            _use_ambiguous_link_name,
            "AMBIGUOUS_CONTROL_NAME",
        ),
    ],
)
def test_product_qa_rejects_coherent_heading_and_accessible_name_failures(
    tmp_path: Path,
    mutation: Callable[[str], str],
    expected: str,
) -> None:
    build = _build(tmp_path)
    home_path = Path(build.root_artifact_path) / "home.html"
    coherent = _coherent_replace(build, "home.html", mutation(home_path.read_text()))

    result = _qa().evaluate(coherent)

    assert any(expected in finding for finding in result.findings)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("media_type", "application/octet-stream", "BUILD_ARTIFACT_MEDIA_TYPE_MISMATCH"),
        ("byte_count", 1, "BUILD_ARTIFACT_BYTE_COUNT_MISMATCH"),
        ("content_sha256", "f" * 64, "BUILD_ARTIFACT_HASH_MISMATCH"),
        ("artifact_id", "artifact-wrong", "BUILD_ARTIFACT_ID_MISMATCH"),
    ],
)
def test_product_qa_binds_all_build_artifact_reference_metadata(
    tmp_path: Path, field: str, value: object, expected: str
) -> None:
    build = _build(tmp_path)
    target = build.artifacts[0].model_copy(update={field: value})
    altered = build.model_copy(update={"artifacts": (target, *build.artifacts[1:])})

    result = _qa().evaluate(altered)

    assert any(expected in finding for finding in result.findings)


def test_product_qa_rejects_build_root_with_runtime_symlinked_ancestor(
    tmp_path: Path,
) -> None:
    ancestor = tmp_path / "trusted"
    build = LocalNotionAdapter().build(_spec(), ancestor / "product")
    relocated = tmp_path / "relocated"
    ancestor.rename(relocated)
    ancestor.symlink_to(relocated, target_is_directory=True)

    result = _qa().evaluate(build)

    assert result.passed is False
    assert "BUILD_ROOT_INVALID" in result.findings


@pytest.mark.parametrize(
    "payload",
    [
        r'.remote { background: url("\68 ttps://example.invalid/pixel.png"); }',
        r'.remote { background: U/**/RL("HTTPS://example.invalid/pixel.png"); }',
        r'@\69 mport "https://example.invalid/theme.css";',
    ],
)
def test_product_qa_rejects_coherent_css_network_constructs(tmp_path: Path, payload: str) -> None:
    build = _build(tmp_path)
    css_path = Path(build.root_artifact_path) / "assets/sage-calm.css"
    coherent = _coherent_replace(build, "assets/sage-calm.css", css_path.read_text() + payload)

    result = _qa().evaluate(coherent)

    assert "CSS_NETWORK_CONSTRUCT:assets/sage-calm.css" in result.findings


@pytest.mark.parametrize(
    "claim",
    [
        "Users double sales in 7 days while offering seven hubs.",
        "plan the household week with confidence and double sales in 7 days.",
        "seven hubs, therefore guaranteed customer demand.",
    ],
)
def test_product_qa_rejects_claim_laundering_with_admitted_copy(tmp_path: Path, claim: str) -> None:
    build = _build(tmp_path)
    home_path = Path(build.root_artifact_path) / "home.html"
    coherent = _coherent_replace(build, "home.html", home_path.read_text() + f"<p>{claim}</p>")

    result = _qa().evaluate(coherent)

    assert "UNSUPPORTED_CLAIM:home.html" in result.findings


def test_product_qa_rejects_whitespace_accessible_name(tmp_path: Path) -> None:
    build = _build(tmp_path)
    home_path = Path(build.root_artifact_path) / "home.html"
    mutated = home_path.read_text().replace(
        '<a href="hubs/tasks.html">Tasks</a>',
        '<a href="hubs/tasks.html" aria-label="   "> </a>',
    )
    coherent = _coherent_replace(build, "home.html", mutated)

    result = _qa().evaluate(coherent)

    assert any("EMPTY_LINK_LABEL:home.html" in finding for finding in result.findings)


@pytest.mark.parametrize(
    "href",
    ["#missing-fragment", "home.html#missing-fragment", "hubs/tasks.html#missing-fragment"],
)
def test_product_qa_rejects_missing_internal_fragment_target(tmp_path: Path, href: str) -> None:
    build = _build(tmp_path)
    home_path = Path(build.root_artifact_path) / "home.html"
    coherent = _coherent_replace(
        build, "home.html", home_path.read_text() + f'<a href="{href}">Missing section</a>'
    )

    result = _qa().evaluate(coherent)

    assert any("BROKEN_INTERNAL_FRAGMENT:home.html" in finding for finding in result.findings)


def test_product_qa_rejects_artifact_symlink_swapped_at_final_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build(tmp_path)
    root = Path(build.root_artifact_path)
    target = root / "README.md"
    outside = tmp_path / "outside-readme.md"
    outside.write_bytes(target.read_bytes())
    swapped = False

    def swap_target() -> None:
        nonlocal swapped
        if swapped:
            return
        target.unlink()
        target.symlink_to(outside)
        swapped = True

    original_symlink_check = cast(
        Callable[[Path, Path], bool] | None,
        getattr(product_service_module, "_has_symlink_component", None),
    )

    def swap_after_legacy_check(check_root: Path, path: Path) -> bool:
        result = (
            False if original_symlink_check is None else original_symlink_check(check_root, path)
        )
        if path.name == "README.md" and not result:
            swap_target()
        return result

    original_open = os.open

    def swap_at_descriptor_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if os.fspath(path) == "README.md" and dir_fd is not None:
            swap_target()
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(
        product_service_module, "_has_symlink_component", swap_after_legacy_check, raising=False
    )
    monkeypatch.setattr(product_service_module.os, "open", swap_at_descriptor_open)

    result = _qa().evaluate(build)

    assert swapped is True
    assert "SYMLINK_ARTIFACT:README.md" in result.findings


@pytest.mark.parametrize(
    "payload",
    [
        'background-image: image-set("https://example.invalid/track.png" 1x);',
        'background-image: -webkit-image-set("//example.invalid/track.png" 1x);',
        r'background-image: \69 mage-set("https://example.invalid/track.png" 1x);',
        'background-image: cross-fade("https://example.invalid/a.png", none, 50%);',
    ],
)
def test_product_qa_rejects_every_unsupported_css_function(tmp_path: Path, payload: str) -> None:
    build = _build(tmp_path)
    css_path = Path(build.root_artifact_path) / "assets/sage-calm.css"
    coherent = _coherent_replace(build, "assets/sage-calm.css", css_path.read_text() + payload)

    result = _qa().evaluate(coherent)

    assert "CSS_NETWORK_CONSTRUCT:assets/sage-calm.css" in result.findings


@pytest.mark.parametrize(
    "claim",
    [
        "Users dou\u200bble sa\u200bles in 7 da\u200bys.",
        "\uff27\uff55\uff41\uff52\uff41\uff4e\uff54\uff45\uff45\uff44 demand from new customers.",
        "Users double sa\x00les in 7 days.",
        "Trusted by ten thousand buyers.",
        "Saves every buyer money.",
    ],
)
def test_product_qa_rejects_unicode_obfuscated_or_unclassified_claim_copy(
    tmp_path: Path, claim: str
) -> None:
    build = _build(tmp_path)
    home_path = Path(build.root_artifact_path) / "home.html"
    coherent = _coherent_replace(build, "home.html", home_path.read_text() + f"<p>{claim}</p>")

    result = _qa().evaluate(coherent)

    assert "UNSUPPORTED_CLAIM:home.html" in result.findings


@pytest.mark.parametrize(
    "label",
    ["!!!", "...", "---", "\u200b", "!\u200b!", "\uff0e\uff01\u2014"],
)
def test_product_qa_rejects_punctuation_or_format_only_accessible_names(
    tmp_path: Path, label: str
) -> None:
    build = _build(tmp_path)
    home_path = Path(build.root_artifact_path) / "home.html"
    mutated = home_path.read_text().replace(
        '<a href="hubs/tasks.html">Tasks</a>',
        f'<a href="hubs/tasks.html" aria-label="{label}">Tasks</a>',
    )
    coherent = _coherent_replace(build, "home.html", mutated)

    result = _qa().evaluate(coherent)

    assert any("EMPTY_LINK_LABEL:home.html" in finding for finding in result.findings)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("complete", None),
        ("empty_readme", "README_INVALID"),
        ("forged_build_id", "BUILD_ID_MISMATCH"),
        ("unsupported_li", "UNSUPPORTED_CLAIM:home.html"),
        ("unsupported_section", "UNSUPPORTED_CLAIM:home.html"),
        ("unsupported_readme", "UNSUPPORTED_CLAIM:README.md"),
        ("unterminated_control", "MALFORMED_CONTROL:home.html"),
        ("nested_control", "NESTED_CONTROL:home.html"),
    ],
)
def test_r5_behavior_contract_qa_is_fail_closed(
    tmp_path: Path, mutation: str, expected: str | None
) -> None:
    try:
        build = _build(tmp_path)
        if mutation == "empty_readme":
            build = _coherent_replace(build, "README.md", "")
        elif mutation == "forged_build_id":
            build = build.model_copy(update={"build_id": f"build-{'f' * 64}"})
        elif mutation == "unsupported_li":
            path = Path(build.root_artifact_path) / "home.html"
            build = _coherent_replace(
                build, "home.html", path.read_text() + "<li>Trusted by ten thousand buyers</li>"
            )
        elif mutation == "unsupported_section":
            path = Path(build.root_artifact_path) / "home.html"
            build = _coherent_replace(
                build,
                "home.html",
                path.read_text() + "<section>Every buyer saves money instantly</section>",
            )
        elif mutation == "unsupported_readme":
            path = Path(build.root_artifact_path) / "README.md"
            build = _coherent_replace(
                build, "README.md", path.read_text() + "\nTrusted by ten thousand buyers.\n"
            )
        elif mutation == "unterminated_control":
            path = Path(build.root_artifact_path) / "home.html"
            build = _coherent_replace(build, "home.html", path.read_text() + '<a href="home.html">')
        elif mutation == "nested_control":
            path = Path(build.root_artifact_path) / "home.html"
            build = _coherent_replace(
                build,
                "home.html",
                path.read_text() + '<a href="home.html"><button aria-label="Open"></button></a>',
            )
        result = _qa().evaluate(build)
    except Exception as error:  # skeleton-stage assertion, removed by real behavior
        pytest.fail(f"QA behavior is not implemented for {mutation}: {error}")

    if expected is None:
        assert result.passed is True
    else:
        assert expected in result.findings


@pytest.mark.parametrize(
    ("container", "copy", "expected_pass"),
    [
        ("li", "Configured with 7 hubs", True),
        ("section", "Configured with 7 hubs", True),
        ("h2", "Configured with 7 hubs", True),
        ("li", "Trusted by ten thousand buyers", False),
        ("section", "Every buyer saves money instantly", False),
    ],
)
def test_product_qa_uses_positive_claim_admission_for_every_html_container(
    tmp_path: Path, container: str, copy: str, expected_pass: bool
) -> None:
    build = _build(tmp_path)
    home = Path(build.root_artifact_path) / "home.html"
    coherent = _coherent_replace(
        build, "home.html", home.read_text() + f"<{container}>{copy}</{container}>"
    )

    result = _qa().evaluate(coherent)

    assert ("UNSUPPORTED_CLAIM:home.html" not in result.findings) is expected_pass


def test_product_qa_rejects_unsupported_markdown_copy(tmp_path: Path) -> None:
    build = _build(tmp_path)
    readme = Path(build.root_artifact_path) / "README.md"
    coherent = _coherent_replace(
        build, "README.md", readme.read_text() + "\nTrusted by ten thousand buyers.\n"
    )

    result = _qa().evaluate(coherent)

    assert "UNSUPPORTED_CLAIM:README.md" in result.findings


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ('<a href="home.html">', "MALFORMED_CONTROL:home.html"),
        (
            '<a href="home.html"><button aria-label="Open"></button></a>',
            "NESTED_CONTROL:home.html",
        ),
        ('<a href="home.html"><img src="local.png" alt="Dashboard"></a>', None),
        ('<a href="home.html" aria-label="Dashboard">ignored</a>', None),
        ('<a href="home.html"></button>', "MALFORMED_CONTROL:home.html"),
    ],
)
def test_product_qa_fails_closed_on_malformed_or_nested_controls(
    tmp_path: Path, payload: str, expected: str | None
) -> None:
    build = _build(tmp_path)
    home = Path(build.root_artifact_path) / "home.html"
    coherent = _coherent_replace(build, "home.html", home.read_text() + payload)

    result = _qa().evaluate(coherent)

    if expected is None:
        assert not any("CONTROL" in finding for finding in result.findings)
    else:
        assert expected in result.findings


def test_product_qa_rejects_forged_build_identity(tmp_path: Path) -> None:
    build = _build(tmp_path).model_copy(update={"build_id": f"build-{'f' * 64}"})

    result = _qa().evaluate(build)

    assert "BUILD_ID_MISMATCH" in result.findings


@pytest.mark.parametrize("readme", ["", "# Title\n", "# Wrong\n\nRenderer: `wrong`\n"])
def test_product_qa_requires_substantive_canonical_readme(tmp_path: Path, readme: str) -> None:
    build = _build(tmp_path)
    coherent = _coherent_replace(build, "README.md", readme)

    result = _qa().evaluate(coherent)

    assert "README_INVALID" in result.findings


@pytest.mark.parametrize(
    "uri",
    [
        "https:evil.example/path",
        "mailto:buyer@example.com",
        "ftp:evil.example/path",
        "blob:payload",
        "about:blank",
        "https%3Aevil.example/path",
    ],
)
def test_product_qa_rejects_scheme_laundering_as_manifest_paths(tmp_path: Path, uri: str) -> None:
    build = _build(tmp_path)
    root = Path(build.root_artifact_path)
    home = root / "home.html"
    coherent = _coherent_replace(
        build,
        "home.html",
        home.read_text() + f'<a href="{uri}">seven hubs</a>',
    )
    coherent = _coherent_add_artifact(coherent, uri, b"local decoy", "text/plain")

    result = _qa().evaluate(coherent)

    assert result.passed is False
    assert any(
        code in finding
        for finding in result.findings
        for code in ("UNSAFE_ARTIFACT_PATH", "UNSAFE_URL_SCHEME", "UNEXPECTED_NETWORK_URL")
    )


@pytest.mark.parametrize(
    "payload",
    [
        '<section aria-label="Trusted by ten thousand buyers"></section>',
        '<button type="button" aria-label="Trusted by ten thousand buyers"></button>',
        '<img src="home.html" alt="Trusted by ten thousand buyers">',
        '<a href="home.html" title="Trusted by ten thousand buyers">Tasks</a>',
        '<meta name="description" content="Trusted by ten thousand buyers">',
    ],
)
def test_product_qa_rejects_unbound_claims_in_semantic_attributes(
    tmp_path: Path, payload: str
) -> None:
    build = _build(tmp_path)
    home = Path(build.root_artifact_path) / "home.html"
    coherent = _coherent_replace(build, "home.html", home.read_text() + payload)

    result = _qa().evaluate(coherent)

    assert "UNSUPPORTED_CLAIM:home.html" in result.findings


@pytest.mark.parametrize(
    "payload",
    [
        '<meta name="keywords" content="Guaranteed sales overnight">',
        '<meta name="author" content="Trusted by ten thousand buyers">',
        '<meta name="arbitrary" content="Passive income guaranteed">',
    ],
)
def test_product_qa_rejects_unknown_semantic_metadata(tmp_path: Path, payload: str) -> None:
    build = _build(tmp_path)
    home = Path(build.root_artifact_path) / "home.html"
    coherent = _coherent_replace(build, "home.html", home.read_text() + payload)

    result = _qa().evaluate(coherent)

    assert result.passed is False
    assert "INVALID_METADATA:home.html" in result.findings


def test_product_qa_accepts_exact_renderer_structural_metadata(tmp_path: Path) -> None:
    build = _build(tmp_path)
    home = Path(build.root_artifact_path) / "home.html"

    assert '<meta charset="utf-8">' in home.read_text(encoding="utf-8")
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in home.read_text(
        encoding="utf-8"
    )
    assert _qa().evaluate(build).passed is True


_DUPLICATE_ATTRIBUTE_CASES = [
    ("aria-label", "section", "seven hubs", "Trusted by ten thousand buyers"),
    ("title", "a", "seven hubs", "Trusted by ten thousand buyers"),
    ("alt", "img", "seven hubs", "Trusted by ten thousand buyers"),
    ("name", "meta", "viewport", "arbitrary"),
    ("content", "meta", "width=device-width, initial-scale=1", "Passive income guaranteed"),
    ("href", "a", "home.html", "https://evil.example/path"),
    ("src", "img", "home.html", "https://evil.example/pixel.png"),
    ("srcset", "img", "home.html 1x", "https://evil.example/pixel.png 2x"),
]


def _duplicate_attribute_payload(
    attribute: str,
    tag: str,
    first: str,
    second: str,
    *,
    second_name: str | None = None,
) -> str:
    attributes = f'{attribute}="{first}" {second_name or attribute}="{second}"'
    if tag == "section":
        return f"<section {attributes}></section>"
    if tag == "a":
        return (
            f'<a {attributes} href="home.html">seven hubs</a>'
            if attribute != "href"
            else f"<a {attributes}>seven hubs</a>"
        )
    if tag == "img":
        return (
            f'<img {attributes} src="home.html">'
            if attribute not in {"src", "srcset"}
            else f'<img {attributes} alt="seven hubs">'
        )
    if attribute == "name":
        return f'<meta {attributes} content="width=device-width, initial-scale=1">'
    return f'<meta name="viewport" {attributes}>'


@pytest.mark.parametrize("attribute,tag,safe,unsafe", _DUPLICATE_ATTRIBUTE_CASES)
@pytest.mark.parametrize("unsafe_first", [False, True], ids=["safe-first", "unsafe-first"])
def test_product_qa_rejects_duplicate_attributes_in_both_orders(
    tmp_path: Path,
    attribute: str,
    tag: str,
    safe: str,
    unsafe: str,
    *,
    unsafe_first: bool,
) -> None:
    build = _build(tmp_path)
    home = Path(build.root_artifact_path) / "home.html"
    first, second = (unsafe, safe) if unsafe_first else (safe, unsafe)
    payload = _duplicate_attribute_payload(attribute, tag, first, second)
    coherent = _coherent_replace(build, "home.html", home.read_text() + payload)

    result = _qa().evaluate(coherent)

    assert result.passed is False
    assert f"DUPLICATE_ATTRIBUTE:home.html:{tag}[{attribute}]" in result.findings


@pytest.mark.parametrize("attribute,tag,safe,unsafe", _DUPLICATE_ATTRIBUTE_CASES)
def test_product_qa_rejects_case_variant_duplicate_attributes(
    tmp_path: Path,
    attribute: str,
    tag: str,
    safe: str,
    unsafe: str,
) -> None:
    build = _build(tmp_path)
    home = Path(build.root_artifact_path) / "home.html"
    payload = _duplicate_attribute_payload(
        attribute,
        tag,
        safe,
        unsafe,
        second_name=attribute.upper(),
    )
    coherent = _coherent_replace(build, "home.html", home.read_text() + payload)

    result = _qa().evaluate(coherent)

    assert result.passed is False
    assert f"DUPLICATE_ATTRIBUTE:home.html:{tag}[{attribute}]" in result.findings


@pytest.mark.parametrize("unexpected", ["payload.html", "assets/remote.js"])
def test_product_qa_rejects_unmanifested_inventory_entries(tmp_path: Path, unexpected: str) -> None:
    build = _build(tmp_path)
    target = Path(build.root_artifact_path) / unexpected
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('fetch("https://example.invalid/x")', encoding="utf-8")

    result = _qa().evaluate(build)

    assert f"UNEXPECTED_BUNDLE_ENTRY:{unexpected}" in result.findings


def test_product_qa_rejects_unmanifested_symlink_inventory_entry(tmp_path: Path) -> None:
    build = _build(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    (Path(build.root_artifact_path) / "outside-link").symlink_to(outside)

    result = _qa().evaluate(build)

    assert "UNSAFE_BUNDLE_ENTRY:outside-link" in result.findings


def test_product_qa_rejects_manifest_declared_active_artifact(tmp_path: Path) -> None:
    build = _build(tmp_path)
    coherent = _coherent_add_artifact(
        build,
        "assets/remote.js",
        b'fetch("https://example.invalid/x")',
        "text/javascript",
    )

    result = _qa().evaluate(coherent)

    assert "UNEXPECTED_MANIFEST_ARTIFACT:assets/remote.js" in result.findings


@pytest.mark.parametrize(
    "replacement",
    [
        "makes ~~no~~ network requests",
        "makes <!--no--> network requests",
    ],
)
def test_product_qa_rejects_readme_markdown_semantic_laundering(
    tmp_path: Path, replacement: str
) -> None:
    build = _build(tmp_path)
    readme = Path(build.root_artifact_path) / "README.md"
    coherent = _coherent_replace(
        build,
        "README.md",
        readme.read_text().replace("makes no network requests", replacement),
    )

    result = _qa().evaluate(coherent)

    assert "README_INVALID" in result.findings


@pytest.mark.parametrize(
    ("path", "media_type"),
    [
        ("product.json", "application/octet-stream"),
        ("README.md", "text/plain"),
        ("home.html", "application/octet-stream"),
        ("assets/sage-calm.css", "text/plain"),
    ],
)
def test_product_qa_enforces_media_type_by_artifact_role(
    tmp_path: Path, path: str, media_type: str
) -> None:
    build = _build(tmp_path)
    coherent = _coherent_change_media_type(build, path, media_type)

    result = _qa().evaluate(coherent)

    assert f"ARTIFACT_MEDIA_TYPE_INVALID:{path}" in result.findings
