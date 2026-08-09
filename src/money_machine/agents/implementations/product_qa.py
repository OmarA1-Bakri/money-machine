"""A09 deterministic local product QA implementation."""

from dataclasses import dataclass
from typing import Protocol

from money_machine.domain.models.product import BuildResult, ProductQAResult


class ProductEvaluator(Protocol):
    """Narrow evaluation dependency used by the A09 agent."""

    def evaluate(self, build: BuildResult) -> ProductQAResult:
        """Evaluate one product build."""
        ...


@dataclass(frozen=True, slots=True)
class DeterministicProductQAAgent:
    """Delegate the A09 boundary to deterministic local QA."""

    evaluator: ProductEvaluator

    def run(self, build: BuildResult) -> ProductQAResult:
        """Evaluate one local product bundle."""

        return self.evaluator.evaluate(build)
