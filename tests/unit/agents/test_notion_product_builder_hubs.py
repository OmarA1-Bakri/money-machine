"""Fixture-only identity-specific hubs phase of the Notion product build."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from money_machine.agents.implementations.notion_dashboard import build_dashboard_and_navigation
from money_machine.agents.implementations.notion_hubs import (
    build_identity_specific_hubs,
    linked_view_name,
    navigation_content,
    section_content,
)
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    PHASE_DASHBOARD_AND_NAVIGATION,
    PHASE_SHARED_DATABASES,
    PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
    ProductBuildCheckpoint,
    ProductBuildError,
    build_top_level_page_and_design_shell,
)
from money_machine.agents.implementations.notion_progress import stamp_integrity_digest
from money_machine.agents.implementations.notion_shared_databases import (
    BUSINESS_SHARED_DATABASES,
    PLANNER_SHARED_DATABASES,
    build_shared_databases,
)
from money_machine.control.state import SESSION_EVIDENCE_KEYS
from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.product_spec import ColourToken, Hub, ProductSpec
from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.domain import (
    NotionCalloutBlock,
    NotionLinkedView,
    NotionPage,
    NotionTextBlock,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from tests.fixtures.products import create_fixture_product_spec

ROOT = Path(__file__).parents[3]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
MODULE_PATH = ROOT / "src/money_machine/agents/implementations/notion_hubs.py"
WHEN = datetime(2026, 10, 3, 0, 30, tzinfo=UTC)
PHASE_TWO_AT = datetime(2026, 10, 5, 20, 0, tzinfo=UTC)
DASHBOARD_AT = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)
LATER = datetime(2026, 10, 5, 23, 45, tzinfo=UTC)
CLOSURE_SHA = "0f94d585f23d79e5ac18479f01e14f67cbaad332"
HEAD_SHA = "6575c567fcadde636846131f98d7599067babb66"
BOOTSTRAP_SHA = "1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d"
_PHASES = (
    PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
    PHASE_SHARED_DATABASES,
    PHASE_DASHBOARD_AND_NAVIGATION,
    "identity_specific_hubs",
)
_ROLES = ("purpose", "practice", "buyer")


def _spec(
    *,
    tier: str = "mass",
    identity: str = "Weekly Planner",
    buyer_problem: str = "Keep one week visible",
    title: str = "Home Dashboard Planner",
    hub_name: str = "Hub",
    hub_count: int = 6,
    hub_description: str | None = None,
    page_count: int = 3,
    flagship_feature: str = "One visible week",
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
        buyer_problem=buyer_problem,
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
            Hub(
                name=f"{hub_name} {index}",
                description=hub_description or f"{identity} copy {index}",
                page_count=page_count,
            )
            for index in range(1, hub_count + 1)
        ),
        colour_variants=("Blue", "Green", "Purple"),
        flagship_feature=flagship_feature,
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
                source_reference="tests/unit/agents/test_notion_product_builder_hubs.py",
                observed_at=WHEN,
                safe_summary="Identity hub fixture spec",
            ),
        ),
        created_at=WHEN,
    )


async def _prepare(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=WHEN)
    await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)
    await build_dashboard_and_navigation(spec, probe, path, recorded_at=DASHBOARD_AT)


async def _build(
    spec: ProductSpec,
    probe: FixtureNotionAdapter,
    path: Path,
    *,
    recorded_at: datetime = LATER,
) -> ProductBuildCheckpoint:
    return await build_identity_specific_hubs(spec, probe, path, recorded_at=recorded_at)


def _home(probe: FixtureNotionAdapter) -> NotionPage:
    return next(page for page in probe.pages.values() if page.parent_type == "workspace")


def _hub_page(probe: FixtureNotionAdapter, title: str) -> NotionPage:
    return next(page for page in probe.pages.values() if page.title == title)


def _database_id(probe: FixtureNotionAdapter, title: str) -> str:
    return next(database.id for database in probe.databases.values() if database.title == title)


def _hub_views(probe: FixtureNotionAdapter, page_id: str) -> list[NotionLinkedView]:
    return [view for view in probe.linked_views.values() if view.parent_page_id == page_id]


def _hub_texts(probe: FixtureNotionAdapter, page_id: str) -> list[str]:
    return [
        block.content
        for block in probe.blocks.values()
        if type(block) is NotionTextBlock and block.parent_id == page_id
    ]


@pytest.mark.asyncio
async def test_mass_tier_builds_identity_hubs_once(tmp_path: Path) -> None:
    spec = _spec(page_count=9)
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe)
    database_ids = {database.id for database in probe.databases.values()}
    today_id = next(view.id for view in probe.linked_views.values() if view.name == "Today")

    checkpoint = await _build(spec, probe, path)

    assert checkpoint.checkpoint_names == _PHASES
    assert checkpoint.next_phase == "notification_dashboard"
    assert checkpoint.next_phase == BUILD_PHASES[4]
    assert checkpoint.recorded_at == LATER
    assert len(probe.pages) == 7
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES)
    assert {database.id for database in probe.databases.values()} == database_ids
    assert probe.views == {}
    assert home.is_published is False
    assert next(view.id for view in probe.linked_views.values() if view.name == "Today") == today_id
    assert len(probe.linked_views) == 15
    for index, hub in enumerate(spec.hubs, start=1):
        page = _hub_page(probe, hub.name)
        assert page.parent_id == home.id
        assert page.parent_type == "page_id"
        assert page.is_published is False
        assert page.icon is None
        assert page.cover is None
        texts = _hub_texts(probe, page.id)
        assert texts == [section_content(spec, hub.name, role) for role in _ROLES] + [
            navigation_content(spec, hub.name)
        ]
        assert len(texts) == 4
        assert spec.identity in texts[0]
        assert hub.description in texts[0]
        assert spec.title in texts[-1]
        views = _hub_views(probe, page.id)
        assert len(views) == 2
        assert any(view.filters for view in views)
        assert {view.source_database_id for view in views} <= database_ids
        assert all(spec.identity in view.name and hub.name in view.name for view in views)
        assert hub.name == f"Hub {index}"
    events = _hub_views(probe, _hub_page(probe, "Hub 3").id)
    by_name = {view.name: view for view in events}
    events_view = by_name[linked_view_name(spec, "Hub 3", "events today")]
    habits_view = by_name[linked_view_name(spec, "Hub 3", "habits today")]
    assert events_view.view_type == "calendar"
    assert events_view.source_database_id == _database_id(probe, "Events")
    assert events_view.filters == (("Date", "equals", "today"),)
    assert habits_view.view_type == "table"
    assert habits_view.source_database_id == _database_id(probe, "Habits")
    open_tasks = next(
        view
        for view in _hub_views(probe, _hub_page(probe, "Hub 1").id)
        if view.name == linked_view_name(spec, "Hub 1", "open tasks")
    )
    assert open_tasks.view_type == "table"
    assert open_tasks.source_database_id == _database_id(probe, "Tasks")
    assert open_tasks.filters == (("Status", "equals", "Open"),)
    notes = next(
        view
        for view in _hub_views(probe, _hub_page(probe, "Hub 6").id)
        if view.name == linked_view_name(spec, "Hub 6", "notes")
    )
    assert notes.source_database_id == _database_id(probe, "Notes")
    assert notes.filters == ()
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["checkpoint_names"] == list(_PHASES)
    assert "notification_dashboard" not in stored["checkpoint_names"]
    assert "aesthetics_and_content_completion" not in stored["checkpoint_names"]
    assert "notification_dashboard" in stored["progress"]["deferred_operations"]
    assert "aesthetics_and_content_completion" in stored["progress"]["deferred_operations"]
    hubs = stored["provider_object_references"]["identity_hubs"]
    assert [row["name"] for row in hubs] == [hub.name for hub in spec.hubs]
    assert [section["role"] for section in hubs[0]["sections"]] == list(_ROLES)
    assert len(hubs[0]["views"]) == 2


@pytest.mark.asyncio
async def test_replay_does_not_create_another_hub(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    first = await _build(spec, probe, path)
    before = path.read_bytes()
    pages = set(probe.pages)
    views = set(probe.linked_views)
    blocks = set(probe.blocks)

    second = await _build(spec, probe, path, recorded_at=datetime(2026, 10, 6, tzinfo=UTC))

    assert set(probe.pages) == pages
    assert set(probe.linked_views) == views
    assert set(probe.blocks) == blocks
    assert second == first
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_business_tier_does_not_invent_events(tmp_path: Path) -> None:
    spec = _spec(tier="business", identity="Client Desk", title="Client Desk Home")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    database_ids = {database.id for database in probe.databases.values()}

    checkpoint = await _build(spec, probe, path)

    titles = [database.title for database in probe.databases.values()]
    assert titles == list(BUSINESS_SHARED_DATABASES)
    assert "Events" not in titles
    assert len(probe.pages) == 7
    assert len(probe.linked_views) == 14
    assert {view.source_database_id for view in probe.linked_views.values()} <= database_ids
    assert all("events today" not in view.name for view in probe.linked_views.values())
    assert all("Weekly Planner" not in view.name for view in probe.linked_views.values())
    hub = _hub_page(probe, "Hub 1")
    texts = _hub_texts(probe, hub.id)
    assert all("Client Desk" in text for text in texts)
    assert all("Weekly Planner" not in text for text in texts)
    assert "Client Desk Home" in texts[-1]
    open_tasks = next(
        view
        for view in _hub_views(probe, hub.id)
        if view.name == linked_view_name(spec, "Hub 1", "open tasks")
    )
    assert open_tasks.source_database_id == _database_id(probe, "Tasks")
    assert open_tasks.filters == (("Status", "equals", "Open"),)
    projects = [
        view
        for view in probe.linked_views.values()
        if view.source_database_id == _database_id(probe, "Projects")
    ]
    assert projects
    assert all(view.view_type == "board" for view in projects)
    assert checkpoint.next_phase == "notification_dashboard"
    before = path.read_bytes()

    again = await _build(spec, probe, path, recorded_at=datetime(2026, 10, 6, tzinfo=UTC))

    assert again == checkpoint
    assert path.read_bytes() == before
    assert "Events" not in [database.title for database in probe.databases.values()]


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["mass", "business"])
async def test_eight_hubs_stay_on_canonical_databases(tier: str, tmp_path: Path) -> None:
    spec = _spec(tier=tier, hub_count=8, identity=f"{tier} desk")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    before = {database.id for database in probe.databases.values()}

    await _build(spec, probe, path)

    assert len(probe.pages) == 9
    assert {page.title for page in probe.pages.values() if page.parent_type == "page_id"} == {
        hub.name for hub in spec.hubs
    }
    assert {database.id for database in probe.databases.values()} == before
    assert all(
        len(_hub_views(probe, page.id)) == 2
        for page in probe.pages.values()
        if page.parent_type == "page_id"
    )
    titles = {database.title for database in probe.databases.values()}
    if tier == "business":
        assert "Events" not in titles
    else:
        assert "Events" in titles


@pytest.mark.asyncio
async def test_two_products_do_not_share_hub_copy(tmp_path: Path) -> None:
    mass = _spec(identity="Weekly Planner", title="Week Home")
    business = _spec(
        tier="business", identity="Studio Ledger", title="Studio Home", hub_name="Desk"
    )
    mass_probe = FixtureNotionAdapter()
    business_probe = FixtureNotionAdapter()
    await _prepare(mass, mass_probe, tmp_path / "mass.json")
    await _prepare(business, business_probe, tmp_path / "business.json")
    await _build(mass, mass_probe, tmp_path / "mass.json")
    await _build(business, business_probe, tmp_path / "business.json")

    def copy(probe: FixtureNotionAdapter) -> set[str]:
        home = _home(probe).id
        return {
            block.content
            for block in probe.blocks.values()
            if type(block) is NotionTextBlock and block.parent_id != home
        }

    mass_copy = copy(mass_probe)
    business_copy = copy(business_probe)
    assert mass_copy.isdisjoint(business_copy)
    assert all("Weekly Planner" in text for text in mass_copy)
    assert all("Studio Ledger" in text for text in business_copy)
    assert not any(text == "Welcome to your hub" for text in mass_copy | business_copy)


@pytest.mark.asyncio
async def test_matching_section_is_adopted(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe)
    existing_page = await probe.add_child_page(home.id, spec.hubs[0].name)
    existing = await probe.add_text_block(
        existing_page.id, section_content(spec, spec.hubs[0].name, "purpose")
    )

    await _build(spec, probe, path)

    purposes = [
        block
        for block in probe.blocks.values()
        if type(block) is NotionTextBlock
        and block.content == section_content(spec, spec.hubs[0].name, "purpose")
    ]
    assert purposes == [existing]
    assert _hub_page(probe, spec.hubs[0].name).id == existing_page.id
    assert len([page for page in probe.pages.values() if page.title == spec.hubs[0].name]) == 1
    assert len(probe.pages) == 7


@pytest.mark.asyncio
async def test_duplicate_hub_page_is_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe)
    await probe.add_child_page(home.id, spec.hubs[0].name)
    await probe.add_child_page(home.id, spec.hubs[0].name)
    before = path.read_bytes()
    views = set(probe.linked_views)

    with pytest.raises(ProductBuildError, match="duplicated"):
        await _build(spec, probe, path)

    assert set(probe.linked_views) == views
    assert len(probe.pages) == 3
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_unexpected_hub_block_is_not_rewritten(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe)
    page = await probe.add_child_page(home.id, spec.hubs[0].name)
    junk = await probe.add_text_block(page.id, "generic filler")
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="unexpected"):
        await _build(spec, probe, path)

    assert junk.content == "generic filler"
    assert len(probe.pages) == 2
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_missing_checkpoint_creates_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "missing.json"

    with pytest.raises(ProductBuildError, match="dashboard checkpoint"):
        await _build(spec, probe, path)

    assert path.exists() is False
    assert probe.pages == {}
    assert probe.linked_views == {}


@pytest.mark.asyncio
async def test_dashboard_phase_is_required(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=WHEN)
    await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="dashboard checkpoint"):
        await _build(spec, probe, path)

    assert len(probe.pages) == 1
    assert probe.linked_views == {}
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_missing_page_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe)
    del probe.pages[home.id]
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="missing"):
        await _build(spec, probe, path)

    assert len(probe.pages) == 0
    assert len(probe.linked_views) == 3
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_missing_database_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    tasks_id = _database_id(probe, "Tasks")
    del probe.databases[tasks_id]
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="missing"):
        await _build(spec, probe, path)

    assert tasks_id not in probe.databases
    assert len(probe.pages) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_missing_dashboard_view_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    today = next(view for view in probe.linked_views.values() if view.name == "Today")
    del probe.linked_views[today.id]
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="missing"):
        await _build(spec, probe, path)

    assert today.id not in probe.linked_views
    assert len(probe.pages) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_missing_hub_page_on_resume_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    hub = _hub_page(probe, "Hub 1")
    del probe.pages[hub.id]
    before = path.read_bytes()
    pages = set(probe.pages)

    with pytest.raises(ProductBuildError, match="missing"):
        await _build(spec, probe, path)

    assert hub.id not in probe.pages
    assert set(probe.pages) == pages
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_tampered_hub_filter_is_not_rewritten(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    view = next(
        item
        for item in _hub_views(probe, _hub_page(probe, "Hub 1").id)
        if item.filters == (("Status", "equals", "Open"),)
    )
    view.filters = (("Status", "equals", "Done"),)
    before = path.read_bytes()
    views = set(probe.linked_views)

    with pytest.raises(ProductBuildError, match="missing"):
        await _build(spec, probe, path)

    assert view.filters == (("Status", "equals", "Done"),)
    assert set(probe.linked_views) == views
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_extra_page_on_resume_is_not_removed(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    first = await _build(spec, probe, path)
    extra = await probe.add_child_page(first.page_id, "Loose page")
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="unexpected"):
        await _build(spec, probe, path)

    assert extra.id in probe.pages
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_published_hub_page_is_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    home = _home(probe)
    page = await probe.add_child_page(home.id, spec.hubs[0].name)
    page.is_published = True
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="unpublished"):
        await _build(spec, probe, path)

    assert page.is_published is True
    assert len(probe.pages) == 2
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_published_page_is_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    _home(probe).is_published = True
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="unpublished"):
        await _build(spec, probe, path)

    assert len(probe.pages) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_newline_in_a_hub_description_creates_nothing(tmp_path: Path) -> None:
    spec = _spec(hub_description="line\nbreak")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="single lines"):
        await _build(spec, probe, path)

    assert len(probe.pages) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_duplicate_hub_names_are_rejected(tmp_path: Path) -> None:
    spec = _spec(hub_name="Same", hub_count=6)
    spec = spec.model_copy(
        update={
            "hubs": tuple(
                Hub(name="Same", description=f"Copy {index}", page_count=3) for index in range(6)
            )
        }
    )
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="unique"):
        await _build(spec, probe, path)

    assert len(probe.pages) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_a_realistic_long_view_name_stays_unique_and_within_the_cap(tmp_path: Path) -> None:
    identity = "Organized Working Parent Command Center"
    hub_name = "School And Activities Planner"
    spec = _spec(identity=identity, hub_name=hub_name, hub_count=6)
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)

    checkpoint = await _build(spec, probe, path)

    raw = [f"{identity} {hub.name} open tasks" for hub in spec.hubs[:2]]
    assert all(len(name) > 64 for name in raw)
    assert raw[0][:64] == raw[1][:64]
    capped = [linked_view_name(spec, hub.name, "open tasks") for hub in spec.hubs[:2]]
    assert capped[0] != capped[1]
    assert all(len(name) <= 64 for name in capped)
    for name in capped:
        token = name.split()[-1]
        assert len(token) == 8
        assert name.endswith(f"open tasks {token}")
    names = [
        view.name for hub in spec.hubs for view in _hub_views(probe, _hub_page(probe, hub.name).id)
    ]
    assert len(names) == len(set(names))
    assert all(len(name) <= 64 for name in names)
    assert checkpoint.next_phase == "notification_dashboard"
    assert len(probe.pages) == 7


@pytest.mark.asyncio
async def test_fewer_or_more_than_six_to_eight_hubs_create_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    before = path.read_bytes()
    short = spec.model_copy(update={"hubs": spec.hubs[:5]})
    extra = tuple(
        Hub(name=f"Extra {index}", description=f"Extra copy {index}", page_count=3)
        for index in range(3)
    )
    long = spec.model_copy(update={"hubs": spec.hubs + extra})

    with pytest.raises(ProductBuildError, match=r"^hubs must be six to eight$"):
        await _build(short, probe, path)
    with pytest.raises(ProductBuildError, match=r"^hubs must be six to eight$"):
        await _build(long, probe, path)

    assert len(probe.pages) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_deleted_design_shell_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    shell_id = payload["provider_object_references"]["design_shell_block_id"]
    del probe.blocks[shell_id]
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="is missing"):
        await _build(spec, probe, path)

    assert shell_id not in probe.blocks
    assert len(probe.pages) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_tampered_design_shell_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    shell_id = payload["provider_object_references"]["design_shell_block_id"]
    shell = probe.blocks[shell_id]
    shell.content = "tampered shell"
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="does not match"):
        await _build(spec, probe, path)

    assert probe.blocks[shell_id].content == "tampered shell"
    assert len(probe.pages) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_deleted_navigation_block_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await _build(spec, probe, path)
    navigation_id = checkpoint.identity_hubs[0].navigation_block_id
    del probe.blocks[navigation_id]
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="hub piece is missing"):
        await _build(spec, probe, path, recorded_at=datetime(2026, 10, 6, tzinfo=UTC))

    assert navigation_id not in probe.blocks
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_catalogue_spec_and_live_probes_are_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    before = path.read_bytes()

    class SubclassProbe(FixtureNotionAdapter):
        async def add_child_page(self, parent_page_id: str, title: str) -> NotionPage:
            raise AssertionError("add_child_page must not run")

    with pytest.raises(ProductBuildError, match="validated ProductSpec"):
        await build_identity_specific_hubs(
            create_fixture_product_spec(), probe, path, recorded_at=LATER
        )
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_identity_specific_hubs(spec, SubclassProbe(), path, recorded_at=LATER)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_identity_specific_hubs(spec, APINotionAdapter(), path, recorded_at=LATER)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_identity_specific_hubs(spec, object(), path, recorded_at=LATER)

    assert len(probe.pages) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_other_spec_does_not_build_hubs(tmp_path: Path) -> None:
    spec = _spec()
    other = _spec(identity="Meal Planner")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="different ProductSpec"):
        await _build(other, probe, path)

    assert len(probe.pages) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_naive_recorded_at_leaves_the_checkpoint_unchanged(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="timezone-aware"):
        await _build(spec, probe, path, recorded_at=datetime(2026, 10, 5, 23, 45))

    assert path.read_bytes() == before
    assert len(probe.pages) == 7


@pytest.mark.asyncio
async def test_earlier_phases_do_not_run_again_after_the_hubs(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    pages = set(probe.pages)
    databases = set(probe.databases)

    with pytest.raises(ProductBuildError):
        await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=LATER)
    with pytest.raises(ProductBuildError):
        await build_shared_databases(spec, probe, path, recorded_at=LATER)
    with pytest.raises(ProductBuildError):
        await build_dashboard_and_navigation(spec, probe, path, recorded_at=LATER)

    assert set(probe.pages) == pages
    assert set(probe.databases) == databases


@pytest.mark.asyncio
async def test_hubs_checkpoint_without_records_is_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    del payload["provider_object_references"]["identity_hubs"]
    payload = stamp_integrity_digest(payload)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="ascii")
    pages = set(probe.pages)

    with pytest.raises(ProductBuildError, match="provider references"):
        await _build(spec, probe, path)

    assert set(probe.pages) == pages


@pytest.mark.asyncio
async def test_five_hub_records_are_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    payload["provider_object_references"]["identity_hubs"] = payload["provider_object_references"][
        "identity_hubs"
    ][:5]
    payload = stamp_integrity_digest(payload)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="ascii")
    pages = set(probe.pages)

    with pytest.raises(ProductBuildError, match="six to eight"):
        await _build(spec, probe, path)

    assert set(probe.pages) == pages


@pytest.mark.asyncio
async def test_swapped_section_roles_are_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    sections = payload["provider_object_references"]["identity_hubs"][0]["sections"]
    sections[0]["role"], sections[1]["role"] = sections[1]["role"], sections[0]["role"]
    payload = stamp_integrity_digest(payload)
    path.write_text(json.dumps(payload) + "\n", encoding="ascii")
    pages = set(probe.pages)

    with pytest.raises(ProductBuildError, match="unsupported"):
        await _build(spec, probe, path)

    assert set(probe.pages) == pages


def test_hubs_module_does_not_name_a_live_client_or_later_phase() -> None:
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
        "AsyncClient",
        "publish_page",
        "create_database",
        "create_page",
        "create_rollup",
        "create_relation",
        "create_formula",
        "build_notification_dashboard",
        "notification_dashboard",
        "aesthetics_and_content_completion",
        "https://",
        "http://",
        "etsy",
        "Etsy",
        "ETSY",
    ):
        assert token.casefold() not in source.casefold()


@pytest.mark.asyncio
async def test_icon_only_design_shell_tamper_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    shell_id = payload["provider_object_references"]["design_shell_block_id"]
    shell = probe.blocks[shell_id]
    assert isinstance(shell, NotionCalloutBlock)
    shell.icon = "💡"
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="does not match"):
        await _build(spec, probe, path)

    assert shell.icon == "💡"
    assert len(probe.pages) == 1
    assert path.read_bytes() == before


def test_linked_view_name_token_is_the_sha256_prefix() -> None:
    identity = "Organized Working Parent Command Center"
    hub_name = "School And Activities Planner"
    spec = _spec(identity=identity, hub_name=hub_name, hub_count=6)
    named = linked_view_name(spec, spec.hubs[0].name, "open tasks")
    assert named == "Organized Working Parent Command Center Scho open tasks 447d8579"
    assert linked_view_name(spec, spec.hubs[0].name, "open tasks") == named


@pytest.mark.asyncio
async def test_long_view_name_replay_keeps_the_same_bytes_and_ids(tmp_path: Path) -> None:
    identity = "Organized Working Parent Command Center"
    hub_name = "School And Activities Planner"
    spec = _spec(identity=identity, hub_name=hub_name, hub_count=6)
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await _build(spec, probe, path)
    before = path.read_bytes()
    view_ids = set(probe.linked_views)

    again = await _build(spec, probe, path, recorded_at=datetime(2026, 10, 6, 1, tzinfo=UTC))

    assert again == checkpoint
    assert path.read_bytes() == before
    assert set(probe.linked_views) == view_ids


@pytest.mark.asyncio
async def test_deleted_section_block_on_resume_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await _build(spec, probe, path)
    block_id = checkpoint.identity_hubs[0].sections[0][1]
    del probe.blocks[block_id]
    before = path.read_bytes()
    pages = set(probe.pages)

    with pytest.raises(ProductBuildError, match="hub piece is missing"):
        await _build(spec, probe, path)

    assert block_id not in probe.blocks
    assert set(probe.pages) == pages
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_hub_checkpoint_parser_rejects_bad_inputs(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    pages = set(probe.pages)
    original = path.read_text(encoding="ascii")
    path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ProductBuildError, match="must be an object"):
        await _build(spec, probe, path)

    payload = json.loads(original)
    payload["provider_object_references"]["identity_hubs"][0].pop("page_id")
    payload = stamp_integrity_digest(payload)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii"
    )

    with pytest.raises(ProductBuildError, match="missing or unsupported"):
        await _build(spec, probe, path)

    assert set(probe.pages) == pages


@pytest.mark.asyncio
async def test_hub_name_longer_than_64_characters_creates_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    before = path.read_bytes()
    cloned = spec.hubs[0].model_copy(update={"name": "N" * 65})
    long = spec.model_copy(update={"hubs": (cloned, *spec.hubs[1:])})

    with pytest.raises(ProductBuildError, match="at most 64"):
        await _build(long, probe, path)

    assert len(probe.pages) == 1
    assert path.read_bytes() == before


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
    assert evidence["identity_hubs_built"] is False
    assert evidence["notification_dashboard_built"] is False
    assert evidence["home_dashboard_built"] is False
    assert state["state_revision"] == 60
    assert "SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE" not in STATE_PATH.read_text(encoding="utf-8")
