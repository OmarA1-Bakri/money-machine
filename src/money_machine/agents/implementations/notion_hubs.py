"""A07 fixture phase 4: identity-specific hubs.

Resumes the home-dashboard checkpoint and stores one hub page per ProductSpec
hub on the fixture probe. The next phase is the following build-phase entry.
This module does not run that phase, open a network connection, or commission
an agent.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import cast

from money_machine.agents.implementations.notion_dashboard import (
    dashboard_provider_references,
    parse_dashboard_checkpoint,
    require_dashboard_pieces,
    require_home_page,
)
from money_machine.agents.implementations.notion_linked_views import (
    create_named_linked_view as _create_linked_view,
)
from money_machine.agents.implementations.notion_linked_views import (
    filter_pairs as _filter_pairs,
)
from money_machine.agents.implementations.notion_linked_views import (
    view_matches as _view_matches,
)
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    CHECKPOINT_KEYS,
    PHASE_DASHBOARD_AND_NAVIGATION,
    PHASE_SHARED_DATABASES,
    PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
    PROVIDER_KEYS,
    IdentityHubRecord,
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
from money_machine.agents.implementations.notion_progress import (
    OP_HUBS_CREATE,
    ProviderFailure,
    guard_operation,
    load_payload,
    raise_recorded,
)
from money_machine.agents.implementations.notion_progress_record import write_checkpoint
from money_machine.agents.implementations.notion_shared_databases import (
    require_checkpoint_databases,
    shared_database_kinds,
)
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.domain import NotionLinkedView, NotionPage, NotionTextBlock
from money_machine.integrations.notion.errors import SchemaBuilderError
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from money_machine.integrations.notion.formulas import MAX_NAME_LENGTH
from money_machine.integrations.notion.relations import (
    LinkedView,
    build_canonical_databases,
    build_filter,
    build_linked_view,
)

_TOP_LEVEL_PARENT = "workspace"
_CHILD_PARENT = "page_id"
_SHARED_KEY = "shared_databases"
_DASHBOARD_KEY = "dashboard"
_HUBS_KEY = "identity_hubs"
_SECTION_ROLES = ("purpose", "practice", "buyer")
_PHASE_THREE = (
    PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
    PHASE_SHARED_DATABASES,
    PHASE_DASHBOARD_AND_NAVIGATION,
)
_PHASE_FOUR = (*_PHASE_THREE, "identity_specific_hubs")
_BLOCK_KINDS = frozenset({"greeting", "hub_navigation", "callout"})
_VIEW_KINDS = frozenset({"today", "month", "quick_notes"})
_HUB_KEYS = frozenset({"name", "navigation_block_id", "page_id", "sections", "views"})
_SECTION_KEYS = frozenset({"block_id", "role"})
_VIEW_KEYS = frozenset({"slug", "view_id"})
_PHASE_THREE_REFERENCE_KEYS = PROVIDER_KEYS | {_SHARED_KEY, _DASHBOARD_KEY}
_PHASE_FOUR_REFERENCE_KEYS = _PHASE_THREE_REFERENCE_KEYS | {_HUBS_KEY}


@dataclass(frozen=True, slots=True)
class _ViewRecipe:
    data_type: str
    view_type: str
    slug: str
    filters: tuple[tuple[str, str, str, str], ...]


_RECIPES: tuple[_ViewRecipe, ...] = (
    _ViewRecipe("Tasks", "table", "open tasks", (("status", "Status", "equals", "Open"),)),
    _ViewRecipe("Tasks", "calendar", "due today", (("date", "Due", "equals", "today"),)),
    _ViewRecipe("Events", "calendar", "events today", (("date", "Date", "equals", "today"),)),
    _ViewRecipe("Habits", "table", "habits today", (("date", "Date", "equals", "today"),)),
    _ViewRecipe("Finance", "table", "money today", (("date", "Date", "equals", "today"),)),
    _ViewRecipe("Meals", "table", "meals today", (("date", "Day", "equals", "today"),)),
    _ViewRecipe("Notes", "table", "notes", ()),
    _ViewRecipe(
        "Projects", "board", "active projects", (("status", "Status", "equals", "Active"),)
    ),
    _ViewRecipe("Invoices", "table", "draft invoices", (("status", "Status", "equals", "Draft"),)),
    _ViewRecipe("Clients", "table", "clients", ()),
    _ViewRecipe("Content", "table", "content", ()),
)
_KNOWN_SLUGS = frozenset(recipe.slug for recipe in _RECIPES)


@dataclass(frozen=True, slots=True)
class _PlannedView:
    slug: str
    view: LinkedView


@dataclass(frozen=True, slots=True)
class _PlannedHub:
    name: str
    views: tuple[_PlannedView, _PlannedView]


@dataclass(frozen=True, slots=True)
class _FoundHub:
    page: NotionPage | None
    sections: tuple[NotionTextBlock | None, NotionTextBlock | None, NotionTextBlock | None]
    navigation: NotionTextBlock | None
    views: tuple[NotionLinkedView | None, NotionLinkedView | None]


def section_content(spec: ProductSpec, hub_name: str, role: str) -> str:
    """Identity-specific section text. The role label keeps sections distinct."""
    hub = next(item for item in spec.hubs if item.name == hub_name)
    details = {
        "purpose": hub.description,
        "practice": spec.flagship_feature,
        "buyer": spec.buyer_problem,
    }
    if role not in details:
        raise ProductBuildError("hub section role is unsupported")
    return f"{spec.identity} / {hub_name} {role}: {details[role]}"


def navigation_content(spec: ProductSpec, hub_name: str) -> str:
    """Navigation back to this product's dashboard title."""
    return f"{spec.identity} / {hub_name} returns to {spec.title}"


