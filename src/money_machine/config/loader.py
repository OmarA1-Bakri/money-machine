"""Safe YAML loading for the canonical application configurations."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import ValidationError

from money_machine.config.settings import (
    AgentsConfig,
    AutonomyConfig,
    ConfigModel,
    ConfigurationBundle,
    ProductRulesConfig,
    PublishingRampConfig,
    RuntimeEnvironment,
    TelemetryConfig,
    WorkflowsConfig,
)
from money_machine.config.validation import apply_environment_safety, validate_config_bundle

ENVIRONMENT_VARIABLE = "APP_ENV"
"""Process environment variable naming the runtime environment (see ``.env.example``)."""

AUTONOMY_FILE_NAME = "autonomy.yaml"
"""Operator-owned standing authority. Git-ignored; required in production."""

AUTONOMY_EXAMPLE_FILE_NAME = "autonomy.example.yaml"
"""Tracked fail-closed template. Never production authority."""


class ConfigLoadError(ValueError):
    """Raised when a configuration file cannot be parsed, located, or validated."""


def resolve_runtime_environment(
    environ: Mapping[str, str] | None = None,
) -> RuntimeEnvironment:
    """Resolve the runtime environment from the process environment, defaulting to development.

    Development is the fail-closed default: it forces simulation-only authority. An
    unrecognised value is an error rather than a silent downgrade or upgrade.
    """
    source = os.environ if environ is None else environ
    raw = source.get(ENVIRONMENT_VARIABLE, RuntimeEnvironment.DEVELOPMENT.value)
    try:
        return RuntimeEnvironment(raw.strip().lower())
    except ValueError as error:
        allowed = ", ".join(member.value for member in RuntimeEnvironment)
        raise ConfigLoadError(
            f"{ENVIRONMENT_VARIABLE}={raw!r} is not a runtime environment; "
            f"expected one of {allowed}"
        ) from error


def load_yaml_model[ConfigT: ConfigModel](path: Path, model_type: type[ConfigT]) -> ConfigT:
    """Parse one YAML mapping with ``safe_load`` and validate its exact schema."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigLoadError(f"cannot read configuration {path.name}: {error}") from error

    try:
        raw = yaml.safe_load(source)
    except yaml.YAMLError as error:
        raise ConfigLoadError(f"cannot parse YAML configuration {path.name}: {error}") from error
    if not isinstance(raw, dict):
        raise ConfigLoadError(f"configuration {path.name} must contain a mapping")

    try:
        return model_type.model_validate(raw)
    except ValidationError as error:
        raise ConfigLoadError(f"invalid configuration {path.name}: {error}") from error


def select_autonomy_path(config_directory: Path, environment: RuntimeEnvironment) -> Path:
    """Choose the standing-authority file: ``autonomy.yaml`` when present, else the template.

    Production fails closed when the operator file is absent; the tracked example is a
    template and must never become production authority.
    """
    operator_path = config_directory / AUTONOMY_FILE_NAME
    example_path = config_directory / AUTONOMY_EXAMPLE_FILE_NAME
    if operator_path.is_symlink():
        raise ConfigLoadError(f"{operator_path} must be a regular file, not a symlink")
    if operator_path.is_file():
        try:
            same_as_example = os.path.samefile(operator_path, example_path)
        except OSError:
            same_as_example = False
        if same_as_example:
            raise ConfigLoadError(
                f"{AUTONOMY_FILE_NAME} must not be the same file as {AUTONOMY_EXAMPLE_FILE_NAME}"
            )
        return operator_path
    if environment is RuntimeEnvironment.PRODUCTION:
        raise ConfigLoadError(
            f"production requires {config_directory / AUTONOMY_FILE_NAME}; "
            f"{AUTONOMY_EXAMPLE_FILE_NAME} is a template, not production authority"
        )
    return config_directory / AUTONOMY_EXAMPLE_FILE_NAME


def load_config_bundle(
    config_directory: Path,
    *,
    environment: RuntimeEnvironment | None = None,
) -> ConfigurationBundle:
    """Load, reduce authority for the environment, and cross-validate all contracts."""
    if environment is None:
        environment = resolve_runtime_environment()
    product_rules = load_yaml_model(
        config_directory / "product_rules.yaml",
        ProductRulesConfig,
    )
    publishing_ramp = load_yaml_model(
        config_directory / "publishing_ramp.yaml",
        PublishingRampConfig,
    )
    autonomy = apply_environment_safety(
        load_yaml_model(select_autonomy_path(config_directory, environment), AutonomyConfig),
        environment,
    )
    agents = load_yaml_model(config_directory / "agents.yaml", AgentsConfig)
    workflows = load_yaml_model(config_directory / "workflows.yaml", WorkflowsConfig)
    telemetry = load_yaml_model(config_directory / "telemetry.yaml", TelemetryConfig)
    return validate_config_bundle(
        product_rules=product_rules,
        publishing_ramp=publishing_ramp,
        autonomy=autonomy,
        agents=agents,
        workflows=workflows,
        telemetry=telemetry,
    )
