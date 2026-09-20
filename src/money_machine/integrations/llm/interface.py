"""LLM provider interface and common types.

Defines the contract for LLM providers that support structured JSON outputs.
Follows OpenAI Chat Completions API patterns (September 2026 revision).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, ConfigDict, Field


class LLMCallMetadata(BaseModel):
    """Metadata captured from a successful LLM provider call."""

    model_config = ConfigDict(frozen=True, strict=True)

    model_name: str = Field(description="Model identifier used for this call")
    prompt_version: str | None = Field(
        default=None, description="Optional prompt version identifier"
    )
    prompt_tokens: int | None = Field(default=None, ge=0, description="Input token count")
    completion_tokens: int | None = Field(default=None, ge=0, description="Output token count")
    total_tokens: int | None = Field(default=None, ge=0, description="Total token count")
    cost_usd: Decimal | None = Field(default=None, ge=Decimal("0"), description="Call cost in USD")


class StructuredLLMResponse[T](BaseModel):
    """Structured response from an LLM provider with metadata."""

    model_config = ConfigDict(frozen=True, strict=True, arbitrary_types_allowed=True)

    content: T = Field(description="Parsed response content matching the requested schema")
    metadata: LLMCallMetadata = Field(description="Metadata about the LLM call")


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""


class LLMTimeoutError(LLMProviderError):
    """Raised when an LLM provider call times out."""


class LLMValidationError(LLMProviderError):
    """Raised when an LLM response fails structured output validation (fail-closed)."""


class LLMProvider(ABC):
    """Abstract base class for LLM providers with structured output support.

    Implementations must support:
    - Chat completions with structured JSON schema output
    - Timeout enforcement
    - Retry logic for transient failures
    - Metadata capture (tokens, cost, model version)
    """

    DEFAULT_TIMEOUT_SECONDS: Final = 60.0
    DEFAULT_MAX_RETRIES: Final = 3

    @abstractmethod
    async def complete_structured[T: BaseModel](
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        model: str | None = None,
        prompt_version: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> StructuredLLMResponse[T]:
        """Request a structured JSON completion from the LLM provider.

        Retries apply to transport/timeout errors only. Validation errors fail-close immediately.

        Args:
            messages: Chat messages in OpenAI format [{"role": "...", "content": "..."}]
            response_model: Pydantic model defining the expected response schema
            model: Optional model override (uses provider default if None)
            prompt_version: Optional prompt version for metadata tracking
            timeout: Timeout in seconds (uses DEFAULT_TIMEOUT_SECONDS if None)
            max_retries: Max retries for transport/timeout failures
                (uses DEFAULT_MAX_RETRIES if None)

        Returns:
            StructuredLLMResponse containing parsed content and metadata

        Raises:
            LLMTimeoutError: If the call exceeds the timeout (after retry budget)
            LLMValidationError: If the response fails schema validation (fail-closed, no retry)
            LLMProviderError: For other provider-specific errors (after retry budget)
        """