def linked_view_name(spec: ProductSpec, hub_name: str, slug: str) -> str:
    """View name for this identity and hub. It is not a shared filler label.

    A name longer than Notion's 64-character cap is shortened. The slug and a
    hash of the full name stay on the end so two hubs that differ past the cut
    do not collide.
    """
    full = f"{spec.identity} {hub_name} {slug}"
    if len(full) <= MAX_NAME_LENGTH:
        return full
    token = hashlib.sha256(full.encode("utf-8")).hexdigest()[:8]
    suffix = f"{slug} {token}"
    if len(suffix) > MAX_NAME_LENGTH:
        keep = MAX_NAME_LENGTH - 8 - 1
        suffix = f"{slug[:keep].rstrip()} {token}"
    room = MAX_NAME_LENGTH - len(suffix) - 1
    if room < 1:
        return suffix
    head = f"{spec.identity} {hub_name}"[:room].rstrip()
    if head == "":
        return suffix
    return f"{head} {suffix}"


async def build_identity_specific_hubs(
    spec: object,
    probe: object,
    checkpoint_path: object,
    *,
    recorded_at: object,
) -> ProductBuildCheckpoint:
    """Create the identity hubs, or resume when that phase is already stored."""
    validated = require_spec(spec)
    fixture = require_probe(probe)
    path = require_path(checkpoint_path)
    moment = require_datetime(recorded_at)
    _reject_hub_fields(validated)
    stored = _load_checkpoint(path)
    require_same_spec(stored, validated)
    kinds = shared_database_kinds(validated)
    page = _require_prior_dashboard(fixture, stored, validated, kinds)
    if stored.checkpoint_names == _PHASE_FOUR:
        _require_saved_hubs(fixture, page, stored, validated, kinds)
        return stored
    try:
        records = await _ensure_hubs(fixture, page, stored, validated, kinds)
    except ProviderFailure as failure:
        raise_recorded(path, _PHASE_FOUR[-1], failure)
    checkpoint = _checkpoint_with_hubs(stored, records, moment)
    _write_hubs_checkpoint(path, checkpoint)
    return checkpoint


