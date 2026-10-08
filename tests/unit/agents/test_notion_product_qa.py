"""Fixture-only product QA. Not a seventh build phase and not the fact ledger."""

from __future__ import annotations

import json
import socket
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from money_machine.agents.implementations import notion_qa as notion_qa_module
from money_machine.agents.implementations.notion_hubs import section_content
from money_machine.agents.implementations.notion_product_builder import (
    SPEC_ID_PROPERTY,
    ProductBuildCheckpoint,
    ProductBuildError,
)
from money_machine.agents.implementations.notion_progress import (
    OP_QA,
    ProviderFailure,
    load_payload,
)
from money_machine.agents.implementations.notion_qa import PHASE_FACT_LEDGER, run_product_qa
from money_machine.agents.implementations.notion_variants import (
    PHASE_QA,
    build_variants,
    load_variant_checkpoint,
)
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.domain import (
    NotionCalloutBlock,
    NotionDatabase,
    NotionDatabaseProperty,
    NotionFormula,
    NotionLinkedView,
    NotionPage,
    NotionRelation,
    NotionTextBlock,
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
LATER = datetime(2026, 10, 6, 4, 30, tzinfo=UTC)


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


def _flag(checkpoint: ProductBuildCheckpoint, name: str) -> bool:
    assert checkpoint.qa is not None
    flags = dict(checkpoint.qa.checks)
    assert name in flags
    return flags[name]


def _false_checks(checkpoint: ProductBuildCheckpoint) -> tuple[str, ...]:
    assert checkpoint.qa is not None
    return tuple(name for name, passed in checkpoint.qa.checks if passed is False)


def _colour_pages(probe: FixtureNotionAdapter, spec: ProductSpec) -> list[NotionPage]:
    pages: list[NotionPage] = []
    for colour in spec.colour_variants:
        title = f"{spec.title} / {colour}"
        pages.append(next(page for page in probe.pages.values() if page.title == title))
    return pages


def _edit_variant_rows(
    document: dict[str, object], mutate: Callable[[dict[str, object]], None]
) -> None:
    references = document["provider_object_references"]
    assert type(references) is dict
    variants = references["variants"]
    assert type(variants) is list
    progress = document["progress"]
    assert type(progress) is dict
    created_ids = progress["created_notion_ids"]
    assert type(created_ids) is dict
    saved = created_ids["variants"]
    assert type(saved) is list
    assert len(variants) == len(saved)
    for row, copy in zip(variants, saved, strict=True):
        assert type(row) is dict and type(copy) is dict
        mutate(row)
        copy.clear()
        copy.update(row)


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
    host = "https://fixture.notion.site"
    assert stored["secret_links"] == ",".join([host] * len(spec.colour_variants))
    assert checkpoint.recorded_at == QA_AT
    assert all(page.id not in str(stored["secret_links"]) for page in probe.pages.values())


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
    home = next(iter(probe.pages.values()))
    probe.blocks["block_no_access"] = NotionTextBlock(
        id="block_no_access",
        parent_id=home.id,
        content="No access",
    )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.proof_page_id == ""
    assert _flag(checkpoint, "no_access_blocks") is False
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
    assert _flag(checkpoint, "duplicate_databases") is False
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
    assert _flag(checkpoint, "notification_values") is False
    assert _flag(checkpoint, "formulas_compile") is True
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
    assert _flag(checkpoint, "cross_catalogue") is False
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

    again = await run_product_qa(spec, probe, path, recorded_at=LATER)

    assert again.qa is not None and again.qa.verdict == "BLOCKED"
    assert again.recorded_at == QA_AT
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


class _ChildDatabase(NotionDatabase):
    """Subclass so isinstance accepts a database that type() would skip."""


class _ChildPage(NotionPage):
    """Subclass so type() rejects a page that a missing type check would accept."""


def _qa_reference(document: dict[str, object]) -> dict[str, object]:
    references = document["provider_object_references"]
    assert type(references) is dict
    qa = references["qa"]
    assert type(qa) is dict
    return qa


async def _built(tmp_path: Path) -> tuple[ProductSpec, FixtureNotionAdapter, Path]:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    await _variants(spec, probe, path)
    return spec, probe, path


def _load_replaced(
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[ProductBuildCheckpoint], ProductBuildCheckpoint],
) -> None:
    original = notion_qa_module.load_variant_checkpoint

    def _load(path: Path) -> tuple[ProductBuildCheckpoint, Mapping[str, object]]:
        stored, created = original(path)
        return mutate(stored), created

    monkeypatch.setattr(notion_qa_module, "load_variant_checkpoint", _load)


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 2, 3])
@pytest.mark.parametrize("defect", ["forged", "stranger"])
async def test_unpublished_variants_block_without_writes(
    tmp_path: Path, count: int, defect: str
) -> None:
    spec, probe, path = await _built(tmp_path)
    pages = _colour_pages(probe, spec)[:count]
    for page in pages:
        page.is_published = False
    if defect == "forged":
        targets = {page.id for page in pages}

        def _forge(document: dict[str, object]) -> None:
            def _one(row: dict[str, object]) -> None:
                if row["page_id"] in targets:
                    row["secret_link"] = "https://fixture.notion.site/forged"

            _edit_variant_rows(document, _one)

        restamp_checkpoint(path, _forge)
    else:

        async def _closed(_url: str) -> bool:
            return False

        probe.verify_stranger_access = _closed  # type: ignore[method-assign]
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ()
    assert checkpoint.qa.proof_page_id == ""
    assert _flag(checkpoint, "public_links") is False
    assert calls == []


