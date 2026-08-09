"""A09 deterministic product QA contract."""

from typing import Protocol

from money_machine.domain.models.product import BuildResult, ProductQAResult


class ProductQAAgent(Protocol):
    """Agent boundary for local product quality assurance."""

    def run(self, build: BuildResult) -> ProductQAResult:
        """Evaluate one complete local product bundle."""
        ...
