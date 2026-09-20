"""Offline PostHog client with an in-memory queue (no network calls)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from money_machine.config.settings import TelemetryConfig
from money_machine.domain.events import TelemetryEventName


class TelemetryNotAllowedError(ValueError):
    """Raised when telemetry is disabled or the event is not on the allow-list."""


@dataclass
class PostHogClient:
    """Queue PostHog-shaped events locally for later dispatch.

    Session 04 never requires a live PostHog connection. Events are validated against
    ``config/telemetry.yaml`` and queued for inspection or optional file persistence.
    """

    config: TelemetryConfig
    queue: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())
    queue_path: Path | None = None

    def capture(self, event: dict[str, Any]) -> None:
        """Validate and queue one PostHog-shaped capture payload."""
        if not self.config.enabled:
            raise TelemetryNotAllowedError("telemetry is disabled")
        event_name = event.get("event")
        if event_name not in {allowed.value for allowed in self.config.allowed_events}:
            raise TelemetryNotAllowedError(f"event {event_name!r} is not allowed")
        self.queue.append(event)
        if self.queue_path is not None:
            with self.queue_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")

    def capture_named(
        self,
        *,
        event: TelemetryEventName,
        distinct_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Build and queue one named telemetry event."""
        payload = {
            "distinct_id": distinct_id,
            "event": event.value,
            "properties": properties,
        }
        self.capture(payload)
        return payload

    def drain(self) -> tuple[dict[str, Any], ...]:
        """Return queued events and clear the in-memory queue."""
        queued = tuple(self.queue)
        self.queue.clear()
        return queued
