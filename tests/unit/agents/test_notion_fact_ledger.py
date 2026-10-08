"""Fixture-only fact ledger and workflow link. Not the section 11 test matrix."""

from __future__ import annotations

import json
import socket
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest

from money_machine.agents.implementations import notion_fact_ledger as ledger_module
from money_machine.agents.implementations.notion_fact_ledger import (
    PHASE_TEST_MATRIX,
    run_fact_ledger,
)
from money_machine.agents.implementations.notion_product_builder import (
    ProductBuildCheckpoint,
    ProductBuildError,
)
from money_machine.agents.implementations.notion_progress_record import CheckpointView
from money_machine.agents.implementations.notion_qa import load_qa_record, run_product_qa
from money_machine.agents.implementations.notion_variants import (
    build_variants,
    load_variant_checkpoint,
)
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.domain import (
    NotionDatabaseProperty,
    NotionFormula,
    NotionLinkedView,
    NotionTextBlock,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from money_machine.orchestration.successor_factory import load_workflows_config
from tests.fixtures.products import create_fixture_product_spec
from tests.unit.agents.test_notion_product_builder_variants import (
    VARIANTS_AT,
    planner_spec,
    prepare_aesthetics,
    restamp_checkpoint,
    watch_adapter_writes,
)

ROOT = Path(__file__).parents[3]
MODULE_PATH = ROOT / "src/money_machine/agents/implementations/notion_fact_ledger.py"
QA_AT = datetime(2026, 10, 6, 3, 30, tzinfo=UTC)
LEDGER_AT = datetime(2026, 10, 7, 5, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 7, 6, 0, tzinfo=UTC)


async def _variants(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    await prepare_aesthetics(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)


async def _qa(tmp_path: Path, **spec_kwargs: str) -> tuple[ProductSpec, FixtureNotionAdapter, Path]:
    spec = planner_spec(**spec_kwargs)
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    return spec, probe, path


def _fact(checkpoint: ProductBuildCheckpoint, name: str) -> str:
    assert checkpoint.fact_ledger is not None
    return dict(checkpoint.fact_ledger.facts)[name]


def _check(checkpoint: ProductBuildCheckpoint, name: str) -> bool:
    assert checkpoint.fact_ledger is not None
    return dict(checkpoint.fact_ledger.checks)[name]


def _watch_checkpoint_writes() -> tuple[dict[str, int], Callable[..., None]]:
    """Count write_checkpoint calls and return the original writer."""
    writes = {"n": 0}
    original = ledger_module.write_checkpoint

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

    ledger_module.write_checkpoint = _count
    return writes, original


def _references(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="ascii"))
    references = document["provider_object_references"]
    assert type(references) is dict
    return references


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tier", "identity", "title", "hub_name"),
    [
        ("mass", "Weekly Planner", "Home Dashboard Planner", "Hub"),
        ("business", "Studio Ledger", "Studio Home", "Desk"),
    ],
)
async def test_qa_pass_persists_one_ledger_and_one_link(
    tmp_path: Path, tier: str, identity: str, title: str, hub_name: str
) -> None:
    spec, probe, path = await _qa(
        tmp_path, tier=tier, identity=identity, title=title, hub_name=hub_name
    )
    writes, original = _watch_checkpoint_writes()
    calls = watch_adapter_writes(probe)
    try:
        checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]

    assert checkpoint.fact_ledger is not None
    assert checkpoint.workflow_link is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert checkpoint.workflow_link.verdict == "PASS"
    assert checkpoint.workflow_link.ready == "ListingCopyJob"
    assert checkpoint.workflow_link.repair_required == "false"
    assert len(checkpoint.workflow_link.steps) == 8
    assert checkpoint.workflow_link.steps[0] == (
        "DEDUPE_PASSED>ProductBuildJob>BUILD_NOTION_TEMPLATE"
    )
    assert checkpoint.workflow_link.steps[-1] == (
        "SCREENSHOTS_CAPTURED>ListingCopyJob>GENERATE_LISTING_PACKAGE"
    )
    assert checkpoint.next_phase == PHASE_TEST_MATRIX
    assert _fact(checkpoint, "supported_devices") == "unverified"
    assert _fact(checkpoint, "free_update_policy") == "not_configured"
    assert _fact(checkpoint, "build_version") == "1"
    assert _fact(checkpoint, "colour_names") == ",".join(spec.colour_variants)
    assert _fact(checkpoint, "hubs") == ",".join(hub.name for hub in spec.hubs)
    assert _fact(checkpoint, "variants") == str(len(spec.colour_variants))
    assert _check(checkpoint, "qa_verdict") is True
    assert _fact(checkpoint, "secret_links").split(",")[0] == checkpoint.variants[0].secret_link
    assert any("CAPTURE_SCREENSHOTS" in step for step in checkpoint.workflow_link.steps)
    assert all(passed for _name, passed in checkpoint.fact_ledger.checks)
    assert calls == []
    assert writes["n"] == 1
    assert checkpoint.recorded_at == LEDGER_AT
    references = _references(path)
    assert type(references["fact_ledger"]) is dict
    assert type(references["workflow_link"]) is dict
    assert type(references["qa"]) is dict


