"""Bounded review subagent coordination for owning agent runs.

An owning job may request internal specialist reviews that produce artifacts only.
Reviews never spawn jobs, never claim work, and fail closed on provider mutations.

Contract: Session 04 W6 — subagent review support lane (S04-09).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final
from uuid import UUID

from money_machine.agents.base import AgentDefinition, AgentRuntimeError
from money_machine.agents.contracts.review_subagent import ReviewSubagentResult
from money_machine.agents.tool_registry import (
    ToolNotFoundError,
    ToolPermissionError,
    ToolRegistry,
)
from money_machine.integrations.llm.interface import LLMProvider

DEFAULT_MAX_REVIEWS_PER_JOB: Final = 3
DEFAULT_MAX_TOKENS_PER_REVIEW: Final = 4096


def _empty_review_artifacts() -> list[ReviewSubagentArtifact]:
    return []


class ReviewSubagentError(AgentRuntimeError):
    """Base exception for bounded review subagent failures."""


class ReviewSubagentMutationError(ReviewSubagentError):
    """Raised when a review subagent attempts a disallowed side effect."""


class ReviewSubagentBudgetError(ReviewSubagentError):
    """Raised when review subagent bounds are exceeded."""


@dataclass(frozen=True, slots=True)
class ReviewSubagentBounds:
    """Per-job limits for review subagent invocations."""

    max_reviews_per_job: int = DEFAULT_MAX_REVIEWS_PER_JOB
    max_tokens_per_review: int = DEFAULT_MAX_TOKENS_PER_REVIEW

    @classmethod
    def from_definition(cls, definition: AgentDefinition) -> ReviewSubagentBounds:
        """Derive conservative defaults from one agent definition."""
        per_review_timeout = max(1, definition.timeout_seconds // DEFAULT_MAX_REVIEWS_PER_JOB)
        token_budget = min(DEFAULT_MAX_TOKENS_PER_REVIEW, per_review_timeout * 32)
        return cls(max_tokens_per_review=token_budget)


@dataclass(frozen=True, slots=True)
class ReviewSubagentRequest:
    """Input for one bounded review subagent invocation."""

    specialist_role: str
    subject_summary: str
    review_prompt: str


@dataclass(frozen=True, slots=True)
class ReviewSubagentArtifact:
    """One review artifact attached to the owning agent run."""

    review_number: int
    specialist_role: str
    result: ReviewSubagentResult
    model: str | None
    token_count: int | None


@dataclass
class ReviewSubagentCoordinator:
    """Coordinate bounded review subagents for one owning agent run."""

    job_id: UUID
    owning_run_id: UUID
    agent_id: str
    allowed_tools: frozenset[str]
    provider: LLMProvider
    tool_registry: ToolRegistry
    bounds: ReviewSubagentBounds = field(default_factory=ReviewSubagentBounds)
    _review_count: int = field(default=0, init=False)
    artifacts: list[ReviewSubagentArtifact] = field(
        default_factory=_empty_review_artifacts,
        init=False,
    )

    async def request_review(self, request: ReviewSubagentRequest) -> ReviewSubagentArtifact:
        """Invoke one bounded review subagent and record its artifact."""
        if self._review_count >= self.bounds.max_reviews_per_job:
            msg = (
                f"review budget exhausted for job {self.job_id}: "
                f"max {self.bounds.max_reviews_per_job} reviews per job"
            )
            raise ReviewSubagentBudgetError(msg)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a bounded internal review specialist. "
                    "Return structured findings and a verdict only. "
                    "Do not mutate external providers."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Specialist role: {request.specialist_role}\n"
                    f"Subject: {request.subject_summary}\n"
                    f"Review focus:\n{request.review_prompt}"
                ),
            },
        ]
        response = await self.provider.complete_structured(
            messages,
            ReviewSubagentResult,
            prompt_version=f"review:{request.specialist_role}",
        )
        token_count = response.metadata.total_tokens
        if token_count is not None and token_count > self.bounds.max_tokens_per_review:
            msg = (
                f"review token budget exceeded for job {self.job_id}: "
                f"{token_count} > {self.bounds.max_tokens_per_review}"
            )
            raise ReviewSubagentBudgetError(msg)

        self._review_count += 1
        artifact = ReviewSubagentArtifact(
            review_number=self._review_count,
            specialist_role=request.specialist_role,
            result=response.content,
            model=response.metadata.model_name,
            token_count=token_count,
        )
        self.artifacts.append(artifact)
        return artifact

    def invoke_review_tool(self, tool_id: str, **kwargs: Any) -> Mapping[str, Any]:
        """Invoke one read-only tool during a review subagent."""
        try:
            return self.tool_registry.invoke_for_review(
                tool_id,
                allowed_tools=self.allowed_tools,
                agent_id=self.agent_id,
                **kwargs,
            )
        except ToolPermissionError as error:
            raise ReviewSubagentMutationError(str(error)) from error
        except ToolNotFoundError as error:
            raise ReviewSubagentMutationError(str(error)) from error

    @property
    def review_count(self) -> int:
        """Number of review subagents invoked for this owning run."""
        return self._review_count
