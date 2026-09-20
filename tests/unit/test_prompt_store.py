"""Tests for PromptStore: load, hash verification, section validation, secret detection.

Contract: Session 04 Wave 3, prompt-integrity addendum point 7.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from money_machine.agents.prompt_store import (
    PromptIntegrityError,
    PromptSecretError,
    PromptStore,
    PromptValidationError,
)

if TYPE_CHECKING:
    from pytest import TempPathFactory


@pytest.fixture
def prompts_root(tmp_path_factory: TempPathFactory) -> Path:
    """Create a temporary prompts directory structure."""
    root = tmp_path_factory.mktemp("repo")
    agents_dir = root / "prompts" / "agents"
    agents_dir.mkdir(parents=True)
    return root


@pytest.fixture
def valid_prompt_content() -> str:
    """A valid prompt with all required sections."""
    return """# Test Agent

## Purpose
This is a test agent for validation.

## Input Contract
Receives JobEnvelope with test data.

## Output Contract
Returns AgentResult with test output.

## Instructions
1. Do the thing
2. Return the result

## Tool Permissions
Allowed:
- tool.read
- tool.write

Prohibited:
- dangerous.tool
"""


@pytest.fixture
def prompt_with_secret() -> str:
    """A prompt containing a forbidden secret pattern."""
    return """# Test Agent

## Purpose
This agent has an embedded api_key which is forbidden.

The API_KEY is sk-abc123.

## Input Contract
Receives JobEnvelope.

## Output Contract
Returns AgentResult.

## Instructions
Use the api_key to connect.

## Tool Permissions
Allowed: tool.read
"""


@pytest.fixture
def prompt_missing_section() -> str:
    """A prompt missing the Tool Permissions section."""
    return """# Test Agent

## Purpose
This agent is missing Tool Permissions.

## Input Contract
Receives JobEnvelope.

## Output Contract
Returns AgentResult.

## Instructions
Do the work.
"""


def test_load_with_correct_hash(prompts_root: Path, valid_prompt_content: str) -> None:
    """Load succeeds when hash matches."""
    # Create prompt file
    agent_dir = prompts_root / "prompts" / "agents" / "A01"
    agent_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = agent_dir / "v1.md"
    prompt_path.write_text(valid_prompt_content, encoding="utf-8")

    # Calculate expected hash
    expected_hash = sha256(valid_prompt_content.encode("utf-8")).hexdigest()

    # Load with hash verification
    store = PromptStore(prompts_root)
    content = store.load("A01", "v1", expected_hash=expected_hash)

    assert content == valid_prompt_content


def test_load_with_incorrect_hash(prompts_root: Path, valid_prompt_content: str) -> None:
    """Load fails when hash does not match."""
    agent_dir = prompts_root / "prompts" / "agents" / "A01"
    agent_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = agent_dir / "v1.md"
    prompt_path.write_text(valid_prompt_content, encoding="utf-8")

    # Use a wrong hash
    wrong_hash = "0" * 64

    store = PromptStore(prompts_root)
    with pytest.raises(PromptIntegrityError, match="hash mismatch"):
        store.load("A01", "v1", expected_hash=wrong_hash)


def test_load_file_not_found(prompts_root: Path) -> None:
    """Load fails when prompt file does not exist."""
    expected_hash = "a" * 64  # Dummy hash, file check happens first
    store = PromptStore(prompts_root)
    with pytest.raises(FileNotFoundError, match="Prompt not found"):
        store.load("A99", "v1", expected_hash=expected_hash)


def test_load_missing_required_section(prompts_root: Path, prompt_missing_section: str) -> None:
    """Load fails when required section is missing."""
    agent_dir = prompts_root / "prompts" / "agents" / "A01"
    agent_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = agent_dir / "v1.md"
    prompt_path.write_text(prompt_missing_section, encoding="utf-8")

    # Hash verification happens before section validation, use correct hash
    expected_hash = sha256(prompt_missing_section.encode("utf-8")).hexdigest()

    store = PromptStore(prompts_root)
    with pytest.raises(PromptValidationError, match="missing required sections"):
        store.load("A01", "v1", expected_hash=expected_hash)


def test_load_with_embedded_secret(prompts_root: Path, prompt_with_secret: str) -> None:
    """Load fails when prompt contains secret patterns."""
    agent_dir = prompts_root / "prompts" / "agents" / "A01"
    agent_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = agent_dir / "v1.md"
    prompt_path.write_text(prompt_with_secret, encoding="utf-8")

    # Hash verification happens before secret check, use correct hash
    expected_hash = sha256(prompt_with_secret.encode("utf-8")).hexdigest()

    store = PromptStore(prompts_root)
    with pytest.raises(PromptSecretError, match="forbidden secret patterns"):
        store.load("A01", "v1", expected_hash=expected_hash)


def test_secret_detection_patterns(prompts_root: Path) -> None:
    """Verify various secret patterns are detected."""
    secret_patterns = [
        "api_key = 'sk-123'",
        "API-KEY: abc123",
        "apikey=secret",
        "TOKEN=bearer_token",
        "password: mypassword",
        "SECRET: sensitive",
        "credential: cred123",
    ]

    agent_dir = prompts_root / "prompts" / "agents" / "A01"
    agent_dir.mkdir(parents=True, exist_ok=True)
    store = PromptStore(prompts_root)

    for idx, pattern in enumerate(secret_patterns):
        prompt_content = f"""# Test Agent

