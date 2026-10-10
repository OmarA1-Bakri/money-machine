"""Fixture-only phase 1 of the Notion product build."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from money_machine.agents.implementations.notion_product_builder import (
    DESIGN_SHELL_ICON,
    PHASE_SHARED_DATABASES,
    PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
    PRODUCT_ID_PROPERTY,
    SPEC_ID_PROPERTY,
    ProductBuildCheckpoint,
    ProductBuildError,
    build_top_level_page_and_design_shell,
    design_shell_content,
)
from money_machine.control.state import SESSION_EVIDENCE_KEYS
from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.product_spec import ColourToken, Hub, ProductSpec
from money_machine.integrations.notion.domain import NotionCalloutBlock, NotionPage, NotionTextBlock
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from tests.fixtures.products import create_fixture_product_spec

ROOT = Path(__file__).parents[3]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
MODULE_PATH = ROOT / "src/money_machine/agents/implementations/notion_product_builder.py"
WHEN = datetime(2026, 10, 3, 0, 30, tzinfo=UTC)
LATER = datetime(2026, 10, 3, 1, 0, tzinfo=UTC)
CLOSURE_SHA = "0f94d585f23d79e5ac18479f01e14f67cbaad332"
HEAD_SHA = "ae2ca6e41a0c6ff87437a53db91feb50bc5a82b3"


def _spec(
    *, identity: str = "Weekly Planner", shared: tuple[str, ...] = ("Tasks", "Events")
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
        title="Phase One Planner",
        tier="mass",
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
        concept_fingerprint="a" * 64,
        rule_version="v1",
        evidence=(
            EvidenceReference(
                evidence_id=uuid4(),
                evidence_type="fixture",
                source_reference="tests/unit/agents/test_notion_product_builder_phase1.py",
                observed_at=WHEN,
                safe_summary="Phase 1 fixture spec",
            ),
        ),
        created_at=WHEN,
    )


def _checkpoint_text(**overrides: object) -> str:
    payload: dict[str, object] = {
        "build_kind": "PRIMARY",
        "build_version": 1,
        "checkpoint_names": [PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL],
        "palette_name": "Modern Minimalist",
        "palette_tokens": [["Primary", "#2C3E50"], ["Secondary", "#3498DB"], ["Accent", "#E74C3C"]],
        "product_id": str(uuid4()),
        "provider_object_references": {
            "design_shell_block_id": "block_x",
            "top_level_page_id": "page_x",
            "workspace_id": "ws_default",
        },
        "recorded_at": WHEN.isoformat(),
        "spec_id": str(uuid4()),
    }
    payload.update(overrides)
    return json.dumps(payload, sort_keys=True) + "\n"


async def _build(
    spec: ProductSpec,
    probe: FixtureNotionAdapter,
    path: Path,
    *,
    recorded_at: datetime = WHEN,
) -> ProductBuildCheckpoint:
    return await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=recorded_at)


@pytest.mark.asyncio
async def test_phase_one_creates_one_unpublished_page_and_palette_shell(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "phase1.json"

    checkpoint = await _build(spec, probe, path)

    assert len(probe.pages) == 1
    assert len(probe.databases) == 0
    assert len(probe.views) == 0
    assert len(probe.linked_views) == 0
    page = next(iter(probe.pages.values()))
    assert page.title == spec.title
    assert page.parent_type == "workspace"
    assert page.parent_id == "ws_default"
    assert page.is_published is False
    assert page.duplicate_as_template is False
    assert page.search_indexing is True
    assert page.properties["product_spec_id"] == str(spec.spec_id)
    assert page.properties["product_id"] == str(spec.product_id)
    assert {item.title for item in probe.pages.values()} == {spec.title}
    hub_names = {hub.name for hub in spec.hubs}
    assert hub_names.isdisjoint({item.title for item in probe.pages.values()})
    shell = probe.blocks[checkpoint.shell_block_id]
    assert type(shell) is NotionCalloutBlock
    assert shell.icon == DESIGN_SHELL_ICON
    assert shell.content == design_shell_content(spec)
    for name in hub_names:
        assert name not in shell.content
    for variant in spec.colour_variants:
        assert variant != page.title
    assert checkpoint.checkpoint_names == (PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,)
    assert checkpoint.next_phase == PHASE_SHARED_DATABASES
    assert checkpoint.build_kind == "PRIMARY"
    assert checkpoint.build_version == 1
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["checkpoint_names"] == [PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL]
    assert stored["provider_object_references"]["top_level_page_id"] == page.id
    assert stored["provider_object_references"]["workspace_id"] == "ws_default"
    assert "shared_databases" not in stored["checkpoint_names"]


@pytest.mark.asyncio
async def test_replay_does_not_create_another_page_or_rewrite_the_checkpoint(
    tmp_path: Path,
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "phase1.json"
    first = await _build(spec, probe, path)
    before = path.read_bytes()
    page_ids = set(probe.pages)
    block_ids = set(probe.blocks)

    second = await _build(spec, probe, path, recorded_at=LATER)

    assert set(probe.pages) == page_ids
    assert set(probe.blocks) == block_ids
    assert second == first
    assert second.recorded_at == WHEN
    assert path.read_bytes() == before
    assert len(probe.databases) == 0


@pytest.mark.asyncio
async def test_missing_checkpoint_page_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "phase1.json"
    await _build(spec, probe, path)
    probe.pages.clear()
    probe.blocks.clear()

    with pytest.raises(ProductBuildError, match="checkpoint page is missing"):
        await _build(spec, probe, path, recorded_at=LATER)

    assert probe.pages == {}
    assert probe.blocks == {}
    assert probe.databases == {}


@pytest.mark.asyncio
async def test_existing_page_without_a_shell_only_adds_the_callout(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    page = NotionPage(
        id="page_existing",
        title=spec.title,
        parent_id="ws_default",
        parent_type="workspace",
        properties={
            "product_spec_id": str(spec.spec_id),
            "product_id": str(spec.product_id),
        },
    )
    probe.pages[page.id] = page

    checkpoint = await _build(spec, probe, tmp_path / "phase1.json")

    assert set(probe.pages) == {"page_existing"}
    assert checkpoint.page_id == "page_existing"
    assert len(probe.blocks) == 1
    assert probe.databases == {}


@pytest.mark.asyncio
async def test_existing_page_and_shell_only_rewrite_a_missing_checkpoint(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    page = NotionPage(
        id="page_existing",
        title=spec.title,
        parent_id="ws_default",
        parent_type="workspace",
        properties={
            "product_spec_id": str(spec.spec_id),
            "product_id": str(spec.product_id),
        },
    )
    shell = NotionCalloutBlock(
        id="block_existing",
        parent_id=page.id,
        content=design_shell_content(spec),
        icon=DESIGN_SHELL_ICON,
    )
    probe.pages[page.id] = page
    probe.blocks[shell.id] = shell
    path = tmp_path / "phase1.json"

    checkpoint = await _build(spec, probe, path)

    assert set(probe.pages) == {page.id}
    assert set(probe.blocks) == {shell.id}
    assert checkpoint.shell_block_id == shell.id
    assert page.properties["design_shell_block_id"] == shell.id
    assert path.is_file()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("title", "parent_type", "parent_id"),
    [
        ("Other title", "workspace", "ws_default"),
        ("Phase One Planner", "page_id", "page_parent"),
        ("Phase One Planner", "workspace", ""),
    ],
)
async def test_mismatched_existing_page_does_not_create_another(
    tmp_path: Path, title: str, parent_type: str, parent_id: str
) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    page = NotionPage(
        id="page_existing",
        title=title,
        parent_id=parent_id or None,
        parent_type=parent_type,
        properties={
            "product_spec_id": str(spec.spec_id),
            "product_id": str(spec.product_id),
        },
    )
    probe.pages[page.id] = page

    with pytest.raises(ProductBuildError):
        await _build(spec, probe, tmp_path / "phase1.json")

    assert set(probe.pages) == {page.id}
    assert probe.blocks == {}
    assert not (tmp_path / "phase1.json").exists()


@pytest.mark.asyncio
async def test_two_pages_for_one_spec_do_not_grow(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    for page_id in ("page_a", "page_b"):
        probe.pages[page_id] = NotionPage(
            id=page_id,
            title=spec.title,
            parent_id="ws_default",
            parent_type="workspace",
            properties={
                "product_spec_id": str(spec.spec_id),
                "product_id": str(spec.product_id),
            },
        )

    with pytest.raises(ProductBuildError, match="more than one page"):
        await _build(spec, probe, tmp_path / "phase1.json")

    assert set(probe.pages) == {"page_a", "page_b"}


@pytest.mark.asyncio
async def test_extra_child_block_is_not_joined_by_a_second_callout(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    page = NotionPage(
        id="page_existing",
        title=spec.title,
        parent_id="ws_default",
        parent_type="workspace",
        properties={
            "product_spec_id": str(spec.spec_id),
            "product_id": str(spec.product_id),
        },
    )
    extra = NotionTextBlock(id="block_extra", parent_id=page.id, content="Hub 1")
    probe.pages[page.id] = page
    probe.blocks[extra.id] = extra

    with pytest.raises(ProductBuildError, match="not the design shell"):
        await _build(spec, probe, tmp_path / "phase1.json")

    assert set(probe.blocks) == {extra.id}
    assert not any(type(block) is NotionCalloutBlock for block in probe.blocks.values())


@pytest.mark.asyncio
async def test_tampered_shell_on_resume_does_not_rewrite(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "phase1.json"
    first = await _build(spec, probe, path)
    shell = probe.blocks[first.shell_block_id]
    assert type(shell) is NotionCalloutBlock
    shell.content = "tampered"
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="does not match the ProductSpec"):
        await _build(spec, probe, path, recorded_at=LATER)

    assert path.read_bytes() == before
    assert len(probe.pages) == 1
    assert len(probe.blocks) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [object(), {"title": "no"}, "spec"])
async def test_non_product_spec_does_not_touch_the_probe(tmp_path: Path, bad: object) -> None:
    probe = FixtureNotionAdapter()
    with pytest.raises(ProductBuildError, match="validated ProductSpec"):
        await build_top_level_page_and_design_shell(
            bad, probe, tmp_path / "phase1.json", recorded_at=WHEN
        )
    assert probe.pages == {}


@pytest.mark.asyncio
async def test_catalogue_product_spec_is_rejected(tmp_path: Path) -> None:
    probe = FixtureNotionAdapter()
    catalogue = create_fixture_product_spec()
    with pytest.raises(ProductBuildError, match="validated ProductSpec"):
        await build_top_level_page_and_design_shell(
            catalogue, probe, tmp_path / "phase1.json", recorded_at=WHEN
        )
    assert probe.pages == {}
    assert probe.databases == {}


@pytest.mark.asyncio
async def test_probe_subclass_is_rejected_before_create(tmp_path: Path) -> None:
    class SubclassProbe(FixtureNotionAdapter):
        async def create_page(
            self,
            title: str,
            parent_id: str | None = None,
            parent_type: str = "workspace",
            icon: str | None = None,
            cover: str | None = None,
        ) -> NotionPage:
            raise AssertionError("create_page must not run")

    probe = SubclassProbe()
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await build_top_level_page_and_design_shell(
            _spec(), probe, tmp_path / "phase1.json", recorded_at=WHEN
        )
    assert probe.pages == {}


@pytest.mark.asyncio
async def test_naive_recorded_at_leaves_a_good_checkpoint_unchanged(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "phase1.json"
    await _build(spec, probe, path)
    before = path.read_bytes()
    pages = set(probe.pages)

    with pytest.raises(ProductBuildError, match="timezone-aware"):
        await _build(spec, probe, path, recorded_at=datetime(2026, 10, 3, 0, 30))

    assert path.read_bytes() == before
    assert set(probe.pages) == pages


@pytest.mark.asyncio
async def test_path_must_be_a_path_in_an_existing_directory(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    with pytest.raises(ProductBuildError, match="must be a path"):
        await build_top_level_page_and_design_shell(
            spec, probe, str(tmp_path / "phase1.json"), recorded_at=WHEN
        )
    with pytest.raises(ProductBuildError, match="directory is missing"):
        await _build(spec, probe, tmp_path / "missing" / "phase1.json")
    with pytest.raises(ProductBuildError, match="is a directory"):
        await _build(spec, probe, tmp_path)
    assert probe.pages == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "",
        "{",
        '{"build_kind":"PRIMARY"}',
        _checkpoint_text(extra=True),
        _checkpoint_text(build_kind="VARIANT"),
        _checkpoint_text(build_version=True),
        _checkpoint_text(checkpoint_names=[]),
        _checkpoint_text(
            checkpoint_names=[
                PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
                PHASE_SHARED_DATABASES,
            ]
        ),
        _checkpoint_text(checkpoint_names=[PHASE_SHARED_DATABASES]),
    ],
)
async def test_bad_checkpoint_does_not_create_a_page(tmp_path: Path, text: str) -> None:
    path = tmp_path / "phase1.json"
    path.write_text(text, encoding="utf-8")
    probe = FixtureNotionAdapter()

    with pytest.raises(ProductBuildError):
        await _build(_spec(), probe, path)

    assert probe.pages == {}
    assert probe.databases == {}


@pytest.mark.asyncio
async def test_checkpoint_for_another_spec_does_not_create_its_page(tmp_path: Path) -> None:
    spec = _spec()
    other = _spec(identity="Meal Planner")
    probe = FixtureNotionAdapter()
    path = tmp_path / "phase1.json"
    await _build(spec, probe, path)
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="different ProductSpec"):
        await _build(other, probe, path, recorded_at=LATER)

    assert path.read_bytes() == before
    assert len(probe.pages) == 1
    assert next(iter(probe.pages.values())).title == spec.title


@pytest.mark.asyncio
async def test_newline_in_identity_is_rejected(tmp_path: Path) -> None:
    probe = FixtureNotionAdapter()
    with pytest.raises(ProductBuildError, match="single lines"):
        await _build(_spec(identity="line\nbreak"), probe, tmp_path / "phase1.json")
    assert probe.pages == {}


def test_phase_one_module_does_not_name_a_live_client() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for token in (
        "notion_client",
        "httpx",
        "urllib",
        "socket",
        "requests",
        "APINotionAdapter",
        "etsy",
        "Etsy",
        "ETSY",
    ):
        assert token.casefold() not in source.casefold()


@pytest.mark.asyncio
async def test_existing_published_page_is_rejected(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "phase1.json"
    page = await probe.create_page(spec.title, parent_id="ws_default", parent_type="workspace")
    page.properties[SPEC_ID_PROPERTY] = str(spec.spec_id)
    page.properties[PRODUCT_ID_PROPERTY] = str(spec.product_id)
    page.is_published = True

    with pytest.raises(ProductBuildError, match="must stay unpublished"):
        await _build(spec, probe, path)

    assert path.exists() is False
    assert len(probe.blocks) == 0
    assert page.is_published is True


@pytest.mark.asyncio
async def test_published_checkpoint_page_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "phase1.json"
    await _build(spec, probe, path)
    page = next(iter(probe.pages.values()))
    page.is_published = True
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="must stay unpublished"):
        await _build(spec, probe, path)

    assert page.is_published is True
    assert len(probe.pages) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_icon_only_design_shell_tamper_is_not_rebuilt(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "phase1.json"
    await _build(spec, probe, path)
    shell = next(iter(probe.blocks.values()))
    assert isinstance(shell, NotionCalloutBlock)
    shell.icon = "💡"
    before = path.read_bytes()

    with pytest.raises(ProductBuildError, match="does not match"):
        await _build(spec, probe, path)

    assert shell.icon == "💡"
    assert len(probe.pages) == 1
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_phase_one_checkpoint_parser_rejects_bad_inputs(tmp_path: Path) -> None:
    spec = _spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "phase1.json"
    await _build(spec, probe, path)
    path.write_text("{\n", encoding="utf-8")

    with pytest.raises(ProductBuildError, match="not JSON"):
        await _build(spec, probe, path)

    assert len(probe.pages) == 1


def test_session_seven_stays_incomplete_with_false_evidence() -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    assert state["current_session"] == 7
    assert state["session_status"] == "incomplete"
    assert state["completed_sessions"] == [0, 1, 2, 3, 4, 5, 6]
    assert state["next_session"] == 7
    assert state["next_prompt"] == "10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md"
    assert state["head_sha"] == HEAD_SHA
    assert state["evidence_closure_commit_sha"] == CLOSURE_SHA
    assert state["commissioned_agents"] == []
    evidence = state["required_completion_evidence"]
    assert evidence.keys() == SESSION_EVIDENCE_KEYS[7]
    assert all(value is False for value in evidence.values())
    assert state["state_revision"] == 61
