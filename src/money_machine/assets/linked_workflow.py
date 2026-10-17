"""Run the fixture workflow and stop at preflight.

The chain calls the fixture provider adapters, then the synthetic path
through preflight. Publish, purchase, and checkout raise. A true flag
does not authorize them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from money_machine.assets.synthetic_paths import receipts_through_preflight
from money_machine.integrations.provider_connections import select_provider_connections

_ACTIONS = frozenset({"publish", "purchase", "checkout"})
WorkflowAction = Literal["publish", "purchase", "checkout"]


class LinkedWorkflowRefusal(ValueError):
    """The workflow was asked to publish, purchase, or check out."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class LinkedWorkflow:
    """A fixture chain that stopped at preflight. Nothing was published or spent."""

    stopped_at: str
    provider: str
    listing_count: int
    notion_connected: bool
    preflight_passed: bool
    published: bool
    purchased: bool
    checkout: bool


def run_linked_workflow() -> LinkedWorkflow:
    """Select the fixture adapters and stop when preflight passes."""
    selected = select_provider_connections()
    receipts = receipts_through_preflight()
    if (
        not receipts
        or receipts[-1].step != "preflight"
        or any(
            item.step in {"publish", "publish_simulation", "purchase", "checkout"}
            for item in receipts
        )
    ):
        raise LinkedWorkflowRefusal("preflight")
    return LinkedWorkflow(
        stopped_at="preflight",
        provider=selected.etsy,
        listing_count=selected.listing_count,
        notion_connected=selected.notion_connected,
        preflight_passed=True,
        published=False,
        purchased=False,
        checkout=False,
    )


def advance_linked_workflow(action: WorkflowAction, *, enabled: bool) -> None:
    """Refuse the action. A true flag does not publish, purchase, or check out."""
    del enabled
    if action not in _ACTIONS:
        raise LinkedWorkflowRefusal("action")
    raise LinkedWorkflowRefusal(action)
