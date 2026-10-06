"""A07 fixture phase 2: canonical shared databases.

Resumes the phase-1 checkpoint and stores the playbook database set on the
fixture probe. The next phase name is dashboard_and_navigation. This module
does not run that phase, open a network connection, or commission an agent.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import cast

from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    CHECKPOINT_KEYS,
    PHASE_DASHBOARD_AND_NAVIGATION,
    PHASE_SHARED_DATABASES,
    PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
    PROVIDER_KEYS,
    ProductBuildCheckpoint,
    ProductBuildError,
    exact_keys,
    find_spec_page,
    parse_checkpoint,
    require_datetime,
    require_path,
    require_probe,
    require_same_spec,
    require_spec,
    require_token,
    resume_stored,
)
from money_machine.agents.implementations.notion_progress import (
    ProviderFailure,
    guard_operation,
    load_payload,
    raise_recorded,
    shared_create_operation,
)
from money_machine.agents.implementations.notion_progress_record import write_checkpoint
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.domain import (
    NotionDatabase,
    NotionDatabaseProperty,
    NotionFormula,
    NotionPage,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from money_machine.integrations.notion.schema_builder import DatabaseSchema, build_database_schema

SAMPLE_MARKER = "sample_marker"
SAMPLE_MARKER_VALUE = "SAMPLE"
_SAMPLE_MARKER_CONFIG = {"options": [SAMPLE_MARKER_VALUE]}

PLANNER_SHARED_DATABASES: tuple[str, ...] = (
    "Tasks",
    "Events",
    "Habits",
    "Finance",
    "Meals",
    "Notes",
)
BUSINESS_SHARED_DATABASES: tuple[str, ...] = (
    "Clients",
    "Projects",
    "Content",
    "Invoices",
    "Tasks",
    "Notes",
)
_DATABASE_PARENT = "page_id"
_TIER_MASS = "mass"
_TIER_BUSINESS = "business"
_SHARED_DATABASES_KEY = "shared_databases"
_DATABASE_ENTRY_KEYS = frozenset({"database_id", "kind"})
_PHASE_ONE_NAMES = (PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,)
_PHASE_TWO_NAMES = (PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL, PHASE_SHARED_DATABASES)


def shared_database_kinds(spec: ProductSpec) -> tuple[str, ...]:
    """Mass and business catalogue sets. A named subset must match the tier."""
    return _shared_database_kinds(spec)


def _shared_database_kinds(spec: ProductSpec) -> tuple[str, ...]:
    """Playbook defaults for mass, the business set for business, both canonical."""
    if spec.tier == _TIER_MASS:
        expected = PLANNER_SHARED_DATABASES
    elif spec.tier == _TIER_BUSINESS:
        expected = BUSINESS_SHARED_DATABASES
    else:
        raise ProductBuildError("shared databases require tier mass or business")
    named = spec.shared_databases
    if type(named) is not tuple or any(type(item) is not str for item in named):
        raise ProductBuildError("shared databases must be a tuple of strings")
    if named and (len(named) != len(expected) or set(named) != set(expected)):
        raise ProductBuildError("shared databases do not match the tier")
    return expected


async def build_shared_databases(
    spec: object,
    probe: object,
    checkpoint_path: object,
    *,
    recorded_at: object,
) -> ProductBuildCheckpoint:
    """Create the canonical databases, or resume when that phase is already stored."""
    validated = require_spec(spec)
    fixture = require_probe(probe)
    path = require_path(checkpoint_path)
    moment = require_datetime(recorded_at)
    kinds = _shared_database_kinds(validated)
    stored = _read_product_checkpoint(path)
    if stored is None:
        raise ProductBuildError("shared databases require the phase 1 checkpoint")
    require_same_spec(stored, validated)
    page = find_spec_page(fixture, str(validated.spec_id))
    resume_stored(fixture, stored, page, validated)
    if page is None:
        raise ProductBuildError("checkpoint page is missing from the fixture probe")
    if stored.checkpoint_names == _PHASE_TWO_NAMES:
        _require_resumed_databases(fixture, page, stored, kinds)
        return stored
    try:
        database_ids = await _ensure_databases(fixture, page, kinds)
    except ProviderFailure as failure:
        raise_recorded(path, PHASE_SHARED_DATABASES, failure)
    checkpoint = _checkpoint_with_databases(stored, database_ids, moment)
    _write_shared_checkpoint(path, checkpoint)
    return checkpoint


def _read_product_checkpoint(path: Path) -> ProductBuildCheckpoint | None:
    envelope = load_payload(path)
    if envelope.payload is None:
        return None
    payload = envelope.payload
    names = payload.get("checkpoint_names")
    if names == list(_PHASE_ONE_NAMES):
        return parse_checkpoint(payload)
    return _parse_shared_checkpoint(payload)


def parse_shared_databases_checkpoint(payload: dict[object, object]) -> ProductBuildCheckpoint:
    """Parse a checkpoint that records phase 1 and the shared databases."""
    return _parse_shared_checkpoint(payload)


def _parse_shared_checkpoint(payload: dict[object, object]) -> ProductBuildCheckpoint:
    if not exact_keys(payload, CHECKPOINT_KEYS):
        raise ProductBuildError("checkpoint fields are missing or unsupported")
    names = payload["checkpoint_names"]
    if type(names) is not list or names != list(_PHASE_TWO_NAMES):
        raise ProductBuildError("checkpoint must record phase 1 and shared databases")
    references = payload["provider_object_references"]
    if type(references) is not dict:
        raise ProductBuildError("provider references must be an object")
    refs = cast(dict[object, object], references)
    if not exact_keys(refs, PROVIDER_KEYS | {_SHARED_DATABASES_KEY}):
        raise ProductBuildError("provider references are missing or unsupported")
    database_ids = _require_database_ids(refs[_SHARED_DATABASES_KEY])
    phase_one = dict(payload)
    phase_one["checkpoint_names"] = [PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL]
    phase_one["provider_object_references"] = {key: refs[key] for key in PROVIDER_KEYS}
    base = parse_checkpoint(phase_one)
    return replace(
        base,
        checkpoint_names=_PHASE_TWO_NAMES,
        next_phase=PHASE_DASHBOARD_AND_NAVIGATION,
        database_ids=database_ids,
    )


def _require_database_ids(value: object) -> tuple[tuple[str, str], ...]:
    if type(value) is not list or not value:
        raise ProductBuildError("checkpoint shared databases must be a non-empty list")
    rows: list[tuple[str, str]] = []
    for item in cast(list[object], value):
        if type(item) is not dict:
            raise ProductBuildError("checkpoint shared database must be an object")
        entry = cast(dict[object, object], item)
        if not exact_keys(entry, _DATABASE_ENTRY_KEYS):
            raise ProductBuildError("checkpoint shared database fields are missing or unsupported")
        kind = require_token(entry["kind"], "shared database kind")
        database_id = require_token(entry["database_id"], "shared database id")
        rows.append((kind, database_id))
    kinds = tuple(kind for kind, _database_id in rows)
    if kinds not in (PLANNER_SHARED_DATABASES, BUSINESS_SHARED_DATABASES):
        raise ProductBuildError("checkpoint databases do not match a tier")
    if len({database_id for _kind, database_id in rows}) != len(rows):
        raise ProductBuildError("checkpoint shared database id is duplicated")
    return tuple(rows)


def _checkpoint_with_databases(
    stored: ProductBuildCheckpoint,
    database_ids: tuple[tuple[str, str], ...],
    recorded_at: datetime,
) -> ProductBuildCheckpoint:
    return replace(
        stored,
        checkpoint_names=_PHASE_TWO_NAMES,
        next_phase=BUILD_PHASES[len(_PHASE_TWO_NAMES)],
        database_ids=database_ids,
        recorded_at=recorded_at,
    )


def _write_shared_checkpoint(path: Path, checkpoint: ProductBuildCheckpoint) -> None:
    references: dict[str, object] = {
        "design_shell_block_id": checkpoint.shell_block_id,
        "shared_databases": [
            {"database_id": database_id, "kind": kind}
            for kind, database_id in checkpoint.database_ids
        ],
        "top_level_page_id": checkpoint.page_id,
        "workspace_id": checkpoint.workspace_id,
    }
    write_checkpoint(path, checkpoint, references)


def _databases_named(probe: FixtureNotionAdapter, title: str, page_id: str) -> list[NotionDatabase]:
    return [database for database in _page_databases(probe, page_id) if database.title == title]


def marker_property(prop: object) -> bool:
    """True when the property is the sample-marker select column."""
    return (
        type(prop) is NotionDatabaseProperty
        and prop.name == SAMPLE_MARKER
        and prop.type == "select"
        and prop.config == _SAMPLE_MARKER_CONFIG
    )


def _page_databases(probe: FixtureNotionAdapter, page_id: str) -> list[NotionDatabase]:
    return [
        database
        for database in probe.databases.values()
        if type(database) is NotionDatabase
        and database.parent_id == page_id
        and database.parent_type == _DATABASE_PARENT
    ]


def _property_config(options: tuple[str, ...]) -> dict[str, list[str]]:
    if options:
        return {"options": list(options)}
    return {}


def _schema_matches(
    database: NotionDatabase,
    kind: str,
    *,
    formula_suffix: tuple[tuple[str, str], ...] = (),
    formulas_optional: bool = False,
) -> bool:
    schema = build_database_schema(kind)
    properties = database.properties
    if type(properties) is not list:
        return False
    catalogue = len(schema.properties)
    if len(properties) < catalogue or not _catalogue_prefix(properties, schema):
        return False
    if (
        database.parent_type != _DATABASE_PARENT
        or database.icon is not None
        or database.cover is not None
    ):
        return False
    formulas, marker, marker_last = _formula_rows(properties, catalogue)
    if formulas is None or marker is False:
        return False
    if formula_suffix and formulas_optional:
        if len(formulas) > len(formula_suffix):
            return False
        return all(
            _formula_property(found, name, expression)
            for found, (name, expression) in zip(formulas, formula_suffix, strict=False)
        )
    if formula_suffix:
        if marker is None or not marker_last or len(formulas) != len(formula_suffix):
            return False
        return all(
            _formula_property(found, name, expression)
            for found, (name, expression) in zip(formulas, formula_suffix, strict=True)
        )
    return not formulas and marker is None


def _formula_rows(
    properties: list[NotionDatabaseProperty], catalogue: int
) -> tuple[list[NotionDatabaseProperty] | None, bool | None, bool]:
    """Formulas after the catalogue, whether a valid marker is present, and if it is last.

    A return of ``(None, False, ...)`` means the extra columns are not a formula
    list plus at most one sample marker.
    """
    extra = properties[catalogue:]
    markers = [prop for prop in extra if prop.name == SAMPLE_MARKER]
    if len(markers) > 1:
        return None, False, False
    if len(markers) == 1 and not marker_property(markers[0]):
        return None, False, False
    formulas = [prop for prop in extra if prop.name != SAMPLE_MARKER]
    if not markers:
        return formulas, None, True
    return formulas, True, extra[-1] is markers[0]


def _catalogue_prefix(properties: list[NotionDatabaseProperty], schema: DatabaseSchema) -> bool:
    catalogue = len(schema.properties)
    for found, expected in zip(properties[:catalogue], schema.properties, strict=True):
        if type(found) is not NotionDatabaseProperty:
            return False
        if found.name != expected.name or found.type != expected.type:
            return False
        if found.config != _property_config(expected.options):
            return False
    return True


def _repairable_catalogue(database: NotionDatabase, kind: str) -> bool:
    schema = build_database_schema(kind)
    properties = database.properties
    if (
        type(properties) is not list
        or len(properties) >= len(schema.properties)
        or database.parent_type != _DATABASE_PARENT
        or database.icon is not None
        or database.cover is not None
    ):
        return False
    for found, expected in zip(properties, schema.properties, strict=False):
        if type(found) is not NotionDatabaseProperty:
            return False
        if found.name != expected.name or found.type != expected.type:
            return False
        if found.config != _property_config(expected.options):
            return False
    return True


async def _append_catalogue(
    probe: FixtureNotionAdapter, database: NotionDatabase, kind: str
) -> None:
    schema = build_database_schema(kind)
    for prop in schema.properties[len(database.properties) :]:
        await probe.add_property(database.id, prop.name, prop.type, _property_config(prop.options))


def _formula_property(prop: NotionDatabaseProperty, name: str, expression: str) -> bool:
    formula = prop.config.get("formula")
    return (
        prop.name == name
        and prop.type == "formula"
        and type(formula) is NotionFormula
        and formula.name == name
        and formula.expression == expression
        and formula.id == prop.id
    )


async def _create_shared_database(
    probe: FixtureNotionAdapter, page_id: str, kind: str
) -> NotionDatabase:
    schema = build_database_schema(kind)
    database = await probe.create_database(
        title=kind,
        parent_id=page_id,
        parent_type=_DATABASE_PARENT,
    )
    for prop in schema.properties:
        await probe.add_property(
            database.id,
            prop.name,
            prop.type,
            _property_config(prop.options),
        )
    return database


async def _ensure_databases(
    probe: FixtureNotionAdapter,
    page: NotionPage,
    kinds: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    """Adopt a matching database or create the missing one. Never add a second store."""
    allowed = set(kinds)
    children = _page_databases(probe, page.id)
    child_titles = [database.title for database in children]
    if len(child_titles) != len(set(child_titles)):
        raise ProductBuildError("shared database title is duplicated on the page")
    if any(title not in allowed for title in child_titles):
        raise ProductBuildError("page has a database outside the shared set")
    planned: list[tuple[str, NotionDatabase | None]] = []
    for kind in kinds:
        matches = _databases_named(probe, kind, page.id)
        if len(matches) > 1:
            raise ProductBuildError("shared database title is duplicated")
        if not matches:
            planned.append((kind, None))
            continue
        found = matches[0]
        if _schema_matches(found, kind):
            planned.append((kind, found))
            continue
        if _repairable_catalogue(found, kind):
            planned.append((kind, found))
            continue
        raise ProductBuildError("shared database schema cannot be repaired")
    created: list[tuple[str, str]] = []
    for kind, existing in planned:
        if existing is None:
            guard_operation(probe, shared_create_operation(kind))
            existing = await _create_shared_database(probe, page.id, kind)
        elif not _schema_matches(existing, kind):
            await _append_catalogue(probe, existing, kind)
        created.append((kind, existing.id))
    return tuple(created)


def require_checkpoint_databases(
    probe: FixtureNotionAdapter,
    page: NotionPage,
    stored: ProductBuildCheckpoint,
    kinds: tuple[str, ...],
    *,
    extra_database_ids: tuple[str, ...] = (),
    formula_suffixes: Mapping[str, tuple[tuple[str, str], ...]] | None = None,
    formulas_optional: bool = False,
) -> None:
    """Reject a checkpoint whose databases are missing, duplicated, or off-schema."""
    _require_resumed_databases(
        probe,
        page,
        stored,
        kinds,
        extra_database_ids=extra_database_ids,
        formula_suffixes=formula_suffixes or {},
        formulas_optional=formulas_optional,
    )


def _require_resumed_databases(
    probe: FixtureNotionAdapter,
    page: NotionPage,
    stored: ProductBuildCheckpoint,
    kinds: tuple[str, ...],
    *,
    extra_database_ids: tuple[str, ...] = (),
    formula_suffixes: Mapping[str, tuple[tuple[str, str], ...]] | None = None,
    formulas_optional: bool = False,
) -> None:
    if tuple(kind for kind, _database_id in stored.database_ids) != kinds:
        raise ProductBuildError("checkpoint databases do not match the ProductSpec")
    seen: list[str] = []
    for kind, database_id in stored.database_ids:
        database = probe.databases.get(database_id)
        suffix = () if formula_suffixes is None else formula_suffixes.get(kind, ())
        if (
            type(database) is not NotionDatabase
            or database.title != kind
            or database.id != database_id
            or not _schema_matches(
                database,
                kind,
                formula_suffix=suffix,
                formulas_optional=formulas_optional,
            )
            or database.parent_id != page.id
        ):
            raise ProductBuildError("checkpoint shared database is missing")
        matches = _databases_named(probe, kind, page.id)
        if len(matches) != 1 or matches[0].id != database_id:
            raise ProductBuildError("checkpoint shared database is duplicated")
        seen.append(database_id)
    children = _page_databases(probe, page.id)
    child_ids = {database.id for database in children}
    allowed = set(seen) | set(extra_database_ids)
    if child_ids != allowed or len(children) != len(allowed):
        raise ProductBuildError("checkpoint page has an unexpected database")