## Purpose
Test secret detection.

## Input Contract
Input data.

## Output Contract
Output data.

## Instructions
Contains: {pattern}

## Tool Permissions
Allowed: none
"""
        prompt_path = agent_dir / f"v{idx + 1}.md"
        prompt_path.write_text(prompt_content, encoding="utf-8")

        # Compute hash for this prompt
        expected_hash = sha256(prompt_content.encode("utf-8")).hexdigest()

        with pytest.raises(PromptSecretError, match="forbidden secret patterns"):
            store.load("A01", f"v{idx + 1}", expected_hash=expected_hash)


def test_hash_stability(prompts_root: Path, valid_prompt_content: str) -> None:
    """Verify hash is stable across multiple loads."""
    agent_dir = prompts_root / "prompts" / "agents" / "A01"
    agent_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = agent_dir / "v1.md"
    prompt_path.write_text(valid_prompt_content, encoding="utf-8")

    expected_hash = sha256(valid_prompt_content.encode("utf-8")).hexdigest()
    store = PromptStore(prompts_root)

    # Load multiple times with same hash
    for _ in range(3):
        content = store.load("A01", "v1", expected_hash=expected_hash)
        assert content == valid_prompt_content


def test_load_different_agent_versions(prompts_root: Path) -> None:
    """Load different versions of the same agent."""
    agent_dir = prompts_root / "prompts" / "agents" / "A01"
    agent_dir.mkdir(parents=True, exist_ok=True)

    v1_content = """# Agent V1

## Purpose
Version 1

## Input Contract
Input

## Output Contract
Output

## Instructions
V1 instructions

## Tool Permissions
Allowed: v1_tool
"""

    v2_content = """# Agent V2

## Purpose
Version 2

## Input Contract
Input

## Output Contract
Output

## Instructions
V2 instructions

