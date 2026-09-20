"""Deterministic fake LLM provider for testing.

Provides fixed responses keyed by prompt content or schema, with no network calls.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from money_machine.integrations.llm.interface import (
    LLMCallMetadata,
    LLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    LLMValidationError,
    StructuredLLMResponse,
)
from money_machine.integrations.llm.structured_output import validate_structured_output


class FakeLLMProvider(LLMProvider):
    """Deterministic fake LLM provider for testing.

    Returns fixed responses based on configuration. Useful for:
    - Unit testing without network calls
    - Deterministic test scenarios
    - Simulating various response conditions (success, timeout, validation failure)

    Example:
        provider = FakeLLMProvider()
        provider.set_response(
            key="user_prompt",
            response='{"name": "Alice", "age": 30}'
        )
        result = await provider.complete_structured([...], UserModel)
    """

    def __init__(
        self,
        default_model: str = "fake-model-1",
        default_prompt_tokens: int = 10,
        default_completion_tokens: int = 20,
    ):
        """Initialize fake provider with defaults.

        Args:
            default_model: Default model name for metadata
            default_prompt_tokens: Default prompt token count
            default_completion_tokens: Default completion token count
        """
        self._default_model = default_model
        self._default_prompt_tokens = default_prompt_tokens
        self._default_completion_tokens = default_completion_tokens
        self._responses: dict[str, str] = {}
        self._errors: dict[str, Exception] = {}
        self._call_count: dict[str, int] = {}

    def set_response(self, key: str, response: str) -> None:
        """Configure a fixed JSON response for a given key.

        Args:
            key: Lookup key (typically a prompt substring or schema name)
            response: JSON string to return for this key
        """
        self._responses[key] = response

    def set_error(self, key: str, error: Exception) -> None:
        """Configure an error to raise for a given key.

        Args:
            key: Lookup key
            error: Exception to raise (LLMTimeoutError, LLMValidationError, etc.)
        """
        self._errors[key] = error

    def set_timeout(self, key: str) -> None:
        """Configure a timeout error for a given key.

        Args:
            key: Lookup key
        """
        self.set_error(key, LLMTimeoutError(f"Fake timeout for key: {key}"))

    def set_validation_error(self, key: str, message: str = "Fake validation error") -> None:
        """Configure a validation error for a given key.

        Args:
            key: Lookup key
            message: Error message
        """
        self.set_error(key, LLMValidationError(message))

    def get_call_count(self, key: str) -> int:
        """Get the number of times a key was called.

        Args:
            key: Lookup key

        Returns:
            Number of calls for this key
        """
        return self._call_count.get(key, 0)

    def reset(self) -> None:
        """Clear all configured responses, errors, and call counts."""
        self._responses.clear()
        self._errors.clear()
        self._call_count.clear()

    async def complete_structured[T: BaseModel](
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        model: str | None = None,
        prompt_version: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> StructuredLLMResponse[T]:
        """Return a configured fake response.

        Looks up responses by:
        1. Schema name (response_model.__name__)
        2. Last user message content
        3. Raises LLMProviderError if no match found

        See LLMProvider.complete_structured for full documentation.
        """
        # Try schema name first, then last message content
        schema_key = response_model.__name__
        message_key = next(
            (msg["content"] for msg in reversed(messages) if msg.get("role") == "user"),
            None,
        )

        # Find matching key
        lookup_key = None
        for candidate in [schema_key, message_key]:
            if candidate and candidate in self._responses:
                lookup_key = candidate
                break
            if candidate and candidate in self._errors:
                lookup_key = candidate
                break

        if lookup_key is None:
            raise LLMProviderError(
                f"No fake response configured for schema '{schema_key}' or message '{message_key}'"
            )

        # Track call count
        self._call_count[lookup_key] = self._call_count.get(lookup_key, 0) + 1

        # Check for configured error
        if lookup_key in self._errors:
            raise self._errors[lookup_key]

        # Get response
        raw_response = self._responses[lookup_key]

        # Validate against schema (fail-closed, just like real provider)
        parsed_content = validate_structured_output(raw_response, response_model)

        # Build metadata
        model_name = model or self._default_model
        metadata = LLMCallMetadata(
            model_name=model_name,
            prompt_version=prompt_version,
            prompt_tokens=self._default_prompt_tokens,
            completion_tokens=self._default_completion_tokens,
            total_tokens=self._default_prompt_tokens + self._default_completion_tokens,
            cost_usd=Decimal("0.001"),  # Fake cost
        )

        return StructuredLLMResponse(content=parsed_content, metadata=metadata)
