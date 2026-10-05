"""A07 fixture phase 2: canonical shared databases.

Resumes the phase-1 checkpoint and stores the playbook database set on the
fixture probe. The next phase name is dashboard_and_navigation. This module
does not run that phase, open a network connection, or commission an agent.
"""

from __future__ import annotations

import json
import os
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
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.domain import (
    NotionDatabase,
    NotionDatabaseProperty,
    NotionPage,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from money_machine.integrations.notion.schema_builder import build_database_schema

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
    database_ids = await _ensure_databases(fixture, page, kinds)
    checkpoint = _checkpoint_with_databases(stored, database_ids, moment)
    _write_shared_checkpoint(path, checkpoint)
    return checkpoint


def _read_product_checkpoint(path: Path) -> ProductBuildCheckpoint | None:
    if not path.exists():
        return None
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
    if names == list(_PHASE_ONE_NAMES):
        return parse_checkpoint(decoded)
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
    payload = {
        "build_kind": checkpoint.build_kind,
        "build_version": checkpoint.build_version,
        "checkpoint_names": list(checkpoint.checkpoint_names),
        "palette_name": checkpoint.palette_name,
        "palette_tokens": [list(token) for token in checkpoint.palette_tokens],
        "product_id": checkpoint.product_id,
        "provider_object_references": {
            "design_shell_block_id": checkpoint.shell_block_id,
            "shared_databases": [
                {"database_id": database_id, "kind": kind}
                for kind, database_id in checkpoint.database_ids
            ],
            "top_level_page_id": checkpoint.page_id,
            "workspace_id": checkpoint.workspace_id,
        },
        "recorded_at": checkpoint.recorded_at.isoformat(),
        "spec_id": checkpoint.spec_id,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="ascii")
    os.replace(temporary, path)


def _databases_named(probe: FixtureNotionAdapter, title: str) -> list[NotionDatabase]:
    return [
        database
        for database in probe.databases.values()
        if type(database) is NotionDatabase and database.title == title
    ]


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


def _schema_matches(database: NotionDatabase, kind: str) -> bool:
    schema = build_database_schema(kind)
    properties = database.properties
    if type(properties) is not list or len(properties) != len(schema.properties):
        return False
    for found, expected in zip(properties, schema.properties, strict=True):
        if type(found) is not NotionDatabaseProperty:
            return False
        if found.name != expected.name or found.type != expected.type:
            return False
        if found.config != _property_config(expected.options):
            return False
    return (
        database.parent_type == _DATABASE_PARENT
        and database.icon is None
        and database.cover is None
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
        matches = _databases_named(probe, kind)
        if len(matches) > 1:
            raise ProductBuildError("shared database title is duplicated")
        if not matches:
            planned.append((kind, None))
            continue
        found = matches[0]
        if found.parent_id != page.id or not _schema_matches(found, kind):
            raise ProductBuildError("existing shared database does not match the schema")
        planned.append((kind, found))
    created: list[tuple[str, str]] = []
    for kind, existing in planned:
        if existing is None:
            existing = await _create_shared_database(probe, page.id, kind)
        created.append((kind, existing.id))
    return tuple(created)


def _require_resumed_databases(
    probe: FixtureNotionAdapter,
    page: NotionPage,
    stored: ProductBuildCheckpoint,
    kinds: tuple[str, ...],
) -> None:
    if tuple(kind for kind, _database_id in stored.database_ids) != kinds:
        raise ProductBuildError("checkpoint databases do not match the ProductSpec")
    seen: list[str] = []
    for kind, database_id in stored.database_ids:
        database = probe.databases.get(database_id)
        if (
            type(database) is not NotionDatabase
            or database.title != kind
            or database.id != database_id
            or not _schema_matches(database, kind)
            or database.parent_id != page.id
        ):
            raise ProductBuildError("checkpoint shared database is missing")
        matches = _databases_named(probe, kind)
        if len(matches) != 1 or matches[0].id != database_id:
            raise ProductBuildError("checkpoint shared database is duplicated")
        seen.append(database_id)
    children = _page_databases(probe, page.id)
    child_ids = {database.id for database in children}
    if child_ids != set(seen) or len(children) != len(seen):
        raise ProductBuildError("checkpoint page has an unexpected database")
