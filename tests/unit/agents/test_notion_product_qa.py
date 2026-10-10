"""Fixture-only product QA. Not a seventh build phase and not the fact ledger."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import traceback
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from money_machine.agents.implementations import notion_qa as notion_qa_module
from money_machine.agents.implementations.notion_aesthetics import accent_content
from money_machine.agents.implementations.notion_dashboard import (
    identity_callout,
)
from money_machine.agents.implementations.notion_dashboard import (
    navigation_content as home_navigation_content,
)
from money_machine.agents.implementations.notion_hubs import (
    navigation_content as hub_navigation_content,
)
from money_machine.agents.implementations.notion_hubs import (
    section_content,
)
from money_machine.agents.implementations.notion_product_builder import (
    SPEC_ID_PROPERTY,
    ProductBuildCheckpoint,
    ProductBuildError,
)
from money_machine.agents.implementations.notion_progress import (
    OP_QA,
    ProviderFailure,
    load_payload,
    raise_recorded,
    record_applied_repairs,
)
from money_machine.agents.implementations.notion_qa import (
    PHASE_FACT_LEDGER,
    load_qa_record,
    prose_digest,
    run_product_qa,
)
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
@pytest.mark.parametrize("content", [None, 5])
async def test_non_text_block_content_is_a_product_error(tmp_path: Path, content: object) -> None:
    """None or an int in block content is a typed error, not a TypeError."""
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    home = next(iter(probe.pages.values()))
    block = NotionTextBlock(id="block_bad_content", parent_id=home.id, content="ok")
    block.content = content  # pyright: ignore[reportAttributeAccessIssue]
    probe.blocks[block.id] = block
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match="qa block content is not text"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert path.read_bytes() == raw


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


class _LyingFormula(str):
    """A str subclass that claims to equal any non-empty expression."""

    def __eq__(self, other: object) -> bool:
        return other != ""


@pytest.mark.asyncio
async def test_lying_formula_expression_is_not_a_string(tmp_path: Path) -> None:
    """QA refuses a str subclass. Equality that always matches is not enough."""
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    changed = False
    for database in probe.databases.values():
        for prop in database.properties:
            formula = prop.config.get("formula")
            if (
                type(formula) is NotionFormula
                and type(formula.expression) is str
                and formula.expression != ""
            ):
                # The text matches the spec, so ``!=`` does not refuse it.
                # ``str.__ne__`` ignores a lying ``__eq__`` when the text differs.
                formula.expression = _LyingFormula(formula.expression)
                changed = True
                break
        if changed:
            break
    assert changed
    values = notion_qa_module._notification_values  # pyright: ignore[reportPrivateUsage]
    assert values(probe, stored, spec) is False
    calls = watch_adapter_writes(probe)
    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert checkpoint.qa is not None and checkpoint.qa.verdict == "BLOCKED"
    assert _flag(checkpoint, "notification_values") is False
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
    # A provider error of any kind is recorded under the fixed text, not raised raw.
    with pytest.raises(ProductBuildError, match=r"^provider operation failed$") as caught:
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert "step crashed" not in str(caught.value)
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
    with pytest.raises(ProductBuildError, match=r"^provider operation failed$"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    stored = json.loads(path.read_text(encoding="ascii"))
    job = stored["progress"]["repair_jobs"][-1]
    assert job["kind"] == "provider_response"
    assert job["operation"] == OP_QA
    assert job["response"] == "provider operation failed"
    assert "url refused" not in path.read_text(encoding="ascii")
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

    with pytest.raises(ProductBuildError, match=r"^provider operation failed$"):
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
    # A provider error of any kind is recorded under the fixed text, not raised raw.
    with pytest.raises(ProductBuildError, match=r"^provider operation failed$") as caught:
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert "publish crashed" not in str(caught.value)
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

    with pytest.raises(ProductBuildError, match=r"^provider operation failed$"):
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
@pytest.mark.parametrize("digest", [5, "a" * 63, "", "g" * 64, "A" * 64])
async def test_prose_digest_must_be_lowercase_hex(tmp_path: Path, digest: object) -> None:
    """Helper and public entry. A short, empty, non-hex, or non-string digest is incomplete."""
    spec, probe, path = await _built(tmp_path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    stored = dict(_qa_body(path))
    stored["prose_digest"] = digest
    require = notion_qa_module._require_qa  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError, match="qa record is incomplete"):
        require(stored)

    def _mutate(document: dict[str, object]) -> None:
        _qa_reference(document)["prose_digest"] = digest

    restamp_checkpoint(path, _mutate)
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)
    with pytest.raises(ProductBuildError, match="qa record is incomplete"):
        await run_product_qa(spec, probe, path, recorded_at=LATER)
    assert calls == []
    assert path.read_bytes() == raw


def _newline_joined(spec: ProductSpec) -> str:
    rows = [hub.description for hub in spec.hubs]
    rows.append(spec.buyer_problem)
    rows.append(spec.flagship_feature)
    return "\n".join(rows)


def test_prose_digest_newline_boundary_does_not_collide() -> None:
    """A newline inside one field must not hash as the next field.

    Joining on a newline makes ``alpha\\nbeta`` plus buyer ``gamma`` the same
    text as description ``alpha`` plus buyer ``beta\\ngamma``.
    """
    base = planner_spec()
    last = base.hubs[-1]
    left = base.model_copy(
        update={
            "hubs": (*base.hubs[:-1], last.model_copy(update={"description": "alpha\nbeta"})),
            "buyer_problem": "gamma",
        }
    )
    right = base.model_copy(
        update={
            "hubs": (*base.hubs[:-1], last.model_copy(update={"description": "alpha"})),
            "buyer_problem": "beta\ngamma",
        }
    )
    assert _newline_joined(left) == _newline_joined(right)
    assert prose_digest(left) != prose_digest(right)


def _rewrite_purposes(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, spec: ProductSpec
) -> None:
    for hub in stored.identity_hubs:
        for role, block_id in hub.sections:
            if role != "purpose":
                continue
            block = probe.blocks[block_id]
            assert type(block) is NotionTextBlock
            block.content = section_content(spec, hub.name, role)


@pytest.mark.asyncio
async def test_judged_caller_can_refresh_changed_prose(tmp_path: Path) -> None:
    """Same hub names and the same row identity may be judged again."""
    spec, probe, path = await _built(tmp_path)
    first_run = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert first_run.qa is not None
    stored, _created = load_variant_checkpoint(path)
    edited = spec.hubs[0].model_copy(update={"description": spec.hubs[0].description + " Edited"})
    caller = spec.model_copy(update={"hubs": (edited, *spec.hubs[1:])})
    _rewrite_purposes(probe, stored, caller)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(caller, probe, path, recorded_at=LATER)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "PASS"
    assert checkpoint.qa.prose_digest == prose_digest(caller)
    assert checkpoint.qa.prose_digest != first_run.qa.prose_digest
    assert checkpoint.recorded_at == LATER
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["renamed", "forged"])
async def test_mismatched_caller_cannot_refresh_changed_prose(tmp_path: Path, kind: str) -> None:
    """A digest change from a caller QA did not judge writes nothing."""
    spec, probe, path = await _built(tmp_path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    edited = spec.hubs[0].model_copy(update={"description": spec.hubs[0].description + " Edited"})
    hubs = (edited, *spec.hubs[1:])
    if kind == "renamed":
        hubs = tuple(hub.model_copy(update={"name": "Other " + hub.name}) for hub in hubs)
        caller = spec.model_copy(update={"hubs": hubs})
    else:
        caller = spec.model_copy(update={"hubs": hubs, "identity": "Not The Row"})
    raw = path.read_bytes()
    calls = watch_adapter_writes(probe)

    with pytest.raises(ProductBuildError, match="qa caller does not match"):
        await run_product_qa(caller, probe, path, recorded_at=LATER)

    assert calls == []
    assert path.read_bytes() == raw
    assert prose_digest(caller) != prose_digest(spec)


@pytest.mark.asyncio
async def test_query_userinfo_and_fragment_are_not_secret_link_facts(tmp_path: Path) -> None:
    """The fact keeps scheme and host. Userinfo, the query, and the fragment do not."""
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    secret = "sk-live-secret"
    forged = f"https://user:{secret}@fixture.notion.site/{page.id}?{secret}=1#{secret}"
    page.is_published = False
    page.public_url = forged

    def _forge(document: dict[str, object]) -> None:
        def _one(row: dict[str, object]) -> None:
            if row["page_id"] == page.id:
                row["secret_link"] = forged

        _edit_variant_rows(document, _one)

    restamp_checkpoint(path, _forge)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    facts = dict(checkpoint.qa.facts)
    host = "https://fixture.notion.site"
    assert facts["secret_links"] == ",".join([host] * len(spec.colour_variants))
    assert secret not in json.dumps(_qa_body(path))
    assert calls == []


@pytest.mark.asyncio
async def test_non_url_secret_link_fact_is_missing(tmp_path: Path) -> None:
    """A raw token is not copied into the fact."""
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    secret = "sk-live-secret"
    page.is_published = False
    page.public_url = secret

    def _forge(document: dict[str, object]) -> None:
        def _one(row: dict[str, object]) -> None:
            if row["page_id"] == page.id:
                row["secret_link"] = secret

        _edit_variant_rows(document, _one)

    restamp_checkpoint(path, _forge)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    facts = dict(checkpoint.qa.facts)
    hosts = ["missing", *(["https://fixture.notion.site"] * (len(spec.colour_variants) - 1))]
    assert facts["secret_links"] == ",".join(hosts)
    assert secret not in json.dumps(_qa_body(path))


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
    page.duplicate_as_template = False
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
    assert checkpoint.qa.repairs == ("published",)
    assert checkpoint.qa.proof_page_id == ""
    assert calls == ["publish_page"]
    assert page.is_published is True
    assert page.public_url == ""


@pytest.mark.asyncio
async def test_unpublished_and_duplicate_off_repairs_both(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
    page.duplicate_as_template = False
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "PASS"
    assert checkpoint.qa.repairs == ("published", "duplicate_button")
    assert calls == ["publish_page", "set_duplicate_as_template", "duplicate_page"]
    assert page.is_published is True
    assert page.duplicate_as_template is True


@pytest.mark.asyncio
async def test_untrusted_publish_does_not_set_the_duplicate(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
    page.duplicate_as_template = False
    original = probe.publish_page

    async def _lie(page_id: str) -> NotionPage:
        published = await original(page_id)
        published.is_published = True
        published.public_url = "https://evil.example/not-trusted"
        return published

    probe.publish_page = _lie  # type: ignore[method-assign]
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ("published",)
    assert calls == ["publish_page"]
    assert page.duplicate_as_template is False


@pytest.mark.asyncio
async def test_publish_that_stays_unpublished_does_not_set_duplicate(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
    page.duplicate_as_template = False
    original = probe.publish_page

    async def _lie(page_id: str) -> NotionPage:
        published = await original(page_id)
        published.is_published = False
        published.public_url = "https://fixture.notion.site/" + page_id
        return published

    probe.publish_page = _lie  # type: ignore[method-assign]
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ("published",)
    assert calls == ["publish_page"]
    assert page.duplicate_as_template is False


@pytest.mark.asyncio
async def test_pass_with_a_false_check_is_refused(tmp_path: Path) -> None:
    spec, probe, path = await _built(tmp_path)
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    def _false_check(document: dict[str, object]) -> None:
        references = document["provider_object_references"]
        assert type(references) is dict
        qa = references["qa"]
        assert type(qa) is dict
        checks = qa["checks"]
        assert type(checks) is list
        row = checks[0]
        assert type(row) is dict
        row["passed"] = "false"

    restamp_checkpoint(path, _false_check)
    with pytest.raises(ProductBuildError, match="qa record does not match"):
        load_qa_record(path)


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
    assert _false_checks(checkpoint) == ("notification_values", "facts_persisted")
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


QA_SECRET = "sk-live-qa-secret"


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [QA_SECRET, "qa " + QA_SECRET, "fact ledger " + QA_SECRET])
async def test_provider_response_is_not_stored_raised_or_chained(
    tmp_path: Path, response: str
) -> None:
    """The QA provider job and the raised error carry fixed text only."""
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)
    probe.fail_operation = OP_QA  # type: ignore[attr-defined]
    probe.fail_response = response  # type: ignore[attr-defined]

    with pytest.raises(ProductBuildError) as caught:
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    error = caught.value
    assert str(error) == "provider operation failed"
    assert error.args == ("provider operation failed",)
    assert error.__context__ is None
    cause = error.__cause__
    assert type(cause) is ProviderFailure
    assert cause.operation == OP_QA
    assert cause.response == "provider operation failed"
    assert cause.args == ("provider operation failed",)
    assert cause.__cause__ is None
    assert cause.__context__ is None
    assert QA_SECRET not in "".join(traceback.format_exception(error))
    assert QA_SECRET not in path.read_text(encoding="ascii")
    stored = json.loads(path.read_text(encoding="ascii"))
    jobs = [job for job in stored["progress"]["repair_jobs"] if job["kind"] == "provider_response"]
    assert len(jobs) == 1
    assert jobs[0]["response"] == "provider operation failed"
    assert "qa" not in stored["provider_object_references"]


def _connection_error() -> Exception:
    return ConnectionError("sk-live-secret")


def _runtime_error() -> Exception:
    error = RuntimeError("upstream said sk-live-secret")
    error.add_note("sk-live-secret")
    return error


def _chained_runtime_error() -> Exception:
    try:
        raise OSError("sk-live-secret")
    except OSError as inner:
        error = RuntimeError("sk-live-secret")
        error.__cause__ = inner
        return error


def _all_text(error: BaseException) -> str:
    """Every string reachable from the error: text, args, notes, chain, traceback."""
    seen: list[str] = []
    stack: list[BaseException | None] = [error]
    while stack:
        item = stack.pop()
        if item is None:
            continue
        seen.append(str(item))
        seen.append(repr(item.args))
        seen.extend(str(note) for note in getattr(item, "__notes__", ()))
        seen.append(repr(vars(item)))
        stack.extend([item.__cause__, item.__context__])
    seen.append("".join(traceback.format_exception(error)))
    return "\n".join(seen)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "make",
    [
        _connection_error,
        _runtime_error,
        _chained_runtime_error,
        lambda: OSError("sk-live-secret"),
        lambda: ValueError("sk-live-secret"),
    ],
)
async def test_any_provider_exception_is_recorded_under_the_fixed_text(
    tmp_path: Path, make: Callable[[], Exception]
) -> None:
    """A non-ProviderFailure provider error carrying a secret is mapped, not raised raw.

    Message, args, cause, context, notes, and traceback hold no secret, and the
    stored provider job has the fixed response only.
    """
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await _variants(spec, probe, path)

    async def _boom(*_args: object, **_kwargs: object) -> NotionPage:
        raise make()

    probe.duplicate_page = _boom  # type: ignore[method-assign]

    with pytest.raises(ProductBuildError) as caught:
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    error = caught.value
    assert str(error) == "provider operation failed"
    assert error.args == ("provider operation failed",)
    assert error.__context__ is None
    cause = error.__cause__
    assert type(cause) is ProviderFailure
    assert cause.args == ("provider operation failed",)
    assert cause.__cause__ is None
    assert cause.__context__ is None
    assert "sk-live-secret" not in _all_text(error)
    assert "sk-live-secret" not in path.read_text(encoding="ascii")
    stored = json.loads(path.read_text(encoding="ascii"))
    jobs = [job for job in stored["progress"]["repair_jobs"] if job["kind"] == "provider_response"]
    assert len(jobs) == 1
    assert jobs[0]["response"] == "provider operation failed"
    assert "qa" not in stored["provider_object_references"]


@pytest.mark.asyncio
async def test_own_refusal_inside_qa_keeps_its_text(tmp_path: Path) -> None:
    """A ProductBuildError raised by QA's own code is an own refusal, not a provider job."""
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    del probe.pages[stored.variants[0].page_id]
    raw = path.read_bytes()

    with pytest.raises(ProductBuildError, match=r"^qa variant page is missing$"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert path.read_bytes() == raw


def _provider_jobs(path: Path) -> list[dict[str, str]]:
    stored = json.loads(path.read_text(encoding="ascii"))
    jobs = stored["progress"]["repair_jobs"]
    return [job for job in jobs if job["kind"] == "provider_response"]


def _every_text(error: BaseException) -> str:
    """_all_text plus repr and each non-dunder attribute of the error and its group members."""
    seen = [_all_text(error)]
    pending: list[BaseException] = [error]
    while pending:
        item = pending.pop()
        seen.append(repr(item))
        seen.extend(repr(getattr(item, name)) for name in dir(item) if not name.startswith("__"))
        if isinstance(item, BaseExceptionGroup):
            pending.extend(cast(tuple[BaseException, ...], item.exceptions))
    return "\n".join(seen)


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["", "qa ", "checkpoint "])
async def test_provider_product_build_error_is_a_provider_job(tmp_path: Path, prefix: str) -> None:
    """A provider-raised ProductBuildError is recorded under the fixed text, not raised raw."""
    spec, probe, path = await _built(tmp_path)

    async def _boom(*_args: object, **_kwargs: object) -> NotionPage:
        raise ProductBuildError(prefix + "sk-live-secret")

    probe.duplicate_page = _boom  # type: ignore[method-assign]
    with pytest.raises(ProductBuildError) as caught:
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert caught.value.args == ("provider operation failed",)
    assert caught.value.__context__ is None
    assert type(caught.value.__cause__) is ProviderFailure
    assert "sk-live-secret" not in _every_text(caught.value)
    assert "sk-live-secret" not in path.read_text(encoding="ascii")
    assert [job["response"] for job in _provider_jobs(path)] == ["provider operation failed"]