@pytest.mark.asyncio
async def test_resume_of_pass_makes_no_second_write(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    first = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)
    writes, original = _watch_checkpoint_writes()
    try:
        again = await run_fact_ledger(spec, probe, path, recorded_at=LATER)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]

    assert again.fact_ledger == first.fact_ledger
    assert again.workflow_link == first.workflow_link
    assert again.next_phase == PHASE_TEST_MATRIX
    assert calls == []
    assert writes["n"] == 0
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_caller_spec_fields_are_not_the_facts(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    renamed = tuple(f"Not{index}" for index, _name in enumerate(spec.colour_variants))
    mutated = spec.model_copy(update={"version": 9, "colour_variants": renamed})
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(mutated, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert _fact(checkpoint, "colour_names") == ",".join(spec.colour_variants)
    assert _fact(checkpoint, "build_version") == "1"
    assert mutated.version == 9
    assert calls == []


@pytest.mark.asyncio
async def test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes(
    tmp_path: Path,
) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    home = next(iter(probe.pages.values()))
    probe.blocks["block_no_access"] = NotionTextBlock(
        id="block_no_access",
        parent_id=home.id,
        content="No access",
    )
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    raw = path.read_bytes()
    again = await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.workflow_link is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert checkpoint.workflow_link.verdict == "BLOCKED"
    assert checkpoint.workflow_link.ready == ""
    assert checkpoint.workflow_link.repair_required == "false"
    assert _check(checkpoint, "qa_verdict") is False
    assert again.fact_ledger == checkpoint.fact_ledger
    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_blocked_ledger_replans_when_the_defect_is_gone(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    home = next(iter(probe.pages.values()))
    probe.blocks["block_no_access"] = NotionTextBlock(
        id="block_no_access",
        parent_id=home.id,
        content="No access",
    )
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    blocked = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert blocked.fact_ledger is not None
    assert blocked.fact_ledger.verdict == "BLOCKED"
    del probe.blocks["block_no_access"]
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert "fact_ledger" in _references(path)
    assert "workflow_link" in _references(path)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert checkpoint.workflow_link is not None
    assert checkpoint.workflow_link.ready == "ListingCopyJob"
    assert calls == []


@pytest.mark.asyncio
async def test_stored_blocked_verdict_replans_a_passing_plan(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _block(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        ledger = references["fact_ledger"]
        link = references["workflow_link"]
        assert type(ledger) is dict and type(link) is dict
        ledger["verdict"] = "BLOCKED"
        link["verdict"] = "BLOCKED"
        link["ready"] = ""

    restamp_checkpoint(path, _block)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="fact ledger does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_forged_fact_does_not_match_and_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _lie(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        ledger = references["fact_ledger"]
        assert type(ledger) is dict
        facts = ledger["facts"]
        assert type(facts) is list
        page_count = facts[0]
        assert type(page_count) is dict
        page_count["value"] = "999"

    restamp_checkpoint(path, _lie)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="fact ledger does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_forged_step_does_not_match_and_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _lie(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        link = references["workflow_link"]
        assert type(link) is dict
        steps = link["steps"]
        assert type(steps) is list
        steps[0] = "DEDUPE_PASSED>ProductBuildJob>FORGED"

    restamp_checkpoint(path, _lie)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="workflow link does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_missing_qa_and_half_a_pair_write_nothing(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="fact ledger requires the qa checkpoint"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert calls == []
    assert path.read_bytes() == raw

    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _drop_link(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        del references["workflow_link"]

    restamp_checkpoint(path, _drop_link)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)
    with pytest.raises(ProductBuildError, match="fact ledger record is incomplete"):
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)
    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_unsupported_verdict_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _rename(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        ledger = references["fact_ledger"]
        assert type(ledger) is dict
        ledger["verdict"] = "MAYBE"

    restamp_checkpoint(path, _rename)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="fact ledger verdict is unsupported"):
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_catalogue_spec_and_live_probe_are_rejected(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="validated ProductSpec"):
        await run_fact_ledger(create_fixture_product_spec(), probe, path, recorded_at=LEDGER_AT)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await run_fact_ledger(spec, APINotionAdapter(), path, recorded_at=LEDGER_AT)
    assert path.read_bytes() == raw
    assert "fact_ledger" not in _references(path)


@pytest.mark.asyncio
async def test_missing_page_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    del probe.pages[stored.variants[0].page_id]
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="fact ledger page is missing"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_renamed_hub_is_blocked_with_no_adapter_writes(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.identity_hubs[0].page_id].title = "Renamed Hub"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert checkpoint.workflow_link is not None
    assert checkpoint.workflow_link.ready == ""
    assert _check(checkpoint, "hubs_present") is False
    assert _check(checkpoint, "qa_facts") is False
    assert _fact(checkpoint, "hubs").split(",")[0] == "Renamed Hub"
    assert _fact(checkpoint, "hubs").split(",")[0] != stored.identity_hubs[0].name
    assert calls == []


@pytest.mark.asyncio
async def test_broken_workflow_graph_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    def _broken() -> tuple[dict[str, list[str]], object]:
        event_map, config = load_workflows_config()
        return {**event_map, "DEDUPE_PASSED": ["ReconceptProductJob"]}, config

    monkeypatch.setattr(ledger_module, "load_workflows_config", _broken)
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="workflow link does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_checkpoint_crash_resumes_to_one_pass(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    original = ledger_module.write_checkpoint

    def _boom(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("checkpoint crashed")

    ledger_module.write_checkpoint = _boom  # type: ignore[assignment]
    try:
        with pytest.raises(RuntimeError, match="checkpoint crashed"):
            await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]
    assert "fact_ledger" not in _references(path)
    assert "workflow_link" not in _references(path)
    calls = watch_adapter_writes(probe)
    writes, original = _watch_checkpoint_writes()
    try:
        checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert checkpoint.workflow_link is not None
    assert checkpoint.workflow_link.ready == "ListingCopyJob"
    assert calls == []
    assert writes["n"] == 1


@pytest.mark.asyncio
async def test_variants_after_the_ledger_do_not_drop_the_keys(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    references = _references(path)
    assert type(references["qa"]) is dict
    assert type(references["fact_ledger"]) is dict
    assert type(references["workflow_link"]) is dict


@pytest.mark.asyncio
async def test_repaired_publish_keeps_the_listing_ready(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    stored, _created = load_variant_checkpoint(path)
    await probe.unpublish_page(stored.variants[0].page_id)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "PASS"
    assert checkpoint.qa.repairs == ("published",)
    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert checkpoint.workflow_link is not None
    assert checkpoint.workflow_link.repair_required == "true"
    assert checkpoint.workflow_link.ready == "ListingCopyJob"
    assert calls == []


@pytest.mark.asyncio
async def test_renamed_variant_page_blocks_qa_facts(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.variants[0].page_id].title = "TAMPERED"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "qa_facts") is False
    assert calls == []


@pytest.mark.asyncio
async def test_renamed_database_blocks_the_database_check(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    _kind, database_id = stored.database_ids[0]
    probe.databases[database_id].title = "Not The Kind"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "databases_present") is False
    assert calls == []


@pytest.mark.asyncio
async def test_forged_captured_url_blocks_secret_links(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.variants[0].page_id].public_url = "https://evil.example/not-the-link"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "secret_links") is False
    assert calls == []


@pytest.mark.asyncio
async def test_blank_formula_blocks_dashboard_outputs(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    kind, _name, property_id = stored.notification_dashboard.formulas[0]
    database_id = next(item_id for item_kind, item_id in stored.database_ids if item_kind == kind)
    database = probe.databases[database_id]
    prop = next(item for item in database.properties if item.id == property_id)
    formula = prop.config["formula"]
    prop.config["formula"] = formula.__class__(id=formula.id, name=formula.name, expression="")
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "dashboard_outputs") is False
    assert _fact(checkpoint, "dashboard_outputs") == "missing"
    assert calls == []


@pytest.mark.asyncio
async def test_missing_listing_package_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()
    event_map, config = load_workflows_config()
    workflow = next(
        item for item in config.workflows if item.workflow_type == "ProductLifecycleWorkflow"
    )
    jobs = tuple(
        job.model_copy(update={"output_contracts": ("AgentResult",)})
        if job.job_type == "ListingCopyJob"
        else job
        for job in workflow.jobs
    )
    patched = config.model_copy(update={"workflows": (workflow.model_copy(update={"jobs": jobs}),)})

    def _broken() -> tuple[dict[str, list[str]], object]:
        return event_map, patched

    monkeypatch.setattr(ledger_module, "load_workflows_config", _broken)
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="workflow link does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_missing_listing_successor_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()
    event_map, config = load_workflows_config()
    mapped = [job for job in event_map["SCREENSHOTS_CAPTURED"] if job != "ListingCopyJob"]

    def _broken() -> tuple[dict[str, list[str]], object]:
        return {**event_map, "SCREENSHOTS_CAPTURED": mapped}, config

    monkeypatch.setattr(ledger_module, "load_workflows_config", _broken)
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="workflow link does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_ledger_does_not_open_a_socket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tripwire: connect, connect_ex, and create_connection raise. Not a sandbox."""

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("socket connect is refused")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    spec, probe, path = await _qa(tmp_path)
    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    source = MODULE_PATH.read_text(encoding="utf-8")
    for token in (
        "notion_client",
        "httpx",
        "urllib",
        "socket",
        "requests",
        "APINotionAdapter",
        "playwright",
        "https://",
        "http://",
        "client_name",
        "etsy",
        "Etsy",
        "ETSY",
    ):
        assert token.casefold() not in source.casefold()


def _ledger(document: dict[str, object]) -> dict[str, object]:
    references = document["provider_object_references"]
    assert type(references) is dict
    ledger = references["fact_ledger"]
    assert type(ledger) is dict
    return ledger


def _link(document: dict[str, object]) -> dict[str, object]:
    references = document["provider_object_references"]
    assert type(references) is dict
    link = references["workflow_link"]
    assert type(link) is dict
    return link


async def _refuse(
    spec: ProductSpec,
    probe: FixtureNotionAdapter,
    path: Path,
    mutate: Callable[[dict[str, object]], None],
    message: str,
) -> None:
    restamp_checkpoint(path, mutate)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)
    writes, original = _watch_checkpoint_writes()
    try:
        with pytest.raises(ProductBuildError, match=message):
            await run_fact_ledger(spec, probe, path, recorded_at=LATER)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]
    assert calls == []
    assert writes["n"] == 0
    assert path.read_bytes() == raw


async def _blocked_ledger(
    tmp_path: Path,
) -> tuple[ProductSpec, FixtureNotionAdapter, Path]:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    home = next(iter(probe.pages.values()))
    probe.blocks["block_no_access"] = NotionTextBlock(
        id="block_no_access",
        parent_id=home.id,
        content="No access",
    )
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    blocked = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert blocked.fact_ledger is not None
    assert blocked.fact_ledger.verdict == "BLOCKED"
    return spec, probe, path


@pytest.mark.asyncio
async def test_forged_blocked_fact_does_not_match_and_writes_nothing(tmp_path: Path) -> None:
    """A forged fact on BLOCKED refuses. PASS is test_forged_fact_does_not_match."""
    spec, probe, path = await _blocked_ledger(tmp_path)

    def _lie(document: dict[str, object]) -> None:
        facts = _ledger(document)["facts"]
        assert type(facts) is list
        page_count = facts[0]
        assert type(page_count) is dict
        page_count["value"] = "999"

    await _refuse(spec, probe, path, _lie, "fact ledger does not match")


@pytest.mark.asyncio
async def test_blocked_ledger_with_a_pass_link_refuses(tmp_path: Path) -> None:
    spec, probe, path = await _blocked_ledger(tmp_path)

    def _lie(document: dict[str, object]) -> None:
        link = _link(document)
        link["verdict"] = "PASS"
        link["ready"] = ""

    await _refuse(spec, probe, path, _lie, "workflow link does not match")


@pytest.mark.asyncio
async def test_blocked_ledger_with_forged_repair_required_refuses(tmp_path: Path) -> None:
    spec, probe, path = await _blocked_ledger(tmp_path)

    def _lie(document: dict[str, object]) -> None:
        _link(document)["repair_required"] = "true"

    await _refuse(spec, probe, path, _lie, "workflow link does not match")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target", "message"),
    [
        ("ledger", "fact ledger record is incomplete"),
        ("link", "workflow link record is incomplete"),
        ("check", "fact ledger record is incomplete"),
    ],
)
async def test_extra_key_is_incomplete(tmp_path: Path, target: str, message: str) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _extra(document: dict[str, object]) -> None:
        if target == "ledger":
            _ledger(document)["extra"] = "x"
            return
        if target == "link":
            _link(document)["extra"] = "x"
            return
        checks = _ledger(document)["checks"]
        assert type(checks) is list
        row = checks[0]
        assert type(row) is dict
        row["extra"] = "x"

    await _refuse(spec, probe, path, _extra, message)


@pytest.mark.asyncio
async def test_database_parent_other_than_home_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    _kind, database_id = stored.database_ids[0]
    probe.databases[database_id].parent_id = "not-the-home-page"
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)
    writes, original = _watch_checkpoint_writes()
    try:
        with pytest.raises(ProductBuildError, match="fact ledger database is missing"):
            await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]
    assert calls == []
    assert writes["n"] == 0
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event", "replacement"),
    [
        ("SCREENSHOTS_CAPTURED", "delete"),
        ("VARIANT_LINKS_VERIFIED", ["DeliveryBuildJob"]),
        ("BUILD_COMPLETED", ["VariantBuildJob"]),
        ("VARIANTS_COMPLETED", ["ScreenshotJob"]),
        ("BUILD_QA_PASSED", "delete"),
        ("REPAIR_APPLIED", "delete"),
        ("VARIANT_LINKS_VERIFIED", ["ScreenshotJob", "ExtraJob"]),
        ("BUILD_QA_FAILED", []),
    ],
    ids=[
        "screenshots-deleted",
        "variant-links-to-delivery",
        "build-completed-to-variant",
        "variants-completed-to-screenshot",
        "build-qa-passed-deleted",
        "repair-applied-deleted",
        "variant-links-extra-job",
        "build-qa-failed-dropped",
    ],
)
async def test_each_workflow_edge_is_read_from_the_event_map(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    event: str,
    replacement: str | list[str],
) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()
    event_map, config = load_workflows_config()

    def _broken() -> tuple[dict[str, list[str]], object]:
        patched = dict(event_map)
        if replacement == "delete":
            del patched[event]
        else:
            assert type(replacement) is list
            patched[event] = replacement
        return patched, config

    monkeypatch.setattr(ledger_module, "load_workflows_config", _broken)
    calls = watch_adapter_writes(probe)
    with pytest.raises(ProductBuildError, match="workflow link does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("captured", ["", None])
async def test_empty_or_missing_public_url_blocks_secret_links(
    tmp_path: Path, captured: str | None
) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.variants[0].page_id].public_url = captured
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "secret_links") is False
    assert _fact(checkpoint, "secret_links").split(",")[0] == "missing"
    assert calls == []


