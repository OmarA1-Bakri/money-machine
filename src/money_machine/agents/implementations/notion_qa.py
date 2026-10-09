"""A09 fixture product QA.

Session 07 prompt section 8. QA reads the variants checkpoint through
FixtureNotionAdapter and records PASS or BLOCKED with write_checkpoint.
A repairable flag is fixed with the existing adapter and QA runs again.
`live_qa_passed` re-runs these predicates for the fact ledger. The stored
verdict is not that result. A07, A08, and A09 stay DESIGNED. This module
does not open a network connection.
"""

from __future__ import annotations

import hashlib
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
_QA_PROVIDER_FAILED = "provider operation failed"
_QA_KEY = "qa"
_NOTIFICATION_TITLE = "Notification dashboard"
_SECTION_ROLES = ("purpose", "practice", "buyer")
_REPAIRABLE = ("published", "duplicate_button", "search_indexing")
_QA_KEYS = frozenset({"checks", "facts", "proof_page_id", "prose_digest", "repairs", "verdict"})
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
    checkpoint: ProductBuildCheckpoint | None = None
    try:
        saved = load_qa_record(path)
        if saved is not None and await _saved_holds(fixture, stored, validated, saved):
            return replace(stored, next_phase=PHASE_FACT_LEDGER, qa=saved)
        plan = await _plan(fixture, stored, validated)
        repairs: tuple[str, ...] = ()
        if not plan.blocked and plan.repairs:
            repairs = await _apply_repairs(fixture, stored, plan.repairs)
            plan = await _plan(fixture, stored, validated)
        if plan.blocked or plan.repairs:
            verdict = "BLOCKED"
            proof = ""
        else:
            verdict = "PASS"
            proof = await _prove_duplicate(fixture, stored, validated, plan.proof_page_id)
        facts = _facts(stored, validated, fixture)
        checkpoint = _with_qa(
            stored, plan.checks, repairs, verdict, proof, facts, moment, prose_digest(validated)
        )
        _write_qa(path, checkpoint, created)
    except ProviderFailure:
        # The provider response can carry a secret. It is not stored, raised,
        # or chained. The handler returns first, so the raise has no context.
        checkpoint = None
    if checkpoint is None:
        raise_recorded(path, BUILD_PHASES[-1], ProviderFailure(OP_QA, _QA_PROVIDER_FAILED))
    return checkpoint


def load_qa_record(path: Path) -> QaRecord | None:
    """Read the stored QA record, or None when the checkpoint has none."""
    envelope = load_payload(path)
    if envelope.payload is None:
        return None
    references = envelope.payload.get("provider_object_references")
    if type(references) is not dict or _QA_KEY not in references:
        return None
    return _require_qa(references[_QA_KEY])


def _require_qa(value: object) -> QaRecord:
    """Parse one QA record. A PASS with a false check is refused."""
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
    if verdict == "PASS" and any(passed is False for _name, passed in parsed_checks):
        raise ProductBuildError("qa record does not match")
    repairs = _require_repairs(entry["repairs"])
    facts = _require_pairs(entry["facts"], "fact", "value")
    digest = entry["prose_digest"]
    if type(digest) is not str or len(digest) != 64 or not _hex_digest(digest):
        raise ProductBuildError("qa record is incomplete")
    return QaRecord(
        verdict=verdict,
        checks=parsed_checks,
        repairs=repairs,
        proof_page_id=proof,
        facts=facts,
        prose_digest=digest,
    )


def prose_digest(spec: ProductSpec) -> str:
    """Digest of the descriptions, buyer, and flagship QA judged.

    Hub names and the row identity are not part of it. A later caller that
    keeps those and changes this prose does not match the stored digest.
    """
    rows = [hub.description for hub in spec.hubs]
    rows.append(spec.buyer_problem)
    rows.append(spec.flagship_feature)
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def _hex_digest(value: str) -> bool:
    return all(character in "0123456789abcdef" for character in value)


def _require_pairs(value: object, left: str, right: str) -> tuple[tuple[str, str], ...]:
    """Rows of two exact string fields. An empty list is incomplete."""
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
    """A list of tokens. A non-list is incomplete."""
    if type(value) is not list:
        raise ProductBuildError("qa record is incomplete")
    rows: list[str] = []
    for item in value:
        if type(item) is not str:
            raise ProductBuildError("qa record is incomplete")
        rows.append(require_token(item, label))
    return tuple(rows)


