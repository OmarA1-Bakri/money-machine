"""Earn the Session 12 read-model, view, telemetry, action, and control-file keys.

The proof does not open a socket, read a credential, or write a cap.
The completed pointer keeps every Session 12 key true, including the closure key.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

from money_machine.assets.operator_actions import (
    OPERATOR_ACTIONS,
    OperatorActionRefusal,
    refuse_operator_action,
)
from money_machine.assets.operator_console import (
    BlockerView,
    CompletionView,
    ConsoleReadModel,
    ConsoleRefusal,
    DecisionView,
    IncidentView,
    IntegrationView,
    JobView,
    ListingView,
    MilestoneView,
    PipelineStageView,
    ProductView,
    ShopView,
    VariantView,
    WeeklyMetricView,
    WorkflowView,
)
from money_machine.assets.operator_views import ConsoleViews, render_console
from money_machine.assets.telemetry_redaction import (
    TelemetryRefusal,
    redact_telemetry,
)

READ_MODEL_EVIDENCE_KEY = "console_read_model_implemented"
VIEWS_EVIDENCE_KEY = "exception_views_implemented"
TELEMETRY_EVIDENCE_KEY = "telemetry_redaction_implemented"
ACTIONS_EVIDENCE_KEY = "operator_actions_fail_closed"
CONTROL_EVIDENCE_KEY = "control_files_and_checkpoint_current"
_CLOSURE_EVIDENCE_KEY = "evidence_closure_commit_recorded"
EARNED_EVIDENCE_KEYS = frozenset(
    {
        READ_MODEL_EVIDENCE_KEY,
        VIEWS_EVIDENCE_KEY,
        TELEMETRY_EVIDENCE_KEY,
        ACTIONS_EVIDENCE_KEY,
        CONTROL_EVIDENCE_KEY,
    }
)
_UNEARNED_KEYS = (_CLOSURE_EVIDENCE_KEY,)
_SESSION_12_KEYS = frozenset(
    {
        READ_MODEL_EVIDENCE_KEY,
        VIEWS_EVIDENCE_KEY,
        TELEMETRY_EVIDENCE_KEY,
        ACTIONS_EVIDENCE_KEY,
        CONTROL_EVIDENCE_KEY,
        *_UNEARNED_KEYS,
    }
)
_SESSION_13_KEYS = frozenset(
    {
        "implementation_matrix_recorded",
        "synthetic_paths_implemented",
        "failure_injection_implemented",
        "backup_restore_fixture_implemented",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
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
_PRIOR_HEAD = "d095501665fbda0f9e6a0e77b57531bc33fda4e2"
_CLOSURE_HEAD = "d81db61033561bdd40869ff1316f0c935c74cdf4"
_SESSION_13_CLOSURE = "fbaf8e8bdd73b1e3b6fa4f87158574057b72d18a"
_SESSION_14_PROMPT = "17_SESSION_14_DEPLOYMENT.md"
_SESSION_14_CLOSURE = "02c26f39ac8800db03ae7f5d1d346487a5ce123e"
_SESSION_15_PROMPT = "18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md"
_SESSION_14_KEYS = frozenset(
    {
        "deployment_target_recorded",
        "production_packaging_defined",
        "release_rollback_implemented",
        "service_controls_fail_closed",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
_SESSION_15_KEYS = frozenset(
    {
        "acceptance_matrix_recorded",
        "control_files_and_checkpoint_current",
        "deployed_state_checked",
        "evidence_closure_commit_recorded",
        "linked_workflow_fixture",
        "provider_connections_fail_closed",
        "standing_authority_recorded",
    }
)
_SESSION_12_PROMPT = "15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md"
_SESSION_13_PROMPT = "16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md"
_DECISION_KINDS = ("hold", "repair", "cull", "multiply", "successor_created")
_WRITERS = ("set_", "pause", "resume", "send", "capture", "publish", "write")


class Session12ProofError(ValueError):
    """The Session 12 fixture did not earn its evidence key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def prove_session_12() -> frozenset[str]:
    """Return the earned Session 12 keys. A miss raises instead of returning them."""
    _prove_read_model()
    _prove_views()
    _prove_telemetry()
    _prove_actions()
    _prove_control_files()
    return EARNED_EVIDENCE_KEYS


