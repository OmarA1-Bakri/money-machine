"""A08 fixture variants.

Session 07 prompt section 7. One shallow copy of the completed top-level page
per colour variant. Copies are published through the fixture. The six build
phases stay the checkpoint names. The returned next phase is qa. A07, A08,
and A09 stay DESIGNED. This module does not commission an agent or open a
network connection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import cast

from money_machine.agents.implementations.notion_aesthetics import (
    AESTHETIC_ICON,
    accent_content,
    aesthetics_provider_references,
    hub_cover,
    hub_icon,
    parse_aesthetics_checkpoint,
    require_aesthetics_created_ids,
    require_completed_aesthetics,
)
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    PRODUCT_ID_PROPERTY,
    SHELL_BLOCK_PROPERTY,
    SPEC_ID_PROPERTY,
    ProductBuildCheckpoint,
    ProductBuildError,
    VariantRecord,
    exact_keys,
    find_spec_page,
    require_datetime,
    require_path,
    require_probe,
    require_same_spec,
    require_spec,
    require_token,
)
from money_machine.agents.implementations.notion_progress import (
    OP_VARIANTS,
    ProviderFailure,
    guard_operation,
    load_payload,
    raise_recorded,
    reject_duplicate_labels,
)
from money_machine.agents.implementations.notion_progress_record import write_checkpoint
from money_machine.domain.models.product_spec import ColourToken, ProductSpec
from money_machine.integrations.notion.domain import (
    NotionCalloutBlock,
    NotionDatabase,
    NotionPage,
    NotionTextBlock,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter

PHASE_QA = "qa"
_VARIANTS_KEY = "variants"
_VARIANT_KEYS = frozenset(
    {
        "accent_block_id",
        "name",
        "page_id",
        "secret_link",
        "token",
        "vocabulary_block_id",
    }
)


def vocabulary_content(spec: ProductSpec, colour: str, token: ColourToken) -> str:
    """Vocabulary that differs for each identity and colour."""
    return f"SAMPLE {spec.identity} / {colour}: {token.name} {token.hex}"


async def build_variants(
    spec: object,
    probe: object,
    checkpoint_path: object,
    *,
    recorded_at: object,
) -> ProductBuildCheckpoint:
    """Publish one fixture variant per colour, or resume when those pages are stored."""
    validated = require_spec(spec)
    fixture = require_probe(probe)
    path = require_path(checkpoint_path)
    moment = require_datetime(recorded_at)
    stored, created = _load_checkpoint(path)
    require_same_spec(stored, validated)
    # Created ids and saved aesthetics first. ProductSpec uniqueness waits until
    # a copied spec id has been released, or a crashed drop looks like two pages.
    _validate_earlier_phases(fixture, stored, validated, created)
    if stored.variants:
        await _require_saved(fixture, stored, validated)
        return stored
    try:
        plan = await _plan_variants(fixture, stored, validated)
        await _release_copied_spec_ids(fixture, plan.drop_ids)
        _bind_earlier_phases(fixture, stored, validated, created)
        records = await _ensure_planned(fixture, stored, validated, plan)
    except ProviderFailure as failure:
        raise_recorded(path, BUILD_PHASES[-1], failure)
    checkpoint = _checkpoint_with(stored, records, moment)
    _write_checkpoint(path, checkpoint, created)
    return checkpoint


def _load_checkpoint(path: Path) -> tuple[ProductBuildCheckpoint, Mapping[str, object]]:
    envelope = load_payload(path)
    if envelope.payload is None or envelope.created_notion_ids is None:
        raise ProductBuildError("variants require the aesthetics checkpoint")
    payload = envelope.payload
    created = envelope.created_notion_ids
    names = payload.get("checkpoint_names")
    if names != list(BUILD_PHASES):
        raise ProductBuildError("variants require the aesthetics checkpoint")
    references = payload.get("provider_object_references")
    if type(references) is not dict:
        raise ProductBuildError("provider references must be an object")
    refs = cast(dict[object, object], references)
    base = parse_aesthetics_checkpoint(payload)
    if _VARIANTS_KEY not in refs:
        return base, created
    records = _require_records(refs[_VARIANTS_KEY])
    _require_variant_created_ids(created, records)
    return replace(base, next_phase=PHASE_QA, variants=records), created


def _validate_earlier_phases(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    created: Mapping[str, object],
) -> None:
    """Created ids and saved aesthetics, without ProductSpec uniqueness."""
    _check_earlier_phases(probe, stored, spec, created, ignore_spec_copies=True)


def _bind_earlier_phases(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    created: Mapping[str, object],
) -> None:
    """ProductSpec uniqueness after copied spec ids have been released."""
    _check_earlier_phases(probe, stored, spec, created, ignore_spec_copies=False)


def _check_earlier_phases(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    created: Mapping[str, object],
    *,
    ignore_spec_copies: bool,
) -> None:
    workspace_ids, block_ids, nested_ids = _open_variant_ids(probe, stored, spec)
    # Ignore open pages so a leftover spec id can be released before the bind.
    ignored = (*workspace_ids, *nested_ids) if ignore_spec_copies else ()
    require_completed_aesthetics(
        probe,
        stored,
        spec,
        extra_top_level_ids=workspace_ids,
        extra_block_ids=block_ids,
        extra_page_ids=nested_ids,
        ignored_page_ids=ignored,
    )
    require_aesthetics_created_ids(probe, created, stored)


def _require_records(value: object) -> tuple[VariantRecord, ...]:
    if type(value) is not list or not value:
        raise ProductBuildError("checkpoint variants list is incomplete")
    records: list[VariantRecord] = []
    for item in cast(list[object], value):
        if type(item) is not dict:
            raise ProductBuildError("checkpoint variant must be an object")
        entry = cast(dict[object, object], item)
        if not exact_keys(entry, _VARIANT_KEYS):
            raise ProductBuildError("checkpoint variant fields are missing or unsupported")
        records.append(
            VariantRecord(
                name=require_token(entry["name"], "variant"),
                token_name=require_token(entry["token"], "variant"),
                page_id=require_token(entry["page_id"], "variant"),
                accent_block_id=require_token(entry["accent_block_id"], "variant"),
                vocabulary_block_id=require_token(entry["vocabulary_block_id"], "variant"),
                secret_link=require_token(entry["secret_link"], "variant"),
            )
        )
    reject_duplicate_labels(
        [record.name for record in records],
        "checkpoint variant is duplicated",
    )
    reject_duplicate_labels(
        [record.page_id for record in records],
        "checkpoint variant is duplicated",
    )
    return tuple(records)


def _require_variant_created_ids(
    created: Mapping[str, object], records: tuple[VariantRecord, ...]
) -> None:
    found = created.get(_VARIANTS_KEY)
    if type(found) is not list or len(found) != len(records):
        raise ProductBuildError("progress created ids do not match the checkpoint")
    for item, record in zip(found, records, strict=True):
        if type(item) is not dict:
            raise ProductBuildError("progress created ids do not match the checkpoint")
        entry = cast(dict[object, object], item)
        if not exact_keys(entry, _VARIANT_KEYS):
            raise ProductBuildError("progress created ids do not match the checkpoint")
        expected = _reference_row(record)
        if any(entry.get(key) != value for key, value in expected.items()):
            raise ProductBuildError("progress created ids do not match the checkpoint")


def _checkpoint_with(
    stored: ProductBuildCheckpoint,
    records: tuple[VariantRecord, ...],
    recorded_at: datetime,
) -> ProductBuildCheckpoint:
    return replace(stored, next_phase=PHASE_QA, variants=records, recorded_at=recorded_at)


def _write_checkpoint(
    path: Path,
    checkpoint: ProductBuildCheckpoint,
    created: Mapping[str, object],
) -> None:
    references = aesthetics_provider_references(checkpoint)
    references[_VARIANTS_KEY] = [_reference_row(record) for record in checkpoint.variants]
    write_checkpoint(path, checkpoint, references, retained_created_ids=created)


def _reference_row(record: VariantRecord) -> dict[str, str]:
    return {
        "accent_block_id": record.accent_block_id,
        "name": record.name,
        "page_id": record.page_id,
        "secret_link": record.secret_link,
        "token": record.token_name,
        "vocabulary_block_id": record.vocabulary_block_id,
    }


def _aligned_pairs(spec: ProductSpec) -> tuple[tuple[str, ColourToken], ...]:
    colours = spec.colour_variants
    tokens = spec.palette_tokens
    if len(colours) != len(tokens):
        raise ProductBuildError("variant count does not match palette tokens")
    if len(set(colours)) != len(colours):
        raise ProductBuildError("colour variant name is duplicated")
    if len({token.name for token in tokens}) != len(tokens):
        raise ProductBuildError("palette token name is duplicated")
    return tuple(zip(colours, tokens, strict=True))


@dataclass(frozen=True)
class _VariantPlan:
    drop_ids: tuple[str, ...]
    adoptions: tuple[tuple[str, str], ...]


def _page_in_play(page: NotionPage, source: NotionPage, spec: ProductSpec) -> bool:
    """Copy leftovers and / <Colour> leftovers. The plan runs only when nothing is recorded."""
    if page.title == f"{source.title} (Copy)":
        return True
    return _colour_from_title(spec, page) is not None


def _in_play_pages(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> list[NotionPage]:
    source = _source_page(probe, stored)
    return [
        page
        for page in probe.pages.values()
        if type(page) is NotionPage and page.id != source.id and _page_in_play(page, source, spec)
    ]


def _collect_drop_ids(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> tuple[str, ...]:
    """Spec-id filter only. In-play pages are already (Copy) or / <Colour> titles."""
    source = _source_page(probe, stored)
    source_spec = source.properties.get(SPEC_ID_PROPERTY)
    drop_ids: list[str] = []
    for page in _in_play_pages(probe, stored, spec):
        if page.properties.get(SPEC_ID_PROPERTY) != source_spec:
            continue
        drop_ids.append(page.id)
    return tuple(drop_ids)


def _refuse_titled_children(
    probe: FixtureNotionAdapter,
    spec: ProductSpec,
    pages: list[NotionPage],
) -> None:
    """Finished colour pages are refused here, before any drop."""
    for page in pages:
        colour = _colour_from_title(spec, page)
        if colour is None:
            continue
        token = next(item for name, item in _aligned_pairs(spec) if name == colour)
        if _has_foreign_child(probe, spec, page, colour, token):
            raise ProductBuildError("variant page does not match")


def _require_unique_after_drops(
    probe: FixtureNotionAdapter,
    source: NotionPage,
    drop_ids: tuple[str, ...],
) -> None:
    """ProductSpec uniqueness as if the planned drops had already happened."""
    source_spec = source.properties.get(SPEC_ID_PROPERTY)
    if source_spec is None:
        return
    found = find_spec_page(probe, str(source_spec), ignored_page_ids=drop_ids)
    if found is not None and found.id != source.id:
        raise ProductBuildError("fixture probe has more than one page for this ProductSpec")


def _plan_adoptions(
    probe: FixtureNotionAdapter,
    source: NotionPage,
    spec: ProductSpec,
) -> tuple[tuple[str, str], ...]:
    copy = _find_copy(probe, source)
    used_copy = False
    adoptions: list[tuple[str, str]] = []
    for colour, _token in _aligned_pairs(spec):
        existing = _find_titled(probe, source, _variant_title(spec, colour))
        if existing is None and copy is not None and not used_copy:
            existing = copy
            used_copy = True
        adoptions.append((colour, "" if existing is None else existing.id))
    return tuple(adoptions)


async def _plan_variants(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> _VariantPlan:
    """Write-free plan. Refusal, or a fixed list of drops and adoptions.

    Every adoption is checked here, before any adapter call: the original home,
    the shell copy, the spec value, duplicate accent or vocabulary blocks, and
    the secret link of a page that is already published. ``get_public_url`` is a
    read. It is not one of the counted write methods. A ``ProviderFailure`` from
    that read is handled by ``build_variants`` with the same repair-job rule as
    any other provider failure.
    """
    source = _source_page(probe, stored)
    _require_original(source)
    in_play = _in_play_pages(probe, stored, spec)
    _refuse_titled_children(probe, spec, in_play)
    drop_ids = _collect_drop_ids(probe, stored, spec)
    for page_id in drop_ids:
        page = probe.pages[page_id]
        _refuse_unadoptable_release(probe, source, spec, page)
    _require_unique_after_drops(probe, source, drop_ids)
    adoptions = _plan_adoptions(probe, source, spec)
    for colour, page_id in adoptions:
        if page_id == "":
            continue
        found = probe.pages[page_id]
        token = next(item for name, item in _aligned_pairs(spec) if name == colour)
        _require_adoptable(probe, source, found, spec, colour, token)
        await _require_published_link(probe, found)
    return _VariantPlan(drop_ids, adoptions)


async def _require_published_link(probe: FixtureNotionAdapter, page: NotionPage) -> None:
    """Refuse a published adoption whose secret link is missing. No write."""
    if page.is_published is not True:
        return
    link = await probe.get_public_url(page.id)
    if type(link) is not str or link == "":
        raise ProductBuildError("variant secret link is missing")


async def _ensure_planned(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    plan: _VariantPlan,
) -> tuple[VariantRecord, ...]:
    """Apply the plan. No new choice is made here."""
    source = _source_page(probe, stored)
    chosen = {colour: page_id for colour, page_id in plan.adoptions}
    records: list[VariantRecord] = []
    for colour, token in _aligned_pairs(spec):
        page_id = chosen[colour]
        if page_id == "":
            if records:
                guard_operation(probe, OP_VARIANTS)
            page = await probe.duplicate_page(source.id)
        else:
            found = probe.pages.get(page_id)
            if type(found) is not NotionPage:
                raise ProductBuildError("variant page does not match")
            page = found
        records.append(await _finish_variant(probe, spec, source, page, colour, token))
    _require_one_spec_page(probe, spec, stored)
    _require_original(source)
    return tuple(records)


def _open_variant_ids(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    source = probe.pages.get(stored.page_id)
    if type(source) is not NotionPage:
        return (), (), ()
    titles = {_variant_title(spec, colour) for colour in spec.colour_variants}
    copy_title = f"{source.title} (Copy)"
    recorded = {record.page_id for record in stored.variants}
    source_spec = source.properties.get(SPEC_ID_PROPERTY)
    workspace_ids: list[str] = []
    nested_ids: list[str] = []

    def _title_open(page: NotionPage) -> bool:
        holds_source_spec = (
            source_spec is not None and page.properties.get(SPEC_ID_PROPERTY) == source_spec
        )
        return page.title in titles or page.title == copy_title or holds_source_spec

    for page in probe.pages.values():
        if type(page) is not NotionPage or page.id == source.id:
            continue
        if page.id in recorded:
            if page.parent_type == "workspace":
                workspace_ids.append(page.id)
            else:
                nested_ids.append(page.id)
            continue
        # Stored path: a variant or nested id is a recorded page id.
        # A hub child with a variant title is not that id.
        # An extra workspace / Blue passes even with a child under it.
        # A forgery with the recorded title and a different id is rejected.
        if stored.variants:
            if page.parent_type == "workspace" and _title_open(page):
                workspace_ids.append(page.id)
            continue
        # Empty path: an unrecorded copy is open so resume can adopt it.
        if not _title_open(page):
            continue
        if page.parent_type == "workspace":
            workspace_ids.append(page.id)
        else:
            nested_ids.append(page.id)
    known = set(workspace_ids) | set(nested_ids)
    block_ids: list[str] = []
    for page_id in tuple(known):
        page = probe.pages.get(page_id)
        if type(page) is not NotionPage:
            continue
        owned = _page_block_ids(probe, page)
        block_ids.extend(block_id for block_id in owned if block_id not in block_ids)
        parents = {page.id, *owned}
        for child in probe.pages.values():
            if type(child) is not NotionPage or child.id in known or child.parent_id not in parents:
                continue
            nested_ids.append(child.id)
            known.add(child.id)
    return tuple(workspace_ids), tuple(block_ids), tuple(nested_ids)


async def _release_copied_spec_ids(
    probe: FixtureNotionAdapter,
    drop_ids: tuple[str, ...],
) -> None:
    """Drop only the ids the plan already accepted."""
    for page_id in drop_ids:
        await probe.drop_page_property(page_id, SPEC_ID_PROPERTY)


def _source_page(probe: FixtureNotionAdapter, stored: ProductBuildCheckpoint) -> NotionPage:
    page = probe.pages.get(stored.page_id)
    if type(page) is not NotionPage or page.parent_type != "workspace":
        raise ProductBuildError("variants require the aesthetics checkpoint")
    return page


def _variant_title(spec: ProductSpec, colour: str) -> str:
    return f"{spec.title} / {colour}"


def _find_titled(probe: FixtureNotionAdapter, source: NotionPage, title: str) -> NotionPage | None:
    matches = [
        page
        for page in probe.pages.values()
        if type(page) is NotionPage and page.id != source.id and page.title == title
    ]
    if len(matches) > 1:
        raise ProductBuildError("variant page does not match")
    if not matches:
        return None
    return matches[0]


def _find_copy(probe: FixtureNotionAdapter, source: NotionPage) -> NotionPage | None:
    copy_title = f"{source.title} (Copy)"
    matches = [
        page
        for page in probe.pages.values()
        if type(page) is NotionPage and page.id != source.id and page.title == copy_title
    ]
    if len(matches) > 1:
        raise ProductBuildError("variant page does not match")
    if not matches:
        return None
    return matches[0]


def _require_shell_copy(source: NotionPage, page: NotionPage) -> None:
    if (
        page.parent_type != "workspace"
        or page.parent_id != source.parent_id
        or page.properties.get(PRODUCT_ID_PROPERTY) != source.properties.get(PRODUCT_ID_PROPERTY)
        or page.properties.get(SHELL_BLOCK_PROPERTY) != source.properties.get(SHELL_BLOCK_PROPERTY)
    ):
        raise ProductBuildError("variant page does not match")


def _page_block_ids(probe: FixtureNotionAdapter, page: NotionPage) -> set[str]:
    """Every block of this page, including blocks nested under other blocks."""
    owned: set[str] = set()
    parents = {page.id}
    while parents:
        found = {
            block.id
            for block in probe.blocks.values()
            if block.id not in owned and block.parent_id in parents
        }
        if not found:
            break
        owned.update(found)
        parents = found
    return owned


def _has_nested_child(probe: FixtureNotionAdapter, page: NotionPage) -> bool:
    """A database or page whose parent is this page or any of its blocks."""
    parents = {page.id, *_page_block_ids(probe, page)}
    if any(
        type(database) is NotionDatabase and database.parent_id in parents
        for database in probe.databases.values()
    ):
        return True
    return any(
        type(child) is NotionPage and child.id != page.id and child.parent_id in parents
        for child in probe.pages.values()
    )


def _has_foreign_child(
    probe: FixtureNotionAdapter,
    spec: ProductSpec,
    page: NotionPage,
    colour: str,
    token: ColourToken,
) -> bool:
    if _has_nested_child(probe, page):
        return True
    accent = _matching_accent(probe, page, token)
    vocabulary = _matching_vocabulary(probe, spec, page, colour, token)
    allowed = {block.id for block in (accent, vocabulary) if block is not None}
    return any(
        block.parent_id == page.id and block.id not in allowed for block in probe.blocks.values()
    )


def _has_unrecognized_child(
    probe: FixtureNotionAdapter, spec: ProductSpec, page: NotionPage
) -> bool:
    if _has_nested_child(probe, page):
        return True
    children = [block for block in probe.blocks.values() if block.parent_id == page.id]
    pairs = _aligned_pairs(spec)
    for block in children:
        matched = False
        for colour, token in pairs:
            accent_ok = (
                type(block) is NotionCalloutBlock
                and block.content == accent_content(token.name, token.hex)
                and block.icon == AESTHETIC_ICON
            )
            vocabulary_ok = type(block) is NotionTextBlock and block.content == vocabulary_content(
                spec, colour, token
            )
            if accent_ok or vocabulary_ok:
                matched = True
                break
        if not matched:
            return True
    return False


def _colour_from_title(spec: ProductSpec, page: NotionPage) -> str | None:
    for colour in spec.colour_variants:
        if page.title == _variant_title(spec, colour):
            return colour
    return None


def _require_adoptable(
    probe: FixtureNotionAdapter,
    source: NotionPage,
    page: NotionPage,
    spec: ProductSpec,
    colour: str,
    token: ColourToken,
) -> None:
    """Shell fields, then no nested page or database under the page or its blocks."""
    _require_shell_copy(source, page)
    found = page.properties.get(SPEC_ID_PROPERTY)
    if found is not None and found != source.properties.get(SPEC_ID_PROPERTY):
        raise ProductBuildError("variant page does not match")
    if _has_foreign_child(probe, spec, page, colour, token):
        raise ProductBuildError("variant page does not match")


def _refuse_unadoptable_release(
    probe: FixtureNotionAdapter,
    source: NotionPage,
    spec: ProductSpec,
    page: NotionPage,
) -> None:
    _require_shell_copy(source, page)
    colour = _colour_from_title(spec, page)
    if colour is None:
        if _has_unrecognized_child(probe, spec, page):
            raise ProductBuildError("variant page does not match")
        return
    token = next(item for name, item in _aligned_pairs(spec) if name == colour)
    if _has_foreign_child(probe, spec, page, colour, token):
        raise ProductBuildError("variant page does not match")


async def _finish_variant(
    probe: FixtureNotionAdapter,
    spec: ProductSpec,
    source: NotionPage,
    page: NotionPage,
    colour: str,
    token: ColourToken,
) -> VariantRecord:
    _require_adoptable(probe, source, page, spec, colour, token)
    title = _variant_title(spec, colour)
    if SPEC_ID_PROPERTY in page.properties:
        page = await probe.drop_page_property(page.id, SPEC_ID_PROPERTY)
    if page.title != title:
        page = await probe.rename_page(page.id, title)
    if page.icon != hub_icon(token):
        page = await probe.set_icon(page.id, hub_icon(token))
    if page.cover != hub_cover(token):
        page = await probe.set_cover(page.id, hub_cover(token))
    accent = _matching_accent(probe, page, token)
    if accent is None:
        accent = await probe.add_callout_block(
            page.id,
            accent_content(token.name, token.hex),
            icon=AESTHETIC_ICON,
        )
    vocabulary = _matching_vocabulary(probe, spec, page, colour, token)
    if vocabulary is None:
        vocabulary = await probe.add_text_block(page.id, vocabulary_content(spec, colour, token))
    if page.is_published is not True:
        page = await probe.publish_page(page.id)
    if page.duplicate_as_template is not True:
        page = await probe.set_duplicate_as_template(page.id, True)
    if page.search_indexing is not False:
        page = await probe.set_search_indexing(page.id, False)
    link = await probe.get_public_url(page.id)
    if type(link) is not str or link == "":
        raise ProviderFailure(OP_VARIANTS, "variant secret link is missing")
    _require_variant_page(probe, spec, page, colour, token)
    return _record_from(page, colour, token, accent.id, vocabulary.id, link)


def _matching_accent(
    probe: FixtureNotionAdapter, page: NotionPage, token: ColourToken
) -> NotionCalloutBlock | None:
    matches = [
        block
        for block in probe.blocks.values()
        if type(block) is NotionCalloutBlock
        and block.parent_id == page.id
        and block.content == accent_content(token.name, token.hex)
        and block.icon == AESTHETIC_ICON
    ]
    if len(matches) > 1:
        raise ProductBuildError("variant page does not match")
    if not matches:
        return None
    return matches[0]


def _matching_vocabulary(
    probe: FixtureNotionAdapter,
    spec: ProductSpec,
    page: NotionPage,
    colour: str,
    token: ColourToken,
) -> NotionTextBlock | None:
    expected = vocabulary_content(spec, colour, token)
    matches = [
        block
        for block in probe.blocks.values()
        if (
            type(block) is NotionTextBlock
            and block.parent_id == page.id
            and block.content == expected
        )
    ]
    if len(matches) > 1:
        raise ProductBuildError("variant page does not match")
    if not matches:
        return None
    return matches[0]


def _record_from(
    page: NotionPage,
    colour: str,
    token: ColourToken,
    accent_id: str,
    vocabulary_id: str,
    link: str,
) -> VariantRecord:
    return VariantRecord(
        name=colour,
        token_name=token.name,
        page_id=page.id,
        accent_block_id=accent_id,
        vocabulary_block_id=vocabulary_id,
        secret_link=link,
    )


async def _require_saved(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> None:
    if stored.next_phase != PHASE_QA or not stored.variants:
        raise ProductBuildError("variant record is missing")
    pairs = _aligned_pairs(spec)
    if len(stored.variants) != len(pairs):
        raise ProductBuildError("checkpoint variants do not match the ProductSpec")
    aligned = tuple(zip(stored.variants, pairs, strict=True))
    if tuple((record.name, record.token_name) for record, _pair in aligned) != tuple(
        (colour, token.name) for _record, (colour, token) in aligned
    ):
        raise ProductBuildError("checkpoint variants do not match the ProductSpec")
    source = _source_page(probe, stored)
    _require_original(source)
    for record, (colour, token) in aligned:
        page = probe.pages.get(record.page_id)
        if type(page) is not NotionPage:
            raise ProductBuildError("variant page does not match")
        _require_variant_page(probe, spec, page, colour, token)
        accent_id, vocabulary_id = _block_ids(probe, spec, page, colour, token)
        if accent_id != record.accent_block_id or vocabulary_id != record.vocabulary_block_id:
            raise ProductBuildError("variant page does not match")
        link = await probe.get_public_url(page.id)
        if link != record.secret_link:
            raise ProductBuildError("variant page does not match")
    _require_one_spec_page(probe, spec, stored)


def _require_variant_page(
    probe: FixtureNotionAdapter,
    spec: ProductSpec,
    page: NotionPage,
    colour: str,
    token: ColourToken,
) -> None:
    if (
        page.parent_type != "workspace"
        or page.title != _variant_title(spec, colour)
        or page.icon != hub_icon(token)
        or page.cover != hub_cover(token)
        or page.is_published is not True
        or page.duplicate_as_template is not True
        or page.search_indexing is not False
        or SPEC_ID_PROPERTY in page.properties
        or _has_nested_child(probe, page)
    ):
        raise ProductBuildError("variant page does not match")
    _block_ids(probe, spec, page, colour, token)


def _block_ids(
    probe: FixtureNotionAdapter,
    spec: ProductSpec,
    page: NotionPage,
    colour: str,
    token: ColourToken,
) -> tuple[str, str]:
    children = [block for block in probe.blocks.values() if block.parent_id == page.id]
    accents = [
        block
        for block in children
        if type(block) is NotionCalloutBlock
        and block.content == accent_content(token.name, token.hex)
        and block.icon == AESTHETIC_ICON
    ]
    samples = [
        block
        for block in children
        if type(block) is NotionTextBlock
        and block.content == vocabulary_content(spec, colour, token)
    ]
    if len(children) != 2 or len(accents) != 1 or len(samples) != 1:
        raise ProductBuildError("variant page does not match")
    return accents[0].id, samples[0].id


def _require_one_spec_page(
    probe: FixtureNotionAdapter, spec: ProductSpec, stored: ProductBuildCheckpoint
) -> None:
    home = find_spec_page(probe, str(spec.spec_id))
    if home is None or home.id != stored.page_id:
        raise ProductBuildError("variant page does not match")


def _require_original(page: NotionPage) -> None:
    if page.is_published or page.duplicate_as_template or page.search_indexing is not True:
        raise ProductBuildError("variant page does not match")
