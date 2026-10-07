"""Merged build and variant stages for the sandbox runner.

QA, the fact ledger, the workflow link, and W11 stay out of this module.
The registry in ``notion_sandbox`` records those slots as ``NOT_RUN``.
``get_public_url`` is a fixture read. It is not a counted write.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
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


def _chain_reaches_sandbox(ctx: SandboxRun, page: PageView) -> None:
    current = page
    seen: set[str] = set()
    for _step in range(4):
        page_id = canonical_id(current.page_id)
        if page_id == SANDBOX_PARENT_PAGE_ID:
            if canonical_id(current.space_id) != SANDBOX_SPACE_ID or current.archived:
                raise SandboxError("created page is not under the requested parent")
            return
        parent_id = canonical_id(current.parent_id)
        if parent_id == "" or page_id == "" or page_id in seen:
            raise SandboxError("created page is not under the requested parent")
        seen.add(page_id)
        current = ctx.client.read_page(parent_id)
        if canonical_id(current.space_id) != SANDBOX_SPACE_ID or current.archived:
            raise SandboxError("created page is not under the requested parent")
    raise SandboxError("created page is not under the requested parent")


def create_under(ctx: SandboxRun, parent_id: str, title: str) -> PageView:
    allowed = (SANDBOX_PARENT_PAGE_ID, *ctx.created_ids)
    requested = canonical_id(parent_id)
    if not parent_is_allowed(requested, allowed):
        raise SandboxError("parent is not the sandbox parent")
    page = ctx.client.create_child_page(parent_id, title)
    ctx.write_counts["create_child_page"] = ctx.write_counts.get("create_child_page", 0) + 1
    page_id = canonical_id(page.page_id)
    if page_id in {"", SANDBOX_PARENT_PAGE_ID, requested}:
        raise SandboxError("created page is not new")
    if canonical_id(page.parent_id) != requested:
        raise SandboxError("created page is not under the requested parent")
    if canonical_id(page.space_id) != SANDBOX_SPACE_ID:
        raise SandboxError("created page is not under the requested parent")
    confirmed = ctx.client.read_page(page_id)
    if canonical_id(confirmed.page_id) != page_id:
        raise SandboxError("created page is not under the requested parent")
    if canonical_id(confirmed.parent_id) != requested:
        raise SandboxError("created page is not under the requested parent")
    if canonical_id(confirmed.space_id) != SANDBOX_SPACE_ID or confirmed.archived:
        raise SandboxError("created page is not under the requested parent")
    _chain_reaches_sandbox(ctx, confirmed)
    ctx.created_ids.append(page_id)
    ctx.created.append(
        {"id": page_id, "parent_id": canonical_id(confirmed.parent_id), "url": confirmed.url}
    )
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