def _reject_hub_fields(spec: ProductSpec) -> None:
    if len(spec.hubs) < 6 or len(spec.hubs) > 8:
        raise ProductBuildError("hubs must be six to eight")
    fields = [spec.identity, spec.title, spec.buyer_problem, spec.flagship_feature]
    fields.extend(hub.name for hub in spec.hubs)
    fields.extend(hub.description for hub in spec.hubs)
    if any("\n" in field or "\r" in field for field in fields):
        raise ProductBuildError("hub fields must be single lines")
    if any(len(hub.name) > MAX_NAME_LENGTH for hub in spec.hubs):
        raise ProductBuildError("hub name must be at most 64 characters")
    names = [hub.name for hub in spec.hubs]
    if len(names) != len(set(names)):
        raise ProductBuildError("hub names must be unique")


def _recipes_for(kinds: tuple[str, ...]) -> tuple[_ViewRecipe, ...]:
    return tuple(recipe for recipe in _RECIPES if recipe.data_type in kinds)


def _pair(index: int, available: tuple[_ViewRecipe, ...]) -> tuple[_ViewRecipe, _ViewRecipe]:
    filtered = tuple(recipe for recipe in available if recipe.filters)
    if len(filtered) < 1:
        raise ProductBuildError("tier cannot fill a hub view")
    primary = filtered[index % len(filtered)]
    rest = tuple(recipe for recipe in available if recipe != primary)
    if len(rest) < 1:
        raise ProductBuildError("tier cannot fill a hub view")
    return primary, rest[index % len(rest)]


def _plan(spec: ProductSpec, kinds: tuple[str, ...]) -> tuple[_PlannedHub, ...]:
    available = _recipes_for(kinds)
    canonical = build_canonical_databases(kinds)
    planned: list[_PlannedHub] = []
    for index, hub in enumerate(spec.hubs):
        views: list[_PlannedView] = []
        for recipe in _pair(index, available):
            filters = tuple(
                build_filter(dimension, prop, condition, value)
                for dimension, prop, condition, value in recipe.filters
            )
            try:
                view = build_linked_view(
                    hub.name,
                    recipe.data_type,
                    recipe.view_type,
                    linked_view_name(spec, hub.name, recipe.slug),
                    filters,
                    canonical,
                )
            except SchemaBuilderError as error:
                raise ProductBuildError("hub view is not valid") from error
            views.append(_PlannedView(recipe.slug, view))
        first, second = views
        planned.append(_PlannedHub(hub.name, (first, second)))
    return tuple(planned)


def _load_checkpoint(path: Path) -> ProductBuildCheckpoint:
    envelope = load_payload(path)
    if envelope.payload is None:
        raise ProductBuildError("identity hubs require the dashboard checkpoint")
    payload = envelope.payload
    names = payload.get("checkpoint_names")
    if names == list(_PHASE_THREE):
        return parse_dashboard_checkpoint(payload)
    if names == list(_PHASE_FOUR):
        return _parse_hubs_checkpoint(payload)
    raise ProductBuildError("identity hubs require the dashboard checkpoint")


def parse_identity_hubs_checkpoint(payload: dict[object, object]) -> ProductBuildCheckpoint:
    """Parse a checkpoint that records the identity hubs."""
    return _parse_hubs_checkpoint(payload)


def _parse_hubs_checkpoint(payload: dict[object, object]) -> ProductBuildCheckpoint:
    if not exact_keys(payload, CHECKPOINT_KEYS):
        raise ProductBuildError("checkpoint fields are missing or unsupported")
    names = payload["checkpoint_names"]
    if type(names) is not list or names != list(_PHASE_FOUR):
        raise ProductBuildError("checkpoint must record the identity hubs")
    references = payload["provider_object_references"]
    if type(references) is not dict:
        raise ProductBuildError("provider references must be an object")
    refs = cast(dict[object, object], references)
    if not exact_keys(refs, _PHASE_FOUR_REFERENCE_KEYS):
        raise ProductBuildError("provider references are missing or unsupported")
    hubs = _require_hub_records(refs[_HUBS_KEY])
    phase_three = dict(payload)
    phase_three["checkpoint_names"] = list(_PHASE_THREE)
    phase_three["provider_object_references"] = {
        key: refs[key] for key in _PHASE_THREE_REFERENCE_KEYS
    }
    base = parse_dashboard_checkpoint(phase_three)
    return replace(
        base,
        checkpoint_names=_PHASE_FOUR,
        next_phase=BUILD_PHASES[len(_PHASE_FOUR)],
        identity_hubs=hubs,
    )


