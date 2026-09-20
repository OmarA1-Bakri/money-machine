"""Unit tests for LLM provider implementations.

Tests the LLMProvider interface, FakeLLMProvider, OpenAIProvider (mocked),
structured output validation, timeout/retry behavior, and metadata capture.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel, Field

from money_machine.integrations.llm import (
    FakeLLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    LLMValidationError,
    OpenAIProvider,
    pydantic_to_json_schema,
    validate_structured_output,
)


# Test models
class SimpleResponse(BaseModel):
    """Simple test response model."""

    name: str = Field(description="User name")
    age: int = Field(description="User age", ge=0)


class NestedResponse(BaseModel):
    """Nested response model for testing complex schemas."""

    user: SimpleResponse
    active: bool


class TestStructuredOutputValidator:
    """Tests for structured output validation logic."""

    def test_validate_valid_json(self) -> None:
        """Valid JSON matching schema parses successfully."""
        raw = '{"name": "Alice", "age": 30}'
        result = validate_structured_output(raw, SimpleResponse)

        assert result.name == "Alice"
        assert result.age == 30

    def test_validate_invalid_json(self) -> None:
        """Malformed JSON raises LLMValidationError (fail-closed)."""
        raw = '{"name": "Alice", "age": '  # Incomplete JSON

        with pytest.raises(LLMValidationError, match="Failed to parse"):
            validate_structured_output(raw, SimpleResponse)

    def test_validate_schema_mismatch(self) -> None:
        """JSON not matching schema raises LLMValidationError (fail-closed)."""
        raw = '{"name": "Alice", "age": "thirty"}'  # age should be int

        with pytest.raises(LLMValidationError, match="failed schema validation"):
            validate_structured_output(raw, SimpleResponse)

    def test_validate_missing_required_field(self) -> None:
        """Missing required field raises LLMValidationError (fail-closed)."""
        raw = '{"name": "Alice"}'  # Missing 'age'

        with pytest.raises(LLMValidationError, match="failed schema validation"):
            validate_structured_output(raw, SimpleResponse)

    def test_validate_nested_model(self) -> None:
        """Nested models validate correctly."""
        raw = '{"user": {"name": "Bob", "age": 25}, "active": true}'
        result = validate_structured_output(raw, NestedResponse)

        assert result.user.name == "Bob"
        assert result.user.age == 25
        assert result.active is True


class TestPydanticToJsonSchema:
    """Tests for Pydantic to JSON schema conversion."""

    def test_simple_model_schema(self) -> None:
        """Simple model converts to strict JSON schema."""
        schema = pydantic_to_json_schema(SimpleResponse)

        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]
        assert schema["required"] == ["name", "age"]
        assert schema["additionalProperties"] is False

    def test_nested_model_schema(self) -> None:
        """Nested model converts to strict JSON schema recursively."""
        schema = pydantic_to_json_schema(NestedResponse)

        assert schema["type"] == "object"
        assert "user" in schema["properties"]
        assert "active" in schema["properties"]
        assert schema["required"] == ["user", "active"]
        assert schema["additionalProperties"] is False

        # Check nested user object is also strict
        user_schema = schema["properties"]["user"]
        assert user_schema["additionalProperties"] is False


class TestFakeLLMProvider:
    """Tests for deterministic fake LLM provider."""

    @pytest.fixture
    def provider(self) -> FakeLLMProvider:
        """Create a fresh fake provider for each test."""
        return FakeLLMProvider()

    async def test_happy_path(self, provider: FakeLLMProvider) -> None:
        """Fake provider returns configured response successfully."""
        provider.set_response("SimpleResponse", '{"name": "Alice", "age": 30}')

        messages = [{"role": "user", "content": "Get user info"}]
        result = await provider.complete_structured(messages, SimpleResponse)

        assert result.content.name == "Alice"
        assert result.content.age == 30
        assert result.metadata.model_name == "fake-model-1"
        assert result.metadata.total_tokens == 30

    async def test_lookup_by_schema_name(self, provider: FakeLLMProvider) -> None:
        """Provider looks up response by schema name."""
        provider.set_response("SimpleResponse", '{"name": "Bob", "age": 25}')

        messages = [{"role": "user", "content": "Anything"}]
        result = await provider.complete_structured(messages, SimpleResponse)

        assert result.content.name == "Bob"

    async def test_lookup_by_message_content(self, provider: FakeLLMProvider) -> None:
        """Provider looks up response by message content if schema match fails."""
        provider.set_response("Get user info", '{"name": "Charlie", "age": 35}')

        messages = [{"role": "user", "content": "Get user info"}]
        result = await provider.complete_structured(messages, SimpleResponse)

        assert result.content.name == "Charlie"

    async def test_no_response_configured(self, provider: FakeLLMProvider) -> None:
        """Provider raises error if no response configured."""
        messages = [{"role": "user", "content": "Unknown"}]

        with pytest.raises(LLMProviderError, match="No fake response configured"):
            await provider.complete_structured(messages, SimpleResponse)

    async def test_malformed_response_fails_closed(self, provider: FakeLLMProvider) -> None:
        """Malformed response raises LLMValidationError (fail-closed)."""
        provider.set_response("SimpleResponse", '{"name": "Invalid", "age": "not-a-number"}')

        messages = [{"role": "user", "content": "Test"}]

        with pytest.raises(LLMValidationError, match="failed schema validation"):
            await provider.complete_structured(messages, SimpleResponse)

    async def test_timeout_error(self, provider: FakeLLMProvider) -> None:
        """Provider can simulate timeout."""
        provider.set_timeout("SimpleResponse")

        messages = [{"role": "user", "content": "Test"}]

        with pytest.raises(LLMTimeoutError, match="Fake timeout"):
            await provider.complete_structured(messages, SimpleResponse)

    async def test_validation_error(self, provider: FakeLLMProvider) -> None:
        """Provider can simulate validation error."""
        provider.set_validation_error("SimpleResponse", "Custom validation failure")

        messages = [{"role": "user", "content": "Test"}]

        with pytest.raises(LLMValidationError, match="Custom validation failure"):
            await provider.complete_structured(messages, SimpleResponse)

    async def test_call_count_tracking(self, provider: FakeLLMProvider) -> None:
        """Provider tracks call counts per key."""
        provider.set_response("SimpleResponse", '{"name": "Test", "age": 1}')

        messages = [{"role": "user", "content": "Test"}]

        assert provider.get_call_count("SimpleResponse") == 0

        await provider.complete_structured(messages, SimpleResponse)
        assert provider.get_call_count("SimpleResponse") == 1

        await provider.complete_structured(messages, SimpleResponse)
        assert provider.get_call_count("SimpleResponse") == 2

    async def test_reset_clears_state(self, provider: FakeLLMProvider) -> None:
        """Reset clears responses, errors, and call counts."""
        provider.set_response("SimpleResponse", '{"name": "Test", "age": 1}')
        provider.set_error("OtherSchema", LLMProviderError("Test"))

        messages = [{"role": "user", "content": "Test"}]
        await provider.complete_structured(messages, SimpleResponse)

        assert provider.get_call_count("SimpleResponse") == 1

        provider.reset()

        assert provider.get_call_count("SimpleResponse") == 0
        with pytest.raises(LLMProviderError, match="No fake response configured"):
            await provider.complete_structured(messages, SimpleResponse)

    async def test_metadata_present(self, provider: FakeLLMProvider) -> None:
        """Metadata fields are populated correctly."""
        provider.set_response("SimpleResponse", '{"name": "Test", "age": 1}')

        messages = [{"role": "user", "content": "Test"}]
        result = await provider.complete_structured(
            messages,
            SimpleResponse,
            model="custom-model",
            prompt_version="v1.2.3",
        )

        assert result.metadata.model_name == "custom-model"
        assert result.metadata.prompt_version == "v1.2.3"
        assert result.metadata.prompt_tokens == 10
        assert result.metadata.completion_tokens == 20
        assert result.metadata.total_tokens == 30
        assert result.metadata.cost_usd == Decimal("0.001")


class TestOpenAIProviderConfiguration:
    """Tests for OpenAI provider configuration (no network calls)."""

    def test_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Provider raises error if API key not provided."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(LLMProviderError, match="OPENAI_API_KEY"):
            OpenAIProvider()

    def test_reads_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Provider reads API key from environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-env-key")

        provider = OpenAIProvider()
        assert provider._api_key == "test-env-key"  # pyright: ignore[reportPrivateUsage]

    def test_api_key_parameter_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API key parameter overrides environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")

        provider = OpenAIProvider(api_key="param-key")
        assert provider._api_key == "param-key"  # pyright: ignore[reportPrivateUsage]

    def test_default_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Provider uses default OpenAI base URL."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        provider = OpenAIProvider()
        assert provider._base_url == "https://api.openai.com/v1"  # pyright: ignore[reportPrivateUsage]

    def test_base_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Provider reads base URL from environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://custom.api.com/v1")

        provider = OpenAIProvider()
        assert provider._base_url == "https://custom.api.com/v1"  # pyright: ignore[reportPrivateUsage]

    def test_base_url_parameter_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Base URL parameter overrides environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://env.api.com/v1")

        provider = OpenAIProvider(base_url="https://param.api.com/v1")
        assert provider._base_url == "https://param.api.com/v1"  # pyright: ignore[reportPrivateUsage]

    def test_default_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Provider uses default model."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        provider = OpenAIProvider()
        assert provider._default_model == "gpt-4o"  # pyright: ignore[reportPrivateUsage]


class TestOpenAIProviderBehavioral:
    """Behavioral tests for OpenAIProvider with mocked HTTP transport."""

    @pytest.fixture
    def provider(self, monkeypatch: pytest.MonkeyPatch) -> OpenAIProvider:
        """Create provider with test API key."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
        return OpenAIProvider()

    async def test_happy_path_returns_validated_response(self, provider: OpenAIProvider) -> None:
        """Mocked 200 JSON matching schema returns validated result with metadata."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"name": "Alice", "age": 30}'}}],
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 25,
                "total_tokens": 40,
            },
        }

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            messages = [{"role": "user", "content": "Get user info"}]
            result = await provider.complete_structured(
                messages, SimpleResponse, prompt_version="v1.0"
            )

        assert result.content.name == "Alice"
        assert result.content.age == 30
        assert result.metadata.model_name == "gpt-4o"
        assert result.metadata.prompt_version == "v1.0"
        assert result.metadata.prompt_tokens == 15
        assert result.metadata.completion_tokens == 25
        assert result.metadata.total_tokens == 40
        assert result.metadata.cost_usd is None

    async def test_timeout_after_retry_budget_exhausted(self, provider: OpenAIProvider) -> None:
        """Mocked transport timeout raises LLMTimeoutError after retry budget."""
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.TimeoutException("Request timeout")

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            messages = [{"role": "user", "content": "Test"}]
            with pytest.raises(
                LLMTimeoutError,
                match=r"Request timed out after .* \(attempt 4/4\)",
            ):
                await provider.complete_structured(
                    messages, SimpleResponse, timeout=1.0, max_retries=3
                )

        # Should have tried 4 times total (initial + 3 retries)
        assert mock_client.post.call_count == 4

    async def test_transport_retry_succeeds_on_second_attempt(
        self, provider: OpenAIProvider
    ) -> None:
        """First call transport failure, second succeeds — proves retry on transport."""
        mock_response_success = MagicMock(spec=httpx.Response)
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "choices": [{"message": {"content": '{"name": "Bob", "age": 25}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        # First call fails with transport error, second succeeds
        mock_client.post.side_effect = [
            httpx.RequestError("Connection failed"),
            mock_response_success,
        ]

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            messages = [{"role": "user", "content": "Test"}]
            result = await provider.complete_structured(messages, SimpleResponse, max_retries=3)

        assert result.content.name == "Bob"
        assert result.content.age == 25
        # Should have called twice (first failed, second succeeded)
        assert mock_client.post.call_count == 2

    async def test_malformed_api_response_raises_provider_error(
        self, provider: OpenAIProvider
    ) -> None:
        """Bad API envelope (KeyError) wrapped as LLMProviderError."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"bad": "structure"}  # Missing 'choices'

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            messages = [{"role": "user", "content": "Test"}]
            with pytest.raises(LLMProviderError, match="Unexpected API response structure"):
                await provider.complete_structured(messages, SimpleResponse)

    async def test_validation_error_fails_immediately_no_retry(
        self, provider: OpenAIProvider
    ) -> None:
        """Validation failure fail-closes immediately (no retry)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"name": "Invalid", "age": "not-int"}'}}],
            "usage": {},
        }

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            messages = [{"role": "user", "content": "Test"}]
            with pytest.raises(LLMValidationError, match="failed schema validation"):
                await provider.complete_structured(messages, SimpleResponse, max_retries=3)

        # Should only call once (no retry on validation error)
        assert mock_client.post.call_count == 1
