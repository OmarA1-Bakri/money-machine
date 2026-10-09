"""Fixture-only notification dashboard phase of the Notion product build."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from money_machine.agents.implementations.notion_dashboard import build_dashboard_and_navigation
from money_machine.agents.implementations.notion_hubs import build_identity_specific_hubs
from money_machine.agents.implementations.notion_notifications import (
    SAMPLE_DATE,
    _ensure_sample_column,  # pyright: ignore[reportPrivateUsage]
    build_notification_dashboard,
    sample_field_values,
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
    NotionDatabase,
    NotionFormula,
    NotionPage,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from money_machine.integrations.notion.formulas import generate_notification_dashboard_formulas
from money_machine.integrations.notion.schema_builder import schema_definitions
from tests.fixtures.products import create_fixture_product_spec

ROOT = Path(__file__).parents[3]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
MODULE_PATH = ROOT / "src/money_machine/agents/implementations/notion_notifications.py"
WHEN = datetime(2026, 10, 3, 0, 30, tzinfo=UTC)
PHASE_TWO_AT = datetime(2026, 10, 5, 20, 0, tzinfo=UTC)
DASHBOARD_AT = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)
HUBS_AT = datetime(2026, 10, 5, 23, 45, tzinfo=UTC)
LATER = datetime(2026, 10, 6, 0, 30, tzinfo=UTC)
CLOSURE_SHA = "0f94d585f23d79e5ac18479f01e14f67cbaad332"
HEAD_SHA = "4b899fcf6bf09730b952bf5517d6bd691b72ba9a"
BOOTSTRAP_SHA = "1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d"
_PHASES = (
    PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
    PHASE_SHARED_DATABASES,
    PHASE_DASHBOARD_AND_NAVIGATION,
    "identity_specific_hubs",
    "notification_dashboard",
)
_MASS_CLAIMS = (
    "Buyer name",
    "current_date",
    "Tasks",
    "Events",
    "Finance",
    "Habits",
    "open_tasks_due_today",
    "birthday_status",
    "money_spent_today",
    "water_glasses_remaining",
)
_BUSINESS_OMITTED = (
    "Events",
    "Finance",
    "Habits",
    "birthday_status",
    "money_spent_today",
    "water_glasses_remaining",
    "client_name",
)


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
                source_reference="tests/unit/agents/test_notion_product_builder_notifications.py",
                observed_at=WHEN,
                safe_summary="Notification dashboard fixture spec",
            ),
        ),
        created_at=WHEN,
    )


async def _prepare(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=WHEN)
    await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)
    await build_dashboard_and_navigation(spec, probe, path, recorded_at=DASHBOARD_AT)
    await build_identity_specific_hubs(spec, probe, path, recorded_at=HUBS_AT)


async def _build(
    spec: ProductSpec,
    probe: FixtureNotionAdapter,
    path: Path,
    *,
    recorded_at: datetime = LATER,
) -> ProductBuildCheckpoint:
    return await build_notification_dashboard(spec, probe, path, recorded_at=recorded_at)


def _database(probe: FixtureNotionAdapter, title: str) -> NotionDatabase:
    return next(database for database in probe.databases.values() if database.title == title)


def _formula(database: NotionDatabase, name: str) -> NotionFormula:
    prop = next(item for item in database.properties if item.name == name)
    formula = prop.config["formula"]
    assert type(formula) is NotionFormula
    return formula


def _rows(probe: FixtureNotionAdapter, database_id: str) -> list[NotionPage]:
    return [
        page
        for page in probe.pages.values()
        if page.parent_id == database_id and page.parent_type == "database_id"
    ]


@pytest.mark.asyncio
async def test_mass_tier_builds_one_notification_row(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    blocks = {block.id for block in probe.blocks.values()}
    views = {view.id for view in probe.linked_views.values()}

    checkpoint = await _build(spec, probe, path)

    assert checkpoint.checkpoint_names == _PHASES
    assert checkpoint.next_phase == "aesthetics_and_content_completion"
    assert checkpoint.next_phase == BUILD_PHASES[5]
    assert checkpoint.recorded_at == LATER
    assert len(probe.databases) == len(PLANNER_SHARED_DATABASES) + 1
    assert len(probe.pages) == 12
    dashboard = _database(probe, "Notification dashboard")
    assert [prop.name for prop in dashboard.properties] == ["Name", *_MASS_CLAIMS]
    assert _formula(dashboard, "current_date").expression == "now()"
    assert _formula(_database(probe, "Tasks"), "current_date").expression == "now()"
    assert _formula(_database(probe, "Tasks"), "task_open_and_due_today").expression != ""
    rollups = {
        prop.name: prop.config["rollup"] for prop in dashboard.properties if prop.type == "rollup"
    }
    assert rollups["open_tasks_due_today"].function == "checked"
    assert rollups["birthday_status"].function == "checked"
    assert rollups["money_spent_today"].function == "sum"
    assert rollups["water_glasses_remaining"].function == "sum"
    assert (
        rollups["open_tasks_due_today"].rollup_property_id
        == _formula(_database(probe, "Tasks"), "task_open_and_due_today").id
    )
    rows = _rows(probe, dashboard.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.title == spec.identity
    assert row.properties["Name"] == spec.identity
    assert row.properties["Buyer name"] == spec.identity
    assert row.properties["Buyer name"] != "Buyer"
    assert "sample_marker" not in row.properties
    assert "client_name" not in row.properties
    assert "client_name" not in {prop.name for prop in dashboard.properties}
    for kind in ("Tasks", "Events", "Finance", "Habits"):
        samples = _rows(probe, _database(probe, kind).id)
        assert len(samples) == 1
        assert samples[0].title == f"SAMPLE {kind}"
        assert samples[0].properties == {
            **sample_field_values(kind),
            "sample_marker": "SAMPLE",
        }
        database = _database(probe, kind)
        assert database.properties[-1].name == "sample_marker"
        assert database.properties[-1].type == "select"
        assert database.properties[-1].config == {"options": ["SAMPLE"]}
        assert row.properties[kind] == samples[0].id
    for kind in ("Meals", "Notes"):
        assert _rows(probe, _database(probe, kind).id) == []
        assert all(prop.name != "sample_marker" for prop in _database(probe, kind).properties)
    assert {block.id for block in probe.blocks.values()} == blocks
    assert {view.id for view in probe.linked_views.values()} == views
    record = checkpoint.notification_dashboard
    assert record is not None
    assert record.database_id == dashboard.id
    assert record.row_page_id == row.id


@pytest.mark.asyncio
async def test_business_tier_omits_unsupported_claims(tmp_path: Path) -> None:
    spec = _spec(tier="business", identity="Studio Ledger", title="Studio Home", hub_name="Desk")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)

    await _build(spec, probe, path)

    assert len(probe.databases) == len(BUSINESS_SHARED_DATABASES) + 1
    assert len(probe.pages) == 9
    dashboard = _database(probe, "Notification dashboard")
    names = [prop.name for prop in dashboard.properties]
    assert names == ["Name", "Buyer name", "current_date", "Tasks", "open_tasks_due_today"]
    assert all(claim not in names for claim in _BUSINESS_OMITTED)
    assert _rows(probe, _database(probe, "Tasks").id)[0].title == "SAMPLE Tasks"
    tasks = _database(probe, "Tasks")
    assert tasks.properties[-1].name == "sample_marker"
    assert _rows(probe, tasks.id)[0].properties["Name"] == "SAMPLE Tasks"
    assert _rows(probe, tasks.id)[0].properties["Status"] == "Open"
    assert _rows(probe, tasks.id)[0].properties["Due"] == SAMPLE_DATE
    for kind in ("Clients", "Projects", "Content", "Invoices", "Notes"):
        assert _rows(probe, _database(probe, kind).id) == []
        assert all(prop.name != "sample_marker" for prop in _database(probe, kind).properties)
    row = _rows(probe, dashboard.id)[0]
    assert row.properties["Name"] == "Studio Ledger"
    assert row.properties["Buyer name"] == "Studio Ledger"
    assert "client_name" not in row.properties


@pytest.mark.asyncio
async def test_replay_keeps_the_same_checkpoint_bytes_and_ids(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await _build(spec, probe, path)
    before = path.read_bytes()
    pages = set(probe.pages)
    databases = set(probe.databases)
    formula_id = _formula(_database(probe, "Tasks"), "current_date").id

    again = await _build(spec, probe, path, recorded_at=datetime(2026, 10, 6, 1, tzinfo=UTC))

    assert set(probe.pages) == pages
    assert set(probe.databases) == databases
    assert _formula(_database(probe, "Tasks"), "current_date").id == formula_id
    assert again == checkpoint
    assert path.read_bytes() == before
    assert len(_rows(probe, _database(probe, "Notification dashboard").id)) == 1


@pytest.mark.asyncio
async def test_missing_checkpoint_creates_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "missing.json"

    with pytest.raises(ProductBuildError, match="identity hubs"):
        await _build(spec, probe, path)

    assert path.exists() is False
    assert probe.pages == {}
    assert probe.databases == {}


@pytest.mark.asyncio
async def test_dashboard_checkpoint_is_not_enough(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=WHEN)
    await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)
    await build_dashboard_and_navigation(spec, probe, path, recorded_at=DASHBOARD_AT)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="identity hubs"):
        await _build(spec, probe, path)

    assert path.read_bytes() == before
    assert len(probe.pages) == 1
    assert "Notification dashboard" not in {database.title for database in probe.databases.values()}


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
    pages = set(probe.pages)

    with pytest.raises(ProductBuildError, match="is missing"):
        await _build(spec, probe, path)

    assert shell_id not in probe.blocks
    assert set(probe.pages) == pages
    assert path.read_bytes() == before
    assert "Notification dashboard" not in {database.title for database in probe.databases.values()}


@pytest.mark.asyncio
async def test_tampered_design_shell_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    shell_id = payload["provider_object_references"]["design_shell_block_id"]
    probe.blocks[shell_id].content = "tampered shell"
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="does not match"):
        await _build(spec, probe, path)

    assert probe.blocks[shell_id].content == "tampered shell"
    assert path.read_bytes() == before
    assert "Notification dashboard" not in {database.title for database in probe.databases.values()}


@pytest.mark.asyncio
async def test_deleted_sample_on_resume_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    checkpoint = await _build(spec, probe, path)
    assert checkpoint.notification_dashboard is not None
    sample_id = checkpoint.notification_dashboard.samples[0][1]
    del probe.pages[sample_id]
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="notification sample"):
        await _build(spec, probe, path, recorded_at=datetime(2026, 10, 6, 2, tzinfo=UTC))

    assert sample_id not in probe.pages
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_deleted_formula_on_resume_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    tasks = _database(probe, "Tasks")
    formula_id = _formula(tasks, "current_date").id
    tasks.properties = [prop for prop in tasks.properties if prop.id != formula_id]
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="notification formula"):
        await _build(spec, probe, path)

    assert all(prop.id != formula_id for prop in _database(probe, "Tasks").properties)
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_existing_formulas_are_adopted(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    tasks = _database(probe, "Tasks")
    definitions = schema_definitions()
    verified = {
        kind: {prop.name: prop.type for prop in definitions[kind].properties}
        for kind in PLANNER_SHARED_DATABASES
    }
    generated = generate_notification_dashboard_formulas(verified)
    created: list[str] = []
    for name, expression in generated.expressions.items():
        if generated.databases[name] != "Tasks":
            continue
        formula = await probe.create_formula(tasks.id, name, expression)
        created.append(formula.id)

    await _build(spec, probe, path)

    ids = [prop.id for prop in _database(probe, "Tasks").properties if prop.type == "formula"]
    assert ids == created
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_junk_property_creates_no_notification_database(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    tasks = _database(probe, "Tasks")
    await probe.add_property(tasks.id, "Junk", "text", {})
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="notification formula"):
        await _build(spec, probe, path)

    assert path.read_bytes() == before
    assert "Notification dashboard" not in {database.title for database in probe.databases.values()}
    assert len(probe.pages) == 7


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
        await build_notification_dashboard(
            create_fixture_product_spec(), probe, path, recorded_at=LATER
        )
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_notification_dashboard(spec, SubclassProbe(), path, recorded_at=LATER)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_notification_dashboard(spec, APINotionAdapter(), path, recorded_at=LATER)

    assert path.read_bytes() == before
    assert "Notification dashboard" not in {database.title for database in probe.databases.values()}


@pytest.mark.asyncio
async def test_earlier_phases_do_not_run_again(tmp_path: Path) -> None:
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
    with pytest.raises(ProductBuildError):
        await build_identity_specific_hubs(spec, probe, path, recorded_at=LATER)

    assert set(probe.pages) == pages
    assert set(probe.databases) == databases


def test_notification_module_does_not_name_a_live_client() -> None:
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
        "aesthetics_and_content_completion",
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
    pages = set(probe.pages)

    with pytest.raises(ProductBuildError, match="does not match"):
        await _build(spec, probe, path)

    assert shell.icon == "💡"
    assert set(probe.pages) == pages
    assert path.read_bytes() == before
    assert "Notification dashboard" not in {database.title for database in probe.databases.values()}


@pytest.mark.asyncio
async def test_formula_prefix_is_completed_and_keeps_the_first_id(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    tasks = _database(probe, "Tasks")
    definitions = schema_definitions()
    verified = {
        kind: {prop.name: prop.type for prop in definitions[kind].properties}
        for kind in PLANNER_SHARED_DATABASES
    }
    generated = generate_notification_dashboard_formulas(verified)
    first_name = next(name for name, database in generated.databases.items() if database == "Tasks")
    formula = await probe.create_formula(tasks.id, first_name, generated.expressions[first_name])

    await _build(spec, probe, path)

    formulas = [prop for prop in _database(probe, "Tasks").properties if prop.type == "formula"]
    assert formulas[0].id == formula.id
    assert len(formulas) == 2
    assert _database(probe, "Tasks").properties[-1].name == "sample_marker"


@pytest.mark.asyncio
async def test_non_prefix_formula_is_not_repaired(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    tasks = _database(probe, "Tasks")
    definitions = schema_definitions()
    verified = {
        kind: {prop.name: prop.type for prop in definitions[kind].properties}
        for kind in PLANNER_SHARED_DATABASES
    }
    generated = generate_notification_dashboard_formulas(verified)
    names = [name for name, database in generated.databases.items() if database == "Tasks"]
    await probe.create_formula(tasks.id, names[1], generated.expressions[names[1]])
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="notification formula"):
        await _build(spec, probe, path)

    assert path.read_bytes() == before
    assert "Notification dashboard" not in {database.title for database in probe.databases.values()}


@pytest.mark.asyncio
async def test_notification_database_prefix_is_repaired_in_place(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    page = next(item for item in probe.pages.values() if item.parent_type == "workspace")
    database = await probe.create_database(
        title="Notification dashboard", parent_id=page.id, parent_type="page_id"
    )
    await probe.add_property(database.id, "Name", "title", {})

    await _build(spec, probe, path)

    found = _database(probe, "Notification dashboard")
    assert found.id == database.id
    assert [prop.name for prop in found.properties] == ["Name", *_MASS_CLAIMS]


@pytest.mark.asyncio
async def test_notification_database_junk_cannot_be_repaired(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    page = next(item for item in probe.pages.values() if item.parent_type == "workspace")
    database = await probe.create_database(
        title="Notification dashboard", parent_id=page.id, parent_type="page_id"
    )
    await probe.add_property(database.id, "Name", "text", {})
    before = path.read_bytes()
    pages = set(probe.pages)

    with pytest.raises(ProductBuildError, match="cannot be repaired"):
        await _build(spec, probe, path)

    assert path.read_bytes() == before
    assert set(probe.pages) == pages
    assert _database(probe, "Notification dashboard").id == database.id
    assert [prop.name for prop in database.properties] == ["Name"]


@pytest.mark.asyncio
async def test_missing_sample_values_are_filled_and_wrong_values_are_not(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    tasks = _database(probe, "Tasks")
    page = await probe.create_page("SAMPLE Tasks", parent_id=tasks.id, parent_type="database_id")

    await _build(spec, probe, path)

    assert page.properties["Name"] == "SAMPLE Tasks"
    assert page.properties["Status"] == "Open"
    assert page.properties["Due"] == SAMPLE_DATE
    assert page.properties["sample_marker"] == "SAMPLE"
    assert _rows(probe, tasks.id) == [page]

    fresh = FixtureNotionAdapter()
    fresh_path = tmp_path / "fresh.json"
    await _prepare(spec, fresh, fresh_path)
    events = _database(fresh, "Events")
    bad = await fresh.create_page("SAMPLE Events", parent_id=events.id, parent_type="database_id")
    bad.properties["Name"] = "SAMPLE Events"
    bad.properties["Date"] = SAMPLE_DATE
    bad.properties["Birthday"] = False
    before = fresh_path.read_bytes()

    with pytest.raises(ProductBuildError, match="notification sample does not match"):
        await _build(spec, fresh, fresh_path)

    assert bad.properties["Birthday"] is False
    assert fresh_path.read_bytes() == before
    assert "Notification dashboard" not in {item.title for item in fresh.databases.values()}


@pytest.mark.asyncio
async def test_buyer_name_placeholder_is_rejected_on_resume(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    row = _rows(probe, _database(probe, "Notification dashboard").id)[0]
    row.properties["Buyer name"] = "Buyer"
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="notification row"):
        await _build(spec, probe, path)

    assert row.properties["Buyer name"] == "Buyer"
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_buyer_name_placeholder_on_an_existing_row_is_not_overwritten(
    tmp_path: Path,
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    page = next(item for item in probe.pages.values() if item.parent_type == "workspace")
    database = await probe.create_database(
        title="Notification dashboard", parent_id=page.id, parent_type="page_id"
    )
    await probe.add_property(database.id, "Name", "title", {})
    await probe.add_property(database.id, "Buyer name", "text", {})
    row = await probe.create_page(spec.identity, parent_id=database.id, parent_type="database_id")
    row.properties["Name"] = spec.identity
    row.properties["Buyer name"] = "Buyer"
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="notification row"):
        await _build(spec, probe, path)

    assert row.properties["Buyer name"] == "Buyer"
    assert row.properties["Name"] == spec.identity
    assert path.read_bytes() == before
    assert _database(probe, "Notification dashboard").id == database.id


@pytest.mark.asyncio
async def test_sample_marker_not_last_is_rejected_on_resume(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    tasks = _database(probe, "Tasks")
    assert tasks.properties[-1].name == "sample_marker"
    tasks.properties[-1], tasks.properties[-2] = tasks.properties[-2], tasks.properties[-1]
    assert tasks.properties[-1].name != "sample_marker"
    before = path.read_bytes()
    pages = set(probe.pages)

    with pytest.raises(ProductBuildError, match="checkpoint shared database is missing"):
        await _build(spec, probe, path)

    assert path.read_bytes() == before
    assert set(probe.pages) == pages
    assert tasks.properties[-1].name != "sample_marker"


@pytest.mark.asyncio
async def test_sample_marker_column_is_moved_to_the_end() -> None:
    probe = FixtureNotionAdapter()
    database = await probe.create_database(
        title="Tasks", parent_id="ws_default", parent_type="workspace"
    )
    await probe.add_property(database.id, "sample_marker", "select", {"options": ["SAMPLE"]})
    await probe.add_property(database.id, "Name", "title", {})
    assert database.properties[-1].name == "Name"

    await _ensure_sample_column(probe, database.id)

    assert database.properties[-1].name == "sample_marker"


@pytest.mark.asyncio
async def test_notification_checkpoint_parser_rejects_bad_inputs(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    await _build(spec, probe, path)
    pages = set(probe.pages)
    original = path.read_text(encoding="ascii")
    path.write_text("{\n", encoding="utf-8")

    with pytest.raises(ProductBuildError, match="not JSON"):
        await _build(spec, probe, path)

    payload = json.loads(original)
    payload["provider_object_references"]["notification_dashboard"] = {"database_id": "x"}
    payload = stamp_integrity_digest(payload)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii"
    )

    with pytest.raises(ProductBuildError, match="missing or unsupported"):
        await _build(spec, probe, path)

    assert set(probe.pages) == pages


@pytest.mark.asyncio
async def test_ensure_row_rejects_client_name_on_an_adopted_database(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    hubs = path.read_bytes()
    await _build(spec, probe, path)
    database = _database(probe, "Notification dashboard")
    row = _rows(probe, database.id)
    assert len(row) == 1
    row[0].properties["client_name"] = spec.identity
    path.write_bytes(hubs)

    with pytest.raises(ProductBuildError, match="notification row does not match"):
        await _build(spec, probe, path)

    assert path.read_bytes() == hubs
    assert row[0].properties["client_name"] == spec.identity


@pytest.mark.asyncio
async def test_adopted_database_rejects_a_text_title(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _prepare(spec, probe, path)
    hubs = path.read_bytes()
    await _build(spec, probe, path)
    database = _database(probe, "Notification dashboard")
    database.properties[0].type = "text"
    path.write_bytes(hubs)

    with pytest.raises(ProductBuildError, match="cannot be repaired"):
        await _build(spec, probe, path)

    assert path.read_bytes() == hubs
    assert database.properties[0].type == "text"


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
    assert evidence["notification_dashboard_built"] is False
    assert state["state_revision"] == 59
    assert "SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE" not in STATE_PATH.read_text(encoding="utf-8")
