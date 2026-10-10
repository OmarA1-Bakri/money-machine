"""Section 11 fixture test matrix.

The matrix re-reads a passing fact ledger and records the fixture proofs.
A broken formula, a wrong linked view, or a missing hub section stays
BLOCKED with zero adapter writes (D-0030). ListingCopyJob is not created
(D-0029). This module does not open a network connection or run the live
sandbox. A07, A08, and A09 stay DESIGNED.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from money_machine.agents.implementations.notion_fact_ledger import (
    PHASE_TEST_MATRIX,
    LedgerRead,
    load_stored_ledger,
    read_ledger_plan,
    workflow_steps,
)
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    ProductBuildCheckpoint,
    ProductBuildError,
    TestMatrixRecord,
    WorkflowLinkRecord,
    exact_keys,
    require_datetime,
    require_path,
    require_probe,
    require_same_spec,
    require_spec,
    require_token,
)
from money_machine.agents.implementations.notion_progress import (
    PROGRESS_KEY,
    ProviderFailure,
    clean_interrupt,
    load_payload,
    raise_recorded,
    raised_in_package,
)
from money_machine.agents.implementations.notion_progress_record import write_checkpoint
from money_machine.agents.implementations.notion_qa import (
    fixture_matrix_flags,
    load_qa_record,
)
from money_machine.agents.implementations.notion_shared_databases import (
    BUSINESS_SHARED_DATABASES,
    PLANNER_SHARED_DATABASES,
)
from money_machine.agents.implementations.notion_variants import (
    load_variant_checkpoint,
    variant_provider_references,
)
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter

PHASE_SANDBOX = "sandbox_build"
_MATRIX_KEY = "test_matrix"
_READY = "ListingCopyJob"
_PROVIDER_FAILED = "provider operation failed"
_LOCAL_FAILED = "test matrix failed in local code"
_MATRIX_KEYS = frozenset({"checks", "tier", "verdict"})
_VERDICTS = frozenset({"PASS", "BLOCKED"})
_TIERS = frozenset({"mass", "business", ""})
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
_OWN_PREFIXES = (
    "test matrix",
    "phase 1",
    "checkpoint ",
    "fact ledger",
    "workflow link",
    "qa ",
    "progress ",
    "recorded_at",
    "design shell",
)
_KEPT_REFERENCES = ("qa", "fact_ledger", "workflow_link")


@dataclass(frozen=True, slots=True)
class _Plan:
    checks: tuple[tuple[str, bool], ...]
    tier: str
    blocked: bool


async def run_test_matrix(
    spec: object,
    probe: object,
    checkpoint_path: object,
    *,
    recorded_at: object,
) -> ProductBuildCheckpoint:
    """Record the fixture section 11 proofs for a passing fact ledger.

    A stored matrix that still matches the live plan is returned as-is.
    A defect that the fixture cannot repair in place is BLOCKED. No adapter
    write runs on either path. The live sandbox is not started.
    """
    validated = require_spec(spec)
    fixture = require_probe(probe)
    path = require_path(checkpoint_path)
    moment = require_datetime(recorded_at)
    stored, created = load_variant_checkpoint(path)
    require_same_spec(stored, validated)
    attached = _require_ledger(path, stored)
    saved = _stored_matrix(path)
    _require_phase(path, saved)
    steps = workflow_steps()
    record, plan, failure = await _guarded(fixture, attached, validated, saved, steps)
    if failure == _PROVIDER_FAILED:
        raise_recorded(
            path,
            BUILD_PHASES[-1],
            ProviderFailure("test_matrix.read", _PROVIDER_FAILED),
        )
    if failure != "":
        raise ProductBuildError(failure) from None
    if plan is None:
        if record is None:
            raise ProductBuildError("test matrix record is missing")
        return _attach(attached, record, attached.recorded_at)
    matrix = _record(plan)
    checkpoint = _attach(attached, matrix, moment)
    _write(path, checkpoint, created)
    return checkpoint


async def _guarded(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    saved: TestMatrixRecord | None,
    steps: tuple[str, ...],
) -> tuple[TestMatrixRecord | None, _Plan | None, str]:
    """The resumed record, or the plan, or a fixed failure text.

    No Exception leaves this function. The caller raises after this frame
    has returned, so a provider error is not reachable as __context__.
    """
    escaped: BaseException
    try:
        if saved is not None and await _saved_holds(probe, stored, spec, saved, steps):
            return saved, None, ""
        return None, await _plan(probe, stored, spec, steps), ""
    except ProductBuildError as error:
        if _own_message(error):
            return None, None, str(error)
        return None, None, _LOCAL_FAILED
    except (ProviderFailure, ConnectionError, OSError):
        return None, None, _PROVIDER_FAILED
    except Exception:
        return None, None, _LOCAL_FAILED
    except BaseException as error:
        escaped = clean_interrupt(error, _LOCAL_FAILED)
    raise escaped from None


def _own_message(error: ProductBuildError) -> bool:
    """True when package code raised a fixed refusal, not a provider error."""
    if not str(error).startswith(_OWN_PREFIXES):
        return False
    if isinstance(error.__cause__, ProviderFailure):
        return False
    return raised_in_package(error)


def _require_ledger(path: Path, stored: ProductBuildCheckpoint) -> ProductBuildCheckpoint:
    """Attach the passing ledger. A missing or blocked ledger writes nothing."""
    qa = load_qa_record(path)
    ledger, link = load_stored_ledger(path)
    if qa is None or ledger is None or link is None or not stored.variants:
        raise ProductBuildError("test matrix requires the fact ledger checkpoint")
    if qa.verdict != "PASS" or ledger.verdict != "PASS" or link.verdict != "PASS":
        raise ProductBuildError("test matrix requires a passing fact ledger")
    if link.ready != _READY:
        raise ProductBuildError("test matrix requires a passing fact ledger")
    return replace(stored, qa=qa, fact_ledger=ledger, workflow_link=link)


def _require_phase(path: Path, saved: TestMatrixRecord | None) -> None:
    """The first run is test_matrix with no record. A stored record is sandbox_build."""
    phase = _recorded_phase(path)
    if phase == PHASE_TEST_MATRIX and saved is None:
        return
    if phase == PHASE_SANDBOX and saved is not None:
        return
    if saved is None:
        raise ProductBuildError("test matrix requires the fact ledger checkpoint")
    raise ProductBuildError("test matrix does not match")


def _recorded_phase(path: Path) -> str:
    """The progress next_phase. The variant loader does not keep this field."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if type(document) is not dict:
        raise ProductBuildError("test matrix requires the fact ledger checkpoint")
    progress = document.get(PROGRESS_KEY)
    if type(progress) is not dict:
        raise ProductBuildError("test matrix requires the fact ledger checkpoint")
    phase = progress.get("next_phase")
    if type(phase) is not str:
        raise ProductBuildError("test matrix requires the fact ledger checkpoint")
    return phase