class _StrInterrupt(KeyboardInterrupt):
    """A provider interrupt whose text is the secret."""

    def __str__(self) -> str:
        return "token=sk-live-secret"


def _noted_keyboard() -> BaseException:
    error = KeyboardInterrupt("sk-live-secret")
    error.add_note("sk-live-secret")
    return error


def _interrupt_group() -> BaseException:
    return BaseExceptionGroup("sk-live-secret", [_StrInterrupt(), RuntimeError("sk-live-secret")])


def _identity_interrupt(shape: str) -> type[BaseException]:
    """Round 11: a KeyboardInterrupt subclass whose name, qualname, module, or doc is the secret."""
    secret = "sk-live-secret"
    bodies: dict[str, tuple[str, dict[str, object]]] = {
        "name": (secret, {"__module__": __name__}),
        "qualname": ("_Qualname", {"__module__": __name__, "__qualname__": "probe." + secret}),
        "module": ("_Module", {"__module__": secret}),
        "doc": ("_Doc", {"__module__": __name__, "__doc__": secret}),
    }
    name, body = bodies[shape]
    return cast(type[BaseException], type(name, (KeyboardInterrupt,), body))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("make", "kinds", "args"),
    [
        (_noted_keyboard, [KeyboardInterrupt], ()),
        (lambda: asyncio.CancelledError("sk-live-secret"), [asyncio.CancelledError], ()),
        (lambda: SystemExit("sk-live-secret"), [SystemExit], (1,)),
        (_StrInterrupt, [KeyboardInterrupt], ()),
        (_identity_interrupt("name"), [KeyboardInterrupt], ()),
        (_identity_interrupt("qualname"), [KeyboardInterrupt], ()),
        (_identity_interrupt("module"), [KeyboardInterrupt], ()),
        (_identity_interrupt("doc"), [KeyboardInterrupt], ()),
        (
            lambda: BaseExceptionGroup("w", [_identity_interrupt("name")()]),
            [BaseExceptionGroup, KeyboardInterrupt],
            ("provider operation failed", [KeyboardInterrupt()]),
        ),
        (
            _interrupt_group,
            [BaseExceptionGroup, KeyboardInterrupt, Exception],
            (
                "provider operation failed",
                [KeyboardInterrupt(), Exception("provider operation failed")],
            ),
        ),
    ],
)
async def test_provider_interrupt_in_qa_becomes_its_built_in_base(
    tmp_path: Path,
    make: Callable[[], BaseException],
    kinds: list[type[BaseException]],
    args: tuple[object, ...],
) -> None:
    """A BaseException from the provider propagates cleaned, with no text, chain, or write."""
    spec, probe, path = await _built(tmp_path)
    raw = path.read_bytes()

    async def _boom(*_args: object, **_kwargs: object) -> NotionPage:
        raise make()

    probe.duplicate_page = _boom  # type: ignore[method-assign]
    with pytest.raises(BaseException) as caught:
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    error = caught.value
    members = [error]
    if isinstance(error, BaseExceptionGroup):
        members.extend(cast(tuple[BaseException, ...], error.exceptions))
    assert [type(member) for member in members] == kinds
    assert repr(error.args) == repr(args)
    assert error.__suppress_context__ is True
    assert error.__cause__ is None
    for member in members:
        assert member.__cause__ is None
        assert member.__context__ is None
        assert getattr(member, "__notes__", None) is None
        assert vars(member) == {}
    assert "sk-live-secret" not in _every_text(error)
    assert "sk-live-secret" not in "".join(traceback.format_exception(error))
    for member in members:
        assert "sk-live-secret" not in repr(type(member))
        assert "sk-live-secret" not in (type(member).__doc__ or "")
    assert path.read_bytes() == raw


