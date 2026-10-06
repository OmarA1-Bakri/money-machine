"""Build the one progress record from a product-build checkpoint.

write_checkpoint is the only caller of notion_progress.write_document. Every
phase, repair job, and refused rebuild goes through that function. The
integrity digest is stamped there over the whole payload.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from money_machine.agents.implementations.notion_progress import (
    PHASES,
    PHASES_COMPLETE,
    ProductBuildError,
    empty_created_ids,
    write_document,
)


class _Hub(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def page_id(self) -> str: ...

    @property
    def sections(self) -> tuple[tuple[str, str], ...]: ...

    @property
    def navigation_block_id(self) -> str: ...

    @property
    def views(self) -> tuple[tuple[str, str], ...]: ...


class _Notification(Protocol):
    @property
    def database_id(self) -> str: ...

    @property
    def row_page_id(self) -> str: ...

    @property
    def formulas(self) -> tuple[tuple[str, str, str], ...]: ...

    @property
    def relations(self) -> tuple[tuple[str, str], ...]: ...

    @property
    def rollups(self) -> tuple[tuple[str, str], ...]: ...

    @property
    def samples(self) -> tuple[tuple[str, str], ...]: ...


class _Aesthetics(Protocol):
    @property
    def accents(self) -> tuple[tuple[str, str], ...]: ...

    @property
    def samples(self) -> tuple[tuple[str, str], ...]: ...


class CheckpointView(Protocol):
    """The checkpoint fields the progress record stores. Read-only for frozen records."""

    @property
    def checkpoint_names(self) -> tuple[str, ...]: ...

    @property
    def next_phase(self) -> str: ...

    @property
    def build_kind(self) -> str: ...

    @property
    def build_version(self) -> int: ...

    @property
    def palette_name(self) -> str: ...

    @property
    def palette_tokens(self) -> tuple[tuple[str, str], ...]: ...

    @property
    def product_id(self) -> str: ...

    @property
    def spec_id(self) -> str: ...

    @property
    def recorded_at(self) -> object: ...

    @property
    def page_id(self) -> str: ...

    @property
    def workspace_id(self) -> str: ...

    @property
    def shell_block_id(self) -> str: ...

    @property
    def database_ids(self) -> tuple[tuple[str, str], ...]: ...

    @property
    def dashboard_pieces(self) -> tuple[tuple[str, str], ...]: ...

    @property
    def identity_hubs(self) -> tuple[_Hub, ...]: ...

    @property
    def notification_dashboard(self) -> _Notification | None: ...

    @property
    def aesthetics(self) -> _Aesthetics | None: ...


def write_checkpoint(
    path: Path,
    checkpoint: CheckpointView | None = None,
    references: Mapping[str, object] | None = None,
    *,
    preserved_payload: Mapping[str, object] | None = None,
    progress: Mapping[str, object] | None = None,
) -> None:
    """Write one checkpoint through the single progress writer."""
    if preserved_payload is not None:
        if progress is None:
            raise ProductBuildError("progress record is missing")
        payload = dict(preserved_payload)
        body = dict(progress)
    else:
        if checkpoint is None or references is None:
            raise ProductBuildError("checkpoint is incomplete")
        recorded_at = checkpoint.recorded_at
        isoformat = getattr(recorded_at, "isoformat", None)
        if not callable(isoformat):
            raise TypeError("checkpoint recorded_at must be a datetime")
        payload = {
            "build_kind": checkpoint.build_kind,
            "build_version": checkpoint.build_version,
            "checkpoint_names": list(checkpoint.checkpoint_names),
            "palette_name": checkpoint.palette_name,
            "palette_tokens": [list(token) for token in checkpoint.palette_tokens],
            "product_id": checkpoint.product_id,
            "provider_object_references": dict(references),
            "recorded_at": isoformat(),
            "spec_id": checkpoint.spec_id,
        }
        body = progress_from_checkpoint(checkpoint)
    write_document(path, payload, body)


def progress_from_checkpoint(checkpoint: CheckpointView) -> dict[str, object]:
    """One progress body for whichever build phase the checkpoint has reached."""
    completed = list(checkpoint.checkpoint_names)
    if checkpoint.next_phase == PHASES_COMPLETE or completed == list(PHASES):
        deferred: list[str] = []
    else:
        deferred = [phase for phase in PHASES if phase not in completed]
    return {
        "completed_operations": completed,
        "deferred_operations": deferred,
        "created_notion_ids": _created_ids(checkpoint),
        "property_mappings": _mappings(checkpoint),
        "page_counts": _counts(checkpoint),
        "formula_state": _formulas(checkpoint),
        "repair_jobs": [],
        "recovery": "recoverable",
    }


def _created_ids(checkpoint: CheckpointView) -> dict[str, object]:
    created = empty_created_ids()
    created["design_shell_block_id"] = checkpoint.shell_block_id
    created["top_level_page_id"] = checkpoint.page_id
    created["workspace_id"] = checkpoint.workspace_id
    created["databases"] = [
        {"database_id": database_id, "kind": kind} for kind, database_id in checkpoint.database_ids
    ]
    created["dashboard"] = [
        {"kind": kind, "value": value} for kind, value in checkpoint.dashboard_pieces
    ]
    created["hubs"] = [
        {
            "name": hub.name,
            "navigation_block_id": hub.navigation_block_id,
            "page_id": hub.page_id,
            "sections": [{"block_id": block_id, "role": role} for role, block_id in hub.sections],
            "views": [{"slug": slug, "view_id": view_id} for slug, view_id in hub.views],
        }
        for hub in checkpoint.identity_hubs
    ]
    notice = checkpoint.notification_dashboard
    if notice is not None:
        created["notification"] = {
            "database_id": notice.database_id,
            "formulas": [
                {"kind": kind, "name": name, "property_id": property_id}
                for kind, name, property_id in notice.formulas
            ],
            "relations": [
                {"data_type": data_type, "property_id": property_id}
                for data_type, property_id in notice.relations
            ],
            "rollups": [
                {"name": name, "property_id": property_id} for name, property_id in notice.rollups
            ],
            "row_page_id": notice.row_page_id,
            "samples": [{"kind": kind, "page_id": page_id} for kind, page_id in notice.samples],
        }
    record = checkpoint.aesthetics
    if record is not None:
        created["aesthetics"] = {
            "accents": [
                {"block_id": block_id, "token": token} for token, block_id in record.accents
            ],
            "samples": [{"block_id": block_id, "hub": hub} for hub, block_id in record.samples],
        }
    return created


def _mappings(checkpoint: CheckpointView) -> dict[str, str]:
    mappings = {
        "design_shell_block_id": "design_shell_block_id",
        "product_id": "product_id",
        "product_spec_id": "product_spec_id",
    }
    if checkpoint.notification_dashboard is not None:
        mappings["buyer_name"] = "Buyer name"
        mappings["sample_marker"] = "sample_marker"
    return mappings


def _counts(checkpoint: CheckpointView) -> dict[str, int]:
    blocks = 1
    blocks += sum(
        1
        for kind, _value in checkpoint.dashboard_pieces
        if kind in {"callout", "greeting", "hub_navigation"}
    )
    for hub in checkpoint.identity_hubs:
        blocks += len(hub.sections) + 1
    pages = 1 + len(checkpoint.identity_hubs)
    databases = len(checkpoint.database_ids)
    notice = checkpoint.notification_dashboard
    if notice is not None:
        databases += 1
        pages += 1 + len(notice.samples)
    record = checkpoint.aesthetics
    if record is not None:
        blocks += len(record.accents) + len(record.samples)
    return {"blocks": blocks, "databases": databases, "pages": pages}


def _formulas(checkpoint: CheckpointView) -> list[dict[str, str]]:
    notice = checkpoint.notification_dashboard
    if notice is None:
        return []
    return [
        {"kind": kind, "name": name, "property_id": property_id}
        for kind, name, property_id in notice.formulas
    ]
