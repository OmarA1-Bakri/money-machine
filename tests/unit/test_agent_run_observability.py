"""Unit tests for agent-run observability: structured logs and PostHog-shaped events."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from money_machine.config.settings import TelemetryConfig
from money_machine.domain.events import TelemetryEventName
from money_machine.integrations.posthog.client import PostHogClient, TelemetryNotAllowedError
from money_machine.integrations.posthog.events import (
    agent_run_completed_properties,
    build_posthog_event,
)
from money_machine.observability.correlation import CorrelationContext
from money_machine.observability.logging import StructuredLogSink, emit_structured_log
from money_machine.observability.telemetry import emit_agent_run_completed, emit_agent_run_started


def _telemetry_config(enabled: bool = True) -> TelemetryConfig:
    return TelemetryConfig(
        version=1,
        enabled=enabled,
        allowed_events=tuple(TelemetryEventName),
    )


def test_structured_log_emits_required_fields() -> None:
    """Structured logs carry timestamp, level, event_type, correlation, and message."""
    sink = StructuredLogSink(capture=True)
    job_id = uuid4()
    run_id = uuid4()

    record = emit_structured_log(
        sink=sink,
        level="INFO",
        event_type="agent_run_started",
        message="agent run started",
        correlation=CorrelationContext(
            job_id=job_id,
            agent_id="A01",
            workflow_id=uuid4(),
            agent_run_id=run_id,
            job_type="RESEARCH",
            attempt=1,
        ),
        metadata={"model": "fake-model"},
    )

    assert record["level"] == "INFO"
    assert record["event_type"] == "agent_run_started"
    assert record["job_id"] == str(job_id)
    assert record["agent_id"] == "A01"
    assert record["agent_run_id"] == str(run_id)
    assert record["metadata"] == {"model": "fake-model"}
    assert "timestamp" in record
    assert len(sink.records) == 1


def test_posthog_event_builder_matches_capture_shape() -> None:
    """PostHog-shaped events include distinct_id, event name, properties, and timestamp."""
    job_id = uuid4()
    run_id = uuid4()
    properties = agent_run_completed_properties(
        job_id=job_id,
        agent_run_id=run_id,
        workflow_id=uuid4(),
        status="SUCCESS",
        duration_ms=1200,
        model="gpt-test",
        prompt_reference="prompt://A01/system",
        run_number=2,
        token_count=150,
        cost_usd=Decimal("0.0042"),
        tool_call_count=1,
    )
    event = build_posthog_event(
        event=TelemetryEventName.AGENT_RUN_COMPLETED,
        distinct_id="A01",
        properties=properties,
    )

    assert event["distinct_id"] == "A01"
    assert event["event"] == "agent_run_completed"
    assert event["properties"]["job_id"] == str(job_id)
    assert event["properties"]["run_id"] == str(run_id)
    assert event["properties"]["status"] == "SUCCESS"
    assert event["properties"]["token_count"] == 150
    assert event["properties"]["cost_usd"] == "0.0042"
    assert "timestamp" in event


def test_posthog_client_queues_without_network() -> None:
    """Allowed telemetry events queue locally when telemetry is enabled."""
    client = PostHogClient(config=_telemetry_config())
    correlation = CorrelationContext(job_id=uuid4(), agent_id="A02")
    run_id = uuid4()

    emit_agent_run_started(
        client,
        correlation=correlation,
        agent_run_id=run_id,
        prompt_reference="prompt://A02/system",
        run_number=1,
        model="fake-model",
    )
    emit_agent_run_completed(
        client,
        correlation=correlation,
        agent_run_id=run_id,
        prompt_reference="prompt://A02/system",
        run_number=1,
        model="fake-model",
        status="SUCCESS",
        duration_ms=500,
        token_count=42,
        cost_usd=Decimal("0.001"),
    )

    queued = client.drain()
    assert len(queued) == 2
    assert queued[0]["event"] == "agent_run_started"
    assert queued[1]["event"] == "agent_run_completed"


def test_posthog_client_rejects_disallowed_event() -> None:
    """Telemetry allow-list is enforced before queueing."""
    client = PostHogClient(
        config=TelemetryConfig(
            version=1,
            enabled=True,
            allowed_events=(TelemetryEventName.WORKFLOW_STARTED,),
        )
    )

    with pytest.raises(TelemetryNotAllowedError, match="not allowed"):
        client.capture_named(
            event=TelemetryEventName.AGENT_RUN_COMPLETED,
            distinct_id="A01",
            properties={"job_id": str(uuid4())},
        )


def test_posthog_client_rejects_when_disabled() -> None:
    """Disabled telemetry refuses capture rather than silently queueing."""
    client = PostHogClient(config=_telemetry_config(enabled=False))

    with pytest.raises(TelemetryNotAllowedError, match="disabled"):
        client.capture_named(
            event=TelemetryEventName.AGENT_RUN_STARTED,
            distinct_id="A01",
            properties={"job_id": str(uuid4())},
        )
