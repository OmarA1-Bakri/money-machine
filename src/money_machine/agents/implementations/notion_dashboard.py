"""A07 fixture phase 3: home dashboard and navigation.

Resumes the shared-database checkpoint and stores the home dashboard on the
fixture probe. The next phase is the following build-phase entry. This module
does not run that phase, build the one-row notification database, open a
network connection, or commission an agent.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import cast

from money_machine.agents.implementations.notion_linked_views import (
    create_named_linked_view as _create_linked_view,
)
from money_machine.agents.implementations.notion_linked_views import (
    filter_pairs as _filter_pairs,
)
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    CHECKPOINT_KEYS,
    DESIGN_SHELL_ICON,
    PHASE_DASHBOARD_AND_NAVIGATION,
    PHASE_SHARED_DATABASES,
    PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
    PRODUCT_ID_PROPERTY,
    PROVIDER_KEYS,
    SHELL_BLOCK_PROPERTY,
    ProductBuildCheckpoint,
    ProductBuildError,
    design_shell_content,
    exact_keys,
    find_spec_page,
    require_datetime,
    require_path,
    require_probe,
    require_same_spec,
    require_spec,
    require_token,
)
from money_machine.agents.implementations.notion_shared_databases import (
    parse_shared_databases_checkpoint,
    require_checkpoint_databases,
    shared_database_kinds,
)
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.domain import (
    NotionCalloutBlock,
    NotionLinkedView,
    NotionPage,
    NotionTextBlock,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from money_machine.integrations.notion.relations import (
    CanonicalDatabase,
    CanonicalDatabases,
    LinkedView,
    dashboard_today_view,
    monthly_calendar,
    quick_notes,
)

CALLOUT_ICON = "✦"
_TOP_LEVEL_PARENT = "workspace"
_SHARED_KEY = "shared_databases"
_DASHBOARD_KEY = "dashboard"
_PHASE_TWO = (PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL, PHASE_SHARED_DATABASES)
_PHASE_THREE = (*_PHASE_TWO, PHASE_DASHBOARD_AND_NAVIGATION)
_MASS_PIECES = (
    "cover",
    "header",
    "greeting",
    "hub_navigation",
    "today",
    "month",
    "quick_notes",
    "callout",
    "callout",
)
_BUSINESS_PIECES = (
    "cover",
    "header",
    "greeting",
    "hub_navigation",
    "today",
    "quick_notes",
    "callout",
    "callout",
)
_PIECE_FIELDS = {
    "cover": "value",
    "header": "value",
    "greeting": "block_id",
    "hub_navigation": "block_id",
    "today": "view_id",
    "month": "view_id",
    "quick_notes": "view_id",
    "callout": "block_id",
}
_VALUE_KINDS = frozenset({"cover", "header"})


def palette_cover(spec: ProductSpec) -> str:
    """Fixture-local cover derived from the first palette token."""
    token = spec.palette_tokens[0]
    return f"fixture://palette/{token.name}/{token.hex}"


def palette_header(spec: ProductSpec) -> str:
    """Header mark derived from the first palette token."""
    token = spec.palette_tokens[0]
    return f"header:{token.name}:{token.hex}"


def greeting_content(spec: ProductSpec) -> str:
    """Greeting names this product's identity. It is not a shared filler line."""
    return f"Hello, {spec.identity}. {spec.title} is ready."


def navigation_content(spec: ProductSpec) -> str:
    """Hub names in spec order. This does not create the hub pages."""
    return "\n".join(("navigate", *(hub.name for hub in spec.hubs)))


def identity_callout(spec: ProductSpec) -> str:
    """Identity callout. The wording follows this spec, not a second product."""
    return f"{spec.identity} callout: {spec.buyer_problem}"


def flagship_callout(spec: ProductSpec) -> str:
    """Flagship callout for this identity."""
    return f"{spec.identity} flagship: {spec.flagship_feature}"


