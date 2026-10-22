"""Known formula drift must enter targeted repair without blessing other damage."""

from dataclasses import replace
from pathlib import Path

from money_machine.agents.implementations.notion_progress import load_payload
from money_machine.agents.implementations.notion_qa import run_product_qa
from money_machine.agents.implementations.notion_variants import build_variants
from money_machine.integrations.notion.domain import NotionFormula
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from tests.unit.agents.test_notion_product_builder_variants import (
    VARIANTS_AT,
    prepare_aesthetics,
)
from tests.unit.agents.test_notion_product_qa import QA_AT, planner_spec


async def prepare_variants(spec, probe, path):
    await prepare_aesthetics(spec, probe, path)
    await build_variants(spec, probe, path, recorded_at=VARIANTS_AT)


async def test_formula_drift_queues_one_targeted_repair(tmp_path: Path) -> None:
    spec = planner_spec()
    probe = FixtureNotionAdapter()
    path = tmp_path / "build.json"
    await prepare_variants(spec, probe, path)
    prop = next(
        p
        for db in probe.databases.values()
        for p in db.properties
        if isinstance(p.config.get("formula"), NotionFormula)
    )
    original = prop.config["formula"]
    prop.config["formula"] = replace(original, expression="length(prop('Title'))")
    before = (set(probe.pages), set(probe.databases), prop.id)

    result = await run_product_qa(spec, probe, path, recorded_at=QA_AT)

    assert result.qa is not None and result.qa.verdict == "FAIL_REPAIRABLE"
    assert result.qa.repairs == ("notification_formulas",)
    assert dict(result.qa.checks)["notification_values"] is False
    assert prop.config["formula"].expression == "length(prop('Title'))"
    jobs = load_payload(path).repair_jobs
    assert len(jobs) == 1
    assert jobs[0] == {
        "kind": "qa_repair_required",
        "operation": "qa.repair",
        "phase": "qa",
        "response": "notification_formulas",
    }
    await run_product_qa(spec, probe, path, recorded_at=QA_AT)
    assert load_payload(path).repair_jobs == jobs
    assert (set(probe.pages), set(probe.databases), prop.id) == before