def _prove_read_model() -> None:
    module = inspect.getmodule(ConsoleReadModel)
    if module is None or module.__file__ is None:
        raise Session12ProofError("read_model_socket")
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    folded = " ".join(imported)
    if any(token in folded for token in ("socket", "httpx", "urllib", "requests")):
        raise Session12ProofError("read_model_socket")
    names = [name for name in dir(ConsoleReadModel) if not name.startswith("_")]
    if any(name.startswith(_WRITERS) for name in names):
        raise Session12ProofError("read_model_writer")
    empty = ConsoleReadModel()
    if empty.current_shop() is not None:
        raise Session12ProofError("read_model_empty")
    empty_pages = (
        empty.workflow_page(limit=1),
        empty.pipeline_stages(limit=1),
        empty.job_page(status="ready", limit=1),
        empty.job_page(status="running", limit=1),
        empty.job_page(status="blocked", limit=1),
        empty.product_page(limit=1),
        empty.variant_page(limit=1),
        empty.listing_page(limit=1),
        empty.metric_page(limit=1),
        empty.decision_page(limit=1),
        empty.incident_page(limit=1),
        empty.integration_page(limit=1),
        empty.milestone_page(limit=1),
    )
    if any(page.items != () or page.next_cursor is not None for page in empty_pages):
        raise Session12ProofError("read_model_empty")
    health = empty.system_health()
    settings = empty.autonomy_settings()
    if (
        health.running != 0
        or health.blocked != 0
        or health.action_required is not False
        or settings.publication_cap != 0
        or settings.posthog != "offline"
    ):
        raise Session12ProofError("read_model_empty")
    for limit in (0, 51):
        try:
            empty.workflow_page(limit=limit)
        except ConsoleRefusal as error:
            if error.code != "limit":
                raise Session12ProofError("read_model_limit") from error
        else:
            raise Session12ProofError("read_model_limit")
    try:
        empty.job_page(status="connected")
    except ConsoleRefusal as error:
        if error.code != "status":
            raise Session12ProofError("read_model_status") from error
    else:
        raise Session12ProofError("read_model_status")
    _prove_seeded_pages()


def _prove_seeded_pages() -> None:
    model = _seeded()
    first = model.workflow_page(limit=2)
    if (
        tuple(item.workflow_id for item in first.items) != ("w-1", "w-2")
        or first.next_cursor != "w-2"
    ):
        raise Session12ProofError("read_model_page")
    second = model.workflow_page(cursor=first.next_cursor, limit=2)
    if (
        tuple(item.workflow_id for item in second.items) != ("w-3",)
        or second.next_cursor is not None
    ):
        raise Session12ProofError("read_model_page")
    shop = model.current_shop()
    if shop is None or shop.shop_id != "shop-1":
        raise Session12ProofError("read_model_shop")
    for status, job_id in (
        ("ready", "j-ready"),
        ("running", "j-running"),
        ("blocked", "j-blocked"),
    ):
        page = model.job_page(status=status, limit=5)
        if tuple(item.job_id for item in page.items) != (job_id,):
            raise Session12ProofError("read_model_jobs")
    kinds = tuple(item.kind for item in model.decision_page(limit=5).items)
    if kinds != _DECISION_KINDS:
        raise Session12ProofError("read_model_decisions")
    health = model.system_health()
    if health.running != 1 or health.blocked != 1 or health.action_required is not True:
        raise Session12ProofError("read_model_health")
    if model.integration_page(limit=5).items[0].status != "offline":
        raise Session12ProofError("read_model_integration")
    if model.listing_page(limit=5).items[0].state != "active":
        raise Session12ProofError("read_model_listing")


