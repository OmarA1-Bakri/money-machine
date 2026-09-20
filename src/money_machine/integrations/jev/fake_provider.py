"""Deterministic fake Jev provider for testing.

Provides fixed decision answers keyed by decision type or question ID, with no network calls.
"""

from __future__ import annotations

from money_machine.integrations.jev.client import JevClient, JevClientError, JevTimeoutError
from money_machine.integrations.jev.models import DecisionPacket, DecisionResult


class FakeJevProvider(JevClient):
    """Deterministic fake Jev provider for testing.

    Returns fixed answers based on configuration. Useful for:
    - Unit testing without network calls
    - Deterministic test scenarios
    - Simulating various response conditions (success, timeout, errors)

    Example:
        provider = FakeJevProvider()
        provider.set_answers(
            "preflight_blockers_present",
            {"has_blockers": False, "blocker_count": 0}
        )
        result = await provider.evaluate(packet)
    """

    def __init__(
        self,
        default_model_id: str = "fake-jev-1",
        default_latency_ms: int = 100,
    ):
        """Initialize fake provider with defaults.

        Args:
            default_model_id: Default model identifier for metadata
            default_latency_ms: Default latency in milliseconds
        """
        self._default_model_id = default_model_id
        self._default_latency_ms = default_latency_ms
        self._answers: dict[str, dict[str, str | bool | int]] = {}
        self._errors: dict[str, Exception] = {}
        self._call_count: dict[str, int] = {}

    def set_answers(self, decision_type: str, answers: dict[str, str | bool | int]) -> None:
        """Configure fixed answers for a decision type.

        Args:
            decision_type: Decision type identifier
            answers: Dict of answers keyed by question_id
        """
        self._answers[decision_type] = answers

    def set_error(self, decision_type: str, error: Exception) -> None:
        """Configure an error to raise for a decision type.

        Args:
            decision_type: Decision type identifier
            error: Exception to raise (JevTimeoutError, JevClientError, etc.)
        """
        self._errors[decision_type] = error

    def set_timeout(self, decision_type: str) -> None:
        """Configure a timeout error for a decision type.

        Args:
            decision_type: Decision type identifier
        """
        self.set_error(decision_type, JevTimeoutError(f"Fake timeout for: {decision_type}"))

    def get_call_count(self, decision_type: str) -> int:
        """Get the number of times a decision type was evaluated.

        Args:
            decision_type: Decision type identifier

        Returns:
            Number of evaluate calls for this decision type
        """
        return self._call_count.get(decision_type, 0)

    def reset(self) -> None:
        """Clear all configured answers, errors, and call counts."""
        self._answers.clear()
        self._errors.clear()
        self._call_count.clear()

    async def evaluate(
        self,
        packet: DecisionPacket,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> DecisionResult:
        """Return a configured fake decision result.

        Looks up answers by decision_type.
        Raises configured error if set.
        Raises JevClientError if no answers configured.

        See JevClient.evaluate for full documentation.
        """
        decision_type = packet.decision_type

        # Track call count
        self._call_count[decision_type] = self._call_count.get(decision_type, 0) + 1

        # Check for configured error
        if decision_type in self._errors:
            raise self._errors[decision_type]

        # Get configured answers
        if decision_type not in self._answers:
            raise JevClientError(f"No fake answers configured for decision type: {decision_type}")

        answers = self._answers[decision_type]

        # Validate that answers match the questions
        question_ids = {q.question_id for q in packet.questions}
        answer_keys = set(answers.keys())
        if question_ids != answer_keys:
            raise JevClientError(
                f"Answer keys mismatch for {decision_type}. "
                f"Expected {question_ids}, got {answer_keys}"
            )

        return DecisionResult(
            decision_type=decision_type,
            answers=answers,
            model_id=self._default_model_id,
            latency_ms=self._default_latency_ms,
        )
