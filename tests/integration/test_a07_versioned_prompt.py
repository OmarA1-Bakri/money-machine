"""Actual versioned prompt loading is separate from production admission."""

from hashlib import sha256

import pytest
from sqlalchemy import select

from money_machine.agents.base import AgentNotCommissionedError
from money_machine.agents.prompt_store import PromptIntegrityError, PromptStore
from money_machine.agents.registry import AgentRegistry
from money_machine.domain.enums import AgentRunStatus
from money_machine.persistence.seed import seed
from money_machine.persistence.tables import AgentDefinition, AgentRun, PromptVersion
from tests.integration.test_notification_recovery_guard import recovery as recovery
from tests.integration.test_notification_recovery_invocation import invocation as invocation
from tests.integration.test_real_draft_runner import runner_inputs as runner_inputs


async def test_actual_a07_prompt_seeds_loads_and_preserves_designed_state(session, repository_root):
    path = repository_root / "prompts/agents/A07/v1.md"
    payload = path.read_bytes()
    digest = sha256(payload).hexdigest()
    await seed(session, repository_root=repository_root)
    await session.commit()
    stored = (
        await session.scalars(
            select(PromptVersion).where(PromptVersion.prompt_reference == "agent://A07/system/v1")
        )
    ).one()
    assert stored.sha256 == digest and stored.source_path == "prompts/agents/A07/v1.md"
    assert PromptStore(repository_root).load("A07", "v1", stored.sha256).encode() == payload
    with pytest.raises(PromptIntegrityError):
        PromptStore(repository_root).load("A07", "v1", "f" * 64)
    definition = (
        await session.scalars(select(AgentDefinition).where(AgentDefinition.agent_id == "A07"))
    ).one()
    assert definition.commissioning_state == "DESIGNED" and not definition.commissioning_evidence
    again = await seed(session, repository_root=repository_root)
    await session.commit()
    assert again.total_created == 0 and not again.changed


async def test_real_artifact_does_not_enable_production(session, repository_root):
    from money_machine.agents.base import assert_production_executable

    definition = AgentRegistry.from_yaml(repository_root).get("A07")
    with pytest.raises(AgentNotCommissionedError):
        assert_production_executable(definition)


async def test_conflicting_registered_version_is_not_overwritten(session, repository_root):
    from sqlalchemy.exc import IntegrityError

    legacy = PromptVersion(
        prompt_reference="agent://A07/system/v1",
        version=1,
        sha256="a" * 64,
        source_path="legacy-registered-prompt",
    )
    session.add(legacy)
    await session.commit()
    legacy_id = legacy.id
    with pytest.raises(IntegrityError):
        await seed(session, repository_root=repository_root)
    await session.rollback()
    unchanged = await session.get(PromptVersion, legacy_id)
    assert unchanged.sha256 == "a" * 64 and unchanged.source_path == "legacy-registered-prompt"


@pytest.mark.parametrize("recovery", ["runner"], indirect=True)
async def test_finite_fixture_path_traces_the_actual_default_prompt(
    invocation, session_factory, repository_root
):
    state, execute, *_ = invocation
    result, _ = await execute()
    assert result.status == AgentRunStatus.SUCCESS and state["posts"] == 1
    async with session_factory() as session:
        run = await session.get(AgentRun, result.agent_run_id)
        prompt = await session.get(PromptVersion, run.prompt_version_id)
        expected = sha256((repository_root / "prompts/agents/A07/v1.md").read_bytes()).hexdigest()
        assert prompt.sha256 == run.prompt_sha256 == expected
        assert prompt.source_path == "prompts/agents/A07/v1.md"
        assert run.prompt_reference == "agent://A07/system/v1"