def test_recorded_provider_response_is_not_an_own_refusal(tmp_path: Path) -> None:
    """raise_recorded is package code, but its error carries the provider response."""
    own_refusal = notion_qa_module._own_refusal  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ProductBuildError) as caught:
        raise_recorded(
            tmp_path / "absent.json", "phase", ProviderFailure("op", "qa sk-live-secret")
        )
    assert own_refusal(caught.value) is False
    broken = tmp_path / "broken.json"
    broken.write_text("x\n", encoding="ascii")
    with pytest.raises(ProductBuildError, match="checkpoint is not JSON") as refused:
        load_qa_record(broken)
    assert own_refusal(refused.value) is True


@pytest.mark.asyncio
async def test_local_programming_error_is_not_a_provider_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A TypeError raised by QA's own code is a fixed local failure with no provider job."""
    spec, probe, path = await _built(tmp_path)
    raw = path.read_bytes()
    # A code bug inside run_product_qa itself: the digest helper is not callable.
    monkeypatch.setattr(notion_qa_module, "prose_digest", "sk-live-secret")
    with pytest.raises(ProductBuildError) as caught:
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert caught.value.args == ("qa failed in local code",)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "sk-live-secret" not in _every_text(caught.value)
    assert path.read_bytes() == raw


@pytest.mark.asyncio
async def test_provider_type_error_is_still_a_provider_job(tmp_path: Path) -> None:
    """A TypeError raised inside the provider is a provider error, recorded once."""
    spec, probe, path = await _built(tmp_path)

    async def _boom(*_args: object, **_kwargs: object) -> NotionPage:
        raise TypeError("sk-live-secret")

    probe.duplicate_page = _boom  # type: ignore[method-assign]
    with pytest.raises(ProductBuildError) as caught:
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert caught.value.args == ("provider operation failed",)
    assert "sk-live-secret" not in _every_text(caught.value)
    assert "sk-live-secret" not in path.read_text(encoding="ascii")
    assert [job["response"] for job in _provider_jobs(path)] == ["provider operation failed"]