async def build_dashboard_and_navigation(
    spec: object,
    probe: object,
    checkpoint_path: object,
    *,
    recorded_at: object,
) -> ProductBuildCheckpoint:
    """Create the home dashboard, or resume when that phase is already stored."""
    validated = require_spec(spec)
    fixture = require_probe(probe)
    path = require_path(checkpoint_path)
    moment = require_datetime(recorded_at)
    _reject_line_breaks(validated)
    stored = _load_checkpoint(path)
    require_same_spec(stored, validated)
    _require_one_page(fixture)
    page = _require_home_page(fixture, stored, validated)
    kinds = shared_database_kinds(validated)
    require_checkpoint_databases(fixture, page, stored, kinds)
    if stored.checkpoint_names == _PHASE_THREE:
        _require_resumed_dashboard(fixture, page, stored, validated)
        return stored
    pieces = await _ensure_dashboard(fixture, page, stored, validated)
    checkpoint = _checkpoint_with_dashboard(stored, pieces, moment)
    _write_dashboard_checkpoint(path, checkpoint)
    return checkpoint


def _reject_line_breaks(spec: ProductSpec) -> None:
    fields = [
        spec.identity,
        spec.title,
        spec.buyer_problem,
        spec.flagship_feature,
        spec.palette_name,
    ]
    fields.extend(token.name for token in spec.palette_tokens)
    fields.extend(hub.name for hub in spec.hubs)
    if any("\n" in field or "\r" in field for field in fields):
        raise ProductBuildError("dashboard fields must be single lines")


def _load_checkpoint(path: Path) -> ProductBuildCheckpoint:
    if not path.exists():
        raise ProductBuildError("dashboard requires the shared databases checkpoint")
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
    if names == list(_PHASE_TWO):
        return parse_shared_databases_checkpoint(payload)
    if names == list(_PHASE_THREE):
        return _parse_dashboard_checkpoint(payload)
    raise ProductBuildError("dashboard requires the shared databases checkpoint")


def parse_dashboard_checkpoint(payload: dict[object, object]) -> ProductBuildCheckpoint:
    """Parse a checkpoint that records the home dashboard."""
    return _parse_dashboard_checkpoint(payload)


def _parse_dashboard_checkpoint(payload: dict[object, object]) -> ProductBuildCheckpoint:
    if not exact_keys(payload, CHECKPOINT_KEYS):
        raise ProductBuildError("checkpoint fields are missing or unsupported")
    names = payload["checkpoint_names"]
    if type(names) is not list or names != list(_PHASE_THREE):
        raise ProductBuildError("checkpoint must record the dashboard phase")
    references = payload["provider_object_references"]
    if type(references) is not dict:
        raise ProductBuildError("provider references must be an object")
    refs = cast(dict[object, object], references)
    allowed = PROVIDER_KEYS | {_SHARED_KEY, _DASHBOARD_KEY}
    if not exact_keys(refs, allowed):
        raise ProductBuildError("provider references are missing or unsupported")
    pieces = _require_pieces(refs[_DASHBOARD_KEY])
    phase_two = dict(payload)
    phase_two["checkpoint_names"] = list(_PHASE_TWO)
    phase_two["provider_object_references"] = {
        key: refs[key] for key in (*PROVIDER_KEYS, _SHARED_KEY)
    }
    base = parse_shared_databases_checkpoint(phase_two)
    return _checkpoint_with_dashboard(base, pieces, base.recorded_at)


