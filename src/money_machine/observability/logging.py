"""Structured JSON logging for agent-run observability."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TextIO

from money_machine.observability.correlation import CorrelationContext


@dataclass
class StructuredLogSink:
    """Collect structured log records for tests or forward them to a stream."""

    stream: TextIO = field(default_factory=lambda: sys.stdout)
    records: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())
    capture: bool = False

    def write(self, record: dict[str, Any]) -> None:
        """Persist one structured log record."""
        if self.capture:
            self.records.append(record)
        self.stream.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        self.stream.flush()


def emit_structured_log(
    *,
    sink: StructuredLogSink,
    level: str,
    event_type: str,
    message: str,
    correlation: CorrelationContext,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit one JSON log line with the observability contract fields."""
    record: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level,
        "event_type": event_type,
        "message": message,
        **correlation.as_log_fields(),
    }
    if metadata:
        record["metadata"] = metadata
    sink.write(record)
    return record
