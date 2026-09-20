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


class PromptIntegrityError(ValueError):
    """Raised when a prompt's SHA-256 hash does not match the stored hash."""


class PromptValidationError(ValueError):
    """Raised when a prompt is missing required sections."""


class PromptSecretError(ValueError):
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
# Matches secret-like patterns with:
# - Assignment operators (=, :) followed by a value, OR
# - Natural language with value-like strings nearby ("api_key is sk-abc123")
SECRET_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:api[_-]?key|token|password|secret|credential)\s*(?:[:=]|is|of)\s*['\"]?[a-zA-Z0-9_-]{6,}",
    re.IGNORECASE,
)


class PromptStore:
    """Load and verify agent prompts with hash integrity checks."""

    def __init__(self, repository_root: Path) -> None:
        """Initialize the prompt store.

        Args:
            repository_root: Path to the repository root containing `prompts/agents/`.
        """
        self._repository_root = repository_root
        self._prompts_dir = repository_root / "prompts" / "agents"

    def load(
        self,
        agent_id: str,
        version: str,
        expected_hash: str,
    ) -> str:
        """Load an agent prompt and verify its integrity.

        Args:
            agent_id: The agent identifier (e.g., "A01", "A02").
            version: The prompt version (e.g., "v1").
            expected_hash: Required SHA-256 hash to verify against.
                          Hash verification always runs (fail-closed).

        Returns:
            The prompt content as a string.

        Raises:
            ValueError: If agent_id or version contains path traversal attempts.
            FileNotFoundError: If the prompt file does not exist.
            PromptIntegrityError: If the SHA-256 hash does not match expected_hash.
            PromptValidationError: If required sections are missing.
            PromptSecretError: If the prompt contains embedded secrets.
        """
        # Sanitize inputs to prevent directory traversal
        self._validate_path_component(agent_id, "agent_id")
        self._validate_path_component(version, "version")

        # Construct path: prompts/agents/<agent-id>/<version>.md
        prompt_path = self._prompts_dir / agent_id / f"{version}.md"

        # Resolve and verify path is within prompts/agents (prevent traversal)
        try:
            resolved_path = prompt_path.resolve()
            resolved_prompts_dir = self._prompts_dir.resolve()
            if not resolved_path.is_relative_to(resolved_prompts_dir):
                msg = f"Path traversal attempt detected: {agent_id}/{version}"
                raise ValueError(msg)
        except (OSError, ValueError) as error:
            msg = f"Invalid path for {agent_id}/{version}: {error}"
            raise ValueError(msg) from error

        if not resolved_path.is_file():
            msg = f"Prompt not found: {agent_id}/{version}"
            raise FileNotFoundError(msg)

        # Read the prompt content
        content = resolved_path.read_text(encoding="utf-8")

        # Always verify hash (fail-closed integrity)
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

    def _validate_path_component(self, component: str, name: str) -> None:
        """Validate a path component to prevent directory traversal.

        Args:
            component: The path component to validate (agent_id or version).
            name: The parameter name for error messages.

        Raises:
            ValueError: If the component contains dangerous patterns.
        """
        if not component:
            msg = f"{name} cannot be empty"
            raise ValueError(msg)

        # Reject path traversal attempts
        dangerous_patterns = ["..", "/", "\\", "\0", "~"]
        for pattern in dangerous_patterns:
            if pattern in component:
                msg = f"{name} contains forbidden pattern '{pattern}': {component}"
                raise ValueError(msg)

        # Reject absolute paths (starting with / or drive letter on Windows)
        if component.startswith("/") or (len(component) > 1 and component[1] == ":"):
            msg = f"{name} cannot be an absolute path: {component}"
            raise ValueError(msg)

    def _validate_sections(self, content: str, agent_id: str, version: str) -> None:
        """Validate that all required sections are present.

        Args:
            content: The prompt content.
            agent_id: The agent identifier.
            version: The prompt version.

        Raises:
            PromptValidationError: If any required section is missing.
        """
        missing_sections = [section for section in REQUIRED_SECTIONS if section not in content]

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
