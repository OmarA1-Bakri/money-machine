"""Sandbox runner for the merged Session 07 build and variant pipeline.

Dry-run is the default. ``--execute`` is the only path that writes. The token
is read from ``NOTION_SANDBOX_TOKEN`` and is never printed. Git, the control
ids, and the evidence file are resolved before any network read or write.

Exit codes: 0 ok, 64 usage, a bad token, an evidence-path refusal, or a set
``NOTION_CONFIG`` / ``NOTION_SANDBOX_CONFIG`` / ``NOTION_TOKEN_FILE``, 65
target mismatch, 66 missing token, 69 git, control, read, stage, clock, or an
interrupted run, 70 redaction self-check failure. Exit 78 is not used, and
this module does not change that hold.

``get_public_url`` reads are excluded from ``write_counts``. Only methods in
``PIPELINE_WRITE_METHODS`` and the live ``create_child_page`` counter are
recorded.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

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
) -> dict[str, object]:
    payload: dict[str, object] = {
        "asserted_parent_page_id": SANDBOX_PARENT_PAGE_ID,
        "asserted_space_id": SANDBOX_SPACE_ID,
        "bot_user_id": bot_user_id,
        "created_pages": created,
        "ended_at": stamp(ended),
        "git_sha": git,
        "mode": mode,
        "qa_verdict": qa_verdict(stages),
        "stages": stages,
        "started_at": stamp(started),
        "write_counts": counts,
    }
    payload.update(control)
    payload.update(evidence_sections(counts, created))
    return payload


def _emit(fd: int, path: Path, payload: Mapping[str, object], token: str | None) -> str:
    result = commit_evidence(fd, payload, token)
    print(path.resolve())
    return result


def _preflight(path: Path, root: Path) -> tuple[str, dict[str, object], int]:
    """Git, control ids, and the evidence fd. No network."""
    return git_sha(root), control_ids(root), open_evidence(path)


def _read_target(client: SandboxClient) -> tuple[BotView, PageView]:
    bot = client.read_bot()
    return bot, client.read_page(SANDBOX_PARENT_PAGE_ID)


def main(
    argv: Sequence[str] | None = None,
    *,
    client: SandboxClient | None = None,
    environ: Mapping[str, str] | None = None,
    spec: object | None = None,
    clock: Callable[[], datetime] | None = None,
) -> int:
    """Run the sandbox checks. Writes only when ``--execute`` is present."""
    try:
        return _main(argv, client=client, environ=environ, spec=spec, clock=clock)
    except SandboxError as exc:
        return _fail(str(exc), exc.code)
    except OSError:
        return _fail("evidence path is refused", EXIT_USAGE)


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
    if argv_names_a_target(arguments) or environ_names_a_target(env):
        return _refuse(early_path, secret, started, root, "usage error", EXIT_USAGE, clock)
    try:
        parsed = _parser().parse_args(arguments)
    except SandboxError:
        return _fail("usage error", EXIT_USAGE)
    evidence = Path(parsed.evidence_out)
    if str(evidence) == "" or leaks(str(evidence), secret):
        return _fail("usage error", EXIT_USAGE)
    git, control, fd = _preflight(evidence, root)
    if parsed.execute and parsed.dry_run:
        return _refuse_open(
            fd, evidence, secret, started, clock, git, control, "usage error", EXIT_USAGE
        )
    mode = "execute" if parsed.execute else "dry-run"
    if token is None:
        return _refuse_open(
            fd,
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
            fd,
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
    try:
        bot, page = _read_target(active)
    except Exception as exc:
        LOGGER.info("%s", redact_text(str(exc), secret))
        return _finish(
            fd,
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
    except BaseException as exc:
        _reraise(exc)
    if type(bot.user_type) is not str:
        return _finish(
            fd,
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
            fd,
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
            fd,
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
        )
        stages = asyncio.run(_run_stages(ctx, secret))
        created = list(ctx.created)
    interrupted = any(stage["status"] == "INTERRUPTED" for stage in stages)
    failed = any(stage["status"] == "FAILED" for stage in stages)
    if interrupted:
        error: str | None = None
        code = EXIT_API
        log = "sandbox interrupted"
    elif failed:
        error = "sandbox stage failed"
        code = EXIT_API
        log = "sandbox stage failed"
    else:
        error = None
        code = EXIT_OK
        log = "sandbox execute ok"
    return _finish(
        fd,
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
    )


def _user_id(bot: BotView) -> str | None:
    if type(bot.user_id) is str:
        return bot.user_id
    return None


def _finish(
    fd: int,
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
    )
    if error is not None:
        payload["error"] = error
    if any(stage.get("status") == "INTERRUPTED" for stage in stages):
        payload["run_status"] = "INTERRUPTED"
    check = _emit(fd, path, payload, token)
    if check == "FAIL":
        return _fail("redaction self-check failed", EXIT_REDACTION)
    if code == EXIT_OK:
        LOGGER.info("%s", log)
        return EXIT_OK
    return _fail(log, code)


def _refuse_open(
    fd: int,
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
        fd,
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
        git, control, fd = _preflight(path, root)
        return _refuse_open(fd, path, token, started, clock, git, control, message, code)
    return _fail(message, code)


def _reraise(exc: BaseException) -> NoReturn:
    if isinstance(exc, SystemExit):
        status = exc.code if type(exc.code) is int and exc.code != 0 else 1
        blank: BaseException = SystemExit(status)
    elif isinstance(exc, KeyboardInterrupt):
        blank = KeyboardInterrupt()
    else:
        blank = BaseException()
    try:
        raise blank from None
    except BaseException as surfaced:
        surfaced.__context__ = None
        surfaced.__cause__ = None
        surfaced.__suppress_context__ = True
        raise


if __name__ == "__main__":
    raise SystemExit(main())
