"""One typed progress record for the six fixture product-build phases.

Never rebuild the whole product unless the progress record is unrecoverable.
A recoverable provider failure stores a repair job and resumes from the failed
operation. A missing prior record is an error and writes nothing. The fixture
has no screenshots; captured evidence kind is provider_response.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, cast

PHASES: tuple[str, ...] = (
    "top_level_page_and_design_shell",
    "shared_databases",
    "dashboard_and_navigation",
    "identity_specific_hubs",
    "notification_dashboard",
    "aesthetics_and_content_completion",
)
PHASES_COMPLETE = "build_phases_complete"
RECOVERY_RULE = (
    "Never rebuild the whole product unless the progress record is unrecoverable. "
    "A recoverable provider failure stores a repair job and resumes from the failed "
    "operation. A missing prior record is an error and writes nothing. The fixture "
    "has no screenshots; captured evidence kind is provider_response."
)
PROGRESS_KEY = "progress"
OP_PHASE1_PAGE = "top_level_page_and_design_shell.create_page"
OP_PHASE1_SHELL = "top_level_page_and_design_shell.design_shell"
OP_DASHBOARD_COVER = "dashboard_and_navigation.cover"
OP_HUBS_CREATE = "identity_specific_hubs.create"
OP_NOTIFICATION_DATABASE = "notification_dashboard.database"
OP_AESTHETICS_SAMPLES = "aesthetics_and_content_completion.samples"
_RECOVERIES = frozenset({"recoverable", "unrecoverable"})
_PROGRESS_FIELDS = (
    "completed_operations",
    "deferred_operations",
    "created_notion_ids",
    "property_mappings",
    "page_counts",
    "formula_state",
    "repair_jobs",
    "recovery",
)
_PROGRESS_KEYS = frozenset((*_PROGRESS_FIELDS, "record_digest"))
_COUNT_KEYS = frozenset({"blocks", "databases", "pages"})
_JOB_KEYS = frozenset({"kind", "operation", "phase", "response"})
_FORMULA_KEYS = frozenset({"kind", "name", "property_id"})
_CREATED_KEYS = frozenset(
    {
        "aesthetics",
        "dashboard",
        "databases",
        "design_shell_block_id",
        "hubs",
        "notification",
        "top_level_page_id",
        "workspace_id",
    }
)


class ProductBuildError(ValueError):
    """Raised when a fixture product-build phase cannot proceed."""


class ProviderFailure(Exception):
    """A fixture operation failed and its response must be stored."""

    def __init__(self, operation: str, response: str) -> None:
        self.operation = operation
        self.response = response
        super().__init__(response)


class UnrecoverableCheckpoint(Exception):
    """A signed progress record says the product must be rebuilt from phase 1."""

    def __init__(self, payload: dict[object, object]) -> None:
        self.payload = payload
        super().__init__(RECOVERY_RULE)


@dataclass(frozen=True, slots=True)
class CheckpointEnvelope:
    """A checkpoint object with its progress record removed and checked."""

    payload: dict[object, object] | None
    recovery: str
    repair_jobs: tuple[object, ...]


def reject_duplicate_labels(labels: list[str], message: str) -> None:
    """Raise when a checkpoint list repeats a name."""
    if len(labels) != len(set(labels)):
        raise ProductBuildError(message)


def guard_operation(probe: object, operation: str) -> None:
    """Raise ProviderFailure when the fixture was armed for this operation."""
    if getattr(probe, "fail_operation", None) != operation:
        return
    response = getattr(probe, "fail_response", None)
    if type(response) is not str or response == "":
        response = "provider rejected the operation"
    raise ProviderFailure(operation, response)


def shared_create_operation(kind: str) -> str:
    """Failure point for one shared-database create."""
    return f"shared_databases.create:{kind}"


def raise_recorded(path: Path, phase: str, failure: ProviderFailure) -> NoReturn:
    """Store the provider response and raise it as a product-build error."""
    record_provider_failure(path, failure.operation, failure.response, phase)
    raise ProductBuildError(failure.response) from failure


def load_payload(path: Path, *, allow_unrecoverable: bool = False) -> CheckpointEnvelope:
    """Read one checkpoint file. A missing file returns an empty envelope.

    A forged or tampered progress record raises and leaves the file untouched.
    Later phases pass allow_unrecoverable false, so an unrecoverable record
    raises RECOVERY_RULE and writes nothing.
    """
    if not path.exists():
        return CheckpointEnvelope(None, "absent", ())
    text = path.read_text(encoding="utf-8")
    if text == "" or not text.endswith("\n"):
        raise ProductBuildError("checkpoint is incomplete")
    try:
        decoded = cast(object, json.loads(text))
    except json.JSONDecodeError as error:
        raise ProductBuildError("checkpoint is not JSON") from error
    if type(decoded) is not dict:
        raise ProductBuildError("checkpoint must be an object")
    raw = cast(dict[object, object], decoded)
    progress_value = raw.get(PROGRESS_KEY)
    payload = {key: value for key, value in raw.items() if key != PROGRESS_KEY}
    if progress_value is None:
        return CheckpointEnvelope(payload, "recoverable", ())
    progress = _validate_progress(progress_value, payload.get("checkpoint_names"))
    recovery = progress["recovery"]
    if type(recovery) is not str:
        raise ProductBuildError("progress record is tampered")
    if recovery == "unrecoverable" and not allow_unrecoverable:
        raise ProductBuildError(RECOVERY_RULE)
    jobs = progress["repair_jobs"]
    if type(jobs) is not list:
        raise ProductBuildError("progress record is tampered")
    return CheckpointEnvelope(payload, recovery, tuple(jobs))


def sign_progress(body: Mapping[str, object]) -> dict[str, object]:
    """Return a copy of the progress body with its record digest."""
    unsigned = _unsigned_body(body)
    _require_shape(unsigned)
    signed = dict(unsigned)
    signed["record_digest"] = _digest(unsigned)
    return signed


def write_document(
    path: Path, payload: Mapping[str, object], progress: Mapping[str, object]
) -> None:
    """Atomically write one checkpoint payload and its signed progress record."""
    body = dict(payload)
    body[PROGRESS_KEY] = sign_progress(progress)
    text = json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="ascii")
    os.replace(temporary, path)


def record_provider_failure(path: Path, operation: str, response: str, phase: str) -> None:
    """Append one repair job. The checkpoint phase list is not advanced."""
    job = _repair_job(operation, response, phase)
    if not path.exists():
        progress = _empty_progress()
        progress["repair_jobs"] = [job]
        write_document(path, {"checkpoint_names": []}, progress)
        return
    text = path.read_text(encoding="utf-8")
    if text == "" or not text.endswith("\n"):
        raise ProductBuildError("checkpoint is incomplete")
    try:
        decoded = cast(object, json.loads(text))
    except json.JSONDecodeError as error:
        raise ProductBuildError("checkpoint is not JSON") from error
    if type(decoded) is not dict:
        raise ProductBuildError("checkpoint must be an object")
    raw = cast(dict[object, object], decoded)
    existing = raw.get(PROGRESS_KEY)
    payload = _string_payload(raw)
    if existing is None:
        progress = _compatible_progress(payload.get("checkpoint_names"))
    else:
        checked = _validate_progress(existing, payload.get("checkpoint_names"))
        progress = {key: checked[key] for key in _PROGRESS_FIELDS}
    jobs = progress["repair_jobs"]
    if type(jobs) is not list:
        raise ProductBuildError("progress record is tampered")
    progress["repair_jobs"] = [*jobs, job]
    write_document(path, payload, progress)


def empty_created_ids() -> dict[str, object]:
    """The created-id object used before any provider object is stored."""
    return {
        "aesthetics": None,
        "dashboard": [],
        "databases": [],
        "design_shell_block_id": "",
        "hubs": [],
        "notification": None,
        "top_level_page_id": "",
        "workspace_id": "",
    }


def _empty_progress() -> dict[str, object]:
    return {
        "completed_operations": [],
        "deferred_operations": list(PHASES),
        "created_notion_ids": empty_created_ids(),
        "property_mappings": {},
        "page_counts": {"blocks": 0, "databases": 0, "pages": 0},
        "formula_state": [],
        "repair_jobs": [],
        "recovery": "recoverable",
    }


def _compatible_progress(names: object) -> dict[str, object]:
    if type(names) is not list or not _is_prefix([item for item in names if type(item) is str]):
        raise ProductBuildError("progress record is tampered")
    completed = cast(list[str], names)
    if len(completed) != len(names):
        raise ProductBuildError("progress record is tampered")
    progress = _empty_progress()
    progress["completed_operations"] = completed
    progress["deferred_operations"] = _deferred(completed)
    return progress


def _repair_job(operation: str, response: str, phase: str) -> dict[str, str]:
    if operation == "" or response == "" or phase == "":
        raise ProductBuildError("progress record is tampered")
    if not operation.isascii() or not response.isascii() or not phase.isascii():
        raise ProductBuildError("progress record is tampered")
    return {
        "kind": "provider_response",
        "operation": operation,
        "phase": phase,
        "response": response,
    }


def _validate_progress(value: object, checkpoint_names: object) -> dict[str, object]:
    if type(value) is not dict:
        raise ProductBuildError("progress record is tampered")
    found = cast(dict[object, object], value)
    if not _exact_keys(found, _PROGRESS_KEYS):
        raise ProductBuildError("progress record is tampered")
    unsigned = {key: found[key] for key in _PROGRESS_FIELDS}
    _require_shape(unsigned)
    _reject_non_provider_evidence(unsigned)
    digest = found["record_digest"]
    if type(digest) is not str or digest != _digest(unsigned):
        raise ProductBuildError("progress record is forged")
    _require_alignment(unsigned, checkpoint_names)
    return {key: found[key] for key in _PROGRESS_KEYS}


def _unsigned_body(body: Mapping[str, object]) -> dict[str, object]:
    if not _exact_keys(body, frozenset(_PROGRESS_FIELDS)):
        raise ProductBuildError("progress record is tampered")
    return {key: body[key] for key in _PROGRESS_FIELDS}


def _require_shape(body: Mapping[str, object]) -> None:
    completed = body["completed_operations"]
    deferred = body["deferred_operations"]
    if type(completed) is not list or type(deferred) is not list:
        raise ProductBuildError("progress record is tampered")
    if any(type(item) is not str or not item.isascii() for item in completed):
        raise ProductBuildError("progress record is tampered")
    if any(type(item) is not str or not item.isascii() for item in deferred):
        raise ProductBuildError("progress record is tampered")
    if not _is_prefix(cast(list[str], completed)):
        raise ProductBuildError("progress record is tampered")
    if list(deferred) != _deferred(cast(list[str], completed)):
        raise ProductBuildError("progress record is tampered")
    _require_created(body["created_notion_ids"])
    _require_string_map(body["property_mappings"])
    _require_counts(body["page_counts"])
    _require_formulas(body["formula_state"])
    _require_jobs(body["repair_jobs"])
    recovery = body["recovery"]
    if type(recovery) is not str:
        raise ProductBuildError("progress record is tampered")
    if recovery not in _RECOVERIES:
        raise ProductBuildError("progress record is forged")


def _require_alignment(body: Mapping[str, object], checkpoint_names: object) -> None:
    completed = body["completed_operations"]
    if type(checkpoint_names) is not list or type(completed) is not list:
        return
    if list(checkpoint_names) != list(completed):
        raise ProductBuildError("progress record is tampered")


def _require_created(value: object) -> None:
    if type(value) is not dict:
        raise ProductBuildError("progress record is tampered")
    found = cast(dict[object, object], value)
    if not _exact_keys(found, _CREATED_KEYS):
        raise ProductBuildError("progress record is tampered")
    for key in ("design_shell_block_id", "top_level_page_id", "workspace_id"):
        if type(found[key]) is not str or not cast(str, found[key]).isascii():
            raise ProductBuildError("progress record is tampered")
    if type(found["databases"]) is not list or type(found["dashboard"]) is not list:
        raise ProductBuildError("progress record is tampered")
    if type(found["hubs"]) is not list:
        raise ProductBuildError("progress record is tampered")
    if found["notification"] is not None and type(found["notification"]) is not dict:
        raise ProductBuildError("progress record is tampered")
    if found["aesthetics"] is not None and type(found["aesthetics"]) is not dict:
        raise ProductBuildError("progress record is tampered")
    if not json.dumps(found, sort_keys=True).isascii():
        raise ProductBuildError("progress record is tampered")


def _require_string_map(value: object) -> None:
    if type(value) is not dict:
        raise ProductBuildError("progress record is tampered")
    found = cast(dict[object, object], value)
    for key, item in found.items():
        if type(key) is not str or type(item) is not str:
            raise ProductBuildError("progress record is tampered")
        if not key.isascii() or not item.isascii():
            raise ProductBuildError("progress record is tampered")


def _require_counts(value: object) -> None:
    if type(value) is not dict:
        raise ProductBuildError("progress record is tampered")
    found = cast(dict[object, object], value)
    if not _exact_keys(found, _COUNT_KEYS):
        raise ProductBuildError("progress record is tampered")
    for key in _COUNT_KEYS:
        count = found[key]
        if type(count) is not int or count < 0:
            raise ProductBuildError("progress record is tampered")


def _require_formulas(value: object) -> None:
    if type(value) is not list:
        raise ProductBuildError("progress record is tampered")
    for item in cast(list[object], value):
        if type(item) is not dict:
            raise ProductBuildError("progress record is tampered")
        entry = cast(dict[object, object], item)
        if not _exact_keys(entry, _FORMULA_KEYS):
            raise ProductBuildError("progress record is tampered")
        if any(
            type(entry[key]) is not str or not cast(str, entry[key]).isascii()
            for key in _FORMULA_KEYS
        ):
            raise ProductBuildError("progress record is tampered")


def _require_jobs(value: object) -> None:
    if type(value) is not list:
        raise ProductBuildError("progress record is tampered")
    for item in cast(list[object], value):
        if type(item) is not dict:
            raise ProductBuildError("progress record is tampered")
        entry = cast(dict[object, object], item)
        if not _exact_keys(entry, _JOB_KEYS):
            raise ProductBuildError("progress record is tampered")
        kind = entry["kind"]
        if type(kind) is not str or kind == "" or not kind.isascii():
            raise ProductBuildError("progress record is tampered")
        for key in ("operation", "phase", "response"):
            text = entry[key]
            if type(text) is not str or text == "" or not text.isascii():
                raise ProductBuildError("progress record is tampered")


def _reject_non_provider_evidence(body: Mapping[str, object]) -> None:
    """The fixture has no screenshots. Any other evidence kind is forged."""
    jobs = body["repair_jobs"]
    if type(jobs) is not list:
        raise ProductBuildError("progress record is tampered")
    for item in jobs:
        if type(item) is not dict:
            raise ProductBuildError("progress record is tampered")
        if item.get("kind") != "provider_response":
            raise ProductBuildError("progress record is forged")


def _string_payload(raw: Mapping[object, object]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in raw.items():
        if type(key) is not str or key == PROGRESS_KEY:
            continue
        payload[key] = value
    return payload


def _is_prefix(completed: list[str]) -> bool:
    return completed == list(PHASES[: len(completed)])


def _deferred(completed: list[str]) -> list[str]:
    if completed == list(PHASES):
        return []
    return list(PHASES[len(completed) :])


def _digest(unsigned: Mapping[str, object]) -> str:
    text = json.dumps(dict(unsigned), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _exact_keys[KeyT](mapping: Mapping[KeyT, object], expected: frozenset[str]) -> bool:
    found: set[str] = set()
    for key in mapping:
        if type(key) is not str:
            return False
        found.add(key)
    return found == set(expected)
