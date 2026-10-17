"""Earn the Session 13 matrix, path, failure, backup, and control-file keys.

The proof reads the matrix, runs the fixture paths, runs each named failure
injection, restores the fixture snapshot twice, checks the continuity files,
refuses a live publish, and does not open a socket. Completion records the
closure key. This proof requires that completed pointer.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from money_machine.assets.backup_restore import (
    BackupRefusal,
    FixtureStore,
    artifact_sha256,
    backup,
    restore_snapshot,
    sample_store,
    take_snapshot,
)
from money_machine.assets.failure_injection import (
    INJECTIONS,
    FailureInjectionError,
    run_failure_injections,
)
from money_machine.assets.implementation_matrix import (
    MatrixRefusal,
    MatrixStatus,
    build_matrix,
)
from money_machine.assets.synthetic_paths import (
    BROKEN_LINK_STEPS,
    CULL_STEPS,
    DEDUPE_STEPS,
    MAIN_STEPS,
    REPAIR_STEPS,
    PathReceipt,
    SyntheticPathRefusal,
    run_synthetic_paths,
    simulate_publish,
)

MATRIX_EVIDENCE_KEY = "implementation_matrix_recorded"
SYNTHETIC_EVIDENCE_KEY = "synthetic_paths_implemented"
FAILURE_EVIDENCE_KEY = "failure_injection_implemented"
BACKUP_EVIDENCE_KEY = "backup_restore_fixture_implemented"
CONTROL_EVIDENCE_KEY = "control_files_and_checkpoint_current"
_CLOSURE_EVIDENCE_KEY = "evidence_closure_commit_recorded"
EARNED_EVIDENCE_KEYS = frozenset(
    {
        MATRIX_EVIDENCE_KEY,
        SYNTHETIC_EVIDENCE_KEY,
        FAILURE_EVIDENCE_KEY,
        BACKUP_EVIDENCE_KEY,
        CONTROL_EVIDENCE_KEY,
    }
)
_FAILURE_RESULTS = {
    "worker_crash": ("RECOVERED", "READY", "can_retry=true;next_attempt=1;status=READY"),
    "scheduler_restart": ("RECOVERED", "READY", "ready=1;count=2"),
    "database_reconnect": ("RECOVERED", "CONNECTED", "attempts=2;status=CONNECTED"),
    "expired_lease": ("BLOCKED", "LEASE_EXPIRED", "executed=false"),
    "duplicate_event": ("RECOVERED", "DEDUPED", "length=1"),
    "duplicate_publish_request": ("RECOVERED", "CONFIRMED", "creates=1;effect=CONFIRMED"),
    "provider_timeout_before_response": ("RECOVERED", "CONFIRMED", "creates=2;effect=CONFIRMED"),
    "provider_timeout_after_success": (
        "RECOVERED",
        "CONFIRMED",
        "creates=1;effect=CONFIRMED;provider=provider-observed",
    ),
    "expired_etsy_token": (
        "BLOCKED",
        "CREDENTIAL_EXPIRED",
        "read_env=false;state=CREDENTIAL_EXPIRED",
    ),
    "expired_notion_session": (
        "BLOCKED",
        "SESSION_EXPIRED",
        "read_env=false;state=SESSION_EXPIRED",
    ),
    "malformed_llm_output": ("BLOCKED", "MALFORMED_OUTPUT", "parsed=false"),
    "unavailable_llm_provider": ("BLOCKED", "PROVIDER_UNAVAILABLE", "calls=0"),
    "asset_render_failure": ("BLOCKED", "RENDER_FAILED", "uri="),
    "wrong_pdf_link": ("BLOCKED", "LINK_MISMATCH", "reason=link_mismatch"),
    "stale_product_facts": ("BLOCKED", "STALE_FACTS", "copy="),
    "browser_selector_change": ("BLOCKED", "SELECTOR_UNKNOWN", "known=false"),
    "ramp_full": ("BLOCKED", "RAMP_FULL", "may_publish=false"),
    "spend_cap_reached": ("BLOCKED", "SPEND_CAP", "spent=0"),
}
_SESSION_13_KEYS = frozenset(
    {
        MATRIX_EVIDENCE_KEY,
        "synthetic_paths_implemented",
        "failure_injection_implemented",
        "backup_restore_fixture_implemented",
        CONTROL_EVIDENCE_KEY,
        _CLOSURE_EVIDENCE_KEY,
    }
)
_CONTROL_FILES = (
    Path("docs/control/IMPLEMENTATION_STATE.json"),
    Path("docs/control/IMPLEMENTATION_LOG.md"),
    Path("docs/control/DECISIONS.md"),
    Path("docs/control/TEST_EVIDENCE.md"),
    Path("docs/control/NEXT_SESSION.md"),
    Path("docs/control/SESSION_EVIDENCE.md"),
)
_CLOSURE_HEAD = "fbaf8e8bdd73b1e3b6fa4f87158574057b72d18a"
_SESSION_14_PROMPT = "17_SESSION_14_DEPLOYMENT.md"
_SESSION_14_KEYS = frozenset(
    {
        "deployment_target_recorded",
        "production_packaging_defined",
        "release_rollback_implemented",
        "service_controls_fail_closed",
        CONTROL_EVIDENCE_KEY,
        _CLOSURE_EVIDENCE_KEY,
    }
)


class Session13ProofError(ValueError):
    """The Session 13 fixture did not earn its evidence key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def prove_session_13() -> frozenset[str]:
    """Return the earned Session 13 keys. A miss raises instead of returning them."""
    _prove_matrix()
    _prove_synthetic()
    _prove_failure()
    _prove_backup()
    _prove_control_files()
    return EARNED_EVIDENCE_KEYS


