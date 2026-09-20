"""Jev Gateway client for decision evaluation.

Provides in-process SDK-shaped API: one evaluate call → many typed questions.
Prefers Gateway HTTP API over subprocess CLI; fail-closed if provider down.
"""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from typing import Final

import httpx

from money_machine.integrations.jev.models import DecisionPacket, DecisionResult


class JevClientError(Exception):
    """Base exception for Jev client errors."""


class JevTimeoutError(JevClientError):
    """Raised when a Jev evaluation times out."""


class JevClient(ABC):
    """Abstract base class for Jev decision clients.

    Implementations must support:
    - Evaluate one packet (multiple questions)
    - Timeout enforcement
    - Retry logic for transient failures
    - Metadata capture (model_id, latency_ms)
    - Fail-closed: if provider down, raise error
    """

    DEFAULT_TIMEOUT_SECONDS: Final = 30.0
    DEFAULT_MAX_RETRIES: Final = 3

    @abstractmethod
    async def evaluate(
        self,
        packet: DecisionPacket,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> DecisionResult:
        """Evaluate a decision packet with Jev.

        Retries apply to transport/timeout errors only.
        Fail-closed: if provider unreachable, raise error (no silent fallback).

        Args:
            packet: Decision packet with context and questions
            timeout: Timeout in seconds (uses DEFAULT_TIMEOUT_SECONDS if None)
            max_retries: Max retries for transport/timeout failures
                (uses DEFAULT_MAX_RETRIES if None)

        Returns:
            DecisionResult with answers and metadata

        Raises:
            JevTimeoutError: If the call exceeds the timeout (after retry budget)
            JevClientError: For other provider-specific errors (after retry budget)
        """


class JevGatewayClient(JevClient):
    """Jev Gateway HTTP client implementation.

    Calls the Jev Gateway evaluate API with automatic retry and timeout.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        default_timeout: float = JevClient.DEFAULT_TIMEOUT_SECONDS,
    ):
        """Initialize Jev Gateway client.

        Args:
            base_url: Gateway base URL (reads JEV_GATEWAY_URL env var if None)
            api_key: Gateway API key (reads JEV_API_KEY env var if None)
            default_timeout: Default timeout in seconds

        Raises:
            JevClientError: If required config missing
        """
        self._base_url = base_url or os.getenv("JEV_GATEWAY_URL")
        if not self._base_url:
            raise JevClientError("JEV_GATEWAY_URL environment variable or base_url parameter required")

        self._api_key = api_key or os.getenv("JEV_API_KEY")
        if not self._api_key:
            raise JevClientError("JEV_API_KEY environment variable or api_key parameter required")

        self._default_timeout = default_timeout

    async def evaluate(
        self,
        packet: DecisionPacket,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> DecisionResult:
        """Evaluate a decision packet via Jev Gateway HTTP API.

        See JevClient.evaluate for full documentation.
        """
        timeout_seconds = timeout if timeout is not None else self._default_timeout
        max_attempts = (max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES) + 1

        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return await self._call_gateway(packet, timeout_seconds)
            except (httpx.TimeoutException, httpx.RequestError) as e:
                last_error = e
                if attempt < max_attempts:
                    # Exponential backoff: 1s, 2s, 4s
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                # Final attempt failed
                if isinstance(e, httpx.TimeoutException):
                    raise JevTimeoutError(
                        f"Jev Gateway timed out after {timeout_seconds}s (attempt {attempt}/{max_attempts})"
                    ) from e
                raise JevClientError(
                    f"Jev Gateway request failed (attempt {attempt}/{max_attempts}): {e}"
                ) from e

        # Should never reach here, but satisfy type checker
        raise JevClientError(f"Jev Gateway evaluation failed after {max_attempts} attempts") from last_error

    async def _call_gateway(self, packet: DecisionPacket, timeout: float) -> DecisionResult:
        """Make one HTTP call to Jev Gateway evaluate endpoint."""
        import time

        start_ms = int(time.time() * 1000)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self._base_url}/evaluate",
                json=packet.model_dump(),
                headers={"Authorization": f"Bearer {self._api_key}"},
            )

            if response.status_code != 200:
                raise JevClientError(
                    f"Jev Gateway returned {response.status_code}: {response.text}"
                )

            try:
                result_data = response.json()
            except Exception as e:
                raise JevClientError(f"Failed to parse Jev Gateway response: {e}") from e

            end_ms = int(time.time() * 1000)
            latency_ms = end_ms - start_ms

            # Build DecisionResult from response
            # Expect: {"decision_type": "...", "answers": {...}, "model_id": "..."}
            try:
                return DecisionResult(
                    decision_type=result_data["decision_type"],
                    answers=result_data["answers"],
                    model_id=result_data.get("model_id", "unknown"),
                    latency_ms=result_data.get("latency_ms", latency_ms),
                    metadata=result_data.get("metadata", {}),
                )
            except (KeyError, TypeError) as e:
                raise JevClientError(f"Unexpected Jev Gateway response structure: {e}") from e
