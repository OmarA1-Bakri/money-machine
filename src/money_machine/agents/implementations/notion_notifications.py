"""A07 fixture phase 5: the one-row notification dashboard.

Resumes the identity-hub checkpoint and stores one notification database on
the fixture probe. The next build phase is recorded and not run. This module
does not open a network connection or commission an agent.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import cast

from money_machine.agents.implementations.notion_dashboard import require_home_page
from money_machine.agents.implementations.notion_hubs import (
    hub_provider_references,
    parse_identity_hubs_checkpoint,
    require_identity_hubs,
)
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    CHECKPOINT_KEYS,
    NotificationDashboardRecord,
    ProductBuildCheckpoint,
    ProductBuildError,
    exact_keys,
    require_datetime,
    require_path,
    require_probe,
    require_same_spec,
    require_spec,
    require_token,
)
from money_machine.agents.implementations.notion_shared_databases import shared_database_kinds
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.domain import (
    NotionDatabase,
    NotionDatabaseProperty,
    NotionFormula,
    NotionPage,
    NotionRelation,
    NotionRollup,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from money_machine.integrations.notion.formulas import generate_notification_dashboard_formulas
from money_machine.integrations.notion.relations import (
    CanonicalDatabase,
    CanonicalDatabases,
    DashboardRollup,
    NotificationDashboard,
)
from money_machine.integrations.notion.relations import (
    build_notification_dashboard as plan_notification_dashboard,
)
from money_machine.integrations.notion.schema_builder import (
    build_database_schema,
    schema_definitions,
)

_PHASE_FOUR = BUILD_PHASES[:4]
_PHASE_FIVE = BUILD_PHASES[:5]
_NOTIFICATION_KEY = "notification_dashboard"
_DATABASE_TITLE = "Notification dashboard"
_BUYER_PROPERTY = "Buyer name"
_DATE_PROPERTY = "current_date"
_DATE_EXPRESSION = "now()"
_SAMPLE_MARKER = "sample_marker"
_SAMPLE_VALUE = "SAMPLE"
_DATABASE_PARENT = "page_id"
_ROW_PARENT = "database_id"
_RECORD_KEYS = frozenset(
    {
        "buyer_name_property_id",
        "current_date_property_id",
        "database_id",
        "formulas",
        "relations",
        "rollups",
        "row_page_id",
        "samples",
    }
)
_FORMULA_KEYS = frozenset({"kind", "name", "property_id"})
_RELATION_KEYS = frozenset({"data_type", "property_id"})
_ROLLUP_KEYS = frozenset({"name", "property_id"})
_SAMPLE_KEYS = frozenset({"kind", "page_id"})


async def build_notification_dashboard(
    spec: object,
    probe: object,
    checkpoint_path: object,
    *,
    recorded_at: object,
) -> ProductBuildCheckpoint:
    """Create the one-row dashboard, or resume when that phase is already stored."""
    validated = require_spec(spec)
    fixture = require_probe(probe)
    path = require_path(checkpoint_path)
    moment = require_datetime(recorded_at)
    stored = _load_checkpoint(path)
    require_same_spec(stored, validated)
    kinds = shared_database_kinds(validated)
    suffixes = _formula_suffixes(kinds)
    if stored.checkpoint_names == _PHASE_FIVE:
        _require_saved(fixture, stored, validated, kinds, suffixes)
        return stored
    record = await _ensure(fixture, stored, validated, kinds, suffixes)
    checkpoint = _checkpoint_with_notification(stored, record, moment)
    _write_checkpoint(path, checkpoint)
    return checkpoint


def _formula_suffixes(kinds: tuple[str, ...]) -> dict[str, tuple[tuple[str, str], ...]]:
    definitions = schema_definitions()
    verified = {
        kind: {prop.name: prop.type for prop in definitions[kind].properties} for kind in kinds
    }
    generated = generate_notification_dashboard_formulas(verified)
    grouped: dict[str, list[tuple[str, str]]] = {kind: [] for kind in kinds}
    for name, expression in generated.expressions.items():
        grouped[generated.databases[name]].append((name, expression))
    return {kind: tuple(rows) for kind, rows in grouped.items()}


def _plan(kinds: tuple[str, ...]) -> NotificationDashboard:
    canonical = CanonicalDatabases(
        data_types=kinds,
        by_type={kind: CanonicalDatabase(data_type=kind) for kind in kinds},
    )
    return plan_notification_dashboard(canonical)


def _load_checkpoint(path: Path) -> ProductBuildCheckpoint:
    if not path.exists():
        raise ProductBuildError("notification dashboard requires the identity hubs checkpoint")
    text = path.read_text(encoding="utf-8")
    if text == "" or not text.endswith("\n"):
        raise ProductBuildError("checkpoint is incomplete")
    try:
        decoded = cast(object, json.loads(text))
    except json.JSONDecodeError as error:
        raise ProductBuildError("checkpoint is not JSON") from error
    if type(decoded) is not dict:
        raise ProductBuildError("checkpoint must be an object")
    payload = cast(dict[object, object], decoded)
    names = payload.get("checkpoint_names")
    if names == list(_PHASE_FOUR):
        return parse_identity_hubs_checkpoint(payload)
    if names == list(_PHASE_FIVE):
        return _parse_notification_checkpoint(payload)
    raise ProductBuildError("notification dashboard requires the identity hubs checkpoint")


def _parse_notification_checkpoint(payload: dict[object, object]) -> ProductBuildCheckpoint:
    if not exact_keys(payload, CHECKPOINT_KEYS):
        raise ProductBuildError("checkpoint fields are missing or unsupported")
    names = payload["checkpoint_names"]
    if type(names) is not list or names != list(_PHASE_FIVE):
        raise ProductBuildError("checkpoint must record the notification dashboard")
    references = payload["provider_object_references"]
    if type(references) is not dict:
        raise ProductBuildError("provider references must be an object")
    refs = cast(dict[object, object], references)
    phase_four_keys = set(refs) - {_NOTIFICATION_KEY}
    if _NOTIFICATION_KEY not in refs or len(phase_four_keys) + 1 != len(refs):
        raise ProductBuildError("provider references are missing or unsupported")
    record = _require_record(refs[_NOTIFICATION_KEY])
    phase_four = dict(payload)
    phase_four["checkpoint_names"] = list(_PHASE_FOUR)
    phase_four["provider_object_references"] = {key: refs[key] for key in phase_four_keys}
    base = parse_identity_hubs_checkpoint(phase_four)
    return replace(
        base,
        checkpoint_names=_PHASE_FIVE,
        next_phase=BUILD_PHASES[len(_PHASE_FIVE)],
        notification_dashboard=record,
    )


def _require_record(value: object) -> NotificationDashboardRecord:
    if type(value) is not dict:
        raise ProductBuildError("checkpoint notification dashboard must be an object")
    entry = cast(dict[object, object], value)
    if not exact_keys(entry, _RECORD_KEYS):
        raise ProductBuildError(
            "checkpoint notification dashboard fields are missing or unsupported"
        )
    return NotificationDashboardRecord(
        database_id=require_token(entry["database_id"], "notification database"),
        row_page_id=require_token(entry["row_page_id"], "notification row"),
        buyer_name_property_id=require_token(entry["buyer_name_property_id"], "buyer name"),
        current_date_property_id=require_token(entry["current_date_property_id"], "current date"),
        relations=_require_pairs(entry["relations"], _RELATION_KEYS, "data_type", "relation"),
        rollups=_require_pairs(entry["rollups"], _ROLLUP_KEYS, "name", "rollup"),
        formulas=_require_formulas(entry["formulas"]),
        samples=_require_pairs(entry["samples"], _SAMPLE_KEYS, "kind", "sample"),
    )


def _require_pairs(
    value: object, keys: frozenset[str], label_key: str, field: str
) -> tuple[tuple[str, str], ...]:
    if type(value) is not list:
        raise ProductBuildError(f"checkpoint notification {field} must be a list")
    rows: list[tuple[str, str]] = []
    for item in cast(list[object], value):
        if type(item) is not dict:
            raise ProductBuildError(f"checkpoint notification {field} must be an object")
        entry = cast(dict[object, object], item)
        if not exact_keys(entry, keys):
            raise ProductBuildError(
                f"checkpoint notification {field} fields are missing or unsupported"
            )
        rows.append(
            (
                require_token(entry[label_key], f"notification {field}"),
                require_token(
                    entry["property_id"] if "property_id" in entry else entry["page_id"], field
                ),
            )
        )
    return tuple(rows)


def _require_formulas(value: object) -> tuple[tuple[str, str, str], ...]:
    if type(value) is not list:
        raise ProductBuildError("checkpoint notification formula must be a list")
    rows: list[tuple[str, str, str]] = []
    for item in cast(list[object], value):
        if type(item) is not dict:
            raise ProductBuildError("checkpoint notification formula must be an object")
        entry = cast(dict[object, object], item)
        if not exact_keys(entry, _FORMULA_KEYS):
            raise ProductBuildError(
                "checkpoint notification formula fields are missing or unsupported"
            )
        rows.append(
            (
                require_token(entry["kind"], "notification formula"),
                require_token(entry["name"], "notification formula"),
                require_token(entry["property_id"], "notification formula"),
            )
        )
    return tuple(rows)


def _checkpoint_with_notification(
    stored: ProductBuildCheckpoint,
    record: NotificationDashboardRecord,
    recorded_at: datetime,
) -> ProductBuildCheckpoint:
    return replace(
        stored,
        checkpoint_names=_PHASE_FIVE,
        next_phase=BUILD_PHASES[len(_PHASE_FIVE)],
        notification_dashboard=record,
        recorded_at=recorded_at,
    )


def _write_checkpoint(path: Path, checkpoint: ProductBuildCheckpoint) -> None:
    record = checkpoint.notification_dashboard
    if record is None:
        raise ProductBuildError("notification dashboard is missing")
    references = hub_provider_references(checkpoint)
    references[_NOTIFICATION_KEY] = {
        "buyer_name_property_id": record.buyer_name_property_id,
        "current_date_property_id": record.current_date_property_id,
        "database_id": record.database_id,
        "formulas": [
            {"kind": kind, "name": name, "property_id": property_id}
            for kind, name, property_id in record.formulas
        ],
        "relations": [
            {"data_type": data_type, "property_id": property_id}
            for data_type, property_id in record.relations
        ],
        "rollups": [
            {"name": name, "property_id": property_id} for name, property_id in record.rollups
        ],
        "row_page_id": record.row_page_id,
        "samples": [{"kind": kind, "page_id": page_id} for kind, page_id in record.samples],
    }
    payload = {
        "build_kind": checkpoint.build_kind,
        "build_version": checkpoint.build_version,
        "checkpoint_names": list(checkpoint.checkpoint_names),
        "palette_name": checkpoint.palette_name,
        "palette_tokens": [list(token) for token in checkpoint.palette_tokens],
        "product_id": checkpoint.product_id,
        "provider_object_references": references,
        "recorded_at": checkpoint.recorded_at.isoformat(),
        "spec_id": checkpoint.spec_id,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="ascii")
    os.replace(temporary, path)


def _require_saved(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    kinds: tuple[str, ...],
    suffixes: dict[str, tuple[tuple[str, str], ...]],
) -> None:
    record = stored.notification_dashboard
    if record is None:
        raise ProductBuildError("notification dashboard is missing")
    require_home_page(probe, stored, spec)
    plan = _plan(kinds)
    _require_objects(probe, stored, spec, record, plan, suffixes)
    require_identity_hubs(
        probe,
        stored,
        spec,
        extra_page_ids=(record.row_page_id, *(page_id for _kind, page_id in record.samples)),
        extra_database_ids=(record.database_id,),
        formula_suffixes=suffixes,
        formulas_optional=False,
    )


def _require_objects(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    record: NotificationDashboardRecord,
    plan: NotificationDashboard,
    suffixes: dict[str, tuple[tuple[str, str], ...]],
) -> None:
    database_ids = dict(stored.database_ids)
    _require_formula_ids(probe, database_ids, record, suffixes)
    database = probe.databases.get(record.database_id)
    if (
        type(database) is not NotionDatabase
        or database.parent_id != stored.page_id
        or not _database_ok(database, record, plan, database_ids)
    ):
        raise ProductBuildError("notification database is missing")
    _require_samples(probe, spec, record, database_ids)
    _require_row(probe, spec, record)


def _require_formula_ids(
    probe: FixtureNotionAdapter,
    database_ids: dict[str, str],
    record: NotificationDashboardRecord,
    suffixes: dict[str, tuple[tuple[str, str], ...]],
) -> None:
    expected = [
        (kind, name, database_ids[kind])
        for kind, rows in suffixes.items()
        for name, _expression in rows
    ]
    found = tuple((kind, name) for kind, name, _property_id in record.formulas)
    if found != tuple((kind, name) for kind, name, _database_id in expected):
        raise ProductBuildError("notification formula is missing")
    for (_kind, name, property_id), (kind, formula_name, database_id) in zip(
        record.formulas, expected, strict=True
    ):
        if name != formula_name:
            raise ProductBuildError("notification formula is missing")
        expression = dict(suffixes[kind])[name]
        prop = _named_property(probe.databases.get(database_id), property_id)
        if not _formula_property(prop, name, expression):
            raise ProductBuildError("notification formula is missing")


def _named_property(database: object, property_id: str) -> NotionDatabaseProperty | None:
    if type(database) is not NotionDatabase:
        return None
    for prop in database.properties:
        if type(prop) is NotionDatabaseProperty and prop.id == property_id:
            return prop
    return None


def _formula_property(prop: NotionDatabaseProperty | None, name: str, expression: str) -> bool:
    if prop is None:
        return False
    formula = prop.config.get("formula")
    return (
        prop.name == name
        and prop.type == "formula"
        and type(formula) is NotionFormula
        and formula.id == prop.id
        and formula.name == name
        and formula.expression == expression
    )


def _database_ok(
    database: object,
    record: NotificationDashboardRecord,
    plan: NotificationDashboard,
    database_ids: dict[str, str],
) -> bool:
    if (
        type(database) is not NotionDatabase
        or database.id != record.database_id
        or database.title != _DATABASE_TITLE
        or database.parent_type != _DATABASE_PARENT
        or database.icon is not None
        or database.cover is not None
    ):
        return False
    properties = database.properties
    expected = _expected_names(plan)
    if [prop.name for prop in properties] != expected:
        return False
    buyer = properties[1]
    current = properties[2]
    if buyer.id != record.buyer_name_property_id or buyer.type != "text" or buyer.config != {}:
        return False
    if not _formula_property(current, _DATE_PROPERTY, _DATE_EXPRESSION):
        return False
    if current.id != record.current_date_property_id:
        return False
    relation_ids = dict(record.relations)
    rollup_ids = dict(record.rollups)
    if tuple(relation_ids) != tuple(item.data_type for item in plan.relations):
        return False
    if tuple(rollup_ids) != tuple(item.name for item in plan.rollups):
        return False
    for relation, prop in zip(plan.relations, properties[3 : 3 + len(plan.relations)], strict=True):
        if not _relation_property(prop, relation.data_type, database_ids[relation.data_type]):
            return False
        if prop.id != relation_ids[relation.data_type]:
            return False
    offset = 3 + len(plan.relations)
    for rollup, prop in zip(plan.rollups, properties[offset:], strict=True):
        if not _rollup_property(
            prop,
            rollup,
            relation_ids[rollup.relation_name],
            _stored_formula_id(record, rollup),
        ):
            return False
        if prop.id != rollup_ids[rollup.name]:
            return False
    return "client_name" not in {prop.name for prop in properties}


def _stored_formula_id(record: NotificationDashboardRecord, rollup: DashboardRollup) -> str:
    for kind, name, property_id in record.formulas:
        if kind == rollup.relation_name and name == rollup.property_name:
            return property_id
    return ""


def _expected_names(plan: NotificationDashboard) -> list[str]:
    names = ["Name", _BUYER_PROPERTY, _DATE_PROPERTY]
    names.extend(item.data_type for item in plan.relations)
    names.extend(item.name for item in plan.rollups)
    return names


def _relation_property(prop: NotionDatabaseProperty, name: str, target_id: str) -> bool:
    relation = prop.config.get("relation")
    return (
        prop.name == name
        and prop.type == "relation"
        and type(relation) is NotionRelation
        and relation.id == prop.id
        and relation.database_id == target_id
    )


def _rollup_property(
    prop: NotionDatabaseProperty, rollup: DashboardRollup, relation_id: str, formula_id: str
) -> bool:
    found = prop.config.get("rollup")
    return (
        prop.name == rollup.name
        and prop.type == "rollup"
        and type(found) is NotionRollup
        and found.id == prop.id
        and found.function == rollup.function
        and found.relation_property_id == relation_id
        and found.rollup_property_id == formula_id
        and formula_id != ""
    )


def _require_samples(
    probe: FixtureNotionAdapter,
    spec: ProductSpec,
    record: NotificationDashboardRecord,
    database_ids: dict[str, str],
) -> None:
    del spec
    for kind, page_id in record.samples:
        page = probe.pages.get(page_id)
        if not _sample_ok(page, kind, database_ids[kind]):
            raise ProductBuildError("notification sample is missing")
        if _page_blocks(probe, page_id):
            raise ProductBuildError("notification sample does not match")


def _require_row(
    probe: FixtureNotionAdapter, spec: ProductSpec, record: NotificationDashboardRecord
) -> None:
    page = probe.pages.get(record.row_page_id)
    if not _row_ok(page, spec, record):
        raise ProductBuildError("notification row is missing")
    if _page_blocks(probe, record.row_page_id):
        raise ProductBuildError("notification row does not match")
    rows = _database_pages(probe, record.database_id)
    if len(rows) != 1 or rows[0].id != record.row_page_id:
        raise ProductBuildError("notification row does not match")


def _sample_ok(page: object, kind: str, database_id: str) -> bool:
    return (
        type(page) is NotionPage
        and page.title == f"SAMPLE {kind}"
        and page.parent_id == database_id
        and page.parent_type == _ROW_PARENT
        and page.is_published is False
        and page.properties.get(_SAMPLE_MARKER) == _SAMPLE_VALUE
    )


def _row_ok(page: object, spec: ProductSpec, record: NotificationDashboardRecord) -> bool:
    if (
        type(page) is not NotionPage
        or page.title != spec.identity
        or page.parent_id != record.database_id
        or page.parent_type != _ROW_PARENT
        or page.is_published is not False
        or _SAMPLE_MARKER in page.properties
        or page.properties.get(_BUYER_PROPERTY) != spec.identity
        or "client_name" in page.properties
    ):
        return False
    return all(
        page.properties.get(data_type) == _sample_id(record, data_type)
        for data_type, _id in record.relations
    )


def _sample_id(record: NotificationDashboardRecord, kind: str) -> str:
    for sample_kind, page_id in record.samples:
        if sample_kind == kind:
            return page_id
    return ""


def _page_blocks(probe: FixtureNotionAdapter, page_id: str) -> list[object]:
    return [block for block in probe.blocks.values() if block.parent_id == page_id]


def _database_pages(probe: FixtureNotionAdapter, database_id: str) -> list[NotionPage]:
    return [
        page
        for page in probe.pages.values()
        if type(page) is NotionPage
        and page.parent_id == database_id
        and page.parent_type == _ROW_PARENT
    ]


async def _ensure(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    kinds: tuple[str, ...],
    suffixes: dict[str, tuple[tuple[str, str], ...]],
) -> NotificationDashboardRecord:
    page = require_home_page(probe, stored, spec)
    plan = _plan(kinds)
    database_ids = dict(stored.database_ids)
    _reject_formula_shape(probe, database_ids, suffixes)
    existing = _find_notification_database(probe, page, kinds)
    if existing is not None and not _sources_complete(probe, database_ids, suffixes):
        raise ProductBuildError("notification database does not match")
    _reject_foreign_rows(probe, database_ids, plan, existing)
    _require_prior_objects(probe, stored, spec, database_ids, plan, suffixes, existing)
    formula_ids = await _ensure_formulas(probe, database_ids, suffixes)
    if existing is not None and not _adopted_database(existing, plan, database_ids, formula_ids):
        raise ProductBuildError("notification database does not match")
    samples = await _ensure_samples(probe, plan, database_ids)
    database = existing or await _create_database(probe, page, plan, database_ids, formula_ids)
    if existing is not None:
        _require_adopted_ids(database, plan)
    row = await _ensure_row(probe, spec, database, plan, samples)
    return _record_from(database, row, plan, formula_ids, samples)


def _reject_formula_shape(
    probe: FixtureNotionAdapter,
    database_ids: dict[str, str],
    suffixes: dict[str, tuple[tuple[str, str], ...]],
) -> None:
    for kind, database_id in database_ids.items():
        database = probe.databases.get(database_id)
        if type(database) is not NotionDatabase:
            raise ProductBuildError("notification formula does not match")
        suffix = suffixes.get(kind, ())
        catalogue = len(build_database_schema(kind).properties)
        extra = database.properties[catalogue:]
        if not extra:
            continue
        if len(extra) != len(suffix) or not all(
            _formula_property(prop, name, expression)
            for prop, (name, expression) in zip(extra, suffix, strict=True)
        ):
            raise ProductBuildError("notification formula does not match")


def _sources_complete(
    probe: FixtureNotionAdapter,
    database_ids: dict[str, str],
    suffixes: dict[str, tuple[tuple[str, str], ...]],
) -> bool:
    for kind, rows in suffixes.items():
        if not rows:
            continue
        database = probe.databases.get(database_ids[kind])
        if type(database) is not NotionDatabase:
            return False
        catalogue = len(build_database_schema(kind).properties)
        if len(database.properties) - catalogue != len(rows):
            return False
    return True


def _find_notification_database(
    probe: FixtureNotionAdapter, page: NotionPage, kinds: tuple[str, ...]
) -> NotionDatabase | None:
    extras = [
        database
        for database in probe.databases.values()
        if type(database) is NotionDatabase
        and database.parent_id == page.id
        and database.parent_type == _DATABASE_PARENT
        and database.title not in kinds
    ]
    if not extras:
        return None
    if len(extras) != 1 or extras[0].title != _DATABASE_TITLE:
        raise ProductBuildError("notification database does not match")
    return extras[0]


async def _ensure_formulas(
    probe: FixtureNotionAdapter,
    database_ids: dict[str, str],
    suffixes: dict[str, tuple[tuple[str, str], ...]],
) -> dict[str, tuple[tuple[str, str], ...]]:
    saved: dict[str, tuple[tuple[str, str], ...]] = {}
    for kind, database_id in database_ids.items():
        suffix = suffixes.get(kind, ())
        if not suffix:
            saved[kind] = ()
            continue
        database = probe.databases[database_id]
        catalogue = len(build_database_schema(kind).properties)
        extra = database.properties[catalogue:]
        if extra:
            saved[kind] = tuple((prop.name, prop.id) for prop in extra)
            continue
        created: list[tuple[str, str]] = []
        for name, expression in suffix:
            formula = await probe.create_formula(database_id, name, expression)
            created.append((name, formula.id))
        saved[kind] = tuple(created)
    return saved


def _adopted_database(
    database: NotionDatabase,
    plan: NotificationDashboard,
    database_ids: dict[str, str],
    formula_ids: dict[str, tuple[tuple[str, str], ...]],
) -> bool:
    if [prop.name for prop in database.properties] != _expected_names(plan):
        return False
    if database.properties[1].type != "text" or database.properties[1].name != _BUYER_PROPERTY:
        return False
    if not _formula_property(database.properties[2], _DATE_PROPERTY, _DATE_EXPRESSION):
        return False
    relation_props = database.properties[3 : 3 + len(plan.relations)]
    if len(relation_props) != len(plan.relations):
        return False
    for relation, prop in zip(plan.relations, relation_props, strict=True):
        if not _relation_property(prop, relation.data_type, database_ids[relation.data_type]):
            return False
    relation_ids = {prop.name: prop.id for prop in relation_props}
    for rollup, prop in zip(
        plan.rollups, database.properties[3 + len(plan.relations) :], strict=True
    ):
        formula_id = dict(formula_ids[rollup.relation_name])[rollup.property_name]
        if not _rollup_property(prop, rollup, relation_ids[rollup.relation_name], formula_id):
            return False
    return True


def _require_prior_objects(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    database_ids: dict[str, str],
    plan: NotificationDashboard,
    suffixes: dict[str, tuple[tuple[str, str], ...]],
    existing: NotionDatabase | None,
) -> None:
    sample_ids: list[str] = []
    for relation in plan.relations:
        pages = _database_pages(probe, database_ids[relation.data_type])
        if len(pages) == 1:
            sample_ids.append(pages[0].id)
    row_ids: list[str] = []
    if existing is not None and len(_database_pages(probe, existing.id)) == 1:
        row_ids.append(_database_pages(probe, existing.id)[0].id)
    require_identity_hubs(
        probe,
        stored,
        spec,
        extra_page_ids=(*row_ids, *sample_ids),
        extra_database_ids=() if existing is None else (existing.id,),
        formula_suffixes=suffixes,
        formulas_optional=True,
    )


def _reject_foreign_rows(
    probe: FixtureNotionAdapter,
    database_ids: dict[str, str],
    plan: NotificationDashboard,
    existing: NotionDatabase | None,
) -> None:
    _ = existing
    linked = {item.data_type for item in plan.relations}
    for database_id in database_ids.values():
        kind = _kind_of(database_ids, database_id)
        if kind not in linked and _database_pages(probe, database_id):
            raise ProductBuildError("notification sample is unexpected")
    for relation in plan.relations:
        pages = _database_pages(probe, database_ids[relation.data_type])
        if len(pages) > 1:
            raise ProductBuildError("notification sample is unexpected")
        if len(pages) == 1 and not _sample_ok(
            pages[0], relation.data_type, database_ids[relation.data_type]
        ):
            raise ProductBuildError("notification sample does not match")


def _kind_of(database_ids: dict[str, str], database_id: str) -> str:
    for kind, stored_id in database_ids.items():
        if stored_id == database_id:
            return kind
    return ""


async def _ensure_samples(
    probe: FixtureNotionAdapter,
    plan: NotificationDashboard,
    database_ids: dict[str, str],
) -> tuple[tuple[str, str], ...]:
    samples: list[tuple[str, str]] = []
    for relation in plan.relations:
        pages = _database_pages(probe, database_ids[relation.data_type])
        if pages:
            samples.append((relation.data_type, pages[0].id))
            continue
        page = await probe.create_page(
            f"SAMPLE {relation.data_type}",
            parent_id=database_ids[relation.data_type],
            parent_type=_ROW_PARENT,
        )
        page.properties[_SAMPLE_MARKER] = _SAMPLE_VALUE
        samples.append((relation.data_type, page.id))
    return tuple(samples)


async def _create_database(
    probe: FixtureNotionAdapter,
    page: NotionPage,
    plan: NotificationDashboard,
    database_ids: dict[str, str],
    formula_ids: dict[str, tuple[tuple[str, str], ...]],
) -> NotionDatabase:
    database = await probe.create_database(
        title=_DATABASE_TITLE, parent_id=page.id, parent_type=_DATABASE_PARENT
    )
    await probe.add_property(database.id, "Name", "title", {})
    await probe.add_property(database.id, _BUYER_PROPERTY, "text", {})
    await probe.create_formula(database.id, _DATE_PROPERTY, _DATE_EXPRESSION)
    for relation in plan.relations:
        await probe.create_relation(
            database.id, relation.data_type, database_ids[relation.data_type]
        )
    relation_ids = {prop.name: prop.id for prop in database.properties if prop.type == "relation"}
    for rollup in plan.rollups:
        formula_id = dict(formula_ids[rollup.relation_name])[rollup.property_name]
        await probe.create_rollup(
            database.id,
            rollup.name,
            relation_ids[rollup.relation_name],
            formula_id,
            rollup.function,
        )
    return database


def _require_adopted_ids(database: NotionDatabase, plan: NotificationDashboard) -> None:
    if [prop.name for prop in database.properties] != _expected_names(plan):
        raise ProductBuildError("notification database does not match")


async def _ensure_row(
    probe: FixtureNotionAdapter,
    spec: ProductSpec,
    database: NotionDatabase,
    plan: NotificationDashboard,
    samples: tuple[tuple[str, str], ...],
) -> NotionPage:
    pages = _database_pages(probe, database.id)
    if len(pages) > 1:
        raise ProductBuildError("notification row does not match")
    sample_ids = dict(samples)
    if pages:
        page = pages[0]
        if page.title != spec.identity or page.properties.get(_BUYER_PROPERTY) != spec.identity:
            raise ProductBuildError("notification row does not match")
        if _SAMPLE_MARKER in page.properties or "client_name" in page.properties:
            raise ProductBuildError("notification row does not match")
        for relation in plan.relations:
            if page.properties.get(relation.data_type) != sample_ids[relation.data_type]:
                raise ProductBuildError("notification row does not match")
        return page
    page = await probe.create_page(spec.identity, parent_id=database.id, parent_type=_ROW_PARENT)
    page.properties[_BUYER_PROPERTY] = spec.identity
    for relation in plan.relations:
        page.properties[relation.data_type] = sample_ids[relation.data_type]
    return page


def _record_from(
    database: NotionDatabase,
    row: NotionPage,
    plan: NotificationDashboard,
    formula_ids: dict[str, tuple[tuple[str, str], ...]],
    samples: tuple[tuple[str, str], ...],
) -> NotificationDashboardRecord:
    by_name = {prop.name: prop.id for prop in database.properties}
    relations = tuple((item.data_type, by_name[item.data_type]) for item in plan.relations)
    rollups = tuple((item.name, by_name[item.name]) for item in plan.rollups)
    formulas = tuple(
        (kind, name, property_id)
        for kind, rows in formula_ids.items()
        for name, property_id in rows
    )
    return NotificationDashboardRecord(
        database_id=database.id,
        row_page_id=row.id,
        buyer_name_property_id=by_name[_BUYER_PROPERTY],
        current_date_property_id=by_name[_DATE_PROPERTY],
        relations=relations,
        rollups=rollups,
        formulas=formulas,
        samples=samples,
    )
