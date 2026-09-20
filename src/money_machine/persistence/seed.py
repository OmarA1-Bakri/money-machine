"""Idempotent, convergent seeding of canonical configuration.

What is seeded, per the Session 02 corrective addendum:

* one default shop in ``UNCONNECTED`` state;
* the sixteen agent definitions at the commissioning state recorded in
  ``config/agents.yaml`` (currently ``DESIGNED``); nothing is ever seeded as
  ``COMMISSIONED``;
* one prompt-version row per implementation prompt, carrying the file's real SHA-256;
* advisory ``config_references`` rows naming each loaded YAML file and its content hash.

What is deliberately **not** seeded: autonomy values, product-rule values, or workflow
definitions. YAML remains the single runtime authority for those (D-0019, D-0022,
addendum 3). Seeding them would fork authority.

Three properties, all tested:

* **idempotent** — an unchanged second run inserts nothing and mutates nothing;
* **convergent** — a row that has drifted from the YAML authority is corrected, so a
  hand-edited database cannot outrank ``config/agents.yaml``;
* **concurrency-safe** — inserts use ``ON CONFLICT DO NOTHING`` on the natural keys, so two
  processes seeding at once both succeed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast
from uuid import uuid4

from sqlalchemy import CursorResult, Insert, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.config.loader import load_yaml_model
from money_machine.config.settings import AgentsConfig
from money_machine.persistence.tables import (
    AgentDefinition,
    ConfigReference,
    PromptVersion,
    Shop,
)

DEFAULT_SHOP_NAME: Final = "default"
SEEDED_CONFIG_FILES: Final = (
    "product_rules.yaml",
    "publishing_ramp.yaml",
    "agents.yaml",
    "workflows.yaml",
    "telemetry.yaml",
)
"""The tracked YAML authority files whose identity is recorded. ``autonomy.yaml`` is
excluded on purpose: it is operator-owned, git-ignored standing authority."""

PROMPT_GLOB: Final = "*_SESSION_*.md"


@dataclass(frozen=True)
class SeedReport:
    """What one seed run changed. Every count is zero on an unchanged repeat run."""

    shops_created: int = 0
    agents_created: int = 0
    prompt_versions_created: int = 0
    config_references_created: int = 0
    agents_corrected: int = 0
    prompt_versions_corrected: int = 0

    @property
    def total_created(self) -> int:
        """Rows inserted by this run."""
        return (
            self.shops_created
            + self.agents_created
            + self.prompt_versions_created
            + self.config_references_created
        )

    @property
    def total_corrected(self) -> int:
        """Rows whose drifted columns this run restored from the YAML authority."""
        return self.agents_corrected + self.prompt_versions_corrected

    @property
    def changed(self) -> bool:
        """Whether this run inserted or corrected anything."""
        return self.total_created > 0 or self.total_corrected > 0


async def _insert_count(session: AsyncSession, statement: Insert) -> int:
    """Execute one conflict-tolerant insert and report whether a row was written."""
    result = await session.execute(statement)
    return int(cast("CursorResult[Any]", result).rowcount or 0)


def file_sha256(path: Path) -> str:
    """Content hash of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def seed(
    session: AsyncSession,
    *,
    repository_root: Path,
    shop_name: str = DEFAULT_SHOP_NAME,
) -> SeedReport:
    """Insert or correct canonical configuration, and nothing else.

    The caller owns the transaction: this function flushes but never commits.
    """
    shops = await _seed_shop(session, shop_name)
    agents_created, agents_corrected = await _seed_agents(session, repository_root)
    prompts_created, prompts_corrected = await _seed_prompt_versions(session, repository_root)
    configs = await _seed_config_references(session, repository_root)
    await session.flush()
    return SeedReport(
        shops_created=shops,
        agents_created=agents_created,
        prompt_versions_created=prompts_created,
        config_references_created=configs,
        agents_corrected=agents_corrected,
        prompt_versions_corrected=prompts_corrected,
    )


async def _seed_shop(session: AsyncSession, shop_name: str) -> int:
    statement = (
        insert(Shop)
        .values(
            id=uuid4(),
            name=shop_name,
            connection_state="UNCONNECTED",
            timezone="UTC",
            active=True,
        )
        .on_conflict_do_nothing(index_elements=[Shop.name])
    )
    return await _insert_count(session, statement)


