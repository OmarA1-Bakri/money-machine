"""Versioned, hashed, loadable prompt store with integrity verification.

The prompt store loads agent prompts from `prompts/agents/<agent-id>/<version>.md`,
verifies SHA-256 hashes against the `prompt_versions` table, validates required
sections, and rejects prompts containing embedded secrets.

Required prompt sections:
- ## Purpose
- ## Input Contract
- ## Output Contract
- ## Instructions
- ## Tool Permissions

Contract: D-0026, Session 04 prompt-integrity addendum point 7.
"""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from typing import Final

from money_machine.domain.errors import ContractError


class PromptIntegrityError(ContractError):
    """Raised when a prompt's SHA-256 hash does not match the stored hash."""


class PromptValidationError(ContractError):
    """Raised when a prompt is missing required sections."""


class PromptSecretError(ContractError):
    """Raised when a prompt contains embedded secrets."""


# Required sections that every agent prompt must contain
REQUIRED_SECTIONS: Final[list[str]] = [
    "## Purpose",
    "## Input Contract",
    "## Output Contract",
    "## Instructions",
    "## Tool Permissions",
]

# Pattern matching runtime secrets that must not appear in prompts
SECRET_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:api[_-]?key|token|password|secret|credential)",
    re.IGNORECASE,
)


class PromptStore:
    """Load and verify agent prompts with hash integrity checks."""

    def __init__(self, repository_root: Path) -> None:
        """Initialize the prompt store.

        Args:
            repository_root: Path to the repository root containing `prompts/agents/`.
        """
        self._prompts_dir = repository_root / "prompts" / "agents"

    def load(
        self,
        agent_id: str,
        version: str,
        expected_hash: str | None = None,
    ) -> str:
        """Load an agent prompt and verify its integrity.

        Args:
            agent_id: The agent identifier (e.g., "A01", "A02").
            version: The prompt version (e.g., "v1").
            expected_hash: Optional SHA-256 hash to verify against.
                          If None, verification is skipped (use in tests only).

        Returns:
            The prompt content as a string.

        Raises:
            FileNotFoundError: If the prompt file does not exist.
            PromptIntegrityError: If the SHA-256 hash does not match expected_hash.
            PromptValidationError: If required sections are missing.
            PromptSecretError: If the prompt contains embedded secrets.
        """
        # Construct path: prompts/agents/<agent-id>/<version>.md
        prompt_path = self._prompts_dir / agent_id / f"{version}.md"

        if not prompt_path.is_file():
            msg = f"Prompt not found: {prompt_path}"
            raise FileNotFoundError(msg)

        # Read the prompt content
        content = prompt_path.read_text(encoding="utf-8")

        # Verify hash if expected_hash is provided
        if expected_hash is not None:
            actual_hash = sha256(content.encode("utf-8")).hexdigest()
            if actual_hash != expected_hash:
                msg = (
                    f"Prompt hash mismatch for {agent_id}/{version}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )
                raise PromptIntegrityError(msg)

        # Validate required sections
        self._validate_sections(content, agent_id, version)

        # Check for embedded secrets
        self._check_secrets(content, agent_id, version)

        return content

    def _validate_sections(self, content: str, agent_id: str, version: str) -> None:
        """Validate that all required sections are present.

        Args:
            content: The prompt content.
            agent_id: The agent identifier.
            version: The prompt version.

        Raises:
            PromptValidationError: If any required section is missing.
        """
        missing_sections = [
            section for section in REQUIRED_SECTIONS if section not in content
        ]

        if missing_sections:
            msg = (
                f"Prompt {agent_id}/{version} is missing required sections: "
                f"{', '.join(missing_sections)}"
            )
            raise PromptValidationError(msg)

    def _check_secrets(self, content: str, agent_id: str, version: str) -> None:
        """Check for embedded secrets in the prompt.

        Args:
            content: The prompt content.
            agent_id: The agent identifier.
            version: The prompt version.

        Raises:
            PromptSecretError: If the prompt contains patterns matching secrets.
        """
        if SECRET_PATTERN.search(content):
            msg = (
                f"Prompt {agent_id}/{version} contains forbidden secret patterns. "
                f"Secrets must not be embedded in prompts."
            )
            raise PromptSecretError(msg)
