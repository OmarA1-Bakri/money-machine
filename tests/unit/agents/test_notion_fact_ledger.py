"""Fixture-only fact ledger and workflow link. Not the section 11 test matrix."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import fields, replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from money_machine.agents.implementations import notion_fact_ledger as ledger_module
from money_machine.agents.implementations import notion_progress as progress_module
from money_machine.agents.implementations import notion_qa as qa_module
from money_machine.agents.implementations.notion_fact_ledger import (
    PHASE_TEST_MATRIX,
    run_fact_ledger,
)
from money_machine.agents.implementations.notion_hubs import section_content
from money_machine.agents.implementations.notion_product_builder import (
    FactLedgerRecord,
    ProductBuildCheckpoint,
    ProductBuildError,
    QaRecord,
    WorkflowLinkRecord,
)
from money_machine.agents.implementations.notion_progress import (
    OP_REBUILD,
    PHASES,
    ProviderFailure,
    append_refused_rebuild,
    record_provider_failure,
)
from money_machine.agents.implementations.notion_progress_record import CheckpointView
from money_machine.agents.implementations.notion_qa import (
    live_qa_passed,
    load_qa_record,
    run_product_qa,
)
from money_machine.agents.implementations.notion_shared_databases import (
    BUSINESS_SHARED_DATABASES,
    PLANNER_SHARED_DATABASES,
)
from money_machine.agents.implementations.notion_variants import (
    build_variants,
    load_variant_checkpoint,
)
from money_machine.domain.models.product_spec import Hub, ProductSpec
from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.domain import (
    NotionCalloutBlock,
    NotionDatabaseProperty,
    NotionFormula,
    NotionLinkedView,
    NotionPage,
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
    mutated = spec.model_copy(
        update={
            "version": 9,
            "colour_variants": renamed,
            "tier": "nope",
        }
    )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(mutated, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert _fact(checkpoint, "colour_names") == ",".join(spec.colour_variants)
    assert _fact(checkpoint, "hubs") == ",".join(hub.name for hub in spec.hubs)
    assert _fact(checkpoint, "build_version") == "1"
    assert mutated.version == 9
    assert mutated.tier == "nope"
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
    stored_qa = _references(path)["qa"]
    assert type(stored_qa) is dict
    qa_checks = stored_qa["checks"]
    assert type(qa_checks) is list
    assert any(type(row) is dict and row["passed"] == "false" for row in qa_checks)


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
    shown = _fact(checkpoint, "secret_links").split(",")[0]
    assert shown == "https://evil.example"
    assert "/not-the-link" not in shown
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
    read_expression = ledger_module._formula_expression  # pyright: ignore[reportPrivateUsage]
    assert read_expression(probe, stored, kind, property_id) == formula.expression
    formula.expression = ""
    assert read_expression(probe, stored, kind, property_id) is None
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


async def _assert_redacted_read(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    calls = watch_adapter_writes(probe)
    with pytest.raises(ProductBuildError, match="provider read failed") as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    text = path.read_text(encoding="utf-8")
    assert "sk-live-secret" not in str(caught.value)
    assert "sk-live-secret" not in text
    assert calls == []
    jobs = _jobs(path)
    assert len(jobs) == 1
    job = jobs[0]
    assert type(job) is dict
    assert job["kind"] == "provider_response"
    assert job["operation"] == "fact_ledger.read"
    assert job["response"] == "provider read failed"
    assert "fact_ledger" not in _references(path)


def _jobs(path: Path) -> list[object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    progress = document["progress"]
    assert type(progress) is dict
    jobs = progress["repair_jobs"]
    assert type(jobs) is list
    return jobs


def _qa_record(document: dict[str, object]) -> dict[str, object]:
    references = document["provider_object_references"]
    assert type(references) is dict
    qa = references["qa"]
    assert type(qa) is dict
    return qa


class _ChildPage(NotionPage):
    """A page subclass. It is still a page."""


class _Url(str):
    """A str subclass. Exact type str is required for a captured URL."""


class _Spoof:
    """Equals the trusted URL without being a str."""

    def __init__(self, trusted: str) -> None:
        self._trusted = trusted

    def __eq__(self, other: object) -> bool:
        return type(other) is str and other == self._trusted

    def __hash__(self) -> int:
        return hash(self._trusted)


class _View:
    def __init__(
        self,
        job_type: object,
        admitted_events: tuple[object, ...],
        successor_job_types: tuple[object, ...],
        output_contracts: object,
    ) -> None:
        self.job_type = job_type
        self.admitted_events = admitted_events
        self.successor_job_types = successor_job_types
        self.output_contracts = output_contracts


class _Flow:
    def __init__(self, workflow_type: str, jobs: tuple[_View, ...]) -> None:
        self.workflow_type = workflow_type
        self.jobs = jobs


class _Bundle:
    def __init__(self, workflows: tuple[_Flow, ...]) -> None:
        self.workflows = workflows


_PATH_EDGES = (
    ("DedupeJob", "DEDUPE_PASSED", "ProductBuildJob"),
    ("ProductBuildJob", "BUILD_COMPLETED", "ProductQAJob"),
    ("ProductQAJob", "BUILD_QA_FAILED", "BuildRepairJob"),
    ("BuildRepairJob", "REPAIR_APPLIED", "ProductQAJob"),
    ("ProductQAJob", "BUILD_QA_PASSED", "VariantBuildJob"),
    ("VariantBuildJob", "VARIANTS_COMPLETED", "VariantPublishJob"),
    ("VariantPublishJob", "VARIANT_LINKS_VERIFIED", "ScreenshotJob"),
    ("ScreenshotJob", "SCREENSHOTS_CAPTURED", "ListingCopyJob"),
    ("ScreenshotJob", "SCREENSHOTS_CAPTURED", "AssetFactoryJob"),
    ("ScreenshotJob", "SCREENSHOTS_CAPTURED", "DeliveryBuildJob"),
)


def test_missing_hub_in_the_spec_is_a_product_error() -> None:
    with pytest.raises(ProductBuildError, match="hub section is missing"):
        section_content(planner_spec(), "Not A Hub", "purpose")


@pytest.mark.asyncio
async def test_blocked_qa_with_a_live_pass_writes_nothing(tmp_path: Path) -> None:
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
    del probe.blocks["block_no_access"]
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)
    writes, original = _watch_checkpoint_writes()
    try:
        with pytest.raises(ProductBuildError, match="qa record does not match"):
            await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]

    assert calls == []
    assert writes["n"] == 0
    assert path.read_bytes() == raw
    assert _jobs(path) == []
    assert _qa_record(json.loads(path.read_text(encoding="ascii")))["verdict"] == "BLOCKED"


@pytest.mark.asyncio
async def test_fresh_duplicate_block_is_not_a_ledger_pass(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    page = next(
        item for item in probe.pages.values() if item.title.endswith("/ " + spec.colour_variants[0])
    )
    original = page.title
    page.title = "tampered source"
    blocked = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert blocked.qa is not None
    assert blocked.qa.verdict == "BLOCKED"
    assert blocked.qa.proof_page_id == ""
    assert dict(blocked.qa.checks)["fresh_duplicate"] is False
    page.title = original
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa record does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert _jobs(path) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("blocked", "qa record does not match"),
        ("repairable", "qa record does not match"),
        ("nope", "qa verdict is unsupported"),
        ("missing", "qa record fields are missing or unsupported"),
        ("false-check", "qa record does not match"),
    ],
)
async def test_inconsistent_stored_qa_writes_nothing(
    tmp_path: Path, mode: str, message: str
) -> None:
    """An inconsistent stored QA record writes nothing.

    A forged but internally consistent PASS is not this case. With a live
    defect that record writes one BLOCKED ledger, because it cannot be told
    apart from a real PASS.
    """
    spec, probe, path = await _qa(tmp_path)

    def _mutate(document: dict[str, object]) -> None:
        qa = _qa_record(document)
        if mode == "blocked":
            qa["verdict"] = "BLOCKED"
            return
        if mode == "repairable":
            qa["verdict"] = "FAIL_REPAIRABLE"
            return
        if mode == "nope":
            qa["verdict"] = "NOPE"
            return
        if mode == "missing":
            del qa["verdict"]
            return
        checks = qa["checks"]
        assert type(checks) is list
        row = checks[0]
        assert type(row) is dict
        row["passed"] = "false"

    await _refuse(spec, probe, path, _mutate, message)
    assert _jobs(path) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    ["leading-url", "trailing-url", "leading-title", "trailing-title", "tab", "newline", "nbsp"],
)
async def test_edge_whitespace_is_refused_before_persist(tmp_path: Path, mode: str) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)
    notice = stored.notification_dashboard
    assert notice is not None
    row = probe.pages[notice.row_page_id]
    if mode == "leading-url":
        page = probe.pages[stored.variants[0].page_id]
        page.public_url = " " + str(page.public_url)
    elif mode == "trailing-url":
        page = probe.pages[stored.variants[-1].page_id]
        page.public_url = str(page.public_url) + "\t"
    elif mode == "leading-title":
        row.title = " " + row.title
    elif mode == "tab":
        row.title = row.title + "\t"
    elif mode == "newline":
        row.title = row.title + "\n"
    elif mode == "nbsp":
        row.title = row.title + "\u00a0"
    else:
        row.title = row.title + " "

    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert _jobs(path) == []
    if mode == "leading-url":
        page = probe.pages[stored.variants[0].page_id]
        page.public_url = str(page.public_url).strip()
    elif mode == "trailing-url":
        page = probe.pages[stored.variants[-1].page_id]
        page.public_url = str(page.public_url).strip()
    else:
        row.title = row.title.strip()

    recovered = await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert recovered.fact_ledger is not None
    assert recovered.fact_ledger.verdict == "PASS"


@pytest.mark.asyncio
@pytest.mark.parametrize("title", ["", None])
async def test_blank_dashboard_row_title_refuses(tmp_path: Path, title: str | None) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    row = probe.pages[stored.notification_dashboard.row_page_id]
    original = row.title
    if title is None:
        row.__dict__["title"] = None
    else:
        row.title = title
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="fact ledger dashboard row is missing"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert _jobs(path) == []
    row.title = original

    recovered = await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert recovered.fact_ledger is not None
    assert recovered.fact_ledger.verdict == "PASS"


@pytest.mark.asyncio
@pytest.mark.parametrize("padded", ["SAMPLE Tasks ", " SAMPLE Tasks"])
async def test_padded_sample_title_recovers_after_the_trim(tmp_path: Path, padded: str) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    sample_id = stored.notification_dashboard.samples[0][1]
    sample = probe.pages[sample_id]
    original = sample.title
    sample.title = padded
    calls = watch_adapter_writes(probe)

    blocked = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert blocked.fact_ledger is not None
    assert blocked.fact_ledger.verdict == "BLOCKED"
    assert _fact(blocked, "dashboard_outputs") == "missing"
    assert padded not in path.read_text(encoding="ascii")
    assert calls == []
    sample.title = original

    recovered = await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert recovered.fact_ledger is not None
    assert recovered.fact_ledger.verdict == "PASS"
    assert _check(recovered, "dashboard_outputs") is True
    assert original in _fact(recovered, "dashboard_outputs")
    assert padded not in _fact(recovered, "dashboard_outputs")


@pytest.mark.asyncio
async def test_blank_sample_title_is_missing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    sample_id = stored.notification_dashboard.samples[0][1]
    sample = probe.pages[sample_id]
    original = sample.title
    sample.title = ""
    calls = watch_adapter_writes(probe)

    blocked = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert blocked.fact_ledger is not None
    assert blocked.fact_ledger.verdict == "BLOCKED"
    assert _fact(blocked, "dashboard_outputs") == "missing"
    assert "sample:" not in _fact(blocked, "dashboard_outputs")
    assert calls == []
    sample.title = original

    recovered = await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert recovered.fact_ledger is not None
    assert recovered.fact_ledger.verdict == "PASS"


@pytest.mark.asyncio
@pytest.mark.parametrize("mark", ["\u200b", "\ufeff"])
async def test_invisible_sample_mark_is_missing(tmp_path: Path, mark: str) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    sample_id = stored.notification_dashboard.samples[0][1]
    sample = probe.pages[sample_id]
    original = sample.title
    sample.title = f"{original}{mark}"
    calls = watch_adapter_writes(probe)

    blocked = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert blocked.fact_ledger is not None
    assert blocked.fact_ledger.verdict == "BLOCKED"
    assert _fact(blocked, "dashboard_outputs") == "missing"
    assert mark not in path.read_text(encoding="ascii")
    assert calls == []
    sample.title = original

    recovered = await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert recovered.fact_ledger is not None
    assert recovered.fact_ledger.verdict == "PASS"


@pytest.mark.asyncio
async def test_semicolon_in_a_formula_expression_is_missing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    kind, _name, property_id = stored.notification_dashboard.formulas[0]
    database_id = next(item_id for item_kind, item_id in stored.database_ids if item_kind == kind)
    prop = next(item for item in probe.databases[database_id].properties if item.id == property_id)
    formula = prop.config["formula"]
    assert type(formula) is NotionFormula
    formula.expression = f"{formula.expression};injected"
    calls = watch_adapter_writes(probe)

    blocked = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert blocked.fact_ledger is not None
    assert blocked.fact_ledger.verdict == "BLOCKED"
    assert _fact(blocked, "dashboard_outputs") == "missing"
    assert "injected" not in path.read_text(encoding="ascii")
    assert calls == []


@pytest.mark.asyncio
async def test_oversized_hub_description_is_not_adopted(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    hub = stored.identity_hubs[0]
    purpose_id = next(block_id for role, block_id in hub.sections if role == "purpose")
    block = probe.blocks[purpose_id]
    assert type(block) is NotionTextBlock
    block.content = f"{spec.identity} / {hub.name} purpose: " + ("x" * 501)
    calls = watch_adapter_writes(probe)
    raw = path.read_bytes()

    message = "fact ledger fact is not a durable string"
    with pytest.raises(ProductBuildError, match=message):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert "x" * 501 not in path.read_text(encoding="ascii")
    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_dashboard_delimiter_is_not_a_fact(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    row = probe.pages[stored.notification_dashboard.row_page_id]
    original = row.title
    row.title = "a;row=Forged"
    calls = watch_adapter_writes(probe)

    blocked = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert blocked.fact_ledger is not None
    assert blocked.fact_ledger.verdict == "BLOCKED"
    assert _fact(blocked, "dashboard_outputs") == "missing"
    assert "row=Forged" not in path.read_text(encoding="ascii")
    assert calls == []
    row.title = original
    sample_id = stored.notification_dashboard.samples[0][1]
    sample = probe.pages[sample_id]
    sample_title = sample.title
    sample.title = " padded"

    still = await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert still.fact_ledger is not None
    assert still.fact_ledger.verdict == "BLOCKED"
    assert _fact(still, "dashboard_outputs") == "missing"
    sample.title = sample_title

    recovered = await run_fact_ledger(
        spec, probe, path, recorded_at=datetime(2026, 10, 7, 7, tzinfo=UTC)
    )

    assert recovered.fact_ledger is not None
    assert recovered.fact_ledger.verdict == "PASS"


@pytest.mark.asyncio
async def test_wrong_hub_shape_stays_refused_until_the_name_matches(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    page = probe.pages[stored.identity_hubs[0].page_id]
    original = page.title
    page.title = "Hub X"
    calls = watch_adapter_writes(probe)

    blocked = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert blocked.fact_ledger is not None
    assert blocked.fact_ledger.verdict == "BLOCKED"
    assert calls == []
    page.title = "Hub Y"
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="fact ledger does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert path.read_bytes() == raw
    page.title = original

    recovered = await run_fact_ledger(
        spec, probe, path, recorded_at=datetime(2026, 10, 7, 7, tzinfo=UTC)
    )

    assert recovered.fact_ledger is not None
    assert recovered.fact_ledger.verdict == "PASS"


@pytest.mark.asyncio
async def test_permuted_check_names_are_incomplete(tmp_path: Path) -> None:
    spec, probe, path = await _blocked_ledger(tmp_path)

    def _swap(document: dict[str, object]) -> None:
        checks = _ledger(document)["checks"]
        assert type(checks) is list
        checks[0], checks[1] = checks[1], checks[0]

    await _refuse(spec, probe, path, _swap, "fact ledger record is incomplete")


@pytest.mark.asyncio
async def test_permuted_fact_names_are_incomplete(tmp_path: Path) -> None:
    spec, probe, path = await _blocked_ledger(tmp_path)

    def _swap(document: dict[str, object]) -> None:
        facts = _ledger(document)["facts"]
        assert type(facts) is list
        facts[0], facts[1] = facts[1], facts[0]

    await _refuse(spec, probe, path, _swap, "fact ledger record is incomplete")


@pytest.mark.asyncio
async def test_check_flag_maybe_is_incomplete(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _maybe(document: dict[str, object]) -> None:
        checks = _ledger(document)["checks"]
        assert type(checks) is list
        row = checks[0]
        assert type(row) is dict
        row["passed"] = "maybe"

    await _refuse(spec, probe, path, _maybe, "fact ledger record is incomplete")


@pytest.mark.asyncio
async def test_forged_repair_required_on_a_pass_refuses(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _lie(document: dict[str, object]) -> None:
        _link(document)["repair_required"] = "true"

    await _refuse(spec, probe, path, _lie, "workflow link does not match")


@pytest.mark.asyncio
async def test_renamed_workflow_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()
    event_map, config = load_workflows_config()
    renamed = config.model_copy(
        update={
            "workflows": tuple(
                item.model_copy(update={"workflow_type": f"Renamed{index}"})
                for index, item in enumerate(config.workflows)
            )
        }
    )

    def _load() -> tuple[object, object]:
        return event_map, renamed

    monkeypatch.setattr(ledger_module, "load_workflows_config", _load)
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="workflow link does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("edge", _PATH_EDGES)
@pytest.mark.parametrize("drop", ["map", "admitted", "successor"])
async def test_each_edge_is_read_three_ways(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    edge: tuple[str, str, str],
    drop: str,
) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()
    predecessor, event, successor = edge

    def _load() -> tuple[dict[str, list[str]], _Bundle]:
        event_map, config = load_workflows_config()
        new_map = {key: list(value) for key, value in event_map.items()}
        if drop == "map":
            new_map[event] = [name for name in new_map[event] if name != successor]
        flows: list[_Flow] = []
        for workflow in config.workflows:
            views: list[_View] = []
            for job in workflow.jobs:
                admitted: tuple[object, ...] = tuple(job.admitted_events)
                successors: tuple[object, ...] = tuple(job.successor_job_types)
                if (
                    workflow.workflow_type == "ProductLifecycleWorkflow"
                    and job.job_type == predecessor
                ):
                    if drop == "admitted":
                        admitted = tuple(item for item in admitted if item != event)
                        if not admitted:
                            admitted = ("DEDUPE_FAILED",)
                    if drop == "successor":
                        successors = tuple(item for item in successors if item != successor)
                views.append(_View(job.job_type, admitted, successors, job.output_contracts))
            flows.append(_Flow(workflow.workflow_type, tuple(views)))
        return new_map, _Bundle(tuple(flows))

    monkeypatch.setattr(ledger_module, "load_workflows_config", _load)
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="workflow link does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["subclass", "spoof"])
async def test_captured_url_must_be_exact_str(tmp_path: Path, kind: str) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    page = probe.pages[stored.variants[0].page_id]
    trusted = str(page.public_url)
    if kind == "subclass":
        page.__dict__["public_url"] = _Url(trusted)
    else:
        page.__dict__["public_url"] = _Spoof(trusted)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "secret_links") is False
    assert _fact(checkpoint, "secret_links").split(",")[0] == "missing"
    assert trusted not in _fact(checkpoint, "secret_links").split(",")[0]
    assert calls == []


@pytest.mark.asyncio
async def test_wrong_host_path_is_stored_as_the_captured_url(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    captured = "https://fixture.notion.site/not-this-page"
    probe.pages[stored.variants[0].page_id].public_url = captured

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert _check(checkpoint, "secret_links") is False
    shown = _fact(checkpoint, "secret_links").split(",")[0]
    assert shown == "https://fixture.notion.site"
    assert "not-this-page" not in shown


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "captured",
    ["ftp://example.com", "https://@", "https://evil;example"],
)
async def test_untrusted_scheme_or_host_is_stored_as_missing(tmp_path: Path, captured: str) -> None:
    """A bad captured URL is the word missing at the public entry.

    Helper ``_redacted_url`` and this entry agree. ``ftp`` kills the scheme
    check. ``https://@`` kills the empty-host check. A semicolon in the host
    kills the delimiter check.
    """
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.variants[0].page_id].public_url = captured

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "secret_links") is False
    assert _fact(checkpoint, "secret_links").split(",")[0] == "missing"
    assert captured not in path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_page_subclass_is_not_accepted(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    home = probe.pages[stored.page_id]
    probe.pages[home.id] = _ChildPage(
        id=home.id,
        title=home.title,
        parent_id=home.parent_id,
        parent_type=home.parent_type,
    )
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="fact ledger page is missing"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_extra_page_subclass_blocks_the_ledger(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    extra = _ChildPage(id="extra-subclass-page", title="Extra")
    probe.pages[extra.id] = extra
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "qa_verdict") is False
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["qa", "fact_ledger", "workflow_link"])
async def test_missing_record_raises_product_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()
    writer = ledger_module.__dict__["_with_records"]

    def _drop(
        stored: ProductBuildCheckpoint,
        qa: object,
        plan: object,
        recorded_at: datetime,
    ) -> ProductBuildCheckpoint:
        built = writer(stored, qa, plan, recorded_at)
        assert isinstance(built, ProductBuildCheckpoint)
        return replace(built, **{field: None})

    monkeypatch.setattr(ledger_module, "_with_records", _drop)

    with pytest.raises(ProductBuildError, match="fact ledger record is missing"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc_type",
    [ConnectionError, OSError, TimeoutError],
)
async def test_live_read_failure_is_a_redacted_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exc_type: type[Exception]
) -> None:
    spec, probe, path = await _qa(tmp_path)

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        raise exc_type("sk-live-secret")

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    await _assert_redacted_read(spec, probe, path)


@pytest.mark.asyncio
async def test_provider_failure_text_is_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, probe, path = await _qa(tmp_path)

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        raise ProviderFailure("fact_ledger.read", "sk-live-secret")

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    await _assert_redacted_read(spec, probe, path)


@pytest.mark.asyncio
async def test_resume_read_failure_is_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        raise ConnectionError("sk-live-secret")

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    with pytest.raises(ProductBuildError, match="provider read failed") as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert "sk-live-secret" not in str(caught.value)
    assert "sk-live-secret" not in path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_runtime_error_is_not_a_provider_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        raise RuntimeError("sk-live-secret")

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)

    with pytest.raises(ProductBuildError, match="fact ledger read failed") as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert "sk-live-secret" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert path.read_bytes() == raw
    assert _jobs(path) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("exc_type", [RuntimeError, Exception, LookupError, ValueError, KeyError])
async def test_code_errors_are_redacted_and_not_provider_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exc_type: type[Exception]
) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        raise exc_type("sk-live-secret")

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)

    with pytest.raises(ProductBuildError, match="fact ledger read failed") as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert "sk-live-secret" not in str(caught.value)
    assert caught.value.__cause__ is None
    context = caught.value.__context__
    if context is not None:
        assert "sk-live-secret" not in str(context)
        assert context.__cause__ is None or "sk-live-secret" not in str(context.__cause__)
    assert path.read_bytes() == raw
    assert _jobs(path) == []


@pytest.mark.asyncio
async def test_provider_product_error_does_not_carry_a_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A provider ProductBuildError is redacted. It is not re-raised raw."""
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        raise ProductBuildError("sk-live-secret")

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    with pytest.raises(ProductBuildError, match="fact ledger read failed") as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert "sk-live-secret" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert path.read_bytes() == raw
    assert _jobs(path) == []


