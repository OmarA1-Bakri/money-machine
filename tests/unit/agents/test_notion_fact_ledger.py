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
from money_machine.agents.implementations.notion_qa import run_product_qa
from money_machine.agents.implementations.notion_variants import (
    build_variants,
    load_variant_checkpoint,
)
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.domain import NotionTextBlock
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
        checkpoint = run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
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
    assert _check(checkpoint, "workflow") is True
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
    first = run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)
    writes, original = _watch_checkpoint_writes()
    try:
        again = run_fact_ledger(spec, probe, path, recorded_at=LATER)
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

    checkpoint = run_fact_ledger(mutated, probe, path, recorded_at=LEDGER_AT)

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

    checkpoint = run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    raw = path.read_bytes()
    again = run_fact_ledger(spec, probe, path, recorded_at=LATER)

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
    blocked = run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert blocked.fact_ledger is not None
    assert blocked.fact_ledger.verdict == "BLOCKED"
    del probe.blocks["block_no_access"]
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert "fact_ledger" in _references(path)
    assert "workflow_link" in _references(path)
    calls = watch_adapter_writes(probe)

    checkpoint = run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert checkpoint.workflow_link is not None
    assert checkpoint.workflow_link.ready == "ListingCopyJob"
    assert calls == []


@pytest.mark.asyncio
async def test_stored_blocked_verdict_replans_a_passing_plan(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

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
    calls = watch_adapter_writes(probe)

    checkpoint = run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "PASS"
    assert checkpoint.workflow_link is not None
    assert checkpoint.workflow_link.ready == "ListingCopyJob"
    assert calls == []


@pytest.mark.asyncio
async def test_forged_fact_does_not_match_and_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

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
        run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_forged_step_does_not_match_and_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

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
        run_fact_ledger(spec, probe, path, recorded_at=LATER)

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
        run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    assert calls == []
    assert path.read_bytes() == raw

    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    def _drop_link(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        del references["workflow_link"]

    restamp_checkpoint(path, _drop_link)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)
    with pytest.raises(ProductBuildError, match="fact ledger record is incomplete"):
        run_fact_ledger(spec, probe, path, recorded_at=LATER)
    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_unsupported_verdict_writes_nothing(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

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
        run_fact_ledger(spec, probe, path, recorded_at=LATER)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_catalogue_spec_and_live_probe_are_rejected(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="validated ProductSpec"):
        run_fact_ledger(create_fixture_product_spec(), probe, path, recorded_at=LEDGER_AT)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        run_fact_ledger(spec, APINotionAdapter(), path, recorded_at=LEDGER_AT)
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
        run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_renamed_hub_is_blocked_with_no_adapter_writes(tmp_path: Path) -> None:
    spec, probe, path = await _qa(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    probe.pages[stored.identity_hubs[0].page_id].title = "Renamed Hub"
    calls = watch_adapter_writes(probe)

    checkpoint = run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert checkpoint.fact_ledger is not None
    assert checkpoint.fact_ledger.verdict == "BLOCKED"
    assert checkpoint.workflow_link is not None
    assert checkpoint.workflow_link.ready == ""
    assert _check(checkpoint, "hubs_present") is False
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
        run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

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
            run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
    finally:
        ledger_module.write_checkpoint = original  # type: ignore[assignment]
    assert "fact_ledger" not in _references(path)
    assert "workflow_link" not in _references(path)
    calls = watch_adapter_writes(probe)
    writes, original = _watch_checkpoint_writes()
    try:
        checkpoint = run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
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
    run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
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

    checkpoint = run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

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

    checkpoint = run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

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

    checkpoint = run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

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

    checkpoint = run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

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

    checkpoint = run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

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
        run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_missing_listing_successor_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, probe, path = await _qa(tmp_path)
    raw = path.read_bytes()
    event_map, config = load_workflows_config()
    workflow = next(
        item for item in config.workflows if item.workflow_type == "ProductLifecycleWorkflow"
    )
    jobs = tuple(
        job.model_copy(
            update={
                "successor_job_types": tuple(
                    item for item in job.successor_job_types if item != "ListingCopyJob"
                )
            }
        )
        if job.job_type == "ScreenshotJob"
        else job
        for job in workflow.jobs
    )
    patched = config.model_copy(update={"workflows": (workflow.model_copy(update={"jobs": jobs}),)})

    def _broken() -> tuple[dict[str, list[str]], object]:
        return event_map, patched

    monkeypatch.setattr(ledger_module, "load_workflows_config", _broken)
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="workflow link does not match"):
        run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)

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
    checkpoint = run_fact_ledger(spec, probe, path, recorded_at=LEDGER_AT)
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
