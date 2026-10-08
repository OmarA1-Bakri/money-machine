"""Sandbox runner for the merged Session 07 build and variant pipeline.

Dry-run is the default. ``--execute`` is the only path that writes. The token
is read from ``NOTION_SANDBOX_TOKEN`` and is never printed. Git, the control
ids, and the evidence file are resolved before any network read or write.

Exit codes: 0 ok, 64 usage, a bad token, an evidence-path refusal, a set
``NOTION_CONFIG`` / ``NOTION_SANDBOX_CONFIG`` / ``NOTION_TOKEN_FILE``, or a set
``SSL_CERT_FILE`` / ``SSL_CERT_DIR`` / ``SSLKEYLOGFILE``, 65 target mismatch,
66 missing token, 69 git, control, read, stage, clock, an interrupted run
including SIGINT, a full disk (ENOSPC, EIO, EDQUOT, EFBIG), a swapped evidence
file, or unprintable stdout, 70 redaction self-check failure. Exit 78 is not
used, and this module does not change that hold.

``get_public_url`` reads are excluded from ``write_counts``. The top-level
``write_counts`` object splits fixture pipeline methods from the live
``create_child_page`` counter. The ``fixture`` and ``live`` sections repeat
that split.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import stat
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, cast

from money_machine.cli.notion import token_shape_ok
from money_machine.cli.notion_sandbox_guard import (
    EXIT_API,
    EXIT_NO_TOKEN,
    EXIT_OK,
    EXIT_REDACTION,
    EXIT_TARGET,
    EXIT_USAGE,
    SANDBOX_PARENT_PAGE_ID,
    SANDBOX_SPACE_ID,
    BotView,
    PageView,
    SandboxClient,
    SandboxError,
    canonical_id,
    cert_env_set,
    commit_evidence,
    control_ids,
    empty_write_counts,
    evidence_sections,
    git_sha,
    leaks,
    open_evidence,
    qa_verdict,
    redact_text,
    repo_root,
    stage_status,
    stamp,
    target_ok,
)
from money_machine.cli.notion_sandbox_guard import (
    argv_refused as argv_names_a_target,
)
from money_machine.cli.notion_sandbox_guard import (
    override_env as environ_names_a_target,
)
from money_machine.cli.notion_sandbox_guard import (
    token_from_environ as sandbox_token,
)
from money_machine.cli.notion_sandbox_live import LiveSandboxClient
from money_machine.cli.notion_sandbox_pipeline import (
    SandboxRun,
    sandbox_product_spec,
    stage_runners,
)

LOGGER = logging.getLogger(__name__)

# Plug-in slots. Replace None with a runner name that ``stage_runners`` defines.
# qa: W9 notion_qa.py, not merged. fact_ledger and workflow_link: W10, not merged.
# w11: later close, not merged. A None runner is NOT_RUN and is never PASS.
STAGE_REGISTRY: tuple[tuple[str, str | None], ...] = (
    ("build", "run_build"),
    ("variants", "run_variants"),
    ("qa", None),
    ("fact_ledger", None),
    ("workflow_link", None),
    ("w11", None),
)


def _stage_row(name: str, available: bool, status: str, *, planned: bool) -> dict[str, object]:
    return {"available": available, "name": name, "planned": planned, "status": status}


def planned_stages() -> list[dict[str, object]]:
    """Dry-run plan. Available stages are planned and still ``NOT_RUN``."""
    return [
        _stage_row(
            name,
            runner_name is not None,
            stage_status(runner_name, None),
            planned=runner_name is not None,
        )
        for name, runner_name in STAGE_REGISTRY
    ]


def blocked_stages() -> list[dict[str, object]]:
    """Target mismatch. Missing stages stay ``NOT_RUN``."""
    rows: list[dict[str, object]] = []
    for name, runner_name in STAGE_REGISTRY:
        if runner_name is None:
            rows.append(_stage_row(name, False, stage_status(runner_name, None), planned=False))
        else:
            rows.append(_stage_row(name, True, "BLOCKED", planned=False))
    return rows


def _signal_stages() -> list[dict[str, object]]:
    """SIGINT after the stages return. Created ids stay on the run."""
    rows: list[dict[str, object]] = []
    for name, runner_name in STAGE_REGISTRY:
        available = runner_name is not None
        status = "INTERRUPTED" if available else "NOT_RUN"
        rows.append(_stage_row(name, available, status, planned=False))
    return rows


def _read_interrupted() -> list[dict[str, object]]:
    """A signal during the target reads. No page was created."""
    rows: list[dict[str, object]] = []
    marked = False
    for name, runner_name in STAGE_REGISTRY:
        available = runner_name is not None
        if available and not marked:
            rows.append(_stage_row(name, True, "INTERRUPTED", planned=False))
            marked = True
            continue
        rows.append(_stage_row(name, available, "NOT_RUN", planned=False))
    return rows


def _remaining(start: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name, runner_name in STAGE_REGISTRY[start:]:
        available = runner_name is not None
        rows.append(_stage_row(name, available, stage_status(runner_name, None), planned=False))
    return rows


async def _run_stages(ctx: SandboxRun, token: str | None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    failed = False
    runners = stage_runners()
    for index, (name, runner_name) in enumerate(STAGE_REGISTRY):
        available = runner_name is not None
        if not available or failed:
            rows.append(_stage_row(name, available, stage_status(runner_name, None), planned=False))
            continue
        runner = runners.get(runner_name)
        if runner is None:
            rows.append(_stage_row(name, False, stage_status(None, "PASS"), planned=False))
            continue
        try:
            await runner(ctx)
        except Exception as exc:
            row = _stage_row(name, True, stage_status(runner_name, "FAILED"), planned=False)
            row["error"] = redact_text(str(exc), token)
            rows.append(row)
            failed = True
            continue
        except BaseException as exc:
            row = _stage_row(name, True, "INTERRUPTED", planned=False)
            row["error"] = redact_text(f"{type(exc).__name__}: {exc}", token)
            rows.append(row)
            rows.extend(_remaining(index + 1))
            return rows
        rows.append(_stage_row(name, True, stage_status(runner_name, "PASS"), planned=False))
    return rows


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise SandboxError("usage error")


def _parser() -> _Parser:
    parser = _Parser(prog="python -m money_machine.cli.notion_sandbox", allow_abbrev=False)
    parser.add_argument("--evidence-out", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _evidence_argument(argv: Sequence[str]) -> Path | None:
    for index, arg in enumerate(argv):
        if arg == "--evidence-out" and index + 1 < len(argv):
            return Path(argv[index + 1])
        if arg.startswith("--evidence-out="):
            return Path(arg.split("=", 1)[1])
    return None


def _with_ids(prefix: str, created: list[dict[str, str]]) -> str:
    ids = [row["id"] for row in created if type(row.get("id")) is str and row["id"] != ""]
    if not ids:
        return prefix
    return prefix + ": " + ", ".join(ids)


def _sink_stdout() -> None:
    """Drop a broken stdout so process exit stays the sandbox code."""
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115


def _fail(message: str, code: int) -> int:
    cleaned = redact_text(message, None)
    LOGGER.info("%s", cleaned)
    print(cleaned, file=sys.stderr)
    return code


def _now(clock: Callable[[], datetime] | None, token: str | None) -> datetime:
    try:
        moment = datetime.now(UTC) if clock is None else clock()
    except Exception as exc:
        raise SandboxError(redact_text(str(exc), token)) from None
    if type(moment) is not datetime or moment.tzinfo is None:
        raise SandboxError("clock must be timezone-aware")
    return moment.astimezone(UTC)


def _shaped(token: str | None) -> str | None:
    if token is not None and token_shape_ok(token):
        return token
    return None


def _payload(
    *,
    mode: str,
    started: datetime,
    ended: datetime,
    stages: list[dict[str, object]],
    created: list[dict[str, str]],
    counts: dict[str, int],
    bot_user_id: str | None,
    git: str,
    control: Mapping[str, object],
    rejected: list[dict[str, str]] | None = None,
    flagged: list[dict[str, str]] | None = None,
    orphans: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "asserted_parent_page_id": SANDBOX_PARENT_PAGE_ID,
        "asserted_space_id": SANDBOX_SPACE_ID,
        "bot_user_id": bot_user_id,
        "created_pages": created,
        "ended_at": stamp(ended),
        "flagged_pages": [] if flagged is None else flagged,
        "git_sha": git,
        "mode": mode,
        "possible_orphans": [] if orphans is None else orphans,
        "qa_verdict": qa_verdict(stages),
        "rejected_pages": [] if rejected is None else rejected,
        "stages": stages,
        "started_at": stamp(started),
        "write_counts": _split_counts(counts),
    }
    payload.update(control)
    payload.update(evidence_sections(counts, created))
    return payload


def _split_counts(counts: Mapping[str, int]) -> dict[str, object]:
    sections = evidence_sections(counts, [])
    fixture = cast(dict[str, object], sections["fixture"])
    live = cast(dict[str, object], sections["live"])
    return {"fixture": fixture["write_counts"], "live": live["write_counts"]}


def _emit(path: Path, payload: Mapping[str, object], token: str | None) -> str:
    result = commit_evidence(path, payload, token)
    try:
        print(path.resolve())
    except (OSError, UnicodeError):
        _sink_stdout()
        raise SandboxError("stdout is unavailable") from None
    return result


def _preflight(path: Path, root: Path) -> tuple[str, dict[str, object]]:
    """Git, control ids, and a refused-or-acceptable evidence path. No network."""
    git = git_sha(root)
    control = control_ids(root)
    open_evidence(path)
    return git, control


def _read_target(client: SandboxClient) -> tuple[BotView, PageView]:
    bot = client.read_bot()
    return bot, client.read_page(SANDBOX_PARENT_PAGE_ID)


class _Held:
    """Ids captured before an interrupt so main can still write evidence."""

    def __init__(self) -> None:
        self.path: Path | None = None
        self.token: str | None = None
        self.started: datetime | None = None
        self.clock: Callable[[], datetime] | None = None
        self.mode: str = "dry-run"
        self.stages: list[dict[str, object]] = []
        self.created: list[dict[str, str]] = []
        self.counts: dict[str, int] = {}
        self.bot_user_id: str | None = None
        self.git: str = ""
        self.control: dict[str, object] = {}
        self.rejected: list[dict[str, str]] = []
        self.flagged: list[dict[str, str]] = []
        self.orphans: list[dict[str, str]] = []
        self.ready: bool = False


_HELD = _Held()


def _raise_interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def _arm_interrupt() -> None:
    """Keep SIGINT as a catchable interrupt for the whole process."""
    try:
        current = signal.getsignal(signal.SIGINT)
    except ValueError:
        return
    if current not in (signal.SIG_DFL, signal.default_int_handler):
        return
    signal.signal(signal.SIGINT, _raise_interrupt)


def _evidence_is_complete(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode) or info.st_size <= 0:
        return False
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return type(parsed) is dict


def _remember_held(
    path: Path,
    token: str | None,
    started: datetime,
    clock: Callable[[], datetime] | None,
    mode: str,
    git: str,
    control: Mapping[str, object],
    counts: dict[str, int],
) -> None:
    held = _HELD
    held.path = path
    held.token = token
    held.started = started
    held.clock = clock
    held.mode = mode
    held.git = git
    held.control = dict(control)
    held.counts = counts
    held.ready = True


def _publish_held() -> int:
    """Write INTERRUPTED evidence, or leave a complete file that is already there."""
    held = _HELD
    log = _with_ids("sandbox interrupted", held.created)
    path = held.path
    if path is None or held.started is None or not held.ready:
        return _fail(log, EXIT_API)
    if _evidence_is_complete(path):
        return _fail(log, EXIT_API)
    stages = held.stages
    if not any(stage.get("status") == "INTERRUPTED" for stage in stages):
        stages = _signal_stages()
    try:
        return _finish(
            path,
            held.token,
            held.started,
            held.clock,
            mode=held.mode,
            stages=stages,
            created=held.created,
            counts=held.counts if held.counts else empty_write_counts(),
            bot_user_id=held.bot_user_id,
            git=held.git,
            control=held.control,
            error=None,
            code=EXIT_API,
            log=log,
            rejected=held.rejected,
            flagged=held.flagged,
            orphans=held.orphans,
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        if _evidence_is_complete(path):
            return _fail(log, EXIT_API)
        raise


def main(
    argv: Sequence[str] | None = None,
    *,
    client: SandboxClient | None = None,
    environ: Mapping[str, str] | None = None,
    spec: object | None = None,
    clock: Callable[[], datetime] | None = None,
) -> int:
    """Run the sandbox checks. Writes only when ``--execute`` is present."""
    _arm_interrupt()
    try:
        return _main(argv, client=client, environ=environ, spec=spec, clock=clock)
    except SandboxError as exc:
        return _fail(str(exc), exc.code)
    except OSError:
        return _fail("evidence path is refused", EXIT_USAGE)
    except (KeyboardInterrupt, asyncio.CancelledError):
        return _publish_held()


def _main(
    argv: Sequence[str] | None,
    *,
    client: SandboxClient | None,
    environ: Mapping[str, str] | None,
    spec: object | None,
    clock: Callable[[], datetime] | None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    env = os.environ if environ is None else environ
    token = sandbox_token(env)
    secret = _shaped(token)
    started = _now(clock, secret)
    early_path = _evidence_argument(arguments)
    root = repo_root()
    if argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env):
        return _refuse(early_path, secret, started, root, "usage error", EXIT_USAGE, clock)
    try:
        parsed = _parser().parse_args(arguments)
    except SandboxError:
        return _fail("usage error", EXIT_USAGE)
    evidence = Path(parsed.evidence_out)
    if str(evidence) == "" or leaks(str(evidence), secret):
        return _fail("usage error", EXIT_USAGE)
    git, control = _preflight(evidence, root)
    _remember_held(evidence, secret, started, clock, "dry-run", git, control, empty_write_counts())
    if parsed.execute and parsed.dry_run:
        return _refuse_open(
            evidence, secret, started, clock, git, control, "usage error", EXIT_USAGE
        )
    mode = "execute" if parsed.execute else "dry-run"
    _HELD.mode = mode
    if token is None:
        return _refuse_open(
            evidence,
            None,
            started,
            clock,
            git,
            control,
            "notion sandbox token is missing",
            EXIT_NO_TOKEN,
        )
    if secret is None:
        return _refuse_open(
            evidence,
            None,
            started,
            clock,
            git,
            control,
            "notion token shape is invalid",
            EXIT_USAGE,
        )
    active = client if client is not None else LiveSandboxClient(token)
    counts = empty_write_counts()
    active.write_counts = counts
    _HELD.counts = counts
    try:
        bot, page = _read_target(active)
    except Exception as exc:
        LOGGER.info("%s", redact_text(str(exc), secret))
        return _finish(
            evidence,
            secret,
            started,
            clock,
            mode=mode,
            stages=planned_stages(),
            created=[],
            counts=counts,
            bot_user_id=None,
            git=git,
            control=control,
            error="notion api error",
            code=EXIT_API,
            log="notion api error",
        )
    except BaseException:
        return _finish(
            evidence,
            secret,
            started,
            clock,
            mode=mode,
            stages=_read_interrupted(),
            created=[],
            counts=counts,
            bot_user_id=None,
            git=git,
            control=control,
            error="interrupted",
            code=EXIT_API,
            log="interrupted",
        )
    if type(bot.user_type) is not str:
        return _finish(
            evidence,
            secret,
            started,
            clock,
            mode=mode,
            stages=planned_stages(),
            created=[],
            counts=counts,
            bot_user_id=None,
            git=git,
            control=control,
            error="notion api error",
            code=EXIT_API,
            log="notion api error",
        )
    if not target_ok(bot, page):
        return _finish(
            evidence,
            secret,
            started,
            clock,
            mode=mode,
            stages=blocked_stages(),
            created=[],
            counts=counts,
            bot_user_id=_user_id(bot),
            git=git,
            control=control,
            error="sandbox target mismatch",
            code=EXIT_TARGET,
            log="sandbox target mismatch",
        )
    if mode == "dry-run":
        return _finish(
            evidence,
            secret,
            started,
            clock,
            mode="dry-run",
            stages=planned_stages(),
            created=[],
            counts=counts,
            bot_user_id=_user_id(bot),
            git=git,
            control=control,
            error=None,
            code=EXIT_OK,
            log="sandbox dry-run ok",
        )
    chosen: object = sandbox_product_spec(started) if spec is None else spec
    with tempfile.TemporaryDirectory() as folder:
        ctx = SandboxRun(
            spec=chosen,
            client=active,
            checkpoint=Path(folder) / "checkpoint.json",
            moment=started,
            write_counts=counts,
            bot_user_id=_user_id(bot) or "",
            bot_space_id=canonical_id(bot.space_id),
        )
        _bind_record(active, ctx)
        try:
            stages = asyncio.run(_run_stages(ctx, secret))
        except (KeyboardInterrupt, asyncio.CancelledError):
            stages = _signal_stages()
        created = list(ctx.created)
        rejected = list(ctx.rejected_pages)
        flagged = list(ctx.flagged_pages)
        orphans = list(ctx.possible_orphans)
        _HELD.created = created
        _HELD.rejected = rejected
        _HELD.flagged = flagged
        _HELD.orphans = orphans
        _HELD.stages = stages
        _HELD.bot_user_id = _user_id(bot)
        _HELD.counts = counts
    interrupted = any(stage["status"] == "INTERRUPTED" for stage in stages)
    failed = any(stage["status"] == "FAILED" for stage in stages)
    if interrupted:
        error = None
        code = EXIT_API
        log = _with_ids("sandbox interrupted", created)
    elif failed:
        error = "sandbox stage failed"
        code = EXIT_API
        log = "sandbox stage failed"
    else:
        error = None
        code = EXIT_OK
        log = "sandbox execute ok"
    try:
        return _finish(
            evidence,
            secret,
            started,
            clock,
            mode=mode,
            stages=stages,
            created=created,
            counts=counts,
            bot_user_id=_user_id(bot),
            git=git,
            control=control,
            error=error,
            code=code,
            log=log,
            rejected=rejected,
            flagged=flagged,
            orphans=orphans,
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        return _publish_held()


def _bind_record(client: SandboxClient, ctx: SandboxRun) -> None:
    bind = getattr(client, "bind_created", None)
    if bind is None:
        return
    bind(ctx.created_ids, ctx.created)


def _user_id(bot: BotView) -> str | None:
    if type(bot.user_id) is str:
        return bot.user_id
    return None


def _finish(
    path: Path,
    token: str | None,
    started: datetime,
    clock: Callable[[], datetime] | None,
    *,
    mode: str,
    stages: list[dict[str, object]],
    created: list[dict[str, str]],
    counts: dict[str, int],
    bot_user_id: str | None,
    git: str,
    control: Mapping[str, object],
    error: str | None,
    code: int,
    log: str,
    rejected: list[dict[str, str]] | None = None,
    flagged: list[dict[str, str]] | None = None,
    orphans: list[dict[str, str]] | None = None,
) -> int:
    ended = _now(clock, token)
    payload = _payload(
        mode=mode,
        started=started,
        ended=ended,
        stages=stages,
        created=created,
        counts=counts,
        bot_user_id=bot_user_id,
        git=git,
        control=control,
        rejected=rejected,
        flagged=flagged,
        orphans=orphans,
    )
    if error is not None:
        payload["error"] = error
    if any(stage.get("status") == "INTERRUPTED" for stage in stages):
        payload["run_status"] = "INTERRUPTED"
    check = _emit(path, payload, token)
    if check == "FAIL":
        return _fail("redaction self-check failed", EXIT_REDACTION)
    if code == EXIT_OK:
        LOGGER.info("%s", log)
        return EXIT_OK
    return _fail(log, code)


def _refuse_open(
    path: Path,
    token: str | None,
    started: datetime,
    clock: Callable[[], datetime] | None,
    git: str,
    control: Mapping[str, object],
    message: str,
    code: int,
) -> int:
    return _finish(
        path,
        token,
        started,
        clock,
        mode="dry-run",
        stages=planned_stages(),
        created=[],
        counts=empty_write_counts(),
        bot_user_id=None,
        git=git,
        control=control,
        error=message,
        code=code,
        log=message,
    )


def _refuse(
    path: Path | None,
    token: str | None,
    started: datetime,
    root: Path,
    message: str,
    code: int,
    clock: Callable[[], datetime] | None,
) -> int:
    if path is not None and str(path) != "" and not leaks(str(path), token):
        git, control = _preflight(path, root)
        _remember_held(path, token, started, clock, "dry-run", git, control, empty_write_counts())
        return _refuse_open(path, token, started, clock, git, control, message, code)
    return _fail(message, code)


if __name__ == "__main__":
    raise SystemExit(main())
