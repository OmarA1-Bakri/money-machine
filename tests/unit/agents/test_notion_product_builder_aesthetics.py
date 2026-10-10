"""Fixture-only aesthetics and content completion phase of the Notion product build."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from money_machine.agents.implementations.notion_aesthetics import (
    AESTHETIC_ICON,
    accent_content,
    build_aesthetics_and_content_completion,
    sample_content,
)
from money_machine.agents.implementations.notion_dashboard import build_dashboard_and_navigation
from money_machine.agents.implementations.notion_hubs import build_identity_specific_hubs
from money_machine.agents.implementations.notion_notifications import build_notification_dashboard
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    BUILD_PHASES_COMPLETE,
    ProductBuildCheckpoint,
    ProductBuildError,
    build_top_level_page_and_design_shell,
)
from money_machine.agents.implementations.notion_progress import stamp_integrity_digest
from money_machine.agents.implementations.notion_shared_databases import build_shared_databases
from money_machine.control.s07_evidence import assert_session_seven_continuity
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
MODULE_PATH = ROOT / "src/money_machine/agents/implementations/notion_aesthetics.py"
WHEN = datetime(2026, 10, 3, 0, 30, tzinfo=UTC)
PHASE_TWO_AT = datetime(2026, 10, 5, 20, 0, tzinfo=UTC)
DASHBOARD_AT = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)
HUBS_AT = datetime(2026, 10, 5, 23, 45, tzinfo=UTC)
NOTIFICATION_AT = datetime(2026, 10, 6, 0, 30, tzinfo=UTC)
LATER = datetime(2026, 10, 6, 1, 30, tzinfo=UTC)


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
                source_reference="tests/unit/agents/test_notion_product_builder_aesthetics.py",
                observed_at=WHEN,
                safe_summary="Aesthetics fixture spec",
            ),
        ),
        created_at=WHEN,
    )


async def _prepare(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=WHEN)
    await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)
    await build_dashboard_and_navigation(spec, probe, path, recorded_at=DASHBOARD_AT)
    await build_identity_specific_hubs(spec, probe, path, recorded_at=HUBS_AT)
    await build_notification_dashboard(spec, probe, path, recorded_at=NOTIFICATION_AT)


async def _build(
    spec: ProductSpec,
    probe: FixtureNotionAdapter,
    path: Path,
    *,
    recorded_at: datetime = LATER,
) -> ProductBuildCheckpoint:
    return await build_aesthetics_and_content_completion(spec, probe, path, recorded_at=recorded_at)


def _home(probe: FixtureNotionAdapter) -> NotionPage:
    return next(page for page in probe.pages.values() if page.parent_type == "workspace")


def _resign(path: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    document = json.loads(path.read_text(encoding="ascii"))
    mutate(document)
    stamped = stamp_integrity_digest(document)
    path.write_text(
        json.dumps(stamped, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )


def _created(document: dict[str, object]) -> dict[str, object]:
    progress = document["progress"]
    assert type(progress) is dict
    created = progress["created_notion_ids"]
    assert type(created) is dict
    return created


@pytest.mark.asyncio
async def test_mass_tier_adds_palette_accents_and_sample_hub_text(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe)
    cover = home.cover
    icon = home.icon
    pages = len(probe.pages)

    checkpoint = await _build(spec, probe, path)

    assert checkpoint.checkpoint_names == BUILD_PHASES
    assert checkpoint.next_phase == BUILD_PHASES_COMPLETE
    assert checkpoint.next_phase == "build_phases_complete"
    assert checkpoint.recorded_at == LATER
    assert len(probe.pages) == pages == 12
    assert home.cover == cover
    assert home.icon == icon
    record = checkpoint.aesthetics
    assert record is not None
    assert tuple(name for name, _block_id in record.accents) == tuple(
        token.name for token in spec.palette_tokens
    )
    for token_name, block_id in record.accents:
        block = probe.blocks[block_id]
        token = next(item for item in spec.palette_tokens if item.name == token_name)
        assert type(block) is NotionCalloutBlock
        assert block.parent_id == home.id
        assert block.icon == AESTHETIC_ICON
        assert block.content == f"palette {token.name} {token.hex}"
    assert tuple(name for name, _block_id in record.samples) == tuple(hub.name for hub in spec.hubs)
    hubs = {hub.name: hub for hub in spec.hubs}
    for hub_name, block_id in record.samples:
        block = probe.blocks[block_id]
        assert type(block) is NotionTextBlock
        assert block.content == f"SAMPLE {spec.identity} / {hub_name}: {hubs[hub_name].description}"
        assert "client_name" not in block.content
        assert block.content == sample_content(spec, hub_name)
        assert block.content.startswith("SAMPLE ")
        assert hubs[hub_name].description in block.content
    for index, (page_id, mark_icon, mark_cover) in enumerate(record.marks):
        token = spec.palette_tokens[index % len(spec.palette_tokens)]
        page = probe.pages[page_id]
        assert page.icon == mark_icon == f"palette:{token.name}:{token.hex}"
        assert page.cover == mark_cover == f"fixture://palette/{token.name}/{token.hex}"


@pytest.mark.asyncio
async def test_business_tier_uses_the_same_palette_rules(tmp_path: Path) -> None:
    spec = _spec(tier="business", identity="Studio Ledger", title="Studio Home", hub_name="Desk")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    pages = len(probe.pages)

    checkpoint = await _build(spec, probe, path)

    assert pages == 9
    assert len(probe.pages) == 9
    assert checkpoint.next_phase == BUILD_PHASES_COMPLETE
    assert checkpoint.aesthetics is not None
    assert len(checkpoint.aesthetics.accents) == len(spec.palette_tokens)
    assert len(checkpoint.aesthetics.samples) == len(spec.hubs)


@pytest.mark.asyncio
async def test_replay_keeps_the_same_checkpoint_bytes_and_ids(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await _build(spec, probe, path)
    before = path.read_bytes()
    blocks = set(probe.blocks)
    pages = {page.id: (page.icon, page.cover) for page in probe.pages.values()}

    again = await _build(spec, probe, path, recorded_at=datetime(2026, 10, 6, 2, tzinfo=UTC))

    assert set(probe.blocks) == blocks
    assert {page.id: (page.icon, page.cover) for page in probe.pages.values()} == pages
    assert again == checkpoint
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_missing_checkpoint_creates_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "missing.json"

    with pytest.raises(ProductBuildError, match="notification"):
        await _build(spec, probe, path)

    assert path.exists() is False
    assert probe.pages == {}
    assert probe.blocks == {}


@pytest.mark.asyncio
async def test_hubs_checkpoint_creates_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=WHEN)
    await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)
    await build_dashboard_and_navigation(spec, probe, path, recorded_at=DASHBOARD_AT)
    await build_identity_specific_hubs(spec, probe, path, recorded_at=HUBS_AT)
    before = path.read_bytes()
    blocks = set(probe.blocks)

    with pytest.raises(ProductBuildError, match="notification"):
        await _build(spec, probe, path)

    assert path.read_bytes() == before
    assert set(probe.blocks) == blocks


@pytest.mark.asyncio
async def test_partial_accent_is_adopted(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe)
    token = spec.palette_tokens[0]
    existing = await probe.add_callout_block(
        home.id, accent_content(token.name, token.hex), icon=AESTHETIC_ICON
    )

    checkpoint = await _build(spec, probe, path)

    assert checkpoint.aesthetics is not None
    assert checkpoint.aesthetics.accents[0] == (token.name, existing.id)
    assert len(checkpoint.aesthetics.accents) == len(spec.palette_tokens)


@pytest.mark.asyncio
async def test_wrong_accent_icon_is_not_repaired(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe)
    token = spec.palette_tokens[0]
    await probe.add_callout_block(home.id, accent_content(token.name, token.hex), icon="✦")
    before = path.read_bytes()
    blocks = set(probe.blocks)

    with pytest.raises(ProductBuildError, match="does not match"):
        await _build(spec, probe, path)

    assert path.read_bytes() == before
    assert set(probe.blocks) == blocks


@pytest.mark.asyncio
async def test_unexpected_block_creates_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe)
    await probe.add_text_block(home.id, "not a palette accent")
    before = path.read_bytes()
    blocks = set(probe.blocks)

    with pytest.raises(ProductBuildError, match="unexpected"):
        await _build(spec, probe, path)

    assert path.read_bytes() == before
    assert set(probe.blocks) == blocks


@pytest.mark.asyncio
async def test_wrong_hub_mark_is_not_repaired(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    hub = next(page for page in probe.pages.values() if page.title == spec.hubs[0].name)
    await probe.set_icon(hub.id, "palette:nope:#000000")
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="does not match"):
        await _build(spec, probe, path)

    assert hub.icon == "palette:nope:#000000"
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_catalogue_spec_and_live_probes_are_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    before = path.read_bytes()

    class SubclassProbe(FixtureNotionAdapter):
        async def create_database(
            self,
            title: str,
            parent_id: str | None = None,
            parent_type: str = "workspace",
            icon: str | None = None,
            cover: str | None = None,
        ) -> NotionDatabase:
            raise AssertionError("create_database must not run")

    with pytest.raises(ProductBuildError, match="validated ProductSpec"):
        await build_aesthetics_and_content_completion(
            create_fixture_product_spec(), probe, path, recorded_at=LATER
        )
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_aesthetics_and_content_completion(
            spec, SubclassProbe(), path, recorded_at=LATER
        )
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_aesthetics_and_content_completion(
            spec, APINotionAdapter(), path, recorded_at=LATER
        )

    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_aesthetics_checkpoint_parser_rejects_bad_inputs(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    blocks = set(probe.blocks)
    original = path.read_text(encoding="ascii")
    path.write_text("{\n", encoding="utf-8")

    with pytest.raises(ProductBuildError, match="not JSON"):
        await _build(spec, probe, path)

    payload = json.loads(original)
    payload["provider_object_references"]["aesthetics"]["accents"] = []
    payload = stamp_integrity_digest(payload)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii"
    )

    with pytest.raises(ProductBuildError, match="incomplete"):
        await _build(spec, probe, path)

    assert set(probe.blocks) == blocks


@pytest.mark.asyncio
async def test_replay_rejects_a_tampered_top_level_page_id(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)

    def mutate(document: dict[str, object]) -> None:
        _created(document)["top_level_page_id"] = "page_missing"

    _resign(path, mutate)
    with pytest.raises(ProductBuildError, match="progress created ids do not match"):
        await _build(spec, probe, path)


@pytest.mark.asyncio
async def test_replay_rejects_a_tampered_database_id(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)

    def mutate(document: dict[str, object]) -> None:
        databases = _created(document)["databases"]
        assert type(databases) is list and databases
        assert type(databases[0]) is dict
        databases[0]["database_id"] = "db_missing"

    _resign(path, mutate)
    with pytest.raises(ProductBuildError, match="progress created ids do not match"):
        await _build(spec, probe, path)


@pytest.mark.asyncio
async def test_replay_rejects_a_tampered_hub_page_id(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)

    def mutate(document: dict[str, object]) -> None:
        hubs = _created(document)["hubs"]
        assert type(hubs) is list and hubs
        assert type(hubs[0]) is dict
        hubs[0]["page_id"] = "page_missing"

    _resign(path, mutate)
    with pytest.raises(ProductBuildError, match="progress created ids do not match"):
        await _build(spec, probe, path)


@pytest.mark.asyncio
async def test_replay_rejects_a_tampered_navigation_block_id(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)

    def mutate(document: dict[str, object]) -> None:
        hubs = _created(document)["hubs"]
        assert type(hubs) is list and hubs
        hub = hubs[0]
        assert type(hub) is dict
        sections = hub["sections"]
        assert type(sections) is list and sections
        section = sections[0]
        assert type(section) is dict
        hub["navigation_block_id"] = section["block_id"]

    _resign(path, mutate)
    with pytest.raises(ProductBuildError, match="progress created ids do not match"):
        await _build(spec, probe, path)


@pytest.mark.asyncio
async def test_replay_rejects_a_tampered_notification_database_id(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)

    def mutate(document: dict[str, object]) -> None:
        created = _created(document)
        databases = created["databases"]
        notice = created["notification"]
        assert type(databases) is list and databases
        assert type(databases[0]) is dict
        assert type(notice) is dict
        notice["database_id"] = databases[0]["database_id"]

    _resign(path, mutate)
    with pytest.raises(ProductBuildError, match="progress created ids do not match"):
        await _build(spec, probe, path)


@pytest.mark.asyncio
async def test_replay_rejects_a_tampered_accent_block_id(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)

    def mutate(document: dict[str, object]) -> None:
        created = _created(document)
        aesthetics = created["aesthetics"]
        assert type(aesthetics) is dict
        accents = aesthetics["accents"]
        assert type(accents) is list and accents
        assert type(accents[0]) is dict
        accents[0]["block_id"] = created["design_shell_block_id"]

    _resign(path, mutate)
    with pytest.raises(ProductBuildError, match="progress created ids do not match"):
        await _build(spec, probe, path)


@pytest.mark.asyncio
async def test_replay_rejects_a_duplicated_accent_token(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)

    def mutate(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        aesthetics = references["aesthetics"]
        assert type(aesthetics) is dict
        accents = aesthetics["accents"]
        assert type(accents) is list and len(accents) > 1
        assert type(accents[0]) is dict and type(accents[1]) is dict
        accents[1]["token"] = accents[0]["token"]

    _resign(path, mutate)
    with pytest.raises(ProductBuildError, match="duplicated"):
        await _build(spec, probe, path)


def test_aesthetics_module_does_not_name_a_live_client() -> None:
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
        "publish_page",
        "https://",
        "http://",
        "client_name",
        "etsy",
        "Etsy",
        "ETSY",
    ):
        assert token.casefold() not in source.casefold()


def test_session_seven_close_keeps_evidence_false() -> None:
    assert_session_seven_continuity(ROOT)
