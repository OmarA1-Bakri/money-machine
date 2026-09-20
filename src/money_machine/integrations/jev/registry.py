"""Jev decision registry loader.

Loads decision definitions from YAML config files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from money_machine.integrations.jev.models import (
    ChoiceQuestion,
    NoulQuestion,
    Question,
    ScoreQuestion,
)


class DecisionDefinition(BaseModel):
    """A decision definition from the registry."""

    model_config = ConfigDict(frozen=True, strict=True)

    name: str = Field(description="Decision type identifier (snake_case)")
    description: str = Field(description="Human-readable description")
    questions: list[Question] = Field(description="Questions for this decision", min_length=1)
    auto_gates: dict[str, Any] = Field(
        description="Auto gate configuration (threshold_question, threshold_value, below_threshold_action)"
    )
    authority_tier: str = Field(
        description="Authority tier (automated/operator_required/safety_gate/shadow_only)"
    )


class DecisionRegistry:
    """Registry of Jev decision definitions loaded from YAML config."""

    def __init__(self, config_dir: Path | None = None):
        """Initialize decision registry.

        Args:
            config_dir: Path to jev_decisions config directory
                (defaults to repo config/jev_decisions)
        """
        if config_dir is None:
            # Default to repo config/jev_decisions
            # Walk up from this file to find the repo root
            current = Path(__file__).resolve()
            repo_root = current.parent.parent.parent.parent.parent
            config_dir = repo_root / "config" / "jev_decisions"

        self._config_dir = config_dir
        self._decisions: dict[str, DecisionDefinition] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all decision YAML files from config directory."""
        if not self._config_dir.exists():
            raise FileNotFoundError(f"Jev decisions config directory not found: {self._config_dir}")

        yaml_files = list(self._config_dir.glob("*.yaml")) + list(self._config_dir.glob("*.yml"))
        if not yaml_files:
            raise ValueError(f"No YAML files found in {self._config_dir}")

        for yaml_file in yaml_files:
            self._load_file(yaml_file)

    def _load_file(self, yaml_file: Path) -> None:
        """Load decisions from a single YAML file."""
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load {yaml_file}: {e}") from e

        if not isinstance(data, dict) or "decisions" not in data:
            raise ValueError(f"{yaml_file} must contain 'decisions' key")

        for decision_data in data["decisions"]:
            try:
                # Parse questions
                questions = []
                for q in decision_data["questions"]:
                    q_type = q["question_type"]
                    if q_type == "noul":
                        questions.append(NoulQuestion(**q))
                    elif q_type == "choice":
                        questions.append(ChoiceQuestion(**q))
                    elif q_type == "score":
                        questions.append(ScoreQuestion(**q))
                    else:
                        raise ValueError(f"Unknown question_type: {q_type}")

                # Build DecisionDefinition
                decision = DecisionDefinition(
                    name=decision_data["name"],
                    description=decision_data["description"],
                    questions=questions,
                    auto_gates=decision_data["auto_gates"],
                    authority_tier=decision_data["authority_tier"],
                )

                if decision.name in self._decisions:
                    raise ValueError(f"Duplicate decision name: {decision.name}")

                self._decisions[decision.name] = decision

            except (KeyError, ValidationError) as e:
                raise ValueError(f"Invalid decision in {yaml_file}: {e}") from e

    def get(self, decision_type: str) -> DecisionDefinition:
        """Get a decision definition by name.

        Args:
            decision_type: Decision type identifier

        Returns:
            DecisionDefinition for this type

        Raises:
            KeyError: If decision type not found
        """
        if decision_type not in self._decisions:
            raise KeyError(f"Decision type not found: {decision_type}")
        return self._decisions[decision_type]

    def list_all(self) -> list[str]:
        """List all registered decision types.

        Returns:
            Sorted list of decision type names
        """
        return sorted(self._decisions.keys())

    def __len__(self) -> int:
        """Get number of registered decisions."""
        return len(self._decisions)
