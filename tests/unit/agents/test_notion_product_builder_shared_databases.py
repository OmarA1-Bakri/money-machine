"""Fixture-only shared-databases phase of the Notion product build."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
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
from money_machine.integrations.notion.domain import NotionDatabase, NotionPage
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from money_machine.integrations.notion.schema_builder import build_database_schema
from tests.fixtures.products import create_fixture_product_spec

ROOT = Path(__file__).parents[3]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
MODULE_PATHS = (
    ROOT / "src/money_machine/agents/implementations/notion_product_builder.py",
    ROOT / "src/money_machine/agents/implementations/notion_shared_databases.py",
)
WHEN = datetime(2026, 10, 3, 0, 30, tzinfo=UTC)
LATER = datetime(2026, 10, 5, 20, 0, tzinfo=UTC)
CLOSURE_SHA = "0f94d585f23d79e5ac18479f01e14f67cbaad332"
HEAD_SHA = "91a33eba7961ea2819dcc695f73ffe9a45e37b33"
BOOTSTRAP_SHA = "1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d"


def _spec(
    *,
    tier: str = "mass",
    shared: tuple[str, ...] = (),
    identity: str = "Weekly Planner",
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
        title="Shared Database Planner",
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
        hubs=(
            Hub(name="Hub 1", description="First hub", page_count=5),
            Hub(name="Hub 2", description="Second hub", page_count=5),
            Hub(name="Hub 3", description="Third hub", page_count=5),
            Hub(name="Hub 4", description="Fourth hub", page_count=5),
            Hub(name="Hub 5", description="Fifth hub", page_count=5),
            Hub(name="Hub 6", description="Sixth hub", page_count=5),
        ),
        colour_variants=("Blue", "Green", "Purple"),
        flagship_feature="One visible week",
        experiment_hypothesis="A visible week is enough",
        shared_databases=shared,
        page_target_min=40,
        page_target_max=60,
        concept_fingerprint="b" * 64,
        rule_version="v1",
        evidence=(
            EvidenceReference(
                evidence_id=uuid4(),
                evidence_type="fixture",
                source_reference="tests/unit/agents/test_notion_product_builder_shared_databases.py",
                observed_at=WHEN,
                safe_summary="Shared database fixture spec",
            ),
        ),
        created_at=WHEN,
    )


async def _phase_one(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=WHEN)


async def _build(
    spec: ProductSpec,
    probe: FixtureNotionAdapter,
    path: Path,
    *,
    recorded_at: datetime = LATER,
) -> ProductBuildCheckpoint:
    return await build_shared_databases(spec, probe, path, recorded_at=recorded_at)


def _page(probe: FixtureNotionAdapter) -> NotionPage:
    return next(iter(probe.pages.values()))


async def _seed(probe: FixtureNotionAdapter, page_id: str, kind: str) -> NotionDatabase:
    schema = build_database_schema(kind)
    database = await probe.create_database(title=kind, parent_id=page_id, parent_type="page_id")
    for prop in schema.properties:
        config = {"options": list(prop.options)} if prop.options else {}
        await probe.add_property(database.id, prop.name, prop.type, config)
    return database


def _titles(probe: FixtureNotionAdapter) -> list[str]:
    return [database.title for database in probe.databases.values()]


@pytest.mark.asyncio
async def test_mass_tier_creates_the_planner_databases_once(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)

    checkpoint = await _build(spec, probe, path)

    assert _titles(probe) == list(PLANNER_SHARED_DATABASES)
    assert checkpoint.checkpoint_names == (
        PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
        PHASE_SHARED_DATABASES,
    )
    assert checkpoint.next_phase == PHASE_DASHBOARD_AND_NAVIGATION
    assert checkpoint.next_phase == BUILD_PHASES[2]
    assert checkpoint.database_ids == tuple(
        (kind, database.id)
        for kind, database in zip(PLANNER_SHARED_DATABASES, probe.databases.values(), strict=True)
    )
    page = _page(probe)
    assert page.is_published is False
    assert len(probe.pages) == 1
    assert len(probe.blocks) == 1
    assert probe.views == {}
    assert probe.linked_views == {}
    hub_names = {hub.name for hub in spec.hubs}
    assert hub_names.isdisjoint(_titles(probe))
    for database in probe.databases.values():
        assert database.parent_id == page.id
        assert database.parent_type == "page_id"
        assert database.icon is None
        assert database.cover is None
    tasks = next(database for database in probe.databases.values() if database.title == "Tasks")
    assert [prop.name for prop in tasks.properties] == ["Name", "Status", "Due"]
    assert [prop.type for prop in tasks.properties] == ["title", "select", "date"]
    assert tasks.properties[1].config == {"options": ["Open", "Done"]}
    assert type(tasks.properties[1].config["options"]) is list
    assert tasks.properties[0].config == {}
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["checkpoint_names"] == [
        PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
        PHASE_SHARED_DATABASES,
    ]
    assert stored["recorded_at"] == LATER.isoformat()
    assert [
        row["kind"] for row in stored["provider_object_references"]["shared_databases"]
    ] == list(PLANNER_SHARED_DATABASES)
    assert "dashboard_and_navigation" not in stored["checkpoint_names"]


@pytest.mark.asyncio
async def test_replay_does_not_create_another_database(tmp_path: Path) -> None:
    spec = _spec(shared=tuple(reversed(PLANNER_SHARED_DATABASES)))
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    first = await _build(spec, probe, path)
    before = path.read_bytes()
    ids = {database.id for database in probe.databases.values()}

    second = await _build(spec, probe, path, recorded_at=datetime(2026, 10, 6, tzinfo=UTC))

    assert second == first
    assert path.read_bytes() == before
    assert {database.id for database in probe.databases.values()} == ids
    assert _titles(probe) == list(PLANNER_SHARED_DATABASES)
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES)


@pytest.mark.asyncio
async def test_business_tier_uses_the_business_set(tmp_path: Path) -> None:
    spec = _spec(tier="business")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)

    checkpoint = await _build(spec, probe, path)

    assert _titles(probe) == list(BUSINESS_SHARED_DATABASES)
    assert "Meals" not in _titles(probe)
    assert "Habits" not in _titles(probe)
    assert "Finance" not in _titles(probe)
    assert "Events" not in _titles(probe)
    assert checkpoint.database_ids[0][0] == "Clients"
    invoices = next(
        database for database in probe.databases.values() if database.title == "Invoices"
    )
    status = next(prop for prop in invoices.properties if prop.name == "Status")
    assert status.type == "select"
    assert status.config["options"] == ["Draft", "Sent", "Paid"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tier", "shared"),
    [
        ("mass", ("Tasks",)),
        ("mass", BUSINESS_SHARED_DATABASES),
        ("business", PLANNER_SHARED_DATABASES),
        ("mass", ("Tasks", "Tasks", "Events", "Habits", "Finance", "Meals", "Notes")),
        ("mass", ("tasks", "Events", "Habits", "Finance", "Meals", "Notes")),
        ("premium", ()),
        ("Mass", ()),
    ],
)
async def test_mismatched_databases_create_nothing(
    tmp_path: Path, tier: str, shared: tuple[str, ...]
) -> None:
    spec = _spec(tier=tier, shared=shared)
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="shared databases"):
        await _build(spec, probe, path)

    assert probe.databases == {}
    assert path.read_bytes() == before
    assert len(probe.pages) == 1


@pytest.mark.asyncio
async def test_missing_checkpoint_does_not_create_databases(tmp_path: Path) -> None:
    probe = FixtureNotionAdapter()
    with pytest.raises(ProductBuildError, match="phase 1 checkpoint"):
        await _build(_spec(), probe, tmp_path / "missing.json")
    assert probe.databases == {}
    assert probe.pages == {}


@pytest.mark.asyncio
async def test_missing_checkpoint_database_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    first = await _build(spec, probe, path)
    removed = first.database_ids[0][1]
    del probe.databases[removed]
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="missing"):
        await _build(spec, probe, path)

    assert removed not in probe.databases
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES) - 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_existing_matching_database_is_not_duplicated(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    page = _page(probe)
    seeded = await _seed(probe, page.id, "Meals")

    checkpoint = await _build(spec, probe, path)

    meals = [database for database in probe.databases.values() if database.title == "Meals"]
    assert len(meals) == 1
    assert meals[0].id == seeded.id
    assert _titles(probe).count("Meals") == 1
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES)
    assert dict(checkpoint.database_ids)["Meals"] == seeded.id


@pytest.mark.asyncio
async def test_existing_database_on_the_wrong_parent_is_not_copied(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    await _seed(probe, "ws_default", "Tasks")
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="does not match the schema"):
        await _build(spec, probe, path)

    assert _titles(probe) == ["Tasks"]
    assert next(iter(probe.databases.values())).parent_id == "ws_default"
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_wrong_schema_does_not_create_a_second_database(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    page = _page(probe)
    database = await probe.create_database(
        title="Finance", parent_id=page.id, parent_type="page_id"
    )
    await probe.add_property(database.id, "Name", "title", {})
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="does not match the schema"):
        await _build(spec, probe, path)

    assert len(probe.databases) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_duplicate_title_does_not_grow(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    page = _page(probe)
    await _seed(probe, page.id, "Notes")
    await _seed(probe, page.id, "Notes")
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="duplicated"):
        await _build(spec, probe, path)

    assert _titles(probe) == ["Notes", "Notes"]
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_extra_database_on_the_page_blocks_the_set(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    page = _page(probe)
    await probe.create_database(title="Scratch", parent_id=page.id, parent_type="page_id")
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="outside the shared set"):
        await _build(spec, probe, path)

    assert _titles(probe) == ["Scratch"]
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_tampered_database_on_resume_does_not_rewrite(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    await _build(spec, probe, path)
    tasks = next(database for database in probe.databases.values() if database.title == "Tasks")
    tasks.properties[1].type = "text"
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="missing"):
        await _build(spec, probe, path)

    assert path.read_bytes() == before
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES)


@pytest.mark.asyncio
async def test_extra_database_on_resume_does_not_rewrite(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    first = await _build(spec, probe, path)
    await probe.create_database(title="Scratch", parent_id=first.page_id, parent_type="page_id")
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="unexpected"):
        await _build(spec, probe, path)

    assert path.read_bytes() == before
    assert _titles(probe).count("Scratch") == 1
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES) + 1


@pytest.mark.asyncio
async def test_catalogue_spec_and_live_probes_are_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
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
        await build_shared_databases(create_fixture_product_spec(), probe, path, recorded_at=LATER)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_shared_databases(spec, SubclassProbe(), path, recorded_at=LATER)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_shared_databases(spec, APINotionAdapter(), path, recorded_at=LATER)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_shared_databases(spec, object(), path, recorded_at=LATER)

    assert probe.databases == {}
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_other_spec_does_not_create_databases(tmp_path: Path) -> None:
    spec = _spec()
    other = _spec(identity="Meal Planner")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="different ProductSpec"):
        await _build(other, probe, path)

    assert probe.databases == {}
    assert path.read_bytes() == before
    assert len(probe.pages) == 1


@pytest.mark.asyncio
async def test_naive_recorded_at_leaves_the_checkpoint_unchanged(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    await _build(spec, probe, path)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="timezone-aware"):
        await _build(spec, probe, path, recorded_at=datetime(2026, 10, 5, 20, 0))

    assert path.read_bytes() == before
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES)


@pytest.mark.asyncio
async def test_phase_one_does_not_run_again_after_shared_databases(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    await _build(spec, probe, path)
    before_pages = set(probe.pages)

    with pytest.raises(ProductBuildError):
        await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=LATER)

    assert set(probe.pages) == before_pages
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES)


def test_shared_databases_module_does_not_name_a_live_client() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in MODULE_PATHS)
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
        "create_linked_view",
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
    assert state["state_revision"] == 53
    assert "SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE" not in STATE_PATH.read_text(encoding="utf-8")
