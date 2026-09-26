"""Typed errors for the Notion schema and formula builders.

Session 06 prompt heading "### 5. Implement formula and schema builders".
These errors stay in-process. Nothing in this module opens a network connection.
"""

from __future__ import annotations


class SchemaBuilderError(ValueError):
    """Raised when a schema or formula builder rejects input."""


class UnverifiedPropertyNameError(SchemaBuilderError):
    """Raised when a formula references a property name that was not verified."""

    def __init__(self, property_name: str) -> None:
        self.property_name = property_name
        super().__init__(f"property name {property_name!r} is not verified")
