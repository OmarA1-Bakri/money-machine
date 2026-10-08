"""One typed progress record for the six fixture product-build phases.

Never rebuild the whole product unless the progress record is unrecoverable.
A recoverable provider failure stores a repair job and resumes from the failed
operation. A missing prior record is an error and writes nothing. A refused
rebuild makes no fixture writes and appends one rebuild_refused job through
write_checkpoint. The integrity digest covers the whole payload. It detects
accidental corruption. It is not a signature and it is not tamper-proof against
someone who can recompute it. The fixture has no screenshots; captured evidence
kind is provider_response.
"""

from __future__ import annotations

import contextlib
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
    "operation. A missing prior record is an error and writes nothing. "
    "A refused rebuild appends one rebuild_refused job and does not mutate the fixture. "
    "The fixture has no screenshots; captured evidence kind is provider_response."
)
PROGRESS_KEY = "progress"
OP_PHASE1_PAGE = "top_level_page_and_design_shell.create_page"
OP_PHASE1_SHELL = "top_level_page_and_design_shell.design_shell"
OP_DASHBOARD_COVER = "dashboard_and_navigation.cover"
OP_HUBS_CREATE = "identity_specific_hubs.create"
OP_NOTIFICATION_DATABASE = "notification_dashboard.database"
OP_AESTHETICS_SAMPLES = "aesthetics_and_content_completion.samples"
OP_VARIANTS = "variants.duplicate"
OP_QA = "qa.duplicate"
OP_REBUILD = "top_level_page_and_design_shell.rebuild"
REBUILD_REFUSED = "rebuild_refused"
_ACCEPTED_JOB_KINDS = frozenset({"provider_response", REBUILD_REFUSED})
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
        "variants",
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
    """An integrity digest says the product must be rebuilt from phase 1."""

    def __init__(self, payload: dict[object, object]) -> None:
        self.payload = payload
        super().__init__(RECOVERY_RULE)


@dataclass(frozen=True, slots=True)
class CheckpointEnvelope:
    """A checkpoint object with its progress record removed and checked."""

    payload: dict[object, object] | None
    recovery: str
    repair_jobs: tuple[object, ...]
    created_notion_ids: dict[str, object] | None = None


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
    """Store the provider response and raise it as a product-build error.

    A missing prior record raises the provider response and writes nothing.
    """
    if path.exists():
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
    if PROGRESS_KEY not in raw or progress_value is None:
        raise ProductBuildError("progress record is missing")
    progress = _validate_progress(progress_value, payload.get("checkpoint_names"), raw)
    recovery = progress["recovery"]
    if type(recovery) is not str:
        raise ProductBuildError("progress record is tampered")
    if recovery == "unrecoverable" and not allow_unrecoverable:
        raise ProductBuildError(RECOVERY_RULE)
    jobs = progress["repair_jobs"]
    if type(jobs) is not list:
        raise ProductBuildError("progress record is tampered")
    created = progress["created_notion_ids"]
    if type(created) is not dict:
        raise ProductBuildError("progress record is tampered")
    return CheckpointEnvelope(payload, recovery, tuple(jobs), cast(dict[str, object], created))


def stamp_integrity_digest(document: Mapping[str, object]) -> dict[str, object]:
    """Return a copy of the checkpoint with a recomputed integrity digest.

    The digest covers the whole payload except ``record_digest``. It detects
    accidental corruption. It is not a signature and it is not tamper-proof
    against someone who can recompute it. A recomputed digest is accepted.
    """
    raw = dict(document)
    progress = raw.get(PROGRESS_KEY)
    if type(progress) is not dict:
        raise ProductBuildError("progress record is missing")
    unsigned_source = {
        key: value
        for key, value in cast(Mapping[object, object], progress).items()
        if key != "record_digest"
    }
    unsigned = _unsigned_body(cast(Mapping[str, object], unsigned_source))
    _require_shape(unsigned)
    raw[PROGRESS_KEY] = unsigned
    digest = _digest(raw)
    stored = dict(unsigned)
    stored["record_digest"] = digest
    raw[PROGRESS_KEY] = stored
    return raw