def _seeded() -> ConsoleReadModel:
    shop = ShopView(shop_id="shop-1", name="Fixture Shop", currency="USD")
    workflows = tuple(
        WorkflowView(
            workflow_id=f"w-{index}",
            name=f"Workflow {index}",
            stage="build",
            owning_agent="fixture",
            elapsed_seconds=index,
            next_transition="review",
            blocked_dependency=None,
        )
        for index in (1, 2, 3)
    )
    jobs = (
        JobView(
            job_id="j-ready",
            workflow_id="w-1",
            job_type="ResearchCollectionJob",
            status="ready",
            attempt=0,
        ),
        JobView(
            job_id="j-running",
            workflow_id="w-1",
            job_type="ListingRepairJob",
            status="running",
            attempt=1,
        ),
        JobView(
            job_id="j-blocked",
            workflow_id="w-2",
            job_type="IncidentRepairJob",
            status="blocked",
            attempt=2,
        ),
    )
    decisions = tuple(
        DecisionView(
            decision_id=f"d-{index}",
            kind=kind,
            evidence="fixture",
            status="recorded",
            routine=kind == "hold",
        )
        for index, kind in enumerate(_DECISION_KINDS, start=1)
    )
    return ConsoleReadModel(
        shop=shop,
        workflows=workflows,
        stages=(PipelineStageView(stage="build", experiment_count=1),),
        jobs=jobs,
        products=(ProductView(product_id="p-1", name="Fixture"),),
        variants=(VariantView(variant_id="v-1", product_id="p-1", name="Blue"),),
        listings=(
            ListingView(
                listing_id="l-1",
                product_id="p-1",
                state="active",
                age_days=3,
                views=4,
                favourites=1,
                sales=0,
                decision="hold",
                next_review_at="2026-10-24",
            ),
        ),
        weekly_metrics=(WeeklyMetricView(week_start="2026-10-12", views=4, favourites=1, sales=0),),
        decisions=decisions,
        incidents=(
            IncidentView(
                incident_id="i-1",
                summary="the file could not be opened",
                severity="normal",
                repair_step="verify",
                response_status="draft",
            ),
        ),
        integrations=(IntegrationView(name="posthog", status="offline"),),
        milestones=(MilestoneView(name="read-model", completed=1, total=1),),
    )


def _prove_views() -> None:
    module = inspect.getmodule(render_console)
    if module is None or module.__file__ is None:
        raise Session12ProofError("views_socket")
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    if "money_machine.assets.operator_console" not in imported:
        raise Session12ProofError("views_source")
    if any(token in " ".join(imported) for token in ("socket", "httpx", "urllib", "requests")):
        raise Session12ProofError("views_socket")
    names = tuple(field for field in ConsoleViews.__dataclass_fields__)
    if names != ("now", "pipeline", "shop", "blocked", "decisions", "incidents", "settings"):
        raise Session12ProofError("views_names")
    empty = render_console(ConsoleReadModel())
    if any(
        view.status != "empty" or view.error is not None
        for view in (
            empty.now,
            empty.pipeline,
            empty.shop,
            empty.blocked,
            empty.decisions,
            empty.incidents,
            empty.settings,
        )
    ):
        raise Session12ProofError("views_empty")
    if empty.now.running or empty.shop.active or empty.decisions.rows or empty.blocked.blockers:
        raise Session12ProofError("views_empty")
    if empty.settings.publication_cap != 0 or empty.settings.posthog != "offline":
        raise Session12ProofError("views_empty")
    failed = render_console(ConsoleReadModel(), cursor="missing")
    if any(
        view.status != "error" or view.error != "cursor"
        for view in (
            failed.now,
            failed.pipeline,
            failed.shop,
            failed.blocked,
            failed.decisions,
            failed.incidents,
            failed.settings,
        )
    ):
        raise Session12ProofError("views_error")
    if failed.now.running or failed.decisions.rows or failed.settings.mode != "":
        raise Session12ProofError("views_error")
    _prove_seeded_views()


