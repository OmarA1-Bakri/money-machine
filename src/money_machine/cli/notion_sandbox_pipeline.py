"""Merged build and variant stages for the sandbox runner.

QA, the fact ledger, the workflow link, and W11 stay out of this module.
The registry in ``notion_sandbox`` records those slots as ``NOT_RUN``.
``get_public_url`` is a fixture read. It is not a counted write.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import NoReturn
from uuid import UUID

from money_machine.agents.implementations.notion_aesthetics import (
    build_aesthetics_and_content_completion,
)
from money_machine.agents.implementations.notion_dashboard import build_dashboard_and_navigation
from money_machine.agents.implementations.notion_hubs import build_identity_specific_hubs
from money_machine.agents.implementations.notion_notifications import build_notification_dashboard
from money_machine.agents.implementations.notion_product_builder import (
    build_top_level_page_and_design_shell,
)
from money_machine.agents.implementations.notion_shared_databases import build_shared_databases
from money_machine.agents.implementations.notion_variants import build_variants
from money_machine.cli.notion_sandbox_guard import (
    PIPELINE_WRITE_METHODS,
    SANDBOX_PARENT_PAGE_ID,
    SANDBOX_SPACE_ID,
    PageView,
    SandboxClient,
    SandboxError,
    canonical_id,
    parent_is_allowed,
    space_conflicts,
)
from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.product_spec import ColourToken, Hub, ProductSpec
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter

_SPEC_ID = UUID("11111111-1111-4111-8111-111111111111")
_PRODUCT_ID = UUID("22222222-2222-4222-8222-222222222222")
_WORKFLOW_ID = UUID("33333333-3333-4333-8333-333333333333")
_JOB_ID = UUID("44444444-4444-4444-8444-444444444444")
_AGENT_RUN_ID = UUID("55555555-5555-4555-8555-555555555555")
_EVIDENCE_ID = UUID("66666666-6666-4666-8666-666666666666")


@dataclass
class SandboxRun:
    spec: object
    client: SandboxClient
    checkpoint: Path
    moment: datetime
    write_counts: dict[str, int]
    created_ids: list[str] = field(default_factory=list)
    created: list[dict[str, str]] = field(default_factory=list)
    probe: FixtureNotionAdapter | None = None
    product_page_id: str | None = None
    bot_user_id: str = ""
    bot_space_id: str = ""
    rejected_pages: list[dict[str, str]] = field(default_factory=list)
    flagged_pages: list[dict[str, str]] = field(default_factory=list)
    possible_orphans: list[dict[str, str]] = field(default_factory=list)


# Notion floors created_time to the minute. Two minutes covers a clock that
# is a second ahead across that boundary. A page from a previous day is still stale.
_FRESH_SKEW = timedelta(minutes=2)


def sandbox_product_spec(moment: datetime) -> ProductSpec:
    """The one product this runner builds under the sandbox parent."""
    return ProductSpec(
        spec_id=_SPEC_ID,
        product_id=_PRODUCT_ID,
        workflow_id=_WORKFLOW_ID,
        version=1,
        producing_job_id=_JOB_ID,
        producing_agent_run_id=_AGENT_RUN_ID,
        identity="Weekly Planner",
        base_category="Planners",
        buyer_problem="Keep one week visible",
        title="Sandbox Weekly Planner",
        tier="mass",
        real_price=Decimal("9.99"),
        anchor_price=Decimal("19.99"),
        currency="USD",
        palette_name="Modern Minimalist",
        palette_tokens=(
            ColourToken(name="Primary", hex="#2C3E50"),
            ColourToken(name="Secondary", hex="#3498DB"),
            ColourToken(name="Accent", hex="#E74C3C"),
            ColourToken(name="Neutral", hex="#111111"),
        ),
        hubs=tuple(
            Hub(name=f"Hub {index}", description=f"Weekly Planner copy {index}", page_count=3)
            for index in range(1, 7)
        ),
        colour_variants=("Blue", "Green", "Purple", "Gold"),
        flagship_feature="One visible week",
        shared_databases=(),
        page_target_min=40,
        page_target_max=60,
        experiment_hypothesis="A visible week is enough",
        concept_fingerprint="c" * 64,
        rule_version="v1",
        evidence=(
            EvidenceReference(
                evidence_id=_EVIDENCE_ID,
                evidence_type="sandbox",
                source_reference="money_machine.cli.notion_sandbox",
                observed_at=moment,
                safe_summary="Sandbox product for the asserted parent",
            ),
        ),
        created_at=moment,
    )


def _watch(probe: FixtureNotionAdapter, counts: dict[str, int]) -> None:
    for name in PIPELINE_WRITE_METHODS:
        original = getattr(probe, name)

        def _bind(
            method: Callable[..., Awaitable[object]],
            label: str,
        ) -> Callable[..., Awaitable[object]]:
            async def _wrapped(*args: object, **kwargs: object) -> object:
                counts[label] = counts.get(label, 0) + 1
                return await method(*args, **kwargs)

            return _wrapped

        setattr(probe, name, _bind(original, name))


def _drop_tail(ctx: SandboxRun, page_id: str, before: int) -> None:
    """Remove an id this create just published. An earlier id stays put."""
    if page_id not in ctx.created_ids:
        return
    if ctx.created_ids.index(page_id) < before:
        return
    _drop_recorded(ctx, page_id)


def _drop_recorded(ctx: SandboxRun, page_id: str) -> None:
    """Remove one id in place. Callers that bound the list keep that object."""
    if page_id == "" or page_id not in ctx.created_ids:
        return
    ctx.created_ids.remove(page_id)
    ctx.created[:] = [row for row in ctx.created if row.get("id") != page_id]


def _flag(ctx: SandboxRun, page_id: str, reason: str) -> None:
    if page_id == "":
        return
    for row in ctx.flagged_pages:
        if row.get("id") == page_id and row.get("reason") == reason:
            return
    ctx.flagged_pages.append({"id": page_id, "reason": reason})


def _remember(ctx: SandboxRun, page: PageView, page_id: str) -> None:
    if page_id == "" or page_id in ctx.created_ids:
        return
    ctx.created_ids.append(page_id)
    ctx.created.append({"id": page_id, "parent_id": canonical_id(page.parent_id), "url": page.url})


def _reject_unfresh(ctx: SandboxRun, page: PageView) -> NoReturn:
    """A stale or other-user page is not ours. Cleanup must not delete it."""
    page_id = canonical_id(page.page_id)
    if page_id in ctx.created_ids:
        ctx.created_ids.remove(page_id)
    ctx.created[:] = [row for row in ctx.created if row.get("id") != page_id]
    if page_id != "" and all(row.get("id") != page_id for row in ctx.rejected_pages):
        ctx.rejected_pages.append({"id": page_id, "reason": "not_new"})
    raise SandboxError("created page is not new")


def _request_fingerprint(parent_id: str, title: str) -> str:
    return hashlib.sha256(f"{parent_id}\n{title}".encode()).hexdigest()


def _earliest(moment: datetime) -> datetime:
    floored = moment.astimezone(UTC).replace(second=0, microsecond=0)
    return floored - _FRESH_SKEW


def _latest(moment: datetime) -> datetime:
    """A created time past this is a provider lie, not a clock a little behind."""
    return moment.astimezone(UTC) + _FRESH_SKEW


def _align(ctx: SandboxRun, page: PageView, before: int) -> str:
    """Keep the evidence id equal to the page the create returned."""
    page_id = canonical_id(page.page_id)
    remaining = len(ctx.created_ids) - before
    guard = remaining + 1
    while len(ctx.created_ids) > before:
        if guard <= 0:
            raise SandboxError("created id list did not shrink")
        guard -= 1
        tail = ctx.created_ids[-1]
        if tail == page_id:
            break
        _drop_tail(ctx, tail, before)
    # _remember, _flag, and _drop_recorded each ignore a blank id.
    if space_conflicts(page.space_id):
        if page_id in ctx.created_ids[:before]:
            _drop_recorded(ctx, page_id)
            return page_id
        _remember(ctx, page, page_id)
        _flag(ctx, page_id, "space_conflict")
        return page_id
    _remember(ctx, page, page_id)
    return page_id


def _fresh(ctx: SandboxRun, page: PageView) -> None:
    if page.created_by != ctx.bot_user_id:
        _reject_unfresh(ctx, page)
    moment = page.created_time
    if moment is None:
        _reject_unfresh(ctx, page)
    if moment.tzinfo is None:
        _reject_unfresh(ctx, page)
    if moment < _earliest(ctx.moment):
        _reject_unfresh(ctx, page)
    if moment > _latest(ctx.moment):
        _reject_unfresh(ctx, page)


def chain_reaches_sandbox(ctx: SandboxRun, page: PageView) -> None:
    created_id = canonical_id(page.page_id)
    current = page
    seen: set[str] = set()
    for _step in range(4):
        page_id = canonical_id(current.page_id)
        if page_id == SANDBOX_PARENT_PAGE_ID:
            if space_conflicts(current.space_id) or current.archived:
                _flag(ctx, created_id, "chain")
                raise SandboxError("created page is not under the requested parent")
            return
        parent_id = canonical_id(current.parent_id)
        if parent_id == "" or page_id == "" or page_id in seen:
            raise SandboxError("created page is not under the requested parent")
        seen.add(page_id)
        current = ctx.client.read_page(parent_id)
        if canonical_id(current.page_id) != parent_id:
            _flag(ctx, created_id, "chain_id")
            raise SandboxError("created page is not under the requested parent")
        if space_conflicts(current.space_id) or current.archived:
            _flag(ctx, created_id, "chain")
            raise SandboxError("created page is not under the requested parent")
    raise SandboxError("created page is not under the requested parent")


def create_under(ctx: SandboxRun, parent_id: str, title: str) -> PageView:
    allowed = (SANDBOX_PARENT_PAGE_ID, *ctx.created_ids)
    requested = canonical_id(parent_id)
    if not parent_is_allowed(requested, allowed):
        raise SandboxError("parent is not the sandbox parent")
    if canonical_id(ctx.bot_space_id) != SANDBOX_SPACE_ID:
        raise SandboxError("created page is not under the requested parent")
    before = len(ctx.created_ids)
    marker = {
        "fingerprint": _request_fingerprint(requested, title),
        "parent_id": requested,
    }
    ctx.possible_orphans.append(marker)
    try:
        page = ctx.client.create_child_page(parent_id, title)
    except BaseException:
        raise
    ctx.possible_orphans.remove(marker)
    ctx.write_counts["create_child_page"] = ctx.write_counts.get("create_child_page", 0) + 1
    page_id = _align(ctx, page, before)
    if page_id in {"", SANDBOX_PARENT_PAGE_ID, requested}:
        if page_id not in {"", SANDBOX_PARENT_PAGE_ID}:
            _flag(ctx, page_id, "not_new")
        else:
            _drop_recorded(ctx, page_id)
        raise SandboxError("created page is not new")
    if page_id in ctx.created_ids[:before]:
        raise SandboxError("created page is not new")
    if space_conflicts(page.space_id):
        _flag(ctx, page_id, "space_conflict")
        raise SandboxError("created page is not under the requested parent")
    if canonical_id(page.parent_id) != requested:
        raise SandboxError("created page is not under the requested parent")
    _fresh(ctx, page)
    confirmed = ctx.client.read_page(page_id)
    if canonical_id(confirmed.page_id) != page_id:
        raise SandboxError("created page is not under the requested parent")
    if canonical_id(confirmed.parent_id) != requested:
        raise SandboxError("created page is not under the requested parent")
    if space_conflicts(confirmed.space_id) or confirmed.archived:
        reason = "archived" if confirmed.archived else "space_conflict"
        _flag(ctx, page_id, reason)
        raise SandboxError("created page is not under the requested parent")
    _fresh(ctx, confirmed)
    chain_reaches_sandbox(ctx, confirmed)
    if ctx.created and ctx.created[-1].get("id") == page_id:
        ctx.created[-1] = {
            "id": page_id,
            "parent_id": canonical_id(confirmed.parent_id),
            "url": confirmed.url,
        }
    return confirmed


async def _run_build(ctx: SandboxRun) -> None:
    probe = FixtureNotionAdapter()
    _watch(probe, ctx.write_counts)
    ctx.probe = probe
    spec = ctx.spec
    path = ctx.checkpoint
    moment = ctx.moment
    await build_top_level_page_and_design_shell(spec, probe, path, recorded_at=moment)
    await build_shared_databases(spec, probe, path, recorded_at=moment)
    await build_dashboard_and_navigation(spec, probe, path, recorded_at=moment)
    await build_identity_specific_hubs(spec, probe, path, recorded_at=moment)
    await build_notification_dashboard(spec, probe, path, recorded_at=moment)
    await build_aesthetics_and_content_completion(spec, probe, path, recorded_at=moment)
    if type(spec) is not ProductSpec:
        raise SandboxError("build requires a ProductSpec")
    created = create_under(ctx, SANDBOX_PARENT_PAGE_ID, spec.title)
    ctx.product_page_id = canonical_id(created.page_id)


async def _run_variants(ctx: SandboxRun) -> None:
    spec = ctx.spec
    if ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec:
        raise SandboxError("variants require the build stage")
    await build_variants(spec, ctx.probe, ctx.checkpoint, recorded_at=ctx.moment)
    for colour in spec.colour_variants:
        create_under(ctx, ctx.product_page_id, f"{spec.title} / {colour}")


def stage_runners() -> dict[str, Callable[[SandboxRun], Awaitable[None]]]:
    return {"run_build": _run_build, "run_variants": _run_variants}
