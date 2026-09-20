"""Seeding must be idempotent by content and must not fork configuration authority."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.persistence.seed import SEEDED_CONFIG_FILES, seed
from money_machine.persistence.tables import AgentDefinition, ConfigReference, PromptVersion, Shop


async def count(session: AsyncSession, table: type[object]) -> int:
    """Count rows in one table."""
    return int((await session.execute(select(func.count()).select_from(table))).scalar_one())


async def test_seed_inserts_the_canonical_configuration(
    session: AsyncSession,
    repository_root: Path,
) -> None:
    """One shop, sixteen agents at their real state, every prompt, every config file."""
    report = await seed(session, repository_root=repository_root)

    assert report.shops_created == 1
    assert report.agents_created == 16
    assert report.prompt_versions_created == 18  # 16 impl + A01 + A02 agent prompts
    assert report.config_references_created == len(SEEDED_CONFIG_FILES)
    assert report.changed

    shop = (await session.execute(select(Shop))).scalars().one()
    assert shop.connection_state == "UNCONNECTED"
    assert shop.timezone == "UTC"

    agents = (await session.execute(select(AgentDefinition))).scalars().all()
    assert {row.agent_id for row in agents} == {f"A{number:02d}" for number in range(1, 17)}
    # L2: A01/A02 are TESTED, A03-A16 are DESIGNED
    assert {row.commissioning_state for row in agents} == {"DESIGNED", "TESTED"}
    tested_agents = {row.agent_id for row in agents if row.commissioning_state == "TESTED"}
    assert tested_agents == {"A01", "A02"}
    assert all(row.commissioning_evidence == [] for row in agents)


async def test_seed_is_idempotent(session: AsyncSession, repository_root: Path) -> None:
    """A second and third run insert nothing and mutate nothing."""
    await seed(session, repository_root=repository_root)
    await session.commit()
    before = {
        "shops": await count(session, Shop),
        "agents": await count(session, AgentDefinition),
        "prompts": await count(session, PromptVersion),
        "configs": await count(session, ConfigReference),
    }
    fingerprint = {
        row.id: (row.agent_id, row.commissioning_state, row.contract_version)
        for row in (await session.execute(select(AgentDefinition))).scalars().all()
    }

    second = await seed(session, repository_root=repository_root)
    third = await seed(session, repository_root=repository_root)
    await session.commit()

    assert second.total_created == 0
    assert third.total_created == 0
    assert not second.changed
    assert {
        "shops": await count(session, Shop),
        "agents": await count(session, AgentDefinition),
        "prompts": await count(session, PromptVersion),
        "configs": await count(session, ConfigReference),
    } == before
    assert {
        row.id: (row.agent_id, row.commissioning_state, row.contract_version)
        for row in (await session.execute(select(AgentDefinition))).scalars().all()
    } == fingerprint


async def test_seed_records_real_prompt_hashes(
    session: AsyncSession,
    repository_root: Path,
) -> None:
    """Prompt versions carry the file's actual hash, so lineage is checkable."""
    import hashlib

    await seed(session, repository_root=repository_root)
    rows = (await session.execute(select(PromptVersion))).scalars().all()

    by_path = {row.source_path: row.sha256 for row in rows}
    for path, digest in by_path.items():
        actual = hashlib.sha256((repository_root / path).read_bytes()).hexdigest()
        assert digest == actual, path
    assert len(by_path) == len(rows)


async def test_seed_never_writes_autonomy_or_rule_values(
    session: AsyncSession,
    repository_root: Path,
) -> None:
    """YAML stays the only runtime authority (D-0019, addendum 3)."""
    await seed(session, repository_root=repository_root)

    references = (await session.execute(select(ConfigReference))).scalars().all()

    assert {row.config_name for row in references} == set(SEEDED_CONFIG_FILES)
    assert "autonomy.yaml" not in {row.config_name for row in references}
    assert "autonomy.example.yaml" not in {row.config_name for row in references}
    assert all(row.advisory_only for row in references)
    assert not (repository_root / "config/autonomy.yaml").exists()
    columns = set(ConfigReference.__table__.c.keys())
    assert columns == {
        "id",
        "config_name",
        "source_path",
        "sha256",
        "advisory_only",
        "loaded_at",
    }


async def test_seed_never_marks_an_agent_commissioned(
    session: AsyncSession,
    repository_root: Path,
) -> None:
    """No seeded agent may claim commissioning, per the prompt and the addendum."""
    await seed(session, repository_root=repository_root)

    commissioned = (
        (
            await session.execute(
                select(AgentDefinition).where(AgentDefinition.commissioning_state == "COMMISSIONED")
            )
        )
        .scalars()
        .all()
    )

    assert commissioned == []