@pytest.mark.asyncio
async def test_hub_title_that_is_not_text_is_blocked(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.identity_hubs[0].page_id].__dict__["title"] = 5
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "hubs_present") is False
    assert _fact(checkpoint, "hubs").split(",")[0] == "missing"
    assert calls == []


@pytest.mark.asyncio
async def test_blank_database_title_is_missing_and_blocked(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    kind, database_id = stored.database_ids[0]
    assert kind == "Tasks"
    probe.databases[database_id].title = ""
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    fact = _fact(checkpoint, "databases")
    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "databases_present") is False
    assert fact.split(",")[0] == "missing"
    assert not fact.startswith(",")
    assert fact.split(",")[0] != "Tasks"
    assert calls == []


@pytest.mark.asyncio
async def test_database_title_with_edge_space_is_missing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    kind, database_id = stored.database_ids[0]
    probe.databases[database_id].title = kind + " "
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "databases_present") is False
    assert _fact(checkpoint, "databases").split(",")[0] == "missing"
    assert (kind + " ") not in path.read_text(encoding="ascii")
    assert calls == []


@pytest.mark.asyncio
async def test_decoy_formula_is_not_the_dashboard_fact(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    kind, _name, _property_id = stored.notification_dashboard.formulas[0]
    database_id = next(item_id for item_kind, item_id in stored.database_ids if item_kind == kind)
    database = probe.databases[database_id]
    database.properties.insert(
        0,
        NotionDatabaseProperty(
            id="decoy-formula",
            name="Decoy",
            type="formula",
            config={"formula": NotionFormula(id="decoy-formula", name="Decoy", expression="DECOY")},
        ),
    )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert "DECOY" not in _fact(checkpoint, "dashboard_outputs")
    assert calls == []


@pytest.mark.asyncio
async def test_blank_formula_expression_is_missing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    kind, _name, property_id = stored.notification_dashboard.formulas[0]
    database_id = next(item_id for item_kind, item_id in stored.database_ids if item_kind == kind)
    prop = next(item for item in probe.databases[database_id].properties if item.id == property_id)
    formula = prop.config["formula"]
    assert type(formula) is NotionFormula
    formula.expression = ""
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _fact(checkpoint, "dashboard_outputs") == "missing"
    assert calls == []


@pytest.mark.asyncio
async def test_formula_recorded_on_the_wrong_database_is_missing(tmp_path: Path) -> None:
    """The expression can match and still be missing when the database kind does not."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    kind, _name, property_id = stored.notification_dashboard.formulas[0]
    other = next(item for item, _database_id in stored.database_ids if item != kind)
    source_id = next(item_id for item_kind, item_id in stored.database_ids if item_kind == kind)
    other_id = next(item_id for item_kind, item_id in stored.database_ids if item_kind == other)
    prop = next(item for item in probe.databases[source_id].properties if item.id == property_id)
    formula = prop.config["formula"]
    assert type(formula) is NotionFormula
    probe.databases[other_id].properties.append(
        NotionDatabaseProperty(
            id=property_id,
            name=prop.name,
            type="formula",
            config={
                "formula": NotionFormula(
                    id=formula.id,
                    name=formula.name,
                    expression=formula.expression,
                )
            },
        )
    )

    def _move(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        notice = references["notification_dashboard"]
        assert type(notice) is dict
        formulas = notice["formulas"]
        assert type(formulas) is list
        row = formulas[0]
        assert type(row) is dict
        row["kind"] = other

    restamp_checkpoint(path, _move)
    calls = watch_adapter_writes(probe)
    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "dashboard_outputs") is False
    assert _fact(checkpoint, "dashboard_outputs") == "missing"
    assert calls == []


@pytest.mark.asyncio
async def test_persisted_qa_flags_match_the_qa_record(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert checkpoint.qa is not None
    stored_qa = _references(path)["qa"]
    assert type(stored_qa) is dict
    rows = stored_qa["checks"]
    assert type(rows) is list
    assert len(rows) == len(checkpoint.qa.checks)
    for row, (name, passed) in zip(rows, checkpoint.qa.checks, strict=True):
        assert type(row) is dict
        assert row["check"] == name
        assert row["passed"] == ("true" if passed else "false")
    assert any(row["passed"] == "true" for row in rows if type(row) is dict)


@pytest.mark.asyncio
async def test_link_verdict_maybe_is_unsupported(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _rename(document: dict[str, object]) -> None:
        _link(document)["verdict"] = "MAYBE"

    await _refuse(spec, probe, path, _rename, "workflow link verdict is unsupported")


@pytest.mark.asyncio
async def test_ready_nope_is_incomplete(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _rename(document: dict[str, object]) -> None:
        _link(document)["ready"] = "Nope"

    await _refuse(spec, probe, path, _rename, "workflow link record is incomplete")


@pytest.mark.asyncio
async def test_empty_steps_are_incomplete(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _clear(document: dict[str, object]) -> None:
        _link(document)["steps"] = []

    await _refuse(spec, probe, path, _clear, "workflow link record is incomplete")


@pytest.mark.asyncio
async def test_check_flag_number_is_incomplete(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _number(document: dict[str, object]) -> None:
        checks = _ledger(document)["checks"]
        assert type(checks) is list
        row = checks[0]
        assert type(row) is dict
        row["passed"] = 1

    await _refuse(spec, probe, path, _number, "fact ledger record is incomplete")


@pytest.mark.asyncio
async def test_facts_json_number_is_incomplete(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _number(document: dict[str, object]) -> None:
        _ledger(document)["facts"] = 1

    await _refuse(spec, probe, path, _number, "fact ledger record is incomplete")


@pytest.mark.asyncio
async def test_repair_required_list_is_incomplete(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _list(document: dict[str, object]) -> None:
        _link(document)["repair_required"] = ["true"]

    await _refuse(spec, probe, path, _list, "workflow link record is incomplete")


@pytest.mark.asyncio
async def test_unknown_page_before_the_ledger_is_not_a_fact(tmp_path: Path) -> None:
    """A page outside the known ids is not a ledger fact.

    The proof page is the only extra page. Removing it before the first ledger
    run leaves the pre-duplicate shape. Live QA can still pass, and the ledger
    records PASS with one checkpoint write. It does not recreate the proof.
    """
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    qa = load_qa_record(path)
    assert qa is not None
    proof = qa.proof_page_id
    assert proof != ""
    known = {stored.page_id, *(hub.page_id for hub in stored.identity_hubs)}
    notice = stored.notification_dashboard
    if notice is not None:
        known.add(notice.row_page_id)
        known.update(page_id for _kind, page_id in notice.samples)
    known.update(record.page_id for record in stored.variants)
    assert proof not in known
    del probe.pages[proof]
    calls = watch_adapter_writes(probe)
    writes, original = _watch_checkpoint_writes()
    try:
        checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert calls == []
    assert writes["n"] == 1
    assert proof not in probe.pages


@pytest.mark.asyncio
async def test_stale_checkpoint_tmp_is_removed_on_the_next_write(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    orphan = path.with_name(f".{path.name}.999.tmp")
    orphan.write_text("stale\n", encoding="ascii")

    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert not orphan.exists()


@pytest.mark.asyncio
async def test_trailing_space_in_a_hub_title_can_be_repaired(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    hub = stored.identity_hubs[0]
    page = probe.pages[hub.page_id]
    page.title = hub.name + " "
    calls = watch_adapter_writes(probe)

    blocked = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert blocked.fact_ledger is not None
    assert blocked.fact_ledger.verdict == "BLOCKED"
    assert _fact(blocked, "hubs").split(",")[0] == "missing"
    assert _check(blocked, "hubs_present") is False
    assert (hub.name + " ") not in path.read_text(encoding="ascii")
    assert calls == []
    page.title = hub.name

    recovered = await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert recovered.fact_ledger is not None
    assert recovered.fact_ledger.verdict == "PASS"
    assert _fact(recovered, "hubs").split(",")[0] == hub.name


@pytest.mark.asyncio
async def test_one_fixed_defect_replans_the_other(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.identity_hubs[0].page_id].title = "Renamed Hub"
    assert stored.notification_dashboard is not None
    kind, _name, property_id = stored.notification_dashboard.formulas[0]
    database_id = next(item_id for item_kind, item_id in stored.database_ids if item_kind == kind)
    prop = next(item for item in probe.databases[database_id].properties if item.id == property_id)
    formula = prop.config["formula"]
    assert type(formula) is NotionFormula
    original = formula.expression
    formula.expression = "1+1"
    blocked = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert blocked.fact_ledger is not None
    assert blocked.fact_ledger.verdict == "BLOCKED"
    assert _check(blocked, "dashboard_outputs") is False
    assert _check(blocked, "hubs_present") is False
    formula.expression = original
    raw = path.read_bytes()

    again = await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert path.read_bytes() != raw
    assert again.fact_ledger is not None
    assert again.fact_ledger.verdict == "BLOCKED"
    assert _check(again, "dashboard_outputs") is True
    assert _check(again, "hubs_present") is False
    assert _fact(again, "hubs").split(",")[0] == "Renamed Hub"


@pytest.mark.asyncio
async def test_stale_pass_refuses_when_the_live_page_is_unpublished(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    stored, _created = load_variant_checkpoint(path)
    await probe.unpublish_page(stored.variants[0].page_id)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="fact ledger does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    [
        "unpublished",
        "template",
        "indexing",
        "icon",
        "cover",
        "no_access",
        "foreign_view",
        "formula",
    ],
)
async def test_live_state_qa_rejects_is_not_a_pass(tmp_path: Path, mode: str) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    page = probe.pages[stored.variants[0].page_id]
    if mode == "unpublished":
        await probe.unpublish_page(page.id)
    elif mode == "template":
        page.duplicate_as_template = False
    elif mode == "indexing":
        page.search_indexing = True
    elif mode == "icon":
        page.icon = "not-the-icon"
    elif mode == "cover":
        page.cover = "not-the-cover"
    elif mode == "no_access":
        probe.blocks["block_no_access"] = NotionTextBlock(
            id="block_no_access",
            parent_id=stored.page_id,
            content="No access",
        )
    elif mode == "foreign_view":
        probe.linked_views["foreign-view"] = NotionLinkedView(
            id="foreign-view",
            source_database_id="not-a-known-database",
            parent_page_id=stored.page_id,
        )
    elif mode == "formula":
        assert stored.notification_dashboard is not None
        kind, _name, property_id = stored.notification_dashboard.formulas[0]
        database_id = next(
            item_id for item_kind, item_id in stored.database_ids if item_kind == kind
        )
        prop = next(
            item for item in probe.databases[database_id].properties if item.id == property_id
        )
        formula = prop.config["formula"]
        assert type(formula) is NotionFormula
        formula.expression = "1+1"
    else:
        raise AssertionError(mode)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "qa_verdict") is False
    assert calls == []
    if mode == "formula":
        assert _fact(checkpoint, "dashboard_outputs") == "missing"
        assert _check(checkpoint, "dashboard_outputs") is False


@pytest.mark.asyncio
async def test_forged_ready_on_a_pass_refuses(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _ready(document: dict[str, object]) -> None:
        _link(document)["ready"] = ""

    await _refuse(spec, probe, path, _ready, "workflow link does not match")


@pytest.mark.asyncio
async def test_forged_link_verdict_on_a_pass_refuses(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _verdict(document: dict[str, object]) -> None:
        _link(document)["verdict"] = "BLOCKED"

    await _refuse(spec, probe, path, _verdict, "workflow link does not match")


@pytest.mark.asyncio
async def test_blocked_link_ready_job_refuses(tmp_path: Path) -> None:
    spec, probe, path = await _blocked_ledger(tmp_path)

    def _ready(document: dict[str, object]) -> None:
        _link(document)["ready"] = "ListingCopyJob"

    await _refuse(spec, probe, path, _ready, "workflow link does not match")


@pytest.mark.asyncio
async def test_blocked_forged_step_refuses(tmp_path: Path) -> None:
    spec, probe, path = await _blocked_ledger(tmp_path)

    def _step(document: dict[str, object]) -> None:
        steps = _link(document)["steps"]
        assert type(steps) is list
        steps[0] = "DEDUPE_PASSED>ProductBuildJob>FORGED"

    await _refuse(spec, probe, path, _step, "workflow link does not match")


@pytest.mark.asyncio
async def test_unknown_formula_name_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A formula name the spec does not expect is missing, not a TypeError."""
    spec, probe, path = await _qa(tmp_path)
    real = ledger_module.dashboard_formula_expressions

    def _drop(current: ProductSpec) -> dict[str, tuple[str, str]]:
        found = dict(real(current))
        found.pop(next(iter(found)))
        return found

    monkeypatch.setattr(ledger_module, "dashboard_formula_expressions", _drop)
    calls = watch_adapter_writes(probe)
    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _fact(checkpoint, "dashboard_outputs") == "missing"
    assert calls == []


@pytest.mark.asyncio
async def test_non_formula_config_is_missing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    kind, _name, property_id = stored.notification_dashboard.formulas[0]
    database_id = next(item_id for item_kind, item_id in stored.database_ids if item_kind == kind)
    prop = next(item for item in probe.databases[database_id].properties if item.id == property_id)
    prop.config["formula"] = "nope"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _fact(checkpoint, "dashboard_outputs") == "missing"
    assert calls == []


@pytest.mark.asyncio
async def test_text_property_is_not_a_dashboard_formula(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    kind, _name, property_id = stored.notification_dashboard.formulas[0]
    database_id = next(item_id for item_kind, item_id in stored.database_ids if item_kind == kind)
    prop = next(item for item in probe.databases[database_id].properties if item.id == property_id)
    prop.type = "text"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _fact(checkpoint, "dashboard_outputs") == "missing"
    assert calls == []


@pytest.mark.asyncio
async def test_database_title_integer_is_missing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    _kind, database_id = stored.database_ids[0]
    probe.databases[database_id].__dict__["title"] = 5
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "databases_present") is False
    assert _fact(checkpoint, "databases").split(",")[0] == "missing"
    assert calls == []


@pytest.mark.asyncio
async def test_missing_database_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    _kind, database_id = stored.database_ids[0]
    del probe.databases[database_id]
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)
    writes, original = _watch_checkpoint_writes()
    try:
        with pytest.raises(ProductBuildError, match="fact ledger database is missing"):
            await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]
    assert calls == []
    assert writes["n"] == 0
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_unpublished_trusted_url_blocks_secret_links(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    page = probe.pages[stored.variants[0].page_id]
    page.is_published = False
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "secret_links") is False
    assert calls == []


