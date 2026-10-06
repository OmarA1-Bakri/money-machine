"""Fixture-only product variants. Not a seventh build phase."""

from __future__ import annotations

import json
import socket
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from money_machine.agents.implementations import notion_variants as notion_variants_module
from money_machine.agents.implementations.notion_aesthetics import (
    build_aesthetics_and_content_completion,
)
from money_machine.agents.implementations.notion_dashboard import build_dashboard_and_navigation
from money_machine.agents.implementations.notion_hubs import build_identity_specific_hubs
from money_machine.agents.implementations.notion_notifications import build_notification_dashboard
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    PRODUCT_ID_PROPERTY,
    SHELL_BLOCK_PROPERTY,
    SPEC_ID_PROPERTY,
    ProductBuildError,
    build_top_level_page_and_design_shell,
    find_spec_page,
)
from money_machine.agents.implementations.notion_progress import (
    OP_VARIANTS,
    ProviderFailure,
    stamp_integrity_digest,
)
from money_machine.agents.implementations.notion_progress_record import CheckpointView
from money_machine.agents.implementations.notion_shared_databases import build_shared_databases
from money_machine.agents.implementations.notion_variants import PHASE_QA, build_variants
from money_machine.control.state import SESSION_EVIDENCE_KEYS
from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.product_spec import ColourToken, Hub, ProductSpec
from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.domain import NotionCalloutBlock, NotionPage, NotionTextBlock
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from tests.fixtures.products import create_fixture_product_spec

ROOT = Path(__file__).parents[3]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
MODULE_PATH = ROOT / "src/money_machine/agents/implementations/notion_variants.py"
WHEN = datetime(2026, 10, 3, 0, 30, tzinfo=UTC)
PHASE_TWO_AT = datetime(2026, 10, 5, 20, 0, tzinfo=UTC)
DASHBOARD_AT = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)
HUBS_AT = datetime(2026, 10, 5, 23, 45, tzinfo=UTC)
NOTIFICATION_AT = datetime(2026, 10, 6, 0, 30, tzinfo=UTC)
LATER = datetime(2026, 10, 6, 1, 30, tzinfo=UTC)
VARIANTS_AT = datetime(2026, 10, 6, 2, 30, tzinfo=UTC)
CLOSURE_SHA = "0f94d585f23d79e5ac18479f01e14f67cbaad332"
HEAD_SHA = "9bc56b2c839f66fce13bebf55cb30e88474f526e"
BOOTSTRAP_SHA = "1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d"


def _spec(
    *,
    tier: str = "mass",
    identity: str = "Weekly Planner",
    title: str = "Home Dashboard Planner",
    hub_name: str = "Hub",
) -> ProductSpec:
    return ProductSpec(
        spec_id=uuid4(),
        product_id=uuid4(),
        workflow_id=uuid4(),
        version=1,
        producing_job_id=uuid4(),
        producing_agent_run_id=uuid4(),
        identity=identity,
        base_category="Planners",
        buyer_problem="Keep one week visible",
        title=title,
        tier=tier,
        real_price=Decimal("9.99"),
        anchor_price=Decimal("19.99"),
        currency="USD",
        palette_name="Modern Minimalist",
        palette_tokens=(
            ColourToken(name="Primary", hex="#2C3E50"),
            ColourToken(name="Secondary", hex="#3498DB"),
            ColourToken(name="Accent", hex="#E74C3C"),
        ),
        hubs=tuple(
            Hub(name=f"{hub_name} {index}", description=f"{identity} copy {index}", page_count=3)
            for index in range(1, 7)
        ),
        colour_variants=("Blue", "Green", "Purple"),
        flagship_feature="One visible week",
        experiment_hypothesis="A visible week is enough",
        shared_databases=(),
        page_target_min=40,
        page_target_max=60,
        concept_fingerprint="c" * 64,
        rule_version="v1",
        evidence=(
            EvidenceReference(
                evidence_id=uuid4(),
                evidence_type="fixture",
                source_reference="tests/unit/agents/test_notion_product_builder_variants.py",
                observed_at=WHEN,
                safe_summary="Variants fixture spec",
            ),
        ),
        created_at=WHEN,
    )


async def _through_notification(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=WHEN)
    await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)
    await build_dashboard_and_navigation(spec, probe, path, recorded_at=DASHBOARD_AT)
    await build_identity_specific_hubs(spec, probe, path, recorded_at=HUBS_AT)
    await build_notification_dashboard(spec, probe, path, recorded_at=NOTIFICATION_AT)


