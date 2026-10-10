"""Fixture section 11 test matrix. The live sandbox is not started."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest

from money_machine.agents.implementations import notion_test_matrix as matrix_module
from money_machine.agents.implementations.notion_fact_ledger import run_fact_ledger
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    ProductBuildCheckpoint,
    ProductBuildError,
)
from money_machine.agents.implementations.notion_progress import ProviderFailure
from money_machine.agents.implementations.notion_progress_record import CheckpointView
from money_machine.agents.implementations.notion_qa import run_product_qa
from money_machine.agents.implementations.notion_test_matrix import (
    PHASE_SANDBOX,
    run_test_matrix,
)
from money_machine.agents.implementations.notion_variants import (
    build_variants,
    load_variant_checkpoint,
)
from money_machine.domain.models.product_spec import ColourToken, ProductSpec
from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.domain import NotionFormula
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from tests.fixtures.products import create_fixture_product_spec
from tests.unit.agents.test_notion_product_builder_variants import (
    VARIANTS_AT,
    planner_spec,
    prepare_aesthetics,
    restamp_checkpoint,
    watch_adapter_writes,
)

ROOT = Path(__file__).parents[3]
MODULE_PATH = ROOT / "src/money_machine/agents/implementations/notion_test_matrix.py"
QA_AT = datetime(2026, 10, 6, 3, 30, tzinfo=UTC)
LEDGER_AT = datetime(2026, 10, 7, 5, 0, tzinfo=UTC)
MATRIX_AT = datetime(2026, 10, 10, 2, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 10, 3, 0, tzinfo=UTC)
_CHECK_NAMES = (
    "complete_build",
    "variant_count",
    "public_links",
    "isolation",
    "fresh_duplicate",
    "fact_extraction",
    "successor_recorded",
    "formulas_match",
    "linked_views",
    "sections_present",
)


async def _variants(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    await prepare_aesthetics(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)


async def _ledger(
    tmp_path: Path, **spec_kwargs: str
) -> tuple[ProductSpec, FixtureNotionAdapter, Path]:
    spec = planner_spec(**spec_kwargs)
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    return spec, probe, path


def _passed(checkpoint: ProductBuildCheckpoint, name: str) -> bool:
    assert checkpoint.test_matrix is not None
    return dict(checkpoint.test_matrix.checks)[name]


def _references(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="ascii"))
    references = document["provider_object_references"]
    assert type(references) is dict
    return references


def _watch_writes() -> tuple[dict[str, int], Callable[..., None]]:
    writes = {"n": 0}
    original = matrix_module.write_checkpoint

    def _count(
        path: Path,
        checkpoint: CheckpointView | None = None,
        references: Mapping[str, object] | None = None,
        *,
        preserved_payload: Mapping[str, object] | None = None,
        progress: Mapping[str, object] | None = None,
        retained_created_ids: Mapping[str, object] | None = None,
    ) -> None:
        writes["n"] += 1
        original(
            path,
            checkpoint,
            references,
            preserved_payload=preserved_payload,
            progress=progress,
            retained_created_ids=retained_created_ids,
        )

    matrix_module.write_checkpoint = _count
    return writes, original


def _four(spec: ProductSpec) -> ProductSpec:
    return spec.model_copy(
        update={
            "palette_tokens": (*spec.palette_tokens, ColourToken(name="Neutral", hex="#111111")),
            "colour_variants": ("Blue", "Green", "Purple", "Gold"),
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tier", "identity", "title", "hub_name"),
    [
        ("mass", "Weekly Planner", "Home Dashboard Planner", "Hub"),
        ("business", "Studio Ledger", "Studio Home", "Desk"),
    ],
)
async def test_passing_ledger_records_the_matrix_once(
    tmp_path: Path, tier: str, identity: str, title: str, hub_name: str
) -> None:
    spec, probe, path = await _ledger(
        tmp_path, tier=tier, identity=identity, title=title, hub_name=hub_name
    )
    writes, original = _watch_writes()
    calls = watch_adapter_writes(probe)
    try:
        checkpoint = await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)
    finally:
        matrix_module.write_checkpoint = original  # type: ignore[assignment]

    assert checkpoint.test_matrix is not None
    assert checkpoint.test_matrix.verdict == "PASS"
    assert checkpoint.test_matrix.tier == tier
    assert checkpoint.next_phase == PHASE_SANDBOX
    assert checkpoint.checkpoint_names == BUILD_PHASES
    assert tuple(name for name, _flag in checkpoint.test_matrix.checks) == _CHECK_NAMES
    assert all(passed for _name, passed in checkpoint.test_matrix.checks)
    assert _passed(checkpoint, "variant_count") is True
    assert _passed(checkpoint, "successor_recorded") is True
    assert len(checkpoint.variants) == 3
    assert calls == []
    assert writes["n"] == 1
    assert checkpoint.recorded_at == MATRIX_AT
    document = json.loads(path.read_text(encoding="ascii"))
    assert document["progress"]["next_phase"] == PHASE_SANDBOX
    references = _references(path)
    assert type(references["test_matrix"]) is dict
    assert type(references["fact_ledger"]) is dict
    assert type(references["workflow_link"]) is dict
    stored = references["workflow_link"]
    assert type(stored) is dict
    assert stored["ready"] == "ListingCopyJob"


@pytest.mark.asyncio
async def test_four_colours_pass_the_variant_count(tmp_path: Path) -> None:
    spec = _four(planner_spec())
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)

    assert checkpoint.test_matrix is not None
    assert checkpoint.test_matrix.verdict == "PASS"
    assert len(checkpoint.variants) == 4
    assert _passed(checkpoint, "variant_count") is True
    assert calls == []


@pytest.mark.asyncio
async def test_resume_of_pass_makes_no_second_write(tmp_path: Path) -> None:
    spec, probe, path = await _ledger(tmp_path)
    first = await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)
    writes, original = _watch_writes()
    try:
        again = await run_test_matrix(spec, probe, path, recorded_at=LATER)
    finally:
        matrix_module.write_checkpoint = original  # type: ignore[assignment]

    assert again.test_matrix == first.test_matrix
    assert again.next_phase == PHASE_SANDBOX
    assert again.recorded_at == MATRIX_AT
    assert calls == []
    assert writes["n"] == 0
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_crash_before_the_write_resumes_once(tmp_path: Path) -> None:
    spec, probe, path = await _ledger(tmp_path)
    raw = path.read_bytes()
    original = matrix_module.write_checkpoint

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk")

    matrix_module.write_checkpoint = _boom  # type: ignore[assignment]
    try:
        with pytest.raises(OSError, match="disk"):
            await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)
    finally:
        matrix_module.write_checkpoint = original  # type: ignore[assignment]

    assert path.read_bytes() == raw
    assert "test_matrix" not in _references(path)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)

    assert checkpoint.test_matrix is not None
    assert checkpoint.test_matrix.verdict == "PASS"
    assert calls == []
    assert json.loads(path.read_text(encoding="ascii"))["progress"]["next_phase"] == PHASE_SANDBOX


@pytest.mark.asyncio
async def test_wrong_formula_is_blocked_and_not_rewritten(tmp_path: Path) -> None:
    spec, probe, path = await _ledger(tmp_path)
    changed = False
    before = ""
    for database in probe.databases.values():
        for prop in database.properties:
            formula = prop.config.get("formula")
            if type(formula) is NotionFormula:
                before = formula.expression
                prop.config["formula"] = NotionFormula(
                    id=formula.id,
                    name=formula.name,
                    expression="length(prop('Title'))",
                )
                changed = True
                break
        if changed:
            break
    assert changed
    calls = watch_adapter_writes(probe)

    checkpoint = await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)

    assert checkpoint.test_matrix is not None
    assert checkpoint.test_matrix.verdict == "BLOCKED"
    assert _passed(checkpoint, "formulas_match") is False
    assert calls == []
    for database in probe.databases.values():
        for prop in database.properties:
            formula = prop.config.get("formula")
            if type(formula) is NotionFormula and formula.expression == "length(prop('Title'))":
                assert formula.expression != before
                return
    raise AssertionError("the broken formula was rewritten")


@pytest.mark.asyncio
async def test_wrong_linked_view_is_blocked_and_not_retargeted(tmp_path: Path) -> None:
    spec, probe, path = await _ledger(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    _slug, view_id = stored.identity_hubs[0].views[0]
    view = probe.linked_views[view_id]
    original = view.source_database_id
    other = next(database_id for database_id in probe.databases if database_id != original)
    view.source_database_id = other
    calls = watch_adapter_writes(probe)

    checkpoint = await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)

    assert checkpoint.test_matrix is not None
    assert checkpoint.test_matrix.verdict == "BLOCKED"
    assert _passed(checkpoint, "linked_views") is False
    assert calls == []
    assert probe.linked_views[view_id].source_database_id == other


@pytest.mark.asyncio
async def test_missing_section_is_blocked_and_not_recreated(tmp_path: Path) -> None:
    spec, probe, path = await _ledger(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    _role, block_id = stored.identity_hubs[0].sections[0]
    removed = probe.blocks.pop(block_id)
    calls = watch_adapter_writes(probe)
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="fact ledger section is missing"):
        await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert block_id not in probe.blocks
    assert removed.id == block_id


@pytest.mark.asyncio
async def test_blocked_matrix_resumes_without_a_second_write(tmp_path: Path) -> None:
    spec, probe, path = await _ledger(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    _slug, view_id = stored.identity_hubs[0].views[0]
    view = probe.linked_views[view_id]
    view.source_database_id = next(
        database_id for database_id in probe.databases if database_id != view.source_database_id
    )
    first = await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)
    raw = path.read_bytes()
    writes, original = _watch_writes()
    try:
        again = await run_test_matrix(spec, probe, path, recorded_at=LATER)
    finally:
        matrix_module.write_checkpoint = original  # type: ignore[assignment]

    assert again.test_matrix == first.test_matrix
    assert again.test_matrix is not None and again.test_matrix.verdict == "BLOCKED"
    assert writes["n"] == 0
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_pass_that_no_longer_matches_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _ledger(tmp_path)
    await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)

    def _lie(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        matrix = references["test_matrix"]
        assert type(matrix) is dict
        matrix["verdict"] = "BLOCKED"

    restamp_checkpoint(path, _lie)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="test matrix does not match"):
        await run_test_matrix(spec, probe, path, recorded_at=LATER)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_catalogue_spec_and_live_probe_are_rejected(tmp_path: Path) -> None:
    spec, probe, path = await _ledger(tmp_path)
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="validated ProductSpec"):
        await run_test_matrix(create_fixture_product_spec(), probe, path, recorded_at=MATRIX_AT)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await run_test_matrix(spec, APINotionAdapter(), path, recorded_at=MATRIX_AT)

    assert path.read_bytes() == raw
    assert "test_matrix" not in _references(path)


@pytest.mark.asyncio
async def test_variants_checkpoint_is_not_a_matrix(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="fact ledger checkpoint"):
        await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_blocked_ledger_is_not_a_matrix(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    changed = False
    for database in probe.databases.values():
        for prop in database.properties:
            formula = prop.config.get("formula")
            if type(formula) is NotionFormula:
                prop.config["formula"] = NotionFormula(
                    id=formula.id,
                    name=formula.name,
                    expression="length(prop('Title'))",
                )
                changed = True
                break
        if changed:
            break
    assert changed
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    ledger = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert ledger.fact_ledger is not None and ledger.fact_ledger.verdict == "BLOCKED"
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="passing fact ledger"):
        await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert "test_matrix" not in _references(path)


@pytest.mark.asyncio
async def test_provider_failure_stores_the_fixed_text(tmp_path: Path) -> None:
    spec, probe, path = await _ledger(tmp_path)
    raw = path.read_bytes()

    async def _boom(*_args: object, **_kwargs: object) -> str:
        raise ProviderFailure("test_matrix.read", "sk-live-secret")

    probe.get_public_url = _boom  # type: ignore[method-assign]
    with pytest.raises(ProductBuildError, match="provider operation failed") as caught:
        await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)

    assert "sk-live-secret" not in str(caught.value)
    assert "sk-live-secret" not in path.read_text(encoding="utf-8")
    assert path.read_bytes() != raw
    assert "test_matrix" not in _references(path)


@pytest.mark.asyncio
async def test_local_error_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _ledger(tmp_path)
    raw = path.read_bytes()

    async def _boom(*_args: object, **_kwargs: object) -> str:
        raise ValueError("sk-live-secret")

    probe.get_public_url = _boom  # type: ignore[method-assign]
    with pytest.raises(ProductBuildError, match="test matrix failed in local code") as caught:
        await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)

    assert caught.value.__cause__ is None
    assert "sk-live-secret" not in str(caught.value)
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_interrupt_is_cleaned_and_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _ledger(tmp_path)
    raw = path.read_bytes()

    async def _boom(*_args: object, **_kwargs: object) -> str:
        raise KeyboardInterrupt("sk-live-secret")

    probe.get_public_url = _boom  # type: ignore[method-assign]
    with pytest.raises(KeyboardInterrupt) as caught:
        await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)

    assert type(caught.value) is KeyboardInterrupt
    assert caught.value.args == ()
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_qa_rewrite_keeps_the_matrix_key(tmp_path: Path) -> None:
    spec, probe, path = await _ledger(tmp_path)
    await run_test_matrix(spec, probe, path, recorded_at=MATRIX_AT)
    before = _references(path)["test_matrix"]

    def _drop_qa(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        del references["qa"]

    restamp_checkpoint(path, _drop_qa)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    references = _references(path)
    assert references["test_matrix"] == before
    assert type(references["qa"]) is dict
    assert type(references["fact_ledger"]) is dict


def test_matrix_source_does_not_create_a_job_or_open_a_network() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "ListingCopyJob" in source
    for banned in (
        "create_job",
        "JobRepository",
        "spawn_successor",
        "httpx",
        "requests",
        "APINotionAdapter",
        "notion_client",
        "--execute",
    ):
        assert banned not in source