def _prove_matrix() -> None:
    module = Path(__file__).resolve().parents[1] / "assets" / "implementation_matrix.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    folded = " ".join(imported)
    if any(token in folded for token in ("socket", "httpx", "urllib", "requests")):
        raise Session13ProofError("matrix_socket")
    try:
        rows = build_matrix()
    except MatrixRefusal as error:
        raise Session13ProofError(error.code) from error
    if not rows:
        raise Session13ProofError("matrix_empty")
    blocked = [row for row in rows if row.status is MatrixStatus.BLOCKED_BY_EXTERNAL_CREDENTIAL]
    missing = [row for row in rows if row.status is MatrixStatus.MISSING]
    if not blocked or not missing:
        raise Session13ProofError("matrix_gap")
    if any(row.status is MatrixStatus.IMPLEMENTED_AND_TESTED for row in blocked):
        raise Session13ProofError("matrix_relabel")


def _prove_synthetic() -> None:
    module = Path(__file__).resolve().parents[1] / "assets" / "synthetic_paths.py"
    _refuse_network(module, "synthetic_socket")
    try:
        simulate_publish(mode="live", idempotency_key="proof")
    except SyntheticPathRefusal as error:
        if error.code != "live_publish":
            raise Session13ProofError("live_publish") from error
    else:
        raise Session13ProofError("live_publish")
    run = run_synthetic_paths()
    if run.published_live or run_synthetic_paths() != run:
        raise Session13ProofError("synthetic_duplicate")
    _require_steps(run.receipts, "main", MAIN_STEPS)
    _require_steps(run.receipts, "cull", CULL_STEPS)
    _require_steps(run.receipts, "repair", REPAIR_STEPS)
    _require_steps(run.receipts, "broken_link", BROKEN_LINK_STEPS)
    _require_steps(run.receipts, "dedupe", DEDUPE_STEPS)
    blocked = [
        item
        for item in run.receipts
        if item.path == "main" and item.step == "post_publish_verification"
    ]
    if len(blocked) != 1 or blocked[0].outcome != "BLOCKED_BY_EXTERNAL_CREDENTIAL":
        raise Session13ProofError("synthetic_verification")
    withheld = [item for item in run.receipts if item.outcome == "WITHHELD"]
    if len(withheld) != 2:
        raise Session13ProofError("synthetic_publish")


def _prove_backup() -> None:
    module = Path(__file__).resolve().parents[1] / "assets" / "backup_restore.py"
    _refuse_network(module, "backup_socket")
    try:
        backup(mode="postgres")
    except BackupRefusal as error:
        if error.code != "live_postgres":
            raise Session13ProofError("live_postgres") from error
    else:
        raise Session13ProofError("live_postgres")
    source = sample_store()
    snapshot = take_snapshot(source)
    source.clear()
    if source.workflows or source.jobs or source.products or source.listings or source.incidents:
        raise Session13ProofError("backup_copy")
    target = FixtureStore()
    try:
        first = restore_snapshot(target, snapshot)
        second = restore_snapshot(target, snapshot)
    except BackupRefusal as error:
        raise Session13ProofError(error.code) from error
    if first.inserted != 7 or second.inserted != 0:
        raise Session13ProofError("backup_duplicate")
    counts = (
        first.workflow_count,
        first.job_count,
        first.product_count,
        first.listing_count,
        first.incident_count,
    )
    if counts != (1, 1, 1, 1, 1) or second.workflow_count != 1:
        raise Session13ProofError("backup_rows")
    workflow = snapshot.workflows[0]
    job = snapshot.jobs[0]
    product = snapshot.products[0]
    listing = snapshot.listings[0]
    incident = snapshot.incidents[0]
    artifact = snapshot.artifacts[0]
    expected_sha = hashlib.sha256(b"Household reset planner delivery").hexdigest()
    if (
        target.workflows.get(workflow.workflow_id) != workflow
        or target.jobs.get(job.job_id) != job
        or target.products.get(product.product_id) != product
        or target.listings.get(listing.listing_id) != listing
        or target.incidents.get(incident.incident_id) != incident
        or listing.listing_state != "DRAFT"
        or artifact.sha256 != expected_sha
        or artifact.sha256 != artifact_sha256(b"Household reset planner delivery")
        or target.config != snapshot.config
        or snapshot.config.publishing_mode != "simulation"
    ):
        raise Session13ProofError("backup_rows")


