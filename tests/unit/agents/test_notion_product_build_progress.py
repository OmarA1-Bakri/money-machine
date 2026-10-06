"""Progress record, repair jobs, and the wave-7 killing tests.

Fixture only. A provider failure stores kind provider_response. Resume continues
from the failed operation. An unrecoverable phase-1-only record is rebuilt in
place. Later-phase objects refuse that rebuild: zero adapter writes, one
write_checkpoint, one rebuild_refused job, and a recomputed integrity digest.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from money_machine.agents.implementations import notion_notifications as notification_module
from money_machine.agents.implementations.notion_aesthetics import (
    build_aesthetics_and_content_completion,
)
from money_machine.agents.implementations.notion_dashboard import build_dashboard_and_navigation
from money_machine.agents.implementations.notion_hubs import build_identity_specific_hubs
from money_machine.agents.implementations.notion_notifications import (
    NOTIFICATION_COVER,
    NOTIFICATION_ICON,
    build_notification_dashboard,
)
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
    ProductBuildError,
    build_top_level_page_and_design_shell,
)
from money_machine.agents.implementations.notion_progress import (
    OP_AESTHETICS_SAMPLES,
    OP_DASHBOARD_COVER,
    OP_HUBS_CREATE,
    OP_NOTIFICATION_DATABASE,
    OP_PHASE1_PAGE,
    OP_PHASE1_SHELL,
    OP_REBUILD,
    PHASES,
    REBUILD_REFUSED,
    RECOVERY_RULE,
    record_provider_failure,
    shared_create_operation,
    stamp_integrity_digest,
)
from money_machine.agents.implementations.notion_shared_databases import build_shared_databases
from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.product_spec import ColourToken, Hub, ProductSpec
from money_machine.integrations.notion.domain import (
    NotionCalloutBlock,
    NotionDatabase,
    NotionPage,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter

WHEN = datetime(2026, 10, 3, 0, 30, tzinfo=UTC)
PHASE_TWO_AT = datetime(2026, 10, 5, 20, 0, tzinfo=UTC)
DASHBOARD_AT = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)
HUBS_AT = datetime(2026, 10, 5, 23, 45, tzinfo=UTC)
NOTIFICATION_AT = datetime(2026, 10, 6, 0, 30, tzinfo=UTC)
LATER = datetime(2026, 10, 6, 1, 30, tzinfo=UTC)
_WRITE_METHODS = (
    "create_page",
    "add_text_block",
    "add_callout_block",
    "create_database",
    "add_property",
    "create_relation",
    "create_rollup",
    "create_formula",
    "create_linked_view",
    "set_icon",
    "set_cover",
    "add_child_page",
    "publish_page",
)


def _spec(*, tier: str = "mass", identity: str = "Weekly Planner") -> ProductSpec:
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
        title="Home Dashboard Planner",
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
            Hub(name=f"Hub {index}", description=f"{identity} copy {index}", page_count=3)
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
                source_reference="tests/unit/agents/test_notion_product_build_progress.py",
                observed_at=WHEN,
                safe_summary="Progress fixture spec",
            ),
        ),
        created_at=WHEN,
    )


def _block_ids(probe: FixtureNotionAdapter) -> set[str]:
    return {block.id for block in probe.blocks.values()}


def _database_ids(probe: FixtureNotionAdapter) -> set[str]:
    return {database.id for database in probe.databases.values()}


def _page_ids(probe: FixtureNotionAdapter) -> set[str]:
    return {page.id for page in probe.pages.values() if type(page) is NotionPage}


def _home(probe: FixtureNotionAdapter) -> NotionPage:
    return next(page for page in probe.pages.values() if page.parent_type == "workspace")


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


def _job(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="ascii"))
    jobs = payload["progress"]["repair_jobs"]
    assert type(jobs) is list and jobs
    job = jobs[-1]
    assert type(job) is dict
    return job


def _assert_job(path: Path, operation: str, response: str) -> None:
    job = _job(path)
    assert job["kind"] == "provider_response"
    assert job["operation"] == operation
    assert job["response"] == response


def _resign(path: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    payload = json.loads(path.read_text(encoding="ascii"))
    progress = payload["progress"]
    assert type(progress) is dict
    body = {key: value for key, value in progress.items() if key != "record_digest"}
    mutate(body)
    payload["progress"] = body
    stamped = stamp_integrity_digest(payload)
    path.write_text(
        json.dumps(stamped, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )


async def _phase_one(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=WHEN)


async def _through_shared(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await _phase_one(spec, probe, path)
    await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)


async def _through_dashboard(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await _through_shared(spec, probe, path)
    await build_dashboard_and_navigation(spec, probe, path, recorded_at=DASHBOARD_AT)


async def _through_hubs(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await _through_dashboard(spec, probe, path)
    await build_identity_specific_hubs(spec, probe, path, recorded_at=HUBS_AT)


async def _through_notification(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await _through_hubs(spec, probe, path)
    await build_notification_dashboard(spec, probe, path, recorded_at=NOTIFICATION_AT)


def test_progress_phases_match_the_build_phases() -> None:
    assert PHASES == BUILD_PHASES
    assert "provider_response" in RECOVERY_RULE
    assert "unrecoverable" in RECOVERY_RULE


@pytest.mark.asyncio
async def test_phase1_page_failure_resumes_without_rebuilding_prior_ids(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    probe.fail_operation = OP_PHASE1_PAGE  # type: ignore[attr-defined]
    probe.fail_response = "page refused"  # type: ignore[attr-defined]

    with pytest.raises(ProductBuildError, match="page refused"):
        await _phase_one(spec, probe, path)

    assert not path.exists()
    assert _page_ids(probe) == set()
    assert _block_ids(probe) == set()
    assert _database_ids(probe) == set()
    del probe.fail_operation  # type: ignore[attr-defined]

    await _phase_one(spec, probe, path)

    assert len(_page_ids(probe)) == 1
    assert len(_block_ids(probe)) == 1
    assert _database_ids(probe) == set()
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["progress"]["repair_jobs"] == []
    assert stored["checkpoint_names"] == [PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL]


@pytest.mark.asyncio
async def test_phase1_shell_failure_keeps_the_page_and_adds_one_block(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    probe.fail_operation = OP_PHASE1_SHELL  # type: ignore[attr-defined]
    probe.fail_response = "shell refused"  # type: ignore[attr-defined]

    with pytest.raises(ProductBuildError, match="shell refused"):
        await _phase_one(spec, probe, path)

    assert not path.exists()
    page_ids = _page_ids(probe)
    assert len(page_ids) == 1
    assert _block_ids(probe) == set()
    del probe.fail_operation  # type: ignore[attr-defined]
    await _phase_one(spec, probe, path)
    assert _page_ids(probe) == page_ids
    assert len(_block_ids(probe)) == 1
    assert _database_ids(probe) == set()


@pytest.mark.asyncio
async def test_shared_database_failure_resumes_from_the_failed_kind(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    before_blocks = _block_ids(probe)
    before_databases = _database_ids(probe)
    operation = shared_create_operation("Events")
    probe.fail_operation = operation  # type: ignore[attr-defined]
    probe.fail_response = "events refused"  # type: ignore[attr-defined]

    with pytest.raises(ProductBuildError, match="events refused"):
        await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)

    _assert_job(path, operation, "events refused")
    assert _block_ids(probe) == before_blocks
    created = _database_ids(probe) - before_databases
    assert len(created) == 1
    tasks_id = next(iter(created))
    del probe.fail_operation  # type: ignore[attr-defined]
    await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)
    assert tasks_id in _database_ids(probe)
    assert len(_database_ids(probe) - before_databases) == 6
    assert _block_ids(probe) == before_blocks


@pytest.mark.asyncio
async def test_dashboard_failure_adds_only_the_dashboard_blocks(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_shared(spec, probe, path)
    before_blocks = _block_ids(probe)
    before_databases = _database_ids(probe)
    probe.fail_operation = OP_DASHBOARD_COVER  # type: ignore[attr-defined]
    probe.fail_response = "cover refused"  # type: ignore[attr-defined]

    with pytest.raises(ProductBuildError, match="cover refused"):
        await build_dashboard_and_navigation(spec, probe, path, recorded_at=DASHBOARD_AT)

    _assert_job(path, OP_DASHBOARD_COVER, "cover refused")
    greeting = _block_ids(probe) - before_blocks
    assert len(greeting) == 1
    assert _database_ids(probe) == before_databases
    del probe.fail_operation  # type: ignore[attr-defined]
    await build_dashboard_and_navigation(spec, probe, path, recorded_at=DASHBOARD_AT)
    assert greeting < _block_ids(probe)
    assert len(_block_ids(probe) - before_blocks) == 4
    assert _database_ids(probe) == before_databases


@pytest.mark.asyncio
async def test_hub_failure_adds_only_the_hub_pages_and_blocks(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_dashboard(spec, probe, path)
    before_blocks = _block_ids(probe)
    before_databases = _database_ids(probe)
    before_pages = _page_ids(probe)
    probe.fail_operation = OP_HUBS_CREATE  # type: ignore[attr-defined]
    probe.fail_response = "hubs refused"  # type: ignore[attr-defined]

    with pytest.raises(ProductBuildError, match="hubs refused"):
        await build_identity_specific_hubs(spec, probe, path, recorded_at=HUBS_AT)

    _assert_job(path, OP_HUBS_CREATE, "hubs refused")
    created_pages = _page_ids(probe) - before_pages
    assert len(created_pages) == 1
    assert _block_ids(probe) == before_blocks
    assert _database_ids(probe) == before_databases
    del probe.fail_operation  # type: ignore[attr-defined]
    await build_identity_specific_hubs(spec, probe, path, recorded_at=HUBS_AT)
    assert created_pages < _page_ids(probe)
    assert before_blocks < _block_ids(probe)
    assert len(_block_ids(probe) - before_blocks) == 24
    assert len(_page_ids(probe) - before_pages) == 6
    assert _database_ids(probe) == before_databases


@pytest.mark.asyncio
async def test_notification_failure_adds_one_database_and_no_blocks(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_hubs(spec, probe, path)
    before_blocks = _block_ids(probe)
    before_databases = _database_ids(probe)
    before_pages = _page_ids(probe)
    before_properties = {
        database_id: tuple(prop.name for prop in probe.databases[database_id].properties)
        for database_id in before_databases
    }
    probe.fail_operation = OP_NOTIFICATION_DATABASE  # type: ignore[attr-defined]
    probe.fail_response = "notice refused"  # type: ignore[attr-defined]

    with pytest.raises(ProductBuildError, match="notice refused"):
        await build_notification_dashboard(spec, probe, path, recorded_at=NOTIFICATION_AT)

    _assert_job(path, OP_NOTIFICATION_DATABASE, "notice refused")
    created = _database_ids(probe) - before_databases
    assert len(created) == 1
    notice_id = next(iter(created))
    assert _block_ids(probe) == before_blocks
    assert _page_ids(probe) == before_pages
    for database_id, names in before_properties.items():
        current = probe.databases[database_id].properties
        assert tuple(prop.name for prop in current[: len(names)]) == names
        added = current[len(names) :]
        assert all(prop.type == "formula" for prop in added)
        assert all(prop.name != "sample_marker" for prop in added)
    del probe.fail_operation  # type: ignore[attr-defined]
    await build_notification_dashboard(spec, probe, path, recorded_at=NOTIFICATION_AT)
    assert notice_id in _database_ids(probe)
    assert _block_ids(probe) == before_blocks
    assert len(_database_ids(probe) - before_databases) == 1
    assert before_databases < _database_ids(probe)
    assert before_pages < _page_ids(probe)
    tasks = next(database for database in probe.databases.values() if database.title == "Tasks")
    assert tasks.properties[-1].name == "sample_marker"


@pytest.mark.asyncio
async def test_aesthetics_failure_resumes_samples_without_new_accents(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_notification(spec, probe, path)
    before_blocks = _block_ids(probe)
    before_databases = _database_ids(probe)
    probe.fail_operation = OP_AESTHETICS_SAMPLES  # type: ignore[attr-defined]
    probe.fail_response = "samples refused"  # type: ignore[attr-defined]

    with pytest.raises(ProductBuildError, match="samples refused"):
        await build_aesthetics_and_content_completion(spec, probe, path, recorded_at=LATER)

    _assert_job(path, OP_AESTHETICS_SAMPLES, "samples refused")
    accents = _block_ids(probe) - before_blocks
    assert len(accents) == len(spec.palette_tokens)
    assert _database_ids(probe) == before_databases
    del probe.fail_operation  # type: ignore[attr-defined]
    await build_aesthetics_and_content_completion(spec, probe, path, recorded_at=LATER)
    assert accents < _block_ids(probe)
    assert len(_block_ids(probe) - before_blocks - accents) == len(spec.hubs)
    assert _database_ids(probe) == before_databases


@pytest.mark.asyncio
async def test_forged_and_tampered_progress_records_are_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    pages = _page_ids(probe)
    original = path.read_bytes()
    payload = json.loads(original)
    payload["progress"]["record_digest"] = "0" * 64
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    forged = path.read_bytes()

    with pytest.raises(ProductBuildError, match="forged"):
        await _phase_one(spec, probe, path)

    assert path.read_bytes() == forged
    assert _page_ids(probe) == pages
    path.write_bytes(original)
    payload = json.loads(original)
    payload["progress"]["extra"] = "nope"
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii"
    )
    tampered = path.read_bytes()

    with pytest.raises(ProductBuildError, match="tampered"):
        await _phase_one(spec, probe, path)

    assert path.read_bytes() == tampered
    assert _page_ids(probe) == pages


@pytest.mark.asyncio
async def test_screenshot_kind_is_forged(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)

    def _screenshot(body: dict[str, object]) -> None:
        body["repair_jobs"] = [
            {
                "kind": "screenshot",
                "operation": OP_PHASE1_PAGE,
                "phase": PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
                "response": "png",
            }
        ]

    _resign(path, _screenshot)
    before = path.read_bytes()
    pages = len(probe.pages)

    with pytest.raises(ProductBuildError, match="forged"):
        await _phase_one(spec, probe, path)

    assert path.read_bytes() == before
    assert len(probe.pages) == pages


def _mark_unrecoverable(path: Path) -> None:
    _resign(path, lambda body: body.__setitem__("recovery", "unrecoverable"))


def _workspace_pages(probe: FixtureNotionAdapter) -> list[NotionPage]:
    return [
        page
        for page in probe.pages.values()
        if type(page) is NotionPage and page.parent_type == "workspace"
    ]


async def _through_aesthetics(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await _through_notification(spec, probe, path)
    await build_aesthetics_and_content_completion(spec, probe, path, recorded_at=LATER)


def _assert_refused_diff(before: dict[str, object], after: dict[str, object]) -> None:
    """The appended rebuild_refused job and the recomputed digest are the only differences.

    The integrity digest covers the whole payload, so appending a job recomputes it.
    That recomputed digest is the only permitted difference besides the new job.
    """
    assert set(before) == set(after)
    for key, value in before.items():
        if key != "progress":
            assert after[key] == value
    before_progress = before["progress"]
    after_progress = after["progress"]
    assert type(before_progress) is dict and type(after_progress) is dict
    assert set(before_progress) == set(after_progress)
    for key, value in before_progress.items():
        if key in {"repair_jobs", "record_digest"}:
            continue
        assert after_progress[key] == value
    assert after_progress["record_digest"] != before_progress["record_digest"]
    before_jobs = before_progress["repair_jobs"]
    after_jobs = after_progress["repair_jobs"]
    assert type(before_jobs) is list and type(after_jobs) is list
    assert after_jobs[:-1] == before_jobs
    job = after_jobs[-1]
    assert type(job) is dict
    assert job["kind"] == REBUILD_REFUSED
    assert job["operation"] == OP_REBUILD
    response = job["response"]
    assert type(response) is str and response.startswith("rebuild refused:")


@pytest.mark.asyncio
async def test_unrecoverable_phase1_rebuilds_in_place_and_later_phases_do_not(
    tmp_path: Path,
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    old_page = _home(probe)
    markers = dict(old_page.properties)
    _mark_unrecoverable(path)

    await _phase_one(spec, probe, path)

    assert _workspace_pages(probe) == [old_page]
    assert len(probe.pages) == 1
    assert old_page.properties["product_spec_id"] == markers["product_spec_id"]
    assert old_page.properties["product_id"] == markers["product_id"]
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["progress"]["recovery"] == "recoverable"
    assert stored["checkpoint_names"] == [PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL]
    assert len(probe.blocks) == 1

    await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)
    databases = _database_ids(probe)
    _mark_unrecoverable(path)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="unrecoverable"):
        await build_shared_databases(spec, probe, path, recorded_at=LATER)

    assert path.read_bytes() == before
    assert _database_ids(probe) == databases


@pytest.mark.asyncio
async def test_refused_rebuild_appends_one_job_and_writes_no_fixture_objects(
    tmp_path: Path,
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_aesthetics(spec, probe, path)
    page = _home(probe)
    markers = dict(page.properties)
    icon, cover = page.icon, page.cover
    blocks = _block_ids(probe)
    _mark_unrecoverable(path)
    before = json.loads(path.read_text(encoding="ascii"))
    counts = (len(probe.pages), len(probe.databases), len(probe.blocks))
    calls = _watch(probe)

    with pytest.raises(ProductBuildError, match="rebuild refused"):
        await _phase_one(spec, probe, path)

    assert calls == []
    assert (len(probe.pages), len(probe.databases), len(probe.blocks)) == counts
    assert _block_ids(probe) == blocks
    assert page.properties == markers
    assert page.icon == icon
    assert page.cover == cover
    after = json.loads(path.read_text(encoding="ascii"))
    _assert_refused_diff(before, after)
    response = after["progress"]["repair_jobs"][-1]["response"]
    for name in ("Tasks", "Notification dashboard", "Hub 1", "dashboard icon", "dashboard cover"):
        assert name in response

    stable = path.read_bytes()
    for build in (
        build_shared_databases,
        build_dashboard_and_navigation,
        build_identity_specific_hubs,
        build_notification_dashboard,
        build_aesthetics_and_content_completion,
    ):
        with pytest.raises(ProductBuildError, match="unrecoverable"):
            await build(spec, probe, path, recorded_at=LATER)
        assert path.read_bytes() == stable
        assert (len(probe.pages), len(probe.databases), len(probe.blocks)) == counts


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tier", "identity", "catalogue"),
    [
        ("mass", "Weekly Planner", ("Tasks", "Events", "Habits", "Finance", "Meals", "Notes")),
        (
            "business",
            "Studio Ledger",
            ("Clients", "Projects", "Content", "Invoices", "Tasks", "Notes"),
        ),
    ],
)
async def test_phase1_only_rebuild_continues_through_phase_6(
    tmp_path: Path, tier: str, identity: str, catalogue: tuple[str, ...]
) -> None:
    spec = _spec(tier=tier, identity=identity)
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    home = _home(probe)
    _mark_unrecoverable(path)

    await _through_aesthetics(spec, probe, path)

    assert _workspace_pages(probe) == [home]
    titles = [database.title for database in probe.databases.values()]
    assert sorted(titles) == sorted([*catalogue, "Notification dashboard"])
    assert titles.count("Tasks") == 1
    assert titles.count("Notification dashboard") == 1
    stored = json.loads(path.read_text(encoding="ascii"))
    progress = stored["progress"]
    assert progress["page_counts"]["databases"] == len(catalogue) + 1
    assert progress["page_counts"]["pages"] > 1
    assert progress["page_counts"]["blocks"] > 1
    assert progress["property_mappings"]["product_spec_id"] == "product_spec_id"
    assert progress["property_mappings"]["buyer_name"] == "Buyer name"
    assert progress["formula_state"]
    assert {entry["kind"] for entry in progress["formula_state"]}
    created = progress["created_notion_ids"]
    _assert_created_ids(created, probe, home)
    pages = _page_ids(probe)
    databases = _database_ids(probe)

    await build_aesthetics_and_content_completion(spec, probe, path, recorded_at=LATER)

    assert _page_ids(probe) == pages
    assert _database_ids(probe) == databases
    resumed = json.loads(path.read_text(encoding="ascii"))["progress"]["created_notion_ids"]
    assert resumed == created
    assert {row["database_id"] for row in resumed["databases"]} <= databases
    assert {hub["page_id"] for hub in resumed["hubs"]} <= pages
    assert resumed["top_level_page_id"] in pages


def _assert_created_ids(created: object, probe: FixtureNotionAdapter, home: NotionPage) -> None:
    """Persisted created ids match the probe, including databases, hubs, and the whole field."""
    assert type(created) is dict
    databases = created["databases"]
    hubs = created["hubs"]
    assert type(databases) is list and type(hubs) is list
    catalogue = {
        (database.title, database.id)
        for database in probe.databases.values()
        if type(database) is NotionDatabase and database.title != "Notification dashboard"
    }
    assert {(row["kind"], row["database_id"]) for row in databases} == catalogue
    children = {
        (page.title, page.id)
        for page in probe.pages.values()
        if type(page) is NotionPage and page.parent_type == "page_id" and page.parent_id == home.id
    }
    assert {(hub["name"], hub["page_id"]) for hub in hubs} == children
    notice = next(
        database
        for database in probe.databases.values()
        if type(database) is NotionDatabase and database.title == "Notification dashboard"
    )
    notification = created["notification"]
    aesthetics = created["aesthetics"]
    assert type(notification) is dict and type(aesthetics) is dict
    assert notification["database_id"] == notice.id
    assert notice.id in probe.databases
    shell_id = home.properties["design_shell_block_id"]
    assert type(shell_id) is str
    assert created["top_level_page_id"] == home.id
    assert created["workspace_id"] == home.parent_id
    assert created["design_shell_block_id"] == shell_id
    assert home.id in probe.pages
    assert shell_id in probe.blocks
    for row in aesthetics["accents"]:
        assert row["block_id"] in probe.blocks
    for row in aesthetics["samples"]:
        assert row["block_id"] in probe.blocks
    dashboard = created["dashboard"]
    assert type(dashboard) is list and dashboard
    live_values = set(probe.blocks) | set(probe.linked_views)
    for page in probe.pages.values():
        if page.icon is not None:
            live_values.add(page.icon)
        if page.cover is not None:
            live_values.add(page.cover)
    for piece in dashboard:
        assert piece["value"] in live_values


def test_write_checkpoint_is_the_only_progress_writer() -> None:
    root = Path(__file__).resolve().parents[3] / "src/money_machine/agents/implementations"
    calls = [
        (path.name, line.strip())
        for path in sorted(root.glob("*.py"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if "write_document(" in line
    ]
    assert calls == [
        ("notion_progress.py", "def write_document("),
        ("notion_progress_record.py", "write_document(path, payload, body)"),
    ]


@pytest.mark.asyncio
async def test_phase1_rebuild_failure_records_a_repair_job(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    pages = _page_ids(probe)
    blocks = _block_ids(probe)
    databases = _database_ids(probe)
    _mark_unrecoverable(path)
    before = json.loads(path.read_text(encoding="ascii"))
    probe.fail_operation = OP_REBUILD  # type: ignore[attr-defined]
    probe.fail_response = "rebuild provider refused"  # type: ignore[attr-defined]

    with pytest.raises(ProductBuildError, match="rebuild provider refused"):
        await _phase_one(spec, probe, path)

    assert _page_ids(probe) == pages
    assert _block_ids(probe) == blocks
    assert _database_ids(probe) == databases
    after = json.loads(path.read_text(encoding="ascii"))
    assert set(before) == set(after)
    for key, value in before.items():
        if key != "progress":
            assert after[key] == value
    before_progress = before["progress"]
    after_progress = after["progress"]
    assert type(before_progress) is dict and type(after_progress) is dict
    for key, value in before_progress.items():
        if key in {"repair_jobs", "record_digest"}:
            continue
        assert after_progress[key] == value
    assert after_progress["recovery"] == "unrecoverable"
    assert after_progress["record_digest"] != before_progress["record_digest"]
    jobs = after_progress["repair_jobs"]
    assert type(jobs) is list and len(jobs) == len(before_progress["repair_jobs"]) + 1
    job = jobs[-1]
    assert job["kind"] == "provider_response"
    assert job["operation"] == OP_REBUILD
    assert job["response"] == "rebuild provider refused"


def test_provider_failure_with_no_prior_record_leaves_the_file_absent(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"

    with pytest.raises(ProductBuildError, match="no prior record"):
        record_provider_failure(path, OP_PHASE1_PAGE, "page refused", PHASES[0])

    assert not path.exists()


@pytest.mark.asyncio
async def test_payload_edit_with_a_stale_digest_is_forged(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    payload["palette_name"] = "Other Palette"
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii"
    )
    before = path.read_bytes()
    pages = _page_ids(probe)

    with pytest.raises(ProductBuildError, match="forged"):
        await _phase_one(spec, probe, path)

    assert path.read_bytes() == before
    assert _page_ids(probe) == pages


@pytest.mark.asyncio
async def test_deleted_progress_key_is_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    del payload["progress"]
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii"
    )
    before = path.read_bytes()
    pages = _page_ids(probe)

    with pytest.raises(ProductBuildError, match="progress record is missing"):
        await _phase_one(spec, probe, path)

    assert path.read_bytes() == before
    assert _page_ids(probe) == pages


@pytest.mark.asyncio
async def test_forged_unrecoverable_flag_with_a_stale_digest_does_not_rebuild(
    tmp_path: Path,
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    payload["progress"]["recovery"] = "unrecoverable"
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii"
    )
    before = path.read_bytes()
    pages = len(probe.pages)

    with pytest.raises(ProductBuildError, match="forged"):
        await _phase_one(spec, probe, path)

    assert path.read_bytes() == before
    assert len(probe.pages) == pages


@pytest.mark.asyncio
async def test_progress_alignment_with_checkpoint_names_is_required(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)

    def _misalign(body: dict[str, object]) -> None:
        body["completed_operations"] = list(PHASES[:2])
        body["deferred_operations"] = list(PHASES[2:])

    _resign(path, _misalign)
    before = path.read_bytes()
    pages = _page_ids(probe)

    with pytest.raises(ProductBuildError, match="tampered"):
        await _phase_one(spec, probe, path)

    assert path.read_bytes() == before
    assert _page_ids(probe) == pages


@pytest.mark.asyncio
async def test_saved_notification_rejects_loose_adopt_fields_and_client_name(
    tmp_path: Path,
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_notification(spec, probe, path)
    database = next(
        item for item in probe.databases.values() if item.title == "Notification dashboard"
    )
    row = next(
        page
        for page in probe.pages.values()
        if type(page) is NotionPage
        and page.parent_id == database.id
        and page.title == spec.identity
    )
    before = path.read_bytes()
    databases = _database_ids(probe)

    database.properties[0].type = "text"
    with pytest.raises(ProductBuildError, match="notification database"):
        await build_notification_dashboard(spec, probe, path, recorded_at=LATER)
    assert path.read_bytes() == before
    database.properties[0].type = "title"

    database.properties[1].config = {"options": ["nope"]}
    with pytest.raises(ProductBuildError, match="notification database"):
        await build_notification_dashboard(spec, probe, path, recorded_at=LATER)
    assert path.read_bytes() == before
    database.properties[1].config = {}

    database.icon = "other"
    with pytest.raises(ProductBuildError, match="notification database"):
        await build_notification_dashboard(spec, probe, path, recorded_at=LATER)
    assert path.read_bytes() == before
    database.icon = NOTIFICATION_ICON

    row.properties["client_name"] = "hidden"
    with pytest.raises(ProductBuildError, match="notification row"):
        await build_notification_dashboard(spec, probe, path, recorded_at=LATER)
    assert path.read_bytes() == before
    assert row.properties["client_name"] == "hidden"
    assert _database_ids(probe) == databases


@pytest.mark.asyncio
async def test_unrecoverable_checkpoint_for_another_spec_writes_nothing(tmp_path: Path) -> None:
    spec = _spec()
    other = _spec(identity="Meal Planner")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    _resign(path, lambda body: body.__setitem__("recovery", "unrecoverable"))
    before = path.read_bytes()
    pages = len(probe.pages)

    with pytest.raises(ProductBuildError, match="different ProductSpec"):
        await build_top_level_page_and_design_shell(other, probe, path, recorded_at=LATER)

    assert path.read_bytes() == before
    assert len(probe.pages) == pages


@pytest.mark.asyncio
async def test_missing_prior_record_writes_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "missing.json"

    with pytest.raises(ProductBuildError, match="phase 1 checkpoint"):
        await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)

    assert not path.exists()
    assert probe.databases == {}


@pytest.mark.asyncio
async def test_reparented_design_shell_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    shell = next(block for block in probe.blocks.values() if type(block) is NotionCalloutBlock)
    shell.parent_id = "ws_other"
    before = path.read_bytes()
    blocks = _block_ids(probe)

    with pytest.raises(ProductBuildError, match="design shell is missing"):
        await _phase_one(spec, probe, path)

    assert path.read_bytes() == before
    assert _block_ids(probe) == blocks
    assert shell.parent_id == "ws_other"


@pytest.mark.asyncio
async def test_forged_business_events_relation_is_rejected(tmp_path: Path) -> None:
    spec = _spec(tier="business", identity="Studio Ledger")
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_notification(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    relations = payload["provider_object_references"]["notification_dashboard"]["relations"]
    relations.append({"data_type": "Events", "property_id": "forged_events"})
    payload = stamp_integrity_digest(payload)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii"
    )
    before = path.read_bytes()
    databases = {
        database.id: [prop.name for prop in database.properties]
        for database in probe.databases.values()
    }

    with pytest.raises(ProductBuildError, match="notification"):
        await build_notification_dashboard(spec, probe, path, recorded_at=LATER)

    assert path.read_bytes() == before
    assert {
        database.id: [prop.name for prop in database.properties]
        for database in probe.databases.values()
    } == databases
    assert "Events" not in {database.title for database in probe.databases.values()}


@pytest.mark.asyncio
async def test_duplicate_notification_relation_is_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_notification(spec, probe, path)
    payload = json.loads(path.read_text(encoding="ascii"))
    relations = payload["provider_object_references"]["notification_dashboard"]["relations"]
    relations.append(dict(relations[0]))
    payload = stamp_integrity_digest(payload)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii"
    )
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="duplicated"):
        await build_notification_dashboard(spec, probe, path, recorded_at=LATER)

    assert path.read_bytes() == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "buyer",
    ["BUYER", " Buyer ", "buyer name", "client", "{{buyer}}", "[buyer]", "<buyer>"],
)
async def test_buyer_placeholder_variants_write_nothing(tmp_path: Path, buyer: str) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_hubs(spec, probe, path)
    page = _home(probe)
    database = await probe.create_database(
        title="Notification dashboard", parent_id=page.id, parent_type="page_id"
    )
    await probe.add_property(database.id, "Name", "title", {})
    await probe.add_property(database.id, "Buyer name", "text", {})
    row = await probe.create_page(spec.identity, parent_id=database.id, parent_type="database_id")
    row.properties["Name"] = spec.identity
    row.properties["Buyer name"] = buyer
    calls = _watch(probe)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="notification row"):
        await build_notification_dashboard(spec, probe, path, recorded_at=NOTIFICATION_AT)

    assert calls == []
    assert row.properties["Buyer name"] == buyer
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_junk_notification_database_writes_nothing(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_hubs(spec, probe, path)
    page = _home(probe)
    database = await probe.create_database(
        title="Notification dashboard", parent_id=page.id, parent_type="page_id"
    )
    await probe.add_property(database.id, "Name", "text", {})
    tasks = next(item for item in probe.databases.values() if item.title == "Tasks")
    task_names = [prop.name for prop in tasks.properties]
    calls = _watch(probe)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="cannot be repaired"):
        await build_notification_dashboard(spec, probe, path, recorded_at=NOTIFICATION_AT)

    assert calls == []
    assert [prop.name for prop in database.properties] == ["Name"]
    assert [prop.name for prop in tasks.properties] == task_names
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_notification_icon_cover_crash_resumes(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_hubs(spec, probe, path)

    def _boom(database: NotionDatabase) -> None:
        raise RuntimeError("cover crashed")

    original = notification_module.set_notification_cover
    notification_module.set_notification_cover = _boom  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError, match="cover crashed"):
            await build_notification_dashboard(spec, probe, path, recorded_at=NOTIFICATION_AT)
    finally:
        notification_module.set_notification_cover = original
    database = next(
        item for item in probe.databases.values() if item.title == "Notification dashboard"
    )
    assert database.icon == NOTIFICATION_ICON
    assert database.cover is None

    await build_notification_dashboard(spec, probe, path, recorded_at=NOTIFICATION_AT)

    assert database.icon == NOTIFICATION_ICON
    assert database.cover == NOTIFICATION_COVER


@pytest.mark.asyncio
async def test_hub_icon_cover_crash_resumes(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_notification(spec, probe, path)
    original = probe.set_cover

    async def _boom(page_id: str, cover_url: str) -> NotionPage:
        raise RuntimeError("cover crashed")

    probe.set_cover = _boom  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError, match="cover crashed"):
            await build_aesthetics_and_content_completion(spec, probe, path, recorded_at=LATER)
    finally:
        probe.set_cover = original  # type: ignore[method-assign]
    hubs = [
        page
        for page in probe.pages.values()
        if page.parent_type == "page_id" and page.title.startswith("Hub")
    ]
    assert any(page.icon is not None and page.cover is None for page in hubs)
    blocks = _block_ids(probe)

    await build_aesthetics_and_content_completion(spec, probe, path, recorded_at=LATER)

    assert all(page.icon is not None and page.cover is not None for page in hubs)
    assert _block_ids(probe) == blocks


@pytest.mark.asyncio
async def test_sample_marker_tamper_is_not_overwritten(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_notification(spec, probe, path)
    sample = next(page for page in probe.pages.values() if page.title == "SAMPLE Tasks")
    sample.properties["sample_marker"] = "OTHER"
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="notification sample"):
        await build_notification_dashboard(spec, probe, path, recorded_at=LATER)

    assert sample.properties["sample_marker"] == "OTHER"
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_phase6_resume_rejects_tampered_accent_content(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_notification(spec, probe, path)
    await build_aesthetics_and_content_completion(spec, probe, path, recorded_at=LATER)
    accent = next(
        block
        for block in probe.blocks.values()
        if type(block) is NotionCalloutBlock and block.content.startswith("palette ")
    )
    accent.content = "tampered accent"
    before = path.read_bytes()
    blocks = _block_ids(probe)

    with pytest.raises(ProductBuildError, match="aesthetics accent"):
        await build_aesthetics_and_content_completion(
            spec, probe, path, recorded_at=datetime(2026, 10, 6, 2, 0, tzinfo=UTC)
        )

    assert accent.content == "tampered accent"
    assert path.read_bytes() == before
    assert _block_ids(probe) == blocks


@pytest.mark.asyncio
async def test_full_catalogue_plus_junk_column_cannot_be_repaired(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    page = _home(probe)
    database = await probe.create_database(title="Tasks", parent_id=page.id, parent_type="page_id")
    await probe.add_property(database.id, "Name", "title", {})
    await probe.add_property(database.id, "Status", "select", {"options": ["Open", "Done"]})
    await probe.add_property(database.id, "Due", "date", {})
    await probe.add_property(database.id, "Junk", "text", {})
    names = [prop.name for prop in database.properties]
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="cannot be repaired"):
        await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)

    assert [prop.name for prop in database.properties] == names
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_wrong_catalogue_type_cannot_be_repaired(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    page = _home(probe)
    database = await probe.create_database(title="Tasks", parent_id=page.id, parent_type="page_id")
    await probe.add_property(database.id, "Name", "text", {})
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="cannot be repaired"):
        await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)

    assert database.properties[0].type == "text"
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_wrong_catalogue_options_cannot_be_repaired(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    page = _home(probe)
    database = await probe.create_database(title="Tasks", parent_id=page.id, parent_type="page_id")
    await probe.add_property(database.id, "Name", "title", {})
    await probe.add_property(database.id, "Status", "select", {"options": ["Later"]})
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="cannot be repaired"):
        await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)

    assert database.properties[1].config == {"options": ["Later"]}
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_catalogue_icon_cannot_be_repaired(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _phase_one(spec, probe, path)
    page = _home(probe)
    database = await probe.create_database(title="Tasks", parent_id=page.id, parent_type="page_id")
    await probe.add_property(database.id, "Name", "title", {})
    database.icon = "nope"
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="cannot be repaired"):
        await build_shared_databases(spec, probe, path, recorded_at=PHASE_TWO_AT)

    assert database.icon == "nope"
    assert len(database.properties) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_notification_junk_icon_cannot_be_repaired(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _through_hubs(spec, probe, path)
    page = _home(probe)
    database = await probe.create_database(
        title="Notification dashboard", parent_id=page.id, parent_type="page_id"
    )
    await probe.add_property(database.id, "Name", "title", {})
    database.icon = "nope"
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="cannot be repaired"):
        await build_notification_dashboard(spec, probe, path, recorded_at=NOTIFICATION_AT)

    assert database.icon == "nope"
    assert path.read_bytes() == before