@pytest.mark.asyncio
async def test_chained_secret_is_not_left_on_the_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A secret in __cause__ does not survive on the error that leaves."""
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        try:
            raise RuntimeError("sk-live-secret")
        except RuntimeError as inner:
            raise RuntimeError("outer") from inner

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    with pytest.raises(ProductBuildError, match="fact ledger read failed") as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert "sk-live-secret" not in str(caught.value)
    assert caught.value.__cause__ is None
    context = caught.value.__context__
    assert context is None or context.__cause__ is None
    if context is not None and context.__cause__ is not None:
        assert "sk-live-secret" not in str(context.__cause__)
    assert path.read_bytes() == raw
    assert _jobs(path) == []


@pytest.mark.asyncio
async def test_repeated_provider_failure_is_one_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, probe, path = await _qa(tmp_path)

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        raise ConnectionError("sk-live-secret")

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    with pytest.raises(ProductBuildError, match="provider read failed"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    with pytest.raises(ProductBuildError, match="provider read failed"):
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    jobs = [
        job for job in _jobs(path) if type(job) is dict and job.get("kind") == "provider_response"
    ]
    assert len(jobs) == 1
    assert "sk-live-secret" not in path.read_text(encoding="utf-8")


def _provider_jobs(path: Path) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for job in _jobs(path):
        if type(job) is dict and job.get("kind") == "provider_response":
            found.append(job)
    return found


@pytest.mark.asyncio
async def test_a_second_distinct_provider_failure_is_kept(tmp_path: Path) -> None:
    """Same operation and phase, different response: both jobs stay."""
    _spec, _probe, path = await _qa(tmp_path)
    phase = "aesthetics_and_content_completion"
    record_provider_failure(path, "fact_ledger.read", "provider read failed", phase)
    record_provider_failure(path, "fact_ledger.read", "different failure", phase)
    jobs = _provider_jobs(path)
    assert len(jobs) == 2
    assert {job["response"] for job in jobs} == {"provider read failed", "different failure"}


@pytest.mark.asyncio
async def test_provider_failures_on_different_operations_are_kept(tmp_path: Path) -> None:
    _spec, _probe, path = await _qa(tmp_path)
    phase = "aesthetics_and_content_completion"
    record_provider_failure(path, "fact_ledger.read", "provider read failed", phase)
    record_provider_failure(path, "fact_ledger.write", "provider read failed", phase)
    assert len(_provider_jobs(path)) == 2


@pytest.mark.asyncio
async def test_provider_failures_on_different_phases_are_kept(tmp_path: Path) -> None:
    _spec, _probe, path = await _qa(tmp_path)
    record_provider_failure(path, "fact_ledger.read", "provider read failed", "shared_databases")
    record_provider_failure(
        path, "fact_ledger.read", "provider read failed", "aesthetics_and_content_completion"
    )
    assert len(_provider_jobs(path)) == 2


@pytest.mark.asyncio
async def test_provider_stream_job_counts_are_exact(tmp_path: Path) -> None:
    """DIFF_PHASE, DIFF_OP, DIFF_KIND, and SAME are 2, 2, 2, and 1.

    Forcing the kind, operation, or phase compare to True, or flipping either
    ``and`` to ``or``, changes one of these counts.
    """
    phase = "aesthetics_and_content_completion"
    response = "provider read failed"
    counts: list[int] = []
    for label in ("diff-phase", "diff-op", "diff-kind", "same"):
        _spec, _probe, path = await _qa(tmp_path / label)
        if label == "diff-phase":
            record_provider_failure(path, "fact_ledger.read", response, "shared_databases")
            record_provider_failure(path, "fact_ledger.read", response, phase)
        elif label == "diff-op":
            record_provider_failure(path, "fact_ledger.read", response, phase)
            record_provider_failure(path, "fact_ledger.write", response, phase)
        elif label == "diff-kind":
            append_refused_rebuild(path, response)
            record_provider_failure(path, OP_REBUILD, response, PHASES[0])
        elif label == "same":
            record_provider_failure(path, "fact_ledger.read", response, phase)
            record_provider_failure(path, "fact_ledger.read", response, phase)
        else:
            raise AssertionError(label)
        counts.append(len(_jobs(path)))
    assert counts == [2, 2, 2, 1]


@pytest.mark.asyncio
async def test_two_rebuild_refusals_are_kept(tmp_path: Path) -> None:
    """A rebuild refusal is not collapsed with another refusal."""
    _spec, _probe, path = await _qa(tmp_path)
    append_refused_rebuild(path, "first rebuild stays")
    append_refused_rebuild(path, "second rebuild stays")
    kept = [
        job for job in _jobs(path) if type(job) is dict and job.get("kind") == "rebuild_refused"
    ]
    assert len(kept) == 2
    assert {job["response"] for job in kept} == {"first rebuild stays", "second rebuild stays"}


@pytest.mark.asyncio
async def test_prior_rebuild_job_survives_the_ledger_write(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    append_refused_rebuild(path, "prior rebuild stays")

    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    kept = [
        job for job in _jobs(path) if type(job) is dict and job.get("kind") == "rebuild_refused"
    ]
    assert len(kept) == 1
    assert kept[0]["response"] == "prior rebuild stays"


@pytest.mark.asyncio
async def test_temp_names_are_matched_literally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, probe, path = await _qa(tmp_path)
    weird = tmp_path / "b[x].json"
    weird.write_bytes(path.read_bytes())
    unrelated = tmp_path / ".bx.json.999.tmp"
    unrelated.write_text("keep\n", encoding="ascii")
    notes = tmp_path / "notes.tmp"
    cache = tmp_path / "unrelated-cache.tmp"
    other = tmp_path / ".other.json.4242.tmp"
    notes.write_text("notes\n", encoding="ascii")
    cache.write_text("cache\n", encoding="ascii")
    other.write_text("other\n", encoding="ascii")
    dead = tmp_path / ".b[x].json.999.tmp"
    dead.write_text("dead\n", encoding="ascii")
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    live = tmp_path / f".b[x].json.{process.pid}.tmp"
    live.write_text("live\n", encoding="ascii")

    def _alive(pid: int) -> bool:
        return pid == process.pid

    monkeypatch.setattr(progress_module, "_pid_alive", _alive)
    try:
        await run_fact_ledger(spec, probe, weird, recorded_at=LEDGER_AT)
        assert unrelated.exists()
        assert notes.exists()
        assert cache.exists()
        assert other.exists()
        assert not dead.exists()
        assert live.exists()
        assert os.getpid() != process.pid
    finally:
        process.kill()
        process.wait()


def _role_block(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, index: int, role: str
) -> NotionTextBlock:
    hub = stored.identity_hubs[index]
    block_id = dict(hub.sections)[role]
    block = probe.blocks[block_id]
    assert type(block) is NotionTextBlock
    return block


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "scope"),
    [
        ("purpose", "one"),
        ("purpose", "all"),
        ("buyer", "all"),
        ("practice", "all"),
    ],
)
async def test_edited_hub_prose_is_blocked_not_self_compared(
    tmp_path: Path, role: str, scope: str
) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    indexes = range(1) if scope == "one" else range(len(stored.identity_hubs))
    for index in indexes:
        block = _role_block(probe, stored, index, role)
        suffix = {
            "purpose": "Edited live purpose",
            "buyer": "Edited buyer",
            "practice": "Edited practice",
        }[role]
        block.content = block.content + suffix
    derived_hubs = tuple(
        Hub(
            name=hub.name,
            description=hub.description + "Edited live purpose"
            if role == "purpose" and index in indexes
            else hub.description,
            page_count=hub.page_count,
        )
        for index, hub in enumerate(spec.hubs)
    )
    derived = spec.model_copy(
        update={
            "hubs": derived_hubs,
            "buyer_problem": spec.buyer_problem + "Edited buyer"
            if role == "buyer"
            else spec.buyer_problem,
            "flagship_feature": spec.flagship_feature + "Edited practice"
            if role == "practice"
            else spec.flagship_feature,
        }
    )
    assert await live_qa_passed(probe, stored, derived) is True
    calls = watch_adapter_writes(probe)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.workflow_link is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert checkpoint.workflow_link.ready == ""
    assert checkpoint.next_phase == PHASE_TEST_MATRIX
    stored_progress = json.loads(path.read_text(encoding="utf-8"))["progress"]
    assert stored_progress["next_phase"] == checkpoint.next_phase
    assert _check(checkpoint, "qa_verdict") is False
    assert calls == []


def _mismatched_caller(spec: ProductSpec, kind: str) -> ProductSpec:
    """A caller that is not the hub set QA judged."""
    if kind == "forged":
        return spec.model_copy(update={"identity": "Not The Row"})
    if kind == "renamed":
        renamed = tuple(
            Hub(
                name="Other " + hub.name,
                description=hub.description,
                page_count=hub.page_count,
            )
            for hub in spec.hubs
        )
        return spec.model_copy(update={"hubs": renamed})
    if kind == "rotated":
        return spec.model_copy(update={"hubs": (*spec.hubs[1:], spec.hubs[0])})
    raise AssertionError(kind)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "scope"),
    [
        ("purpose", "one"),
        ("purpose", "all"),
        ("buyer", "all"),
        ("practice", "all"),
    ],
)
@pytest.mark.parametrize("caller_kind", ["forged", "renamed", "rotated"])
async def test_unnamed_caller_cannot_adopt_a_live_hub_edit(
    tmp_path: Path, role: str, scope: str, caller_kind: str
) -> None:
    """Twelve combinations. A post-QA edit plus a mismatched caller is a refusal.

    One purpose edit is hub 2. All-purpose, all-buyer, and all-practice edits
    cover the other three. Identity ``Not The Row``, hubs named ``Other `` plus
    the judged name, and rotated hubs are the three callers. QA does not pass
    the same pair. The first call writes nothing, so a resume cannot keep a PASS.
    """
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    indexes = (2,) if scope == "one" else range(len(stored.identity_hubs))
    suffix = {
        "purpose": "Edited live purpose",
        "buyer": "Edited buyer",
        "practice": "Edited practice",
    }[role]
    for index in indexes:
        block = _role_block(probe, stored, index, role)
        block.content = block.content + suffix
    caller = _mismatched_caller(spec, caller_kind)
    try:
        qa_passed = await live_qa_passed(probe, stored, caller)
    except ProductBuildError:
        qa_passed = False
    assert qa_passed is False
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="fact ledger caller does not match"):
        await run_fact_ledger(caller, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("caller_kind", ["forged", "renamed"])
async def test_stored_blocked_is_not_overwritten_on_a_forged_resume(
    tmp_path: Path, caller_kind: str
) -> None:
    """An honest BLOCKED ledger stays BLOCKED when a mismatched caller resumes.

    ``_saved_holds`` must not return false and let ``_plan`` write PASS.
    """
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    block = _role_block(probe, stored, 2, "purpose")
    block.content = block.content + "Edited live purpose"
    blocked = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert blocked.fact_ledger is not None
    assert blocked.fact_ledger.verdict == "BLOCKED"
    assert blocked.next_phase == PHASE_TEST_MATRIX
    on_disk = json.loads(path.read_text(encoding="utf-8"))["progress"]["next_phase"]
    assert on_disk == blocked.next_phase
    raw = path.read_bytes()
    caller = _mismatched_caller(spec, caller_kind)

    with pytest.raises(ProductBuildError, match="fact ledger caller does not match"):
        await run_fact_ledger(caller, probe, path, recorded_at=LATER)

    assert path.read_bytes() == raw
    ledger = _references(path)["fact_ledger"]
    assert type(ledger) is dict
    assert ledger["verdict"] == "BLOCKED"


@pytest.mark.asyncio
@pytest.mark.parametrize("caller_kind", ["forged", "renamed"])
async def test_forged_caller_does_not_return_a_stale_pass(tmp_path: Path, caller_kind: str) -> None:
    """A stored PASS plus a live edit is not returned to a mismatched caller."""
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    stored, _created = load_variant_checkpoint(path)
    block = _role_block(probe, stored, 2, "purpose")
    block.content = block.content + "Edited live purpose"
    raw = path.read_bytes()
    caller = _mismatched_caller(spec, caller_kind)

    with pytest.raises(ProductBuildError, match="fact ledger caller does not match"):
        await run_fact_ledger(caller, probe, path, recorded_at=LATER)

    assert path.read_bytes() == raw
    ledger = _references(path)["fact_ledger"]
    assert type(ledger) is dict
    assert ledger["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_row_title_is_not_the_identity(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    notice = stored.notification_dashboard
    assert notice is not None
    row = probe.pages[notice.row_page_id]
    assert row.properties.get("Name") == spec.identity
    row.title = "Weekly Planner Pro"

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert _check(checkpoint, "qa_verdict") is True


@pytest.mark.asyncio
@pytest.mark.parametrize("forged", [False, True])
async def test_unresolved_section_block_refuses(tmp_path: Path, forged: bool) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    block = _role_block(probe, stored, 0, "buyer")
    moved = replace(block, id="buyer-block-moved")
    del probe.blocks[block.id]
    probe.blocks[moved.id] = moved
    used = spec.model_copy(update={"buyer_problem": "forged buyer"}) if forged else spec
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="fact ledger section is missing"):
        await run_fact_ledger(used, probe, path, recorded_at=LEDGER_AT)

    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["mass", "solo", "x"])
async def test_caller_tier_does_not_override_stored_kinds(tmp_path: Path, tier: str) -> None:
    spec, probe, path = await _qa(
        tmp_path,
        tier="business",
        identity="Studio Ledger",
        title="Studio Home",
        hub_name="Desk",
    )
    mutated = spec.model_copy(update={"tier": tier})

    checkpoint = await run_fact_ledger(mutated, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"


@pytest.mark.asyncio
async def test_tampered_hub_name_refuses_before_a_write(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)

    def _rename(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        hubs = references["identity_hubs"]
        assert type(hubs) is list
        row = hubs[0]
        assert type(row) is dict
        row["name"] = "X"

    restamp_checkpoint(path, _rename)
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_overlong_hub_name_is_a_product_error(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    long_name = "H" * 65
    hub = stored.identity_hubs[0]
    for role, _block_id in hub.sections:
        block = _role_block(probe, stored, 0, role)
        prefix = f"{spec.identity} / {hub.name} {role}: "
        assert block.content.startswith(prefix)
        detail = block.content[len(prefix) :]
        block.content = f"{spec.identity} / {long_name} {role}: {detail}"

    def _rename(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        hubs = references["identity_hubs"]
        assert type(hubs) is list
        row = hubs[0]
        assert type(row) is dict
        row["name"] = long_name

    restamp_checkpoint(path, _rename)

    message = "fact ledger fact is not a durable string"
    with pytest.raises(ProductBuildError, match=message) as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert "ValidationError" not in type(caught.value).__name__
    assert long_name not in str(caught.value)


@pytest.mark.asyncio
async def test_whitespace_purpose_is_not_a_validation_error(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    block = _role_block(probe, stored, 0, "purpose")
    prefix = f"{spec.identity} / {stored.identity_hubs[0].name} purpose: "
    assert block.content.startswith(prefix)
    block.content = prefix + "   "
    forged = spec.model_copy(update={"identity": "Not The Row"})
    raw = path.read_bytes()

    message = "fact ledger fact is not a durable string"
    with pytest.raises(ProductBuildError, match=message) as caught:
        await run_fact_ledger(forged, probe, path, recorded_at=LEDGER_AT)

    assert "sk-live-secret" not in str(caught.value)
    assert "ValidationError" not in type(caught.value).__name__
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_blocked_resume_after_the_live_fix_stays_blocked(tmp_path: Path) -> None:
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
    raw = path.read_bytes()
    writes, original = _watch_checkpoint_writes()
    try:
        again = await run_fact_ledger(spec, probe, path, recorded_at=LATER)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]

    assert again.fact_ledger is not None
    assert again.fact_ledger.verdict == "BLOCKED"
    assert writes["n"] == 0
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_query_token_is_not_stored(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    page = probe.pages[stored.variants[0].page_id]
    page.public_url = str(page.public_url) + "?token=sk-live-secret"

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert _check(checkpoint, "secret_links") is False
    shown = _fact(checkpoint, "secret_links").split(",")[0]
    assert "sk-live-secret" not in shown
    assert "?" not in shown
    assert "sk-live-secret" not in path.read_text(encoding="utf-8")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["extra", "cycle"])
async def test_extra_or_cyclic_successor_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    def _load() -> tuple[dict[str, list[str]], _Bundle]:
        event_map, config = load_workflows_config()
        new_map = {key: list(value) for key, value in event_map.items()}
        flows: list[_Flow] = []
        for workflow in config.workflows:
            views: list[_View] = []
            for job in workflow.jobs:
                successors = tuple(job.successor_job_types)
                if workflow.workflow_type == "ProductLifecycleWorkflow":
                    if mode == "extra" and job.job_type == "ScreenshotJob":
                        successors = (*successors, "ExtraJob")
                    if mode == "cycle" and job.job_type == "ProductBuildJob":
                        successors = (*successors, "ProductBuildJob")
                views.append(
                    _View(
                        job.job_type,
                        tuple(job.admitted_events),
                        successors,
                        job.output_contracts,
                    )
                )
            flows.append(_Flow(workflow.workflow_type, tuple(views)))
        return new_map, _Bundle(tuple(flows))

    monkeypatch.setattr(ledger_module, "load_workflows_config", _load)

    with pytest.raises(ProductBuildError, match="workflow link does not match"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_temp_cleanup_keeps_unrelated_names(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stray = tmp_path / ".build.json.abc.tmp"
    backup = tmp_path / ".build.json.backup"
    zero = tmp_path / ".build.json.0.tmp"
    stray.write_text("stray\n", encoding="ascii")
    backup.write_text("backup\n", encoding="ascii")
    zero.write_text("zero\n", encoding="ascii")

    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert not stray.exists()
    assert backup.exists()
    assert not zero.exists()


@pytest.mark.asyncio
async def test_foreign_pid_temp_is_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec, probe, path = await _qa(tmp_path)
    foreign = tmp_path / ".build.json.424242.tmp"
    foreign.write_text("foreign\n", encoding="ascii")

    def _kill(pid: int, _signal: int) -> None:
        raise PermissionError(pid)

    monkeypatch.setattr(progress_module.os, "kill", _kill)

    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert foreign.exists()


@pytest.mark.asyncio
async def test_whitespace_purpose_on_the_built_spec_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    block = _role_block(probe, stored, 0, "purpose")
    prefix = f"{spec.identity} / {stored.identity_hubs[0].name} purpose: "
    assert block.content.startswith(prefix)
    block.content = prefix + "   "
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    message = "fact ledger fact is not a durable string"
    with pytest.raises(ProductBuildError, match=message) as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert "ValidationError" not in type(caught.value).__name__
    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_row_subclass_is_a_missing_identity(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    notice = stored.notification_dashboard
    assert notice is not None
    row = probe.pages[notice.row_page_id]
    probe.pages[row.id] = _ChildPage(
        id=row.id,
        title=row.title,
        parent_id=row.parent_id,
        parent_type=row.parent_type,
        properties={"Name": "Forged Name"},
    )
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="fact ledger identity is missing"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_padded_row_name_is_a_missing_identity(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    notice = stored.notification_dashboard
    assert notice is not None
    row = probe.pages[notice.row_page_id]
    row.properties["Name"] = " " + spec.identity
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="fact ledger identity is missing"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert path.read_bytes() == raw
    assert " " + spec.identity not in path.read_text(encoding="ascii")


@pytest.mark.asyncio
async def test_non_text_purpose_block_is_refused(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    block = _role_block(probe, stored, 0, "purpose")
    probe.blocks[block.id] = NotionCalloutBlock(
        id=block.id,
        parent_id=block.parent_id,
        content=block.content,
    )
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="fact ledger section is missing"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_numeric_purpose_content_is_a_product_error(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    block = _role_block(probe, stored, 0, "purpose")
    block.__dict__["content"] = 5
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="fact ledger section is missing") as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert "AttributeError" not in type(caught.value).__name__
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_numeric_sample_title_is_missing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    sample_id = stored.notification_dashboard.samples[0][1]
    probe.pages[sample_id].__dict__["title"] = 1

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _fact(checkpoint, "dashboard_outputs") == "missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["business", "solo", "x"])
async def test_caller_tier_does_not_override_mass_kinds(tmp_path: Path, tier: str) -> None:
    spec, probe, path = await _qa(tmp_path)
    mutated = spec.model_copy(update={"tier": tier})

    checkpoint = await run_fact_ledger(mutated, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("duplicate", "checkpoint databases do not match a tier"),
        ("custom", "checkpoint databases do not match a tier"),
        ("five-hubs", "checkpoint hubs must be six to eight"),
        ("nine-hubs", "checkpoint hubs must be six to eight"),
        ("empty-facts", "fact ledger record is incomplete"),
        ("empty-checks", "fact ledger record is incomplete"),
        ("foreign-check", "fact ledger record is incomplete"),
    ],
)
async def test_verifier_shapes_are_refused(tmp_path: Path, mode: str, message: str) -> None:
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _mutate(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        if mode in {"empty-facts", "empty-checks", "foreign-check"}:
            ledger = references["fact_ledger"]
            assert type(ledger) is dict
            if mode == "empty-facts":
                ledger["facts"] = []
                return
            if mode == "empty-checks":
                ledger["checks"] = []
                return
            checks = ledger["checks"]
            assert type(checks) is list
            row = checks[0]
            assert type(row) is dict
            row["check"] = "foreign_check"
            return
        if mode in {"duplicate", "custom"}:
            shared = references["shared_databases"]
            assert type(shared) is list
            first = shared[0]
            second = shared[1]
            assert type(first) is dict and type(second) is dict
            second["kind"] = first["kind"] if mode == "duplicate" else "Custom"
            return
        hubs = references["identity_hubs"]
        assert type(hubs) is list
        if mode == "five-hubs":
            del hubs[-1]
            return
        for extra_index in range(3):
            extra = dict(hubs[-1])
            assert type(extra) is dict
            label = f"Hub {7 + extra_index}"
            extra["name"] = label
            extra["page_id"] = f"page-{label}"
            extra["navigation_block_id"] = f"nav-{label}"
            sections = extra["sections"]
            assert type(sections) is list
            extra["sections"] = [
                {"role": item["role"], "block_id": f"block-{label}-{item['role']}"}
                for item in sections
                if type(item) is dict
            ]
            views = extra["views"]
            assert type(views) is list
            extra["views"] = [
                {"slug": item["slug"], "view_id": f"view-{label}-{index}"}
                for index, item in enumerate(views)
                if type(item) is dict
            ]
            hubs.append(extra)

    await _refuse(spec, probe, path, _mutate, message)


@pytest.mark.asyncio
async def test_legal_bounds_pass_and_one_past_refuses(tmp_path: Path) -> None:
    """64, 500, and 8 pass. The test itself then runs 65 and 9, which refuse."""
    long_name = "N" * 64
    long_copy = "D" * 500
    base = planner_spec()
    hubs = tuple(
        Hub(
            name=long_name if index == 1 else f"Hub {index}",
            description=long_copy if index == 1 else f"Weekly Planner copy {index}",
            page_count=3,
        )
        for index in range(1, 9)
    )
    spec = base.model_copy(update={"hubs": hubs})
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert len(spec.hubs) == 8
    assert _fact(checkpoint, "hubs").split(",")[0] == long_name
    stored, _created = load_variant_checkpoint(path)
    block = _role_block(probe, stored, 0, "purpose")
    block.content = block.content + "x"
    raw = path.read_bytes()

    message = "fact ledger fact is not a durable string"
    with pytest.raises(ProductBuildError, match=message):
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert path.read_bytes() == raw
    require_name = ledger_module._require_hub_name  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match=message):
        require_name(SimpleNamespace(name="N" * 65))
    require_count = ledger_module._require_hub_count  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match=message):
        require_count(cast(ProductBuildCheckpoint, SimpleNamespace(identity_hubs=tuple(range(9)))))
    too_long = "N" * 65
    hub = stored.identity_hubs[0]
    for role, _block_id in hub.sections:
        edited = _role_block(probe, stored, 0, role)
        prefix = f"{spec.identity} / {hub.name} {role}: "
        assert edited.content.startswith(prefix)
        detail = edited.content[len(prefix) :]
        edited.content = f"{spec.identity} / {too_long} {role}: {detail}"

    def _rename(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        rows = references["identity_hubs"]
        assert type(rows) is list
        row = rows[0]
        assert type(row) is dict
        row["name"] = too_long

    restamp_checkpoint(path, _rename)
    with pytest.raises(ProductBuildError, match=message):
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)

    def _nine(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        rows = references["identity_hubs"]
        assert type(rows) is list
        for extra_index in range(3):
            extra = dict(rows[-1])
            assert type(extra) is dict
            label = f"Hub {7 + extra_index}"
            extra["name"] = label
            extra["page_id"] = f"page-{label}"
            rows.append(extra)

    restamp_checkpoint(path, _nine)
    with pytest.raises(ProductBuildError, match="checkpoint hubs must be six to eight"):
        await run_fact_ledger(spec, probe, path, recorded_at=LATER)


@pytest.mark.asyncio
async def test_unnamed_sixty_four_character_hub_name_passes(tmp_path: Path) -> None:
    """A mismatched caller with a 64-character hub name passes.

    ``_require_hub_name`` allows 64 and refuses 65, on the named path and on
    this one. The detail check repeats that name rule and is not what refuses 65.
    """
    long_name = "H" * 64
    base = planner_spec()
    hubs = tuple(
        Hub(
            name=long_name if index == 1 else f"Hub {index}",
            description=f"Weekly Planner copy {index}",
            page_count=3,
        )
        for index in range(1, 9)
    )
    spec = base.model_copy(update={"hubs": hubs})
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    caller = spec.model_copy(update={"identity": "Not The Row"})
    writes, original = _watch_checkpoint_writes()
    try:
        checkpoint = await run_fact_ledger(caller, probe, path, recorded_at=LEDGER_AT)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]

    assert writes["n"] == 1
    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert _fact(checkpoint, "hubs").split(",")[0] == long_name


@pytest.mark.asyncio
async def test_long_buyer_passes_on_named_and_unnamed_paths(tmp_path: Path) -> None:
    """501 to 1000 characters are legal for the buyer on both paths."""
    buyer = "B" * 600
    spec = planner_spec().model_copy(update={"buyer_problem": buyer})
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    stored, _created = load_variant_checkpoint(path)
    detail = ledger_module._durable_detail  # pyright: ignore[reportPrivateUsage]
    assert detail(probe, stored.identity_hubs[0], spec.identity, "buyer") == buyer
    named = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert named.fact_ledger is not None and named.fact_ledger.verdict == "PASS"
    caller = spec.model_copy(update={"identity": "Not The Row"})
    unnamed = await run_fact_ledger(caller, probe, path, recorded_at=LATER)
    assert unnamed.fact_ledger is not None and unnamed.fact_ledger.verdict == "PASS"


def test_empty_pair_list_is_incomplete() -> None:
    """An empty fact or check list is incomplete. It is not an empty tuple."""
    require_pairs = ledger_module._require_pairs  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="fact ledger record is incomplete"):
        require_pairs([], "fact", "value")


def test_pass_with_a_false_check_is_not_stored() -> None:
    """A PASS record that contains a false check is not a ledger source."""
    require_stored = ledger_module._require_stored_qa  # pyright: ignore[reportPrivateUsage]
    record = QaRecord(
        verdict="PASS",
        checks=(("qa_verdict", False),),
        repairs=(),
        proof_page_id="proof",
        facts=(("page_count", "15"),),
        prose_digest="0" * 64,
    )
    with pytest.raises(ProductBuildError, match="qa record does not match"):
        require_stored(record, False)


def test_hub_count_accepts_six_through_eight() -> None:
    """Five and nine hubs are refused. Six and eight are a product fact."""
    require_count = ledger_module._require_hub_count  # pyright: ignore[reportPrivateUsage]
    for count in (6, 8):
        hubs = tuple(range(count))
        require_count(cast(ProductBuildCheckpoint, SimpleNamespace(identity_hubs=hubs)))
    for count in (5, 9):
        with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
            require_count(
                cast(ProductBuildCheckpoint, SimpleNamespace(identity_hubs=tuple(range(count))))
            )


def test_hub_name_bounds_are_a_product_error() -> None:
    """A hub name is a token of at most 64 characters."""
    require_name = ledger_module._require_hub_name  # pyright: ignore[reportPrivateUsage]
    require_name(SimpleNamespace(name="N" * 64))
    for name in (5, "", " padded", "N" * 65):
        with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
            require_name(SimpleNamespace(name=name))


def test_tier_follows_the_stored_kind_set() -> None:
    """Duplicate kinds are neither mass nor business. A same-length foreign set is neither."""
    tier_from = ledger_module._tier_from_kinds  # pyright: ignore[reportPrivateUsage]
    assert tier_from(PLANNER_SHARED_DATABASES) == "mass"
    assert tier_from(BUSINESS_SHARED_DATABASES) == "business"
    assert tier_from((*PLANNER_SHARED_DATABASES, PLANNER_SHARED_DATABASES[0])) == ""
    assert tier_from((*BUSINESS_SHARED_DATABASES, BUSINESS_SHARED_DATABASES[0])) == ""
    foreign = tuple(f"Kind {index}" for index in range(len(BUSINESS_SHARED_DATABASES)))
    assert tier_from(foreign) == ""


def test_redacted_url_drops_a_bare_token() -> None:
    """Scheme and host only. Userinfo, a path, a query, and a bare token are not stored."""
    redact = ledger_module._redacted_url  # pyright: ignore[reportPrivateUsage]
    assert redact(cast(str, 5)) == "missing"
    assert redact("?") == "missing"
    assert redact("sk-live-secret") == "missing"
    assert redact("http://fixture.notion.site/page ?dropped") == "missing"
    secret = "sk-live-secret"
    userinfo = redact("https://user:" + secret + "@evil.example/p")
    path_token = redact("https://evil.example/" + secret)
    assert userinfo == "https://evil.example"
    assert path_token == "https://evil.example"
    assert secret not in userinfo
    assert secret not in path_token
    assert "/" + secret not in path_token
    # A non-http scheme, an empty host, and a delimiter in the host are missing.
    # Forcing those operands to False, or flipping the surrounding ``or``, stores them.
    assert redact("ftp://example.com") == "missing"
    assert redact("https://@") == "missing"
    assert redact("https://evil;example") == "missing"
    assert redact("http://") == "missing"
    assert redact("notaurl") == "missing"


@pytest.mark.asyncio
async def test_caller_identity_must_match_the_row(tmp_path: Path) -> None:
    """Same hub names and a different identity are not the caller's spec."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    identity = ledger_module._stable_identity(probe, stored)  # pyright: ignore[reportPrivateUsage]
    matches = ledger_module._caller_matches  # pyright: ignore[reportPrivateUsage]
    assert matches(spec, stored, identity) is True
    forged = spec.model_copy(update={"identity": "Other Identity"})
    assert matches(forged, stored, identity) is False


