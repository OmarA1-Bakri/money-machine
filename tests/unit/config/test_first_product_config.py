"""Tests for the strict first-product YAML configuration contract."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from money_machine.config.loader import load_first_product_config
from money_machine.config.validation import (
    FIRST_PRODUCT_JOB_TYPES,
    FIRST_PRODUCT_ROLE_IDS,
    FirstProductConfig,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "config"


def test_product_rules_freeze_all_slice_counts_and_safety_flags() -> None:
    config = load_first_product_config(CONFIG_ROOT)
    rules = config.product_rules

    assert (rules.research.min_rows, rules.research.max_rows) == (25, 40)
    assert rules.qualification.shortlist_size == 5
    assert rules.qualification.minimum_total_score == 30
    assert (rules.product.min_hubs, rules.product.max_hubs) == (6, 8)
    assert (rules.product.min_colour_variants, rules.product.max_colour_variants) == (3, 4)
    assert rules.listing.tag_count == 13
    assert rules.listing.image_count == 10
    assert rules.listing.video_count == 1
    assert rules.listing.video_mode == "REQUIRED_GENERATED"
    assert rules.safety.external_mutations_enabled is False
    assert rules.safety.spend_enabled is False


def test_exact_first_slice_roles_are_registered_once() -> None:
    config = load_first_product_config(CONFIG_ROOT)
    role_ids = tuple(role.role_id for role in config.agents.roles)

    assert role_ids == FIRST_PRODUCT_ROLE_IDS
    assert len(role_ids) == len(set(role_ids))
    assert all(role.external_mutations_enabled is False for role in config.agents.roles)


def test_exact_first_slice_workflow_steps_are_registered_once_and_in_order() -> None:
    config = load_first_product_config(CONFIG_ROOT)
    workflow = config.workflows.workflows[0]

    assert config.workflows.workflows[0].workflow_id == "first-product"
    assert tuple(step.job_type for step in workflow.steps) == FIRST_PRODUCT_JOB_TYPES
    assert FIRST_PRODUCT_JOB_TYPES == (
        "ADMIT_RESEARCH_PACKET",
        "QUALIFY_CANDIDATES",
        "CREATE_PRODUCT_SPEC",
        "CHECK_CATALOGUE_DEDUPE",
        "BUILD_PRODUCT",
        "RUN_PRODUCT_QA",
        "CREATE_LISTING_PACKAGE",
        "RUN_PREFLIGHT",
    )
    assert len(workflow.steps) == len({step.job_type for step in workflow.steps})
    assert workflow.external_mutations_enabled is False
    assert workflow.spend_enabled is False


def test_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    _write_valid_config(tmp_path)
    product_rules = (tmp_path / "product_rules.yaml").read_text(encoding="utf-8")
    (tmp_path / "product_rules.yaml").write_text(
        f"{product_rules}\nunreviewed_rule: true\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        load_first_product_config(tmp_path)


@pytest.mark.parametrize(
    ("filename", "duplicate"),
    [
        ("product_rules.yaml", "version: 1\nversion: 1\n"),
        ("agents.yaml", "version: 1\nversion: 1\n"),
        ("workflows.yaml", "version: 1\nversion: 1\n"),
    ],
)
def test_all_strict_loaders_reject_duplicate_root_keys(
    tmp_path: Path, filename: str, duplicate: str
) -> None:
    _write_valid_config(tmp_path)
    path = tmp_path / filename
    path.write_text(path.read_text(encoding="utf-8").replace("version: 1\n", duplicate, 1))

    with pytest.raises(ValueError, match="duplicate YAML mapping key"):
        load_first_product_config(tmp_path)


@pytest.mark.parametrize(
    ("filename", "original", "duplicate"),
    [
        (
            "product_rules.yaml",
            "  spend_enabled: false\n",
            "  spend_enabled: false\n  spend_enabled: false\n",
        ),
        (
            "agents.yaml",
            "  - role_id: market_research\n",
            "  - role_id: market_research\n    role_id: market_research\n",
        ),
        (
            "workflows.yaml",
            "      - job_type: ADMIT_RESEARCH_PACKET\n",
            "      - job_type: ADMIT_RESEARCH_PACKET\n        job_type: ADMIT_RESEARCH_PACKET\n",
        ),
    ],
)
def test_all_strict_loaders_reject_duplicate_nested_keys(
    tmp_path: Path, filename: str, original: str, duplicate: str
) -> None:
    _write_valid_config(tmp_path)
    path = tmp_path / filename
    path.write_text(path.read_text(encoding="utf-8").replace(original, duplicate, 1))

    with pytest.raises(ValueError, match="duplicate YAML mapping key"):
        load_first_product_config(tmp_path)


def test_validated_registries_are_deeply_immutable_tuples() -> None:
    config = load_first_product_config(CONFIG_ROOT)
    workflow = config.workflows.workflows[0]

    assert isinstance(config.agents.roles, tuple)
    assert isinstance(config.workflows.workflows, tuple)
    assert isinstance(workflow.steps, tuple)
    assert not hasattr(config.agents.roles, "append")
    assert not hasattr(workflow.steps, "append")
    with pytest.raises(ValidationError, match="Instance is frozen"):
        config.agents.roles[0].role_id = "changed"


def test_loader_rejects_duplicate_roles_and_steps(tmp_path: Path) -> None:
    _write_valid_config(tmp_path)
    loaded = load_first_product_config(tmp_path)

    duplicated_role = loaded.agents.model_copy(
        update={"roles": (*loaded.agents.roles, loaded.agents.roles[0])}
    )
    with pytest.raises(ValidationError, match="duplicate role_id"):
        FirstProductConfig(
            product_rules=loaded.product_rules,
            agents=duplicated_role,
            workflows=loaded.workflows,
        )

    workflow = loaded.workflows.workflows[0]
    duplicated_workflow = workflow.model_copy(
        update={"steps": (*workflow.steps, workflow.steps[0])}
    )
    duplicated_steps = loaded.workflows.model_copy(update={"workflows": (duplicated_workflow,)})
    with pytest.raises(ValidationError, match="duplicate job_type"):
        FirstProductConfig(
            product_rules=loaded.product_rules,
            agents=loaded.agents,
            workflows=duplicated_steps,
        )


def test_configuration_rejects_conflicting_ranges_and_unsafe_modes(tmp_path: Path) -> None:
    _write_valid_config(tmp_path)
    loaded = load_first_product_config(tmp_path)

    bad_research = loaded.product_rules.research.model_copy(update={"min_rows": 41, "max_rows": 40})
    with pytest.raises(ValidationError, match="min_rows"):
        loaded.product_rules.model_copy(update={"research": bad_research}).__class__.model_validate(
            {
                **loaded.product_rules.model_dump(),
                "research": bad_research.model_dump(),
            },
            strict=True,
        )

    unsafe = loaded.product_rules.safety.model_copy(update={"spend_enabled": True})
    with pytest.raises(ValidationError, match="spend_enabled"):
        loaded.product_rules.__class__.model_validate(
            {
                **loaded.product_rules.model_dump(),
                "safety": unsafe.model_dump(),
            },
            strict=True,
        )


def _write_valid_config(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("product_rules.yaml", "agents.yaml", "workflows.yaml"):
        (destination / name).write_bytes((CONFIG_ROOT / name).read_bytes())