async def _prepare(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await _through_notification(spec, probe, path)
    await build_aesthetics_and_content_completion(spec, probe, path, recorded_at=LATER)


def _home(probe: FixtureNotionAdapter, spec: ProductSpec) -> NotionPage:
    return next(page for page in probe.pages.values() if page.title == spec.title)


def _expected_copy(spec: ProductSpec, colour: str, token: ColourToken) -> str:
    return f"SAMPLE {spec.identity} / {colour}: {token.name} {token.hex}"


def _four_spec() -> ProductSpec:
    return _spec().model_copy(
        update={
            "palette_tokens": (
                *_spec().palette_tokens,
                ColourToken(name="Neutral", hex="#111111"),
            ),
            "colour_variants": ("Blue", "Green", "Purple", "Gold"),
        }
    )


_WRITE_METHODS = (
    "add_callout_block",
    "add_child_page",
    "add_property",
    "add_text_block",
    "create_database",
    "create_formula",
    "create_linked_view",
    "create_page",
    "create_relation",
    "create_rollup",
    "drop_page_property",
    "duplicate_page",
    "publish_page",
    "rename_page",
    "set_cover",
    "set_duplicate_as_template",
    "set_icon",
    "set_search_indexing",
)


def _watch(probe: FixtureNotionAdapter) -> list[str]:
    calls: list[str] = []
    for name in _WRITE_METHODS:
        original = getattr(probe, name)

        def _bind(
            method: Callable[..., Awaitable[object]], label: str
        ) -> Callable[..., Awaitable[object]]:
            async def wrapped(*args: object, **kwargs: object) -> object:
                calls.append(label)
                return await method(*args, **kwargs)

            return wrapped

        setattr(probe, name, _bind(original, name))
    return calls


def _restamp(path: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    document = json.loads(path.read_text(encoding="ascii"))
    mutate(document)
    stamped = stamp_integrity_digest(document)
    path.write_text(
        json.dumps(stamped, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )


def _assert_finished(spec: ProductSpec, probe: FixtureNotionAdapter, started: int) -> None:
    assert len(probe.pages) == started + len(spec.colour_variants)
    titles = [page.title for page in probe.pages.values()]
    assert not any(title.endswith(" (Copy)") for title in titles)
    for colour, token in zip(spec.colour_variants, spec.palette_tokens, strict=True):
        title = f"{spec.title} / {colour}"
        assert titles.count(title) == 1
        page = next(item for item in probe.pages.values() if item.title == title)
        assert page.is_published is True
        assert page.duplicate_as_template is True
        assert page.search_indexing is False
        assert SPEC_ID_PROPERTY not in page.properties
        assert page.icon == f"palette:{token.name}:{token.hex}"
        assert page.cover == f"fixture://palette/{token.name}/{token.hex}"


@pytest.mark.asyncio
async def test_mass_tier_publishes_one_page_per_colour(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    original = (
        home.title,
        home.icon,
        home.cover,
        home.is_published,
        home.duplicate_as_template,
        home.search_indexing,
        dict(home.properties),
    )
    pages = set(probe.pages)
    databases = set(probe.databases)
    before = json.loads(path.read_text(encoding="ascii"))["progress"]
    assert before["created_notion_ids"]["variants"] is None

    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert checkpoint.checkpoint_names == BUILD_PHASES
    assert checkpoint.next_phase == PHASE_QA
    assert checkpoint.recorded_at == VARIANTS_AT
    assert len(checkpoint.variants) == 3
    assert len(probe.pages) == len(pages) + 3
    assert set(probe.databases) == databases
    assert (
        home.title,
        home.icon,
        home.cover,
        home.is_published,
        home.duplicate_as_template,
        home.search_indexing,
        dict(home.properties),
    ) == original
    assert home.is_published is False
    found = find_spec_page(probe, str(spec.spec_id))
    assert found is not None and found.id == home.id
    copies = [
        _expected_copy(spec, colour, token)
        for colour, token in zip(spec.colour_variants, spec.palette_tokens, strict=True)
    ]
    assert len(set(copies)) == 3
    for record, colour, token, copy in zip(
        checkpoint.variants, spec.colour_variants, spec.palette_tokens, copies, strict=True
    ):
        page = probe.pages[record.page_id]
        assert page.title == f"{spec.title} / {colour}"
        assert page.parent_type == "workspace"
        assert page.parent_id == home.parent_id
        assert page.icon == f"palette:{token.name}:{token.hex}"
        assert page.cover == f"fixture://palette/{token.name}/{token.hex}"
        assert page.is_published is True
        assert page.duplicate_as_template is True
        assert page.search_indexing is False
        assert page.public_url == record.secret_link
        assert SPEC_ID_PROPERTY not in page.properties
        assert page.properties["product_id"] == str(spec.product_id)
        children = [block for block in probe.blocks.values() if block.parent_id == page.id]
        assert len(children) == 2
        accent = next(block for block in children if type(block) is NotionCalloutBlock)
        vocabulary = next(block for block in children if type(block) is NotionTextBlock)
        assert accent.id == record.accent_block_id
        assert accent.content == f"palette {token.name} {token.hex}"
        assert vocabulary.id == record.vocabulary_block_id
        assert vocabulary.content == copy
        assert "client_name" not in vocabulary.content
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["checkpoint_names"] == list(BUILD_PHASES)
    progress = stored["progress"]
    assert progress["completed_operations"] == list(BUILD_PHASES)
    assert progress["deferred_operations"] == []
    assert len(progress["created_notion_ids"]["variants"]) == 3
    assert progress["page_counts"]["pages"] == before["page_counts"]["pages"] + 3
    assert progress["page_counts"]["blocks"] == before["page_counts"]["blocks"] + 6
    assert progress["page_counts"]["databases"] == before["page_counts"]["databases"]


@pytest.mark.asyncio
async def test_business_tier_keeps_its_identity_in_the_vocabulary(tmp_path: Path) -> None:
    spec = _spec(tier="business", identity="Studio Ledger", title="Studio Home", hub_name="Desk")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    pages = len(probe.pages)

    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert pages == 9
    assert len(probe.pages) == 12
    assert len(checkpoint.variants) == 3
    variant_ids = {record.page_id for record in checkpoint.variants}
    text = {
        block.content
        for block in probe.blocks.values()
        if type(block) is NotionTextBlock and block.parent_id in variant_ids
    }
    assert text == {
        _expected_copy(spec, colour, token)
        for colour, token in zip(spec.colour_variants, spec.palette_tokens, strict=True)
    }


@pytest.mark.asyncio
async def test_four_colour_spec_publishes_four_variants(tmp_path: Path) -> None:
    spec = _spec().model_copy(
        update={
            "palette_tokens": (
                *_spec().palette_tokens,
                ColourToken(name="Neutral", hex="#111111"),
            ),
            "colour_variants": ("Blue", "Green", "Purple", "Gold"),
        }
    )
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    pages = len(probe.pages)

    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert len(checkpoint.variants) == 4
    assert len(probe.pages) == pages + 4
    assert checkpoint.variants[-1].name == "Gold"
    assert checkpoint.variants[-1].token_name == "Neutral"


@pytest.mark.asyncio
async def test_replay_keeps_the_same_bytes_and_ids(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    first = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    raw = path.read_bytes()
    pages = set(probe.pages)

    second = await build_variants(
        spec, probe, path, recorded_at=datetime(2026, 10, 6, 3, tzinfo=UTC)
    )

    assert path.read_bytes() == raw
    assert set(probe.pages) == pages
    assert second.variants == first.variants
    assert second.next_phase == PHASE_QA


@pytest.mark.asyncio
async def test_aesthetics_replay_after_variants_writes_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    raw = path.read_bytes()
    pages = set(probe.pages)

    with pytest.raises(ProductBuildError, match="hub page is unexpected"):
        await build_aesthetics_and_content_completion(spec, probe, path, recorded_at=VARIANTS_AT)

    assert path.read_bytes() == raw
    assert set(probe.pages) == pages


@pytest.mark.asyncio
async def test_missing_checkpoint_and_earlier_phase_write_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    missing = tmp_path / "absent.json"
    with pytest.raises(ProductBuildError, match="aesthetics checkpoint"):
        await build_variants(spec, probe, missing, recorded_at=VARIANTS_AT)
    assert not missing.exists()
    assert probe.pages == {}

    path = tmp_path / "build.json"
    await _through_notification(spec, probe, path)
    raw = path.read_bytes()
    pages = set(probe.pages)
    with pytest.raises(ProductBuildError, match="aesthetics checkpoint"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    assert path.read_bytes() == raw
    assert set(probe.pages) == pages


@pytest.mark.asyncio
async def test_mismatched_or_duplicate_colours_write_nothing(tmp_path: Path) -> None:
    longer = _spec().model_copy(
        update={
            "palette_tokens": (
                *_spec().palette_tokens,
                ColourToken(name="Neutral", hex="#111111"),
            )
        }
    )
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(longer, probe, path)
    raw = path.read_bytes()
    pages = set(probe.pages)
    with pytest.raises(ProductBuildError, match="does not match palette tokens"):
        await build_variants(longer, probe, path, recorded_at=VARIANTS_AT)
    assert path.read_bytes() == raw
    assert set(probe.pages) == pages

    duplicated = _spec().model_copy(update={"colour_variants": ("Blue", "Blue", "Green")})
    other = tmp_path / "duplicated.json"
    other_probe = FixtureNotionAdapter()
    await _prepare(duplicated, other_probe, other)
    duplicated_raw = other.read_bytes()
    with pytest.raises(ProductBuildError, match="colour variant name is duplicated"):
        await build_variants(duplicated, other_probe, other, recorded_at=VARIANTS_AT)
    assert other.read_bytes() == duplicated_raw


@pytest.mark.asyncio
async def test_provider_failure_resumes_without_a_second_copy(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    pages = set(probe.pages)
    probe.fail_operation = OP_VARIANTS  # type: ignore[attr-defined]
    probe.fail_response = "variant refused"  # type: ignore[attr-defined]

    with pytest.raises(ProductBuildError, match="variant refused"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    extra = set(probe.pages) - pages
    assert len(extra) == 1
    kept = next(iter(extra))
    stored = json.loads(path.read_text(encoding="ascii"))
    assert "variants" not in stored["provider_object_references"]
    job = stored["progress"]["repair_jobs"][-1]
    assert job == {
        "kind": "provider_response",
        "operation": OP_VARIANTS,
        "phase": "aesthetics_and_content_completion",
        "response": "variant refused",
    }
    del probe.fail_operation  # type: ignore[attr-defined]
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    assert kept in {record.page_id for record in checkpoint.variants}
    assert len(probe.pages) == len(pages) + len(spec.colour_variants)
    titles = [page.title for page in probe.pages.values()]
    assert titles.count(f"{spec.title} / Blue") == 1


@pytest.mark.asyncio
async def test_replay_rejects_a_tampered_variant_page_id(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    document = json.loads(path.read_text(encoding="ascii"))
    created = document["progress"]["created_notion_ids"]
    created["variants"][0]["page_id"] = "page_missing"
    stamped = stamp_integrity_digest(document)
    path.write_text(
        json.dumps(stamped, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )

    with pytest.raises(ProductBuildError, match="progress created ids do not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)


def _tamper_created(document: dict[str, object], kind: str) -> None:
    progress = document["progress"]
    assert type(progress) is dict
    created = progress["created_notion_ids"]
    assert type(created) is dict
    if kind == "hub":
        hubs = created["hubs"]
        assert type(hubs) is list and type(hubs[0]) is dict
        hubs[0]["page_id"] = "page_missing"
        return
    if kind == "database":
        databases = created["databases"]
        assert type(databases) is list and type(databases[0]) is dict
        databases[0]["database_id"] = "db_missing"
        return
    raise AssertionError(kind)


def _drop_home_accent(probe: FixtureNotionAdapter, spec: ProductSpec) -> None:
    home = _home(probe, spec)
    accent_id = next(
        block.id
        for block in probe.blocks.values()
        if type(block) is NotionCalloutBlock
        and block.parent_id == home.id
        and block.content.startswith("palette ")
    )
    del probe.blocks[accent_id]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["empty", "stored"])
@pytest.mark.parametrize("kind", ["hub", "database", "accent"])
async def test_earlier_phase_tamper_writes_nothing(tmp_path: Path, stage: str, kind: str) -> None:
    spec = _four_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    if stage == "stored":
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    if kind == "accent":
        _drop_home_accent(probe, spec)
    else:
        _restamp(path, lambda document: _tamper_created(document, kind))
    raw = path.read_bytes()
    calls = _watch(probe)
    message = "aesthetics accent" if kind == "accent" else "progress created ids do not match"

    with pytest.raises(ProductBuildError, match=message):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


async def _plant_leftover_spec_id(
    probe: FixtureNotionAdapter, spec: ProductSpec, shape: str
) -> None:
    home = _home(probe, spec)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    assert type(spec_value) is str
    if shape == "copy":
        copy = await probe.duplicate_page(home.id)
        assert copy.title == f"{home.title} (Copy)"
        assert copy.properties.get(SPEC_ID_PROPERTY) == spec_value
        return
    if shape == "titled":
        title = f"{spec.title} / {spec.colour_variants[0]}"
        titled = next((page for page in probe.pages.values() if page.title == title), None)
        if titled is None:
            created = await probe.duplicate_page(home.id)
            titled = await probe.rename_page(created.id, title)
        titled.properties[SPEC_ID_PROPERTY] = spec_value
        return
    raise AssertionError(shape)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["empty", "stored"])
@pytest.mark.parametrize("kind", ["hub", "database", "accent"])
@pytest.mark.parametrize("shape", ["titled", "copy"])
async def test_leftover_spec_id_tamper_writes_nothing(
    tmp_path: Path, stage: str, kind: str, shape: str
) -> None:
    spec = _four_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    if stage == "stored":
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    if kind == "accent":
        _drop_home_accent(probe, spec)
    else:
        _restamp(path, lambda document: _tamper_created(document, kind))
    await _plant_leftover_spec_id(probe, spec, shape)
    raw = path.read_bytes()
    calls = _watch(probe)
    message = "aesthetics accent" if kind == "accent" else "progress created ids do not match"

    with pytest.raises(ProductBuildError, match=message):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("shape", ["titled", "copy"])
@pytest.mark.parametrize("body", ["empty", "private"])
async def test_unrelated_page_is_not_adopted(tmp_path: Path, shape: str, body: str) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    title = f"{spec.title} / Blue" if shape == "titled" else f"{home.title} (Copy)"
    if body == "private":
        page = await probe.duplicate_page(home.id)
        if shape == "titled":
            page = await probe.rename_page(page.id, title)
        await probe.add_text_block(page.id, "private note")
    else:
        page = await probe.create_page(title, parent_id=home.parent_id, parent_type="workspace")
    raw = path.read_bytes()
    pages = set(probe.pages)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert set(probe.pages) == pages
    stored = json.loads(path.read_text(encoding="ascii"))
    assert "variants" not in stored["provider_object_references"]
    assert page.is_published is False
    assert page.title == title


@pytest.mark.asyncio
async def test_mixed_leftover_and_unrelated_spec_id_writes_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    assert type(spec_value) is str
    copy = await probe.duplicate_page(home.id)
    assert copy.title == f"{home.title} (Copy)"
    assert copy.properties.get(SPEC_ID_PROPERTY) == spec_value
    other = await probe.create_page(
        f"{spec.title} / Blue", parent_id=home.parent_id, parent_type="workspace"
    )
    other.properties[SPEC_ID_PROPERTY] = spec_value
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert copy.properties.get(SPEC_ID_PROPERTY) == spec_value
    assert other.properties.get(SPEC_ID_PROPERTY) == spec_value
    assert copy.is_published is False
    assert other.is_published is False
    stored = json.loads(path.read_text(encoding="ascii"))
    assert "variants" not in stored["provider_object_references"]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["database", "page"])
async def test_copy_with_a_nested_child_writes_nothing(tmp_path: Path, kind: str) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    copy = await probe.duplicate_page(home.id)
    if kind == "database":
        await probe.create_database("Private", parent_id=copy.id, parent_type="page_id")
    elif kind == "page":
        await probe.create_page("Nested", parent_id=copy.id, parent_type="page_id")
    else:
        raise AssertionError(kind)
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert SPEC_ID_PROPERTY in copy.properties
    assert copy.is_published is False
    assert copy.duplicate_as_template is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    ["parent_type", "parent_id", "product_id", "shell_block", "foreign_child", "release_shell"],
)
async def test_one_adoption_field_refuses_before_any_write(tmp_path: Path, field: str) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    copy = await probe.duplicate_page(home.id)
    if field == "parent_type":
        copy.parent_type = "page_id"
    elif field == "parent_id":
        copy.parent_id = "other-parent"
    elif field == "product_id":
        copy.properties[PRODUCT_ID_PROPERTY] = "other-product"
    elif field == "shell_block":
        copy.properties[SHELL_BLOCK_PROPERTY] = "other-shell"
    elif field == "foreign_child":
        await probe.drop_page_property(copy.id, SPEC_ID_PROPERTY)
        await probe.add_text_block(copy.id, "private note")
    elif field == "release_shell":
        copy.properties[PRODUCT_ID_PROPERTY] = "other-product"
    else:
        raise AssertionError(field)
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert copy.is_published is False


@pytest.mark.asyncio
async def test_release_keeps_a_different_spec_id_value(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    copy = await probe.duplicate_page(home.id)
    copy.properties[SPEC_ID_PROPERTY] = "other-spec"
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert copy.properties.get(SPEC_ID_PROPERTY) == "other-spec"
    assert copy.is_published is False


@pytest.mark.asyncio
async def test_release_provider_failure_records_a_repair_job(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    copy = await probe.duplicate_page(home.id)
    before = json.loads(path.read_text(encoding="ascii"))

    async def _boom(page_id: str, name: str) -> NotionPage:
        raise ProviderFailure(OP_VARIANTS, "drop refused")

    probe.drop_page_property = _boom  # type: ignore[method-assign]

    with pytest.raises(ProductBuildError, match="drop refused"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert SPEC_ID_PROPERTY in copy.properties
    assert copy.is_published is False
    stored = json.loads(path.read_text(encoding="ascii"))
    progress = stored["progress"]
    before_progress = before["progress"]
    assert type(progress) is dict and type(before_progress) is dict
    jobs = progress["repair_jobs"]
    before_jobs = before_progress["repair_jobs"]
    assert type(jobs) is list and type(before_jobs) is list
    assert len(jobs) == len(before_jobs) + 1
    job = jobs[-1]
    assert type(job) is dict
    assert job["kind"] == "provider_response"
    assert job["response"] == "drop refused"
    assert "variants" not in stored["provider_object_references"]


@pytest.mark.asyncio
async def test_replay_refuses_a_restored_spec_id_without_a_write(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    page = probe.pages[checkpoint.variants[0].page_id]
    page.properties[SPEC_ID_PROPERTY] = str(spec.spec_id)
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert SPEC_ID_PROPERTY in page.properties


@pytest.mark.asyncio
async def test_replay_refuses_an_unrelated_workspace_page(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    home = _home(probe, spec)
    extra = await probe.create_page("Scratch", parent_id=home.parent_id, parent_type="workspace")
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="hub page is unexpected"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert extra.is_published is False


@pytest.mark.asyncio
async def test_replay_refuses_a_database_under_a_variant(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    page = probe.pages[checkpoint.variants[0].page_id]
    await probe.create_database("Private", parent_id=page.id, parent_type="page_id")
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert page.is_published is True


@pytest.mark.asyncio
async def test_release_keeps_another_products_spec_id_on_private_notes(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    notes = await probe.create_page(
        "Private Notes", parent_id=home.parent_id, parent_type="workspace"
    )
    notes.properties[SPEC_ID_PROPERTY] = "other-spec"
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="hub page is unexpected"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert notes.properties[SPEC_ID_PROPERTY] == "other-spec"
    assert notes.title == "Private Notes"
    assert notes.is_published is False


@pytest.mark.asyncio
async def test_release_keeps_a_renamed_duplicate_spec_id(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    renamed = await probe.rename_page((await probe.duplicate_page(home.id)).id, "Notes")
    assert renamed.properties.get(SPEC_ID_PROPERTY) == spec_value
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="more than one page for this ProductSpec"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert renamed.properties.get(SPEC_ID_PROPERTY) == spec_value
    assert renamed.is_published is False
    stored = json.loads(path.read_text(encoding="ascii"))
    assert "variants" not in stored["provider_object_references"]


@pytest.mark.asyncio
async def test_finish_does_not_record_a_page_that_stays_indexed(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    raw = path.read_bytes()

    async def _keep(page_id: str, enabled: bool) -> NotionPage:
        return probe.pages[page_id]

    probe.set_search_indexing = _keep  # type: ignore[method-assign]

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "step",
    [
        "duplicate_page",
        "drop_page_property",
        "rename_page",
        "set_icon",
        "set_cover",
        "add_callout_block",
        "add_text_block",
        "publish_page",
        "set_duplicate_as_template",
        "set_search_indexing",
        "get_public_url",
    ],
)
async def test_each_variant_step_crash_resumes_without_a_second_page(
    tmp_path: Path, step: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    started = len(probe.pages)
    raw = path.read_bytes()
    original = getattr(probe, step)
    failed = {"done": False}
    if step == "publish_page":
        error: Exception = ProviderFailure(OP_VARIANTS, "publish refused")
        expected: type[Exception] = ProductBuildError
    else:
        error = RuntimeError("step crashed")
        expected = RuntimeError

    async def _boom(*args: object, **kwargs: object) -> object:
        if not failed["done"]:
            failed["done"] = True
            raise error
        return await original(*args, **kwargs)

    setattr(probe, step, _boom)
    message = "publish refused" if step == "publish_page" else "step crashed"
    with pytest.raises(expected, match=message):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    if step == "publish_page":
        stored = json.loads(path.read_text(encoding="ascii"))
        job = stored["progress"]["repair_jobs"][-1]
        assert job["kind"] == "provider_response"
        assert job["response"] == "publish refused"
    else:
        assert path.read_bytes() == raw

    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert len(checkpoint.variants) == len(spec.colour_variants)
    _assert_finished(spec, probe, started)
    resumed = json.loads(path.read_text(encoding="ascii"))
    assert resumed["progress"]["repair_jobs"] == []


@pytest.mark.asyncio
async def test_drop_crash_then_tamper_writes_nothing_and_clean_resume_finishes(
    tmp_path: Path,
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    started = len(probe.pages)
    original = probe.drop_page_property
    failed = {"done": False}

    async def _boom(page_id: str, name: str) -> NotionPage:
        if not failed["done"]:
            failed["done"] = True
            raise RuntimeError("step crashed")
        return await original(page_id, name)

    probe.drop_page_property = _boom  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="step crashed"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    copy = next(page for page in probe.pages.values() if page.title.endswith(" (Copy)"))
    assert SPEC_ID_PROPERTY in copy.properties
    clean = path.read_bytes()

    _restamp(path, lambda document: _tamper_created(document, "hub"))
    raw = path.read_bytes()
    calls = _watch(probe)
    with pytest.raises(ProductBuildError, match="progress created ids do not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    assert calls == []
    assert path.read_bytes() == raw
    assert SPEC_ID_PROPERTY in copy.properties

    path.write_bytes(clean)
    probe.drop_page_property = original  # type: ignore[method-assign]
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert len(checkpoint.variants) == len(spec.colour_variants)
    _assert_finished(spec, probe, started)
    assert SPEC_ID_PROPERTY not in copy.properties


@pytest.mark.asyncio
async def test_drop_crash_then_child_database_refuses_with_zero_writes(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    original = probe.drop_page_property
    failed = {"done": False}

    async def _boom(page_id: str, name: str) -> NotionPage:
        if not failed["done"]:
            failed["done"] = True
            raise RuntimeError("step crashed")
        return await original(page_id, name)

    probe.drop_page_property = _boom  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="step crashed"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    copy = next(page for page in probe.pages.values() if page.title.endswith(" (Copy)"))
    assert copy.title == f"{_home(probe, spec).title} (Copy)"
    assert SPEC_ID_PROPERTY in copy.properties
    await probe.create_database("Private", parent_id=copy.id, parent_type="page_id")
    probe.drop_page_property = original  # type: ignore[method-assign]
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert SPEC_ID_PROPERTY in copy.properties
    assert copy.is_published is False
    assert copy.duplicate_as_template is False


@pytest.mark.asyncio
async def test_crash_after_write_checkpoint_resumes_without_a_second_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    original = notion_variants_module.write_checkpoint

    def _boom(
        path: Path,
        checkpoint: CheckpointView | None = None,
        references: Mapping[str, object] | None = None,
        *,
        preserved_payload: Mapping[str, object] | None = None,
        progress: Mapping[str, object] | None = None,
        retained_created_ids: Mapping[str, object] | None = None,
    ) -> None:
        original(
            path,
            checkpoint,
            references,
            preserved_payload=preserved_payload,
            progress=progress,
            retained_created_ids=retained_created_ids,
        )
        raise RuntimeError("checkpoint write crashed")

    monkeypatch.setattr(notion_variants_module, "write_checkpoint", _boom)
    with pytest.raises(RuntimeError, match="checkpoint write crashed"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    written = len(probe.pages)
    stored = json.loads(path.read_text(encoding="ascii"))
    assert "variants" in stored["provider_object_references"]

    monkeypatch.setattr(notion_variants_module, "write_checkpoint", original)
    raw = path.read_bytes()
    finds: list[str] = []
    original_find = cast(
        Callable[[FixtureNotionAdapter, NotionPage, str], NotionPage | None],
        notion_variants_module.__dict__["_find_titled"],
    )

    def _find(probe: FixtureNotionAdapter, source: NotionPage, title: str) -> NotionPage | None:
        finds.append(title)
        return original_find(probe, source, title)

    monkeypatch.setattr(notion_variants_module, "_find_titled", _find)
    calls = _watch(probe)
    checkpoint_writes = {"count": 0}
    real_write = notion_variants_module.write_checkpoint

    def _count_write(
        path: Path,
        checkpoint: CheckpointView | None = None,
        references: Mapping[str, object] | None = None,
        *,
        preserved_payload: Mapping[str, object] | None = None,
        progress: Mapping[str, object] | None = None,
        retained_created_ids: Mapping[str, object] | None = None,
    ) -> None:
        checkpoint_writes["count"] += 1
        real_write(
            path,
            checkpoint,
            references,
            preserved_payload=preserved_payload,
            progress=progress,
            retained_created_ids=retained_created_ids,
        )

    monkeypatch.setattr(notion_variants_module, "write_checkpoint", _count_write)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert finds == []
    assert calls == []
    assert checkpoint_writes["count"] == 0
    assert path.read_bytes() == raw
    assert len(probe.pages) == written
    assert len(checkpoint.variants) == len(spec.colour_variants)
    titles = [page.title for page in probe.pages.values()]
    for colour in spec.colour_variants:
        assert titles.count(f"{spec.title} / {colour}") == 1


@pytest.mark.asyncio
async def test_crash_inside_write_checkpoint_before_the_file_lands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    started = len(probe.pages)
    raw = path.read_bytes()
    original = notion_variants_module.write_checkpoint

    def _boom(
        path: Path,
        checkpoint: CheckpointView | None = None,
        references: Mapping[str, object] | None = None,
        *,
        preserved_payload: Mapping[str, object] | None = None,
        progress: Mapping[str, object] | None = None,
        retained_created_ids: Mapping[str, object] | None = None,
    ) -> None:
        raise RuntimeError("checkpoint write crashed")

    monkeypatch.setattr(notion_variants_module, "write_checkpoint", _boom)
    with pytest.raises(RuntimeError, match="checkpoint write crashed"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    assert path.read_bytes() == raw
    written = len(probe.pages)
    assert written == started + len(spec.colour_variants)

    monkeypatch.setattr(notion_variants_module, "write_checkpoint", original)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert len(probe.pages) == written
    assert len(checkpoint.variants) == len(spec.colour_variants)
    _assert_finished(spec, probe, started)


@pytest.mark.asyncio
async def test_secret_link_comes_from_get_public_url(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    seen: list[str] = []

    async def _spy(page_id: str) -> str:
        seen.append(page_id)
        return f"secret-link:{page_id}"

    probe.get_public_url = _spy  # type: ignore[method-assign]
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert [record.page_id for record in checkpoint.variants] == seen
    for record in checkpoint.variants:
        page = probe.pages[record.page_id]
        assert record.secret_link == f"secret-link:{page.id}"
        assert record.secret_link != page.public_url
    raw = path.read_bytes()

    second = await build_variants(
        spec, probe, path, recorded_at=datetime(2026, 10, 6, 3, tzinfo=UTC)
    )

    assert path.read_bytes() == raw
    assert second.variants == checkpoint.variants
    assert seen[len(checkpoint.variants) :] == [record.page_id for record in checkpoint.variants]


def _variant_rows(document: dict[str, object]) -> tuple[list[object], list[object]]:
    references = document["provider_object_references"]
    progress = document["progress"]
    assert type(references) is dict and type(progress) is dict
    created = progress["created_notion_ids"]
    assert type(created) is dict
    stored = references["variants"]
    fresh = created["variants"]
    assert type(stored) is list and type(fresh) is list
    return stored, fresh


@pytest.mark.asyncio
async def test_replay_rejects_a_dropped_colour(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    def _drop(document: dict[str, object]) -> None:
        stored, fresh = _variant_rows(document)
        del stored[0]
        del fresh[0]

    _restamp(path, _drop)
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(
        ProductBuildError, match="checkpoint variants do not match the ProductSpec"
    ) as caught:
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert type(caught.value) is ProductBuildError
    assert str(caught.value) == "checkpoint variants do not match the ProductSpec"
    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_replay_rejects_a_swapped_colour_token(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    def _swap(document: dict[str, object]) -> None:
        stored, fresh = _variant_rows(document)
        for rows in (stored, fresh):
            first = rows[0]
            second = rows[1]
            assert type(first) is dict and type(second) is dict
            first["token"], second["token"] = second["token"], first["token"]

    _restamp(path, _swap)
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="checkpoint variants do not match the ProductSpec"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_refused_rebuild_names_the_variant_pages(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    def _unrecoverable(document: dict[str, object]) -> None:
        progress = document["progress"]
        assert type(progress) is dict
        progress["recovery"] = "unrecoverable"

    _restamp(path, _unrecoverable)
    raw_progress = json.loads(path.read_text(encoding="ascii"))
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="rebuild refused"):
        await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=WHEN)

    assert calls == []
    after = json.loads(path.read_text(encoding="ascii"))
    before_progress = raw_progress["progress"]
    after_progress = after["progress"]
    assert type(before_progress) is dict and type(after_progress) is dict
    for key, value in before_progress.items():
        if key not in {"repair_jobs", "record_digest"}:
            assert after_progress[key] == value
    assert after_progress["record_digest"] != before_progress["record_digest"]
    jobs = after_progress["repair_jobs"]
    before_jobs = before_progress["repair_jobs"]
    assert type(jobs) is list and type(before_jobs) is list
    assert len(jobs) == len(before_jobs) + 1
    job = jobs[-1]
    assert type(job) is dict and job["kind"] == "rebuild_refused"
    response = job["response"]
    assert type(response) is str
    for record in checkpoint.variants:
        assert f"{spec.title} / {record.name}" in response


@pytest.mark.asyncio
async def test_catalogue_spec_and_live_probes_are_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    raw = path.read_bytes()

    class SubclassProbe(FixtureNotionAdapter):
        async def duplicate_page(self, page_id: str) -> NotionPage:
            raise AssertionError("duplicate_page must not run")

    with pytest.raises(ProductBuildError, match="validated ProductSpec"):
        await build_variants(create_fixture_product_spec(), probe, path, recorded_at=VARIANTS_AT)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_variants(spec, SubclassProbe(), path, recorded_at=VARIANTS_AT)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_variants(spec, APINotionAdapter(), path, recorded_at=VARIANTS_AT)
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_variant_build_does_not_open_a_socket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tripwire: connect, connect_ex, and create_connection raise. Not a sandbox."""

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("socket connect is refused")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    assert len(checkpoint.variants) == len(spec.colour_variants)
    source = MODULE_PATH.read_text(encoding="utf-8")
    for token in (
        "notion_client",
        "httpx",
        "urllib",
        "socket",
        "requests",
        "APINotionAdapter",
        "BrowserNotionAdapter",
        "CombinedNotionAdapter",
        "playwright",
        "https://",
        "http://",
        "client_name",
        "etsy",
        "Etsy",
        "ETSY",
    ):
        assert token.casefold() not in source.casefold()


def test_session_seven_stays_incomplete_after_the_tip_sync() -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    assert state["current_session"] == 7
    assert state["session_status"] == "incomplete"
    assert state["completed_sessions"] == [0, 1, 2, 3, 4, 5, 6]
    assert state["next_session"] == 7
    assert state["next_prompt"] == "10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md"
    assert state["head_sha"] == HEAD_SHA
    assert state["evidence_closure_commit_sha"] == CLOSURE_SHA
    assert state["head_sha"] != state["evidence_closure_commit_sha"]
    assert state["last_verified_commit"] == BOOTSTRAP_SHA
    assert state["commissioned_agents"] == []
    evidence = state["required_completion_evidence"]
    assert evidence.keys() == SESSION_EVIDENCE_KEYS[7]
    assert all(value is False for value in evidence.values())
    assert evidence["variant_builder_implemented"] is False
    assert state["state_revision"] == 56
    assert "SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE" not in STATE_PATH.read_text(encoding="utf-8")