def _pid_alive(pid: int) -> bool:
    """True when a process still owns this pid. A dead pid's temp is stale."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _remove_dead_temps(path: Path) -> None:
    """Delete this checkpoint's leftover temps. The name is matched literally.

    A glob would treat ``[`` in the file name as a character class and could
    delete a different file. A temp whose pid is still running is left alone.
    """
    marker = f".{path.name}."
    suffix = ".tmp"
    for stale in path.parent.iterdir():
        name = stale.name
        if not name.startswith(marker) or not name.endswith(suffix):
            continue
        pid_text = name[len(marker) : -len(suffix)]
        if pid_text.isdigit() and _pid_alive(int(pid_text)):
            continue
        with contextlib.suppress(OSError):
            stale.unlink()


def write_document(
    path: Path, payload: Mapping[str, object], progress: Mapping[str, object]
) -> None:
    """Atomically write one checkpoint. Called only from write_checkpoint."""
    unsigned = _unsigned_body(progress)
    _require_shape(unsigned)
    body = dict(payload)
    body[PROGRESS_KEY] = unsigned
    stored = dict(unsigned)
    stored["record_digest"] = _digest(body)
    body[PROGRESS_KEY] = stored
    text = json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n"
    _remove_dead_temps(path)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(text, encoding="ascii")
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            temporary.unlink(missing_ok=True)
        raise


def record_provider_failure(path: Path, operation: str, response: str, phase: str) -> None:
    """Append one provider_response job through write_checkpoint.

    The checkpoint phase list is not advanced. A missing file raises and writes
    nothing.
    """
    _append_job(path, _repair_job(operation, response, phase))


def append_refused_rebuild(path: Path, reason: str) -> None:
    """Append one rebuild_refused job through write_checkpoint.

    Every other field of the record stays byte-identical. The integrity digest
    covers the whole payload, so it is recomputed. That recomputed digest is the
    only other permitted difference.
    """
    _append_job(path, _repair_job(OP_REBUILD, reason, PHASES[0], kind=REBUILD_REFUSED))


def _append_job(path: Path, job: Mapping[str, str]) -> None:
    if not path.exists():
        raise ProductBuildError("a provider failure with no prior record writes nothing")
    raw = _load_object(path)
    progress_value = raw.get(PROGRESS_KEY)
    if PROGRESS_KEY not in raw or progress_value is None:
        raise ProductBuildError("progress record is missing")
    checked = _validate_progress(progress_value, raw.get("checkpoint_names"), raw)
    progress = {key: checked[key] for key in _PROGRESS_FIELDS}
    jobs = progress["repair_jobs"]
    if type(jobs) is not list:
        raise ProductBuildError("progress record is tampered")
    progress["repair_jobs"] = [*list(jobs), dict(job)]
    _write_through_checkpoint(path, _string_payload(raw), progress)


def _write_through_checkpoint(
    path: Path, payload: Mapping[str, object], progress: Mapping[str, object]
) -> None:
    # notion_progress_record imports this module, so this import stays local.
    from money_machine.agents.implementations.notion_progress_record import write_checkpoint

    write_checkpoint(path, preserved_payload=payload, progress=progress)


def _load_object(path: Path) -> dict[object, object]:
    text = path.read_text(encoding="utf-8")
    if text == "" or not text.endswith("\n"):
        raise ProductBuildError("checkpoint is incomplete")
    try:
        decoded = cast(object, json.loads(text))
    except json.JSONDecodeError as error:
        raise ProductBuildError("checkpoint is not JSON") from error
    if type(decoded) is not dict:
        raise ProductBuildError("checkpoint must be an object")
    return cast(dict[object, object], decoded)


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
        "variants": None,
        "workspace_id": "",
    }


def _repair_job(
    operation: str, response: str, phase: str, *, kind: str = "provider_response"
) -> dict[str, str]:
    if kind not in _ACCEPTED_JOB_KINDS:
        raise ProductBuildError("progress record is forged")
    if operation == "" or response == "" or phase == "":
        raise ProductBuildError("progress record is tampered")
    if not operation.isascii() or not response.isascii() or not phase.isascii():
        raise ProductBuildError("progress record is tampered")
    return {
        "kind": kind,
        "operation": operation,
        "phase": phase,
        "response": response,
    }


def _validate_progress(
    value: object, checkpoint_names: object, document: Mapping[object, object]
) -> dict[str, object]:
    if type(value) is not dict:
        raise ProductBuildError("progress record is tampered")
    found = cast(dict[object, object], value)
    if not _exact_keys(found, _PROGRESS_KEYS):
        raise ProductBuildError("progress record is tampered")
    unsigned = {key: found[key] for key in _PROGRESS_FIELDS}
    _require_shape(unsigned)
    _reject_non_provider_evidence(unsigned)
    digest = found["record_digest"]
    covered = _string_payload(document)
    covered[PROGRESS_KEY] = unsigned
    if type(digest) is not str or digest != _digest(covered):
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
    if found["variants"] is not None and type(found["variants"]) is not list:
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
    """Screenshot evidence is forged. provider_response and rebuild_refused are kept."""
    jobs = body["repair_jobs"]
    if type(jobs) is not list:
        raise ProductBuildError("progress record is tampered")
    for item in jobs:
        if type(item) is not dict:
            raise ProductBuildError("progress record is tampered")
        if item.get("kind") not in _ACCEPTED_JOB_KINDS:
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