def _require_hub_records(value: object) -> tuple[IdentityHubRecord, ...]:
    if type(value) is not list or not value:
        raise ProductBuildError("checkpoint hubs must be a non-empty list")
    records = tuple(_require_hub_record(item) for item in cast(list[object], value))
    if len(records) < 6 or len(records) > 8:
        raise ProductBuildError("checkpoint hubs must be six to eight")
    names = [record.name for record in records]
    if len(names) != len(set(names)):
        raise ProductBuildError("checkpoint hub name is duplicated")
    identifiers = [record.page_id for record in records]
    identifiers.extend(record.navigation_block_id for record in records)
    for record in records:
        identifiers.extend(block_id for _role, block_id in record.sections)
        identifiers.extend(view_id for _slug, view_id in record.views)
    if len(identifiers) != len(set(identifiers)):
        raise ProductBuildError("checkpoint hub id is duplicated")
    return records


def _require_hub_record(value: object) -> IdentityHubRecord:
    if type(value) is not dict:
        raise ProductBuildError("checkpoint hub must be an object")
    entry = cast(dict[object, object], value)
    if not exact_keys(entry, _HUB_KEYS):
        raise ProductBuildError("checkpoint hub fields are missing or unsupported")
    sections = _require_sections(entry["sections"])
    views = _require_view_rows(entry["views"])
    return IdentityHubRecord(
        name=require_token(entry["name"], "hub name"),
        page_id=require_token(entry["page_id"], "hub page"),
        sections=sections,
        navigation_block_id=require_token(entry["navigation_block_id"], "hub navigation"),
        views=views,
    )


def _require_sections(value: object) -> tuple[tuple[str, str], ...]:
    if type(value) is not list or len(value) != len(_SECTION_ROLES):
        raise ProductBuildError("checkpoint hub sections are unsupported")
    rows: list[tuple[str, str]] = []
    for item in cast(list[object], value):
        if type(item) is not dict:
            raise ProductBuildError("checkpoint hub section must be an object")
        entry = cast(dict[object, object], item)
        if not exact_keys(entry, _SECTION_KEYS):
            raise ProductBuildError("checkpoint hub section fields are missing or unsupported")
        rows.append(
            (
                require_token(entry["role"], "hub section role"),
                require_token(entry["block_id"], "hub section"),
            )
        )
    if tuple(role for role, _block_id in rows) != _SECTION_ROLES:
        raise ProductBuildError("checkpoint hub sections are unsupported")
    return tuple(rows)


def _require_view_rows(value: object) -> tuple[tuple[str, str], ...]:
    if type(value) is not list or len(value) != 2:
        raise ProductBuildError("checkpoint hub views are unsupported")
    rows: list[tuple[str, str]] = []
    for item in cast(list[object], value):
        if type(item) is not dict:
            raise ProductBuildError("checkpoint hub view must be an object")
        entry = cast(dict[object, object], item)
        if not exact_keys(entry, _VIEW_KEYS):
            raise ProductBuildError("checkpoint hub view fields are missing or unsupported")
        slug = require_token(entry["slug"], "hub view slug")
        if slug not in _KNOWN_SLUGS:
            raise ProductBuildError("checkpoint hub view is unsupported")
        rows.append((slug, require_token(entry["view_id"], "hub view")))
    return tuple(rows)


def require_identity_hubs(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    *,
    extra_page_ids: tuple[str, ...] = (),
    extra_top_level_ids: tuple[str, ...] = (),
    extra_database_ids: tuple[str, ...] = (),
    extra_block_ids: tuple[str, ...] = (),
    page_marks: Mapping[str, tuple[str, str]] | None = None,
    formula_suffixes: Mapping[str, tuple[tuple[str, str], ...]] | None = None,
    formulas_optional: bool = False,
) -> NotionPage:
    """Check the saved hubs. Extra pages and databases belong to a later phase."""
    kinds = shared_database_kinds(spec)
    page = _require_prior_dashboard(
        probe,
        stored,
        spec,
        kinds,
        extra_database_ids=extra_database_ids,
        formula_suffixes=formula_suffixes,
        formulas_optional=formulas_optional,
    )
    _require_saved_hubs(
        probe,
        page,
        stored,
        spec,
        kinds,
        extra_page_ids=extra_page_ids,
        extra_top_level_ids=extra_top_level_ids,
        extra_block_ids=extra_block_ids,
        page_marks=page_marks,
    )
    return page