def _prove_seeded_views() -> None:
    shown = render_console(_view_model())
    if shown.now.status != "ready" or shown.now.running[0].job_id != "j-running":
        raise Session12ProofError("views_now")
    if shown.now.next_scheduled[0].job_id != "j-ready" or shown.now.action_required is not True:
        raise Session12ProofError("views_now")
    if shown.now.recent_completions[0].job_id != "j-done":
        raise Session12ProofError("views_now")
    row = shown.pipeline.rows[0]
    if (
        shown.pipeline.status != "ready"
        or row.stage != "build"
        or row.owning_agent != "fixture"
        or row.elapsed_seconds != 4
        or row.next_transition != "review"
        or row.blocked_dependency != "credential"
    ):
        raise Session12ProofError("views_pipeline")
    if (
        shown.shop.active[0].state != "active"
        or shown.shop.draft[0].age_days != 2
        or shown.shop.deactivated[0].sales != 1
        or shown.shop.active[0].next_review_at != "2026-10-24"
    ):
        raise Session12ProofError("views_shop")
    if shown.blocked.blockers != (
        BlockerView(blocker_id="b-1", kind="credentials", detail="credential missing"),
    ):
        raise Session12ProofError("views_blocked")
    jobs_only = render_console(
        ConsoleReadModel(
            workflows=_view_model().workflows,
            jobs=(
                JobView(
                    job_id="j-blocked",
                    workflow_id="w-1",
                    job_type="IncidentRepairJob",
                    status="blocked",
                    attempt=1,
                ),
            ),
        )
    )
    if jobs_only.blocked.status != "empty" or jobs_only.blocked.blockers:
        raise Session12ProofError("views_blocked")
    kinds = tuple(item.kind for item in shown.decisions.rows)
    if kinds != _DECISION_KINDS:
        raise Session12ProofError("views_decisions")
    routine = shown.decisions.rows[0]
    if (
        routine.kind != "hold"
        or routine.approval_request is not False
        or routine.evidence != "fixture"
    ):
        raise Session12ProofError("views_decisions")
    incident = shown.incidents.rows[0]
    if (
        incident.buyer_issue != "the file could not be opened"
        or incident.severity != "normal"
        or incident.repair_step != "verify"
        or incident.response_status != "draft"
        or incident.resolution_evidence != "hash-aaaa"
    ):
        raise Session12ProofError("views_incidents")
    if (
        shown.settings.status != "ready"
        or shown.settings.mode != "held"
        or shown.settings.publication_cap != 0
        or shown.settings.loop_day != 0
        or shown.settings.posthog != "offline"
        or shown.settings.provider != "unread"
    ):
        raise Session12ProofError("views_settings")


