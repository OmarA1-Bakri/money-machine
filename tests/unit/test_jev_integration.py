"""Unit tests for Jev integration client, models, and registry.

Tests JevClient interface, FakeJevProvider, DecisionRegistry, and real client behavior
with httpx mocking (mirrors W2 OpenAIProvider bar).
"""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import ValidationError

from money_machine.integrations.jev import (
    ChoiceQuestion,
    DecisionPacket,
    DecisionRegistry,
    DecisionResult,
    FakeJevProvider,
    JevClientError,
    JevGatewayClient,
    JevTimeoutError,
    NoulQuestion,
    ScoreLevel,
    ScoreQuestion,
)


class TestNoulQuestion:
    """Tests for Noul (binary YES/NO) questions."""

    def test_valid_noul_question(self) -> None:
        """Valid Noul question constructs successfully."""
        q = NoulQuestion(
            question_id="has_blockers",
            prompt="Are there any blocking conditions?",
        )
        assert q.question_id == "has_blockers"
        assert q.question_type == "noul"
        assert q.prompt == "Are there any blocking conditions?"

    def test_noul_question_frozen(self) -> None:
        """Noul questions are immutable."""
        q = NoulQuestion(
            question_id="test",
            prompt="Test",
        )
        with pytest.raises(ValidationError):
            q.question_id = "modified"  # pyright: ignore[reportAttributeAccessIssue]


class TestChoiceQuestion:
    """Tests for Choice (multiple-choice) questions."""

    def test_valid_choice_question(self) -> None:
        """Valid Choice question constructs successfully."""
        q = ChoiceQuestion(
            question_id="draft_reason",
            prompt="Why is this draft?",
            choices=["incomplete_assets", "qa_fail", "policy_hold"],
        )
        assert q.question_id == "draft_reason"
        assert q.question_type == "choice"
        assert len(q.choices) == 3

    def test_choice_requires_at_least_two_options(self) -> None:
        """Choice question requires at least 2 choices."""
        with pytest.raises(ValidationError):
            ChoiceQuestion(
                question_id="test",
                prompt="Test",
                choices=["only_one"],
            )


class TestScoreQuestion:
    """Tests for Score questions with concrete levels."""

    def test_valid_score_question(self) -> None:
        """Valid Score question constructs successfully."""
        levels = [
            ScoreLevel(level="low", description="Confidence below 60%"),
            ScoreLevel(level="high", description="Confidence above 85%"),
        ]
        q = ScoreQuestion(
            question_id="confidence_score",
            prompt="What is the confidence level?",
            levels=levels,
        )
        assert q.question_id == "confidence_score"
        assert q.question_type == "score"
        assert len(q.levels) == 2

    def test_score_requires_at_least_two_levels(self) -> None:
        """Score question requires at least 2 levels."""
        with pytest.raises(ValidationError):
            ScoreQuestion(
                question_id="test",
                prompt="Test",
                levels=[ScoreLevel(level="only_one", description="Test")],
            )


class TestDecisionPacket:
    """Tests for DecisionPacket input model."""

    def test_valid_packet(self) -> None:
        """Valid packet constructs successfully."""
        packet = DecisionPacket(
            decision_type="preflight_blockers_present",
            context={"workflow_id": "abc123"},
            questions=[
                NoulQuestion(question_id="has_blockers", prompt="Any blockers?"),
            ],
        )
        assert packet.decision_type == "preflight_blockers_present"
        assert len(packet.questions) == 1

    def test_packet_requires_at_least_one_question(self) -> None:
        """Packet requires at least one question."""
        with pytest.raises(ValidationError):
            DecisionPacket(
                decision_type="test",
                context={},
                questions=[],
            )


class TestDecisionResult:
    """Tests for DecisionResult output model."""

    def test_valid_result(self) -> None:
        """Valid result constructs successfully."""
        result = DecisionResult(
            decision_type="preflight_blockers_present",
            answers={"has_blockers": False},
            model_id="jev-1.0",
            latency_ms=150,
        )
        assert result.decision_type == "preflight_blockers_present"
        assert result.answers["has_blockers"] is False
        assert result.latency_ms == 150

    def test_result_latency_must_be_non_negative(self) -> None:
        """Result latency must be >= 0."""
        with pytest.raises(ValidationError):
            DecisionResult(
                decision_type="test",
                answers={},
                model_id="test",
                latency_ms=-1,
            )