def _stored_matrix(path: Path) -> TestMatrixRecord | None:
    """The stored matrix, or None when the key is absent. A partial key is refused."""
    envelope = load_payload(path)
    if envelope.payload is None:
        raise ProductBuildError("test matrix requires the fact ledger checkpoint")
    references = envelope.payload.get("provider_object_references")
    if type(references) is not dict:
        raise ProductBuildError("test matrix requires the fact ledger checkpoint")
    if _MATRIX_KEY not in references:
        return None
    return _require_matrix(references[_MATRIX_KEY])


def _require_matrix(value: object) -> TestMatrixRecord:
    """Parse one matrix. Names, order, and the tier word are part of the record."""
    if type(value) is not dict or not exact_keys(value, _MATRIX_KEYS):
        raise ProductBuildError("test matrix record is incomplete")
    verdict = value["verdict"]
    if type(verdict) is not str or verdict not in _VERDICTS:
        raise ProductBuildError("test matrix verdict is unsupported")
    tier = value["tier"]
    if type(tier) is not str or tier not in _TIERS:
        raise ProductBuildError("test matrix record is incomplete")
    checks = _require_checks(value["checks"])
    return TestMatrixRecord(verdict=verdict, checks=checks, tier=tier)


def _require_checks(value: object) -> tuple[tuple[str, bool], ...]:
    """Rows of check and passed. The names and order are exact."""
    if type(value) is not list or not value:
        raise ProductBuildError("test matrix record is incomplete")
    rows: list[tuple[str, bool]] = []
    for item in value:
        if type(item) is not dict or not exact_keys(item, frozenset({"check", "passed"})):
            raise ProductBuildError("test matrix record is incomplete")
        label = item["check"]
        flag = item["passed"]
        if type(label) is not str or type(flag) is not str:
            raise ProductBuildError("test matrix record is incomplete")
        rows.append((require_token(label, "test matrix"), _require_flag(flag)))
    parsed = tuple(rows)
    if tuple(name for name, _flag in parsed) != _CHECK_NAMES:
        raise ProductBuildError("test matrix record is incomplete")
    return parsed