async def _seed_agents(session: AsyncSession, repository_root: Path) -> tuple[int, int]:
    roster = load_yaml_model(repository_root / "config/agents.yaml", AgentsConfig)
    created = 0
    corrected = 0
    for definition in roster.agents:
        authoritative: dict[str, object] = {
            "name": definition.name,
            "implementation_version": definition.implementation_version,
            "default_side_effect_class": definition.default_side_effect_class.value,
            "default_retry_class": definition.default_retry_class.value,
            "timeout_seconds": definition.timeout_seconds,
            "commissioning_state": definition.commissioning_state.value,
            "commissioning_evidence": list(definition.commissioning_evidence),
        }
        statement = (
            insert(AgentDefinition)
            .values(
                id=uuid4(),
                agent_id=definition.agent_id,
                contract_version=definition.contract_version,
                **authoritative,
            )
            .on_conflict_do_nothing(
                index_elements=[AgentDefinition.agent_id, AgentDefinition.contract_version]
            )
        )
        inserted = await _insert_count(session, statement)
        created += inserted
        if inserted:
            continue
        existing = (
            (
                await session.execute(
                    select(AgentDefinition).where(
                        AgentDefinition.agent_id == definition.agent_id,
                        AgentDefinition.contract_version == definition.contract_version,
                    )
                )
            )
            .scalars()
            .one()
        )
        drifted = {
            field: value
            for field, value in authoritative.items()
            if getattr(existing, field) != value
        }
        if drifted:
            for field, value in drifted.items():
                setattr(existing, field, value)
            corrected += 1
    return created, corrected


async def _seed_prompt_versions(
    session: AsyncSession,
    repository_root: Path,
) -> tuple[int, int]:
    """Seed both implementation prompts and agent prompts."""
    created = 0
    corrected = 0

    # Seed implementation prompts (session prompts)
    impl_prompts = sorted((repository_root / "prompts/implementation").glob(PROMPT_GLOB))
    for prompt in impl_prompts:
        digest = file_sha256(prompt)
        reference = f"prompt://{prompt.stem}"
        source_path = f"prompts/implementation/{prompt.name}"
        statement = (
            insert(PromptVersion)
            .values(
                id=uuid4(),
                prompt_reference=reference,
                version=1,
                sha256=digest,
                source_path=source_path,
            )
            .on_conflict_do_nothing(index_elements=[PromptVersion.sha256])
        )
        inserted = await _insert_count(session, statement)
        created += inserted
        if inserted:
            continue
        existing = (
            (await session.execute(select(PromptVersion).where(PromptVersion.sha256 == digest)))
            .scalars()
            .one()
        )
        if (existing.source_path, existing.prompt_reference) != (source_path, reference):
            existing.source_path = source_path
            existing.prompt_reference = reference
            corrected += 1

    # Seed agent prompts from prompts/agents/<agent-id>/<version>.md
    agents_dir = repository_root / "prompts" / "agents"
    if agents_dir.exists():
        for agent_dir in sorted(agents_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            agent_id = agent_dir.name
            for prompt_file in sorted(agent_dir.glob("*.md")):
                digest = file_sha256(prompt_file)
                version_name = prompt_file.stem  # e.g., "v1"
                # Extract version number (v1 -> 1, v2 -> 2, etc.)
                try:
                    version_num = int(version_name.lstrip("v"))
                except ValueError:
                    # Skip files that don't match v<number> pattern
                    continue
                reference = f"agent://{agent_id}/system/{version_name}"
                source_path = f"prompts/agents/{agent_id}/{prompt_file.name}"
                statement = (
                    insert(PromptVersion)
                    .values(
                        id=uuid4(),
                        prompt_reference=reference,
                        version=version_num,
                        sha256=digest,
                        source_path=source_path,
                    )
                    .on_conflict_do_nothing(index_elements=[PromptVersion.sha256])
                )
                inserted = await _insert_count(session, statement)
                created += inserted
                if inserted:
                    continue
                existing = (
                    (
                        await session.execute(
                            select(PromptVersion).where(PromptVersion.sha256 == digest)
                        )
                    )
                    .scalars()
                    .one()
                )
                if (existing.source_path, existing.prompt_reference) != (source_path, reference):
                    existing.source_path = source_path
                    existing.prompt_reference = reference
                    corrected += 1

    return created, corrected


async def _seed_config_references(session: AsyncSession, repository_root: Path) -> int:
    created = 0
    for name in SEEDED_CONFIG_FILES:
        path = repository_root / "config" / name
        if not path.is_file():
            continue
        statement = (
            insert(ConfigReference)
            .values(
                id=uuid4(),
                config_name=name,
                source_path=f"config/{name}",
                sha256=file_sha256(path),
                advisory_only=True,
            )
            .on_conflict_do_nothing(
                index_elements=[ConfigReference.config_name, ConfigReference.sha256]
            )
        )
        created += await _insert_count(session, statement)
    return created
