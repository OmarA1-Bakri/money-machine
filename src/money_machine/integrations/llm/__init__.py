"""LLM provider integration module.

Provides OpenAI-compatible LLM providers with structured JSON output support.
"""

from money_machine.integrations.llm.fake_provider import FakeLLMProvider
from money_machine.integrations.llm.interface import (
    LLMCallMetadata,
    LLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    LLMValidationError,
    StructuredLLMResponse,
)
from money_machine.integrations.llm.openai_provider import OpenAIProvider
from money_machine.integrations.llm.structured_output import (
    pydantic_to_json_schema,
    validate_structured_output,
)

__all__ = [
    "FakeLLMProvider",
    "LLMCallMetadata",
    "LLMProvider",
    "LLMProviderError",
    "LLMTimeoutError",
    "LLMValidationError",
    "OpenAIProvider",
    "StructuredLLMResponse",
    "pydantic_to_json_schema",
    "validate_structured_output",
]