def _require_flag(value: str) -> bool:
    """A check flag is the word true or the word false."""
    if value == "true":
        return True
    if value == "false":
        return False
    raise ProductBuildError("test matrix record is incomplete")


async def _saved_holds(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    saved: TestMatrixRecord,
    steps: tuple[str, ...],
) -> bool:
    """True when the stored matrix still stands. A fixed BLOCKED record is re-run."""
    plan = await _plan(probe, stored, spec, steps)
    if not _verdict_agrees(saved):
        raise ProductBuildError("test matrix does not match")
    if saved.checks != plan.checks or saved.tier != plan.tier:
        if saved.verdict == "BLOCKED" and saved.checks != plan.checks:
            return False
        raise ProductBuildError("test matrix does not match")
    if saved.verdict == "PASS" and plan.blocked:
        raise ProductBuildError("test matrix does not match")
    return True


def _verdict_agrees(saved: TestMatrixRecord) -> bool:
    """BLOCKED needs a false check. PASS needs every check true."""
    failed = any(passed is False for _name, passed in saved.checks)
    if saved.verdict == "BLOCKED":
        return failed
    if saved.verdict == "PASS":
        return not failed
    return False


async def _plan(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    steps: tuple[str, ...],
) -> _Plan:
    """Write-free plan. Every check is a live fixture read or the stored ledger."""
    tier = _tier(stored)
    qa = stored.qa
    ledger = stored.fact_ledger
    link = stored.workflow_link
    if qa is None or ledger is None or link is None:
        raise ProductBuildError("test matrix requires the fact ledger checkpoint")
    live = await read_ledger_plan(probe, stored, spec, qa, steps)
    return await _checks(probe, stored, spec, link, live, steps, tier)


async def _checks(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    link: WorkflowLinkRecord,
    live: LedgerRead,
    steps: tuple[str, ...],
    tier: str,
) -> _Plan:
    """The ordered checks. Split out so the link is a workflow record, not optional."""
    live_flags = await fixture_matrix_flags(probe, stored, spec)
    flags = {
        "complete_build": _complete_build(stored, tier),
        "variant_count": _variant_count(stored, spec),
        "public_links": live_flags["public_links"],
        "isolation": live_flags["isolation"],
        "fresh_duplicate": live_flags["fresh_duplicate"],
        "fact_extraction": _facts_hold(stored, live),
        "successor_recorded": _successor(link, live, steps),
        "formulas_match": live_flags["formulas_match"],
        "linked_views": live_flags["linked_views"],
        "sections_present": live_flags["sections_present"],
    }
    checks = tuple((name, flags[name]) for name in _CHECK_NAMES)
    blocked = any(passed is False for _name, passed in checks)
    return _Plan(checks=checks, tier=tier, blocked=blocked)