class TestFakeJevProvider:
    """Tests for deterministic fake Jev provider."""

    @pytest.fixture
    def provider(self) -> FakeJevProvider:
        """Create a fresh fake provider for each test."""
        return FakeJevProvider()

    async def test_happy_path(self, provider: FakeJevProvider) -> None:
        """Fake provider returns configured answers successfully."""
        provider.set_answers("preflight_blockers_present", {"has_blockers": False})

        packet = DecisionPacket(
            decision_type="preflight_blockers_present",
            context={},
            questions=[
                NoulQuestion(question_id="has_blockers", prompt="Any blockers?"),
            ],
        )

        result = await provider.evaluate(packet)

        assert result.decision_type == "preflight_blockers_present"
        assert result.answers["has_blockers"] is False
        assert result.model_id == "fake-jev-1"
        assert result.latency_ms == 100

    async def test_no_answers_configured(self, provider: FakeJevProvider) -> None:
        """Provider raises error if no answers configured."""
        packet = DecisionPacket(
            decision_type="unknown_decision",
            context={},
            questions=[NoulQuestion(question_id="q1", prompt="Test")],
        )

        with pytest.raises(JevClientError, match="No fake answers configured"):
            await provider.evaluate(packet)

    async def test_answer_keys_mismatch(self, provider: FakeJevProvider) -> None:
        """Provider raises error if answer keys don't match questions."""
        provider.set_answers("test_decision", {"wrong_id": True})

        packet = DecisionPacket(
            decision_type="test_decision",
            context={},
            questions=[NoulQuestion(question_id="correct_id", prompt="Test")],
        )

        with pytest.raises(JevClientError, match="Answer keys mismatch"):
            await provider.evaluate(packet)

    async def test_timeout_error(self, provider: FakeJevProvider) -> None:
        """Provider can simulate timeout."""
        provider.set_timeout("test_decision")

        packet = DecisionPacket(
            decision_type="test_decision",
            context={},
            questions=[NoulQuestion(question_id="q1", prompt="Test")],
        )

        with pytest.raises(JevTimeoutError, match="Fake timeout"):
            await provider.evaluate(packet)

    async def test_call_count_tracking(self, provider: FakeJevProvider) -> None:
        """Provider tracks call counts per decision type."""
        provider.set_answers("test_decision", {"q1": True})

        packet = DecisionPacket(
            decision_type="test_decision",
            context={},
            questions=[NoulQuestion(question_id="q1", prompt="Test")],
        )

        assert provider.get_call_count("test_decision") == 0

        await provider.evaluate(packet)
        assert provider.get_call_count("test_decision") == 1

        await provider.evaluate(packet)
        assert provider.get_call_count("test_decision") == 2

    async def test_reset_clears_state(self, provider: FakeJevProvider) -> None:
        """Reset clears answers, errors, and call counts."""
        provider.set_answers("test_decision", {"q1": True})

        packet = DecisionPacket(
            decision_type="test_decision",
            context={},
            questions=[NoulQuestion(question_id="q1", prompt="Test")],
        )

        await provider.evaluate(packet)
        assert provider.get_call_count("test_decision") == 1

        provider.reset()

        assert provider.get_call_count("test_decision") == 0
        with pytest.raises(JevClientError, match="No fake answers configured"):
            await provider.evaluate(packet)


class TestDecisionRegistry:
    """Tests for DecisionRegistry YAML loader."""

    def test_loads_all_decision_types(self) -> None:
        """Registry loads all 12 decision types from config."""
        registry = DecisionRegistry()

        decision_types = registry.list_all()

        # Should have exactly 12 decision types
        assert len(decision_types) == 12

        # Check all expected types present
        expected = [
            "preflight_blockers_present",
            "shadow_mode_jev_only_log",
            "winner_confidence_gate",
            "operator_ask_omar_needed",
            "keep_as_draft",
            "retry_class_idempotent",
            "successor_spawn_count",
            "shop_mode_simulation_ok",
            "deep_pass_scope_narrow",
            "uncommissioned_block_live",
            "metrics_snapshot_stale_reject",
            "reconcile_absent_fail",
        ]

        for expected_type in expected:
            assert expected_type in decision_types, f"Missing: {expected_type}"

    def test_get_decision_definition(self) -> None:
        """Can retrieve a decision definition by name."""
        registry = DecisionRegistry()

        decision = registry.get("preflight_blockers_present")

        assert decision.name == "preflight_blockers_present"
        assert len(decision.questions) > 0
        assert "threshold_question" in decision.auto_gates
        assert decision.authority_tier in [
            "automated",
            "operator_required",
            "safety_gate",
            "shadow_only",
        ]

    def test_get_unknown_decision_raises_keyerror(self) -> None:
        """Getting unknown decision type raises KeyError."""
        registry = DecisionRegistry()

        with pytest.raises(KeyError, match="Decision type not found"):
            registry.get("unknown_decision_type")

    def test_decision_has_valid_questions(self) -> None:
        """Decision questions are properly typed."""
        registry = DecisionRegistry()

        decision = registry.get("winner_confidence_gate")

        # Should have at least one question
        assert len(decision.questions) > 0

        # All questions should be valid types
        for question in decision.questions:
            assert isinstance(question, (NoulQuestion, ChoiceQuestion, ScoreQuestion))

    def test_registry_length(self) -> None:
        """Registry reports correct length."""
        registry = DecisionRegistry()

        assert len(registry) == 12


