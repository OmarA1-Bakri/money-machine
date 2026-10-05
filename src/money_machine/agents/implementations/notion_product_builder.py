"""A07 fixture phase 1: top-level page and design shell.

Session 07 prompt action 1. This module stores the top-level page and design
shell. Shared databases resume that checkpoint from notion_shared_databases.
A07, A08, and A09 stay DESIGNED. This module does not commission an agent,
open a network connection, or run a later build phase. The catalogue
ProductSpec is not an input.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PosixPath, WindowsPath
from typing import cast
from uuid import UUID

from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.domain import (
    NotionCalloutBlock,
    NotionPage,
    NotionTextBlock,
)
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter

PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL = "top_level_page_and_design_shell"
PHASE_SHARED_DATABASES = "shared_databases"
PHASE_DASHBOARD_AND_NAVIGATION = "dashboard_and_navigation"
BUILD_PHASES: tuple[str, ...] = (
    PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,
    PHASE_SHARED_DATABASES,
    PHASE_DASHBOARD_AND_NAVIGATION,
    "identity_specific_hubs",
    "notification_dashboard",
    "aesthetics_and_content_completion",
)
BUILD_KIND_PRIMARY = "PRIMARY"
BUILD_VERSION = 1
DESIGN_SHELL_ICON = "🎨"
SPEC_ID_PROPERTY = "product_spec_id"
PRODUCT_ID_PROPERTY = "product_id"
SHELL_BLOCK_PROPERTY = "design_shell_block_id"
_TOP_LEVEL_PARENT = "workspace"
_PATH_TYPES = (PosixPath, WindowsPath)
CHECKPOINT_KEYS = frozenset(
    {
        "build_kind",
        "build_version",
        "checkpoint_names",
        "palette_name",
        "palette_tokens",
        "product_id",
        "provider_object_references",
        "recorded_at",
        "spec_id",
    }
)
PROVIDER_KEYS = frozenset({"design_shell_block_id", "top_level_page_id", "workspace_id"})


class ProductBuildError(ValueError):
    """Raised when a fixture product-build phase cannot proceed."""


@dataclass(frozen=True, slots=True)
class ProductBuildCheckpoint:
    """Persisted build progress. The next phase is not executed."""

    spec_id: str
    product_id: str
    build_kind: str
    build_version: int
    checkpoint_names: tuple[str, ...]
    next_phase: str
    page_id: str
    workspace_id: str
    shell_block_id: str
    palette_name: str
    palette_tokens: tuple[tuple[str, str], ...]
    recorded_at: datetime
    database_ids: tuple[tuple[str, str], ...] = ()


def design_shell_content(spec: ProductSpec) -> str:
    """Palette shell only. Hubs, databases, and variants are later phases."""
    require_spec(spec)
    _reject_shell_line_breaks(spec)
    lines = [f"identity:{spec.identity}", f"palette:{spec.palette_name}"]
    lines.extend(f"{token.name} {token.hex}" for token in spec.palette_tokens)
    return "\n".join(lines)


async def build_top_level_page_and_design_shell(
    spec: object,
    probe: object,
    checkpoint_path: object,
    *,
    recorded_at: object,
) -> ProductBuildCheckpoint:
    """Create the phase-1 page and shell, or resume when that phase is already stored."""
    validated = require_spec(spec)
    fixture = require_probe(probe)
    path = require_path(checkpoint_path)
    moment = require_datetime(recorded_at)
    _reject_shell_line_breaks(validated)
    stored = _read_checkpoint(path)
    if stored is not None:
        require_same_spec(stored, validated)
    page = find_spec_page(fixture, str(validated.spec_id))
    if stored is not None:
        return resume_stored(fixture, stored, page, validated)
    if page is None:
        page = await _create_top_level_page(fixture, validated)
    else:
        _require_page_matches_spec(page, validated, fixture)
    shell = _find_shell(fixture, page, validated)
    if shell is None:
        shell = await fixture.add_callout_block(
            page.id, design_shell_content(validated), icon=DESIGN_SHELL_ICON
        )
        page.properties[SHELL_BLOCK_PROPERTY] = shell.id
    checkpoint = _checkpoint_for(validated, page, shell, moment)
    _write_checkpoint(path, checkpoint)
    return checkpoint


def require_spec(spec: object) -> ProductSpec:
    if type(spec) is not ProductSpec:
        raise ProductBuildError("phase 1 requires a validated ProductSpec")
    return spec


def require_probe(probe: object) -> FixtureNotionAdapter:
    if type(probe) is not FixtureNotionAdapter:
        raise ProductBuildError("phase 1 requires the fixture Notion probe")
    return probe


def require_path(checkpoint_path: object) -> Path:
    if type(checkpoint_path) not in _PATH_TYPES:
        raise ProductBuildError("checkpoint path must be a path")
    path = cast(Path, checkpoint_path)
    if not path.parent.is_dir():
        raise ProductBuildError("checkpoint directory is missing")
    if path.exists() and path.is_dir():
        raise ProductBuildError("checkpoint path is a directory")
    return path


def require_datetime(value: object) -> datetime:
    if type(value) is not datetime:
        raise ProductBuildError("recorded_at must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProductBuildError("recorded_at must be timezone-aware")
    return value


def _reject_shell_line_breaks(spec: ProductSpec) -> None:
    fields = [spec.identity, spec.palette_name]
    fields.extend(token.name for token in spec.palette_tokens)
    if any("\n" in field or "\r" in field for field in fields):
        raise ProductBuildError("design shell fields must be single lines")


def require_same_spec(stored: ProductBuildCheckpoint, spec: ProductSpec) -> None:
    if stored.spec_id != str(spec.spec_id) or stored.product_id != str(spec.product_id):
        raise ProductBuildError("checkpoint belongs to a different ProductSpec")
    if stored.palette_name != spec.palette_name or stored.palette_tokens != _palette(spec):
        raise ProductBuildError("checkpoint palette does not match the ProductSpec")


def _palette(spec: ProductSpec) -> tuple[tuple[str, str], ...]:
    return tuple((token.name, token.hex) for token in spec.palette_tokens)


def _workspace_id(probe: FixtureNotionAdapter) -> str:
    workspaces = list(probe.workspaces.values())
    if len(workspaces) != 1:
        raise ProductBuildError("fixture probe must have exactly one workspace")
    workspace_id = workspaces[0].id
    if type(workspace_id) is not str or workspace_id.strip() != workspace_id or workspace_id == "":
        raise ProductBuildError("fixture workspace id is invalid")
    return workspace_id


def find_spec_page(probe: FixtureNotionAdapter, spec_id: str) -> NotionPage | None:
    matches = [
        page
        for page in probe.pages.values()
        if type(page) is NotionPage and _property(page, SPEC_ID_PROPERTY) == spec_id
    ]
    if len(matches) > 1:
        raise ProductBuildError("fixture probe has more than one page for this ProductSpec")
    if not matches:
        return None
    return matches[0]


def _property(page: NotionPage, key: str) -> str | None:
    value = page.properties.get(key)
    if value is None:
        return None
    if type(value) is not str:
        raise ProductBuildError(f"page property {key} must be a string")
    return value


def _require_page_matches_spec(
    page: NotionPage, spec: ProductSpec, probe: FixtureNotionAdapter
) -> None:
    if page.parent_type != _TOP_LEVEL_PARENT or page.parent_id != _workspace_id(probe):
        raise ProductBuildError("existing page is not top level")
    if page.title != spec.title:
        raise ProductBuildError("existing page title does not match the ProductSpec")
    if _property(page, PRODUCT_ID_PROPERTY) != str(spec.product_id):
        raise ProductBuildError("existing page product id does not match the ProductSpec")
    if page.is_published is not False:
        raise ProductBuildError("existing page must stay unpublished in phase 1")


async def _create_top_level_page(probe: FixtureNotionAdapter, spec: ProductSpec) -> NotionPage:
    workspace_id = _workspace_id(probe)
    page = await probe.create_page(
        title=spec.title,
        parent_id=workspace_id,
        parent_type=_TOP_LEVEL_PARENT,
    )
    page.properties[SPEC_ID_PROPERTY] = str(spec.spec_id)
    page.properties[PRODUCT_ID_PROPERTY] = str(spec.product_id)
    return page


def _page_children(
    probe: FixtureNotionAdapter, page_id: str
) -> list[NotionTextBlock | NotionCalloutBlock]:
    return [block for block in probe.blocks.values() if block.parent_id == page_id]


def _find_shell(
    probe: FixtureNotionAdapter, page: NotionPage, spec: ProductSpec
) -> NotionCalloutBlock | None:
    expected = design_shell_content(spec)
    children = _page_children(probe, page.id)
    matches = [
        block
        for block in children
        if type(block) is NotionCalloutBlock
        and block.content == expected
        and block.icon == DESIGN_SHELL_ICON
    ]
    if len(matches) > 1:
        raise ProductBuildError("fixture probe has more than one design shell")
    if len(matches) == 1:
        shell = matches[0]
        if any(block is not shell for block in children):
            raise ProductBuildError("phase 1 page has a block that is not the design shell")
        marked = _property(page, SHELL_BLOCK_PROPERTY)
        if marked is not None and marked != shell.id:
            raise ProductBuildError("design shell block id does not match the page")
        page.properties[SHELL_BLOCK_PROPERTY] = shell.id
        return shell
    if children:
        raise ProductBuildError("phase 1 page has a block that is not the design shell")
    if _property(page, SHELL_BLOCK_PROPERTY) is not None:
        raise ProductBuildError("design shell block is missing")
    return None


def resume_stored(
    probe: FixtureNotionAdapter,
    stored: ProductBuildCheckpoint,
    page: NotionPage | None,
    spec: ProductSpec,
) -> ProductBuildCheckpoint:
    if stored.workspace_id != _workspace_id(probe):
        raise ProductBuildError("checkpoint workspace does not match the fixture probe")
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
    if _property(page, PRODUCT_ID_PROPERTY) != str(spec.product_id):
        raise ProductBuildError("checkpoint page product id does not match the ProductSpec")
    if page.is_published is not False:
        raise ProductBuildError("checkpoint page must stay unpublished in phase 1")
    shell = probe.blocks.get(stored.shell_block_id)
    if type(shell) is not NotionCalloutBlock or shell.parent_id != page.id:
        raise ProductBuildError("checkpoint design shell is missing")
    if shell.content != design_shell_content(spec) or shell.icon != DESIGN_SHELL_ICON:
        raise ProductBuildError("checkpoint design shell does not match the ProductSpec")
    if any(block is not shell for block in _page_children(probe, page.id)):
        raise ProductBuildError("checkpoint page has a block that is not the design shell")
    if _property(page, SHELL_BLOCK_PROPERTY) != stored.shell_block_id:
        raise ProductBuildError("checkpoint design shell id does not match the page")
    return stored


def _checkpoint_for(
    spec: ProductSpec,
    page: NotionPage,
    shell: NotionCalloutBlock,
    recorded_at: datetime,
) -> ProductBuildCheckpoint:
    workspace_id = page.parent_id
    if type(workspace_id) is not str or workspace_id == "":
        raise ProductBuildError("top-level page has no workspace")
    completed = (PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,)
    return ProductBuildCheckpoint(
        spec_id=str(spec.spec_id),
        product_id=str(spec.product_id),
        build_kind=BUILD_KIND_PRIMARY,
        build_version=BUILD_VERSION,
        checkpoint_names=completed,
        next_phase=BUILD_PHASES[len(completed)],
        page_id=page.id,
        workspace_id=workspace_id,
        shell_block_id=shell.id,
        palette_name=spec.palette_name,
        palette_tokens=_palette(spec),
        recorded_at=recorded_at,
    )


def _read_checkpoint(path: Path) -> ProductBuildCheckpoint | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if text == "" or not text.endswith("\n"):
        raise ProductBuildError("checkpoint is incomplete")
    try:
        decoded = cast(object, json.loads(text))
    except json.JSONDecodeError as error:
        raise ProductBuildError("checkpoint is not JSON") from error
    return parse_checkpoint(decoded)


def parse_checkpoint(decoded: object) -> ProductBuildCheckpoint:
    if type(decoded) is not dict:
        raise ProductBuildError("checkpoint must be an object")
    payload = cast(dict[object, object], decoded)
    if not exact_keys(payload, CHECKPOINT_KEYS):
        raise ProductBuildError("checkpoint fields are missing or unsupported")
    if payload["build_kind"] != BUILD_KIND_PRIMARY:
        raise ProductBuildError("checkpoint build kind must be PRIMARY")
    if type(payload["build_version"]) is not int or payload["build_version"] != BUILD_VERSION:
        raise ProductBuildError("checkpoint build version must be 1")
    names = payload["checkpoint_names"]
    if type(names) is not list or names != [PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL]:
        raise ProductBuildError("checkpoint must record only phase 1")
    references = payload["provider_object_references"]
    if type(references) is not dict:
        raise ProductBuildError("provider references must be an object")
    refs = cast(dict[object, object], references)
    if not exact_keys(refs, PROVIDER_KEYS):
        raise ProductBuildError("provider references are missing or unsupported")
    page_id = require_token(refs["top_level_page_id"], "top_level_page_id")
    workspace_id = require_token(refs["workspace_id"], "workspace_id")
    shell_block_id = require_token(refs["design_shell_block_id"], "design_shell_block_id")
    spec_id = _require_uuid(payload["spec_id"], "spec_id")
    product_id = _require_uuid(payload["product_id"], "product_id")
    palette_name = require_token(payload["palette_name"], "palette_name")
    tokens = _require_tokens(payload["palette_tokens"])
    recorded_at = _require_stored_datetime(payload["recorded_at"])
    return ProductBuildCheckpoint(
        spec_id=spec_id,
        product_id=product_id,
        build_kind=BUILD_KIND_PRIMARY,
        build_version=BUILD_VERSION,
        checkpoint_names=(PHASE_TOP_LEVEL_PAGE_AND_DESIGN_SHELL,),
        next_phase=PHASE_SHARED_DATABASES,
        page_id=page_id,
        workspace_id=workspace_id,
        shell_block_id=shell_block_id,
        palette_name=palette_name,
        palette_tokens=tokens,
        recorded_at=recorded_at,
    )


def exact_keys(mapping: dict[object, object], expected: frozenset[str]) -> bool:
    found: set[str] = set()
    for key in mapping:
        if type(key) is not str:
            return False
        found.add(key)
    return found == set(expected)


def require_token(value: object, field: str) -> str:
    if type(value) is not str or value == "" or value.strip() != value:
        raise ProductBuildError(f"checkpoint {field} must be a non-empty string")
    return value


def _require_uuid(value: object, field: str) -> str:
    text = require_token(value, field)
    try:
        parsed = UUID(text)
    except ValueError as error:
        raise ProductBuildError(f"checkpoint {field} must be a UUID") from error
    if str(parsed) != text:
        raise ProductBuildError(f"checkpoint {field} must be a canonical UUID")
    return text


def _require_tokens(value: object) -> tuple[tuple[str, str], ...]:
    if type(value) is not list or not value:
        raise ProductBuildError("checkpoint palette tokens must be a non-empty list")
    tokens: list[tuple[str, str]] = []
    for item in cast(list[object], value):
        if type(item) is not list or len(item) != 2:
            raise ProductBuildError("checkpoint palette token must be a name and hex")
        pair = cast(list[object], item)
        name = require_token(pair[0], "palette token name")
        hex_value = require_token(pair[1], "palette token hex")
        tokens.append((name, hex_value))
    return tuple(tokens)


def _require_stored_datetime(value: object) -> datetime:
    if type(value) is not str:
        raise ProductBuildError("checkpoint recorded_at must be a string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ProductBuildError("checkpoint recorded_at must be a datetime") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProductBuildError("checkpoint recorded_at must be timezone-aware")
    return parsed


def _write_checkpoint(path: Path, checkpoint: ProductBuildCheckpoint) -> None:
    payload = {
        "build_kind": checkpoint.build_kind,
        "build_version": checkpoint.build_version,
        "checkpoint_names": list(checkpoint.checkpoint_names),
        "palette_name": checkpoint.palette_name,
        "palette_tokens": [list(token) for token in checkpoint.palette_tokens],
        "product_id": checkpoint.product_id,
        "provider_object_references": {
            "design_shell_block_id": checkpoint.shell_block_id,
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