def _require_pieces(value: object) -> tuple[tuple[str, str], ...]:
    if type(value) is not list or not value:
        raise ProductBuildError("checkpoint dashboard must be a non-empty list")
    rows: list[tuple[str, str]] = []
    for item in cast(list[object], value):
        if type(item) is not dict:
            raise ProductBuildError("checkpoint dashboard piece must be an object")
        entry = cast(dict[object, object], item)
        kind = entry.get("kind")
        if type(kind) is not str or kind not in _PIECE_FIELDS:
            raise ProductBuildError("checkpoint dashboard piece kind is unsupported")
        field = _PIECE_FIELDS[kind]
        if not exact_keys(entry, frozenset({"kind", field})):
            raise ProductBuildError("checkpoint dashboard piece fields are missing or unsupported")
        rows.append((kind, require_token(entry[field], "dashboard piece")))
    kinds = tuple(kind for kind, _value in rows)
    if kinds not in (_MASS_PIECES, _BUSINESS_PIECES):
        raise ProductBuildError("checkpoint dashboard does not match a tier")
    identifiers = [token for kind, token in rows if kind not in _VALUE_KINDS]
    if len(identifiers) != len(set(identifiers)):
        raise ProductBuildError("checkpoint dashboard piece id is duplicated")
    return tuple(rows)


def _checkpoint_with_dashboard(
    stored: ProductBuildCheckpoint,
    pieces: tuple[tuple[str, str], ...],
    recorded_at: datetime,
) -> ProductBuildCheckpoint:
    return replace(
        stored,
        checkpoint_names=_PHASE_THREE,
        next_phase=BUILD_PHASES[len(_PHASE_THREE)],
        dashboard_pieces=pieces,
        recorded_at=recorded_at,
    )


def _one_workspace(probe: FixtureNotionAdapter) -> str:
    workspaces = list(probe.workspaces.values())
    if len(workspaces) != 1:
        raise ProductBuildError("fixture probe must have exactly one workspace")
    workspace_id = workspaces[0].id
    if type(workspace_id) is not str or workspace_id.strip() != workspace_id or workspace_id == "":
        raise ProductBuildError("fixture workspace id is invalid")
    return workspace_id


def _require_one_page(probe: FixtureNotionAdapter) -> None:
    if len(probe.pages) > 1:
        raise ProductBuildError("dashboard page is unexpected")