def _pop_text(probe: FixtureNotionAdapter, parent_id: str, content: str) -> None:
    matches = [
        block_id
        for block_id, block in probe.blocks.items()
        if type(block) is NotionTextBlock
        and block.parent_id == parent_id
        and block.content == content
    ]
    assert len(matches) == 1
    del probe.blocks[matches[0]]


def _pop_callout(probe: FixtureNotionAdapter, parent_id: str, content: str) -> None:
    matches = [
        block_id
        for block_id, block in probe.blocks.items()
        if type(block) is NotionCalloutBlock
        and block.parent_id == parent_id
        and block.content == content
    ]
    assert len(matches) == 1
    del probe.blocks[matches[0]]


def _delete_home_contract(
    probe: FixtureNotionAdapter,
    spec: ProductSpec,
    stored: ProductBuildCheckpoint,
    target: str,
) -> None:
    """Remove one home or hub contract the section 8 checks must notice."""
    if target == "home_nav":
        _pop_text(probe, stored.page_id, home_navigation_content(spec))
        return
    if target == "identity":
        _pop_callout(probe, stored.page_id, identity_callout(spec))
        return
    if target.startswith("palette:"):
        token_name = target.split(":", 1)[1]
        token = next(item for item in spec.palette_tokens if item.name == token_name)
        _pop_callout(probe, stored.page_id, accent_content(token.name, token.hex))
        return
    if target.startswith("hub:"):
        hub = stored.identity_hubs[int(target.split(":", 1)[1])]
        _pop_text(probe, hub.page_id, hub_navigation_content(spec, hub.name))
        return
    if target.startswith("view:"):
        name = target.split(":", 1)[1]
        matches = [
            view_id
            for view_id, view in probe.linked_views.items()
            if type(view) is NotionLinkedView
            and view.parent_page_id == stored.page_id
            and view.name == name
        ]
        assert len(matches) == 1
        del probe.linked_views[matches[0]]
        return
    raise AssertionError(target)