@pytest.mark.asyncio
async def test_section_shape_is_a_pair(tmp_path: Path) -> None:
    """A list section and a 3-tuple are missing. They are not the purpose copy."""
    _spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    block = _role_block(probe, stored, 0, "purpose")
    section = ledger_module._section_block  # pyright: ignore[reportPrivateUsage]
    message = "fact ledger section is missing"
    listed = SimpleNamespace(sections=(["purpose", block.id],))
    triple = SimpleNamespace(sections=(("purpose", block.id, "extra"),))
    with pytest.raises(ProductBuildError, match=message):
        section(probe, listed, "purpose")
    with pytest.raises(ProductBuildError, match=message):
        section(probe, triple, "purpose")


@pytest.mark.asyncio
async def test_detail_bounds_are_a_product_error(tmp_path: Path) -> None:
    """500 characters of purpose copy pass. 501, padding, and a 65-character name do not."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    hub = stored.identity_hubs[0]
    block = _role_block(probe, stored, 0, "purpose")
    prefix = f"{spec.identity} / {hub.name} purpose: "
    detail_of = ledger_module._durable_detail  # pyright: ignore[reportPrivateUsage]
    refuse = ledger_module._refuse_undurable_purpose  # pyright: ignore[reportPrivateUsage]
    block.content = prefix
    refuse(block, spec.identity, hub.name)
    block.content = prefix + ("D" * 500)
    assert detail_of(probe, hub, spec.identity, "purpose") == "D" * 500
    message = "fact ledger fact is not a durable string"
    block.content = prefix + ("D" * 501)
    with pytest.raises(ProductBuildError, match=message):
        detail_of(probe, hub, spec.identity, "purpose")
    block.content = prefix + " padded"
    with pytest.raises(ProductBuildError, match=message):
        detail_of(probe, hub, spec.identity, "purpose")
    legal_name = "H" * 64
    block.content = f"{spec.identity} / {legal_name} purpose: copy"
    legal = SimpleNamespace(name=legal_name, sections=hub.sections)
    assert detail_of(probe, legal, spec.identity, "purpose") == "copy"
    for name in (5, "", " padded", "H" * 65):
        shown = name if type(name) is str else "5"
        block.content = f"{spec.identity} / {shown} purpose: copy"
        bad = SimpleNamespace(name=name, sections=hub.sections)
        with pytest.raises(ProductBuildError, match=message):
            detail_of(probe, bad, spec.identity, "purpose")


@pytest.mark.asyncio
async def test_row_name_must_be_a_token(tmp_path: Path) -> None:
    """An empty Name and a numeric Name are a missing identity."""
    _spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    notice = stored.notification_dashboard
    assert notice is not None
    row = probe.pages[notice.row_page_id]
    identity = ledger_module._stable_identity  # pyright: ignore[reportPrivateUsage]
    row.properties["Name"] = ""
    with pytest.raises(ProductBuildError, match="fact ledger identity is missing"):
        identity(probe, stored)
    row.properties["Name"] = 5
    with pytest.raises(ProductBuildError, match="fact ledger identity is missing"):
        identity(probe, stored)


@pytest.mark.asyncio
async def test_blocked_all_true_checks_are_not_a_pass(tmp_path: Path) -> None:
    """BLOCKED with every check true does not plan qa_verdict true."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    qa = load_qa_record(path)
    assert qa is not None
    steps = ledger_module._walk_chain()  # pyright: ignore[reportPrivateUsage]
    plan = ledger_module._plan  # pyright: ignore[reportPrivateUsage]
    true_checks = tuple((name, True) for name, _flag in qa.checks)
    blocked = replace(qa, verdict="BLOCKED", checks=true_checks)
    blocked_plan = await plan(probe, stored, spec, blocked, steps)
    assert dict(blocked_plan.checks)["qa_verdict"] is False
    mixed = replace(
        qa,
        checks=tuple((name, name != "hubs_present") for name, _flag in qa.checks),
    )
    mixed_plan = await plan(probe, stored, spec, mixed, steps)
    assert dict(mixed_plan.checks)["qa_verdict"] is False


