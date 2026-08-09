"""A07 deterministic product builder contract."""

from pathlib import Path
from typing import Protocol

from money_machine.domain.models.product import BuildResult
from money_machine.domain.models.product_spec import ProductSpec


class NotionProductBuilderAgent(Protocol):
    """Agent boundary for a validated specification build."""

    def run(self, spec: ProductSpec, destination: Path) -> BuildResult:
        """Build one local product bundle."""
        ...
