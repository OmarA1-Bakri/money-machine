"""Immutable exact-name handler dispatch."""

from collections.abc import Mapping
from types import MappingProxyType


class HandlerRegistry[HandlerT]:
    def __init__(self, handlers: Mapping[str, HandlerT]) -> None:
        if any(not name.strip() for name in handlers):
            raise ValueError("handler names must not be empty")
        self._handlers = MappingProxyType(dict(handlers))

    def resolve(self, job_type: str) -> HandlerT:
        try:
            return self._handlers[job_type]
        except KeyError as exc:
            raise KeyError(f"no handler registered for {job_type}") from exc