@pytest.mark.asyncio
async def test_empty_variants_still_require_the_qa_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A QA record with no variants is not a ledger checkpoint."""
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    def _drop(checkpoint_path: Path) -> tuple[ProductBuildCheckpoint, Mapping[str, object]]:
        stored, created = load_variant_checkpoint(checkpoint_path)
        return replace(stored, variants=()), created

    monkeypatch.setattr(ledger_module, "load_variant_checkpoint", _drop)
    with pytest.raises(ProductBuildError, match="fact ledger requires the qa checkpoint"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_a_changed_blocked_check_is_replanned(tmp_path: Path) -> None:
    """Facts can match while one stored check does not. That ledger is replanned."""
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
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _flip(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        ledger = references["fact_ledger"]
        assert type(ledger) is dict
        checks = ledger["checks"]
        assert type(checks) is list
        for row in checks:
            assert type(row) is dict
            if row["passed"] == "true":
                row["passed"] = "false"
                return

    restamp_checkpoint(path, _flip)
    raw = path.read_bytes()
    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LATER)
    assert path.read_bytes() != raw
    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"


class _Liar(str):
    """A str subclass whose equality claims to match any non-empty string."""

    def __eq__(self, other: object) -> bool:
        return other != ""

    def __ne__(self, other: object) -> bool:
        return False


@pytest.mark.asyncio
async def test_lying_formula_expression_is_blocked(tmp_path: Path) -> None:
    """Liar("x;y") on current_date is not an exact str, so the ledger stays BLOCKED."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    current = next(
        (kind, property_id)
        for kind, name, property_id in stored.notification_dashboard.formulas
        if name == "current_date"
    )
    kind, property_id = current
    database_id = next(item_id for item_kind, item_id in stored.database_ids if item_kind == kind)
    prop = next(item for item in probe.databases[database_id].properties if item.id == property_id)
    formula = prop.config["formula"]
    assert type(formula) is NotionFormula
    formula.expression = _Liar("x;y")
    read_expression = ledger_module._formula_expression  # pyright: ignore[reportPrivateUsage]
    assert read_expression(probe, stored, kind, property_id) is None
    calls = watch_adapter_writes(probe)
    writes, original = _watch_checkpoint_writes()
    try:
        checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]

    assert checkpoint.fact_ledger is not None
    assert checkpoint.workflow_link is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert checkpoint.workflow_link.ready == ""
    assert _check(checkpoint, "dashboard_outputs") is False
    assert _fact(checkpoint, "dashboard_outputs") == "missing"
    assert "x;y" not in path.read_text(encoding="utf-8")
    assert calls == []
    assert writes["n"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("shape", ["renamed", "reordered", "short"])
async def test_saved_pass_checks_must_match_the_plan(tmp_path: Path, shape: str) -> None:
    """Helper-level: a PASS whose checks are true but not the plan does not hold."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    qa = load_qa_record(path)
    assert qa is not None
    steps = ledger_module._walk_chain()  # pyright: ignore[reportPrivateUsage]
    plan = await ledger_module._plan(probe, stored, spec, qa, steps)  # pyright: ignore[reportPrivateUsage]
    assert all(passed is True for _name, passed in plan.checks)
    checks = plan.checks
    if shape == "renamed":
        saved_checks = (("renamed", True), *checks[1:])
    elif shape == "reordered":
        saved_checks = (checks[1], checks[0], *checks[2:])
    elif shape == "short":
        saved_checks = checks[:-1]
    else:
        raise AssertionError(shape)
    saved = FactLedgerRecord(verdict="PASS", checks=saved_checks, facts=plan.facts)
    link = WorkflowLinkRecord(
        verdict="PASS",
        steps=plan.steps,
        ready=plan.ready,
        repair_required=plan.repair_required,
    )
    holds = ledger_module._saved_holds  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="fact ledger does not match"):
        await holds(probe, stored, spec, qa, saved, link, steps)


@pytest.mark.asyncio
async def test_row_properties_must_be_a_dict(tmp_path: Path) -> None:
    """A non-dict properties value is a missing identity, not an AttributeError."""
    _spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    notice = stored.notification_dashboard
    assert notice is not None
    row = probe.pages[notice.row_page_id]
    row.properties = None  # pyright: ignore[reportAttributeAccessIssue]
    identity = ledger_module._stable_identity  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="fact ledger identity is missing"):
        identity(probe, stored)


class _SemiName(str):
    """A str subclass whose containment check reports a semicolon."""

    def __contains__(self, item: object) -> bool:
        return item == ";"


class _PlainName(str):
    """A str subclass that does not report a semicolon."""

    def __contains__(self, item: object) -> bool:
        return False


def _rename_current_date(stored: ProductBuildCheckpoint, name: str) -> ProductBuildCheckpoint:
    notice = stored.notification_dashboard
    assert notice is not None
    formulas = tuple(
        (kind, _SemiName(name) if formula_name == "current_date" else formula_name, property_id)
        for kind, formula_name, property_id in notice.formulas
    )
    return replace(stored, notification_dashboard=replace(notice, formulas=formulas))


@pytest.mark.asyncio
@pytest.mark.parametrize("colour", ["", " red", "red "])
async def test_plan_refuses_an_undurable_colour_name(tmp_path: Path, colour: str) -> None:
    """Each name is checked. A joined 'red ,Green' or ',Green' is not durable."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    qa = load_qa_record(path)
    assert qa is not None
    variants = (replace(stored.variants[0], name=colour), *stored.variants[1:])
    stored = replace(stored, variants=variants)
    steps = ledger_module._walk_chain()  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        await ledger_module._plan(probe, stored, spec, qa, steps)  # pyright: ignore[reportPrivateUsage]


class _ColourName(str):
    """A colour whose text is a real name. Only the type is wrong."""


@pytest.mark.asyncio
@pytest.mark.parametrize("colour", [_ColourName("Red"), 5, None])
async def test_plan_refuses_a_non_string_colour_name(tmp_path: Path, colour: object) -> None:
    """A subclass, an int, and None are product refusals, not AttributeError.

    ``_colour_names`` checks the type before ``strip``. The joined fact is later.
    """
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    qa = load_qa_record(path)
    assert qa is not None
    variants = (replace(stored.variants[0], name=cast(str, colour)), *stored.variants[1:])
    stored = replace(stored, variants=variants)
    steps = ledger_module._walk_chain()  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        await ledger_module._plan(probe, stored, spec, qa, steps)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
@pytest.mark.parametrize("colour", ["", " red", "red "])
async def test_public_variant_name_is_refused_before_the_plan(tmp_path: Path, colour: str) -> None:
    """The checkpoint loader refuses these names. It does not call _plan."""
    spec, probe, path = await _qa(tmp_path)

    def _rename(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        variants = references["variants"]
        assert type(variants) is list
        row = variants[0]
        assert type(row) is dict
        row["name"] = colour

    restamp_checkpoint(path, _rename)
    raw = path.read_bytes()
    with pytest.raises(ProductBuildError, match="checkpoint variant must be a non-empty string"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("colour", [5, None])
async def test_public_non_string_variant_name_is_refused(tmp_path: Path, colour: object) -> None:
    """JSON can carry an int or null. A str subclass cannot survive the reload."""
    spec, probe, path = await _qa(tmp_path)

    def _rename(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        variants = references["variants"]
        assert type(variants) is list
        row = variants[0]
        assert type(row) is dict
        row["name"] = colour

    restamp_checkpoint(path, _rename)
    raw = path.read_bytes()
    with pytest.raises(ProductBuildError, match="checkpoint variant must be a non-empty string"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_empty_variants_are_a_product_error(tmp_path: Path) -> None:
    """variants=() is a product refusal. It is not an IndexError inside QA."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    qa = load_qa_record(path)
    assert qa is not None
    emptied = replace(stored, variants=())
    steps = ledger_module._walk_chain()  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        await ledger_module._plan(probe, emptied, spec, qa, steps)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_seminame_formula_is_missing(tmp_path: Path) -> None:
    """SemiName('current_date') contains ';'. The expression is the real str now().

    A reload from disk is a real str, so this kill stays on the helper. The public
    expression path is test_lying_formula_expression_is_blocked.
    """
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    mutated = _rename_current_date(stored, "current_date")
    read_dashboard = ledger_module._dashboard_outputs  # pyright: ignore[reportPrivateUsage]
    agreed, fact = read_dashboard(probe, mutated, spec)
    assert agreed is False
    assert fact == "missing"
    assert "current_date=now()" not in fact


@pytest.mark.asyncio
async def test_plain_subclass_formula_name_is_refused(tmp_path: Path) -> None:
    """A non-str name without ';' is refused. A JSON reload is a real str."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    notice = stored.notification_dashboard
    assert notice is not None
    formulas = tuple(
        (
            kind,
            _PlainName(formula_name) if formula_name == "current_date" else formula_name,
            property_id,
        )
        for kind, formula_name, property_id in notice.formulas
    )
    mutated = replace(stored, notification_dashboard=replace(notice, formulas=formulas))
    read_dashboard = ledger_module._dashboard_outputs  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        read_dashboard(probe, mutated, spec)


def _align_live_sections(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, spec: ProductSpec
) -> None:
    for index, hub in enumerate(stored.identity_hubs):
        for role in ("purpose", "practice", "buyer"):
            block = _role_block(probe, stored, index, role)
            block.content = section_content(spec, hub.name, role)


def _prose_caller(spec: ProductSpec, kind: str) -> ProductSpec:
    if kind == "description":
        first = spec.hubs[0].model_copy(
            update={"description": spec.hubs[0].description + " Edited"}
        )
        return spec.model_copy(update={"hubs": (first, *spec.hubs[1:])})
    if kind == "buyer":
        return spec.model_copy(update={"buyer_problem": spec.buyer_problem + " Edited"})
    if kind == "flagship":
        return spec.model_copy(update={"flagship_feature": spec.flagship_feature + " Edited"})
    raise AssertionError(kind)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["description", "buyer", "flagship"])
async def test_changed_prose_does_not_pass_without_a_new_qa(tmp_path: Path, kind: str) -> None:
    """Names and identity stay. Descriptions, buyer, or flagship changed, and the blocks match."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    qa = load_qa_record(path)
    assert qa is not None
    caller = _prose_caller(spec, kind)
    _align_live_sections(probe, stored, caller)
    holds = await qa_module._saved_holds(probe, stored, caller, qa)  # pyright: ignore[reportPrivateUsage]
    assert holds is False
    steps = ledger_module._walk_chain()  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="fact ledger caller does not match"):
        await ledger_module._plan(probe, stored, caller, qa, steps)  # pyright: ignore[reportPrivateUsage]
    raw = path.read_bytes()
    writes, original = _watch_checkpoint_writes()
    try:
        with pytest.raises(ProductBuildError, match="fact ledger caller does not match"):
            await run_fact_ledger(caller, probe, path, recorded_at=LEDGER_AT)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]
    assert writes["n"] == 0
    assert path.read_bytes() == raw
    await run_product_qa(caller, probe, path, recorded_at=LATER)
    checkpoint = await run_fact_ledger(caller, probe, path, recorded_at=LATER)
    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"


@pytest.mark.asyncio
async def test_prefix_only_section_is_the_same_refusal(tmp_path: Path) -> None:
    """Prefix-only content raises. A ``>=`` length compare still raises."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    hub = stored.identity_hubs[0]
    block = _role_block(probe, stored, 0, "purpose")
    block.content = f"{spec.identity} / {hub.name} purpose: "
    detail = ledger_module._durable_detail  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        detail(probe, hub, spec.identity, "purpose")
    caller = spec.model_copy(update={"identity": "Not The Row"})
    raw = path.read_bytes()
    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        await run_fact_ledger(caller, probe, path, recorded_at=LEDGER_AT)
    assert path.read_bytes() == raw


def _install_phase(path: Path, phase: object) -> None:
    """Write one phase with a digest that matches everything except the shape rule."""
    document = json.loads(path.read_text(encoding="utf-8"))
    progress = document["progress"]
    assert type(progress) is dict
    progress["next_phase"] = phase
    fields = progress_module._PROGRESS_FIELDS  # pyright: ignore[reportPrivateUsage]
    unsigned = {key: progress[key] for key in fields}
    covered = {key: value for key, value in document.items() if key != "progress"}
    covered["progress"] = unsigned
    progress["record_digest"] = progress_module._digest(covered)  # pyright: ignore[reportPrivateUsage]
    path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["", " test_matrix", "tést", 5, None])
async def test_next_phase_must_be_an_unpadded_ascii_token(tmp_path: Path, phase: object) -> None:
    """Each bad phase is a product refusal. An int or None is not an AttributeError.

    Empty kills ``== ""``. Padding kills the strip conjunct. ``tést`` kills
    ``isascii``. ``5`` and ``None`` kill the str-type conjunct. The three
    ``or`` to ``and`` flips accept one of the string phases and write.
    """
    spec, probe, path = await _qa(tmp_path)
    document = json.loads(path.read_text(encoding="utf-8"))
    progress = document["progress"]
    assert type(progress) is dict
    body = {key: value for key, value in progress.items() if key != "record_digest"}
    body["next_phase"] = phase
    unsigned = progress_module._unsigned_body(body)  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="progress record is tampered"):
        progress_module._require_shape(unsigned)  # pyright: ignore[reportPrivateUsage]
    progress["next_phase"] = phase
    with pytest.raises(ProductBuildError, match="progress record is tampered"):
        progress_module.stamp_integrity_digest(document)
    _install_phase(path, phase)
    raw = path.read_bytes()
    with pytest.raises(ProductBuildError, match="progress record is tampered"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert path.read_bytes() == raw


class _SelfStr(str):
    """A str subclass whose ``str()`` is itself, so ``str(value)`` is not a str."""

    __slots__ = ()

    def __str__(self) -> str:
        return self


class _Lie(str):
    """A padded str subclass that says it is neither empty nor padded."""

    __slots__ = ()

    def __str__(self) -> str:
        return self

    def __eq__(self, other: object) -> bool:
        return False if other == "" else str.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        return False

    __hash__ = str.__hash__

    def strip(self, chars: str | None = None) -> str:
        return self


class _StrMaker:
    """Not a str. Its ``__str__`` returns a str subclass."""

    def __str__(self) -> str:
        return _SelfStr("1")


def test_str_of_a_subclass_is_not_an_exact_str() -> None:
    """The premise of the two subclass cases below."""
    assert type(str(_SelfStr("1"))) is _SelfStr
    assert type(str(_StrMaker())) is _SelfStr


def test_non_positive_pid_is_not_alive() -> None:
    """pid 0 is refused before os.kill. The temp test does not cover this branch."""
    assert progress_module._pid_alive(0) is False  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("build_version", ""),
        ("build_version", " 1"),
        ("build_version", "1 "),
        ("build_version", _SelfStr("1")),
        ("build_version", _StrMaker()),
        ("build_version", _Lie(" 1")),
        ("database_ids", ()),
    ],
)
async def test_plan_refuses_an_undurable_fact(tmp_path: Path, field: str, value: object) -> None:
    """Helper-level kills for the joined fact check in ``_plan``.

    The public loader refuses each of these before ``_plan``. The helper must
    refuse them too: empty kills ``value == ""``, padding kills the strip
    conjunct, and both kill the two ``or`` to ``and`` flips. ``str()`` can
    return a str subclass, so the two subclass cases kill the type conjunct.
    """
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    qa = load_qa_record(path)
    assert qa is not None
    if field == "build_version":
        stored = replace(stored, build_version=cast(int, value))
    else:
        stored = replace(stored, database_ids=cast(tuple[tuple[str, str], ...], value))
    steps = ledger_module._walk_chain()  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        await ledger_module._plan(probe, stored, spec, qa, steps)  # pyright: ignore[reportPrivateUsage]


SECRET = "sk-live-secret"


def _secret_reachable(error: BaseException) -> list[str]:
    """Every place a secret could sit on a raised error: the chain, attributes, frames."""
    import traceback

    found: list[str] = []
    pending: list[BaseException] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        texts = [
            str(current),
            repr(current),
            repr(current.args),
            repr(getattr(current, "__notes__", None)),
            repr(vars(current)),
        ]
        if any(SECRET in text for text in texts):
            found.append(type(current).__name__)
        for linked in (current.__cause__, current.__context__):
            if linked is not None:
                pending.append(linked)
    formatted = "".join(traceback.format_exception(error))
    if SECRET in formatted:
        found.append("traceback")
    trace = error.__traceback__
    while trace is not None:
        frame = trace.tb_frame
        if frame.f_code.co_filename != __file__ and SECRET in repr(frame.f_locals):
            found.append(f"locals:{frame.f_code.co_name}")
        trace = trace.tb_next
    return found


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prefix", ["qa ", "checkpoint ", "fact ledger ", "progress ", "workflow link "]
)
async def test_provider_error_with_an_own_prefix_is_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    """A provider ProductBuildError is not an own refusal because of its text."""
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        try:
            raise RuntimeError(SECRET)
        except RuntimeError as inner:
            raise ProductBuildError(prefix + SECRET) from inner

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    with pytest.raises(ProductBuildError) as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert str(caught.value) == "fact ledger read failed"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert _secret_reachable(caught.value) == []
    assert path.read_bytes() == raw
    assert _jobs(path) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ["qa " + SECRET, "fact ledger " + SECRET, SECRET])