def require_home_page(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> NotionPage:
    """Return the saved top-level page, or raise when it does not match."""
    return _require_home_page(probe, stored, spec)


def _require_home_page(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> NotionPage:
    if stored.workspace_id != _one_workspace(probe):
        raise ProductBuildError("checkpoint workspace does not match the fixture probe")
    page = find_spec_page(probe, str(spec.spec_id))
    if page is None or page.id != stored.page_id:
        raise ProductBuildError("checkpoint page is missing from the fixture probe")
    if (
        page.parent_type != _TOP_LEVEL_PARENT
        or page.parent_id != stored.workspace_id
        or page.parent_id == ""
    ):
        raise ProductBuildError("checkpoint page is not the stored top-level page")
    if page.title != spec.title:
        raise ProductBuildError("checkpoint page title does not match the ProductSpec")
    product_id = page.properties.get(PRODUCT_ID_PROPERTY)
    if type(product_id) is not str or product_id != str(spec.product_id):
        raise ProductBuildError("checkpoint page product id does not match the ProductSpec")
    if page.is_published is not False:
        raise ProductBuildError("checkpoint page must stay unpublished")
    shell = probe.blocks.get(stored.shell_block_id)
    if type(shell) is not NotionCalloutBlock or shell.parent_id != page.id:
        raise ProductBuildError("checkpoint design shell is missing")
    if shell.content != design_shell_content(spec) or shell.icon != DESIGN_SHELL_ICON:
        raise ProductBuildError("checkpoint design shell does not match the ProductSpec")
    marked = page.properties.get(SHELL_BLOCK_PROPERTY)
    if type(marked) is not str or marked != stored.shell_block_id:
        raise ProductBuildError("checkpoint design shell id does not match the page")
    return page


def _piece_kinds(database_kinds: tuple[str, ...]) -> tuple[str, ...]:
    if "Events" in database_kinds:
        return _MASS_PIECES
    return _BUSINESS_PIECES


def _canonical(kinds: tuple[str, ...]) -> CanonicalDatabases:
    return CanonicalDatabases(
        data_types=kinds,
        by_type={kind: CanonicalDatabase(data_type=kind) for kind in kinds},
    )


def _linked_views(kinds: tuple[str, ...]) -> tuple[tuple[str, LinkedView], ...]:
    canonical = _canonical(kinds)
    views: list[tuple[str, LinkedView]] = [("today", dashboard_today_view(canonical))]
    if "Events" in kinds:
        views.append(("month", monthly_calendar(canonical)))
    views.append(("quick_notes", quick_notes(canonical)))
    return tuple(views)


def _page_blocks(
    probe: FixtureNotionAdapter, page_id: str
) -> list[NotionTextBlock | NotionCalloutBlock]:
    return [block for block in probe.blocks.values() if block.parent_id == page_id]


def _text_matches(
    blocks: list[NotionTextBlock | NotionCalloutBlock], content: str
) -> list[NotionTextBlock]:
    return [
        block for block in blocks if type(block) is NotionTextBlock and block.content == content
    ]


def _callout_matches(
    blocks: list[NotionTextBlock | NotionCalloutBlock], content: str, shell_id: str
) -> list[NotionCalloutBlock]:
    return [
        block
        for block in blocks
        if type(block) is NotionCalloutBlock
        and block.id != shell_id
        and block.content == content
        and block.icon == CALLOUT_ICON
    ]


def _classify_blocks(
    probe: FixtureNotionAdapter, page: NotionPage, spec: ProductSpec, shell_id: str
) -> tuple[
    NotionTextBlock | None,
    NotionTextBlock | None,
    NotionCalloutBlock | None,
    NotionCalloutBlock | None,
]:
    if any(block.parent_id != page.id for block in probe.blocks.values()):
        raise ProductBuildError("dashboard block is unexpected")
    blocks = _page_blocks(probe, page.id)
    greeting = _text_matches(blocks, greeting_content(spec))
    navigation = _text_matches(blocks, navigation_content(spec))
    identity = _callout_matches(blocks, identity_callout(spec), shell_id)
    flagship = _callout_matches(blocks, flagship_callout(spec), shell_id)
    if len(greeting) > 1 or len(navigation) > 1 or len(identity) > 1 or len(flagship) > 1:
        raise ProductBuildError("dashboard block is duplicated")
    known = {shell_id}
    for group in (greeting, navigation, identity, flagship):
        known.update(block.id for block in group)
    if any(block.id not in known for block in blocks):
        raise ProductBuildError("dashboard block is unexpected")
    return (
        greeting[0] if greeting else None,
        navigation[0] if navigation else None,
        identity[0] if identity else None,
        flagship[0] if flagship else None,
    )


def _view_matches(
    probe: FixtureNotionAdapter, page_id: str, source_id: str, view: LinkedView
) -> list[NotionLinkedView]:
    filters = _filter_pairs(view)
    return [
        item
        for item in probe.linked_views.values()
        if type(item) is NotionLinkedView
        and item.parent_page_id == page_id
        and item.source_database_id == source_id
        and item.view_type == view.view_type
        and item.name == view.name
        and item.filters == filters
    ]


def _classify_views(
    probe: FixtureNotionAdapter,
    page: NotionPage,
    database_ids: dict[str, str],
    linked: tuple[tuple[str, LinkedView], ...],
) -> dict[str, NotionLinkedView | None]:
    matched: dict[str, NotionLinkedView | None] = {}
    used: set[str] = set()
    for kind, view in linked:
        found = _view_matches(probe, page.id, database_ids[view.data_type], view)
        if len(found) > 1:
            raise ProductBuildError("dashboard view is duplicated")
        matched[kind] = found[0] if found else None
        used.update(item.id for item in found)
    if any(
        type(item) is not NotionLinkedView or item.id not in used
        for item in probe.linked_views.values()
    ):
        raise ProductBuildError("dashboard view is unexpected")
    if probe.views:
        raise ProductBuildError("dashboard view is unexpected")
    return matched


def _existing_mark(current: str | None, expected: str, label: str) -> str | None:
    if current is None:
        return None
    if current != expected:
        raise ProductBuildError(f"page {label} does not match the palette")
    return current


async def _ensure_dashboard(
    probe: FixtureNotionAdapter,
    page: NotionPage,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> tuple[tuple[str, str], ...]:
    kinds = tuple(kind for kind, _database_id in stored.database_ids)
    database_ids = dict(stored.database_ids)
    greeting, navigation, identity, flagship = _classify_blocks(
        probe, page, spec, stored.shell_block_id
    )
    views = _classify_views(probe, page, database_ids, _linked_views(kinds))
    if _existing_mark(page.cover, palette_cover(spec), "cover") is None:
        await probe.set_cover(page.id, palette_cover(spec))
    if _existing_mark(page.icon, palette_header(spec), "header") is None:
        await probe.set_icon(page.id, palette_header(spec))
    if greeting is None:
        greeting = await probe.add_text_block(page.id, greeting_content(spec))
    if navigation is None:
        navigation = await probe.add_text_block(page.id, navigation_content(spec))
    if identity is None:
        identity = await probe.add_callout_block(page.id, identity_callout(spec), icon=CALLOUT_ICON)
    if flagship is None:
        flagship = await probe.add_callout_block(page.id, flagship_callout(spec), icon=CALLOUT_ICON)
    created = dict(views)
    for kind, view in _linked_views(kinds):
        if created[kind] is None:
            created[kind] = await _create_linked_view(
                probe, page.id, database_ids[view.data_type], view
            )
    return _pieces(spec, kinds, greeting, navigation, identity, flagship, created)


def _pieces(
    spec: ProductSpec,
    kinds: tuple[str, ...],
    greeting: NotionTextBlock,
    navigation: NotionTextBlock,
    identity: NotionCalloutBlock,
    flagship: NotionCalloutBlock,
    views: dict[str, NotionLinkedView | None],
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = [
        ("cover", palette_cover(spec)),
        ("header", palette_header(spec)),
        ("greeting", greeting.id),
        ("hub_navigation", navigation.id),
        ("today", _view_id(views, "today")),
    ]
    if "Events" in kinds:
        rows.append(("month", _view_id(views, "month")))
    rows.extend(
        (
            ("quick_notes", _view_id(views, "quick_notes")),
            ("callout", identity.id),
            ("callout", flagship.id),
        )
    )
    return tuple(rows)


def _view_id(views: dict[str, NotionLinkedView | None], kind: str) -> str:
    view = views[kind]
    if view is None:
        raise ProductBuildError("dashboard piece is missing")
    return view.id


def require_dashboard_pieces(
    probe: FixtureNotionAdapter,
    page: NotionPage,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> None:
    """Check each saved dashboard piece. Other pages are left for the caller."""
    kinds = tuple(kind for kind, _database_id in stored.database_ids)
    if tuple(kind for kind, _value in stored.dashboard_pieces) != _piece_kinds(kinds):
        raise ProductBuildError("checkpoint dashboard does not match the ProductSpec")
    by_kind = _pieces_by_kind(stored)
    if page.cover != palette_cover(spec) or by_kind["cover"] != [palette_cover(spec)]:
        raise ProductBuildError("dashboard piece is missing")
    if page.icon != palette_header(spec) or by_kind["header"] != [palette_header(spec)]:
        raise ProductBuildError("dashboard piece is missing")
    _require_text(probe, page, by_kind["greeting"][0], greeting_content(spec))
    _require_text(probe, page, by_kind["hub_navigation"][0], navigation_content(spec))
    _require_callout(probe, page, by_kind["callout"][0], identity_callout(spec))
    _require_callout(probe, page, by_kind["callout"][1], flagship_callout(spec))
    database_ids = dict(stored.database_ids)
    for kind, view in _linked_views(kinds):
        _require_view(probe, page, by_kind[kind][0], database_ids[view.data_type], view)


def dashboard_provider_references(checkpoint: ProductBuildCheckpoint) -> dict[str, object]:
    """Provider ids recorded for the home dashboard checkpoint."""
    return {
        _DASHBOARD_KEY: [
            {"kind": kind, _PIECE_FIELDS[kind]: value}
            for kind, value in checkpoint.dashboard_pieces
        ],
        "design_shell_block_id": checkpoint.shell_block_id,
        _SHARED_KEY: [
            {"database_id": database_id, "kind": kind}
            for kind, database_id in checkpoint.database_ids
        ],
        "top_level_page_id": checkpoint.page_id,
        "workspace_id": checkpoint.workspace_id,
    }


def _pieces_by_kind(stored: ProductBuildCheckpoint) -> dict[str, list[str]]:
    by_kind: dict[str, list[str]] = {}
    for kind, value in stored.dashboard_pieces:
        by_kind.setdefault(kind, []).append(value)
    return by_kind


def _require_resumed_dashboard(
    probe: FixtureNotionAdapter,
    page: NotionPage,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> None:
    require_dashboard_pieces(probe, page, stored, spec)
    by_kind = _pieces_by_kind(stored)
    expected_blocks = {
        stored.shell_block_id,
        by_kind["greeting"][0],
        by_kind["hub_navigation"][0],
        *by_kind["callout"],
    }
    if any(block.parent_id != page.id for block in probe.blocks.values()):
        raise ProductBuildError("dashboard block is unexpected")
    actual_blocks = _page_blocks(probe, page.id)
    if {block.id for block in actual_blocks} != expected_blocks or len(actual_blocks) != len(
        expected_blocks
    ):
        raise ProductBuildError("dashboard block is unexpected")
    expected_views = {by_kind["today"][0], by_kind["quick_notes"][0]}
    if "month" in by_kind:
        expected_views.add(by_kind["month"][0])
    actual_views = [item for item in probe.linked_views.values() if type(item) is NotionLinkedView]
    if {item.id for item in actual_views} != expected_views or len(actual_views) != len(
        expected_views
    ):
        raise ProductBuildError("dashboard view is unexpected")
    if probe.views:
        raise ProductBuildError("dashboard view is unexpected")


def _require_text(
    probe: FixtureNotionAdapter, page: NotionPage, block_id: str, content: str
) -> None:
    block = probe.blocks.get(block_id)
    if type(block) is not NotionTextBlock or block.parent_id != page.id or block.content != content:
        raise ProductBuildError("dashboard piece is missing")


def _require_callout(
    probe: FixtureNotionAdapter, page: NotionPage, block_id: str, content: str
) -> None:
    block = probe.blocks.get(block_id)
    if (
        type(block) is not NotionCalloutBlock
        or block.parent_id != page.id
        or block.content != content
        or block.icon != CALLOUT_ICON
    ):
        raise ProductBuildError("dashboard piece is missing")


def _require_view(
    probe: FixtureNotionAdapter,
    page: NotionPage,
    view_id: str,
    source_id: str,
    view: LinkedView,
) -> None:
    found = probe.linked_views.get(view_id)
    if (
        type(found) is not NotionLinkedView
        or found.parent_page_id != page.id
        or found.source_database_id != source_id
        or found.view_type != view.view_type
        or found.name != view.name
        or found.filters != _filter_pairs(view)
    ):
        raise ProductBuildError("dashboard piece is missing")


def _write_dashboard_checkpoint(path: Path, checkpoint: ProductBuildCheckpoint) -> None:
    payload = {
        "build_kind": checkpoint.build_kind,
        "build_version": checkpoint.build_version,
        "checkpoint_names": list(checkpoint.checkpoint_names),
        "palette_name": checkpoint.palette_name,
        "palette_tokens": [list(token) for token in checkpoint.palette_tokens],
        "product_id": checkpoint.product_id,
        "provider_object_references": dashboard_provider_references(checkpoint),
        "recorded_at": checkpoint.recorded_at.isoformat(),
        "spec_id": checkpoint.spec_id,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="ascii")
    os.replace(temporary, path)