class TestJevGatewayClient:
    """Tests for real JevGatewayClient with httpx mocking (mirrors W2 OpenAIProvider bar)."""

    @pytest.fixture
    def mock_gateway_url(self) -> str:
        """Mock Jev Gateway URL."""
        return "https://jev-gateway.test"

    @pytest.fixture
    def client(self, mock_gateway_url: str) -> JevGatewayClient:
        """Create a real client pointing at mock URL."""
        return JevGatewayClient(base_url=mock_gateway_url, api_key="test-key")

    @pytest.fixture
    def packet(self) -> DecisionPacket:
        """Sample decision packet."""
        return DecisionPacket(
            decision_type="preflight_blockers_present",
            context={"workflow_id": "test-123"},
            questions=[
                NoulQuestion(question_id="has_blockers", prompt="Any blockers?"),
            ],
        )

    @respx.mock
    async def test_happy_path_structured_response(
        self, client: JevGatewayClient, packet: DecisionPacket, mock_gateway_url: str
    ) -> None:
        """Happy path: client sends request and parses structured response."""
        mock_response = {
            "decision_type": "preflight_blockers_present",
            "answers": {"has_blockers": False},
            "model_id": "jev-production-1.2",
            "latency_ms": 250,
        }

        respx.post(f"{mock_gateway_url}/evaluate").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        result = await client.evaluate(packet, timeout=5.0)

        assert result.decision_type == "preflight_blockers_present"
        assert result.answers == {"has_blockers": False}
        assert result.model_id == "jev-production-1.2"
        assert result.latency_ms == 250

    @respx.mock
    async def test_timeout_behavior(
        self, client: JevGatewayClient, packet: DecisionPacket, mock_gateway_url: str
    ) -> None:
        """Client raises JevTimeoutError on timeout."""
        respx.post(f"{mock_gateway_url}/evaluate").mock(
            side_effect=httpx.TimeoutException("timeout")
        )

        with pytest.raises(JevTimeoutError, match="Jev Gateway timed out after"):
            await client.evaluate(packet, timeout=1.0)

    @respx.mock
    async def test_retry_on_transient_failure(
        self, client: JevGatewayClient, packet: DecisionPacket, mock_gateway_url: str
    ) -> None:
        """Client retries on transient transport failures."""
        mock_response = {
            "decision_type": "preflight_blockers_present",
            "answers": {"has_blockers": False},
            "model_id": "jev-1.0",
            "latency_ms": 100,
        }

        # First attempt: transport error, second attempt: success
        route = respx.post(f"{mock_gateway_url}/evaluate")
        route.side_effect = [
            httpx.RequestError("Connection refused"),
            httpx.Response(200, json=mock_response),
        ]

        result = await client.evaluate(packet, timeout=5.0)

        assert result.answers == {"has_blockers": False}
        assert len(route.calls) == 2  # Verify retry happened

    @respx.mock
    async def test_fail_closed_on_provider_down(
        self, client: JevGatewayClient, packet: DecisionPacket, mock_gateway_url: str
    ) -> None:
        """Client fails closed (raises error) when provider consistently returns 500."""
        respx.post(f"{mock_gateway_url}/evaluate").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        with pytest.raises(JevClientError, match="Jev Gateway returned 500"):
            await client.evaluate(packet, timeout=5.0)

    @respx.mock
    async def test_fail_closed_on_malformed_response(
        self, client: JevGatewayClient, packet: DecisionPacket, mock_gateway_url: str
    ) -> None:
        """Client fails closed on malformed JSON (no silent success)."""
        respx.post(f"{mock_gateway_url}/evaluate").mock(
            return_value=httpx.Response(200, json={"invalid": "response"})
        )

        with pytest.raises(JevClientError, match="Unexpected Jev Gateway response structure"):
            await client.evaluate(packet, timeout=5.0)

    @respx.mock
    async def test_fail_closed_on_missing_answer_keys(
        self, client: JevGatewayClient, packet: DecisionPacket, mock_gateway_url: str
    ) -> None:
        """Client fails closed when response is missing expected answer keys."""
        # Response missing "has_blockers" key
        mock_response = {
            "decision_type": "preflight_blockers_present",
            "answers": {},  # Empty answers - missing "has_blockers"
            "model_id": "jev-1.0",
            "latency_ms": 100,
        }

        respx.post(f"{mock_gateway_url}/evaluate").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        with pytest.raises(JevClientError, match="missing answer keys"):
            await client.evaluate(packet, timeout=5.0)

    @respx.mock
    async def test_fail_closed_on_extra_answer_keys(
        self, client: JevGatewayClient, packet: DecisionPacket, mock_gateway_url: str
    ) -> None:
        """Client fails closed when response has unexpected extra answer keys."""
        # Response has extra "unexpected_key"
        mock_response = {
            "decision_type": "preflight_blockers_present",
            "answers": {
                "has_blockers": False,
                "unexpected_key": True,  # Extra key not in questions
            },
            "model_id": "jev-1.0",
            "latency_ms": 100,
        }

        respx.post(f"{mock_gateway_url}/evaluate").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        with pytest.raises(JevClientError, match="unexpected answer keys"):
            await client.evaluate(packet, timeout=5.0)