_HOME_CONTRACTS = (
    ("home_nav", "teardown_quality"),
    ("palette:Primary", "palette"),
    ("palette:Secondary", "palette"),
    ("palette:Accent", "palette"),
    ("identity", "teardown_quality"),
    *((f"hub:{index}", "teardown_quality") for index in range(6)),
    ("view:Today", "linked_views"),
    ("view:Month", "linked_views"),
    ("view:Quick notes", "linked_views"),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(("target", "flag"), _HOME_CONTRACTS)
async def test_deleted_home_contract_is_blocked(tmp_path: Path, target: str, flag: str) -> None:
    """Deleting one section 8 contract records BLOCKED and writes nothing."""
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    _delete_home_contract(probe, spec, stored, target)
    calls = watch_adapter_writes(probe)

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "BLOCKED"
    assert checkpoint.qa.repairs == ()
    assert checkpoint.qa.proof_page_id == ""
    assert _flag(checkpoint, flag) is False
    assert calls == []
    assert json.loads(path.read_text(encoding="ascii"))["progress"]["repair_jobs"] == []


@pytest.mark.asyncio
async def test_crash_resume_keeps_the_earlier_repair_job(tmp_path: Path) -> None:
    """A repair applied before a checkpoint crash stays on the progress record."""
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
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

    crashed = json.loads(path.read_text(encoding="ascii"))
    assert "qa" not in crashed["provider_object_references"]
    jobs = [job for job in crashed["progress"]["repair_jobs"] if job["kind"] == "qa_repair"]
    assert jobs == [
        {
            "kind": "qa_repair",
            "operation": "qa.repair",
            "phase": "qa",
            "response": "published",
        }
    ]

    calls = watch_adapter_writes(probe)
    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "PASS"
    assert checkpoint.qa.repairs == ("published",)
    assert calls == []
    resumed = json.loads(path.read_text(encoding="ascii"))
    resumed_jobs = [job for job in resumed["progress"]["repair_jobs"] if job["kind"] == "qa_repair"]
    assert resumed_jobs == jobs


@pytest.mark.asyncio
async def test_crash_between_repairs_keeps_the_published_job(tmp_path: Path) -> None:
    """A publish that wrote stays stored when the next repair in that run raises."""
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
    page.duplicate_as_template = False
    original = probe.set_duplicate_as_template

    async def _boom(page_id: str, enabled: bool) -> NotionPage:
        del page_id, enabled
        raise ConnectionError("sk-live-secret")

    probe.set_duplicate_as_template = _boom  # type: ignore[method-assign]
    with pytest.raises(ProductBuildError) as caught:
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    probe.set_duplicate_as_template = original  # type: ignore[method-assign]

    assert caught.value.args == ("provider operation failed",)
    assert caught.value.__context__ is None
    assert "sk-live-secret" not in _every_text(caught.value)
    crashed = json.loads(path.read_text(encoding="ascii"))
    jobs = [job for job in crashed["progress"]["repair_jobs"] if job["kind"] == "qa_repair"]
    assert jobs == [
        {
            "kind": "qa_repair",
            "operation": "qa.repair",
            "phase": "qa",
            "response": "published",
        }
    ]
    assert "sk-live-secret" not in path.read_text(encoding="ascii")

    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "PASS"
    assert "published" in checkpoint.qa.repairs
    resumed = json.loads(path.read_text(encoding="ascii"))
    resumed_names = [
        job["response"] for job in resumed["progress"]["repair_jobs"] if job["kind"] == "qa_repair"
    ]
    assert resumed_names[0] == "published"
    assert "published" in resumed_names


def _raiser_in_package(error_type: type[Exception]) -> Callable[..., None]:
    """Raise from a frame whose module name is the QA package."""
    namespace: dict[str, object] = {
        "__name__": notion_qa_module.__name__,
        "error_type": error_type,
    }
    exec(
        "def boom(*_args: object, **_kwargs: object) -> None:\n"
        "    raise error_type('sk-live-secret')\n",
        namespace,
    )
    boom = namespace["boom"]
    if not callable(boom):
        raise AssertionError("raiser was not callable")
    return cast(Callable[..., None], boom)


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [ValueError, RuntimeError])
async def test_package_error_outside_the_old_fixed_set_is_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[Exception]
) -> None:
    """A package ValueError or RuntimeError is local code, with no provider job."""
    spec, probe, path = await _built(tmp_path)
    raw = path.read_bytes()
    monkeypatch.setattr(notion_qa_module, "_plan", _raiser_in_package(error_type))
    with pytest.raises(ProductBuildError) as caught:
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert caught.value.args == ("qa failed in local code",)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "sk-live-secret" not in _every_text(caught.value)
    assert path.read_bytes() == raw