def _require_passed(value: str) -> bool:
    """A check flag is the word true or the word false."""
    if value == "true":
        return True
    if value == "false":
        return False
    raise ProductBuildError("qa record is incomplete")


def _require_repairs(value: object) -> tuple[str, ...]:
    """Repair names are unique and belong to the repairable set."""
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
    if saved.prose_digest != prose_digest(spec):
        return False
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
    """Publish, duplicate, and indexing, each true or false, in that order."""
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
    """Live structure checks. A false check blocks the verdict."""
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
    """True when the value is a database, including a subclass."""
    return isinstance(value, NotionDatabase)


def _variant_page(probe: FixtureNotionAdapter, record: VariantRecord) -> NotionPage:
    """The stored variant page, or a refusal when it is missing."""
    page = probe.pages.get(record.page_id)
    if type(page) is not NotionPage:
        raise ProductBuildError("qa variant page is missing")
    return page


def _spec_coverage(stored: ProductBuildCheckpoint, spec: ProductSpec) -> bool:
    """True when the stored colours and tokens match the spec."""
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
    """True when the stored databases match the tier catalogue."""
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
    """True when database titles are present once."""
    titles = [database.title for database in probe.databases.values() if _is_database(database)]
    expected = len(shared_database_kinds(spec)) + 1
    return len(titles) == expected and len(set(titles)) == len(titles)


def _hubs_present(
    probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, spec: ProductSpec
) -> bool:
    """True when each hub page is the stored child of home."""
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
    """True when each hub's linked views resolve."""
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
    """True when each dashboard formula matches the spec."""
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
    """True when the notification row names this identity."""
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
        if found is None or type(found.expression) is not str or found.expression != expression:
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
    """True when one stored formula matches the expected expression."""
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
    """The formula property, or None when it is not stored."""
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
    """The database for one kind, or None when the kind is absent."""
    for recorded, database_id in stored.database_ids:
        if recorded != kind:
            continue
        database = probe.databases.get(database_id)
        if isinstance(database, NotionDatabase):
            return database
    return None


def dashboard_formula_expressions(spec: ProductSpec) -> dict[str, tuple[str, str]]:
    """Expected formula name to (database kind, expression) for this spec."""
    generated = _generated(spec)
    return {
        name: (generated.databases[name], expression)
        for name, expression in generated.expressions.items()
    }


