"""A07 local deterministic product builder implementation."""

from dataclasses import dataclass
from pathlib import Path

from money_machine.domain.models.product import BuildResult
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.interface import ProductBundleBuilder


@dataclass(frozen=True, slots=True)
class LocalNotionProductBuilderAgent:
    """Delegate the A07 boundary to the configured local bundle builder."""

    builder: ProductBundleBuilder

    def run(self, spec: ProductSpec, destination: Path) -> BuildResult:
        """Build one deterministic local product."""

        return self.builder.build(spec, destination)