async def test_recorded_provider_response_is_not_an_own_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, response: str
) -> None:
    """raise_recorded is package code. Its provider response is still redacted."""
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()
    elsewhere = tmp_path / "absent.json"

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        progress_module.raise_recorded(
            elsewhere, "qa", ProviderFailure("fact_ledger.read", response)
        )

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    with pytest.raises(ProductBuildError) as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert str(caught.value) == "fact ledger read failed"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert _secret_reachable(caught.value) == []
    assert not elsewhere.exists()
    assert path.read_bytes() == raw


def _permission_error() -> BaseException:
    return PermissionError(13, "denied", SECRET)


def _noted_error() -> BaseException:
    error = ConnectionError("reset")
    error.add_note(SECRET)
    return error


def _provider_chain() -> BaseException:
    try:
        raise RuntimeError(SECRET)
    except RuntimeError as inner:
        error = ConnectionError("outer")
        error.__cause__ = inner
        return error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "make",
    [
        lambda: ConnectionError(SECRET),
        lambda: ProviderFailure("fact_ledger.read", SECRET),
        _permission_error,
        _noted_error,
        _provider_chain,
    ],
)
async def test_provider_failure_leaves_no_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make: Callable[[], BaseException]
) -> None:
    """The provider job error has the fixed cause only. The original is not its context."""
    spec, probe, path = await _qa(tmp_path)

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        raise make()

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    with pytest.raises(ProductBuildError, match="provider read failed") as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert caught.value.__context__ is None
    cause = caught.value.__cause__
    assert type(cause) is ProviderFailure
    assert cause.response == "provider read failed"
    assert cause.__context__ is None
    assert _secret_reachable(caught.value) == []
    assert SECRET not in path.read_text(encoding="utf-8")
    assert len(_provider_jobs(path)) == 1