def _view_model() -> ConsoleReadModel:
    workflows = (
        WorkflowView(
            workflow_id="w-1",
            name="Workflow 1",
            stage="build",
            owning_agent="fixture",
            elapsed_seconds=4,
            next_transition="review",
            blocked_dependency="credential",
        ),
    )
    decisions = tuple(
        DecisionView(
            decision_id=f"d-{index}",
            kind=kind,
            evidence="fixture",
            status="recorded",
            routine=kind == "hold",
        )
        for index, kind in enumerate(_DECISION_KINDS, start=1)
    )
    listings = (
        ListingView(
            listing_id="l-active",
            product_id="p-1",
            state="active",
            age_days=3,
            views=4,
            favourites=1,
            sales=0,
            decision="hold",
            next_review_at="2026-10-24",
        ),
        ListingView(
            listing_id="l-draft",
            product_id="p-1",
            state="draft",
            age_days=2,
            views=4,
            favourites=1,
            sales=0,
            decision="hold",
            next_review_at="2026-10-24",
        ),
        ListingView(
            listing_id="l-off",
            product_id="p-1",
            state="deactivated",
            age_days=9,
            views=4,
            favourites=1,
            sales=1,
            decision="hold",
            next_review_at="2026-10-24",
        ),
    )
    return ConsoleReadModel(
        shop=ShopView(shop_id="shop-1", name="Fixture Shop", currency="USD"),
        workflows=workflows,
        stages=(PipelineStageView(stage="build", experiment_count=1),),
        jobs=(
            JobView(
                job_id="j-ready",
                workflow_id="w-1",
                job_type="ResearchCollectionJob",
                status="ready",
                attempt=0,
            ),
            JobView(
                job_id="j-running",
                workflow_id="w-1",
                job_type="ListingRepairJob",
                status="running",
                attempt=1,
            ),
            JobView(
                job_id="j-blocked",
                workflow_id="w-1",
                job_type="IncidentRepairJob",
                status="blocked",
                attempt=2,
            ),
        ),
        products=(ProductView(product_id="p-1", name="Fixture"),),
        listings=listings,
        decisions=decisions,
        incidents=(
            IncidentView(
                incident_id="i-1",
                summary="the file could not be opened",
                severity="normal",
                repair_step="verify",
                response_status="draft",
                resolution_evidence="hash-aaaa",
            ),
        ),
        integrations=(IntegrationView(name="posthog", status="offline"),),
        completions=(
            CompletionView(
                job_id="j-done",
                workflow_id="w-1",
                job_type="ResearchCollectionJob",
                finished_at="2026-10-17T12:00:00Z",
            ),
        ),
        blockers=(BlockerView(blocker_id="b-1", kind="credentials", detail="credential missing"),),
    )


