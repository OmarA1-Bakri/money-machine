"""Section 9 fact ledger and section 10 workflow link.

Facts are read from the persisted checkpoint and the fixture adapter.
The caller cannot supply a fact value. Supported devices stay unverified
and the free-update policy stays not configured, because no persisted
record verifies either one. A stored ledger or link that disagrees with
the live plan raises and writes nothing. A07, A08, and A09 stay DESIGNED.
This module does not open a network connection or create a job.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from money_machine.agents.implementations.notion_product_builder import (
    FactLedgerRecord,
    ProductBuildCheckpoint,
    ProductBuildError,
    QaRecord,
    WorkflowLinkRecord,
    exact_keys,
    require_datetime,
    require_path,
    require_probe,
    require_same_spec,
    require_spec,
    require_token,
)
from money_machine.agents.implementations.notion_progress import load_payload
from money_machine.agents.implementations.notion_progress_record import write_checkpoint
from money_machine.agents.implementations.notion_qa import (
    dashboard_formula_expressions,
    live_qa_passed,
    load_qa_record,
)
from money_machine.agents.implementations.notion_variants import (
    load_variant_checkpoint,
    variant_provider_references,
)
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.domain import NotionDatabase, NotionFormula, NotionPage
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from money_machine.orchestration.successor_factory import load_workflows_config

PHASE_TEST_MATRIX = "test_matrix"
_LEDGER_KEY = "fact_ledger"
_LINK_KEY = "workflow_link"
_LEDGER_KEYS = frozenset({"checks", "facts", "verdict"})
_LINK_KEYS = frozenset({"ready", "repair_required", "steps", "verdict"})
_VERDICTS = frozenset({"PASS", "BLOCKED"})
_READY_JOB = "ListingCopyJob"
_LINK_HOST = "fixture.notion.site"
_FACT_NAMES = (
    "page_count",
    "hubs",
    "databases",
    "variants",
    "colour_names",
    "dashboard_outputs",
    "supported_devices",
    "secret_links",
    "free_update_policy",
    "build_version",
)
_CHECK_NAMES = (
    "qa_verdict",
    "qa_facts",
    "hubs_present",
    "databases_present",
    "dashboard_outputs",
    "secret_links",
)
_QA_OVERLAP = (
    ("page_count", "page_count"),
    ("hubs", "hubs"),
    ("databases", "databases"),
    ("variants", "variant_count"),
    ("colour_names", "colour_names"),
)
# Prompt section 10 names are labels. The jobs are the workflows.yaml graph.
# Every edge is checked on event_successor_map, the map the runtime routes with.
_EDGES = (
    ("DEDUPE_PASSED", "ProductBuildJob", "BUILD_NOTION_TEMPLATE", ""),
    ("BUILD_COMPLETED", "ProductQAJob", "RUN_PRODUCT_QA", "ProductBuildJob"),
    ("BUILD_QA_FAILED", "BuildRepairJob", "REPAIR", "ProductQAJob"),
    ("REPAIR_APPLIED", "ProductQAJob", "RUN_PRODUCT_QA", "BuildRepairJob"),
    ("BUILD_QA_PASSED", "VariantBuildJob", "CREATE_VARIANTS", "ProductQAJob"),
    ("VARIANTS_COMPLETED", "VariantPublishJob", "RUN_VARIANT_QA", "VariantBuildJob"),
    ("VARIANT_LINKS_VERIFIED", "ScreenshotJob", "CAPTURE_SCREENSHOTS", "VariantPublishJob"),
    ("SCREENSHOTS_CAPTURED", "ListingCopyJob", "GENERATE_LISTING_PACKAGE", "ScreenshotJob"),
)
_ROUTE: dict[str, tuple[str, ...]] = {
    "DEDUPE_PASSED": ("ProductBuildJob",),
    "BUILD_COMPLETED": ("ProductQAJob",),
    "BUILD_QA_FAILED": ("BuildRepairJob",),
    "REPAIR_APPLIED": ("ProductQAJob",),
    "BUILD_QA_PASSED": ("VariantBuildJob",),
    "VARIANTS_COMPLETED": ("VariantPublishJob",),
    "VARIANT_LINKS_VERIFIED": ("ScreenshotJob",),
    "SCREENSHOTS_CAPTURED": ("ListingCopyJob", "AssetFactoryJob", "DeliveryBuildJob"),
}


@dataclass(frozen=True, slots=True)
class _Plan:
    checks: tuple[tuple[str, bool], ...]
    facts: tuple[tuple[str, str], ...]
    blocked: bool
    steps: tuple[str, ...]
    ready: str
    repair_required: str


async def run_fact_ledger(
    spec: object,
    probe: object,
    checkpoint_path: object,
    *,
    recorded_at: object,
) -> ProductBuildCheckpoint:
    """Persist the fact ledger and the workflow link from a QA checkpoint."""
    validated = require_spec(spec)
    fixture = require_probe(probe)
    path = require_path(checkpoint_path)
    moment = require_datetime(recorded_at)
    stored, created = load_variant_checkpoint(path)
    require_same_spec(stored, validated)
    qa = load_qa_record(path)
    if qa is None or not stored.variants:
        raise ProductBuildError("fact ledger requires the qa checkpoint")
    steps = _walk_chain()
    saved_ledger, saved_link = _stored_pair(path)
    if (
        saved_ledger is not None
        and saved_link is not None
        and await _saved_holds(fixture, stored, validated, qa, saved_ledger, saved_link, steps)
    ):
        return replace(
            stored,
            next_phase=PHASE_TEST_MATRIX,
            qa=qa,
            fact_ledger=saved_ledger,
            workflow_link=saved_link,
        )
    plan = await _plan(fixture, stored, validated, qa, steps)
    checkpoint = _with_records(stored, qa, plan, moment)
    _write(path, checkpoint, created)
    return checkpoint


def _stored_pair(path: Path) -> tuple[FactLedgerRecord | None, WorkflowLinkRecord | None]:
    envelope = load_payload(path)
    if envelope.payload is None:
        return None, None
    references = envelope.payload.get("provider_object_references")
    if type(references) is not dict:
        return None, None
    has_ledger = _LEDGER_KEY in references
    has_link = _LINK_KEY in references
    if has_ledger != has_link:
        raise ProductBuildError("fact ledger record is incomplete")
    if not has_ledger:
        return None, None
    return _require_ledger(references[_LEDGER_KEY]), _require_link(references[_LINK_KEY])


def _require_ledger(value: object) -> FactLedgerRecord:
    if type(value) is not dict or not exact_keys(value, _LEDGER_KEYS):
        raise ProductBuildError("fact ledger record is incomplete")
    verdict = value["verdict"]
    if type(verdict) is not str or verdict not in _VERDICTS:
        raise ProductBuildError("fact ledger verdict is unsupported")
    checks = _require_pairs(value["checks"], "check", "passed")
    parsed = tuple((name, _require_flag(flag)) for name, flag in checks)
    if tuple(name for name, _flag in parsed) != _CHECK_NAMES:
        raise ProductBuildError("fact ledger record is incomplete")
    facts = _require_pairs(value["facts"], "fact", "value")
    if tuple(name for name, _stored in facts) != _FACT_NAMES:
        raise ProductBuildError("fact ledger record is incomplete")
    return FactLedgerRecord(verdict=verdict, checks=parsed, facts=facts)


def _require_link(value: object) -> WorkflowLinkRecord:
    if type(value) is not dict or not exact_keys(value, _LINK_KEYS):
        raise ProductBuildError("workflow link record is incomplete")
    verdict = value["verdict"]
    if type(verdict) is not str or verdict not in _VERDICTS:
        raise ProductBuildError("workflow link verdict is unsupported")
    ready = value["ready"]
    if type(ready) is not str or ready not in {"", _READY_JOB}:
        raise ProductBuildError("workflow link record is incomplete")
    repair = value["repair_required"]
    if type(repair) is not str or repair not in {"true", "false"}:
        raise ProductBuildError("workflow link record is incomplete")
    steps = value["steps"]
    if type(steps) is not list or not steps:
        raise ProductBuildError("workflow link record is incomplete")
    parsed = tuple(require_token(item, "workflow link") for item in steps)
    return WorkflowLinkRecord(verdict=verdict, steps=parsed, ready=ready, repair_required=repair)


def _require_pairs(value: object, left: str, right: str) -> tuple[tuple[str, str], ...]:
    if type(value) is not list or not value:
        raise ProductBuildError("fact ledger record is incomplete")
    rows: list[tuple[str, str]] = []
    for item in value:
        if type(item) is not dict or not exact_keys(item, frozenset({left, right})):
            raise ProductBuildError("fact ledger record is incomplete")
        label = item[left]
        stored = item[right]
        if type(label) is not str or type(stored) is not str:
            raise ProductBuildError("fact ledger record is incomplete")
        rows.append((require_token(label, "fact ledger"), require_token(stored, "fact ledger")))
    return tuple(rows)


def _require_flag(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ProductBuildError("fact ledger record is incomplete")


def _verdict_agrees(saved: FactLedgerRecord) -> bool:
    failed = any(passed is False for _name, passed in saved.checks)
    if saved.verdict == "BLOCKED":
        return failed
    if saved.verdict == "PASS":
        return not failed
    return False


async def _saved_holds(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    qa: QaRecord,
    saved: FactLedgerRecord,
    link: WorkflowLinkRecord,
    steps: tuple[str, ...],
) -> bool:
    """True when the stored ledger still stands. A fixed check is re-planned."""
    plan = await _plan(probe, stored, spec, qa, steps)
    if not _verdict_agrees(saved):
        raise ProductBuildError("fact ledger does not match")
    if saved.verdict == "BLOCKED":
        if link.verdict != "BLOCKED" or link.ready != "":
            raise ProductBuildError("workflow link does not match")
        if link.steps != plan.steps or link.repair_required != plan.repair_required:
            raise ProductBuildError("workflow link does not match")
        if saved.facts != plan.facts or saved.checks != plan.checks:
            if saved.checks == plan.checks:
                raise ProductBuildError("fact ledger does not match")
            return False
        return True
    if saved.facts != plan.facts or saved.checks != plan.checks:
        raise ProductBuildError("fact ledger does not match")
    if saved.verdict == "PASS":
        if plan.blocked:
            raise ProductBuildError("fact ledger does not match")
        if link.verdict != "PASS" or link.ready != plan.ready or link.steps != plan.steps:
            raise ProductBuildError("workflow link does not match")
        if link.repair_required != plan.repair_required:
            raise ProductBuildError("workflow link does not match")
        return True
    raise ProductBuildError("fact ledger does not match")


async def _plan(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    qa: QaRecord,
    steps: tuple[str, ...],
) -> _Plan:
    """Write-free plan. Facts are the checkpoint and the adapter."""
    _require_pages(probe, stored)
    database_titles, databases_ok = _database_titles(probe, stored)
    hub_names, hubs_ok = _hub_names(probe, stored)
    secret_ok, links = _secret_links(probe, stored)
    dashboard_ok, dashboard = _dashboard_outputs(probe, stored, spec)
    home = probe.pages[stored.page_id]
    colours_ok = _colours_match(probe, stored, home.title)
    facts = {
        "page_count": str(len(_known_ids(stored))),
        "hubs": ",".join(hub_names),
        "databases": ",".join(database_titles),
        "variants": str(len(stored.variants)),
        "colour_names": ",".join(record.name for record in stored.variants),
        "dashboard_outputs": dashboard,
        "supported_devices": "unverified",
        "secret_links": links,
        "free_update_policy": "not_configured",
        "build_version": str(stored.build_version),
    }
    # Caller colour names and title are not facts. Live QA reads the adapter
    # and the stored variant records.
    home_title = home.title if type(home.title) is str and home.title != "" else spec.title
    live_spec = spec.model_copy(
        update={
            "colour_variants": tuple(record.name for record in stored.variants),
            "title": home_title,
        }
    )
    qa_live = await live_qa_passed(probe, stored, live_spec)
    qa_facts = dict(qa.facts)
    overlap = all(facts[left] == qa_facts.get(right, "") for left, right in _QA_OVERLAP)
    flags = {
        "qa_verdict": qa_live,
        "qa_facts": overlap,
        "hubs_present": hubs_ok,
        "databases_present": databases_ok,
        "dashboard_outputs": dashboard_ok,
        "secret_links": secret_ok,
    }
    if not colours_ok:
        flags["qa_facts"] = False
    ordered: list[tuple[str, str]] = []
    for name in _FACT_NAMES:
        value = facts[name]
        if type(value) is not str or value == "" or value.strip() != value:
            value = "missing"
            flags["qa_facts"] = False
        ordered.append((name, value))
    checks = tuple((name, flags[name]) for name in _CHECK_NAMES)
    blocked = any(passed is False for _name, passed in checks)
    repair_required = "true" if qa.repairs else "false"
    ready = "" if blocked else _READY_JOB
    return _Plan(
        checks=checks,
        facts=tuple(ordered),
        blocked=blocked,
        steps=steps,
        ready=ready,
        repair_required=repair_required,
    )


def _known_ids(stored: ProductBuildCheckpoint) -> tuple[str, ...]:
    ids = [stored.page_id]
    ids.extend(hub.page_id for hub in stored.identity_hubs)
    notice = stored.notification_dashboard
    if notice is not None:
        ids.append(notice.row_page_id)
        ids.extend(page_id for _kind, page_id in notice.samples)
    ids.extend(record.page_id for record in stored.variants)
    return tuple(ids)


def _require_pages(probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint) -> None:
    for page_id in _known_ids(stored):
        page = probe.pages.get(page_id)
        if type(page) is not NotionPage:
            raise ProductBuildError("fact ledger page is missing")


def _page_title(probe: FixtureNotionAdapter, page_id: str) -> str:
    page = probe.pages[page_id]
    if type(page.title) is not str or page.title == "":
        return ""
    return page.title


def _hub_names(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint
) -> tuple[tuple[str, ...], bool]:
    names: list[str] = []
    matched = True
    for hub in stored.identity_hubs:
        title = _page_title(probe, hub.page_id)
        if title != hub.name:
            matched = False
        names.append(title if title != "" else "missing")
    durable: list[str] = []
    for name in names:
        if type(name) is str and (name == "" or name.strip() != name):
            durable.append("missing")
            matched = False
        else:
            durable.append(name)
    return tuple(durable), matched


def _colours_match(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, home_title: str
) -> bool:
    for record in stored.variants:
        if _page_title(probe, record.page_id) != f"{home_title} / {record.name}":
            return False
    return True


def _database_titles(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint
) -> tuple[tuple[str, ...], bool]:
    titles: list[str] = []
    matched = True
    for kind, database_id in stored.database_ids:
        database = probe.databases.get(database_id)
        if not isinstance(database, NotionDatabase) or database.parent_id != stored.page_id:
            raise ProductBuildError("fact ledger database is missing")
        title = (
            database.title if type(database.title) is str and database.title != "" else "missing"
        )
        if type(title) is str and title.strip() != title:
            title = "missing"
        if title != kind:
            matched = False
        titles.append(title)
    return tuple(titles), matched


def _trusted_link(page_id: str) -> str:
    return "https" + "://" + _LINK_HOST + "/" + page_id


def _secret_links(probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint) -> tuple[bool, str]:
    links: list[str] = []
    agreed = True
    for record in stored.variants:
        page = probe.pages[record.page_id]
        trusted = _trusted_link(page.id)
        captured = page.public_url
        usable = type(captured) is str and captured != ""
        if (
            page.is_published is True
            and usable
            and captured == trusted
            and record.secret_link == trusted
        ):
            links.append(trusted)
            continue
        agreed = False
        if usable:
            shown = captured if type(captured) is str else ""
            links.append(shown)
        else:
            links.append("missing")
    return agreed, ",".join(links)


def _dashboard_outputs(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, spec: ProductSpec
) -> tuple[bool, str]:
    notice = stored.notification_dashboard
    if notice is None:
        return False, "missing"
    expected = dashboard_formula_expressions(spec)
    parts: list[str] = []
    for kind, name, property_id in notice.formulas:
        expression = _formula_expression(probe, stored, kind, property_id)
        wanted = expected.get(name)
        if expression is None or wanted is None or wanted[0] != kind or expression != wanted[1]:
            return False, "missing"
        parts.append(f"{name}={expression}")
    for kind, page_id in notice.samples:
        parts.append(f"sample:{kind}={_page_title(probe, page_id)}")
    row = _page_title(probe, notice.row_page_id)
    parts.append(f"row={row}")
    return True, ";".join(parts)


def _formula_expression(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    kind: str,
    property_id: str,
) -> str | None:
    for recorded, database_id in stored.database_ids:
        if recorded != kind:
            continue
        database = probe.databases.get(database_id)
        if not isinstance(database, NotionDatabase):
            return None
        for prop in database.properties:
            if prop.id != property_id or prop.type != "formula":
                continue
            formula = prop.config.get("formula")
            if type(formula) is not NotionFormula or formula.expression == "":
                return None
            return formula.expression
        return None
    return None


def _walk_chain() -> tuple[str, ...]:
    """Read the canonical graph. A missing edge is a refusal, not a ready link."""
    event_map, config = load_workflows_config()
    workflow = next(
        (item for item in config.workflows if item.workflow_type == "ProductLifecycleWorkflow"),
        None,
    )
    if workflow is None:
        raise ProductBuildError("workflow link does not match")
    jobs = {job.job_type: job for job in workflow.jobs}
    steps: list[str] = []
    for event, job_type, label, _predecessor in _EDGES:
        mapped = event_map.get(event, [])
        if job_type not in mapped or tuple(mapped) != _ROUTE[event]:
            raise ProductBuildError("workflow link does not match")
        if job_type not in jobs:
            raise ProductBuildError("workflow link does not match")
        steps.append(f"{event}>{job_type}>{label}")
    listing = jobs[_READY_JOB]
    if "ListingPackage" not in listing.output_contracts:
        raise ProductBuildError("workflow link does not match")
    return tuple(steps)


def _with_records(
    stored: ProductBuildCheckpoint,
    qa: QaRecord,
    plan: _Plan,
    recorded_at: datetime,
) -> ProductBuildCheckpoint:
    verdict = "BLOCKED" if plan.blocked else "PASS"
    ledger = FactLedgerRecord(verdict=verdict, checks=plan.checks, facts=plan.facts)
    link = WorkflowLinkRecord(
        verdict=verdict,
        steps=plan.steps,
        ready=plan.ready,
        repair_required=plan.repair_required,
    )
    return replace(
        stored,
        next_phase=PHASE_TEST_MATRIX,
        qa=qa,
        fact_ledger=ledger,
        workflow_link=link,
        recorded_at=recorded_at,
    )


def _write(
    path: Path,
    checkpoint: ProductBuildCheckpoint,
    created: Mapping[str, object],
) -> None:
    ledger = checkpoint.fact_ledger
    link = checkpoint.workflow_link
    qa = checkpoint.qa
    if ledger is None or link is None or qa is None:
        raise ProductBuildError("fact ledger record is missing")
    references = variant_provider_references(checkpoint)
    references["qa"] = {
        "checks": [
            {"check": name, "passed": "true" if passed else "false"} for name, passed in qa.checks
        ],
        "facts": [{"fact": name, "value": value} for name, value in qa.facts],
        "proof_page_id": qa.proof_page_id,
        "repairs": list(qa.repairs),
        "verdict": qa.verdict,
    }
    references[_LEDGER_KEY] = {
        "checks": [
            {"check": name, "passed": "true" if passed else "false"}
            for name, passed in ledger.checks
        ],
        "facts": [{"fact": name, "value": value} for name, value in ledger.facts],
        "verdict": ledger.verdict,
    }
    references[_LINK_KEY] = {
        "ready": link.ready,
        "repair_required": link.repair_required,
        "steps": list(link.steps),
        "verdict": link.verdict,
    }
    write_checkpoint(path, checkpoint, references, retained_created_ids=created)