class _SecretError(Exception):
    """A code error whose secret is in __str__, an attribute, and a note."""

    def __init__(self) -> None:
        super().__init__("plain")
        self.token = SECRET
        self.add_note(SECRET)

    def __str__(self) -> str:
        return SECRET


@pytest.mark.asyncio
async def test_code_error_attributes_do_not_survive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """__str__, a token attribute, a note, and a chained cause are all unreachable."""
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        try:
            raise RuntimeError(SECRET)
        except RuntimeError as inner:
            raise _SecretError() from inner

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    with pytest.raises(ProductBuildError) as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert str(caught.value) == "fact ledger read failed"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert _secret_reachable(caught.value) == []
    assert path.read_bytes() == raw
    assert _jobs(path) == []


@pytest.mark.asyncio
async def test_own_refusal_is_raised_without_a_chain(tmp_path: Path) -> None:
    """A package refusal keeps its text. Nothing it was raised from comes with it."""
    spec, probe, path = await _qa(tmp_path)
    caller = _prose_caller(spec, "buyer")
    raw = path.read_bytes()
    with pytest.raises(ProductBuildError) as caught:
        await run_fact_ledger(caller, probe, path, recorded_at=LEDGER_AT)
    assert str(caught.value) == "fact ledger caller does not match"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert path.read_bytes() == raw