@pytest.mark.asyncio
async def test_forged_stored_secret_link_blocks(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    forged = "https" + "://" + "fixture.notion.site/forged"

    def _forge(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        variants = references["variants"]
        assert type(variants) is list
        row = variants[0]
        assert type(row) is dict
        row["secret_link"] = forged
        progress = document["progress"]
        assert type(progress) is dict
        created = progress["created_notion_ids"]
        assert type(created) is dict
        created_variants = created["variants"]
        assert type(created_variants) is list
        created_row = created_variants[0]
        assert type(created_row) is dict
        created_row["secret_link"] = forged

    restamp_checkpoint(path, _forge)
    calls = watch_adapter_writes(probe)
    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "secret_links") is False
    assert calls == []


@pytest.mark.asyncio
async def test_blank_home_title_keeps_live_qa(tmp_path: Path) -> None:
    """A blank home title blocks the colour fact and still feeds QA the spec title."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.page_id].title = ""
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "qa_verdict") is True
    assert _check(checkpoint, "qa_facts") is False
    assert calls == []


@pytest.mark.asyncio
async def test_renamed_home_title_fails_live_qa(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.page_id].title = "Renamed Home"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "qa_verdict") is False
    assert calls == []


@pytest.mark.asyncio
async def test_home_title_integer_keeps_live_qa(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.page_id].__dict__["title"] = 5
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "qa_verdict") is True
    assert _check(checkpoint, "qa_facts") is False
    assert calls == []


@pytest.mark.asyncio
async def test_blank_hub_title_is_missing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.identity_hubs[0].page_id].title = ""
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "hubs_present") is False
    assert _fact(checkpoint, "hubs").split(",")[0] == "missing"
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutate_name", "message"),
    [
        ("ledger-list", "fact ledger record is incomplete"),
        ("link-list", "workflow link record is incomplete"),
        ("ledger-number", "fact ledger record is incomplete"),
        ("link-number", "workflow link record is incomplete"),
        ("verdict-list", "fact ledger verdict is unsupported"),
        ("link-verdict-list", "workflow link verdict is unsupported"),
        ("ready-list", "workflow link record is incomplete"),
        ("repair-word", "workflow link record is incomplete"),
        ("steps-string", "workflow link record is incomplete"),
        ("check-string", "fact ledger record is incomplete"),
        ("check-number", "fact ledger record is incomplete"),
        ("check-label-number", "fact ledger record is incomplete"),
        ("checks-empty", "fact ledger record is incomplete"),
    ],
)
async def test_wrong_record_shapes_refuse(tmp_path: Path, mutate_name: str, message: str) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _mutate(document: dict[str, object]) -> None:
        if mutate_name == "ledger-list":
            references = document["provider_object_references"]
            assert type(references) is dict
            references["fact_ledger"] = ["x"]
            return
        if mutate_name == "link-list":
            references = document["provider_object_references"]
            assert type(references) is dict
            references["workflow_link"] = ["x"]
            return
        if mutate_name == "ledger-number":
            references = document["provider_object_references"]
            assert type(references) is dict
            references["fact_ledger"] = 1
            return
        if mutate_name == "link-number":
            references = document["provider_object_references"]
            assert type(references) is dict
            references["workflow_link"] = 1
            return
        if mutate_name == "verdict-list":
            _ledger(document)["verdict"] = ["PASS"]
            return
        if mutate_name == "link-verdict-list":
            _link(document)["verdict"] = ["PASS"]
            return
        if mutate_name == "ready-list":
            _link(document)["ready"] = [""]
            return
        if mutate_name == "repair-word":
            _link(document)["repair_required"] = "maybe"
            return
        if mutate_name == "steps-string":
            _link(document)["steps"] = "NO"
            return
        if mutate_name == "check-string":
            _ledger(document)["checks"] = ["true"]
            return
        if mutate_name == "check-number":
            _ledger(document)["checks"] = [1]
            return
        if mutate_name == "check-label-number":
            checks = _ledger(document)["checks"]
            assert type(checks) is list
            row = checks[0]
            assert type(row) is dict
            row["check"] = 1
            return
        if mutate_name == "checks-empty":
            _ledger(document)["checks"] = []
            return
        raise AssertionError(mutate_name)

    await _refuse(spec, probe, path, _mutate, message)


@pytest.mark.asyncio
async def test_template_flag_after_a_pass_refuses(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.variants[0].page_id].duplicate_as_template = False
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="fact ledger does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert calls == []
    assert path.read_bytes() == raw