def _require_prior_dashboard(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    kinds: tuple[str, ...],
    *,
    extra_database_ids: tuple[str, ...] = (),
    formula_suffixes: Mapping[str, tuple[tuple[str, str], ...]] | None = None,
    formulas_optional: bool = False,
) -> NotionPage:
    page = require_home_page(probe, stored, spec)
    require_checkpoint_databases(
        probe,
        page,
        stored,
        kinds,
        extra_database_ids=extra_database_ids,
        formula_suffixes=formula_suffixes,
        formulas_optional=formulas_optional,
    )
    require_dashboard_pieces(probe, page, stored, spec)
    if probe.views:
        raise ProductBuildError("hub view is unexpected")
    return page


def _checkpoint_with_hubs(
    stored: ProductBuildCheckpoint,
    records: tuple[IdentityHubRecord, ...],
    recorded_at: datetime,
) -> ProductBuildCheckpoint:
    return replace(
        stored,
        checkpoint_names=_PHASE_FOUR,
        next_phase=BUILD_PHASES[len(_PHASE_FOUR)],
        identity_hubs=records,
        recorded_at=recorded_at,
    )


def _dashboard_block_ids(stored: ProductBuildCheckpoint) -> set[str]:
    identifiers = {stored.shell_block_id}
    for kind, value in stored.dashboard_pieces:
        if kind in _BLOCK_KINDS:
            identifiers.add(value)
    return identifiers


def _dashboard_view_ids(stored: ProductBuildCheckpoint) -> set[str]:
    return {value for kind, value in stored.dashboard_pieces if kind in _VIEW_KINDS}


def _child_pages(probe: FixtureNotionAdapter, home: NotionPage) -> list[NotionPage]:
    return [
        page
        for page in probe.pages.values()
        if type(page) is NotionPage
        and page.parent_id == home.id
        and page.parent_type == _CHILD_PARENT
    ]


def _home_pages(
    probe: FixtureNotionAdapter,
    home: NotionPage,
    extra_top_level_ids: tuple[str, ...] = (),
) -> None:
    top_level = [
        page
        for page in probe.pages.values()
        if type(page) is NotionPage and page.parent_type == _TOP_LEVEL_PARENT
    ]
    if not extra_top_level_ids:
        if top_level != [home]:
            raise ProductBuildError("hub page is unexpected")
        return
    allowed = {home.id, *extra_top_level_ids}
    if {page.id for page in top_level} != allowed:
        raise ProductBuildError("hub page is unexpected")


def _classify(
    probe: FixtureNotionAdapter,
    home: NotionPage,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    plan: tuple[_PlannedHub, ...],
    database_ids: dict[str, str],
) -> tuple[_FoundHub, ...]:
    _home_pages(probe, home)
    _require_home_objects(probe, home, stored)
    children = _child_pages(probe, home)
    names = {hub.name for hub in plan}
    if any(page.title not in names for page in children):
        raise ProductBuildError("hub page is unexpected")
    allowed = {home.id, *(page.id for page in children)}
    actual = {page.id for page in probe.pages.values() if type(page) is NotionPage}
    if actual != allowed or len(probe.pages) != len(allowed):
        raise ProductBuildError("hub page is unexpected")
    if any(block.parent_id not in allowed for block in probe.blocks.values()):
        raise ProductBuildError("hub block is unexpected")
    if any(
        type(view) is not NotionLinkedView or view.parent_page_id not in allowed
        for view in probe.linked_views.values()
    ):
        raise ProductBuildError("hub view is unexpected")
    by_title: dict[str, list[NotionPage]] = {}
    for page in children:
        by_title.setdefault(page.title, []).append(page)
    found: list[_FoundHub] = []
    for planned in plan:
        matches = by_title.get(planned.name, [])
        if len(matches) > 1:
            raise ProductBuildError("hub page is duplicated")
        page = matches[0] if matches else None
        if page is None:
            found.append(_FoundHub(None, (None, None, None), None, (None, None)))
            continue
        if page.is_published is not False:
            raise ProductBuildError("hub page must stay unpublished")
        if page.icon is not None or page.cover is not None:
            raise ProductBuildError("hub page does not match")
        found.append(
            _FoundHub(
                page,
                _classify_sections(probe, page, spec, planned.name),
                _classify_navigation(probe, page, spec, planned.name),
                _classify_views(probe, page, planned, database_ids),
            )
        )
    return tuple(found)


