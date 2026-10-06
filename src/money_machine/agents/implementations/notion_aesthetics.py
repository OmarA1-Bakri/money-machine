"""A07 fixture phase 6: palette accents and sample hub content.

Resumes the notification-dashboard checkpoint. Sample text stays marked SAMPLE
and uses only ProductSpec fields. The next phase name records that the build
phases are complete. This module does not build variants, run QA, open a
network connection, or commission an agent.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import cast

from money_machine.agents.implementations.notion_dashboard import require_home_page
from money_machine.agents.implementations.notion_notifications import (
    notification_provider_references,
    parse_notification_checkpoint,
    require_notification_dashboard,
)
from money_machine.agents.implementations.notion_product_builder import (
    BUILD_PHASES,
    BUILD_PHASES_COMPLETE,
    CHECKPOINT_KEYS,
    AestheticsRecord,
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
    OP_AESTHETICS_SAMPLES,
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

AESTHETIC_ICON = "◆"
_PHASE_FIVE = BUILD_PHASES[:5]
_AESTHETICS_KEY = "aesthetics"
_HOME_BLOCK_KINDS = frozenset({"greeting", "hub_navigation", "callout"})
_RECORD_KEYS = frozenset({"accents", "marks", "samples"})
_ACCENT_KEYS = frozenset({"block_id", "token"})
_SAMPLE_KEYS = frozenset({"block_id", "hub"})
_MARK_KEYS = frozenset({"cover", "icon", "page_id"})


def accent_content(token_name: str, token_hex: str) -> str:
    """One palette accent. The text is the token name and hex only."""
    return f"palette {token_name} {token_hex}"


def sample_content(spec: ProductSpec, hub_name: str) -> str:
    """Sample hub text from the identity, hub name, and hub description."""
    hub = next(item for item in spec.hubs if item.name == hub_name)
    return f"SAMPLE {spec.identity} / {hub_name}: {hub.description}"


def hub_icon(token: ColourToken) -> str:
    """Fixture icon drawn from one palette token."""
    return f"palette:{token.name}:{token.hex}"


def hub_cover(token: ColourToken) -> str:
    """Fixture cover drawn from one palette token."""
    return f"fixture://palette/{token.name}/{token.hex}"


async def build_aesthetics_and_content_completion(
    spec: object,
    probe: object,
    checkpoint_path: object,
    *,
    recorded_at: object,
) -> ProductBuildCheckpoint:
    """Store palette accents and sample hub text, or resume when they are stored."""
    validated = require_spec(spec)
    fixture = require_probe(probe)
    path = require_path(checkpoint_path)
    moment = require_datetime(recorded_at)
    stored = _load_checkpoint(path)
    require_same_spec(stored, validated)
    if stored.checkpoint_names == BUILD_PHASES:
        _require_saved(fixture, stored, validated)
        return stored
    try:
        record = await _ensure(fixture, stored, validated)
    except ProviderFailure as failure:
        raise_recorded(path, BUILD_PHASES[-1], failure)
    checkpoint = _checkpoint_with(stored, record, moment)
    _write_checkpoint(path, checkpoint)
    return checkpoint


def _load_checkpoint(path: Path) -> ProductBuildCheckpoint:
    envelope = load_payload(path)
    if envelope.payload is None:
        raise ProductBuildError("aesthetics require the notification dashboard checkpoint")
    payload = envelope.payload
    names = payload.get("checkpoint_names")
    if names == list(_PHASE_FIVE):
        return parse_notification_checkpoint(payload)
    if names == list(BUILD_PHASES):
        return _parse_aesthetics_checkpoint(payload)
    raise ProductBuildError("aesthetics require the notification dashboard checkpoint")


def _parse_aesthetics_checkpoint(payload: dict[object, object]) -> ProductBuildCheckpoint:
    if not exact_keys(payload, CHECKPOINT_KEYS):
        raise ProductBuildError("checkpoint fields are missing or unsupported")
    names = payload["checkpoint_names"]
    if type(names) is not list or names != list(BUILD_PHASES):
        raise ProductBuildError("checkpoint must record aesthetics and content completion")
    references = payload["provider_object_references"]
    if type(references) is not dict:
        raise ProductBuildError("provider references must be an object")
    refs = cast(dict[object, object], references)
    if _AESTHETICS_KEY not in refs:
        raise ProductBuildError("provider references are missing or unsupported")
    record = _require_record(refs[_AESTHETICS_KEY])
    phase_five = dict(payload)
    phase_five["checkpoint_names"] = list(_PHASE_FIVE)
    phase_five["provider_object_references"] = {
        key: refs[key] for key in set(refs) - {_AESTHETICS_KEY}
    }
    base = parse_notification_checkpoint(phase_five)
    return replace(
        base,
        checkpoint_names=BUILD_PHASES,
        next_phase=BUILD_PHASES_COMPLETE,
        aesthetics=record,
    )


def _require_record(value: object) -> AestheticsRecord:
    if type(value) is not dict:
        raise ProductBuildError("checkpoint aesthetics must be an object")
    entry = cast(dict[object, object], value)
    if not exact_keys(entry, _RECORD_KEYS):
        raise ProductBuildError("checkpoint aesthetics fields are missing or unsupported")
    accents = _require_pairs(entry["accents"], _ACCENT_KEYS, "token", "block_id", "accent")
    samples = _require_pairs(entry["samples"], _SAMPLE_KEYS, "hub", "block_id", "sample")
    marks = _require_marks(entry["marks"])
    identifiers = [block_id for _name, block_id in accents]
    identifiers.extend(block_id for _name, block_id in samples)
    identifiers.extend(page_id for page_id, _icon, _cover in marks)
    if len(identifiers) != len(set(identifiers)):
        raise ProductBuildError("checkpoint aesthetics id is duplicated")
    return AestheticsRecord(accents=accents, samples=samples, marks=marks)


def _require_pairs(
    value: object,
    keys: frozenset[str],
    name_key: str,
    id_key: str,
    label: str,
) -> tuple[tuple[str, str], ...]:
    if type(value) is not list or not value:
        raise ProductBuildError(f"checkpoint aesthetics {label} list is incomplete")
    rows: list[tuple[str, str]] = []
    for item in cast(list[object], value):
        if type(item) is not dict:
            raise ProductBuildError(f"checkpoint aesthetics {label} must be an object")
        entry = cast(dict[object, object], item)
        if not exact_keys(entry, keys):
            raise ProductBuildError(
                f"checkpoint aesthetics {label} fields are missing or unsupported"
            )
        rows.append(
            (
                require_token(entry[name_key], f"aesthetics {label}"),
                require_token(entry[id_key], f"aesthetics {label}"),
            )
        )
    names = [name for name, _block_id in rows]
    reject_duplicate_labels(names, f"checkpoint aesthetics {label} is duplicated")
    return tuple(rows)


def _require_marks(value: object) -> tuple[tuple[str, str, str], ...]:
    if type(value) is not list or not value:
        raise ProductBuildError("checkpoint aesthetics mark list is incomplete")
    rows: list[tuple[str, str, str]] = []
    for item in cast(list[object], value):
        if type(item) is not dict:
            raise ProductBuildError("checkpoint aesthetics mark must be an object")
        entry = cast(dict[object, object], item)
        if not exact_keys(entry, _MARK_KEYS):
            raise ProductBuildError("checkpoint aesthetics mark fields are missing or unsupported")
        rows.append(
            (
                require_token(entry["page_id"], "aesthetics mark"),
                require_token(entry["icon"], "aesthetics mark"),
                require_token(entry["cover"], "aesthetics mark"),
            )
        )
    return tuple(rows)


def _checkpoint_with(
    stored: ProductBuildCheckpoint,
    record: AestheticsRecord,
    recorded_at: datetime,
) -> ProductBuildCheckpoint:
    return replace(
        stored,
        checkpoint_names=BUILD_PHASES,
        next_phase=BUILD_PHASES_COMPLETE,
        aesthetics=record,
        recorded_at=recorded_at,
    )


def _write_checkpoint(path: Path, checkpoint: ProductBuildCheckpoint) -> None:
    record = checkpoint.aesthetics
    if record is None:
        raise ProductBuildError("aesthetics record is missing")
    references = notification_provider_references(checkpoint)
    references[_AESTHETICS_KEY] = {
        "accents": [{"block_id": block_id, "token": token} for token, block_id in record.accents],
        "marks": [
            {"cover": cover, "icon": icon, "page_id": page_id}
            for page_id, icon, cover in record.marks
        ],
        "samples": [{"block_id": block_id, "hub": hub} for hub, block_id in record.samples],
    }
    write_checkpoint(path, checkpoint, references)


def _require_saved(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> None:
    record = stored.aesthetics
    if record is None or stored.next_phase != BUILD_PHASES_COMPLETE:
        raise ProductBuildError("aesthetics record is missing")
    home = require_home_page(probe, stored, spec)
    _require_contents(probe, home, stored, spec, record)
    marks = {page_id: (icon, cover) for page_id, icon, cover in record.marks}
    require_notification_dashboard(
        probe,
        stored,
        spec,
        extra_block_ids=tuple(block_id for _name, block_id in (*record.accents, *record.samples)),
        page_marks=marks,
    )


def _require_contents(
    probe: FixtureNotionAdapter,
    home: NotionPage,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    record: AestheticsRecord,
) -> None:
    tokens = tuple(token.name for token in spec.palette_tokens)
    if tuple(name for name, _block_id in record.accents) != tokens:
        raise ProductBuildError("aesthetics accent does not match")
    hubs = tuple(hub.name for hub in spec.hubs)
    if tuple(name for name, _block_id in record.samples) != hubs:
        raise ProductBuildError("aesthetics sample does not match")
    by_token = {token.name: token for token in spec.palette_tokens}
    for token_name, block_id in record.accents:
        block = probe.blocks.get(block_id)
        token = by_token[token_name]
        if (
            type(block) is not NotionCalloutBlock
            or block.parent_id != home.id
            or block.icon != AESTHETIC_ICON
            or block.content != accent_content(token.name, token.hex)
        ):
            raise ProductBuildError("aesthetics accent is missing")
    pages = {record.name: record.page_id for record in stored.identity_hubs}
    for hub_name, block_id in record.samples:
        block = probe.blocks.get(block_id)
        if (
            type(block) is not NotionTextBlock
            or block.parent_id != pages[hub_name]
            or block.content != sample_content(spec, hub_name)
        ):
            raise ProductBuildError("aesthetics sample is missing")
    if tuple(page_id for page_id, _icon, _cover in record.marks) != tuple(pages.values()):
        raise ProductBuildError("hub palette mark does not match")
    for index, (page_id, icon, cover) in enumerate(record.marks):
        token = spec.palette_tokens[index % len(spec.palette_tokens)]
        if icon != hub_icon(token) or cover != hub_cover(token):
            raise ProductBuildError("hub palette mark does not match")
        page = probe.pages.get(page_id)
        if type(page) is not NotionPage or page.icon != icon or page.cover != cover:
            raise ProductBuildError("hub palette mark does not match")


async def _ensure(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> AestheticsRecord:
    require_home_page(probe, stored, spec)
    found = _classify(probe, stored, spec)
    require_notification_dashboard(
        probe,
        stored,
        spec,
        extra_block_ids=found.block_ids,
        page_marks=found.marks or None,
    )
    accents = await _ensure_accents(probe, stored, spec, found.accents)
    guard_operation(probe, OP_AESTHETICS_SAMPLES)
    samples = await _ensure_samples(probe, stored, spec, found.samples)
    marks = await _ensure_marks(probe, stored, spec)
    return AestheticsRecord(accents=accents, samples=samples, marks=marks)


class _Found:
    def __init__(
        self,
        accents: dict[str, str],
        samples: dict[str, str],
        marks: dict[str, tuple[str, str]],
    ) -> None:
        self.accents = accents
        self.samples = samples
        self.marks = marks

    @property
    def block_ids(self) -> tuple[str, ...]:
        return tuple(self.accents.values()) + tuple(self.samples.values())


def _classify(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> _Found:
    expected_accents = {
        accent_content(token.name, token.hex): token.name for token in spec.palette_tokens
    }
    expected_samples = {sample_content(spec, hub.name): hub.name for hub in spec.hubs}
    home_known = _known_home_blocks(stored)
    hub_known: dict[str, str] = {}
    hub_pages = {record.page_id: record.name for record in stored.identity_hubs}
    for record in stored.identity_hubs:
        for block_id in _known_hub_blocks(record):
            hub_known[block_id] = record.name
    accents: dict[str, str] = {}
    samples: dict[str, str] = {}
    for block in probe.blocks.values():
        if block.id in home_known or block.id in hub_known:
            continue
        if block.parent_id == stored.page_id:
            _adopt_accent(block, expected_accents, accents)
            continue
        if block.parent_id in hub_pages:
            _adopt_sample(block, expected_samples, samples, hub_pages[block.parent_id])
            continue
        raise ProductBuildError("aesthetics block is unexpected")
    return _Found(accents, samples, _adopt_marks(probe, stored, spec))


def _known_home_blocks(stored: ProductBuildCheckpoint) -> set[str]:
    identifiers = {stored.shell_block_id}
    for kind, value in stored.dashboard_pieces:
        if kind in _HOME_BLOCK_KINDS:
            identifiers.add(value)
    return identifiers


def _known_hub_blocks(record: IdentityHubRecord) -> set[str]:
    identifiers = {record.navigation_block_id}
    identifiers.update(block_id for _role, block_id in record.sections)
    return identifiers


def _adopt_accent(
    block: object,
    expected: dict[str, str],
    accents: dict[str, str],
) -> None:
    if type(block) is not NotionCalloutBlock:
        raise ProductBuildError("aesthetics block is unexpected")
    token_name = expected.get(block.content)
    if token_name is None:
        raise ProductBuildError("aesthetics block is unexpected")
    if block.icon != AESTHETIC_ICON:
        raise ProductBuildError("aesthetics accent does not match")
    if token_name in accents:
        raise ProductBuildError("aesthetics accent cannot be repaired")
    accents[token_name] = block.id


def _adopt_sample(
    block: object,
    expected: dict[str, str],
    samples: dict[str, str],
    hub_name: str,
) -> None:
    if type(block) is not NotionTextBlock:
        raise ProductBuildError("aesthetics block is unexpected")
    owner = expected.get(block.content)
    if owner is None or owner != hub_name:
        raise ProductBuildError("aesthetics block is unexpected")
    if hub_name in samples:
        raise ProductBuildError("aesthetics sample cannot be repaired")
    samples[hub_name] = block.id


def _adopt_marks(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> dict[str, tuple[str, str]]:
    marks: dict[str, tuple[str, str]] = {}
    for index, record in enumerate(stored.identity_hubs):
        page = probe.pages.get(record.page_id)
        if type(page) is not NotionPage:
            raise ProductBuildError("hub palette mark does not match")
        token = spec.palette_tokens[index % len(spec.palette_tokens)]
        icon = hub_icon(token)
        cover = hub_cover(token)
        if page.icon is None and page.cover is None:
            continue
        if page.icon == icon and page.cover is None:
            marks[page.id] = (icon, cover)
            continue
        if page.icon != icon or page.cover != cover:
            raise ProductBuildError("hub palette mark does not match")
        marks[page.id] = (icon, cover)
    return marks


async def _ensure_accents(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    found: dict[str, str],
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    for token in spec.palette_tokens:
        block_id = found.get(token.name)
        if block_id is None:
            block = await probe.add_callout_block(
                stored.page_id,
                accent_content(token.name, token.hex),
                icon=AESTHETIC_ICON,
            )
            block_id = block.id
        rows.append((token.name, block_id))
    return tuple(rows)


async def _ensure_samples(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
    found: dict[str, str],
) -> tuple[tuple[str, str], ...]:
    pages = {record.name: record.page_id for record in stored.identity_hubs}
    rows: list[tuple[str, str]] = []
    for hub in spec.hubs:
        block_id = found.get(hub.name)
        if block_id is None:
            block = await probe.add_text_block(pages[hub.name], sample_content(spec, hub.name))
            block_id = block.id
        rows.append((hub.name, block_id))
    return tuple(rows)


async def _ensure_marks(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    spec: ProductSpec,
) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    for index, record in enumerate(stored.identity_hubs):
        token = spec.palette_tokens[index % len(spec.palette_tokens)]
        icon = hub_icon(token)
        cover = hub_cover(token)
        page = probe.pages[record.page_id]
        if page.icon is None and page.cover is None:
            await probe.set_icon(page.id, icon)
            await probe.set_cover(page.id, cover)
        elif page.icon == icon and page.cover is None:
            await probe.set_cover(page.id, cover)
        elif page.icon != icon or page.cover != cover:
            raise ProductBuildError("hub palette mark does not match")
        rows.append((page.id, icon, cover))
    return tuple(rows)
