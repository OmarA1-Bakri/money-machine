"""Jev decision engine data models.

Typed questions (Noul/Choice/Score), packets, and results for the Jev Gateway evaluate API.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NoulQuestion(BaseModel):
    """Binary Noul question (YES/NO).

    Fan-out narrow Nouls; avoid mega-Choice questions.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    question_id: str = Field(description="Unique identifier for this question")
    prompt: str = Field(description="Question text for Jev to evaluate")
    question_type: Literal["noul"] = "noul"


class ChoiceQuestion(BaseModel):
    """Multiple-choice question with enumerated options.

    Prefer narrow Nouls over mega-Choice where possible.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    question_id: str = Field(description="Unique identifier for this question")
    prompt: str = Field(description="Question text for Jev to evaluate")
    question_type: Literal["choice"] = "choice"
    choices: list[str] = Field(description="Available choices", min_length=2)


class ScoreLevel(BaseModel):
    """One concrete level in a Score question."""

    model_config = ConfigDict(frozen=True, strict=True)

    level: str = Field(description="Level identifier (e.g. 'low', 'medium', 'high')")
    description: str = Field(description="Concrete situation that matches this level")


class ScoreQuestion(BaseModel):
    """Score question with concrete, descriptive levels.

    Levels must describe concrete situations, not vague intensities.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    question_id: str = Field(description="Unique identifier for this question")
    prompt: str = Field(description="Question text for Jev to evaluate")
    question_type: Literal["score"] = "score"
    levels: list[ScoreLevel] = Field(description="Concrete score levels", min_length=2)


# Union of all question types
Question = NoulQuestion | ChoiceQuestion | ScoreQuestion


class DecisionPacket(BaseModel):
    """Input packet for a Jev decision evaluation.

    Contains the decision context and all questions to evaluate.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    decision_type: str = Field(description="Decision type identifier (from registry)")
    context: dict[str, Any] = Field(description="Decision context (job/workflow/etc)")
    questions: list[Question] = Field(description="Questions to evaluate", min_length=1)


class DecisionResult(BaseModel):
    """Result from a Jev decision evaluation.

    Contains answers for all questions plus metadata.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    decision_type: str = Field(description="Decision type identifier")
    answers: dict[str, str | bool | int] = Field(
        description="Answers keyed by question_id (YES/NO for Noul, choice string, or level index)"
    )
    model_id: str = Field(description="Jev model identifier used for this evaluation")
    latency_ms: int = Field(description="Evaluation latency in milliseconds", ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
