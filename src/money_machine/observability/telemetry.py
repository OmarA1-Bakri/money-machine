"""Telemetry emission helpers for agent-run observability."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from money_machine.domain.events import TelemetryEventName
from money_machine.integrations.posthog.events import (
    agent_run_completed_properties,
    agent_run_started_properties,
    build_posthog_event,
)
from money_machine.observability.correlation import CorrelationContext

if TYPE_CHECKING:
    from money_machine.integrations.posthog.client import PostHogClient


def emit_agent_run_started(
    client: PostHogClient,
    *,
    correlation: CorrelationContext,
    agent_run_id: UUID,
    prompt_reference: str,
    run_number: int,
    model: str | None,
) -> dict[str, object]:
    """Queue an ``agent_run_started`` PostHog-shaped event."""
    properties = agent_run_started_properties(
        job_id=correlation.job_id,
        agent_run_id=agent_run_id,
        workflow_id=correlation.workflow_id,
        model=model,
        prompt_reference=prompt_reference,
        run_number=run_number,
    )
    event = build_posthog_event(
        event=TelemetryEventName.AGENT_RUN_STARTED,
        distinct_id=correlation.agent_id,
        properties=properties,
    )
    client.capture(event)
    return event


def emit_agent_run_completed(
    client: PostHogClient,
    *,
    correlation: CorrelationContext,
    agent_run_id: UUID,
    prompt_reference: str,
    run_number: int,
    model: str | None,
    status: str,
    duration_ms: int,
    token_count: int | None = None,
    cost_usd: Decimal | None = None,
    tool_call_count: int = 0,
) -> dict[str, object]:
    """Queue an ``agent_run_completed`` PostHog-shaped event."""
    properties = agent_run_completed_properties(
        job_id=correlation.job_id,
        agent_run_id=agent_run_id,
        workflow_id=correlation.workflow_id,
        status=status,
        duration_ms=duration_ms,
        model=model,
        prompt_reference=prompt_reference,
        run_number=run_number,
        token_count=token_count,
        cost_usd=cost_usd,
        tool_call_count=tool_call_count,
    )
    event = build_posthog_event(
        event=TelemetryEventName.AGENT_RUN_COMPLETED,
        distinct_id=correlation.agent_id,
        properties=properties,
    )
    client.capture(event)
    return event
