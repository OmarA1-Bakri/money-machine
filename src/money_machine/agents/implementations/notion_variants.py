"""A08 fixture variants.

Session 07 prompt section 7. One shallow copy of the completed top-level page
per colour variant. Copies are published through the fixture. The six build
phases stay the checkpoint names. The returned next phase is qa. A07, A08,
and A09 stay DESIGNED. This module does not commission an agent or open a
network connection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
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
    await _release_copied_spec_ids(fixture, stored, validated)
    _bind_earlier_phases(fixture, stored, validated, created)
    if stored.variants:
        await _require_saved(fixture, stored, validated)
        return stored
    try:
        records = await _ensure(fixture, stored, validated)
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


def _bind_earlier_phases(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    created: Mapping[str, object],
) -> None:
    """Aesthetics saved state, then created ids, before any variant branch."""
    page_ids, block_ids = _open_variant_ids(probe, stored, spec)
    require_completed_aesthetics(
        probe,
        stored,
        spec,
        extra_top_level_ids=page_ids,
        extra_block_ids=block_ids,
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


async def _ensure(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> tuple[VariantRecord, ...]:
    source = _source_page(probe, stored)
    pairs = _aligned_pairs(spec)
    records: list[VariantRecord] = []
    for colour, token in pairs:
        title = _variant_title(spec, colour)
        existing = _find_titled(probe, source, title)
        if existing is None:
            existing = _find_copy(probe, source)
        if existing is None:
            if records:
                guard_operation(probe, OP_VARIANTS)
            existing = await probe.duplicate_page(source.id)
        records.append(await _finish_variant(probe, spec, existing, colour, token))
    _require_one_spec_page(probe, spec, stored)
    _require_original(source)
    return tuple(records)


def _open_variant_ids(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    source = probe.pages.get(stored.page_id)
    if type(source) is not NotionPage:
        return (), ()
    titles = {_variant_title(spec, colour) for colour in spec.colour_variants}
    copy_title = f"{source.title} (Copy)"
    recorded = {record.page_id for record in stored.variants}
    page_ids = [
        page.id
        for page in probe.pages.values()
        if type(page) is NotionPage
        and page.id != source.id
        and page.parent_type == "workspace"
        and (page.id in recorded or page.title in titles or page.title == copy_title)
    ]
    block_ids = [block.id for block in probe.blocks.values() if block.parent_id in set(page_ids)]
    return tuple(page_ids), tuple(block_ids)


async def _release_copied_spec_ids(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> None:
    source = probe.pages.get(stored.page_id)
    if type(source) is not NotionPage:
        return
    titles = {_variant_title(spec, colour) for colour in spec.colour_variants}
    copy_title = f"{source.title} (Copy)"
    for page in list(probe.pages.values()):
        if type(page) is not NotionPage or page.id == source.id:
            continue
        if page.title not in titles and page.title != copy_title:
            continue
        if SPEC_ID_PROPERTY in page.properties:
            await probe.drop_page_property(page.id, SPEC_ID_PROPERTY)


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


async def _finish_variant(
    probe: FixtureNotionAdapter,
    spec: ProductSpec,
    page: NotionPage,
    colour: str,
    token: ColourToken,
) -> VariantRecord:
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
        raise ProductBuildError("variant secret link is missing")
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
