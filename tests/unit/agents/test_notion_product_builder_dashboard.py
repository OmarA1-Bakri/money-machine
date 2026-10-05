"""Fixture-only dashboard and navigation phase of the Notion product build."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from money_machine.agents.implementations.notion_dashboard import (
    CALLOUT_ICON,
    build_dashboard_and_navigation,
    greeting_content,
    palette_cover,
)
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    DESIGN_SHELL_ICON,
    PHASE_DASHBOARD_AND_NAVIGATION,
    PHASE_SHARED_DATABASES,
    PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
    ProductBuildCheckpoint,
    ProductBuildError,
    build_top_level_page_and_design_shell,
)
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
MODULE_PATH = ROOT / "src/money_machine/agents/implementations/notion_dashboard.py"
WHEN = datetime(2026, 10, 3, 0, 30, tzinfo=UTC)
PHASE_TWO_AT = datetime(2026, 10, 5, 20, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)
CLOSURE_SHA = "0f94d585f23d79e5ac18479f01e14f67cbaad332"
HEAD_SHA = "676fabef5bd1b36018f1d2d539d282225d860a99"
BOOTSTRAP_SHA = "1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d"
_PHASES = (
    PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
    PHASE_SHARED_DATABASES,
    PHASE_DASHBOARD_AND_NAVIGATION,
)


def _spec(
    *,
    tier: str = "mass",
    identity: str = "Weekly Planner",
    buyer_problem: str = "Keep one week visible",
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
            Hub(name=f"{hub_name} {index}", description=f"Hub {index} copy", page_count=4)
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
                source_reference="tests/unit/agents/test_notion_product_builder_dashboard.py",
                observed_at=WHEN,
                safe_summary="Dashboard fixture spec",
            ),
        ),
        created_at=WHEN,
    )


async def _prepare(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=WHEN)
    await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)


async def _build(
    spec: ProductSpec,
    probe: FixtureNotionAdapter,
    path: Path,
    *,
    recorded_at: datetime = LATER,
) -> ProductBuildCheckpoint:
    return await build_dashboard_and_navigation(spec, probe, path, recorded_at=recorded_at)


def _page(probe: FixtureNotionAdapter) -> NotionPage:
    return next(iter(probe.pages.values()))


def _linked(probe: FixtureNotionAdapter, name: str) -> NotionLinkedView:
    return next(view for view in probe.linked_views.values() if view.name == name)


@pytest.mark.asyncio
async def test_mass_tier_builds_the_home_dashboard_once(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    database_ids = {database.title: database.id for database in probe.databases.values()}

    checkpoint = await _build(spec, probe, path)

    page = _page(probe)
    assert checkpoint.checkpoint_names == _PHASES
    assert checkpoint.next_phase == "identity_specific_hubs"
    assert checkpoint.next_phase == BUILD_PHASES[3]
    assert page.cover == palette_cover(spec)
    assert page.cover == "fixture://palette/Primary/#2C3E50"
    assert "http" not in (page.cover or "")
    assert page.icon == "header:Primary:#2C3E50"
    assert page.icon != DESIGN_SHELL_ICON
    assert page.is_published is False
    assert len(probe.pages) == 1
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES)
    assert probe.views == {}
    texts = [block.content for block in probe.blocks.values() if type(block) is NotionTextBlock]
    assert texts == [
        f"Hello, {spec.identity}. {spec.title} is ready.",
        "\n".join(("navigate", *(hub.name for hub in spec.hubs))),
    ]
    callouts = [
        block
        for block in probe.blocks.values()
        if type(block) is NotionCalloutBlock and block.icon == CALLOUT_ICON
    ]
    assert [block.content for block in callouts] == [
        f"{spec.identity} callout: {spec.buyer_problem}",
        f"{spec.identity} flagship: {spec.flagship_feature}",
    ]
    assert all(block.icon != DESIGN_SHELL_ICON for block in callouts)
    assert len(probe.blocks) == 5
    today = _linked(probe, "Today")
    month = _linked(probe, "Month")
    notes = _linked(probe, "Quick notes")
    assert today.view_type == "table"
    assert today.source_database_id == database_ids["Tasks"]
    assert today.parent_page_id == page.id
    assert today.filters == (("Due", "equals", "today"), ("Status", "equals", "Open"))
    assert month.view_type == "calendar"
    assert month.source_database_id == database_ids["Events"]
    assert month.filters == ()
    assert notes.view_type == "table"
    assert notes.source_database_id == database_ids["Notes"]
    assert len(probe.linked_views) == 3
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["checkpoint_names"] == list(_PHASES)
    assert stored["recorded_at"] == LATER.isoformat()
    assert [row["kind"] for row in stored["provider_object_references"]["dashboard"]] == [
        "cover",
        "header",
        "greeting",
        "hub_navigation",
        "today",
        "month",
        "quick_notes",
        "callout",
        "callout",
    ]
    assert "identity_specific_hubs" not in stored["checkpoint_names"]
    assert "notification_dashboard" not in stored["checkpoint_names"]
    assert "notification_dashboard" not in path.read_text(encoding="ascii")


@pytest.mark.asyncio
async def test_replay_does_not_create_another_dashboard(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    first = await _build(spec, probe, path)
    before = path.read_bytes()
    block_ids = set(probe.blocks)
    view_ids = set(probe.linked_views)

    second = await _build(spec, probe, path, recorded_at=datetime(2026, 10, 6, tzinfo=UTC))

    assert second == first
    assert path.read_bytes() == before
    assert set(probe.blocks) == block_ids
    assert set(probe.linked_views) == view_ids
    assert len(probe.pages) == 1
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES)


@pytest.mark.asyncio
async def test_business_tier_omits_the_event_calendar(tmp_path: Path) -> None:
    spec = _spec(tier="business", identity="Client Desk")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)

    checkpoint = await _build(spec, probe, path)

    titles = [database.title for database in probe.databases.values()]
    assert titles == list(BUSINESS_SHARED_DATABASES)
    assert "Events" not in titles
    assert {view.name for view in probe.linked_views.values()} == {"Today", "Quick notes"}
    assert all(view.view_type != "calendar" for view in probe.linked_views.values())
    assert "month" not in {kind for kind, _value in checkpoint.dashboard_pieces}
    greeting = next(block for block in probe.blocks.values() if type(block) is NotionTextBlock)
    assert "Client Desk" in greeting.content
    assert "Weekly Planner" not in greeting.content
    assert len(probe.pages) == 1
    assert len(probe.blocks) == 5
    before = path.read_bytes()

    again = await _build(spec, probe, path, recorded_at=datetime(2026, 10, 6, tzinfo=UTC))

    assert again == checkpoint
    assert "month" not in {kind for kind, _value in again.dashboard_pieces}
    assert path.read_bytes() == before
    assert {view.name for view in probe.linked_views.values()} == {"Today", "Quick notes"}


@pytest.mark.asyncio
async def test_matching_pieces_are_adopted(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    page = _page(probe)
    await probe.set_cover(page.id, palette_cover(spec))
    existing = await probe.add_text_block(page.id, greeting_content(spec))

    await _build(spec, probe, path)

    greetings = [
        block
        for block in probe.blocks.values()
        if type(block) is NotionTextBlock and block.content == greeting_content(spec)
    ]
    assert greetings == [existing]
    assert page.cover == palette_cover(spec)


@pytest.mark.asyncio
async def test_duplicate_greeting_is_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    page = _page(probe)
    await probe.add_text_block(page.id, greeting_content(spec))
    await probe.add_text_block(page.id, greeting_content(spec))
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="duplicated"):
        await _build(spec, probe, path)

    assert probe.linked_views == {}
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_matching_month_view_is_adopted(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    page = _page(probe)
    events_id = next(
        database.id for database in probe.databases.values() if database.title == "Events"
    )
    existing = await probe.create_linked_view(events_id, page.id, "calendar")
    existing.name = "Month"
    existing.filters = ()

    await _build(spec, probe, path)

    months = [view for view in probe.linked_views.values() if view.name == "Month"]
    assert months == [existing]
    assert existing.source_database_id == events_id


@pytest.mark.asyncio
async def test_wrong_cover_is_not_rewritten(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    page = _page(probe)
    await probe.set_cover(page.id, "fixture://palette/other")
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="cover"):
        await _build(spec, probe, path)

    assert page.cover == "fixture://palette/other"
    assert probe.linked_views == {}
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_missing_checkpoint_creates_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()

    with pytest.raises(ProductBuildError, match="shared databases checkpoint"):
        await _build(spec, probe, tmp_path / "missing.json")

    assert probe.pages == {}
    assert probe.linked_views == {}
    assert probe.databases == {}


@pytest.mark.asyncio
async def test_phase_one_checkpoint_does_not_build_the_dashboard(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=WHEN)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="shared databases checkpoint"):
        await _build(spec, probe, path)

    assert probe.databases == {}
    assert probe.linked_views == {}
    assert len(probe.blocks) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_missing_page_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    page = _page(probe)
    del probe.pages[page.id]
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="missing"):
        await _build(spec, probe, path)

    assert probe.linked_views == {}
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES)
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_missing_database_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    tasks_id = next(
        database.id for database in probe.databases.values() if database.title == "Tasks"
    )
    del probe.databases[tasks_id]
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="missing"):
        await _build(spec, probe, path)

    assert probe.linked_views == {}
    assert tasks_id not in probe.databases
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_missing_today_view_on_resume_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    today = _linked(probe, "Today")
    del probe.linked_views[today.id]
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="missing"):
        await _build(spec, probe, path)

    assert today.id not in probe.linked_views
    assert len(probe.linked_views) == 2
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_tampered_today_filter_is_not_rewritten(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    today = _linked(probe, "Today")
    today.filters = (("Status", "equals", "Done"),)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="missing"):
        await _build(spec, probe, path)

    assert today.filters == (("Status", "equals", "Done"),)
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_extra_view_on_resume_does_not_rewrite(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    first = await _build(spec, probe, path)
    tasks_id = next(
        database.id for database in probe.databases.values() if database.title == "Tasks"
    )
    extra = await probe.create_linked_view(tasks_id, first.page_id, "board")
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="unexpected"):
        await _build(spec, probe, path)

    assert extra.id in probe.linked_views
    assert len(probe.linked_views) == 4
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_hub_page_is_not_created(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    page = _page(probe)
    extra = await probe.add_child_page(page.id, spec.hubs[0].name)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="unexpected"):
        await _build(spec, probe, path)

    assert extra.id in probe.pages
    assert len(probe.pages) == 2
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_published_page_is_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    _page(probe).is_published = True
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="unpublished"):
        await _build(spec, probe, path)

    assert probe.linked_views == {}
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_newline_in_the_buyer_problem_creates_nothing(tmp_path: Path) -> None:
    spec = _spec(buyer_problem="line\nbreak")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="single lines"):
        await _build(spec, probe, path)

    assert probe.linked_views == {}
    assert len(probe.blocks) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_catalogue_spec_and_live_probes_are_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    before = path.read_bytes()

    class SubclassProbe(FixtureNotionAdapter):
        async def create_linked_view(
            self,
            source_database_id: str,
            parent_page_id: str,
            view_type: str = "table",
        ) -> NotionLinkedView:
            raise AssertionError("create_linked_view must not run")

    with pytest.raises(ProductBuildError, match="validated ProductSpec"):
        await build_dashboard_and_navigation(
            create_fixture_product_spec(), probe, path, recorded_at=LATER
        )
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_dashboard_and_navigation(spec, SubclassProbe(), path, recorded_at=LATER)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_dashboard_and_navigation(spec, APINotionAdapter(), path, recorded_at=LATER)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_dashboard_and_navigation(spec, object(), path, recorded_at=LATER)

    assert probe.linked_views == {}
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES)
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_other_spec_does_not_build_a_dashboard(tmp_path: Path) -> None:
    spec = _spec()
    other = _spec(identity="Meal Planner")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="different ProductSpec"):
        await _build(other, probe, path)

    assert probe.linked_views == {}
    assert path.read_bytes() == before
    assert len(probe.pages) == 1


@pytest.mark.asyncio
async def test_naive_recorded_at_leaves_the_checkpoint_unchanged(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="timezone-aware"):
        await _build(spec, probe, path, recorded_at=datetime(2026, 10, 5, 22, 30))

    assert path.read_bytes() == before
    assert len(probe.linked_views) == 3


@pytest.mark.asyncio
async def test_earlier_phases_do_not_run_again_after_the_dashboard(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    before_pages = set(probe.pages)
    before_databases = set(probe.databases)

    with pytest.raises(ProductBuildError):
        await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=LATER)
    with pytest.raises(ProductBuildError):
        await build_shared_databases(spec, probe, path, recorded_at=LATER)

    assert set(probe.pages) == before_pages
    assert set(probe.databases) == before_databases
    assert len(probe.linked_views) == 3


@pytest.mark.asyncio
async def test_dashboard_checkpoint_without_pieces_is_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    del payload["provider_object_references"]["dashboard"]
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="ascii")
    before_views = set(probe.linked_views)

    with pytest.raises(ProductBuildError, match="provider references"):
        await _build(spec, probe, path)

    assert set(probe.linked_views) == before_views


def test_dashboard_module_does_not_name_a_live_client() -> None:
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
        "build_notification_dashboard",
        "create_rollup",
        "create_relation",
        "create_formula",
        "create_database",
        "create_page",
        "add_child_page",
        "create_calendar_view",
        "create_table_view",
        "create_board_view",
        "https://",
        "http://",
        "notification_dashboard",
        "identity_specific_hubs",
    ):
        assert token not in source


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
    assert state["state_revision"] == 51
    assert "SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE" not in STATE_PATH.read_text(encoding="utf-8")
