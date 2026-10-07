"""A09 fixture product QA.

Session 07 prompt section 8. QA reads the variants checkpoint through
FixtureNotionAdapter and records PASS or BLOCKED with write_checkpoint.
A repairable flag is fixed with the existing adapter and QA runs again.
The section 9 fact ledger and the workflow link are not started. A07, A08,
and A09 stay DESIGNED. This module does not open a network connection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from money_machine.agents.implementations.notion_aesthetics import (
    accent_content,
    hub_cover,
    hub_icon,
)
from money_machine.agents.implementations.notion_hubs import section_content
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    SPEC_ID_PROPERTY,
    ProductBuildCheckpoint,
    ProductBuildError,
    QaRecord,
    VariantRecord,
    exact_keys,
    require_datetime,
    require_path,
    require_probe,
    require_same_spec,
    require_spec,
    require_token,
)
from money_machine.agents.implementations.notion_progress import (
    OP_QA,
    ProviderFailure,
    guard_operation,
    load_payload,
    raise_recorded,
)
from money_machine.agents.implementations.notion_progress_record import write_checkpoint
from money_machine.agents.implementations.notion_shared_databases import shared_database_kinds
from money_machine.agents.implementations.notion_variants import (
    PHASE_QA,
    load_variant_checkpoint,
    variant_provider_references,
    vocabulary_content,
)
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.domain import (
    NotionDatabase,
    NotionFormula,
    NotionLinkedView,
    NotionPage,
    NotionRelation,
    NotionTextBlock,
)
from money_machine.integrations.notion.errors import SchemaBuilderError, UnverifiedPropertyNameError
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from money_machine.integrations.notion.formulas import (
    NotificationDashboardFormulas,
    compile_formula,
    generate_notification_dashboard_formulas,
)
from money_machine.integrations.notion.schema_builder import schema_definitions

PHASE_FACT_LEDGER = "fact_ledger"
_QA_KEY = "qa"
_NOTIFICATION_TITLE = "Notification dashboard"
_SECTION_ROLES = ("purpose", "practice", "buyer")
_REPAIRABLE = ("published", "duplicate_button", "search_indexing")
_QA_KEYS = frozenset({"checks", "facts", "proof_page_id", "repairs", "verdict"})
_VERDICTS = frozenset({"PASS", "FAIL_REPAIRABLE", "BLOCKED"})
_SLUG_DATABASE = {
    "active projects": "Projects",
    "clients": "Clients",
    "content": "Content",
    "draft invoices": "Invoices",
    "due today": "Tasks",
    "events today": "Events",
    "habits today": "Habits",
    "meals today": "Meals",
    "money today": "Finance",
    "notes": "Notes",
    "open tasks": "Tasks",
}


@dataclass(frozen=True, slots=True)
class _QaPlan:
    checks: tuple[tuple[str, bool], ...]
    repairs: tuple[str, ...]
    blocked: bool
    proof_page_id: str


async def run_product_qa(
    spec: object,
    probe: object,
    checkpoint_path: object,
    *,
    recorded_at: object,
) -> ProductBuildCheckpoint:
    """Record a fixture QA verdict for a finished variants build."""
    validated = require_spec(spec)
    fixture = require_probe(probe)
    path = require_path(checkpoint_path)
    moment = require_datetime(recorded_at)
    stored, created = load_variant_checkpoint(path)
    require_same_spec(stored, validated)
    if not stored.variants or stored.next_phase != PHASE_QA:
        raise ProductBuildError("qa requires the variants checkpoint")
    try:
        saved = _stored_qa(path)
        if saved is not None and await _saved_holds(fixture, stored, validated, saved):
            return replace(stored, next_phase=PHASE_FACT_LEDGER, qa=saved)
        plan = await _plan(fixture, stored, validated)
        repairs: tuple[str, ...] = ()
        if not plan.blocked and plan.repairs:
            await _apply_repairs(fixture, stored, plan.repairs)
            repairs = plan.repairs
            plan = await _plan(fixture, stored, validated)
        if plan.blocked or plan.repairs:
            verdict = "BLOCKED"
            proof = ""
        else:
            verdict = "PASS"
            proof = await _prove_duplicate(fixture, stored, validated, plan.proof_page_id)
        facts = _facts(stored, validated, fixture)
        checkpoint = _with_qa(stored, plan.checks, repairs, verdict, proof, facts, moment)
        _write_qa(path, checkpoint, created)
    except ProviderFailure as failure:
        raise_recorded(path, BUILD_PHASES[-1], failure)
    return checkpoint


def _stored_qa(path: Path) -> QaRecord | None:
    envelope = load_payload(path)
    if envelope.payload is None:
        return None
    references = envelope.payload.get("provider_object_references")
    if type(references) is not dict or _QA_KEY not in references:
        return None
    return _require_qa(references[_QA_KEY])


def _require_qa(value: object) -> QaRecord:
    if type(value) is not dict:
        raise ProductBuildError("qa record must be an object")
    entry = value
    if not exact_keys(entry, _QA_KEYS):
        raise ProductBuildError("qa record fields are missing or unsupported")
    verdict = entry["verdict"]
    if type(verdict) is not str or verdict not in _VERDICTS:
        raise ProductBuildError("qa verdict is unsupported")
    proof = entry["proof_page_id"]
    if type(proof) is not str:
        raise ProductBuildError("qa proof page is unsupported")
    checks = _require_pairs(entry["checks"], "check", "passed")
    parsed_checks = tuple((name, _require_passed(passed)) for name, passed in checks)
    repairs = _require_repairs(entry["repairs"])
    facts = _require_pairs(entry["facts"], "fact", "value")
    return QaRecord(
        verdict=verdict,
        checks=parsed_checks,
        repairs=repairs,
        proof_page_id=proof,
        facts=facts,
    )


def _require_pairs(value: object, left: str, right: str) -> tuple[tuple[str, str], ...]:
    if type(value) is not list or not value:
        raise ProductBuildError("qa record is incomplete")
    rows: list[tuple[str, str]] = []
    for item in value:
        if type(item) is not dict or not exact_keys(item, frozenset({left, right})):
            raise ProductBuildError("qa record is incomplete")
        label = item[left]
        stored = item[right]
        if type(label) is not str or type(stored) is not str:
            raise ProductBuildError("qa record is incomplete")
        rows.append((require_token(label, "qa"), require_token(stored, "qa")))
    return tuple(rows)


def _require_tokens(value: object, label: str) -> tuple[str, ...]:
    if type(value) is not list:
        raise ProductBuildError("qa record is incomplete")
    rows: list[str] = []
    for item in value:
        if type(item) is not str:
            raise ProductBuildError("qa record is incomplete")
        rows.append(require_token(item, label))
    return tuple(rows)


def _require_passed(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ProductBuildError("qa record is incomplete")


def _require_repairs(value: object) -> tuple[str, ...]:
    repairs = _require_tokens(value, "qa repair")
    if len(set(repairs)) != len(repairs) or any(name not in _REPAIRABLE for name in repairs):
        raise ProductBuildError("qa record is incomplete")
    return repairs


async def _saved_holds(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    saved: QaRecord,
) -> bool:
    """True when the stored verdict still stands. A fixed BLOCKED record is re-run."""
    plan = await _plan(probe, stored, spec)
    facts = _facts(stored, spec, probe)
    if saved.verdict == "BLOCKED":
        if saved.proof_page_id != "":
            raise ProductBuildError("qa record does not match")
        if not plan.blocked:
            return False
        if saved.facts != facts or plan.checks != saved.checks:
            raise ProductBuildError("qa record does not match")
        return True
    if saved.facts != facts or plan.checks != saved.checks:
        raise ProductBuildError("qa record does not match")
    if saved.verdict == "PASS":
        if plan.blocked or plan.repairs:
            raise ProductBuildError("qa record does not match")
        if saved.proof_page_id == "" or plan.proof_page_id != saved.proof_page_id:
            raise ProductBuildError("qa record does not match")
        return True
    raise ProductBuildError("qa record does not match")


async def _plan(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> _QaPlan:
    """Write-free verdict. Reads may raise ProviderFailure."""
    flags = _flag_failures(probe, stored)
    structural = await _structural_checks(probe, stored, spec)
    checks = structural + flags
    blocked = any(not passed for _name, passed in structural)
    repairs = tuple(name for name, _passed in flags if name in _REPAIRABLE and not _passed)
    if blocked:
        repairs = ()
    proof = _existing_proof_id(probe, stored, spec)
    return _QaPlan(checks, repairs, blocked, proof)


def _flag_failures(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint
) -> tuple[tuple[str, bool], ...]:
    pages = [_variant_page(probe, record) for record in stored.variants]
    published = all(page.is_published is True for page in pages)
    duplicate = all(page.duplicate_as_template is True for page in pages)
    indexed = all(page.search_indexing is False for page in pages)
    return (
        ("published", published),
        ("duplicate_button", duplicate),
        ("search_indexing", indexed),
    )


async def _structural_checks(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> tuple[tuple[str, bool], ...]:
    proof = _existing_proof_id(probe, stored, spec)
    return (
        ("spec_coverage", _spec_coverage(stored, spec)),
        ("shared_databases", _shared_databases(probe, stored, spec)),
        ("duplicate_databases", _duplicate_databases(probe, stored, spec)),
        ("hubs_present", _hubs_present(probe, stored, spec)),
        ("linked_views", _linked_views(probe, stored)),
        ("formulas_compile", _formulas_compile(probe, stored, spec)),
        ("notification_values", _notification_values(probe, stored, spec)),
        ("page_count", _page_count(probe, stored, proof)),
        ("variant_count", len(stored.variants) == len(spec.colour_variants)),
        ("public_links", await _public_links(probe, stored)),
        ("fresh_duplicate", _fresh_duplicate(probe, stored, spec, proof)),
        ("no_access_blocks", _no_access(probe)),
        ("cross_catalogue", _cross_catalogue(probe, stored)),
        ("palette", _palette(probe, stored, spec)),
        ("teardown_quality", _teardown(probe, stored, spec)),
        ("facts_persisted", _facts_persisted(stored, spec, probe)),
    )


def _is_database(value: object) -> bool:
    return isinstance(value, NotionDatabase)


def _variant_page(probe: FixtureNotionAdapter, record: VariantRecord) -> NotionPage:
    page = probe.pages.get(record.page_id)
    if type(page) is not NotionPage:
        raise ProductBuildError("qa variant page is missing")
    return page


def _spec_coverage(stored: ProductBuildCheckpoint, spec: ProductSpec) -> bool:
    colours = spec.colour_variants
    tokens = spec.palette_tokens
    if len(stored.variants) != len(colours) or len(colours) != len(tokens):
        return False
    pairs = tuple((record.name, record.token_name) for record in stored.variants)
    expected = tuple((colour, token.name) for colour, token in zip(colours, tokens, strict=True))
    return pairs == expected


def _shared_databases(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, spec: ProductSpec
) -> bool:
    kinds = shared_database_kinds(spec)
    recorded = tuple(kind for kind, _database_id in stored.database_ids)
    if recorded != kinds:
        return False
    for kind, database_id in stored.database_ids:
        database = probe.databases.get(database_id)
        if (
            not isinstance(database, NotionDatabase)
            or database.title != kind
            or database.parent_id != stored.page_id
        ):
            return False
    return True


def _duplicate_databases(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, spec: ProductSpec
) -> bool:
    titles = [database.title for database in probe.databases.values() if _is_database(database)]
    expected = len(shared_database_kinds(spec)) + 1
    return len(titles) == expected and len(set(titles)) == len(titles)


def _hubs_present(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, spec: ProductSpec
) -> bool:
    if tuple(hub.name for hub in stored.identity_hubs) != tuple(hub.name for hub in spec.hubs):
        return False
    for hub in stored.identity_hubs:
        page = probe.pages.get(hub.page_id)
        if (
            type(page) is not NotionPage
            or page.title != hub.name
            or page.parent_id != stored.page_id
        ):
            return False
    return True


def _linked_views(probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint) -> bool:
    by_kind = dict(stored.database_ids)
    for hub in stored.identity_hubs:
        for slug, view_id in hub.views:
            kind = _SLUG_DATABASE.get(slug)
            view = probe.linked_views.get(view_id)
            if kind is None or kind not in by_kind or type(view) is not NotionLinkedView:
                return False
            if view.source_database_id != by_kind[kind] or view.parent_page_id != hub.page_id:
                return False
    return True


def _formulas_compile(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, spec: ProductSpec
) -> bool:
    generated = _generated(spec)
    for name, expression in generated.expressions.items():
        kind = generated.databases[name]
        if not _formula_compiles(
            probe, stored, kind, name, expression, generated.result_types[name]
        ):
            return False
    return len(generated.expressions) > 0


def _notification_values(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, spec: ProductSpec
) -> bool:
    notice = stored.notification_dashboard
    if notice is None:
        return False
    row = probe.pages.get(notice.row_page_id)
    database = probe.databases.get(notice.database_id)
    if type(row) is not NotionPage or not isinstance(database, NotionDatabase):
        return False
    if database.title != _NOTIFICATION_TITLE:
        return False
    generated = _generated(spec)
    for name, expression in generated.expressions.items():
        kind = generated.databases[name]
        found = _formula_property(probe, stored, kind, name)
        if found is None or found.expression != expression:
            return False
    return True


def _formula_compiles(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    kind: str,
    name: str,
    expression: str,
    result_type: str,
) -> bool:
    database = _kind_database(probe, stored, kind)
    if database is None:
        return False
    verified = {
        prop.name: prop.type
        for prop in database.properties
        if prop.type != "formula" and type(prop.name) is str and type(prop.type) is str
    }
    try:
        compile_formula(expression, verified, result_type)
    except (SchemaBuilderError, UnverifiedPropertyNameError):
        return False
    return True


def _formula_property(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    kind: str,
    name: str,
) -> NotionFormula | None:
    database = _kind_database(probe, stored, kind)
    if database is None:
        return None
    for prop in database.properties:
        if prop.name != name or prop.type != "formula":
            continue
        formula = prop.config.get("formula")
        if type(formula) is NotionFormula and formula.expression != "":
            return formula
    return None


def _kind_database(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, kind: str
) -> NotionDatabase | None:
    for recorded, database_id in stored.database_ids:
        if recorded != kind:
            continue
        database = probe.databases.get(database_id)
        if isinstance(database, NotionDatabase):
            return database
    return None


def _generated(spec: ProductSpec) -> NotificationDashboardFormulas:
    definitions = schema_definitions()
    kinds = shared_database_kinds(spec)
    verified = {
        kind: {prop.name: prop.type for prop in definitions[kind].properties} for kind in kinds
    }
    return generate_notification_dashboard_formulas(verified)


def _page_count(probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, proof: str) -> bool:
    known = _known_page_ids(stored)
    present = [page for page in probe.pages.values() if type(page) is NotionPage]
    known_present = [page for page in present if page.id in known]
    extras = [page for page in present if page.id not in known]
    if len(known_present) != len(known):
        return False
    if not extras:
        return proof == ""
    return len(extras) == 1 and extras[0].id == proof


def _known_page_ids(stored: ProductBuildCheckpoint) -> set[str]:
    known = {stored.page_id}
    known.update(hub.page_id for hub in stored.identity_hubs)
    notice = stored.notification_dashboard
    if notice is not None:
        known.add(notice.row_page_id)
        known.update(page_id for _kind, page_id in notice.samples)
    known.update(record.page_id for record in stored.variants)
    return known


_FIXTURE_LINK_HOST = "fixture.notion.site"


def _trusted_secret_link(page_id: str) -> str:
    """Fixture publish shape: one host and the page id as the only path segment."""
    return "https" + "://" + _FIXTURE_LINK_HOST + "/" + page_id


def _is_trusted_link(link: object, page_id: str) -> bool:
    return type(link) is str and link == _trusted_secret_link(page_id)


async def _public_links(probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint) -> bool:
    """Each stored link and captured URL is checked against the fixture shape."""
    for record in stored.variants:
        page = _variant_page(probe, record)
        link = record.secret_link
        if not _is_trusted_link(link, page.id):
            return False
        accessible = await probe.verify_stranger_access(link)
        if accessible is not True:
            return False
        if page.is_published is True:
            live = await probe.get_public_url(page.id)
            if not _is_trusted_link(live, page.id):
                return False
            continue
        captured = page.public_url
        if type(captured) is str and captured != "" and not _is_trusted_link(captured, page.id):
            return False
    return True


def _fresh_duplicate(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    proof: str,
) -> bool:
    """Publish flags are repairable. This check is the copy source, then the proof."""
    if proof == "":
        page = _variant_page(probe, stored.variants[0])
        token = spec.palette_tokens[0]
        title = f"{spec.title} / {spec.colour_variants[0]}"
        return (
            page.title == title
            and page.parent_type == "workspace"
            and SPEC_ID_PROPERTY not in page.properties
            and page.icon == hub_icon(token)
            and page.cover == hub_cover(token)
        )
    return _proof_matches(probe.pages.get(proof), stored, spec)


def _no_access(probe: FixtureNotionAdapter) -> bool:
    return all("No access" not in block.content for block in probe.blocks.values())


def _cross_catalogue(probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint) -> bool:
    known = {database_id for _kind, database_id in stored.database_ids}
    notice = stored.notification_dashboard
    if notice is not None:
        known.add(notice.database_id)
    for view in probe.linked_views.values():
        if type(view) is not NotionLinkedView or view.source_database_id not in known:
            return False
    for database in probe.databases.values():
        if not _is_database(database):
            continue
        for prop in database.properties:
            relation = prop.config.get("relation")
            if type(relation) is not NotionRelation:
                continue
            if relation.database_id not in known:
                return False
    return True


def _palette(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, spec: ProductSpec
) -> bool:
    colours = spec.colour_variants
    tokens = spec.palette_tokens
    if len(stored.variants) != len(colours) or len(colours) != len(tokens):
        return False
    aligned = zip(stored.variants, colours, tokens, strict=True)
    for record, colour, token in aligned:
        if record.name != colour:
            return False
        page = _variant_page(probe, record)
        if page.icon != hub_icon(token) or page.cover != hub_cover(token):
            return False
        accents = [
            block
            for block in probe.blocks.values()
            if block.parent_id == page.id and block.content == accent_content(token.name, token.hex)
        ]
        samples = [
            block
            for block in probe.blocks.values()
            if block.parent_id == page.id
            and type(block) is NotionTextBlock
            and block.content == vocabulary_content(spec, colour, token)
        ]
        if len(accents) != 1 or len(samples) != 1:
            return False
    return True


def _teardown(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, spec: ProductSpec
) -> bool:
    if not spec.evidence:
        return False
    for hub in stored.identity_hubs:
        for role in _SECTION_ROLES:
            expected = section_content(spec, hub.name, role)
            found = any(
                type(block) is NotionTextBlock
                and block.parent_id == hub.page_id
                and block.content == expected
                for block in probe.blocks.values()
            )
            if not found:
                return False
    return True


def _facts_persisted(
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    probe: FixtureNotionAdapter,
) -> bool:
    """The written snapshot matches counts taken from the live probe and records."""
    return dict(_facts(stored, spec, probe)) == _accounted_facts(stored, spec, probe)


def _accounted_facts(
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    probe: FixtureNotionAdapter,
) -> dict[str, str]:
    databases: list[str] = []
    for _kind, database_id in stored.database_ids:
        database = probe.databases.get(database_id)
        if isinstance(database, NotionDatabase):
            databases.append(database.title)
        else:
            databases.append("")
    links: list[str] = []
    for record in stored.variants:
        page = probe.pages.get(record.page_id)
        if type(page) is NotionPage and type(page.public_url) is str and page.public_url != "":
            links.append(_normalised_secret_link(page.public_url, page.id))
        else:
            links.append(_normalised_secret_link(record.secret_link, record.page_id))
    notice = stored.notification_dashboard
    samples = len(notice.samples) if notice is not None else 0
    page_count = 1 + len(stored.identity_hubs) + samples + len(stored.variants)
    if notice is not None:
        page_count += 1
    return {
        "colour_names": ",".join(record.name for record in stored.variants),
        "databases": ",".join(databases),
        "hubs": ",".join(hub.name for hub in stored.identity_hubs),
        "page_count": str(page_count),
        "secret_links": ",".join(links),
        "variant_count": str(len(spec.colour_variants)),
    }


def _normalised_secret_link(link: str, page_id: str) -> str:
    suffix = "/" + page_id
    if link.endswith(suffix):
        return link[: -len(suffix)]
    return link


def _present_page_count(stored: ProductBuildCheckpoint, probe: FixtureNotionAdapter) -> int:
    known = _known_page_ids(stored)
    return sum(1 for page in probe.pages.values() if type(page) is NotionPage and page.id in known)


def _facts(
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    probe: FixtureNotionAdapter,
) -> tuple[tuple[str, str], ...]:
    return (
        ("colour_names", ",".join(spec.colour_variants)),
        ("databases", ",".join(kind for kind, _database_id in stored.database_ids)),
        ("hubs", ",".join(hub.name for hub in spec.hubs)),
        ("page_count", str(_present_page_count(stored, probe))),
        (
            "secret_links",
            ",".join(
                _normalised_secret_link(record.secret_link, record.page_id)
                for record in stored.variants
            ),
        ),
        ("variant_count", str(len(stored.variants))),
    )


def _existing_proof_id(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, spec: ProductSpec
) -> str:
    title = _proof_title(stored, spec)
    matches = [
        page for page in probe.pages.values() if type(page) is NotionPage and page.title == title
    ]
    if len(matches) > 1:
        raise ProductBuildError("qa proof duplicate is ambiguous")
    if not matches:
        return ""
    if not _proof_matches(matches[0], stored, spec):
        raise ProductBuildError("qa proof duplicate does not match")
    return matches[0].id


def _proof_title(stored: ProductBuildCheckpoint, spec: ProductSpec) -> str:
    colour = spec.colour_variants[0]
    return f"{spec.title} / {colour} (Copy)"


def _proof_matches(page: object, stored: ProductBuildCheckpoint, spec: ProductSpec) -> bool:
    record = stored.variants[0]
    if type(page) is not NotionPage or page.title != _proof_title(stored, spec):
        return False
    source = stored.variants[0]
    return (
        page.id != source.page_id
        and page.parent_type == "workspace"
        and page.is_published is False
        and page.icon == hub_icon(spec.palette_tokens[0])
        and page.cover == hub_cover(spec.palette_tokens[0])
        and SPEC_ID_PROPERTY not in page.properties
        and record.name == spec.colour_variants[0]
    )


async def _apply_repairs(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    repairs: tuple[str, ...],
) -> None:
    guard_operation(probe, OP_QA)
    for record in stored.variants:
        page = _variant_page(probe, record)
        if "published" in repairs and page.is_published is not True:
            page = await probe.publish_page(page.id)
        if "duplicate_button" in repairs and page.duplicate_as_template is not True:
            page = await probe.set_duplicate_as_template(page.id, True)
        if "search_indexing" in repairs and page.search_indexing is not False:
            await probe.set_search_indexing(page.id, False)


async def _prove_duplicate(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    existing: str,
) -> str:
    if existing != "":
        return existing
    guard_operation(probe, OP_QA)
    copy = await probe.duplicate_page(stored.variants[0].page_id)
    if not _proof_matches(copy, stored, spec):
        raise ProductBuildError("qa proof duplicate does not match")
    return copy.id


def _with_qa(
    stored: ProductBuildCheckpoint,
    checks: tuple[tuple[str, bool], ...],
    repairs: tuple[str, ...],
    verdict: str,
    proof: str,
    facts: tuple[tuple[str, str], ...],
    recorded_at: datetime,
) -> ProductBuildCheckpoint:
    record = QaRecord(
        verdict=verdict,
        checks=checks,
        repairs=repairs,
        proof_page_id=proof,
        facts=facts,
    )
    return replace(stored, next_phase=PHASE_FACT_LEDGER, qa=record, recorded_at=recorded_at)


def _write_qa(
    path: Path,
    checkpoint: ProductBuildCheckpoint,
    created: Mapping[str, object],
) -> None:
    record = checkpoint.qa
    if record is None:
        raise ProductBuildError("qa record is missing")
    references = variant_provider_references(checkpoint)
    references[_QA_KEY] = {
        "checks": [
            {"check": name, "passed": "true" if passed else "false"}
            for name, passed in record.checks
        ],
        "facts": [{"fact": name, "value": value} for name, value in record.facts],
        "proof_page_id": record.proof_page_id,
        "repairs": list(record.repairs),
        "verdict": record.verdict,
    }
    write_checkpoint(path, checkpoint, references, retained_created_ids=created)
