"""Fixture-only product variants. Not a seventh build phase."""

from __future__ import annotations

import json
import socket
import traceback
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from money_machine.agents.implementations import notion_aesthetics as notion_aesthetics_module
from money_machine.agents.implementations import notion_dashboard as notion_dashboard_module
from money_machine.agents.implementations import notion_hubs as notion_hubs_module
from money_machine.agents.implementations import (
    notion_notifications as notion_notifications_module,
)
from money_machine.agents.implementations import notion_variants as notion_variants_module
from money_machine.agents.implementations.notion_aesthetics import (
    AESTHETIC_ICON,
    accent_content,
    build_aesthetics_and_content_completion,
    hub_cover,
    hub_icon,
    require_aesthetics_created_ids,
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
from money_machine.agents.implementations.notion_variants import (
    PHASE_QA,
    build_variants,
    load_variant_checkpoint,
    vocabulary_content,
)
from money_machine.control.state import SESSION_EVIDENCE_KEYS
from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.product_spec import ColourToken, Hub, ProductSpec
from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.domain import (
    NotionCalloutBlock,
    NotionDatabase,
    NotionPage,
    NotionTextBlock,
)
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
HEAD_SHA = "98fc06d2d37b206075b6bc91cf1dc964d2f0258f"
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
    "add_filter",
    "add_property",
    "add_sort",
    "add_text_block",
    "create_board_view",
    "create_calendar_view",
    "create_database",
    "create_formula",
    "create_linked_view",
    "create_page",
    "create_relation",
    "create_rollup",
    "create_table_view",
    "drop_page_property",
    "duplicate_page",
    "move_page",
    "publish_page",
    "rename_page",
    "set_cover",
    "set_duplicate_as_template",
    "set_icon",
    "set_search_indexing",
    "set_view_title_visibility",
    "unpublish_page",
)


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _fixture_bytes(probe: FixtureNotionAdapter) -> bytes:
    payload = {
        "blocks": {key: asdict(value) for key, value in probe.blocks.items()},
        "databases": {key: asdict(value) for key, value in probe.databases.items()},
        "linked_views": {key: asdict(value) for key, value in probe.linked_views.items()},
        "pages": {key: asdict(value) for key, value in probe.pages.items()},
        "views": {key: asdict(value) for key, value in probe.views.items()},
    }
    return json.dumps(payload, sort_keys=True, default=_json_default).encode("ascii")


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


def planner_spec(
    *,
    tier: str = "mass",
    identity: str = "Weekly Planner",
    title: str = "Home Dashboard Planner",
    hub_name: str = "Hub",
) -> ProductSpec:
    """ProductSpec for a later-phase test. Same builder the variants file uses."""
    return _spec(tier=tier, identity=identity, title=title, hub_name=hub_name)