def test_error_without_a_traceback_is_not_own() -> None:
    """An error that was never raised has no frame, so it is not a package refusal."""
    own = ledger_module._own_message  # pyright: ignore[reportPrivateUsage]
    assert own(ProductBuildError("fact ledger caller does not match")) is False
    try:
        raise ProductBuildError("fact ledger caller does not match")
    except ProductBuildError as error:
        assert own(error) is False


# Round 8: ifexp kills, interrupts, comma colour names, duplicate-label text.


@pytest.mark.asyncio
async def test_missing_notice_is_not_a_read_failure(tmp_path: Path) -> None:
    """No notification record is the own identity refusal, not a code error.

    Kills ``notice is not None`` to True in ``_require_pages``: the mutant reads
    ``None.row_page_id`` and the run reports "fact ledger read failed".
    """
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    stored = replace(stored, notification_dashboard=None)
    ledger_module._require_pages(probe, stored)  # pyright: ignore[reportPrivateUsage]
    qa = load_qa_record(path)
    assert qa is not None
    steps = ledger_module._walk_chain()  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match=r"^fact ledger identity is missing$"):
        await ledger_module._plan(probe, stored, spec, qa, steps)  # pyright: ignore[reportPrivateUsage]
    guarded = ledger_module._guarded_read  # pyright: ignore[reportPrivateUsage]
    result = await guarded(probe, stored, spec, qa, None, None, steps)
    assert result == (None, None, "fact ledger identity is missing")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["absent", "subclass"])
async def test_missing_or_subclass_sample_is_missing(tmp_path: Path, mode: str) -> None:
    """A sample that is absent or not an exact NotionPage is a missing output.

    Kills ``type(sample) is NotionPage`` to True in ``_dashboard_outputs``.
    ``_require_pages`` refuses both first in ``_plan``, so this is helper level.
    """
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    notice = stored.notification_dashboard
    assert notice is not None and notice.samples
    _kind, page_id = notice.samples[0]
    if mode == "absent":
        del probe.pages[page_id]
    else:

        class _Page(NotionPage):
            pass

        page = probe.pages[page_id]
        values = {item.name: getattr(page, item.name) for item in fields(page)}
        probe.pages[page_id] = _Page(**values)
    outputs = ledger_module._dashboard_outputs  # pyright: ignore[reportPrivateUsage]
    assert outputs(probe, stored, spec) == (False, "missing")


@pytest.mark.asyncio
async def test_colour_name_with_a_comma_is_refused(tmp_path: Path) -> None:
    """The colour fact joins names with commas. A name holding one is refused."""
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    first = replace(stored.variants[0], name="red ,Green,Purple")
    forged = replace(stored, variants=(first, *stored.variants[1:]))
    names = ledger_module._colour_names  # pyright: ignore[reportPrivateUsage]
    assert names(stored) == tuple(record.name for record in stored.variants)
    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        names(forged)
    qa = load_qa_record(path)
    assert qa is not None
    steps = ledger_module._walk_chain()  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        await ledger_module._plan(probe, forged, spec, qa, steps)  # pyright: ignore[reportPrivateUsage]


class _SecretInterrupt(BaseException):
    """A non-Exception error that carries the secret."""

    def __init__(self) -> None:
        super().__init__(SECRET)
        self.token = SECRET


def _cancelled() -> BaseException:
    import asyncio

    return asyncio.CancelledError(SECRET)


def _noted_interrupt() -> BaseException:
    error = KeyboardInterrupt(SECRET)
    error.add_note(SECRET)
    return error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("make", "expected", "args"),
    [
        (_cancelled, "CancelledError", ()),
        (_noted_interrupt, "KeyboardInterrupt", ()),
        (lambda: GeneratorExit(SECRET), "GeneratorExit", ()),
        (lambda: SystemExit(SECRET), "SystemExit", (1,)),
        (lambda: SystemExit(3), "SystemExit", (3,)),
        (_SecretInterrupt, "BaseException", ("fact ledger read failed",)),
    ],
)
async def test_interrupt_keeps_its_kind_and_drops_the_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make: Callable[[], BaseException],
    expected: str,
    args: tuple[object, ...],
) -> None:
    """A BaseException still propagates. Its text, notes, attributes, and chain do not."""
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        try:
            raise RuntimeError(SECRET)
        except RuntimeError:
            raise make() from None

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    with pytest.raises(BaseException) as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    error = caught.value
    assert type(error).__name__ == expected
    assert type(error).__module__ in {"builtins", "asyncio.exceptions"}
    assert error.args == args
    assert error.__cause__ is None
    assert error.__context__ is None
    assert getattr(error, "__notes__", None) is None
    assert _secret_reachable(error) == []
    assert path.read_bytes() == raw
    assert _jobs(path) == []


@pytest.mark.asyncio
async def test_task_cancel_message_is_dropped_and_the_task_is_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Task.cancel(msg) puts msg on the CancelledError. The task still ends cancelled."""
    import asyncio

    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()
    started = asyncio.Event()

    async def _wait(*_args: object, **_kwargs: object) -> bool:
        started.set()
        await asyncio.Event().wait()
        return True

    monkeypatch.setattr(ledger_module, "live_qa_passed", _wait)
    task = asyncio.ensure_future(run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT))
    # Bounded, so a broken QA or ledger that never reaches the read fails here.
    async with asyncio.timeout(30):
        await started.wait()
    task.cancel(SECRET)
    with pytest.raises(asyncio.CancelledError) as caught:
        await task
    assert task.cancelled() is True
    assert caught.value.args == ()
    assert _secret_reachable(caught.value) == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_timeout_still_becomes_timeout_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """asyncio.timeout matches the fresh CancelledError by type and raises TimeoutError."""
    import asyncio

    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    async def _wait(*_args: object, **_kwargs: object) -> bool:
        await asyncio.Event().wait()
        return True

    monkeypatch.setattr(ledger_module, "live_qa_passed", _wait)
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert path.read_bytes() == raw


@pytest.mark.parametrize(
    "message",
    [
        "checkpoint variant is duplicated",
        "checkpoint aesthetics accent is duplicated",
        "checkpoint aesthetics sample is duplicated",
        "checkpoint notification relation is duplicated",
        "checkpoint notification rollup is duplicated",
        "checkpoint notification sample is duplicated",
    ],
)
def test_known_duplicate_refusal_keeps_its_text(message: str) -> None:
    progress_module.reject_duplicate_labels(["a", "b"], message)
    with pytest.raises(ProductBuildError) as caught:
        progress_module.reject_duplicate_labels(["a", "a"], message)
    assert str(caught.value) == message


@pytest.mark.parametrize("message", ["fact ledger " + SECRET, SECRET, "checkpoint " + SECRET])
def test_unknown_duplicate_refusal_text_is_not_raised(message: str) -> None:
    """An own refusal never carries caller text that is not a known message."""
    with pytest.raises(ProductBuildError) as caught:
        progress_module.reject_duplicate_labels(["a", "a"], message)
    # The caller's own argument stays in its frame. The raised error holds none of it.
    assert str(caught.value) == "checkpoint list is duplicated"
    assert caught.value.args == ("checkpoint list is duplicated",)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [_SelfStr("1"), _Lie(" 1"), _StrMaker()])
async def test_public_entry_refuses_a_str_subclass_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    """Through run_fact_ledger, a version whose str() is not an exact str writes nothing.

    The real loader refuses these first. The loader is replaced here so the
    ``type(value) is not str`` conjunct in ``_plan`` is the only guard left.
    """
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()
    real = ledger_module.load_variant_checkpoint

    def _load(target: Path) -> tuple[ProductBuildCheckpoint, object]:
        stored, created = real(target)
        return replace(stored, build_version=cast(int, value)), created

    monkeypatch.setattr(ledger_module, "load_variant_checkpoint", _load)
    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("half", ["ledger", "link"])
async def test_half_a_saved_pair_is_planned_not_a_read_failure(tmp_path: Path, half: str) -> None:
    """Only one saved record is not a resume. ``_guarded_read`` plans instead.

    Kills ``saved_ledger is not None`` and ``saved_link is not None`` to True:
    each mutant passes None into ``_saved_holds`` and reports "fact ledger read failed".
    """
    spec, probe, path = await _qa(tmp_path)
    await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    saved_ledger, saved_link = ledger_module._stored_pair(path)  # pyright: ignore[reportPrivateUsage]
    assert saved_ledger is not None and saved_link is not None
    stored, _created = load_variant_checkpoint(path)
    qa = load_qa_record(path)
    assert qa is not None
    steps = ledger_module._walk_chain()  # pyright: ignore[reportPrivateUsage]
    guarded = ledger_module._guarded_read  # pyright: ignore[reportPrivateUsage]
    if half == "ledger":
        resumed, plan, failure = await guarded(probe, stored, spec, qa, saved_ledger, None, steps)
    else:
        resumed, plan, failure = await guarded(probe, stored, spec, qa, None, saved_link, steps)
    assert failure == ""
    assert resumed is None
    assert plan is not None
    assert plan.blocked is False


def _override_formula(
    monkeypatch: pytest.MonkeyPatch,
    spec: ProductSpec,
    stored: ProductBuildCheckpoint,
    value: str | None,
) -> str:
    """Make one dashboard formula's expected and stored expression both ``value``."""
    notice = stored.notification_dashboard
    assert notice is not None and notice.formulas
    kind, name, property_id = notice.formulas[0]
    real_expected = ledger_module.dashboard_formula_expressions
    real_stored = ledger_module._formula_expression  # pyright: ignore[reportPrivateUsage]

    def _expected(target: ProductSpec) -> dict[str, tuple[str, str | None]]:
        found: dict[str, tuple[str, str | None]] = dict(real_expected(target))
        found[name] = (kind, value)
        return found

    def _stored(
        probe: FixtureNotionAdapter, checkpoint: ProductBuildCheckpoint, wanted: str, pid: str
    ) -> str | None:
        if pid == property_id:
            return value
        return real_stored(probe, checkpoint, wanted, pid)

    monkeypatch.setattr(ledger_module, "dashboard_formula_expressions", _expected)
    monkeypatch.setattr(ledger_module, "_formula_expression", _stored)
    del spec
    return name