def _require_home_objects(
    probe: FixtureNotionAdapter,
    home: NotionPage,
    stored: ProductBuildCheckpoint,
    *,
    extra_block_ids: tuple[str, ...] = (),
) -> None:
    blocks = [block for block in probe.blocks.values() if block.parent_id == home.id]
    expected_blocks = _dashboard_block_ids(stored)
    home_ids = {block.id for block in blocks}
    if (
        len(blocks) != len(home_ids)
        or not expected_blocks <= home_ids
        or not home_ids <= expected_blocks | set(extra_block_ids)
    ):
        raise ProductBuildError("hub block is unexpected")
    views = [
        view
        for view in probe.linked_views.values()
        if type(view) is NotionLinkedView and view.parent_page_id == home.id
    ]
    expected_views = _dashboard_view_ids(stored)
    if {view.id for view in views} != expected_views or len(views) != len(expected_views):
        raise ProductBuildError("hub view is unexpected")
    if any(type(view) is not NotionLinkedView for view in probe.linked_views.values()):
        raise ProductBuildError("hub view is unexpected")


def _page_texts(probe: FixtureNotionAdapter, page_id: str) -> list[NotionTextBlock]:
    blocks = [block for block in probe.blocks.values() if block.parent_id == page_id]
    texts: list[NotionTextBlock] = []
    for block in blocks:
        if type(block) is not NotionTextBlock:
            raise ProductBuildError("hub block is unexpected")
        texts.append(block)
    return texts


def _matching_text(
    blocks: list[NotionTextBlock], content: str, used: set[str]
) -> NotionTextBlock | None:
    matches = [block for block in blocks if block.id not in used and block.content == content]
    if len(matches) > 1:
        raise ProductBuildError("hub block is duplicated")
    if not matches:
        return None
    used.add(matches[0].id)
    return matches[0]


def _classify_sections(
    probe: FixtureNotionAdapter, page: NotionPage, spec: ProductSpec, hub_name: str
) -> tuple[NotionTextBlock | None, NotionTextBlock | None, NotionTextBlock | None]:
    blocks = _page_texts(probe, page.id)
    used: set[str] = set()
    purpose = _matching_text(blocks, section_content(spec, hub_name, "purpose"), used)
    practice = _matching_text(blocks, section_content(spec, hub_name, "practice"), used)
    buyer = _matching_text(blocks, section_content(spec, hub_name, "buyer"), used)
    _matching_text(blocks, navigation_content(spec, hub_name), used)
    if any(block.id not in used for block in blocks):
        raise ProductBuildError("hub block is unexpected")
    return purpose, practice, buyer


def _classify_navigation(
    probe: FixtureNotionAdapter, page: NotionPage, spec: ProductSpec, hub_name: str
) -> NotionTextBlock | None:
    content = navigation_content(spec, hub_name)
    matches = [
        block
        for block in _page_texts(probe, page.id)
        if type(block) is NotionTextBlock and block.content == content
    ]
    if len(matches) > 1:
        raise ProductBuildError("hub block is duplicated")
    return matches[0] if matches else None