def _prove_failure() -> None:
    module = Path(__file__).resolve().parents[1] / "assets" / "failure_injection.py"
    _refuse_network(module, "failure_socket")
    try:
        outcomes = run_failure_injections()
    except FailureInjectionError as error:
        raise Session13ProofError(error.code) from error
    if tuple(item.name for item in outcomes) != INJECTIONS or run_failure_injections() != outcomes:
        raise Session13ProofError("failure_names")
    if set(_FAILURE_RESULTS) != set(INJECTIONS):
        raise Session13ProofError("failure_names")
    for item in outcomes:
        if (item.disposition, item.state, item.detail) != _FAILURE_RESULTS[item.name]:
            raise Session13ProofError("failure_disposition")
    recovered = [item for item in outcomes if item.disposition == "RECOVERED"]
    blocked = [item for item in outcomes if item.disposition == "BLOCKED"]
    if len(recovered) < 2 or len(blocked) < 2:
        raise Session13ProofError("failure_disposition")


def _refuse_network(module: Path, code: str) -> None:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    folded = " ".join(imported)
    banned = ("socket", "httpx", "urllib", "requests", "psycopg", "asyncpg", "sqlalchemy")
    if any(token in folded for token in banned):
        raise Session13ProofError(code)


def _require_steps(receipts: tuple[PathReceipt, ...], path: str, steps: tuple[str, ...]) -> None:
    found = tuple(item.step for item in receipts if item.path == path)
    if found != steps:
        raise Session13ProofError("synthetic_step")


def _prove_control_files() -> None:
    """The continuity files and the catalogue match the checked-in pointer."""
    root = Path(__file__).resolve().parents[3]
    for relative in _CONTROL_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise Session13ProofError("control_files")
    from money_machine.control.session_evidence import render_session_evidence

    catalogue = root / "docs/control/SESSION_EVIDENCE.md"
    if catalogue.read_text(encoding="utf-8") != render_session_evidence():
        raise Session13ProofError("control_checkpoint")
    decoded: object = json.loads(
        (root / "docs/control/IMPLEMENTATION_STATE.json").read_text(encoding="utf-8")
    )
    if not isinstance(decoded, dict):
        raise Session13ProofError("control_checkpoint")
    evidence = decoded.get("required_completion_evidence")
    recorded = set(evidence) if isinstance(evidence, dict) else set()
    values_are_bool = isinstance(evidence, dict) and all(
        isinstance(value, bool) for value in evidence.values()
    )
    if decoded.get("current_session") == 14:
        if (
            decoded.get("session_status") != "incomplete"
            or decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
            or decoded.get("head_sha") != _CLOSURE_HEAD
            or recorded != set(_SESSION_14_KEYS)
            or not values_are_bool
            or not isinstance(evidence, dict)
            or len(evidence) != len(recorded)
            or decoded.get("next_session") != 14
            or decoded.get("completed_sessions") != list(range(14))
            or decoded.get("next_prompt") != _SESSION_14_PROMPT
            or evidence.get("deployment_target_recorded") is not True
            or sum(1 for value in evidence.values() if value is True) != 1
        ):
            raise Session13ProofError("control_checkpoint")
        return
    if (
        decoded.get("current_session") != 13
        or decoded.get("session_status") != "complete"
        or decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or decoded.get("head_sha") != _CLOSURE_HEAD
        or recorded != set(_SESSION_13_KEYS)
        or not values_are_bool
        or not isinstance(evidence, dict)
        or len(evidence) != len(recorded)
        or decoded.get("next_session") != 14
        or decoded.get("completed_sessions") != list(range(14))
        or decoded.get("next_prompt") != _SESSION_14_PROMPT
        or any(value is not True for value in evidence.values())
    ):
        raise Session13ProofError("control_checkpoint")