def _tier(stored: ProductBuildCheckpoint) -> str:
    """The tier is the stored database kinds. The caller spec is not a source."""
    kinds = tuple(kind for kind, _database_id in stored.database_ids)
    if kinds == PLANNER_SHARED_DATABASES:
        return "mass"
    if kinds == BUSINESS_SHARED_DATABASES:
        return "business"
    return ""


def _complete_build(stored: ProductBuildCheckpoint, tier: str) -> bool:
    """True when the six phases and a passing ledger belong to one tier."""
    if tier not in {"mass", "business"}:
        return False
    if stored.checkpoint_names != BUILD_PHASES:
        return False
    if stored.notification_dashboard is None or stored.aesthetics is None:
        return False
    if not stored.variants or stored.qa is None or stored.qa.verdict != "PASS":
        return False
    ledger = stored.fact_ledger
    link = stored.workflow_link
    if ledger is None or link is None:
        return False
    return ledger.verdict == "PASS" and link.verdict == "PASS"


def _variant_count(stored: ProductBuildCheckpoint, spec: ProductSpec) -> bool:
    """True when the build has three or four colours and they match the spec."""
    colours = spec.colour_variants
    records = stored.variants
    if len(records) not in {3, 4} or len(records) != len(colours):
        return False
    return all(record.name == colour for record, colour in zip(records, colours, strict=True))


def _facts_hold(stored: ProductBuildCheckpoint, live: LedgerRead) -> bool:
    """True when the stored ledger still equals the live ledger plan."""
    ledger = stored.fact_ledger
    if ledger is None or ledger.verdict != "PASS" or live.blocked:
        return False
    return ledger.facts == live.facts and ledger.checks == live.checks


def _successor(link: WorkflowLinkRecord, live: LedgerRead, steps: tuple[str, ...]) -> bool:
    """True when the stored link names ListingCopyJob and matches the live route.

    This does not create the job.
    """
    if link.verdict != "PASS" or link.ready != _READY or link.ready != live.ready:
        return False
    if link.repair_required != live.repair_required:
        return False
    if link.steps != steps or link.steps != live.steps:
        return False
    return live.ready == _READY


def _record(plan: _Plan) -> TestMatrixRecord:
    """PASS only when every check is true. BLOCKED keeps the false checks."""
    verdict = "BLOCKED" if plan.blocked else "PASS"
    if verdict == "PASS" and plan.tier not in {"mass", "business"}:
        raise ProductBuildError("test matrix does not match")
    return TestMatrixRecord(verdict=verdict, checks=plan.checks, tier=plan.tier)


def _attach(
    stored: ProductBuildCheckpoint,
    record: TestMatrixRecord,
    recorded_at: datetime,
) -> ProductBuildCheckpoint:
    """Return the checkpoint with the matrix attached. The sandbox is not run."""
    return replace(
        stored,
        next_phase=PHASE_SANDBOX,
        test_matrix=record,
        recorded_at=recorded_at,
    )


def _write(
    path: Path,
    checkpoint: ProductBuildCheckpoint,
    created: Mapping[str, object],
) -> None:
    """Persist the matrix. The ledger, link, and QA objects are copied through."""
    record = checkpoint.test_matrix
    if record is None:
        raise ProductBuildError("test matrix record is missing")
    references = variant_provider_references(checkpoint)
    envelope = load_payload(path)
    if envelope.payload is None:
        raise ProductBuildError("test matrix requires the fact ledger checkpoint")
    prior = envelope.payload.get("provider_object_references")
    if type(prior) is not dict:
        raise ProductBuildError("test matrix requires the fact ledger checkpoint")
    for key in _KEPT_REFERENCES:
        if key not in prior:
            raise ProductBuildError("test matrix requires the fact ledger checkpoint")
        references[key] = prior[key]
    references[_MATRIX_KEY] = {
        "checks": [
            {"check": name, "passed": "true" if passed else "false"}
            for name, passed in record.checks
        ],
        "tier": record.tier,
        "verdict": record.verdict,
    }
    write_checkpoint(path, checkpoint, references, retained_created_ids=created)