def _classify_views(
    probe: FixtureNotionAdapter,
    page: NotionPage,
    planned: _PlannedHub,
    database_ids: dict[str, str],
) -> tuple[NotionLinkedView | None, NotionLinkedView | None]:
    found: list[NotionLinkedView | None] = []
    used: set[str] = set()
    for planned_view in planned.views:
        matches = _view_matches(
            probe, page.id, database_ids[planned_view.view.data_type], planned_view.view
        )
        if len(matches) > 1:
            raise ProductBuildError("hub view is duplicated")
        item = matches[0] if matches else None
        found.append(item)
        if item is not None:
            used.add(item.id)
    page_views = [
        item
        for item in probe.linked_views.values()
        if type(item) is NotionLinkedView and item.parent_page_id == page.id
    ]
    if any(item.id not in used for item in page_views):
        raise ProductBuildError("hub view is unexpected")
    first, second = found
    return first, second


async def _ensure_hubs(
    probe: FixtureNotionAdapter,
    home: NotionPage,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    kinds: tuple[str, ...],
) -> tuple[IdentityHubRecord, ...]:
    database_ids = dict(stored.database_ids)
    plan = _plan(spec, kinds)
    found = _classify(probe, home, stored, spec, plan, database_ids)
    records: list[IdentityHubRecord] = []
    for index, (planned, existing) in enumerate(zip(plan, found, strict=True)):
        page = existing.page or await probe.add_child_page(home.id, planned.name)
        if index == 0:
            guard_operation(probe, OP_HUBS_CREATE)
        section_ids: list[tuple[str, str]] = []
        for role, block in zip(_SECTION_ROLES, existing.sections, strict=True):
            saved = block or await probe.add_text_block(
                page.id, section_content(spec, planned.name, role)
            )
            section_ids.append((role, saved.id))
        navigation = existing.navigation or await probe.add_text_block(
            page.id, navigation_content(spec, planned.name)
        )
        view_ids: list[tuple[str, str]] = []
        for planned_view, current in zip(planned.views, existing.views, strict=True):
            linked = current or await _create_linked_view(
                probe, page.id, database_ids[planned_view.view.data_type], planned_view.view
            )
            view_ids.append((planned_view.slug, linked.id))
        records.append(
            IdentityHubRecord(
                name=planned.name,
                page_id=page.id,
                sections=tuple(section_ids),
                navigation_block_id=navigation.id,
                views=tuple(view_ids),
            )
        )
    return tuple(records)


def _require_saved_hubs(
    probe: FixtureNotionAdapter,
    home: NotionPage,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    kinds: tuple[str, ...],
    *,
    extra_page_ids: tuple[str, ...] = (),
    extra_top_level_ids: tuple[str, ...] = (),
    extra_block_ids: tuple[str, ...] = (),
    page_marks: Mapping[str, tuple[str, str]] | None = None,
) -> None:
    names = tuple(hub.name for hub in spec.hubs)
    if tuple(record.name for record in stored.identity_hubs) != names:
        raise ProductBuildError("checkpoint hubs do not match the ProductSpec")
    plan = _plan(spec, kinds)
    database_ids = dict(stored.database_ids)
    for planned, record in zip(plan, stored.identity_hubs, strict=True):
        _require_hub(probe, home, spec, planned, record, database_ids, page_marks=page_marks)
    _require_exact_hubs(
        probe,
        home,
        stored,
        extra_page_ids=extra_page_ids,
        extra_top_level_ids=extra_top_level_ids,
        extra_block_ids=extra_block_ids,
    )


