"""Structured output validation with fail-closed behavior.

Validates LLM responses against Pydantic models and fails closed on malformed output.
"""

from __future__ import annotations

import json
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from money_machine.integrations.llm.interface import LLMValidationError


def validate_structured_output[T: BaseModel](raw_response: str, response_model: type[T]) -> T:
    """Validate and parse a raw LLM response against a Pydantic model (fail-closed).

    Args:
        raw_response: Raw JSON string from the LLM
        response_model: Pydantic model defining the expected schema

    Returns:
        Parsed and validated instance of response_model

    Raises:
        LLMValidationError: If the response fails parsing or validation (fail-closed)
    """
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError as error:
        raise LLMValidationError(f"Failed to parse LLM response as JSON: {error!s}") from error

    try:
        return response_model.model_validate(data)
    except ValidationError as error:
        raise LLMValidationError(f"LLM response failed schema validation: {error!s}") from error


def pydantic_to_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model to an OpenAI-compatible JSON schema.

    Args:
        model: Pydantic model to convert

    Returns:
        JSON schema dict with strict=true semantics (all required, no additionalProperties)
    """
    schema = model.model_json_schema()

    # Resolve $defs if present and inline them
    defs = schema.pop("$defs", {})

    def resolve_refs(obj: dict[str, Any], definitions: dict[str, Any]) -> dict[str, Any]:
        """Resolve $ref references by inlining definitions."""
        if "$ref" in obj:
            ref_path = obj["$ref"]
            if isinstance(ref_path, str) and ref_path.startswith("#/$defs/"):
                def_name = ref_path.split("/")[-1]
                if def_name in definitions:
                    # Inline the definition
                    resolved = cast(dict[str, Any], definitions[def_name])
                    return resolve_refs(dict(resolved), definitions)

        # Recursively resolve in nested structures
        for key, value in list(obj.items()):
            if isinstance(value, dict):
                obj[key] = resolve_refs(cast(dict[str, Any], value), definitions)
            elif isinstance(value, list):
                obj[key] = [
                    resolve_refs(cast(dict[str, Any], item), definitions)
                    if isinstance(item, dict)
                    else item
                    for item in cast(list[Any], value)
                ]
        return obj

    schema = resolve_refs(schema, defs)

    # Ensure strict schema semantics for OpenAI structured outputs
    def make_strict(obj: dict[str, Any]) -> dict[str, Any]:
        """Recursively enforce strict schema requirements."""
        if obj.get("type") == "object":
            # All fields must be required
            if "properties" in obj:
                properties = cast(dict[str, Any], obj["properties"])
                obj.setdefault("required", list(properties.keys()))
                # Disallow additional properties
                obj.setdefault("additionalProperties", False)
                # Make nested objects strict
                for prop_value in properties.values():
                    if isinstance(prop_value, dict):
                        make_strict(cast(dict[str, Any], prop_value))
        elif obj.get("type") == "array":
            items = obj.get("items")
            if isinstance(items, dict):
                # Make array items strict if they're objects
                make_strict(cast(dict[str, Any], items))
        return obj

    return make_strict(schema)
