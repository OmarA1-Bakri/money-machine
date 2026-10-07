"""Sandbox runner for the merged Session 07 build and variant pipeline.

Dry-run is the default. ``--execute`` is the only path that writes. The token
is read from ``NOTION_SANDBOX_TOKEN`` and is never printed.

Grok Bot runs this later, from a checkout of the merged SHA::

    NOTION_SANDBOX_TOKEN=… python -m money_machine.cli.notion_sandbox \\
        --execute --evidence-out <path>

Exit codes: 0 ok, 64 usage or a bad token, 65 target mismatch, 66 missing
token, 69 read or stage failure, 70 redaction self-check failure. Exit 78 is
not used, and this module does not change that hold.
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
    control_ids,
    empty_write_counts,
    git_sha,
    leaks,
    qa_verdict,
    redact_text,
    repo_root,
    stage_status,
    stamp,
    target_ok,
    write_evidence,
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


async def _run_stages(ctx: SandboxRun) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    failed = False
    runners = stage_runners()
    for name, runner_name in STAGE_REGISTRY:
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
        except Exception:
            rows.append(_stage_row(name, True, stage_status(runner_name, "FAILED"), planned=False))
            failed = True
            continue
        rows.append(_stage_row(name, True, stage_status(runner_name, "PASS"), planned=False))
    return rows


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise SandboxError("usage error")


def _parser() -> _Parser:
    parser = _Parser(prog="python -m money_machine.cli.notion_sandbox")
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


def _now(clock: Callable[[], datetime] | None) -> datetime:
    moment = datetime.now(UTC) if clock is None else clock()
    if type(moment) is not datetime or moment.tzinfo is None:
        raise SandboxError("clock must be timezone-aware")
    return moment.astimezone(UTC)


def _payload(
    *,
    mode: str,
    started: datetime,
    ended: datetime,
    stages: list[dict[str, object]],
    created: list[dict[str, str]],
    counts: dict[str, int],
    bot_user_id: str | None,
    root: Path,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "asserted_parent_page_id": SANDBOX_PARENT_PAGE_ID,
        "asserted_space_id": SANDBOX_SPACE_ID,
        "bot_user_id": bot_user_id,
        "created_pages": created,
        "ended_at": stamp(ended),
        "git_sha": git_sha(root),
        "mode": mode,
        "qa_verdict": qa_verdict(stages),
        "stages": stages,
        "started_at": stamp(started),
        "write_counts": counts,
    }
    payload.update(control_ids(root))
    return payload


def _emit(path: Path, payload: Mapping[str, object], token: str | None) -> str:
    if leaks(str(path), token):
        raise SandboxError("usage error")
    result = write_evidence(path, payload, token)
    print(path.resolve())
    return result


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
    arguments = list(sys.argv[1:] if argv is None else argv)
    env = os.environ if environ is None else environ
    token = sandbox_token(env)
    started = _now(clock)
    early_path = _evidence_argument(arguments)
    root = repo_root()
    if argv_names_a_target(arguments) or environ_names_a_target(env):
        return _refuse(early_path, token, started, root, "usage error", EXIT_USAGE, clock)
    try:
        parsed = _parser().parse_args(arguments)
    except SandboxError:
        return _fail("usage error", EXIT_USAGE)
    evidence = Path(parsed.evidence_out)
    if parsed.execute and parsed.dry_run:
        return _refuse(evidence, token, started, root, "usage error", EXIT_USAGE, clock)
    mode = "execute" if parsed.execute else "dry-run"
    if token is None:
        return _refuse(
            evidence, None, started, root, "notion sandbox token is missing", EXIT_NO_TOKEN, clock
        )
    if not token_shape_ok(token):
        return _refuse(
            evidence, token, started, root, "notion token shape is invalid", EXIT_USAGE, clock
        )
    if leaks(str(evidence), token):
        return _fail("usage error", EXIT_USAGE)
    active = client if client is not None else LiveSandboxClient(token)
    counts = empty_write_counts()
    active.write_counts = counts
    try:
        bot, page = _read_target(active)
    except Exception as exc:
        LOGGER.info("%s", redact_text(str(exc), token))
        ended = _now(clock)
        payload = _payload(
            mode=mode,
            started=started,
            ended=ended,
            stages=planned_stages(),
            created=[],
            counts=counts,
            bot_user_id=None,
            root=root,
        )
        payload["error"] = "notion api error"
        check = _emit(evidence, payload, token)
        _fail("notion api error", EXIT_API)
        return EXIT_REDACTION if check == "FAIL" else EXIT_API
    except BaseException as exc:
        _reraise(exc)
    if not target_ok(bot, page):
        return _finish_target(evidence, token, started, clock, mode, counts, bot, root)
    if mode == "dry-run":
        return _finish_dry_run(evidence, token, started, clock, counts, bot, root)
    chosen: object = sandbox_product_spec(started) if spec is None else spec
    with tempfile.TemporaryDirectory() as folder:
        ctx = SandboxRun(
            spec=chosen,
            client=active,
            checkpoint=Path(folder) / "checkpoint.json",
            moment=started,
            write_counts=counts,
        )
        stages = asyncio.run(_run_stages(ctx))
        created = list(ctx.created)
    failed = any(stage["status"] == "FAILED" for stage in stages)
    ended = _now(clock)
    payload = _payload(
        mode=mode,
        started=started,
        ended=ended,
        stages=stages,
        created=created,
        counts=counts,
        bot_user_id=bot.user_id,
        root=root,
    )
    if failed:
        payload["error"] = "sandbox stage failed"
    check = _emit(evidence, payload, token)
    if check == "FAIL":
        return EXIT_REDACTION
    if failed:
        return _fail("sandbox stage failed", EXIT_API)
    LOGGER.info("sandbox execute ok")
    return EXIT_OK


def _finish_target(
    evidence: Path,
    token: str,
    started: datetime,
    clock: Callable[[], datetime] | None,
    mode: str,
    counts: dict[str, int],
    bot: BotView,
    root: Path,
) -> int:
    ended = _now(clock)
    payload = _payload(
        mode=mode,
        started=started,
        ended=ended,
        stages=blocked_stages(),
        created=[],
        counts=counts,
        bot_user_id=bot.user_id,
        root=root,
    )
    payload["error"] = "sandbox target mismatch"
    check = _emit(evidence, payload, token)
    _fail("sandbox target mismatch", EXIT_TARGET)
    return EXIT_REDACTION if check == "FAIL" else EXIT_TARGET


def _finish_dry_run(
    evidence: Path,
    token: str,
    started: datetime,
    clock: Callable[[], datetime] | None,
    counts: dict[str, int],
    bot: BotView,
    root: Path,
) -> int:
    ended = _now(clock)
    payload = _payload(
        mode="dry-run",
        started=started,
        ended=ended,
        stages=planned_stages(),
        created=[],
        counts=counts,
        bot_user_id=bot.user_id,
        root=root,
    )
    check = _emit(evidence, payload, token)
    LOGGER.info("sandbox dry-run ok")
    return EXIT_REDACTION if check == "FAIL" else EXIT_OK


def _refuse(
    path: Path | None,
    token: str | None,
    started: datetime,
    root: Path,
    message: str,
    code: int,
    clock: Callable[[], datetime] | None,
) -> int:
    if path is not None and not leaks(str(path), token):
        ended = _now(clock)
        payload = _payload(
            mode="dry-run",
            started=started,
            ended=ended,
            stages=planned_stages(),
            created=[],
            counts=empty_write_counts(),
            bot_user_id=None,
            root=root,
        )
        payload["error"] = message
        check = _emit(path, payload, token)
        if check == "FAIL":
            _fail(message, code)
            return EXIT_REDACTION
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