def _boundary_specs(spec: ProductSpec) -> tuple[ProductSpec, ProductSpec]:
    """Two callers a newline-join digest cannot tell apart."""
    first, second = spec.hubs[0], spec.hubs[1]
    left, right = "alpha", "beta"
    shifted = spec.model_copy(
        update={
            "hubs": (
                first.model_copy(update={"description": f"{left}\n{right}"}),
                second,
                *spec.hubs[2:],
            )
        }
    )
    split = spec.model_copy(
        update={
            "hubs": (
                first.model_copy(update={"description": left}),
                second.model_copy(update={"description": f"{right}\n{second.description}"}),
                *spec.hubs[2:],
            )
        }
    )
    return shifted, split


def test_newline_boundary_does_not_share_a_prose_digest() -> None:
    """A newline that moves a field boundary is a different caller."""
    shifted, split = _boundary_specs(planner_spec())
    assert prose_digest(shifted) != prose_digest(split)


def _dead_pid() -> int:
    """A pid os.kill reports as absent. Pid 999 is alive on some CI runners."""
    candidate = 1_000_000_000
    while candidate > 0:
        try:
            os.kill(candidate, 0)
        except PermissionError:
            candidate -= 1
            continue
        except OSError:
            return candidate
        candidate -= 1
    raise AssertionError("no dead pid")


