"""Tests for seeding agent prompts into prompt_versions table.

Contract: Session 04 Wave 3, prompt-integrity addendum point 7.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from money_machine.persistence.seed import seed
from money_machine.persistence.tables import PromptVersion

if TYPE_CHECKING:
    from pytest import TempPathFactory
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def repo_with_agent_prompts(tmp_path_factory: TempPathFactory) -> Path:
    """Create a temporary repo with agent prompts."""
    root = tmp_path_factory.mktemp("repo")

    # Create prompts/agents structure
    agents_dir = root / "prompts" / "agents"
    agents_dir.mkdir(parents=True)

    # Create A01 prompt
    a01_dir = agents_dir / "A01"
    a01_dir.mkdir()
    a01_content = """# Shop Orchestrator

## Purpose
Orchestrate workflows.

## Input Contract
JobEnvelope

## Output Contract
AgentResult

## Instructions
Create jobs.

## Tool Permissions
Allowed: job.create
"""
    (a01_dir / "v1.md").write_text(a01_content, encoding="utf-8")

    # Create A02 prompt
    a02_dir = agents_dir / "A02"
    a02_dir.mkdir()
    a02_content = """# Account & Integration

## Purpose
Check integration readiness.

## Input Contract
JobEnvelope

## Output Contract
AgentResult or IncidentResult

## Instructions
Verify credentials.

## Tool Permissions
Allowed: provider.check
"""
    (a02_dir / "v1.md").write_text(a02_content, encoding="utf-8")

    # Create config directory (needed by seed)
    config_dir = root / "config"
    config_dir.mkdir()

    # Create minimal agents.yaml with 16 agents (schema requirement)
    agents_yaml_lines = ["version: 1", "agents:"]
    for i in range(1, 17):
        agent_num = f"A{i:02d}"
        agents_yaml_lines.extend(
            [
                f"  - agent_id: {agent_num}",
                f"    name: Agent {agent_num}",
                "    implementation_version: 1",
                "    contract_version: 1",
                f"    system_prompt_reference: agent://{agent_num}/system/v1",
                "    input_contracts: [JobEnvelope]",
                "    output_contracts: [AgentResult]",
                "    allowed_tools: [INTERNAL_ORCHESTRATION]",
                "    provider_operations: []",
                "    allowed_side_effect_classes: [NONE]",
                "    default_side_effect_class: NONE",
                "    allowed_retry_classes: [SAFE]",
                "    default_retry_class: SAFE",
                "    timeout_seconds: 300",
                "    model_policy: default",
                "    commissioning_state: DESIGNED",
                "    commissioning_evidence: []",
            ]
        )
    agents_yaml = "\n".join(agents_yaml_lines) + "\n"
    (config_dir / "agents.yaml").write_text(agents_yaml, encoding="utf-8")

    # Create empty implementation prompts directory (needed by seed)
    impl_prompts = root / "prompts" / "implementation"
    impl_prompts.mkdir(parents=True)

    return root


@pytest.mark.asyncio
async def test_seed_agent_prompts(
    repo_with_agent_prompts: Path,
    session: AsyncSession,
) -> None:
    """Seed creates prompt_versions rows for agent prompts."""
    # Run seed
    report = await seed(session, repository_root=repo_with_agent_prompts)
    await session.commit()

    # Check that prompt versions were created
    assert report.prompt_versions_created >= 2

    # Verify A01 prompt was seeded
    a01_prompt = (
        await session.execute(
            select(PromptVersion).where(PromptVersion.prompt_reference == "agent://A01/system/v1")
        )
    ).scalar_one_or_none()

    assert a01_prompt is not None
    assert a01_prompt.version == 1
    assert a01_prompt.source_path == "prompts/agents/A01/v1.md"
    assert len(a01_prompt.sha256) == 64

    # Verify A02 prompt was seeded
    a02_prompt = (
        await session.execute(
            select(PromptVersion).where(PromptVersion.prompt_reference == "agent://A02/system/v1")
        )
    ).scalar_one_or_none()

    assert a02_prompt is not None
    assert a02_prompt.version == 1
    assert a02_prompt.source_path == "prompts/agents/A02/v1.md"
    assert len(a02_prompt.sha256) == 64


@pytest.mark.asyncio
async def test_seed_agent_prompts_idempotent(
    repo_with_agent_prompts: Path,
    session: AsyncSession,
) -> None:
    """Seeding agent prompts twice is idempotent."""
    # First seed
    report1 = await seed(session, repository_root=repo_with_agent_prompts)
    await session.commit()

    created_first = report1.prompt_versions_created

    # Second seed (should be idempotent)
    report2 = await seed(session, repository_root=repo_with_agent_prompts)
    await session.commit()

    assert report2.prompt_versions_created == 0
    assert report2.prompt_versions_corrected == 0

    # Verify count hasn't changed
    count = (
        (
            await session.execute(
                select(PromptVersion).where(PromptVersion.prompt_reference.like("agent://%"))
            )
        )
        .scalars()
        .all()
    )

    assert len(count) == created_first


@pytest.mark.asyncio
async def test_seed_corrects_drifted_agent_prompts(
    repo_with_agent_prompts: Path,
    session: AsyncSession,
) -> None:
    """Seed corrects prompt_versions rows that drifted from source."""
    # First seed
    await seed(session, repository_root=repo_with_agent_prompts)
    await session.commit()

    # Manually drift the source_path
    a01_prompt = (
        await session.execute(
            select(PromptVersion).where(PromptVersion.prompt_reference == "agent://A01/system/v1")
        )
    ).scalar_one()

    a01_prompt.source_path = "wrong/path.md"
    await session.commit()

    # Second seed should correct it
    report = await seed(session, repository_root=repo_with_agent_prompts)
    await session.commit()

    assert report.prompt_versions_corrected >= 1

    # Verify correction
    corrected = (
        await session.execute(
            select(PromptVersion).where(PromptVersion.prompt_reference == "agent://A01/system/v1")
        )
    ).scalar_one()

    assert corrected.source_path == "prompts/agents/A01/v1.md"


@pytest.mark.asyncio
async def test_seed_agent_prompts_hash_matches_file(
    repo_with_agent_prompts: Path,
    session: AsyncSession,
) -> None:
    """Seeded prompt hashes match actual file content."""
    # Read A01 prompt file
    a01_path = repo_with_agent_prompts / "prompts" / "agents" / "A01" / "v1.md"
    a01_content = a01_path.read_text(encoding="utf-8")
    expected_hash = sha256(a01_content.encode("utf-8")).hexdigest()

    # Run seed
    await seed(session, repository_root=repo_with_agent_prompts)
    await session.commit()

    # Verify hash in database matches file
    a01_prompt = (
        await session.execute(
            select(PromptVersion).where(PromptVersion.prompt_reference == "agent://A01/system/v1")
        )
    ).scalar_one()

    assert a01_prompt.sha256 == expected_hash


@pytest.mark.asyncio
async def test_seed_multiple_versions_same_agent(
    tmp_path_factory: TempPathFactory,
    session: AsyncSession,
) -> None:
    """Seed handles multiple versions of the same agent prompt."""
    root = tmp_path_factory.mktemp("repo")
    agents_dir = root / "prompts" / "agents"
    a01_dir = agents_dir / "A01"
    a01_dir.mkdir(parents=True)

    # Create v1 and v2
    v1_content = """# V1

