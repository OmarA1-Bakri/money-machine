"""Fixture-only product variants. Not a seventh build phase."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from money_machine.agents.implementations.notion_aesthetics import (
    build_aesthetics_and_content_completion,
)
from money_machine.agents.implementations.notion_dashboard import build_dashboard_and_navigation
from money_machine.agents.implementations.notion_hubs import build_identity_specific_hubs
from money_machine.agents.implementations.notion_notifications import build_notification_dashboard
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    SPEC_ID_PROPERTY,
    ProductBuildError,
    build_top_level_page_and_design_shell,
    find_spec_page,
)
from money_machine.agents.implementations.notion_progress import OP_VARIANTS, stamp_integrity_digest
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


def test_variants_module_does_not_name_a_live_client() -> None:
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