async def prepare_aesthetics(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    """Build through aesthetics so a later phase can resume the checkpoint."""
    await _prepare(spec, probe, path)


def watch_adapter_writes(probe: FixtureNotionAdapter) -> list[str]:
    """Record adapter write-method names. Reads such as get_public_url are not included."""
    return _watch(probe)


def restamp_checkpoint(path: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    """Mutate a checkpoint and recompute its integrity digest."""
    _restamp(path, mutate)


def adapter_snapshot(probe: FixtureNotionAdapter) -> bytes:
    """Stable bytes for the fixture objects a refusal must leave unchanged."""
    return _fixture_bytes(probe)


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
    if kind == "notification":
        notification = created["notification"]
        assert type(notification) is dict
        notification["database_id"] = "db_missing"
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
@pytest.mark.parametrize("kind", ["hub", "database", "accent", "notification"])
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


def _block_parent(
    probe: FixtureNotionAdapter, page: NotionPage, spec: ProductSpec, block_kind: str
) -> str:
    colour = spec.colour_variants[0]
    token = spec.palette_tokens[0]
    if block_kind == "accent":
        block = probe.blocks.get(
            next(
                (
                    item.id
                    for item in probe.blocks.values()
                    if type(item) is NotionCalloutBlock
                    and item.parent_id == page.id
                    and item.content == accent_content(token.name, token.hex)
                    and item.icon == AESTHETIC_ICON
                ),
                "",
            )
        )
        if type(block) is not NotionCalloutBlock:
            return ""
        return block.id
    if block_kind == "vocabulary":
        expected = vocabulary_content(spec, colour, token)
        block = next(
            (
                item
                for item in probe.blocks.values()
                if type(item) is NotionTextBlock
                and item.parent_id == page.id
                and item.content == expected
            ),
            None,
        )
        if type(block) is not NotionTextBlock:
            return ""
        return block.id
    accent_id = _block_parent(probe, page, spec, "accent")
    if accent_id == "":
        return ""
    nested_id = f"block-{uuid4().hex}"
    if block_kind == "text":
        probe.blocks[nested_id] = NotionTextBlock(
            id=nested_id,
            parent_id=accent_id,
            type="paragraph",
            content="nested note",
            created_at=WHEN,
        )
        return nested_id
    if block_kind == "callout":
        probe.blocks[nested_id] = NotionCalloutBlock(
            id=nested_id,
            parent_id=accent_id,
            type="callout",
            content="nested callout",
            icon="!",
            created_at=WHEN,
        )
        return nested_id
    if block_kind == "depth3":
        mid_id = f"block-mid-{uuid4().hex}"
        deep_id = f"block-deep-{uuid4().hex}"
        probe.blocks[mid_id] = NotionTextBlock(
            id=mid_id,
            parent_id=accent_id,
            type="paragraph",
            content="mid note",
            created_at=WHEN,
        )
        probe.blocks[deep_id] = NotionTextBlock(
            id=deep_id,
            parent_id=mid_id,
            type="paragraph",
            content="deep note",
            created_at=WHEN,
        )
        return deep_id
    raise AssertionError(block_kind)


async def _plant_block_child(
    probe: FixtureNotionAdapter,
    page: NotionPage,
    spec: ProductSpec,
    block_kind: str,
    child_kind: str,
) -> None:
    colour = spec.colour_variants[0]
    token = spec.palette_tokens[0]
    if block_kind == "accent" and _block_parent(probe, page, spec, "accent") == "":
        await probe.add_callout_block(
            page.id, accent_content(token.name, token.hex), icon=AESTHETIC_ICON
        )
    if block_kind == "vocabulary" and _block_parent(probe, page, spec, "vocabulary") == "":
        await probe.add_text_block(page.id, vocabulary_content(spec, colour, token))
    if (
        block_kind in {"text", "callout", "depth3"}
        and _block_parent(probe, page, spec, "accent") == ""
    ):
        await probe.add_callout_block(
            page.id, accent_content(token.name, token.hex), icon=AESTHETIC_ICON
        )
    parent_id = _block_parent(probe, page, spec, block_kind)
    assert parent_id != ""
    if child_kind == "database":
        await probe.create_database("Private", parent_id=parent_id, parent_type="block_id")
        return
    if child_kind == "page":
        await probe.create_page("Nested", parent_id=parent_id, parent_type="block_id")
        return
    raise AssertionError(child_kind)


def _assert_untouched(
    path: Path,
    probe: FixtureNotionAdapter,
    raw: bytes,
    before: object,
    fixture: bytes,
    calls: list[str],
) -> None:
    assert calls == []
    assert path.read_bytes() == raw
    assert _fixture_bytes(probe) == fixture
    stored = json.loads(path.read_text(encoding="ascii"))
    assert type(before) is dict and type(stored) is dict
    progress = stored["progress"]
    before_progress = before["progress"]
    assert type(progress) is dict and type(before_progress) is dict
    assert progress["repair_jobs"] == before_progress["repair_jobs"]


async def _plant_finished(
    probe: FixtureNotionAdapter,
    home: NotionPage,
    spec: ProductSpec,
    colour: str,
    token: ColourToken,
    *,
    publish: bool,
) -> NotionPage:
    page = await probe.duplicate_page(home.id)
    await probe.drop_page_property(page.id, SPEC_ID_PROPERTY)
    page = await probe.rename_page(page.id, f"{spec.title} / {colour}")
    await probe.set_icon(page.id, hub_icon(token))
    await probe.set_cover(page.id, hub_cover(token))
    await probe.add_callout_block(
        page.id, accent_content(token.name, token.hex), icon=AESTHETIC_ICON
    )
    await probe.add_text_block(page.id, vocabulary_content(spec, colour, token))
    if publish:
        await probe.publish_page(page.id)
        await probe.set_duplicate_as_template(page.id, True)
        await probe.set_search_indexing(page.id, False)
    return probe.pages[page.id]


@pytest.mark.asyncio
@pytest.mark.parametrize("block_kind", ["accent", "vocabulary", "text", "callout", "depth3"])
@pytest.mark.parametrize("child_kind", ["database", "page"])
@pytest.mark.parametrize("stage", ["empty", "stored", "copy"])
async def test_child_under_a_page_block_writes_nothing(
    tmp_path: Path, block_kind: str, child_kind: str, stage: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    if stage == "stored":
        checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
        page = probe.pages[checkpoint.variants[0].page_id]
    elif stage == "copy":
        page = await probe.duplicate_page(home.id)
        assert page.title == f"{home.title} (Copy)"
    elif stage == "empty":
        page = await probe.duplicate_page(home.id)
        page = await probe.rename_page(page.id, f"{spec.title} / {spec.colour_variants[0]}")
    else:
        raise AssertionError(stage)
    await _plant_block_child(probe, page, spec, block_kind, child_kind)
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("parent_kind", ["page", "accent", "text", "callout"])
@pytest.mark.parametrize("child_kind", ["database", "page"])
@pytest.mark.parametrize("leftover", ["copy", "green"])
async def test_finished_variant_child_refuses_before_release_drop(
    tmp_path: Path, parent_kind: str, child_kind: str, leftover: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    colour = spec.colour_variants[0]
    token = spec.palette_tokens[0]
    blue = await probe.duplicate_page(home.id)
    await probe.drop_page_property(blue.id, SPEC_ID_PROPERTY)
    blue = await probe.rename_page(blue.id, f"{spec.title} / {colour}")
    await probe.set_icon(blue.id, hub_icon(token))
    await probe.set_cover(blue.id, hub_cover(token))
    await probe.add_callout_block(
        blue.id, accent_content(token.name, token.hex), icon=AESTHETIC_ICON
    )
    await probe.add_text_block(blue.id, vocabulary_content(spec, colour, token))
    await probe.publish_page(blue.id)
    await probe.set_duplicate_as_template(blue.id, True)
    await probe.set_search_indexing(blue.id, False)
    finished = next(
        page for page in probe.pages.values() if page.title == f"{spec.title} / {colour}"
    )
    assert SPEC_ID_PROPERTY not in finished.properties
    green = await probe.duplicate_page(home.id)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    if leftover == "copy":
        assert green.title == f"{home.title} (Copy)"
    elif leftover == "green":
        green = await probe.rename_page(green.id, f"{spec.title} / Green")
    else:
        raise AssertionError(leftover)
    assert green.properties.get(SPEC_ID_PROPERTY) == spec_value
    if parent_kind == "page":
        if child_kind == "database":
            await probe.create_database("Private", parent_id=finished.id, parent_type="page_id")
        else:
            await probe.create_page("Nested", parent_id=finished.id, parent_type="page_id")
    else:
        await _plant_block_child(probe, finished, spec, parent_kind, child_kind)
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert _fixture_bytes(probe) == fixture
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["progress"]["repair_jobs"] == before["progress"]["repair_jobs"]
    assert green.properties.get(SPEC_ID_PROPERTY) == spec_value


@pytest.mark.asyncio
@pytest.mark.parametrize("parent_kind", ["page", "accent"])
@pytest.mark.parametrize("child_kind", ["database", "page"])
async def test_finished_purple_child_refuses_before_blue_copy_is_published(
    tmp_path: Path, parent_kind: str, child_kind: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    colour = spec.colour_variants[2]
    token = spec.palette_tokens[2]
    purple = await probe.duplicate_page(home.id)
    await probe.drop_page_property(purple.id, SPEC_ID_PROPERTY)
    purple = await probe.rename_page(purple.id, f"{spec.title} / {colour}")
    await probe.set_icon(purple.id, hub_icon(token))
    await probe.set_cover(purple.id, hub_cover(token))
    await probe.add_callout_block(
        purple.id, accent_content(token.name, token.hex), icon=AESTHETIC_ICON
    )
    await probe.add_text_block(purple.id, vocabulary_content(spec, colour, token))
    await probe.publish_page(purple.id)
    await probe.set_duplicate_as_template(purple.id, True)
    await probe.set_search_indexing(purple.id, False)
    finished = next(
        page for page in probe.pages.values() if page.title == f"{spec.title} / {colour}"
    )
    blue = await probe.duplicate_page(home.id)
    assert blue.title == f"{home.title} (Copy)"
    if parent_kind == "page":
        if child_kind == "database":
            await probe.create_database("Private", parent_id=finished.id, parent_type="page_id")
        else:
            await probe.create_page("Nested", parent_id=finished.id, parent_type="page_id")
    elif parent_kind == "accent":
        accent_id = next(
            block.id
            for block in probe.blocks.values()
            if type(block) is NotionCalloutBlock and block.parent_id == finished.id
        )
        if child_kind == "database":
            await probe.create_database("Private", parent_id=accent_id, parent_type="block_id")
        else:
            await probe.create_page("Nested", parent_id=accent_id, parent_type="block_id")
    else:
        raise AssertionError(parent_kind)
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert _fixture_bytes(probe) == fixture
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["progress"]["repair_jobs"] == before["progress"]["repair_jobs"]
    assert blue.is_published is False
    assert SPEC_ID_PROPERTY in blue.properties


def _hub_page_id(path: Path) -> str:
    document = json.loads(path.read_text(encoding="ascii"))
    references = document["provider_object_references"]
    assert type(references) is dict
    hubs = references["identity_hubs"]
    assert type(hubs) is list and type(hubs[0]) is dict
    page_id = hubs[0]["page_id"]
    assert type(page_id) is str
    return page_id


@pytest.mark.asyncio
@pytest.mark.parametrize("holder", ["renamed", "workspace", "hub"])
async def test_copy_plus_another_spec_holder_refuses_before_any_drop(
    tmp_path: Path, holder: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    assert type(spec_value) is str
    copy = await probe.duplicate_page(home.id)
    assert copy.title == f"{home.title} (Copy)"
    if holder == "renamed":
        extra = await probe.rename_page((await probe.duplicate_page(home.id)).id, "Notes")
    elif holder == "workspace":
        extra = await probe.create_page(
            "Archive", parent_id=home.parent_id, parent_type="workspace"
        )
        extra.properties[SPEC_ID_PROPERTY] = spec_value
    elif holder == "hub":
        extra = await probe.create_page(
            "Archive", parent_id=_hub_page_id(path), parent_type="page_id"
        )
        extra.properties[SPEC_ID_PROPERTY] = spec_value
    else:
        raise AssertionError(holder)
    assert extra.properties.get(SPEC_ID_PROPERTY) == spec_value
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)
    ignored_calls: list[tuple[str, ...]] = []
    original = notion_dashboard_module.find_spec_page

    def _wrapped(
        fixture_probe: FixtureNotionAdapter,
        spec_id: str,
        *,
        ignored_page_ids: tuple[str, ...] = (),
    ) -> NotionPage | None:
        ignored_calls.append(tuple(ignored_page_ids))
        return original(fixture_probe, spec_id, ignored_page_ids=ignored_page_ids)

    monkeypatch.setattr(notion_dashboard_module, "find_spec_page", _wrapped)

    with pytest.raises(ProductBuildError, match="more than one page for this ProductSpec"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert _fixture_bytes(probe) == fixture
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["progress"]["repair_jobs"] == before["progress"]["repair_jobs"]
    assert extra.id in ignored_calls[0]
    assert SPEC_ID_PROPERTY in copy.properties
    assert copy.is_published is False


@pytest.mark.asyncio
async def test_recorded_variant_id_stays_open_when_the_title_changes(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    recorded = probe.pages[checkpoint.variants[0].page_id]
    recorded.title = "Archived Blue"
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert recorded.title == "Archived Blue"


@pytest.mark.asyncio
async def test_source_spec_id_keeps_a_retitled_page_open_until_bind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    archive = await probe.create_page("Archive", parent_id=home.parent_id, parent_type="workspace")
    archive.properties[SPEC_ID_PROPERTY] = spec_value
    raw = path.read_bytes()
    calls = _watch(probe)
    ignored_calls: list[tuple[str, ...]] = []
    original = notion_dashboard_module.find_spec_page

    def _wrapped(
        fixture: FixtureNotionAdapter,
        spec_id: str,
        *,
        ignored_page_ids: tuple[str, ...] = (),
    ) -> NotionPage | None:
        ignored_calls.append(tuple(ignored_page_ids))
        return original(fixture, spec_id, ignored_page_ids=ignored_page_ids)

    monkeypatch.setattr(notion_dashboard_module, "find_spec_page", _wrapped)

    with pytest.raises(ProductBuildError, match="more than one page for this ProductSpec"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert archive.id in ignored_calls[0]
    assert archive.properties.get(SPEC_ID_PROPERTY) == spec_value
    assert archive.title == "Archive"
    assert archive.is_published is False


@pytest.mark.asyncio
async def test_saved_variant_is_read_by_recorded_page_id(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    record = checkpoint.variants[0]
    recorded = probe.pages[record.page_id]
    token = spec.palette_tokens[0]
    decoy = await probe.create_page(
        recorded.title,
        parent_id=recorded.parent_id,
        parent_type="workspace",
        icon=hub_icon(token),
        cover=hub_cover(token),
    )
    decoy.is_published = True
    decoy.public_url = record.secret_link
    decoy.duplicate_as_template = True
    decoy.search_indexing = False
    for block in probe.blocks.values():
        if block.parent_id == recorded.id:
            block.parent_id = decoy.id
    recorded.title = "Archived Blue"
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert recorded.title == "Archived Blue"
    assert decoy.id != record.page_id


def _rewrite_recorded_blue(document: dict[str, object], page_id: str) -> None:
    references = document["provider_object_references"]
    assert type(references) is dict
    variants = references["variants"]
    assert type(variants) is list and type(variants[0]) is dict
    variants[0]["page_id"] = page_id
    progress = document["progress"]
    assert type(progress) is dict
    created = progress["created_notion_ids"]
    assert type(created) is dict
    created_variants = created["variants"]
    assert type(created_variants) is list and type(created_variants[0]) is dict
    created_variants[0]["page_id"] = page_id


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["missing", "hub", "home", "decoy"])
async def test_replay_rejects_a_recorded_page_id_that_is_not_the_variant(
    tmp_path: Path, target: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    record = checkpoint.variants[0]
    recorded = probe.pages[record.page_id]
    token = spec.palette_tokens[0]
    decoy = await probe.create_page(
        f"{spec.title} / Blue",
        parent_id=recorded.parent_id,
        parent_type="workspace",
        icon=hub_icon(token),
        cover=hub_cover(token),
    )
    decoy.is_published = True
    decoy.public_url = record.secret_link
    decoy.duplicate_as_template = True
    decoy.search_indexing = False
    if target == "decoy":
        for block in probe.blocks.values():
            if block.parent_id == recorded.id:
                block.parent_id = decoy.id
        recorded.title = "Archived Blue"
    elif target == "missing":
        _restamp(path, lambda document: _rewrite_recorded_blue(document, "page-missing"))
    elif target == "hub":
        _restamp(path, lambda document: _rewrite_recorded_blue(document, _hub_page_id(path)))
    elif target == "home":
        _restamp(path, lambda document: _rewrite_recorded_blue(document, checkpoint.page_id))
    else:
        raise AssertionError(target)
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert _fixture_bytes(probe) == fixture
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["progress"]["repair_jobs"] == before["progress"]["repair_jobs"]
    assert decoy.id != record.page_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    [
        "text_block",
        "child_db",
        "wrong_product_id",
        "shell_block",
        "parent_type",
        "wrong_parent",
        "different_spec",
    ],
)
async def test_copy_without_spec_id_and_purple_leftover_refuses_before_any_drop(
    tmp_path: Path, field: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    copy = await probe.duplicate_page(home.id)
    await probe.drop_page_property(copy.id, SPEC_ID_PROPERTY)
    if field == "text_block":
        await probe.add_text_block(copy.id, "private note")
    elif field == "child_db":
        await probe.create_database("Private", parent_id=copy.id, parent_type="page_id")
    elif field == "wrong_product_id":
        copy.properties[PRODUCT_ID_PROPERTY] = "other-product"
    elif field == "shell_block":
        copy.properties[SHELL_BLOCK_PROPERTY] = "other-shell"
    elif field == "parent_type":
        copy.parent_type = "page_id"
    elif field == "wrong_parent":
        copy.parent_id = "other-parent"
    elif field == "different_spec":
        copy.properties[SPEC_ID_PROPERTY] = "other-spec"
    else:
        raise AssertionError(field)
    purple = await probe.duplicate_page(home.id)
    purple = await probe.rename_page(purple.id, f"{spec.title} / Purple")
    assert purple.properties.get(SPEC_ID_PROPERTY) == spec_value
    assert SPEC_ID_PROPERTY not in copy.properties or field == "different_spec"
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    _assert_untouched(path, probe, raw, before, fixture, calls)
    assert purple.properties.get(SPEC_ID_PROPERTY) == spec_value
    assert copy.is_published is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    ["wrong_product_id", "shell_block", "parent_type", "wrong_parent", "different_spec"],
)
async def test_finished_green_different_spec_wrong_parent_or_product_refuses(
    tmp_path: Path, field: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    green = await _plant_finished(probe, home, spec, "Green", spec.palette_tokens[1], publish=True)
    if field == "wrong_product_id":
        green.properties[PRODUCT_ID_PROPERTY] = "other-product"
    elif field == "shell_block":
        green.properties[SHELL_BLOCK_PROPERTY] = "other-shell"
    elif field == "parent_type":
        green.parent_type = "page_id"
    elif field == "wrong_parent":
        green.parent_id = "other-parent"
    elif field == "different_spec":
        green.properties[SPEC_ID_PROPERTY] = "other-spec"
    else:
        raise AssertionError(field)
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    _assert_untouched(path, probe, raw, before, fixture, calls)
    assert not any(page.title == f"{spec.title} / Blue" for page in probe.pages.values())
    assert green.is_published is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    [
        "text_block",
        "child_db",
        "product_id",
        "shell_block",
        "parent_type",
        "parent_id",
        "foreign_spec",
    ],
)
async def test_unpublished_blue_and_bad_green_copy_refuse_before_publish(
    tmp_path: Path, field: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    blue = await _plant_finished(probe, home, spec, "Blue", spec.palette_tokens[0], publish=False)
    copy = await probe.duplicate_page(home.id)
    await probe.drop_page_property(copy.id, SPEC_ID_PROPERTY)
    copy = await probe.rename_page(copy.id, f"{home.title} (Copy)")
    if field == "text_block":
        await probe.add_text_block(copy.id, "private note")
    elif field == "child_db":
        await probe.create_database("Private", parent_id=copy.id, parent_type="page_id")
    elif field == "product_id":
        copy.properties[PRODUCT_ID_PROPERTY] = "other-product"
    elif field == "shell_block":
        copy.properties[SHELL_BLOCK_PROPERTY] = "other-shell"
    elif field == "parent_type":
        copy.parent_type = "page_id"
    elif field == "parent_id":
        copy.parent_id = "other-parent"
    elif field == "foreign_spec":
        copy.properties[SPEC_ID_PROPERTY] = "other-spec"
    else:
        raise AssertionError(field)
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    _assert_untouched(path, probe, raw, before, fixture, calls)
    assert blue.is_published is False
    assert copy.is_published is False


@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ["duplicate_as_template", "search_indexing"])
async def test_home_original_flag_refuses_before_any_write(tmp_path: Path, flag: str) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    if flag == "duplicate_as_template":
        home.duplicate_as_template = True
    elif flag == "search_indexing":
        home.search_indexing = False
    else:
        raise AssertionError(flag)
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    _assert_untouched(path, probe, raw, before, fixture, calls)
    assert len([page for page in probe.pages.values() if page.is_published]) == 0


@pytest.mark.asyncio
async def test_non_string_spec_id_refuses_before_any_drop(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    green = await probe.duplicate_page(home.id)
    green = await probe.rename_page(green.id, f"{spec.title} / Green")
    green.properties[SPEC_ID_PROPERTY] = 7
    copy = await probe.duplicate_page(home.id)
    assert copy.properties.get(SPEC_ID_PROPERTY) == spec_value
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="must be a string"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    _assert_untouched(path, probe, raw, before, fixture, calls)
    assert green.properties.get(SPEC_ID_PROPERTY) == 7
    assert copy.properties.get(SPEC_ID_PROPERTY) == spec_value
    assert copy.is_published is False


@pytest.mark.asyncio
async def test_finished_green_text_block_is_refused_by_the_titled_child_check(
    tmp_path: Path,
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    green = await _plant_finished(probe, home, spec, "Green", spec.palette_tokens[1], publish=True)
    await probe.add_text_block(green.id, "private note")
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match") as caught:
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    frames = traceback.extract_tb(caught.tb)
    assert any(frame.name == "_refuse_titled_children" for frame in frames)
    _assert_untouched(path, probe, raw, before, fixture, calls)
    assert not any(page.title == f"{spec.title} / Blue" for page in probe.pages.values())


@pytest.mark.asyncio
async def test_bind_runs_after_release_and_before_ensure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    copy = await probe.duplicate_page(home.id)
    raw = path.read_bytes()
    before = json.loads(raw)
    pages = len(probe.pages)
    calls = _watch(probe)

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise ProductBuildError("bind refused")

    monkeypatch.setattr(notion_variants_module, "_bind_earlier_phases", _refuse)

    with pytest.raises(ProductBuildError, match="bind refused"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == ["drop_page_property"]
    assert path.read_bytes() == raw
    assert len(probe.pages) == pages
    assert copy.is_published is False
    assert SPEC_ID_PROPERTY not in copy.properties
    stored = json.loads(path.read_text(encoding="ascii"))
    assert type(before) is dict and type(stored) is dict
    progress = stored["progress"]
    before_progress = before["progress"]
    assert type(progress) is dict and type(before_progress) is dict
    assert progress["repair_jobs"] == before_progress["repair_jobs"]


@pytest.mark.asyncio
async def test_finished_green_child_refuses_before_blue_is_copied(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    green = await _plant_finished(probe, home, spec, "Green", spec.palette_tokens[1], publish=True)
    await probe.create_page("Nested", parent_id=green.id, parent_type="page_id")
    blue = await probe.duplicate_page(home.id)
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    _assert_untouched(path, probe, raw, before, fixture, calls)
    assert blue.is_published is False
    assert blue.title == f"{home.title} (Copy)"


@pytest.mark.asyncio
async def test_finished_green_child_four_blocks_deep_writes_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    green = await _plant_finished(probe, home, spec, "Green", spec.palette_tokens[1], publish=True)
    token = spec.palette_tokens[1]
    accent_id = next(
        block.id
        for block in probe.blocks.values()
        if type(block) is NotionCalloutBlock
        and block.parent_id == green.id
        and block.content == accent_content(token.name, token.hex)
    )
    parent_id = accent_id
    for name in ("mid", "deep", "lower"):
        block_id = f"block-{name}-{uuid4().hex}"
        probe.blocks[block_id] = NotionTextBlock(
            id=block_id,
            parent_id=parent_id,
            type="paragraph",
            content=f"{name} note",
            created_at=WHEN,
        )
        parent_id = block_id
    await probe.create_page("Nested", parent_id=parent_id, parent_type="block_id")
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    _assert_untouched(path, probe, raw, before, fixture, calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("holder", ["home_block", "hub_block", "nested_block", "copy_block"])
async def test_spec_holder_under_a_block_refuses_before_any_drop(
    tmp_path: Path, holder: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    assert type(spec_value) is str
    if holder == "home_block":
        parent_id = next(block.id for block in probe.blocks.values() if block.parent_id == home.id)
    elif holder == "hub_block":
        parent_id = next(
            block.id for block in probe.blocks.values() if block.parent_id == _hub_page_id(path)
        )
    elif holder == "copy_block":
        copy = await probe.duplicate_page(home.id)
        await probe.drop_page_property(copy.id, SPEC_ID_PROPERTY)
        parent = await probe.add_text_block(copy.id, "holder parent")
        parent_id = parent.id
    elif holder == "nested_block":
        copy = await probe.duplicate_page(home.id)
        await probe.drop_page_property(copy.id, SPEC_ID_PROPERTY)
        outer = await probe.add_text_block(copy.id, "outer")
        inner_id = f"block-inner-{uuid4().hex}"
        probe.blocks[inner_id] = NotionTextBlock(
            id=inner_id,
            parent_id=outer.id,
            type="paragraph",
            content="inner",
            created_at=WHEN,
        )
        parent_id = inner_id
    else:
        raise AssertionError(holder)
    extra = await probe.create_page("Archive", parent_id=parent_id, parent_type="block_id")
    extra.properties[SPEC_ID_PROPERTY] = spec_value
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="more than one page for this ProductSpec"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    _assert_untouched(path, probe, raw, before, fixture, calls)
    assert extra.properties.get(SPEC_ID_PROPERTY) == spec_value
    assert extra.is_published is False


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["cleared", "empty_reader"])
async def test_finished_green_missing_secret_link_refuses_before_any_write(
    tmp_path: Path, kind: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    green = await _plant_finished(probe, home, spec, "Green", spec.palette_tokens[1], publish=True)
    if kind == "cleared":
        green.public_url = None
    elif kind == "empty_reader":

        async def _empty(_page_id: str) -> str:
            return ""

        probe.get_public_url = _empty  # type: ignore[method-assign]
    else:
        raise AssertionError(kind)
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant secret link is missing"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    _assert_untouched(path, probe, raw, before, fixture, calls)
    assert not any(page.title == f"{spec.title} / Blue" for page in probe.pages.values())
    assert green.is_published is True


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["accent", "vocabulary"])
async def test_copy_with_duplicate_blocks_refuses_before_any_drop(
    tmp_path: Path, kind: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    copy = await probe.duplicate_page(home.id)
    colour = spec.colour_variants[0]
    token = spec.palette_tokens[0]
    if kind == "accent":
        content = accent_content(token.name, token.hex)
        await probe.add_callout_block(copy.id, content, icon=AESTHETIC_ICON)
        await probe.add_callout_block(copy.id, content, icon=AESTHETIC_ICON)
    elif kind == "vocabulary":
        content = vocabulary_content(spec, colour, token)
        await probe.add_text_block(copy.id, content)
        await probe.add_text_block(copy.id, content)
    else:
        raise AssertionError(kind)
    assert copy.properties.get(SPEC_ID_PROPERTY) == spec_value
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match") as caught:
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    frame = "_matching_accent" if kind == "accent" else "_matching_vocabulary"
    frames = traceback.extract_tb(caught.tb)
    assert any(item.name == frame for item in frames)
    _assert_untouched(path, probe, raw, before, fixture, calls)
    assert copy.properties.get(SPEC_ID_PROPERTY) == spec_value
    assert copy.is_published is False


@pytest.mark.asyncio
@pytest.mark.parametrize("child_kind", ["page", "database"])
async def test_spec_less_copy_with_nested_child_refuses_before_any_write(
    tmp_path: Path, child_kind: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    copy = await probe.duplicate_page(home.id)
    await probe.drop_page_property(copy.id, SPEC_ID_PROPERTY)
    if child_kind == "page":
        await probe.create_page("Nested", parent_id=copy.id, parent_type="page_id")
    elif child_kind == "database":
        await probe.create_database("Private", parent_id=copy.id, parent_type="page_id")
    else:
        raise AssertionError(child_kind)
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match") as caught:
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    frames = traceback.extract_tb(caught.tb)
    assert any(item.name == "_plan_variants" for item in frames)
    assert any(item.name == "_require_adoptable" for item in frames)
    assert not any(item.name == "_refuse_unadoptable_release" for item in frames)
    _assert_untouched(path, probe, raw, before, fixture, calls)
    assert SPEC_ID_PROPERTY not in copy.properties
    assert not any(page.title == f"{spec.title} / Blue" for page in probe.pages.values())
    assert copy.title == f"{home.title} (Copy)"
    assert copy.is_published is False


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["shell_block", "parent_id", "child_db"])
async def test_unused_copy_holding_the_spec_id_refuses_before_any_drop(
    tmp_path: Path, fault: str
) -> None:
    """All three colours are finished. The unused (Copy) still holds the spec id."""
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    for colour, token in zip(spec.colour_variants, spec.palette_tokens, strict=True):
        await _plant_finished(probe, home, spec, colour, token, publish=True)
    copy = await probe.duplicate_page(home.id)
    assert copy.properties.get(SPEC_ID_PROPERTY) == spec_value
    if fault == "shell_block":
        copy.properties[SHELL_BLOCK_PROPERTY] = "broken-shell"
    elif fault == "parent_id":
        copy.parent_id = "wrong-parent"
    elif fault == "child_db":
        await probe.create_database("Private", parent_id=copy.id, parent_type="page_id")
    else:
        raise AssertionError(fault)
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    _assert_untouched(path, probe, raw, before, fixture, calls)
    assert copy.properties.get(SPEC_ID_PROPERTY) == spec_value
    assert copy.is_published is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flag",
    ["is_published", "duplicate_as_template", "search_indexing"],
)
async def test_lying_duplicate_source_flag_refuses_at_end_of_ensure(
    tmp_path: Path, flag: str
) -> None:
    """duplicate_page mutates the source. The end-of-ensure check refuses it."""
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    raw = path.read_bytes()
    real = probe.duplicate_page

    async def _lie(page_id: str) -> NotionPage:
        page = await real(page_id)
        if flag == "is_published":
            home.is_published = True
        elif flag == "duplicate_as_template":
            home.duplicate_as_template = True
        elif flag == "search_indexing":
            home.search_indexing = False
        else:
            raise AssertionError(flag)
        return page

    probe.duplicate_page = _lie  # type: ignore[method-assign]

    with pytest.raises(ProductBuildError, match="variant page does not match") as caught:
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    frames = traceback.extract_tb(caught.tb)
    assert any(item.name == "_ensure_planned" for item in frames)
    assert any(item.name == "_require_original" for item in frames)
    assert not any(item.name == "_plan_variants" for item in frames)
    assert path.read_bytes() == raw
    stored = json.loads(path.read_text(encoding="ascii"))
    assert "variants" not in stored["provider_object_references"]
    if flag == "is_published":
        assert home.is_published is True
    elif flag == "duplicate_as_template":
        assert home.duplicate_as_template is True
    else:
        assert home.search_indexing is False


@pytest.mark.asyncio
async def test_plan_refuses_a_missing_adoption_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A planned id that is not in the probe is a ProductBuildError, not KeyError."""
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)

    def _missing(*_args: object, **_kwargs: object) -> tuple[tuple[str, str], ...]:
        return (("Blue", "missing-page"), ("Green", ""), ("Purple", ""))

    monkeypatch.setattr(notion_variants_module, "_plan_adoptions", _missing)
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="planned variant page is missing"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_lying_duplicate_parent_stops_after_duplicate_page(tmp_path: Path) -> None:
    """A duplicate that claims parent_type page_id is refused before publish."""
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    raw = path.read_bytes()
    real = probe.duplicate_page

    async def _lie(page_id: str) -> NotionPage:
        page = await real(page_id)
        page.parent_type = "page_id"
        return page

    probe.duplicate_page = _lie  # type: ignore[method-assign]
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == ["duplicate_page"]
    assert path.read_bytes() == raw
    copied = [page for page in probe.pages.values() if page.title.endswith(" (Copy)")]
    assert len(copied) == 1
    assert copied[0].parent_type == "page_id"
    assert copied[0].is_published is False
    stored = json.loads(path.read_text(encoding="ascii"))
    assert "variants" not in stored["provider_object_references"]


@pytest.mark.asyncio
async def test_plan_secret_link_provider_failure_records_a_repair_job(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    green = await _plant_finished(probe, home, spec, "Green", spec.palette_tokens[1], publish=True)
    before = json.loads(path.read_text(encoding="ascii"))

    async def _boom(_page_id: str) -> str:
        raise ProviderFailure(OP_VARIANTS, "link refused")

    probe.get_public_url = _boom  # type: ignore[method-assign]
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="link refused"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert green.is_published is True
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
    assert job["response"] == "link refused"
    assert "variants" not in stored["provider_object_references"]


@pytest.mark.asyncio
async def test_empty_secret_link_after_publish_records_a_repair_job(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    before = json.loads(path.read_text(encoding="ascii"))

    async def _empty(_page_id: str) -> str:
        return ""

    probe.get_public_url = _empty  # type: ignore[method-assign]

    with pytest.raises(ProductBuildError, match="variant secret link is missing"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

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
    assert job["response"] == "variant secret link is missing"
    assert "variants" not in stored["provider_object_references"]
    blue = f"{spec.title} / Blue"
    published = [page for page in probe.pages.values() if page.title == blue and page.is_published]
    assert len(published) == 1


@pytest.mark.asyncio
async def test_copy_and_green_holding_the_spec_id_are_both_adopted(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    copy = await probe.duplicate_page(home.id)
    green = await probe.duplicate_page(home.id)
    green = await probe.rename_page(green.id, f"{spec.title} / Green")
    assert copy.properties.get(SPEC_ID_PROPERTY) == spec_value
    assert green.properties.get(SPEC_ID_PROPERTY) == spec_value
    started = len(probe.pages)

    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    by_name = {record.name: record.page_id for record in checkpoint.variants}
    assert by_name["Blue"] == copy.id
    assert by_name["Green"] == green.id
    assert by_name["Purple"] not in {copy.id, green.id}
    assert len(probe.pages) == started + 1
    assert probe.pages[copy.id].title == f"{spec.title} / Blue"
    assert probe.pages[green.id].title == f"{spec.title} / Green"
    assert SPEC_ID_PROPERTY not in probe.pages[copy.id].properties
    assert SPEC_ID_PROPERTY not in probe.pages[green.id].properties
    assert probe.pages[copy.id].is_published is True
    assert probe.pages[green.id].is_published is True


@pytest.mark.asyncio
@pytest.mark.parametrize("parent", ["self", "own_block"])
async def test_recorded_page_may_use_its_own_id_or_block_as_parent(
    tmp_path: Path, parent: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    record = checkpoint.variants[0]
    page = probe.pages[record.page_id]
    if parent == "self":
        page.parent_id = page.id
    elif parent == "own_block":
        page.parent_id = record.accent_block_id
    else:
        raise AssertionError(parent)
    raw = path.read_bytes()
    calls = _watch(probe)

    again = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert again.variants[0].page_id == record.page_id
    assert page.parent_type == "workspace"


@pytest.mark.asyncio
async def test_ensure_refuses_a_missing_page_id_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)

    class _MissingPlan:
        drop_ids: tuple[str, ...] = ()
        adoptions: tuple[tuple[str, str], ...] = (
            ("Blue", "missing-page"),
            ("Green", ""),
            ("Purple", ""),
        )

    async def _plan(*_args: object, **_kwargs: object) -> _MissingPlan:
        return _MissingPlan()

    monkeypatch.setattr(notion_variants_module, "_plan_variants", _plan)
    raw = path.read_bytes()
    before = json.loads(raw)
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    _assert_untouched(path, probe, raw, before, fixture, calls)


@pytest.mark.asyncio
async def test_home_retitled_as_blue_is_not_adopted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    blue_title = f"{spec.title} / Blue"
    home.title = blue_title

    def _show_original(fn: Callable[..., object]) -> Callable[..., object]:
        def wrapped(*args: object, **kwargs: object) -> object:
            home.title = spec.title
            try:
                return fn(*args, **kwargs)
            finally:
                home.title = blue_title

        return wrapped

    for module in (notion_aesthetics_module, notion_notifications_module, notion_hubs_module):
        monkeypatch.setattr(module, "require_home_page", _show_original(module.require_home_page))
    started = len(probe.pages)

    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert home.title == blue_title
    assert home.is_published is False
    assert checkpoint.variants[0].page_id != home.id
    assert len(probe.pages) == started + len(spec.colour_variants)
    assert probe.pages[checkpoint.variants[0].page_id].title == blue_title


@pytest.mark.asyncio
async def test_stripped_source_spec_skips_uniqueness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    spec_value = home.properties[SPEC_ID_PROPERTY]
    assert type(spec_value) is str
    del home.properties[SPEC_ID_PROPERTY]

    def _hold_spec(fn: Callable[..., object]) -> Callable[..., object]:
        def wrapped(*args: object, **kwargs: object) -> object:
            home.properties[SPEC_ID_PROPERTY] = spec_value
            try:
                return fn(*args, **kwargs)
            finally:
                home.properties.pop(SPEC_ID_PROPERTY, None)

        return wrapped

    for module in (notion_aesthetics_module, notion_notifications_module, notion_hubs_module):
        monkeypatch.setattr(module, "require_home_page", _hold_spec(module.require_home_page))

    real_find = notion_variants_module.find_spec_page

    def _find(
        probe: FixtureNotionAdapter,
        spec_id: str,
        *,
        ignored_page_ids: tuple[str, ...] = (),
    ) -> NotionPage | None:
        if spec_id != spec_value:
            return real_find(probe, spec_id, ignored_page_ids=ignored_page_ids)
        home.properties[SPEC_ID_PROPERTY] = spec_value
        try:
            return real_find(probe, spec_id, ignored_page_ids=ignored_page_ids)
        finally:
            home.properties.pop(SPEC_ID_PROPERTY, None)

    monkeypatch.setattr(notion_variants_module, "find_spec_page", _find)
    started = len(probe.pages)

    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert SPEC_ID_PROPERTY not in home.properties
    assert len(checkpoint.variants) == len(spec.colour_variants)
    assert len(probe.pages) == started + len(spec.colour_variants)


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
@pytest.mark.parametrize("title_kind", ["copy", "blue"])
async def test_replay_refuses_a_hub_child_with_a_variant_title(
    tmp_path: Path, title_kind: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    hub_id = checkpoint.identity_hubs[0].page_id
    home = _home(probe, spec)
    title = f"{home.title} (Copy)" if title_kind == "copy" else f"{spec.title} / Blue"
    await probe.create_page(title, parent_id=hub_id, parent_type="page_id")
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="hub page is unexpected"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("title_kind", ["blue", "purple", "copy"])
async def test_replay_pins_extra_workspace_variant_titles_as_a_known_limit(
    tmp_path: Path, title_kind: str
) -> None:
    """Known limit: an extra workspace title passes replay with zero writes.

    An extra workspace `/ Blue` also passes when a child database or page sits
    under it. A forgery with the recorded title and a different id is rejected,
    because replay reads `probe.pages.get(record.page_id)`.
    """
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    home = _home(probe, spec)
    if title_kind == "copy":
        title = f"{home.title} (Copy)"
    elif title_kind == "blue":
        title = f"{spec.title} / Blue"
    elif title_kind == "purple":
        title = f"{spec.title} / Purple"
    else:
        raise AssertionError(title_kind)
    await probe.create_page(title, parent_id=home.parent_id, parent_type="workspace")
    raw = path.read_bytes()
    calls = _watch(probe)

    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("child_kind", ["database", "page"])
async def test_replay_pins_extra_workspace_blue_with_a_nested_child(
    tmp_path: Path, child_kind: str
) -> None:
    """Known limit: extra workspace `/ Blue` passes even with a child database or page."""
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    home = _home(probe, spec)
    extra = await probe.create_page(
        f"{spec.title} / Blue", parent_id=home.parent_id, parent_type="workspace"
    )
    if child_kind == "database":
        await probe.create_database("Private", parent_id=extra.id, parent_type="page_id")
    elif child_kind == "page":
        await probe.create_page("Nested", parent_id=extra.id, parent_type="page_id")
    else:
        raise AssertionError(child_kind)
    raw = path.read_bytes()
    calls = _watch(probe)

    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert extra.is_published is False


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
    if step in {"add_callout_block", "add_text_block"}:
        assert all(page.is_published is False for page in probe.pages.values())
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
    if step == "publish_page":
        resumed_jobs = resumed["progress"]["repair_jobs"]
        assert type(resumed_jobs) is list and resumed_jobs
        assert resumed_jobs[-1]["kind"] == "provider_response"
        assert resumed_jobs[-1]["response"] == "publish refused"
    else:
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
    calls = _watch(probe)
    checkpoint_writes = {"count": 0}

    def _boom(
        path: Path,
        checkpoint: CheckpointView | None = None,
        references: Mapping[str, object] | None = None,
        *,
        preserved_payload: Mapping[str, object] | None = None,
        progress: Mapping[str, object] | None = None,
        retained_created_ids: Mapping[str, object] | None = None,
    ) -> None:
        checkpoint_writes["count"] += 1
        raise RuntimeError("checkpoint write crashed")

    monkeypatch.setattr(notion_variants_module, "write_checkpoint", _boom)
    with pytest.raises(RuntimeError, match="checkpoint write crashed"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    assert checkpoint_writes["count"] == 1
    assert calls.count("duplicate_page") == len(spec.colour_variants)
    assert path.read_bytes() == raw
    written = len(probe.pages)
    assert written == started + len(spec.colour_variants)
    resume_calls = len(calls)

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
        original(
            path,
            checkpoint,
            references,
            preserved_payload=preserved_payload,
            progress=progress,
            retained_created_ids=retained_created_ids,
        )

    monkeypatch.setattr(notion_variants_module, "write_checkpoint", _count_write)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert checkpoint_writes["count"] == 2
    assert calls.count("duplicate_page") == len(spec.colour_variants)
    assert len(calls) == resume_calls
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


def _plant_database(probe: FixtureNotionAdapter, parent_id: str) -> None:
    probe.databases["db_nested"] = NotionDatabase(
        id="db_nested",
        title="Nested",
        parent_id=parent_id,
        parent_type="block_id",
    )


def _structure_block_id(probe: FixtureNotionAdapter, spec: ProductSpec, kind: str) -> str:
    home = _home(probe, spec)
    if kind == "home":
        return next(block.id for block in probe.blocks.values() if block.parent_id == home.id)
    hub = next(page for page in probe.pages.values() if page.parent_id == home.id)
    return next(block.id for block in probe.blocks.values() if block.parent_id == hub.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["home", "hub"])
async def test_database_under_a_structure_block_refuses_before_any_write(
    tmp_path: Path, kind: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    _plant_database(probe, _structure_block_id(probe, spec, kind))
    raw = path.read_bytes()
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert _fixture_bytes(probe) == fixture


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["home", "hub"])
async def test_saved_database_under_a_structure_block_refuses(tmp_path: Path, kind: str) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    _plant_database(probe, _structure_block_id(probe, spec, kind))
    raw = path.read_bytes()
    fixture = _fixture_bytes(probe)
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert _fixture_bytes(probe) == fixture


@pytest.mark.asyncio
async def test_database_subclass_under_a_hub_block_is_refused(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)

    class _NestedDatabase(NotionDatabase):
        pass

    parent_id = _structure_block_id(probe, spec, "hub")
    probe.databases["db_sub"] = _NestedDatabase(
        id="db_sub",
        title="Nested",
        parent_id=parent_id,
        parent_type="block_id",
    )
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_database_subclass_under_a_copy_page_is_refused(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    copy = await probe.duplicate_page(home.id)

    class _NestedDatabase(NotionDatabase):
        pass

    probe.databases["db_sub"] = _NestedDatabase(
        id="db_sub",
        title="Nested",
        parent_id=copy.id,
        parent_type="page_id",
    )
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_replay_rejects_a_changed_secret_link(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    page = next(item for item in probe.pages.values() if item.title.endswith("/ Blue"))
    page.public_url = "changed"
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_replay_rejects_a_moved_accent_block_id(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    record = checkpoint.variants[0]
    block = probe.blocks.pop(record.accent_block_id)
    block.id = "block_moved"
    probe.blocks[block.id] = block
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("flag", "value"),
    [("duplicate_as_template", True), ("search_indexing", False)],
)
async def test_saved_home_original_flag_refuses(tmp_path: Path, flag: str, value: bool) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    setattr(_home(probe, spec), flag, value)
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_navigation_callout_fails_the_created_hub_pair(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    stored, created = load_variant_checkpoint(path)
    hub = stored.identity_hubs[0]
    original = probe.blocks[hub.navigation_block_id]
    probe.blocks[hub.navigation_block_id] = NotionCalloutBlock(
        id=original.id,
        parent_id="not-the-hub",
        type="callout",
        content="moved",
        created_at=original.created_at,
    )

    with pytest.raises(ProductBuildError, match="progress created ids do not match the checkpoint"):
        require_aesthetics_created_ids(probe, created, stored)


@pytest.mark.asyncio
async def test_duplicate_palette_token_names_refuse_before_any_write(tmp_path: Path) -> None:
    spec = _spec().model_copy(
        update={
            "palette_tokens": (
                ColourToken(name="Primary", hex="#111111"),
                ColourToken(name="Primary", hex="#111111"),
                ColourToken(name="Accent", hex="#E74C3C"),
            ),
        }
    )
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="checkpoint aesthetics accent is duplicated"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


def _copy_variant_field(document: dict[str, object], field: str) -> None:
    references = document["provider_object_references"]
    assert type(references) is dict
    variants = references["variants"]
    assert type(variants) is list
    first = variants[0]
    second = variants[1]
    assert type(first) is dict and type(second) is dict
    second[field] = first[field]


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["name", "page_id"])
async def test_replay_rejects_a_duplicated_variant_label(tmp_path: Path, field: str) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    _restamp(path, lambda document: _copy_variant_field(document, field))
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="checkpoint variant is duplicated"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_replay_rejects_an_extra_variant_child(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    page_id = checkpoint.variants[0].page_id
    probe.blocks["block_extra"] = NotionTextBlock(
        id="block_extra",
        parent_id=page_id,
        type="paragraph",
        content="extra",
    )
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_replay_rejects_a_home_without_the_spec_id(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    del _home(probe, spec).properties[SPEC_ID_PROPERTY]
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(
        ProductBuildError, match="checkpoint page is missing from the fixture probe"
    ):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_replay_rejects_a_home_that_is_not_workspace(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    _home(probe, spec).parent_type = "page_id"
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="checkpoint page is not the stored top-level page"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_two_colour_titles_refuse_before_any_write(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    title = f"{spec.title} / Blue"
    await probe.rename_page((await probe.duplicate_page(home.id)).id, title)
    await probe.rename_page((await probe.duplicate_page(home.id)).id, title)
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_two_copy_titles_refuse_before_any_write(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe, spec)
    await probe.duplicate_page(home.id)
    await probe.duplicate_page(home.id)
    raw = path.read_bytes()
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_reversed_dashboard_created_ids_survive_variants(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    document = json.loads(path.read_text(encoding="ascii"))
    progress = document["progress"]
    assert type(progress) is dict
    created = progress["created_notion_ids"]
    assert type(created) is dict
    dashboard = created["dashboard"]
    assert type(dashboard) is list and len(dashboard) >= 2
    reversed_rows = list(reversed(dashboard))

    def _reverse(body: dict[str, object]) -> None:
        fresh = body["progress"]
        assert type(fresh) is dict
        ids = fresh["created_notion_ids"]
        assert type(ids) is dict
        rows = ids["dashboard"]
        assert type(rows) is list
        ids["dashboard"] = list(reversed(rows))

    _restamp(path, _reverse)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)
    stored = json.loads(path.read_text(encoding="ascii"))
    after = stored["progress"]
    assert type(after) is dict
    ids = after["created_notion_ids"]
    assert type(ids) is dict
    assert ids["dashboard"] == reversed_rows


def test_aligned_pairs_refuse_a_duplicated_palette_name() -> None:
    """Same token name and a different hex is refused. Unique names are kept.

    Building from a duplicate spec never reaches this check: the aesthetics
    loader refuses the duplicated accent label first. This calls the check
    with that input directly.
    """
    spec = _spec()
    tokens = spec.palette_tokens
    mutated = spec.model_copy(
        update={
            "palette_tokens": (
                tokens[0],
                ColourToken(name=tokens[0].name, hex=tokens[1].hex),
                *tokens[2:],
            ),
        }
    )

    with pytest.raises(ProductBuildError, match="palette token name is duplicated"):
        notion_variants_module._aligned_pairs(mutated)  # pyright: ignore[reportPrivateUsage]

    pairs = notion_variants_module._aligned_pairs(spec)  # pyright: ignore[reportPrivateUsage]
    assert tuple(colour for colour, _token in pairs) == spec.colour_variants


@pytest.mark.asyncio
async def test_non_workspace_home_is_refused_by_the_source_check(tmp_path: Path) -> None:
    """A home whose parent is not workspace fails the source-page check."""
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    stored, _created = load_variant_checkpoint(path)
    page = notion_variants_module._source_page(probe, stored)  # pyright: ignore[reportPrivateUsage]
    assert page.id == stored.page_id
    probe.pages[stored.page_id].parent_type = "page_id"

    with pytest.raises(ProductBuildError, match="variants require the aesthetics checkpoint"):
        notion_variants_module._source_page(probe, stored)  # pyright: ignore[reportPrivateUsage]

    del probe.pages[stored.page_id]
    with pytest.raises(ProductBuildError, match="variants require the aesthetics checkpoint"):
        notion_variants_module._source_page(probe, stored)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_spec_page_must_be_the_stored_home(tmp_path: Path) -> None:
    """The page that carries the spec id has to be the stored home page."""
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    stored, _created = load_variant_checkpoint(path)
    notion_variants_module._require_one_spec_page(probe, spec, stored)  # pyright: ignore[reportPrivateUsage]
    forged = replace(stored, page_id="not-the-home")

    with pytest.raises(ProductBuildError, match="variant page does not match"):
        notion_variants_module._require_one_spec_page(probe, spec, forged)  # pyright: ignore[reportPrivateUsage]

    del _home(probe, spec).properties[SPEC_ID_PROPERTY]
    with pytest.raises(ProductBuildError, match="variant page does not match"):
        notion_variants_module._require_one_spec_page(probe, spec, stored)  # pyright: ignore[reportPrivateUsage]


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
    assert evidence["product_qa_implemented"] is False
    assert state["state_revision"] == 63
    assert "SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE" not in STATE_PATH.read_text(encoding="utf-8")