@pytest.mark.asyncio
async def test_formula_missing_on_both_sides_is_blocked_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expected and stored expression both None is a BLOCKED ledger with ``missing``.

    Kills ``expression is None`` to False in ``_dashboard_outputs``: the mutant
    reaches ``";" in None``, and the run writes nothing.
    """
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    _override_formula(monkeypatch, spec, stored, None)
    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _check(checkpoint, "dashboard_outputs") is False
    assert _fact(checkpoint, "dashboard_outputs") == "missing"


@pytest.mark.asyncio
async def test_semicolon_formula_on_both_sides_is_not_stored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An expression with ``;`` is ``missing`` even when it matches. It is never stored.

    Kills ``";" in expression`` to False in ``_dashboard_outputs``.
    """
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    notice = stored.notification_dashboard
    assert notice is not None
    kind, _name, property_id = notice.formulas[0]
    base = ledger_module._formula_expression(probe, stored, kind, property_id)  # pyright: ignore[reportPrivateUsage]
    assert base is not None and ";" not in base
    name = _override_formula(monkeypatch, spec, stored, base + ";x")
    checkpoint = await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert _fact(checkpoint, "dashboard_outputs") == "missing"
    assert f"{name}={base};x" not in path.read_text(encoding="utf-8")
    assert ";x" not in path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_in_package_error_without_an_own_prefix_is_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Package code that raises a non-refusal text is not an own refusal.

    Kills deleting the own-prefix gate in ``_own_message``: the cause is not a
    ProviderFailure and the innermost frame is package code, so only the
    prefix check keeps ``sk-live-secret`` out of the raised message.
    """
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()
    namespace: dict[str, object] = {
        "__name__": ledger_module.__name__,
        "ProductBuildError": ProductBuildError,
        "SECRET": SECRET,
    }
    source = (
        "def _package_raise():\n"
        "    try:\n"
        "        raise RuntimeError(SECRET)\n"
        "    except RuntimeError as inner:\n"
        "        raise ProductBuildError(SECRET) from inner\n"
    )
    exec(compile(source, "<package_raise>", "exec"), namespace)
    package_raise = cast(Callable[[], None], namespace["_package_raise"])

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        package_raise()
        return True

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    with pytest.raises(ProductBuildError) as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert str(caught.value) == "fact ledger read failed"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert _secret_reachable(caught.value) == []
    assert path.read_bytes() == raw
    assert _jobs(path) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("colour", ["red ,Green,Purple", ",Green,Purple", "red,Green"])
async def test_public_comma_colour_name_is_refused_with_no_write(
    tmp_path: Path, colour: str
) -> None:
    """A variant name with a comma cannot be split back out of the joined fact."""
    spec, probe, path = await _qa(tmp_path)

    def _rename(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        variants = references["variants"]
        assert type(variants) is list
        row = variants[0]
        assert type(row) is dict
        row["name"] = colour
        progress = document["progress"]
        assert type(progress) is dict
        created = progress["created_notion_ids"]
        assert type(created) is dict
        created_variants = created["variants"]
        assert type(created_variants) is list
        created_row = created_variants[0]
        assert type(created_row) is dict
        if "name" in created_row:
            created_row["name"] = colour

    restamp_checkpoint(path, _rename)
    raw = path.read_bytes()
    with pytest.raises(ProductBuildError, match="fact ledger fact is not a durable string"):
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_blank_hub_name_with_blank_title_is_matched(tmp_path: Path) -> None:
    """``_hub_names`` with stored name ``""`` and title ``""`` reports matched True.

    Kills IfExp ``title != ""`` to True at ``_hub_names`` (X748:21->T). Stock
    stores ``missing`` for the blank title and the durable loop leaves it, so
    the empty name and empty title still agree. The mutant keeps ``""``, which
    the durable loop turns into a mismatch. At the public entry the loader and
    ``_require_hub_name`` refuse a blank hub name first, so this is helper level.
    """
    _spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    hub = stored.identity_hubs[0]
    blank = replace(hub, name="")
    forged = replace(stored, identity_hubs=(blank, *stored.identity_hubs[1:]))
    probe.pages[hub.page_id].title = ""
    names = ledger_module._hub_names  # pyright: ignore[reportPrivateUsage]
    durable, matched = names(probe, forged)
    assert matched is True
    assert durable[0] == "missing"


class _PlainInterrupt(BaseException):
    """A custom kind with no constructor of its own, so a fresh one is safe."""


class _PlainKeyboard(KeyboardInterrupt):
    """A custom KeyboardInterrupt with no constructor of its own."""


class _PlainExit(SystemExit):
    """A custom SystemExit with no constructor of its own."""


class _PlainGroup(BaseExceptionGroup[BaseException]):
    """A custom group with no constructor of its own."""


class _BuiltKeyboard(KeyboardInterrupt):
    """A custom KeyboardInterrupt whose constructor is caller code."""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.token = SECRET


class _Meta(type):
    pass


class _MetaInterrupt(BaseException, metaclass=_Meta):
    """A custom kind whose metaclass could run code on construction."""


def _group_members(error: BaseException) -> list[BaseException]:
    found: list[BaseException] = [error]
    if isinstance(error, BaseExceptionGroup):
        for member in cast(tuple[BaseException, ...], error.exceptions):
            found.extend(_group_members(member))
    return found


def _secret_group() -> BaseException:
    inner = KeyboardInterrupt(SECRET)
    inner.add_note(SECRET)
    return BaseExceptionGroup(SECRET, [inner, RuntimeError(SECRET)])


def _nested_group() -> BaseException:
    return BaseExceptionGroup(
        SECRET, [BaseExceptionGroup(SECRET, [SystemExit(SECRET)]), _PlainInterrupt(SECRET)]
    )


def _plain_group() -> BaseException:
    return _PlainGroup(SECRET, [_PlainKeyboard(SECRET)])


def _group_with_an_exception_group() -> BaseException:
    return BaseExceptionGroup(
        SECRET, [ExceptionGroup(SECRET, [RuntimeError(SECRET)]), KeyboardInterrupt(SECRET)]
    )


@pytest.mark.parametrize(
    ("make", "kind", "args"),
    [
        (lambda: _PlainInterrupt(SECRET), _PlainInterrupt, ("fact ledger read failed",)),
        (lambda: _PlainKeyboard(SECRET), _PlainKeyboard, ()),
        (lambda: _PlainExit(SECRET), _PlainExit, (1,)),
        (lambda: _PlainExit(4), _PlainExit, (4,)),
        (lambda: _BuiltKeyboard(SECRET), KeyboardInterrupt, ()),
        (lambda: _MetaInterrupt(SECRET), BaseException, ("fact ledger read failed",)),
        (_SecretInterrupt, BaseException, ("fact ledger read failed",)),
    ],
)
def test_clean_interrupt_keeps_a_custom_kind_or_its_built_in_base(
    make: Callable[[], BaseException], kind: type[BaseException], args: tuple[object, ...]
) -> None:
    """A custom kind is kept when a fresh one runs no caller code, else its built-in base."""
    clean = ledger_module._clean_interrupt  # pyright: ignore[reportPrivateUsage]
    error = clean(make())
    assert type(error) is kind
    assert error.args == args
    assert error.__cause__ is None
    assert error.__context__ is None
    assert getattr(error, "__notes__", None) is None
    assert vars(error) == {}
    assert _secret_reachable(error) == []


@pytest.mark.parametrize(
    ("make", "kinds"),
    [
        (_secret_group, [BaseExceptionGroup, KeyboardInterrupt, Exception]),
        (
            _nested_group,
            [BaseExceptionGroup, BaseExceptionGroup, SystemExit, _PlainInterrupt],
        ),
        (_plain_group, [_PlainGroup, _PlainKeyboard]),
        (
            _group_with_an_exception_group,
            [BaseExceptionGroup, ExceptionGroup, Exception, KeyboardInterrupt],
        ),
    ],
)
def test_clean_interrupt_keeps_a_group_and_cleans_every_member(
    make: Callable[[], BaseException], kinds: list[type[BaseException]]
) -> None:
    """A BaseExceptionGroup keeps its kind and members' kinds, with fixed text only."""
    clean = ledger_module._clean_interrupt  # pyright: ignore[reportPrivateUsage]
    error = clean(make())
    members = _group_members(error)
    assert [type(member) for member in members] == kinds
    for member in members:
        assert member.__cause__ is None
        assert member.__context__ is None
        assert getattr(member, "__notes__", None) is None
        assert _secret_reachable(member) == []
        if isinstance(member, BaseExceptionGroup):
            assert str(member).startswith("fact ledger read failed")


@pytest.mark.asyncio
async def test_interrupt_group_from_the_read_keeps_its_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through run_fact_ledger, a group wrapping a KeyboardInterrupt stays a group."""
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        raise _secret_group()

    monkeypatch.setattr(ledger_module, "live_qa_passed", _boom)
    with pytest.raises(BaseExceptionGroup) as caught:
        await run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    members = _group_members(caught.value)
    assert [type(member) for member in members] == [
        BaseExceptionGroup,
        KeyboardInterrupt,
        Exception,
    ]
    assert caught.value.__context__ is None
    assert all(_secret_reachable(member) == [] for member in members)
    assert path.read_bytes() == raw
    assert _jobs(path) == []


class _ForgedText(str):
    """A str subclass that claims to equal, and hash like, a known refusal."""

    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return hash("checkpoint variant is duplicated")


def test_forged_str_subclass_refusal_text_is_not_raised() -> None:
    """A str subclass with a forged hash and equality is not a known refusal text."""
    forged = _ForgedText("checkpoint " + SECRET)
    assert forged in {"checkpoint variant is duplicated"}
    with pytest.raises(ProductBuildError) as caught:
        progress_module.reject_duplicate_labels(["a", "a"], forged)
    assert type(caught.value.args[0]) is str
    assert caught.value.args == ("checkpoint list is duplicated",)
    assert SECRET not in str(caught.value)