## Purpose
V1

## Input Contract
In

## Output Contract
Out

## Instructions
V1 instructions

## Tool Permissions
Allowed: v1
"""
    v2_content = """# V2

## Purpose
V2

## Input Contract
In

## Output Contract
Out

## Instructions
V2 instructions

## Tool Permissions
Allowed: v2
"""
    (a01_dir / "v1.md").write_text(v1_content, encoding="utf-8")
    (a01_dir / "v2.md").write_text(v2_content, encoding="utf-8")

    # Create minimal config structure with 16 agents (schema requirement)
    config_dir = root / "config"
    config_dir.mkdir()
    agents_yaml_lines = ["version: 1", "agents:"]
    for i in range(1, 17):
        agent_num = f"A{i:02d}"
        agents_yaml_lines.extend(
            [
                f"  - agent_id: {agent_num}",
                f"    name: Agent {agent_num}",
                "    implementation_version: 1",
                "    contract_version: 1",
                f"    system_prompt_reference: agent://{agent_num}/system/v1",
                "    input_contracts: [JobEnvelope]",
                "    output_contracts: [AgentResult]",
                "    allowed_tools: [INTERNAL_ORCHESTRATION]",
                "    provider_operations: []",
                "    allowed_side_effect_classes: [NONE]",
                "    default_side_effect_class: NONE",
                "    allowed_retry_classes: [SAFE]",
                "    default_retry_class: SAFE",
                "    timeout_seconds: 300",
                "    model_policy: default",
                "    commissioning_state: DESIGNED",
                "    commissioning_evidence: []",
            ]
        )
    agents_yaml = "\n".join(agents_yaml_lines) + "\n"
    (config_dir / "agents.yaml").write_text(agents_yaml, encoding="utf-8")
    impl_prompts = root / "prompts" / "implementation"
    impl_prompts.mkdir(parents=True)

    # Seed
    await seed(session, repository_root=root)
    await session.commit()

    # Verify both versions were seeded
    v1_prompt = (
        await session.execute(
            select(PromptVersion).where(PromptVersion.prompt_reference == "agent://A01/system/v1")
        )
    ).scalar_one()

    v2_prompt = (
        await session.execute(
            select(PromptVersion).where(PromptVersion.prompt_reference == "agent://A01/system/v2")
        )
    ).scalar_one()

    assert v1_prompt.version == 1
    assert v2_prompt.version == 2
    assert v1_prompt.sha256 != v2_prompt.sha256
