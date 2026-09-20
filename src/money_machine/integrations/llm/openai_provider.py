"""OpenAI-compatible HTTP provider with structured JSON outputs.

Implements LLMProvider for OpenAI Chat Completions API (September 2026 revision).
Configurable base URL supports OpenAI-compatible endpoints.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Final

import httpx
from pydantic import BaseModel

from money_machine.integrations.llm.interface import (
    LLMCallMetadata,
    LLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    StructuredLLMResponse,
)
from money_machine.integrations.llm.structured_output import (
    pydantic_to_json_schema,
    validate_structured_output,
)


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible LLM provider with structured outputs.

    Reads configuration from environment:
    - OPENAI_API_KEY: Required API key
    - OPENAI_BASE_URL: Optional base URL (defaults to https://api.openai.com/v1)
    - OPENAI_DEFAULT_MODEL: Optional default model (defaults to gpt-4o)
    """

    DEFAULT_BASE_URL: Final = "https://api.openai.com/v1"
    DEFAULT_MODEL: Final = "gpt-4o"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
    ):
        """Initialize OpenAI provider with optional overrides.

        Args:
            api_key: API key (reads from OPENAI_API_KEY if None)
            base_url: Base URL (reads from OPENAI_BASE_URL if None, defaults to DEFAULT_BASE_URL)
            default_model: Default model (reads from OPENAI_DEFAULT_MODEL if None)

        Raises:
            LLMProviderError: If API key is not provided or found in environment
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise LLMProviderError(
                "OPENAI_API_KEY environment variable or api_key parameter required"
            )

        self._base_url = (
            base_url or os.environ.get("OPENAI_BASE_URL") or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self._default_model = (
            default_model or os.environ.get("OPENAI_DEFAULT_MODEL") or self.DEFAULT_MODEL
        )

    async def complete_structured[T: BaseModel](
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        model: str | None = None,
        prompt_version: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> StructuredLLMResponse[T]:
        """Request a structured JSON completion from OpenAI Chat Completions API.

        See LLMProvider.complete_structured for full documentation.
        """
        model_name = model or self._default_model
        timeout_seconds = timeout if timeout is not None else self.DEFAULT_TIMEOUT_SECONDS
        retries = max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES

        # Generate JSON schema from Pydantic model
        json_schema = pydantic_to_json_schema(response_model)

        # Build request payload per OpenAI Chat Completions API (September 2026)
        request_payload = {
            "model": model_name,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": json_schema,
                },
            },
        }

        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                response_data = await self._make_request(request_payload, timeout_seconds)

                # Extract response content
                raw_content = response_data["choices"][0]["message"]["content"]

                # Validate against schema (fail-closed)
                parsed_content = validate_structured_output(raw_content, response_model)

                # Extract metadata
                usage = response_data.get("usage", {})
                metadata = LLMCallMetadata(
                    model_name=model_name,
                    prompt_version=prompt_version,
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                    cost_usd=None,  # Cost calculation can be added based on model pricing
                )

                return StructuredLLMResponse(content=parsed_content, metadata=metadata)

            except (TimeoutError, httpx.TimeoutException) as error:
                if attempt == retries:
                    raise LLMTimeoutError(
                        f"Request timed out after {timeout_seconds}s "
                        f"(attempt {attempt + 1}/{retries + 1})"
                    ) from error
                last_error = error
                # Exponential backoff: 1s, 2s, 4s
                await asyncio.sleep(2**attempt)

            except (httpx.HTTPStatusError, httpx.RequestError) as error:
                if attempt == retries:
                    raise LLMProviderError(
                        f"HTTP request failed after {retries + 1} attempts: {error!s}"
                    ) from error
                last_error = error
                await asyncio.sleep(2**attempt)

        # Shouldn't reach here, but for type safety
        raise LLMProviderError(f"Failed after {retries + 1} attempts") from last_error

    async def _make_request(self, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        """Make HTTP request to OpenAI Chat Completions endpoint.

        Args:
            payload: Request payload
            timeout: Request timeout in seconds

        Returns:
            Response JSON as dict

        Raises:
            httpx.TimeoutException: If request times out
            httpx.HTTPStatusError: If HTTP status is not 2xx
            httpx.RequestError: For other HTTP errors
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