async def live_qa_passed(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> bool:
    """True when the live fixture still satisfies the QA predicates.

    The stored QA verdict is not consulted. A missing proof page is the
    pre-duplicate shape: it is not one of the ledger's known ids, and this
    function can still return True.
    """
    flags = _flag_failures(probe, stored)
    structural = await _structural_checks(probe, stored, spec)
    return all(passed for _name, passed in (*flags, *structural))


def _generated(spec: ProductSpec) -> NotificationDashboardFormulas:
    """Dashboard formulas derived from the spec."""
    definitions = schema_definitions()
    kinds = shared_database_kinds(spec)
    verified = {
        kind: {prop.name: prop.type for prop in definitions[kind].properties} for kind in kinds
    }
    return generate_notification_dashboard_formulas(verified)


def _is_page(value: object) -> bool:
    """True for a page, including a subclass. Exact type would ignore the subclass."""
    return isinstance(value, NotionPage)


def _page_count(probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint, proof: str) -> bool:
    """True when the known pages are the only pages in the probe."""
    known = _known_page_ids(stored)
    present = [page for page in probe.pages.values() if _is_page(page)]
    known_present = [page for page in present if page.id in known]
    extras = [page for page in present if page.id not in known]
    if len(known_present) != len(known):
        return False
    if not extras:
        return proof == ""
    return len(extras) == 1 and extras[0].id == proof


def _known_page_ids(stored: ProductBuildCheckpoint) -> set[str]:
    """Page ids the QA check counts. The proof copy is included."""
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
    """True when the link is the exact fixture URL for the page."""
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
    """True when no block contains the no-access marker.

    Non-text content is a product error. It is not a raw TypeError.
    """
    for block in probe.blocks.values():
        content = getattr(block, "content", None)
        if type(content) is not str:
            raise ProductBuildError("qa block content is not text")
        if "No access" in content:
            return False
    return True


def _cross_catalogue(probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint) -> bool:
    """True when every linked view and relation stays in this checkpoint."""
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
    """True when each variant has its icon, cover, one accent, and one sample."""
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
    """True when hub prose still matches the spec."""
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
    """Live counts compared with the facts QA persists. This is not a boolean."""
    databases: list[str] = []
    for _kind, database_id in stored.database_ids:
        database = probe.databases.get(database_id)
        if isinstance(database, NotionDatabase) and type(database.title) is str:
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
    """Drop a trailing slash and page id. The query and fragment stay."""
    suffix = "/" + page_id
    if link.endswith(suffix):
        return link[: -len(suffix)]
    return link


def _present_page_count(stored: ProductBuildCheckpoint, probe: FixtureNotionAdapter) -> int:
    """How many known pages are present in the probe."""
    known = _known_page_ids(stored)
    return sum(1 for page in probe.pages.values() if type(page) is NotionPage and page.id in known)


def _facts(
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    probe: FixtureNotionAdapter,
) -> tuple[tuple[str, str], ...]:
    """The fact pairs a QA record stores."""
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
    """The stored proof page id, or empty when there is none."""
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
    """The title of the fresh-duplicate proof page."""
    colour = spec.colour_variants[0]
    return f"{spec.title} / {colour} (Copy)"


def _proof_matches(page: object, stored: ProductBuildCheckpoint, spec: ProductSpec) -> bool:
    """True when the page is the stored proof copy."""
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
) -> tuple[str, ...]:
    """Apply repairable flags. A publish that is not trusted stops the rest.

    The returned names are the repairs whose adapter call ran, including a
    publish that wrote and then failed the trusted-link check.
    """
    guard_operation(probe, OP_QA)
    done: list[str] = []
    for record in stored.variants:
        page = _variant_page(probe, record)
        if "published" in repairs and page.is_published is not True:
            page = await probe.publish_page(page.id)
            done.append("published")
            if page.is_published is not True or not _is_trusted_link(page.public_url, page.id):
                return tuple(dict.fromkeys(done))
        if "duplicate_button" in repairs and page.duplicate_as_template is not True:
            page = await probe.set_duplicate_as_template(page.id, True)
            done.append("duplicate_button")
        if "search_indexing" in repairs and page.search_indexing is not False:
            await probe.set_search_indexing(page.id, False)
            done.append("search_indexing")
    return tuple(dict.fromkeys(done))


async def _prove_duplicate(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    existing: str,
) -> str:
    """Publish the fresh-duplicate proof page."""
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
    digest: str,
) -> ProductBuildCheckpoint:
    """Return the checkpoint with the QA record attached."""
    record = QaRecord(
        verdict=verdict,
        checks=checks,
        repairs=repairs,
        proof_page_id=proof,
        facts=facts,
        prose_digest=digest,
    )
    return replace(stored, next_phase=PHASE_FACT_LEDGER, qa=record, recorded_at=recorded_at)


def _write_qa(
    path: Path,
    checkpoint: ProductBuildCheckpoint,
    created: Mapping[str, object],
) -> None:
    """Persist the QA record through the single progress writer."""
    record = checkpoint.qa
    if record is None:
        raise ProductBuildError("qa record is missing")
    references = variant_provider_references(checkpoint)
    envelope = load_payload(path)
    if envelope.payload is not None:
        prior = envelope.payload.get("provider_object_references")
        if type(prior) is dict:
            for key in ("fact_ledger", "workflow_link"):
                if key in prior:
                    references[key] = prior[key]
    references[_QA_KEY] = {
        "checks": [
            {"check": name, "passed": "true" if passed else "false"}
            for name, passed in record.checks
        ],
        "facts": [{"fact": name, "value": value} for name, value in record.facts],
        "proof_page_id": record.proof_page_id,
        "prose_digest": record.prose_digest,
        "repairs": list(record.repairs),
        "verdict": record.verdict,
    }
    write_checkpoint(path, checkpoint, references, retained_created_ids=created)
