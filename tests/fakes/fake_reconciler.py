"""Deterministic fake reconciler for testing.

Moved from orchestration library per should-fix B-5.
Session 04 replaces this with real provider adapters.
"""

from __future__ import annotations

from money_machine.orchestration.reconciliation import EffectState


class FakeReconciler:
    """Deterministic fake reconciler for testing.

    This stub always returns a configurable result without querying any real provider.
    Session 04 replaces this with real provider adapters.
    """

    def __init__(
        self,
        *,
        effect_state: EffectState = EffectState.CONFIRMED,
        provider_object_id: str | None = None,
    ) -> None:
        """Initialize the fake reconciler.

        Args:
            effect_state: The state to return (default CONFIRMED)
            provider_object_id: The object ID to return (default None)
        """
        self.effect_state = effect_state
        self.provider_object_id = provider_object_id

    async def query_effect_state(
        self,
        *,
        idempotency_key: str,
        operation: str,
    ) -> tuple[EffectState, str | None]:
        """Return the configured fake result."""
        return self.effect_state, self.provider_object_id