def _require_hub(
    probe: FixtureNotionAdapter,
    home: NotionPage,
    spec: ProductSpec,
    planned: _PlannedHub,
    record: IdentityHubRecord,
    database_ids: dict[str, str],
    *,
    page_marks: Mapping[str, tuple[str, str]] | None = None,
) -> None:
    page = probe.pages.get(record.page_id)
    if (
        type(page) is not NotionPage
        or page.title != record.name
        or page.parent_id != home.id
        or page.parent_type != _CHILD_PARENT
        or page.is_published is not False
        or not _hub_mark_ok(page, record.page_id, page_marks)
    ):
        raise ProductBuildError("hub piece is missing")
    if tuple(role for role, _block_id in record.sections) != _SECTION_ROLES:
        raise ProductBuildError("checkpoint hubs do not match the ProductSpec")
    if tuple(slug for slug, _view_id in record.views) != tuple(item.slug for item in planned.views):
        raise ProductBuildError("checkpoint hubs do not match the ProductSpec")
    for role, block_id in record.sections:
        block = probe.blocks.get(block_id)
        if (
            type(block) is not NotionTextBlock
            or block.parent_id != page.id
            or block.content != section_content(spec, record.name, role)
        ):
            raise ProductBuildError("hub piece is missing")
    navigation = probe.blocks.get(record.navigation_block_id)
    if (
        type(navigation) is not NotionTextBlock
        or navigation.parent_id != page.id
        or navigation.content != navigation_content(spec, record.name)
    ):
        raise ProductBuildError("hub piece is missing")
    for (slug, view_id), planned_view in zip(record.views, planned.views, strict=True):
        if slug != planned_view.slug:
            raise ProductBuildError("checkpoint hubs do not match the ProductSpec")
        _require_linked_view(
            probe, page, view_id, database_ids[planned_view.view.data_type], planned_view.view
        )


def _require_linked_view(
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
        raise ProductBuildError("hub piece is missing")


def _hub_mark_ok(
    page: NotionPage,
    page_id: str,
    page_marks: Mapping[str, tuple[str, str]] | None,
) -> bool:
    if page_marks is not None and page_id in page_marks:
        icon, cover = page_marks[page_id]
        if page.icon != icon:
            return False
        return page.cover == cover or page.cover is None
    return page.icon is None and page.cover is None


def _require_exact_hubs(
    probe: FixtureNotionAdapter,
    home: NotionPage,
    stored: ProductBuildCheckpoint,
    *,
    extra_page_ids: tuple[str, ...] = (),
    extra_top_level_ids: tuple[str, ...] = (),
    extra_block_ids: tuple[str, ...] = (),
) -> None:
    _home_pages(probe, home, extra_top_level_ids)
    _require_home_objects(probe, home, stored, extra_block_ids=extra_block_ids)
    pages = {home.id, *(record.page_id for record in stored.identity_hubs), *extra_page_ids}
    actual_pages = {page.id for page in probe.pages.values() if type(page) is NotionPage}
    if actual_pages != pages or len(probe.pages) != len(pages):
        raise ProductBuildError("hub page is unexpected")
    blocks = set(_dashboard_block_ids(stored))
    views = set(_dashboard_view_ids(stored))
    for record in stored.identity_hubs:
        blocks.add(record.navigation_block_id)
        blocks.update(block_id for _role, block_id in record.sections)
        views.update(view_id for _slug, view_id in record.views)
    blocks.update(extra_block_ids)
    actual_blocks = {block.id for block in probe.blocks.values()}
    if actual_blocks != blocks or len(probe.blocks) != len(blocks):
        raise ProductBuildError("hub block is unexpected")
    actual_views = {
        view.id for view in probe.linked_views.values() if type(view) is NotionLinkedView
    }
    if actual_views != views or len(probe.linked_views) != len(views):
        raise ProductBuildError("hub view is unexpected")
    if probe.views:
        raise ProductBuildError("hub view is unexpected")


def hub_provider_references(checkpoint: ProductBuildCheckpoint) -> dict[str, object]:
    """Provider ids recorded for the identity-hub checkpoint."""
    references = dict(dashboard_provider_references(checkpoint))
    references[_HUBS_KEY] = [
        {
            "name": record.name,
            "navigation_block_id": record.navigation_block_id,
            "page_id": record.page_id,
            "sections": [
                {"block_id": block_id, "role": role} for role, block_id in record.sections
            ],
            "views": [{"slug": slug, "view_id": view_id} for slug, view_id in record.views],
        }
        for record in checkpoint.identity_hubs
    ]
    return references


def _write_hubs_checkpoint(path: Path, checkpoint: ProductBuildCheckpoint) -> None:
    write_checkpoint(path, checkpoint, hub_provider_references(checkpoint))