@pytest.mark.asyncio
async def test_cleared_public_url_forged_link_does_not_publish(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    page.is_published = False
    page.public_url = None

    def _forge(document: dict[str, object]) -> None:
        def _one(row: dict[str, object]) -> None:
            if row["page_id"] == page.id:
                row["secret_link"] = "https://fixture.notion.site/forged"

        _edit_variant_rows(document, _one)

    restamp_checkpoint(path, _forge)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "public_links") is False
    assert calls == []


@pytest.mark.asyncio
async def test_unpublished_link_with_page_id_still_must_match_captured_url(
    tmp_path: Path,
) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    page.is_published = False

    def _forge(document: dict[str, object]) -> None:
        def _one(row: dict[str, object]) -> None:
            if row["page_id"] == page.id:
                row["secret_link"] = f"https://evil.notion.site/{page.id}"

        _edit_variant_rows(document, _one)

    restamp_checkpoint(path, _forge)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "public_links") is False
    assert calls == []


@pytest.mark.asyncio
async def test_published_live_url_must_match_the_stored_link(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    page.public_url = f"https://evil.notion.site/{page.id}"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "public_links") is False
    assert _flag(checkpoint, "facts_persisted") is False
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "forged",
    [
        "https://evil.notion.site/{page_id}",
        "https://fixture.notion.site/x/{page_id}",
        "https://user:pw@fixture.notion.site/{page_id}",
        "https://fixture.notion.site@evil.notion.site/{page_id}",
        "https://fixture.notion.site/{page_id}?x=1",
        "https://fixture.notion.site/{page_id}#frag",
    ],
)
async def test_matching_forged_unpublished_url_does_not_publish(
    tmp_path: Path, forged: str
) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    forged_url = forged.format(page_id=page.id)
    page.is_published = False
    page.public_url = forged_url

    def _forge(document: dict[str, object]) -> None:
        def _one(row: dict[str, object]) -> None:
            if row["page_id"] == page.id:
                row["secret_link"] = forged_url

        _edit_variant_rows(document, _one)

    restamp_checkpoint(path, _forge)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ()
    assert checkpoint.qa.proof_page_id == ""
    assert _flag(checkpoint, "public_links") is False
    assert calls == []
    assert page.is_published is False
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["progress"]["repair_jobs"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "forged",
    [
        "https://evil.notion.site/{page_id}",
        "https://fixture.notion.site/x/{page_id}",
        "https://user:pw@fixture.notion.site/{page_id}",
        "https://fixture.notion.site@evil.notion.site/{page_id}",
        "https://fixture.notion.site/{page_id}?x=1",
        "https://fixture.notion.site/{page_id}#frag",
        "http://fixture.notion.site/{page_id}",
    ],
)
async def test_unpublished_captured_url_must_match_the_fixture_shape(
    tmp_path: Path, forged: str
) -> None:
    """The captured URL is checked on its own. The stored link stays the fixture shape."""
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    page.is_published = False
    page.public_url = forged.format(page_id=page.id)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ()
    assert checkpoint.qa.proof_page_id == ""
    assert _flag(checkpoint, "public_links") is False
    assert calls == []
    assert page.is_published is False
    stored = json.loads(path.read_text(encoding="ascii"))
    assert stored["progress"]["repair_jobs"] == []