def _prove_telemetry() -> None:
    """A secret, a cookie, or a raw buyer message is refused. Nothing is sent."""
    module = inspect.getmodule(redact_telemetry)
    if module is None or module.__file__ is None:
        raise Session12ProofError("telemetry_socket")
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.append(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            calls.append(node.func.attr)
    folded = " ".join(imported)
    if any(token in folded for token in ("socket", "httpx", "urllib", "requests", "posthog")):
        raise Session12ProofError("telemetry_socket")
    if any(name in calls for name in ("capture", "send", "urlopen", "request")):
        raise Session12ProofError("telemetry_send")
    safe = redact_telemetry(
        event="job_completed",
        distinct_id="fixture-shop",
        properties={
            "workflow_id": "w-1",
            "job_type": "ResearchCollectionJob",
            "agent_id": "fixture",
            "product_id": "p-1",
            "listing_id": "l-1",
            "duration": "4",
            "attempt": "1",
            "status": "recorded",
            "environment": "fixture",
            "autonomy_mode": "held",
            "error_classification": "none",
        },
    )
    recorded = {name for name, _value in safe.properties}
    if safe.sent is not False or safe.event != "job_completed" or "status" not in recorded:
        raise Session12ProofError("telemetry_redaction")
    try:
        redact_telemetry(
            event="connected",
            distinct_id="fixture-shop",
            properties={"status": "connected"},
        )
    except TelemetryRefusal as error:
        if error.code != "event":
            raise Session12ProofError("telemetry_status_word") from error
    else:
        raise Session12ProofError("telemetry_status_word")
    refused = (
        ("secret", "secret"),
        ("api_key", "secret"),
        ("cookie", "cookie"),
        ("cookies", "cookie"),
        ("buyer_message", "buyer_message"),
        ("raw_buyer_message", "buyer_message"),
    )
    for name, code in refused:
        try:
            redact_telemetry(
                event="job_completed",
                distinct_id="fixture-shop",
                properties={name: "value"},
            )
        except TelemetryRefusal as error:
            if error.code != code:
                raise Session12ProofError("telemetry_redaction") from error
        else:
            raise Session12ProofError("telemetry_redaction")
    hidden = (
        ("status", "sk_live_example", "secret"),
        ("status", "cookie=session", "cookie"),
    )
    for name, value, code in hidden:
        try:
            redact_telemetry(
                event="job_completed",
                distinct_id="fixture-shop",
                properties={name: value},
            )
        except TelemetryRefusal as error:
            if error.code != code:
                raise Session12ProofError("telemetry_redaction") from error
        else:
            raise Session12ProofError("telemetry_redaction")


def _prove_actions() -> None:
    """Every named operator action is refused. The worker and the scheduler stay byte-identical."""
    module = inspect.getmodule(refuse_operator_action)
    if module is None or module.__file__ is None:
        raise Session12ProofError("operator_action")
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.append(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            calls.append(node.func.attr)
    folded = " ".join(imported)
    if any(
        token in folded
        for token in ("socket", "httpx", "urllib", "requests", "worker", "scheduler")
    ):
        raise Session12ProofError("operator_action")
    if any(name in calls for name in ("open", "write", "pause", "resume", "capture", "send")):
        raise Session12ProofError("operator_write")
    if len(OPERATOR_ACTIONS) != 9 or len(set(OPERATOR_ACTIONS)) != 9:
        raise Session12ProofError("operator_action")
    root = Path(__file__).resolve().parents[3]
    watched = (
        root / "src/money_machine/orchestration/worker.py",
        root / "src/money_machine/orchestration/scheduler.py",
    )
    before = tuple(path.read_bytes() for path in watched)
    for action in OPERATOR_ACTIONS:
        try:
            refuse_operator_action(action)
        except OperatorActionRefusal as error:
            if error.code != "closed":
                raise Session12ProofError("operator_action") from error
        else:
            raise Session12ProofError("operator_action")
    for action in ("edit_database", "pause/resume workflow", "trigger safe schedule run"):
        try:
            refuse_operator_action(action)
        except OperatorActionRefusal as error:
            if error.code != "closed":
                raise Session12ProofError("operator_action") from error
        else:
            raise Session12ProofError("operator_action")
    try:
        refuse_operator_action("connected")
    except OperatorActionRefusal as error:
        if error.code != "unknown":
            raise Session12ProofError("operator_status_word") from error
    else:
        raise Session12ProofError("operator_status_word")
    if tuple(path.read_bytes() for path in watched) != before:
        raise Session12ProofError("operator_write")
    if "Exit 78 held" not in watched[0].read_text(encoding="utf-8"):
        raise Session12ProofError("operator_write")


def _prove_control_files() -> None:
    """The continuity files and the catalogue match the checked-in pointer."""
    root = Path(__file__).resolve().parents[3]
    for relative in _CONTROL_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise Session12ProofError("control_files")
    # session_evidence imports state, and state imports this module.
    from money_machine.control.session_evidence import render_session_evidence

    catalogue = root / "docs/control/SESSION_EVIDENCE.md"
    if catalogue.read_text(encoding="utf-8") != render_session_evidence():
        raise Session12ProofError("control_checkpoint")
    decoded: object = json.loads(
        (root / "docs/control/IMPLEMENTATION_STATE.json").read_text(encoding="utf-8")
    )
    if not isinstance(decoded, dict):
        raise Session12ProofError("control_checkpoint")
    evidence = decoded.get("required_completion_evidence")
    recorded = set(evidence) if isinstance(evidence, dict) else set()
    values_are_bool = isinstance(evidence, dict) and all(
        isinstance(value, bool) for value in evidence.values()
    )
    status = decoded.get("session_status")
    if decoded.get("current_session") == 15:
        _prove_activated_session_15(decoded, evidence, status, recorded)
        return
    if decoded.get("current_session") == 14:
        _prove_activated_session_14(decoded, evidence, status, recorded)
        return
    if decoded.get("current_session") == 13:
        _prove_activated_session_13(decoded, evidence, status, recorded)
        return
    if (
        decoded.get("current_session") != 12
        or decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or recorded != set(_SESSION_12_KEYS)
        or not values_are_bool
        or not isinstance(evidence, dict)
        or len(evidence) != len(recorded)
        or evidence.get(READ_MODEL_EVIDENCE_KEY) is not True
        or evidence.get(VIEWS_EVIDENCE_KEY) is not True
        or evidence.get(TELEMETRY_EVIDENCE_KEY) is not True
        or evidence.get(ACTIONS_EVIDENCE_KEY) is not True
        or status not in {"incomplete", "complete"}
    ):
        raise Session12ProofError("control_checkpoint")
    if status == "incomplete":
        if (
            decoded.get("head_sha") != _PRIOR_HEAD
            or decoded.get("next_session") != 12
            or decoded.get("completed_sessions") != list(range(12))
            or decoded.get("next_prompt") != _SESSION_12_PROMPT
            or not isinstance(evidence.get(CONTROL_EVIDENCE_KEY), bool)
            or evidence.get(_CLOSURE_EVIDENCE_KEY) is not False
        ):
            raise Session12ProofError("control_checkpoint")
        return
    if (
        decoded.get("head_sha") != _CLOSURE_HEAD
        or decoded.get("next_session") != 13
        or decoded.get("completed_sessions") != list(range(13))
        or decoded.get("next_prompt") != _SESSION_13_PROMPT
        or evidence.get(CONTROL_EVIDENCE_KEY) is not True
        or evidence.get(_CLOSURE_EVIDENCE_KEY) is not True
    ):
        raise Session12ProofError("control_checkpoint")


def _prove_activated_session_13(
    decoded: dict[str, object],
    evidence: object,
    status: object,
    recorded: set[str],
) -> None:
    """Session 12 stays closed while Session 13 is complete."""
    values_are_bool = isinstance(evidence, dict) and all(
        isinstance(value, bool) for value in evidence.values()
    )
    if (
        decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or decoded.get("head_sha") != _SESSION_13_CLOSURE
        or recorded != set(_SESSION_13_KEYS)
        or not values_are_bool
        or not isinstance(evidence, dict)
        or len(evidence) != len(recorded)
        or status != "complete"
        or decoded.get("next_session") != 14
        or decoded.get("completed_sessions") != list(range(14))
        or decoded.get("next_prompt") != _SESSION_14_PROMPT
        or any(value is not True for value in evidence.values())
    ):
        raise Session12ProofError("control_checkpoint")


def _prove_activated_session_15(
    decoded: dict[str, object],
    evidence: object,
    status: object,
    recorded: set[str],
) -> None:
    """Session 12 stays closed while Session 15 is activated."""
    values_are_bool = isinstance(evidence, dict) and all(
        isinstance(value, bool) for value in evidence.values()
    )
    if (
        decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or decoded.get("head_sha") != _SESSION_14_CLOSURE
        or recorded != set(_SESSION_15_KEYS)
        or not values_are_bool
        or not isinstance(evidence, dict)
        or len(evidence) != len(recorded)
        or status != "incomplete"
        or decoded.get("next_session") != 15
        or decoded.get("completed_sessions") != list(range(15))
        or decoded.get("next_prompt") != _SESSION_15_PROMPT
        or any(value is not False for value in evidence.values())
    ):
        raise Session12ProofError("control_checkpoint")


def _prove_activated_session_14(
    decoded: dict[str, object],
    evidence: object,
    status: object,
    recorded: set[str],
) -> None:
    """Session 12 stays closed while Session 14 is complete."""
    values_are_bool = isinstance(evidence, dict) and all(
        isinstance(value, bool) for value in evidence.values()
    )
    if (
        decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or decoded.get("head_sha") != _SESSION_14_CLOSURE
        or recorded != set(_SESSION_14_KEYS)
        or not values_are_bool
        or not isinstance(evidence, dict)
        or len(evidence) != len(recorded)
        or status != "complete"
        or decoded.get("next_session") != 15
        or decoded.get("completed_sessions") != list(range(15))
        or decoded.get("next_prompt") != _SESSION_15_PROMPT
        or any(value is not True for value in evidence.values())
    ):
        raise Session12ProofError("control_checkpoint")