## Tool Permissions
Allowed: v2_tool
"""

    (agent_dir / "v1.md").write_text(v1_content, encoding="utf-8")
    (agent_dir / "v2.md").write_text(v2_content, encoding="utf-8")

    v1_hash = sha256(v1_content.encode("utf-8")).hexdigest()
    v2_hash = sha256(v2_content.encode("utf-8")).hexdigest()

    store = PromptStore(prompts_root)
    v1_loaded = store.load("A01", "v1", expected_hash=v1_hash)
    v2_loaded = store.load("A01", "v2", expected_hash=v2_hash)

    assert v1_loaded == v1_content
    assert v2_loaded == v2_content
    assert "V1 instructions" in v1_loaded
    assert "V2 instructions" in v2_loaded


def test_path_traversal_parent_directory(prompts_root: Path) -> None:
    """Reject path traversal attempts using parent directory (..)."""
    store = PromptStore(prompts_root)
    expected_hash = "a" * 64  # Dummy hash

    # Try to escape via agent_id
    with pytest.raises(ValueError, match="agent_id contains forbidden pattern"):
        store.load("../../../etc", "v1", expected_hash=expected_hash)

    # Try to escape via version
    with pytest.raises(ValueError, match="version contains forbidden pattern"):
        store.load("A01", "../../../passwd", expected_hash=expected_hash)


def test_path_traversal_absolute_path(prompts_root: Path) -> None:
    """Reject absolute path attempts."""
    store = PromptStore(prompts_root)
    expected_hash = "a" * 64  # Dummy hash

    # Absolute Unix path (caught by slash check)
    with pytest.raises(ValueError, match=r"forbidden pattern '/'"):
        store.load("/etc/passwd", "v1", expected_hash=expected_hash)

    # Absolute Windows path (caught by backslash or colon check)
    with pytest.raises(ValueError, match=r"forbidden pattern|cannot be an absolute path"):
        store.load("C:\\Windows", "v1", expected_hash=expected_hash)


def test_path_traversal_forward_slash(prompts_root: Path) -> None:
    """Reject path components with forward slashes."""
    store = PromptStore(prompts_root)
    expected_hash = "a" * 64  # Dummy hash

    with pytest.raises(ValueError, match="forbidden pattern"):
        store.load("A01/subdir", "v1", expected_hash=expected_hash)


def test_path_traversal_backslash(prompts_root: Path) -> None:
    """Reject path components with backslashes."""
    store = PromptStore(prompts_root)
    expected_hash = "a" * 64  # Dummy hash

    with pytest.raises(ValueError, match="forbidden pattern"):
        store.load("A01\\subdir", "v1", expected_hash=expected_hash)


def test_path_traversal_null_byte(prompts_root: Path) -> None:
    """Reject path components with null bytes."""
    store = PromptStore(prompts_root)
    expected_hash = "a" * 64  # Dummy hash

    with pytest.raises(ValueError, match="forbidden pattern"):
        store.load("A01\x00hidden", "v1", expected_hash=expected_hash)


def test_path_traversal_tilde(prompts_root: Path) -> None:
    """Reject path components with tilde (home directory expansion)."""
    store = PromptStore(prompts_root)
    expected_hash = "a" * 64  # Dummy hash

    with pytest.raises(ValueError, match="forbidden pattern"):
        store.load("~/.ssh", "v1", expected_hash=expected_hash)


def test_empty_path_component(prompts_root: Path) -> None:
    """Reject empty path components."""
    store = PromptStore(prompts_root)
    expected_hash = "a" * 64  # Dummy hash

    with pytest.raises(ValueError, match="cannot be empty"):
        store.load("", "v1", expected_hash=expected_hash)

    with pytest.raises(ValueError, match="cannot be empty"):
        store.load("A01", "", expected_hash=expected_hash)


def test_real_a01_prompt_loads(repository_root: Path) -> None:
    """Verify the real A01 prompt exists and loads correctly."""
    real_prompts_dir = repository_root / "prompts" / "agents" / "A01"

    if not real_prompts_dir.exists():
        pytest.skip("Real A01 prompt not found")

    v1_path = real_prompts_dir / "v1.md"
    if not v1_path.exists():
        pytest.skip("A01 v1 prompt not found")

    # Read the real prompt
    real_content = v1_path.read_text(encoding="utf-8")
    expected_hash = sha256(real_content.encode("utf-8")).hexdigest()

    # Load it through the store
    store = PromptStore(repository_root)
    content = store.load("A01", "v1", expected_hash=expected_hash)

    assert content == real_content
    assert "## Purpose" in content
    assert "Shop Orchestrator" in content


def test_real_a02_prompt_loads(repository_root: Path) -> None:
    """Verify the real A02 prompt exists and loads correctly."""
    real_prompts_dir = repository_root / "prompts" / "agents" / "A02"

    if not real_prompts_dir.exists():
        pytest.skip("Real A02 prompt not found")

    v1_path = real_prompts_dir / "v1.md"
    if not v1_path.exists():
        pytest.skip("A02 v1 prompt not found")

    real_content = v1_path.read_text(encoding="utf-8")
    expected_hash = sha256(real_content.encode("utf-8")).hexdigest()

    store = PromptStore(repository_root)
    content = store.load("A02", "v1", expected_hash=expected_hash)

    assert content == real_content
    assert "## Purpose" in content
    assert "Account & Integration" in content