@pytest.mark.asyncio
async def test_unpublish_page_is_repaired_then_passes(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
    assert page.public_url is None
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "PASS"
    assert checkpoint.qa.repairs == ("published",)
    assert checkpoint.qa.proof_page_id != ""
    assert checkpoint.qa.proof_page_id in probe.pages
    assert calls == ["publish_page", "duplicate_page"]
    assert page.is_published is True
    assert page.public_url == "https://fixture.notion.site/" + page.id


@pytest.mark.asyncio
async def test_empty_captured_url_repairs_like_a_missing_url(tmp_path: Path) -> None:
    """Empty captured URL is skipped, the same as a missing URL, then repaired.

    The public-link contract skips a captured value that is missing or "".
    A real unpublish leaves public_url as None. "" takes that same repair.
    """
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
    page.public_url = ""
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "PASS"
    assert checkpoint.qa.repairs == ("published",)
    assert calls == ["publish_page", "duplicate_page"]
    assert page.is_published is True


@pytest.mark.asyncio
async def test_unpublish_publish_crash_then_resume_passes(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
    original = probe.publish_page
    failed = {"done": False}

    async def _boom(page_id: str) -> NotionPage:
        if not failed["done"]:
            failed["done"] = True
            raise RuntimeError("publish crashed")
        return await original(page_id)

    probe.publish_page = _boom  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="publish crashed"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert page.is_published is False
    assert "qa" not in json.loads(path.read_text(encoding="ascii"))["provider_object_references"]

    probe.publish_page = original  # type: ignore[method-assign]
    calls = watch_adapter_writes(probe)
    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "PASS"
    assert checkpoint.qa.proof_page_id != ""
    assert checkpoint.qa.proof_page_id in probe.pages
    assert calls == ["publish_page", "duplicate_page"]


@pytest.mark.asyncio
async def test_unpublish_checkpoint_crash_after_repair_resumes_to_pass(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
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
    assert page.is_published is True
    assert len(probe.pages) == started + 1
    assert "qa" not in json.loads(path.read_text(encoding="ascii"))["provider_object_references"]

    calls = watch_adapter_writes(probe)
    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "PASS"
    assert checkpoint.qa.proof_page_id != ""
    assert checkpoint.qa.proof_page_id in probe.pages
    assert calls == []
    assert len(probe.pages) == started + 1


@pytest.mark.asyncio
async def test_secret_link_facts_match_across_fresh_runs(tmp_path: Path) -> None:
    first_spec, first_probe, first_path = await _built(tmp_path / "one")
    second_spec, second_probe, second_path = await _built(tmp_path / "two")
    first = await run_product_qa(first_spec, first_probe, first_path, recorded_at=QA_AT)
    second = await run_product_qa(second_spec, second_probe, second_path, recorded_at=QA_AT)
    assert first.qa is not None and second.qa is not None
    assert first.qa.verdict == second.qa.verdict == "PASS"
    assert first.qa.checks == second.qa.checks
    assert first.qa.repairs == second.qa.repairs == ()
    assert first.qa.facts == second.qa.facts
    assert first.qa.proof_page_id != ""
    assert second.qa.proof_page_id != ""
    assert first.qa.proof_page_id != second.qa.proof_page_id
    assert first_probe.pages.keys() != second_probe.pages.keys()


@pytest.mark.asyncio
async def test_search_indexing_on_is_repaired_then_passes(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    page.search_indexing = True
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "PASS"
    assert checkpoint.qa.repairs == ("search_indexing",)
    assert calls == ["set_search_indexing", "duplicate_page"]
    assert page.search_indexing is False


@pytest.mark.asyncio
async def test_fixed_access_block_is_rerun_as_a_pass(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    block = next(iter(probe.blocks.values()))
    original = block.content
    block.content = f"{original} No access"
    blocked = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert blocked.qa is not None and blocked.qa.verdict == "BLOCKED"
    block.content = original
    calls = watch_adapter_writes(probe)

    again = await run_product_qa(spec, probe, path, recorded_at=LATER)

    assert again.qa is not None and again.qa.verdict == "PASS"
    assert again.recorded_at == LATER
    assert calls == ["duplicate_page"]


@pytest.mark.asyncio
async def test_structural_block_keeps_flag_repairs_off_the_record(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    page.is_published = False
    home = next(iter(probe.pages.values()))
    probe.blocks["block_no_access"] = NotionTextBlock(
        id="block_no_access",
        parent_id=home.id,
        content="No access",
    )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ()
    assert _flag(checkpoint, "published") is False
    assert _flag(checkpoint, "no_access_blocks") is False
    assert calls == []


@pytest.mark.asyncio
async def test_token_name_drift_fails_spec_coverage_only(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)

    def _rename(document: dict[str, object]) -> None:
        def _one(row: dict[str, object]) -> None:
            if row["name"] == "Blue":
                row["token"] = "Missing"

        _edit_variant_rows(document, _one)

    restamp_checkpoint(path, _rename)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "spec_coverage") is False
    assert _flag(checkpoint, "palette") is True
    assert calls == []


@pytest.mark.asyncio
async def test_renamed_database_fails_shared_databases_only(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    tasks = next(database for database in probe.databases.values() if database.title == "Tasks")
    tasks.title = "Tasks renamed"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "shared_databases") is False
    assert _flag(checkpoint, "duplicate_databases") is True
    assert calls == []


@pytest.mark.asyncio
async def test_database_subclass_is_an_extra_database(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    probe.databases["db_extra"] = _ChildDatabase(id="db_extra", title="Extra catalogue")
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "duplicate_databases") is False
    assert _flag(checkpoint, "cross_catalogue") is True
    assert calls == []


@pytest.mark.asyncio
async def test_database_subclasses_still_pass(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    for key, database in list(probe.databases.items()):
        probe.databases[key] = _ChildDatabase(
            id=database.id,
            title=database.title,
            parent_id=database.parent_id,
            parent_type=database.parent_type,
            icon=database.icon,
            cover=database.cover,
            properties=list(database.properties),
            created_at=database.created_at,
            updated_at=database.updated_at,
        )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "PASS"
    assert calls == ["duplicate_page"]


@pytest.mark.asyncio
async def test_subclass_database_foreign_relation_fails_cross_catalogue(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    key, database = next(iter(probe.databases.items()))
    probe.databases[key] = _ChildDatabase(
        id=database.id,
        title=database.title,
        parent_id=database.parent_id,
        parent_type=database.parent_type,
        properties=[
            *database.properties,
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
            ),
        ],
    )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "cross_catalogue") is False
    assert _flag(checkpoint, "shared_databases") is True
    assert _flag(checkpoint, "duplicate_databases") is True
    assert calls == []


@pytest.mark.asyncio
async def test_renamed_hub_fails_hubs_present_only(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    hub = next(page for page in probe.pages.values() if page.title.startswith("Hub "))
    hub.title = "Renamed hub"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "hubs_present") is False
    assert calls == []


@pytest.mark.asyncio
async def test_linked_view_pointed_at_another_known_database_is_blocked(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    _slug, view_id = stored.identity_hubs[0].views[0]
    view = probe.linked_views[view_id]
    other = next(
        database_id for database_id in probe.databases if database_id != view.source_database_id
    )
    view.source_database_id = other
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "linked_views") is False
    assert _flag(checkpoint, "cross_catalogue") is True
    assert calls == []


@pytest.mark.asyncio
async def test_missing_formula_input_fails_compile_only(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    tasks = next(database for database in probe.databases.values() if database.title == "Tasks")
    tasks.properties = [prop for prop in tasks.properties if prop.name != "Status"]
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "formulas_compile") is False
    assert _flag(checkpoint, "notification_values") is True
    assert calls == []


@pytest.mark.asyncio
async def test_extra_page_fails_page_count_only(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    probe.pages["page_loose"] = NotionPage(id="page_loose", title="Loose note")
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "page_count") is False
    assert _flag(checkpoint, "fresh_duplicate") is True
    assert calls == []


@pytest.mark.asyncio
async def test_dropped_variant_row_fails_variant_count(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)

    def _drop(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        variants = references["variants"]
        assert type(variants) is list and len(variants) == 3
        variants.pop()
        progress = document["progress"]
        assert type(progress) is dict
        created_ids = progress["created_notion_ids"]
        assert type(created_ids) is dict
        saved = created_ids["variants"]
        assert type(saved) is list and len(saved) == 3
        saved.pop()

    restamp_checkpoint(path, _drop)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "variant_count") is False
    assert _flag(checkpoint, "spec_coverage") is False
    assert calls == []


@pytest.mark.asyncio
async def test_colour_and_token_length_mismatch_is_blocked(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    short = spec.model_copy()
    object.__setattr__(short, "colour_variants", spec.colour_variants[:2])
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(short, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "spec_coverage") is False
    assert calls == []


@pytest.mark.asyncio
async def test_moved_variant_fails_fresh_duplicate_only(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    page.parent_type = "page_id"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "fresh_duplicate") is False
    assert _flag(checkpoint, "palette") is True
    assert calls == []


@pytest.mark.asyncio
async def test_changed_icon_fails_palette(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    page.icon = "not-the-icon"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "palette") is False
    assert calls == []


@pytest.mark.asyncio
async def test_edited_hub_section_fails_teardown_only(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    expected = section_content(spec, spec.hubs[0].name, "purpose")
    block = next(item for item in probe.blocks.values() if item.content == expected)
    block.content = f"{expected} edited"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "teardown_quality") is False
    assert calls == []


@pytest.mark.asyncio
async def test_two_proof_copies_are_ambiguous(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    source = _colour_pages(probe, spec)[0]
    await probe.duplicate_page(source.id)
    await probe.duplicate_page(source.id)
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa proof duplicate is ambiguous"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []
    stored = json.loads(path.read_text(encoding="ascii"))
    assert "qa" not in stored["provider_object_references"]


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["parent", "published", "icon", "cover", "spec_id"])
async def test_existing_proof_that_does_not_match_is_refused(tmp_path: Path, defect: str) -> None:
    spec, probe, path = await _built(tmp_path)
    source = _colour_pages(probe, spec)[0]
    copy = await probe.duplicate_page(source.id)
    if defect == "parent":
        copy.parent_type = "page_id"
    elif defect == "published":
        copy.is_published = True
    elif defect == "icon":
        copy.icon = "not-the-icon"
    elif defect == "cover":
        copy.cover = "not-the-cover"
    else:
        copy.properties[SPEC_ID_PROPERTY] = "spec_copied"
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa proof duplicate does not match"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []
    stored = json.loads(path.read_text(encoding="ascii"))
    assert "qa" not in stored["provider_object_references"]


@pytest.mark.asyncio
async def test_proof_name_must_be_the_first_colour(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    source = _colour_pages(probe, spec)[0]
    await probe.duplicate_page(source.id)

    def _rename(document: dict[str, object]) -> None:
        def _one(row: dict[str, object]) -> None:
            if row["name"] == spec.colour_variants[0]:
                row["name"] = "Teal"

        _edit_variant_rows(document, _one)

    restamp_checkpoint(path, _rename)
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa proof duplicate does not match"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []


@pytest.mark.asyncio
async def test_duplicate_that_returns_the_source_page_is_refused(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    source = _colour_pages(probe, spec)[0]

    async def _same(page_id: str) -> NotionPage:
        page = probe.pages[page_id]
        page.title = f"{spec.title} / {spec.colour_variants[0]} (Copy)"
        page.is_published = False
        return page

    probe.duplicate_page = _same  # type: ignore[method-assign]

    with pytest.raises(ProductBuildError, match="qa proof duplicate does not match"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    stored = json.loads(path.read_text(encoding="ascii"))
    assert "qa" not in stored["provider_object_references"]
    assert source.title.endswith("(Copy)")


@pytest.mark.asyncio
async def test_published_duplicate_is_not_accepted_as_proof(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    original = probe.duplicate_page

    async def _published(page_id: str) -> NotionPage:
        copy = await original(page_id)
        copy.is_published = True
        return copy

    probe.duplicate_page = _published  # type: ignore[method-assign]

    with pytest.raises(ProductBuildError, match="qa proof duplicate does not match"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    stored = json.loads(path.read_text(encoding="ascii"))
    assert "qa" not in stored["provider_object_references"]


@pytest.mark.asyncio
async def test_repair_guard_refuses_before_publish(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    page.is_published = False
    probe.fail_operation = OP_QA  # type: ignore[attr-defined]
    probe.fail_response = "qa refused"  # type: ignore[attr-defined]
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa refused"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []
    assert page.is_published is False
    stored = json.loads(path.read_text(encoding="ascii"))
    assert "qa" not in stored["provider_object_references"]


@pytest.mark.asyncio
async def test_other_spec_is_refused_before_a_plan(tmp_path: Path) -> None:
    _spec, probe, path = await _built(tmp_path)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="checkpoint belongs to a different ProductSpec"):
        await run_product_qa(planner_spec(), probe, path, recorded_at=QA_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_loaded_variants_checkpoint_is_already_in_qa(tmp_path: Path) -> None:
    """load_variant_checkpoint sets next_phase to qa whenever variants exist."""
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.variants
    assert stored.next_phase == PHASE_QA
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "PASS"
    assert calls == ["duplicate_page"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "match"),
    [
        ("object", "qa record must be an object"),
        ("missing", "qa record fields are missing or unsupported"),
        ("extra", "qa record fields are missing or unsupported"),
        ("verdict-type", "qa verdict is unsupported"),
        ("verdict-word", "qa verdict is unsupported"),
        ("proof-type", "qa proof page is unsupported"),
        ("checks-empty", "qa record is incomplete"),
        ("checks-item", "qa record is incomplete"),
        ("passed-yes", "qa record is incomplete"),
        ("passed-true-word", "qa record is incomplete"),
        ("repairs-dup", "qa record is incomplete"),
        ("repairs-word", "qa record is incomplete"),
        (
            "repairs-type",
            r"qa record is incomplete|checkpoint qa repair must be a non-empty string",
        ),
        ("repairs-shape", "qa record is incomplete"),
        ("repairs-int", "qa record is incomplete"),
        ("fact-blank", "checkpoint qa must be a non-empty string"),
        ("fact-type", "qa record is incomplete"),
    ],
)
async def test_incomplete_qa_record_is_refused(tmp_path: Path, kind: str, match: str) -> None:
    spec, probe, path = await _built(tmp_path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    def _mutate(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        if kind == "object":
            references["qa"] = []
            return
        qa = _qa_reference(document)
        if kind == "missing":
            del qa["verdict"]
        elif kind == "extra":
            qa["extra"] = "no"
        elif kind == "verdict-type":
            qa["verdict"] = 1
        elif kind == "verdict-word":
            qa["verdict"] = "MAYBE"
        elif kind == "proof-type":
            qa["proof_page_id"] = 1
        elif kind == "checks-empty":
            qa["checks"] = []
        elif kind == "checks-item":
            qa["checks"] = ["published"]
        elif kind == "passed-yes":
            checks = qa["checks"]
            assert type(checks) is list
            first = checks[0]
            assert type(first) is dict
            first["passed"] = "yes"
        elif kind == "passed-true-word":
            checks = qa["checks"]
            assert type(checks) is list
            first = checks[0]
            assert type(first) is dict
            first["passed"] = "TRUE"
        elif kind == "repairs-dup":
            qa["repairs"] = ["published", "published"]
        elif kind == "repairs-word":
            qa["repairs"] = ["nope"]
        elif kind == "repairs-type":
            qa["repairs"] = [1]
        elif kind == "repairs-shape":
            qa["repairs"] = "published"
        elif kind == "repairs-int":
            qa["repairs"] = 1
        elif kind == "fact-blank":
            facts = qa["facts"]
            assert type(facts) is list
            first = facts[0]
            assert type(first) is dict
            first["value"] = ""
        else:
            facts = qa["facts"]
            assert type(facts) is list
            first = facts[0]
            assert type(first) is dict
            first["value"] = 1

    restamp_checkpoint(path, _mutate)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match=match):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_integer_repair_item_is_refused_before_any_write(tmp_path: Path) -> None:
    """A non-string repair is refused. require_token refuses that same input too."""
    spec, probe, path = await _built(tmp_path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    def _mutate(document: dict[str, object]) -> None:
        _qa_reference(document)["repairs"] = [1]

    restamp_checkpoint(path, _mutate)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(
        ProductBuildError,
        match=r"qa record is incomplete|checkpoint qa repair must be a non-empty string",
    ):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_tampered_blocked_fact_is_refused(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    home = next(iter(probe.pages.values()))
    probe.blocks["block_no_access"] = NotionTextBlock(
        id="block_no_access",
        parent_id=home.id,
        content="No access",
    )
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    def _lie(document: dict[str, object]) -> None:
        facts = _qa_reference(document)["facts"]
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
async def test_blocked_record_with_a_proof_id_is_refused(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    home = next(iter(probe.pages.values()))
    probe.blocks["block_no_access"] = NotionTextBlock(
        id="block_no_access",
        parent_id=home.id,
        content="No access",
    )
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    def _proof(document: dict[str, object]) -> None:
        _qa_reference(document)["proof_page_id"] = "page_proof"

    restamp_checkpoint(path, _proof)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa record does not match"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("proof_id", ["page_forged", ""])
async def test_tampered_pass_proof_id_is_refused(tmp_path: Path, proof_id: str) -> None:
    spec, probe, path = await _built(tmp_path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    def _swap(document: dict[str, object]) -> None:
        _qa_reference(document)["proof_page_id"] = proof_id

    restamp_checkpoint(path, _swap)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa record does not match"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("check", ["no_access_blocks", "published"])
async def test_forged_pass_matching_a_failed_check_is_refused(tmp_path: Path, check: str) -> None:
    """A stored PASS whose checks were rewritten to the live failure is still refused."""
    spec, probe, path = await _built(tmp_path)
    passed = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert passed.qa is not None and passed.qa.verdict == "PASS"
    if check == "no_access_blocks":
        home = next(iter(probe.pages.values()))
        probe.blocks["block_no_access"] = NotionTextBlock(
            id="block_no_access",
            parent_id=home.id,
            content="No access",
        )
    else:
        await probe.unpublish_page(_colour_pages(probe, spec)[0].id)

    def _forge(document: dict[str, object]) -> None:
        checks = _qa_reference(document)["checks"]
        assert type(checks) is list
        for item in checks:
            assert type(item) is dict
            if item["check"] == check:
                item["passed"] = "false"

    restamp_checkpoint(path, _forge)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa record does not match"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_stored_pass_with_a_new_unpublished_page_is_refused(tmp_path: Path) -> None:
    """A drifted PASS is refused by the checks compare before the blocked guard."""
    spec, probe, path = await _built(tmp_path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    _colour_pages(probe, spec)[0].is_published = False
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa record does not match"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_duplicate_with_the_wrong_title_is_refused(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    original = probe.duplicate_page

    async def _retitle(page_id: str) -> NotionPage:
        copy = await original(page_id)
        copy.title = "not the proof title"
        return copy

    probe.duplicate_page = _retitle  # type: ignore[method-assign]

    with pytest.raises(ProductBuildError, match="qa proof duplicate does not match"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    stored = json.loads(path.read_text(encoding="ascii"))
    assert "qa" not in stored["provider_object_references"]


@pytest.mark.asyncio
async def test_business_database_order_fails_shared_databases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = planner_spec(
        tier="business", identity="Studio Ledger", title="Studio Home", hub_name="Desk"
    )
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    _load_replaced(
        monkeypatch,
        lambda stored: replace(stored, database_ids=tuple(reversed(stored.database_ids))),
    )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "shared_databases") is False
    assert calls == []


@pytest.mark.asyncio
async def test_renamed_notification_database_fails_notification_values(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    probe.databases[stored.notification_dashboard.database_id].title = "Not the dashboard"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "notification_values") is False
    assert calls == []


@pytest.mark.asyncio
async def test_foreign_linked_view_fails_cross_catalogue(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    probe.linked_views["view_foreign"] = NotionLinkedView(
        id="view_foreign",
        source_database_id="db_foreign",
        parent_page_id=next(iter(probe.pages.values())).id,
    )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "cross_catalogue") is False
    assert calls == []


@pytest.mark.asyncio
async def test_removed_blue_accent_fails_palette(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    blue = next(record for record in stored.variants if record.name == "Blue")
    del probe.blocks[blue.accent_block_id]
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "palette") is False
    assert calls == []


@pytest.mark.asyncio
async def test_empty_evidence_fails_teardown(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    empty = spec.model_copy()
    object.__setattr__(empty, "evidence", ())
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(empty, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "teardown_quality") is False
    assert calls == []


@pytest.mark.asyncio
async def test_missing_known_page_fails_page_count(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    sample_id = stored.notification_dashboard.samples[0][1]
    del probe.pages[sample_id]
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "page_count") is False
    assert calls == []


@pytest.mark.asyncio
async def test_missing_variant_page_is_a_product_build_error(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    del probe.pages[stored.variants[0].page_id]
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa variant page is missing"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []


@pytest.mark.asyncio
async def test_missing_formula_database_is_blocked(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    tasks_id = next(
        database_id
        for database_id, database in probe.databases.items()
        if database.title == "Tasks"
    )
    del probe.databases[tasks_id]
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "formulas_compile") is False
    assert _flag(checkpoint, "notification_values") is False
    assert calls == []


@pytest.mark.asyncio
async def test_missing_notification_dashboard_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, probe, path = await _built(tmp_path)
    _load_replaced(monkeypatch, lambda stored: replace(stored, notification_dashboard=None))
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="notification dashboard is missing"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert calls == []


@pytest.mark.asyncio
async def test_reordered_hubs_fail_hubs_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, probe, path = await _built(tmp_path)
    _load_replaced(
        monkeypatch,
        lambda stored: replace(stored, identity_hubs=tuple(reversed(stored.identity_hubs))),
    )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "hubs_present") is False
    assert calls == []


@pytest.mark.asyncio
async def test_view_of_the_notification_database_stays_in_catalogue(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    probe.linked_views["view_notice"] = NotionLinkedView(
        id="view_notice",
        source_database_id=stored.notification_dashboard.database_id,
        parent_page_id=stored.page_id,
    )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "PASS"
    assert _flag(checkpoint, "cross_catalogue") is True
    assert calls == ["duplicate_page"]


@pytest.mark.asyncio
async def test_non_database_value_is_skipped(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    cast(dict[str, object], probe.databases)["db_not"] = object()
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "PASS"
    assert _flag(checkpoint, "cross_catalogue") is True
    assert calls == ["duplicate_page"]


@pytest.mark.asyncio
async def test_renamed_variant_fails_palette(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)

    def _rename(document: dict[str, object]) -> None:
        def _one(row: dict[str, object]) -> None:
            if row["name"] == "Blue":
                row["name"] = "Blueish"

        _edit_variant_rows(document, _one)

    restamp_checkpoint(path, _rename)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "palette") is False
    assert _flag(checkpoint, "spec_coverage") is False
    assert calls == []


@pytest.mark.asyncio
async def test_missing_linked_view_is_blocked(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    _slug, view_id = stored.identity_hubs[0].views[0]
    del probe.linked_views[view_id]
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "linked_views") is False
    assert calls == []


@pytest.mark.asyncio
async def test_public_entry_payload_and_qa_record_are_present(tmp_path: Path) -> None:
    """The public entry always has a payload, and the writer always has a qa record."""
    spec, probe, path = await _built(tmp_path)
    envelope = load_payload(path)
    assert envelope.payload is not None
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None and checkpoint.qa.verdict == "PASS"
    assert calls == ["duplicate_page"]
    written = load_payload(path)
    assert written.payload is not None
    references = written.payload["provider_object_references"]
    assert type(references) is dict and type(references["qa"]) is dict


@pytest.mark.asyncio
async def test_shared_database_off_the_home_page_is_blocked(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    _kind, database_id = stored.database_ids[0]
    probe.databases[database_id].parent_id = "not-the-home-page"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ()
    assert _false_checks(checkpoint) == ("shared_databases",)
    assert calls == []


def _fresh_duplicate_outcome(
    checkpoint: ProductBuildCheckpoint | None, caught: ProductBuildError | None
) -> tuple[tuple[str, ...], ProductBuildError | None]:
    """Return the false checks. The caller asserts adapter writes before this result."""
    if caught is not None:
        return (), caught
    assert checkpoint is not None and checkpoint.qa is not None
    return _false_checks(checkpoint), None


@pytest.mark.asyncio
async def test_renamed_variant_page_fails_fresh_duplicate(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    page.title = "TAMPERED"
    calls = watch_adapter_writes(probe)
    checkpoint: ProductBuildCheckpoint | None = None
    caught: ProductBuildError | None = None
    try:
        checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    except ProductBuildError as error:
        caught = error

    false_checks, error = _fresh_duplicate_outcome(checkpoint, caught)

    assert calls == []
    assert false_checks == ("fresh_duplicate",)
    assert error is None
    assert checkpoint is not None and checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ()


@pytest.mark.asyncio
async def test_forged_spec_id_fails_fresh_duplicate(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    page.properties[SPEC_ID_PROPERTY] = "forged-spec"
    calls = watch_adapter_writes(probe)
    checkpoint: ProductBuildCheckpoint | None = None
    caught: ProductBuildError | None = None
    try:
        checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    except ProductBuildError as error:
        caught = error

    false_checks, error = _fresh_duplicate_outcome(checkpoint, caught)

    assert calls == []
    assert false_checks == ("fresh_duplicate",)
    assert error is None
    assert checkpoint is not None and checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ()


@pytest.mark.asyncio
async def test_lying_publish_stays_blocked_without_a_duplicate(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
    original = probe.publish_page

    async def _lie(page_id: str) -> NotionPage:
        published = await original(page_id)
        published.public_url = ""
        return published

    probe.publish_page = _lie  # type: ignore[method-assign]
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ()
    assert checkpoint.qa.proof_page_id == ""
    assert calls == ["publish_page"]
    assert page.is_published is True
    assert page.public_url == ""


@pytest.mark.asyncio
async def test_vocabulary_callout_fails_palette(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    block = probe.blocks[stored.variants[0].vocabulary_block_id]
    assert type(block) is NotionTextBlock
    assert block.content.startswith("SAMPLE ")
    probe.blocks[block.id] = NotionCalloutBlock(
        id=block.id,
        parent_id=block.parent_id,
        content=block.content,
    )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ()
    assert _false_checks(checkpoint) == ("palette",)
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["icon", "cover"])
async def test_fresh_duplicate_icon_and_cover_stay_in_the_false_set(
    tmp_path: Path, field: str
) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    if field == "icon":
        page.icon = "not-the-icon"
    else:
        page.cover = "not-the-cover"
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ()
    assert _false_checks(checkpoint) == ("fresh_duplicate", "palette")
    assert calls == []


@pytest.mark.asyncio
async def test_notification_row_subclass_fails_notification_values(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    assert stored.notification_dashboard is not None
    row = probe.pages[stored.notification_dashboard.row_page_id]
    probe.pages[row.id] = _ChildPage(
        id=row.id,
        title=row.title,
        parent_id=row.parent_id,
        parent_type=row.parent_type,
        icon=row.icon,
        cover=row.cover,
        public_url=row.public_url,
        is_published=row.is_published,
        duplicate_as_template=row.duplicate_as_template,
        search_indexing=row.search_indexing,
        created_at=row.created_at,
        updated_at=row.updated_at,
        properties=dict(row.properties),
    )
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ()
    assert _false_checks(checkpoint) == ("notification_values", "page_count", "facts_persisted")
    assert calls == []


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
