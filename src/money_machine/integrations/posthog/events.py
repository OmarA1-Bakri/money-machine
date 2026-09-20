"""PostHog-shaped telemetry event builders."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from money_machine.domain.events import TelemetryEventName


def build_posthog_event(
    *,
    event: TelemetryEventName,
    distinct_id: str,
    properties: dict[str, Any],
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    """Build one PostHog-compatible capture payload.

    The shape matches the PostHog capture API without performing a network call.
    """
    return {
        "distinct_id": distinct_id,
        "event": event.value,
        "properties": properties,
        "timestamp": (timestamp or datetime.now(UTC)).isoformat(),
    }


def agent_run_started_properties(
    *,
    job_id: UUID,
    agent_run_id: UUID,
    workflow_id: UUID | None,
    model: str | None,
    prompt_reference: str,
    run_number: int,
) -> dict[str, Any]:
    """Properties for ``agent_run_started`` telemetry."""
    properties: dict[str, Any] = {
        "job_id": str(job_id),
        "run_id": str(agent_run_id),
        "prompt_reference": prompt_reference,
        "run_number": run_number,
    }
    if workflow_id is not None:
        properties["workflow_id"] = str(workflow_id)
    if model is not None:
        properties["model"] = model
    return properties


def agent_run_completed_properties(
    *,
    job_id: UUID,
    agent_run_id: UUID,
    workflow_id: UUID | None,
    status: str,
    duration_ms: int,
    model: str | None,
    prompt_reference: str,
    run_number: int,
    token_count: int | None = None,
    cost_usd: Decimal | None = None,
    tool_call_count: int = 0,
) -> dict[str, Any]:
    """Properties for ``agent_run_completed`` telemetry."""
    properties = agent_run_started_properties(
        job_id=job_id,
        agent_run_id=agent_run_id,
        workflow_id=workflow_id,
        model=model,
        prompt_reference=prompt_reference,
        run_number=run_number,
    )
    properties.update(
        {
            "status": status,
            "duration_ms": duration_ms,
            "tool_call_count": tool_call_count,
        }
    )
    if token_count is not None:
        properties["token_count"] = token_count
    if cost_usd is not None:
        properties["cost_usd"] = str(cost_usd)
    return properties