def _plant_older_temp(path: Path, pid: int, payload: bytes) -> Path:
    """A complete sibling temp, older than the live checkpoint."""
    stale = path.with_name(f".{path.name}.{pid}.tmp")
    stale.write_bytes(payload)
    current = path.stat()
    os.utime(stale, ns=(current.st_atime_ns - 10**9, current.st_mtime_ns - 10**9))
    return stale


def _distinct_dead_pids(count: int) -> list[int]:
    """Distinct pids that os.kill reports as absent."""
    found: list[int] = []
    candidate = 1_000_000_000
    while candidate > 0 and len(found) < count:
        try:
            os.kill(candidate, 0)
        except PermissionError:
            candidate -= 1
            continue
        except OSError:
            found.append(candidate)
        candidate -= 1
    if len(found) != count:
        raise AssertionError("not enough dead pids")
    return found


def _checkpoint_plus_repairs(path: Path, names: tuple[str, ...]) -> bytes:
    """Bytes of the live checkpoint plus these repair names, built off to the side.

    The side name is not a ``.{checkpoint}.{pid}.tmp``, so writing it cannot
    delete a temp planted beside the live file.
    """
    side = path.with_name(f"{path.name}.extend-side")
    side.write_bytes(path.read_bytes())
    record_applied_repairs(side, names)
    payload = side.read_bytes()
    side.unlink()
    return payload


def _plant_temp(path: Path, pid: int, payload: bytes, *, mtime_ns: int) -> Path:
    stale = path.with_name(f".{path.name}.{pid}.tmp")
    stale.write_bytes(payload)
    os.utime(stale, ns=(mtime_ns, mtime_ns))
    return stale


def _qa_repair_names(path: Path) -> list[str]:
    names: list[str] = []
    document = json.loads(path.read_text(encoding="ascii"))
    for job in document["progress"]["repair_jobs"]:
        if type(job) is not dict or job.get("kind") != "qa_repair":
            continue
        response = job.get("response")
        if type(response) is str:
            names.append(response)
    return names


@pytest.mark.asyncio
@pytest.mark.parametrize("repair", ["published", "duplicate_button", "search_indexing"])
async def test_replace_crash_keeps_the_repair_on_resume(tmp_path: Path, repair: str) -> None:
    """os.replace failing after the adapter call keeps that name, with no second write."""
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    if repair == "published":
        await probe.unpublish_page(page.id)
    elif repair == "duplicate_button":
        page.duplicate_as_template = False
    else:
        page.search_indexing = True
    real = os.replace
    failed = {"n": 0}
    namespace: dict[str, object] = {
        "__name__": "money_machine.agents.implementations.notion_progress",
        "OSError": OSError,
        "Path": Path,
        "failed": failed,
        "path": path,
        "real": real,
    }
    exec(
        "def _replace(src: object, dst: object) -> None:\n"
        "    if Path(str(dst)) == path and failed['n'] == 0:\n"
        "        failed['n'] = 1\n"
        "        raise OSError(5, 'replace crashed')\n"
        "    real(src, dst)\n",
        namespace,
    )
    replacement = namespace["_replace"]
    if not callable(replacement):
        raise AssertionError("replace hook was not callable")
    os.replace = replacement  # type: ignore[assignment]
    try:
        with pytest.raises(ProductBuildError, match="qa failed in local code"):
            await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    finally:
        os.replace = real
    assert failed["n"] == 1
    assert _qa_repair_names(path) == []
    # The leftover temp is this process, which is still alive. Resume adopts
    # only a dead pid, so the crashed repair is renamed onto one.
    crashed_temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    assert crashed_temp.is_file()
    crashed_temp.rename(path.with_name(f".{path.name}.{_dead_pid()}.tmp"))
    calls = watch_adapter_writes(probe)
    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert checkpoint.qa is not None
    assert checkpoint.qa.verdict == "PASS"
    assert checkpoint.qa.repairs == (repair,)
    assert calls == ["duplicate_page"]


