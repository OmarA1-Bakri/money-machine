"""Fixture-only product QA. Not a seventh build phase and not the fact ledger."""

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest

from money_machine.agents.implementations import notion_qa as notion_qa_module
from money_machine.agents.implementations.notion_product_builder import ProductBuildError
from money_machine.agents.implementations.notion_progress import OP_QA, ProviderFailure
from money_machine.agents.implementations.notion_qa import PHASE_FACT_LEDGER, run_product_qa
from money_machine.agents.implementations.notion_variants import build_variants
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.domain import (
    NotionDatabase,
    NotionDatabaseProperty,
    NotionFormula,
    NotionPage,
    NotionRelation,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from tests.fixtures.products import create_fixture_product_spec
from tests.unit.agents.test_notion_product_builder_variants import (
    VARIANTS_AT,
    adapter_snapshot,
    planner_spec,
    prepare_aesthetics,
    restamp_checkpoint,
    watch_adapter_writes,
)

ROOT = Path(__file__).parents[3]
MODULE_PATH = ROOT / "src/money_machine/agents/implementations/notion_qa.py"
QA_AT = datetime(2026, 10, 6, 3, 30, tzinfo=UTC)


async def _variants(spec: ProductSpec, probe: FixtureNotionAdapter, path: Path) -> None:
    await prepare_aesthetics(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)


def _qa_body(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="ascii"))
    references = document["provider_object_references"]
    assert type(references) is dict
    qa = references["qa"]
    assert type(qa) is dict
    return qa


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tier", "identity", "title", "hub_name"),
    [
        ("mass", "Weekly Planner", "Home Dashboard Planner", "Hub"),
        ("business", "Studio Ledger", "Studio Home", "Desk"),
    ],
)
async def test_finished_variants_pass_and_duplicate_once(
    tmp_path: Path, tier: str, identity: str, title: str, hub_name: str
) -> None:
    spec = planner_spec(tier=tier, identity=identity, title=title, hub_name=hub_name)
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    started = len(probe.pages)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "PASS"
    assert checkpoint.qa.repairs == ()
    assert checkpoint.next_phase == PHASE_FACT_LEDGER
    assert calls == ["duplicate_page"]
    assert len(probe.pages) == started + 1
    proof = probe.pages[checkpoint.qa.proof_page_id]
    assert proof.title == f"{spec.title} / {spec.colour_variants[0]} (Copy)"
    assert proof.is_published is False
    body = _qa_body(path)
    assert body["verdict"] == "PASS"
    facts = body["facts"]
    assert type(facts) is list
    stored = {row["fact"]: row["value"] for row in facts if type(row) is dict}
    assert stored["colour_names"] == ",".join(spec.colour_variants)
    assert stored["variant_count"] == str(len(spec.colour_variants))
    assert stored["page_count"] == str(started)
    assert "FAIL_REPAIRABLE" in MODULE_PATH.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_resume_of_pass_makes_no_adapter_writes(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    raw = path.read_bytes()
    pages = len(probe.pages)
    calls = watch_adapter_writes(probe)

    again = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert again.qa is not None and again.qa.verdict == "PASS"
    assert calls == []
    assert path.read_bytes() == raw
    assert len(probe.pages) == pages


@pytest.mark.asyncio
async def test_variants_after_qa_does_not_drop_the_qa_key(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert _qa_body(path)["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_no_access_block_is_blocked_with_no_adapter_writes(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    block = next(iter(probe.blocks.values()))
    block.content = f"{block.content} No access"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.proof_page_id == ""
    assert calls == []
    assert _qa_body(path)["verdict"] == "BLOCKED"


@pytest.mark.asyncio
async def test_extra_database_is_blocked_with_no_adapter_writes(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    probe.databases["db_extra"] = NotionDatabase(id="db_extra", title="Extra")
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert calls == []


@pytest.mark.asyncio
async def test_wrong_formula_expression_is_blocked(tmp_path: Path) -> None:
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
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert calls == []


@pytest.mark.asyncio
async def test_foreign_relation_is_blocked(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    database = next(iter(probe.databases.values()))
    database.properties.append(
        NotionDatabaseProperty(
            id="prop_foreign",
            name="Foreign",
            type="relation",
            config={
                "relation": NotionRelation(
                    id="rel_foreign",
                    name="Foreign",
                    database_id="db_other",
                )
            },
        )
    )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert calls == []


@pytest.mark.asyncio
async def test_unpublished_variant_is_repaired_then_passes(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    page = next(item for item in probe.pages.values() if item.title.endswith("/ Blue"))
    page.is_published = False
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "PASS"
    assert checkpoint.qa.repairs == ("published",)
    assert calls == ["publish_page", "duplicate_page"]
    assert page.is_published is True


@pytest.mark.asyncio
async def test_lying_template_repair_records_blocked(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    page = next(item for item in probe.pages.values() if item.title.endswith("/ Blue"))
    page.duplicate_as_template = False

    async def _lie(page_id: str, enabled: bool) -> NotionPage:
        del enabled
        return probe.pages[page_id]

    probe.set_duplicate_as_template = _lie  # type: ignore[method-assign]
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.proof_page_id == ""
    assert calls == ["set_duplicate_as_template"]
    assert page.duplicate_as_template is False


@pytest.mark.asyncio
async def test_blocked_resume_makes_no_adapter_writes(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    block = next(iter(probe.blocks.values()))
    block.content = f"{block.content} No access"
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    again = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert again.qa is not None and again.qa.verdict == "BLOCKED"
    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_duplicate_crash_then_resume_creates_one_proof(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    started = len(probe.pages)
    original = probe.duplicate_page
    failed = {"done": False}

    async def _boom(page_id: str) -> NotionPage:
        if not failed["done"]:
            failed["done"] = True
            raise RuntimeError("step crashed")
        return await original(page_id)

    probe.duplicate_page = _boom  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="step crashed"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert len(probe.pages) == started
    assert "qa" not in json.loads(path.read_text(encoding="ascii"))["provider_object_references"]

    probe.duplicate_page = original  # type: ignore[method-assign]
    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "PASS"
    assert len(probe.pages) == started + 1


@pytest.mark.asyncio
async def test_crash_after_duplicate_resumes_without_a_second_proof(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    started = len(probe.pages)
    original = notion_qa_module.write_checkpoint

    def _boom(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("checkpoint crashed")

    notion_qa_module.write_checkpoint = _boom  # type: ignore[assignment]
    try:
        with pytest.raises(RuntimeError, match="checkpoint crashed"):
            await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    finally:
        notion_qa_module.write_checkpoint = original  # type: ignore[assignment]
    assert len(probe.pages) == started + 1
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "PASS"
    assert calls == []
    assert len(probe.pages) == started + 1


@pytest.mark.asyncio
async def test_public_url_provider_failure_records_a_repair_job(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    raw_pages = len(probe.pages)

    async def _boom(page_id: str) -> str:
        del page_id
        raise ProviderFailure(OP_QA, "url refused")

    probe.get_public_url = _boom  # type: ignore[method-assign]
    calls = watch_adapter_writes(probe)
    with pytest.raises(ProductBuildError, match="url refused"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    stored = json.loads(path.read_text(encoding="ascii"))
    job = stored["progress"]["repair_jobs"][-1]
    assert job["kind"] == "provider_response"
    assert job["response"] == "url refused"
    assert calls == []
    assert len(probe.pages) == raw_pages
    assert "qa" not in stored["provider_object_references"]


@pytest.mark.asyncio
async def test_guarded_duplicate_records_a_repair_job(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    probe.fail_operation = OP_QA  # type: ignore[attr-defined]
    probe.fail_response = "qa refused"  # type: ignore[attr-defined]
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa refused"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    stored = json.loads(path.read_text(encoding="ascii"))
    job = stored["progress"]["repair_jobs"][-1]
    assert job["kind"] == "provider_response"
    assert calls == []
    assert "qa" not in stored["provider_object_references"]


@pytest.mark.asyncio
async def test_missing_variants_checkpoint_writes_nothing(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await prepare_aesthetics(spec, probe, path)
    raw = path.read_bytes()
    fixture = adapter_snapshot(probe)
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa requires the variants checkpoint"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []
    assert path.read_bytes() == raw
    assert adapter_snapshot(probe) == fixture
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["progress"]["repair_jobs"] == []


@pytest.mark.asyncio
async def test_catalogue_spec_and_live_probe_are_rejected(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="validated ProductSpec"):
        await run_product_qa(create_fixture_product_spec(), probe, path, recorded_at=QA_AT)
    with pytest.raises(ProductBuildError, match="fixture Notion probe"):
        await run_product_qa(spec, APINotionAdapter(), path, recorded_at=QA_AT)
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_tampered_fact_is_refused(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    def _lie(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        qa = references["qa"]
        assert type(qa) is dict
        facts = qa["facts"]
        assert type(facts) is list
        first = facts[0]
        assert type(first) is dict
        first["value"] = "changed"

    restamp_checkpoint(path, _lie)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa record does not match"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_stored_fail_repairable_is_an_accepted_shape(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    def _reword(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        qa = references["qa"]
        assert type(qa) is dict
        qa["verdict"] = "FAIL_REPAIRABLE"

    restamp_checkpoint(path, _reword)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa record does not match"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_qa_does_not_open_a_socket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tripwire: connect, connect_ex, and create_connection raise. Not a sandbox."""

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("socket connect is refused")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert checkpoint.qa is not None and checkpoint.qa.verdict == "PASS"
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