@pytest.mark.asyncio
async def test_live_pid_older_temp_does_not_drop_a_stored_publish(tmp_path: Path) -> None:
    """A live-pid temp from before the stored publish is not installed.

    The temp is older than the live checkpoint. Installing it would drop
    repairs ('published',) to () and would neither redo nor record the publish.
    """
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
    before_publish = path.read_bytes()
    first = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert first.qa is not None
    assert first.qa.repairs == ("published",)
    stored = path.read_bytes()
    assert stored != before_publish
    stale = _plant_older_temp(path, os.getpid(), before_publish)
    calls = watch_adapter_writes(probe)
    second = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert stale.is_file()
    assert path.read_bytes() == stored
    assert calls == []
    assert second.qa is not None
    assert second.qa.repairs == ("published",)
    assert _qa_repair_names(path) == ["published"]


@pytest.mark.asyncio
async def test_live_pid_extending_temp_is_not_adopted(tmp_path: Path) -> None:
    """A live pid is left alone even when its temp strictly extends the checkpoint.

    Deleting the live-pid check installs this temp. Stored repair names become
    published plus duplicate_button, the bytes change, and the temp is consumed.
    """
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
    first = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert first.qa is not None
    assert first.qa.repairs == ("published",)
    stored = path.read_bytes()
    extended = _checkpoint_plus_repairs(path, ("duplicate_button",))
    assert extended != stored
    planted = _plant_temp(path, os.getpid(), extended, mtime_ns=path.stat().st_mtime_ns + 10**9)
    calls = watch_adapter_writes(probe)
    second = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert _qa_repair_names(path) == ["published"]
    assert planted.is_file()
    assert path.read_bytes() == stored
    assert calls == []
    assert second.qa is not None
    assert second.qa.repairs == ("published",)


@pytest.mark.asyncio
async def test_newest_dead_extension_is_adopted(tmp_path: Path) -> None:
    """Two dead extending temps: the newest one is installed, and it holds all three.

    Sorting oldest-first installs the shorter temp and leaves the newer one
    behind, so the stored names stop at published and duplicate_button.
    """
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    await probe.unpublish_page(page.id)
    first = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert first.qa is not None
    assert first.qa.repairs == ("published",)
    shorter = _checkpoint_plus_repairs(path, ("duplicate_button",))
    longer = _checkpoint_plus_repairs(path, ("duplicate_button", "search_indexing"))
    older_pid, newer_pid = _distinct_dead_pids(2)
    base = path.stat().st_mtime_ns
    older = _plant_temp(path, older_pid, shorter, mtime_ns=base - 2 * 10**9)
    newer = _plant_temp(path, newer_pid, longer, mtime_ns=base + 2 * 10**9)
    calls = watch_adapter_writes(probe)
    second = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert _qa_repair_names(path) == [
        "published",
        "duplicate_button",
        "search_indexing",
    ]
    assert not newer.is_file()
    assert older.is_file()
    assert calls == []
    assert second.qa is not None
    assert second.qa.repairs == ("published",)


@pytest.mark.asyncio
async def test_older_dead_pid_temp_is_not_adopted(tmp_path: Path) -> None:
    """A dead-pid temp older than the live checkpoint is not installed."""
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    page.search_indexing = True
    before = path.read_bytes()
    first = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert first.qa is not None
    assert first.qa.repairs == ("search_indexing",)
    stored = path.read_bytes()
    stale = _plant_older_temp(path, _dead_pid(), before)
    page.search_indexing = True
    calls = watch_adapter_writes(probe)
    with pytest.raises(ProductBuildError, match="qa record does not match"):
        await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert stale.is_file()
    assert path.read_bytes() == stored
    assert calls == []


@pytest.mark.asyncio
async def test_unrequested_repair_is_not_applied(tmp_path: Path) -> None:
    """A flag left out of the repairs tuple is not written."""
    spec, probe, path = await _built(tmp_path)
    stored, _created = load_variant_checkpoint(path)
    page = _colour_pages(probe, spec)[0]
    page.search_indexing = True
    page.duplicate_as_template = False
    calls = watch_adapter_writes(probe)
    done = await notion_qa_module._apply_repairs(  # pyright: ignore[reportPrivateUsage]
        probe, stored, ("published",), path
    )
    assert done == ()
    assert calls == []
    assert page.search_indexing is True
    assert page.duplicate_as_template is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "suffix",
    [
        "?token=sk-live-secret",
        "?a=1&token=sk-live-secret",
        "#token=sk-live-secret",
        "?token=sk-live-secret#frag",
    ],
)
async def test_query_or_fragment_token_is_not_a_qa_fact(tmp_path: Path, suffix: str) -> None:
    """A secret in the query or fragment is not stored on the QA fact."""
    spec, probe, path = await _built(tmp_path)
    page = _colour_pages(probe, spec)[0]
    leaked = f"https://fixture.notion.site/{page.id}{suffix}"
    page.public_url = leaked

    def _forge(document: dict[str, object]) -> None:
        def _one(row: dict[str, object]) -> None:
            if row.get("page_id") == page.id:
                row["secret_link"] = leaked

        _edit_variant_rows(document, _one)

    restamp_checkpoint(path, _forge)
    checkpoint = await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert checkpoint.qa is not None
    stored = dict(checkpoint.qa.facts)
    host = "https://fixture.notion.site"
    assert stored["secret_links"] == ",".join([host] * len(spec.colour_variants))
    assert "sk-live-secret" not in stored["secret_links"]
