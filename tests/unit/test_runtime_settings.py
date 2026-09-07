"""Runtime settings: fail-closed loading, mode rejection and secret redaction."""

from __future__ import annotations

import json
import logging

import pytest
from pydantic import ValidationError

from money_machine.config.loader import ConfigLoadError
from money_machine.config.runtime import (
    REDACTED,
    ApiSettings,
    DatabaseSettings,
    ProviderSettings,
    RuntimeSettings,
    RuntimeSettingsError,
    Secret,
    StorageSettings,
    load_runtime_settings,
)
from money_machine.config.settings import RuntimeEnvironment

SECRET_VALUE = "correct-horse-battery-staple"
DSN = "postgresql+asyncpg://user:hunter2@db:5432/money_machine"


def test_secret_never_renders_its_value() -> None:
    """A secret cannot leak through repr, str, format, or JSON serialisation."""
    secret = Secret(SECRET_VALUE)

    assert repr(secret) == REDACTED
    assert str(secret) == REDACTED
    assert f"{secret}" == REDACTED
    assert format(secret, ">40") == REDACTED
    assert SECRET_VALUE not in repr(secret) + str(secret) + f"{secret}"
    assert secret.reveal() == SECRET_VALUE
    assert bool(secret) and len(secret) == len(SECRET_VALUE)
    assert Secret(SECRET_VALUE) == secret


def test_secret_is_redacted_in_model_dumps_and_json() -> None:
    """Dumping settings into a log line or a response body cannot leak a credential."""
    settings = ApiSettings(auth_token=Secret(SECRET_VALUE))

    dumped = settings.model_dump()
    as_json = settings.model_dump_json()

    assert dumped["auth_token"] == REDACTED
    assert SECRET_VALUE not in json.dumps(dumped)
    assert SECRET_VALUE not in as_json
    assert json.loads(as_json)["auth_token"] == REDACTED


def test_database_password_is_extracted_out_of_the_url() -> None:
    """A supplied DSN keeps working, but the stored URL holds no credential at all."""
    settings = DatabaseSettings(url=DSN)

    assert settings.safe_url == "postgresql+asyncpg://user@db:5432/money_machine"
    assert "hunter2" not in settings.safe_url
    assert "hunter2" not in repr(settings)
    assert "hunter2" not in settings.model_dump_json()
    assert settings.password is not None
    assert settings.dsn() == DSN

    separate = DatabaseSettings(url="postgresql+asyncpg://user@db:5432/mm", password=Secret("pw"))
    assert separate.dsn() == "postgresql+asyncpg://user:pw@db:5432/mm"
    assert "pw" not in separate.safe_url
    assert DatabaseSettings(url="postgresql+asyncpg://db:5432/mm").dsn().endswith("/mm")


def test_conflicting_passwords_are_rejected() -> None:
    """A DSN password and an explicit password that disagree is a configuration error."""
    with pytest.raises(ValidationError, match="supplied twice with different values"):
        DatabaseSettings(url=DSN, password=Secret("something-else"))

    agreeing = DatabaseSettings(url=DSN, password=Secret("hunter2"))
    assert agreeing.dsn() == DSN


def test_no_secret_reaches_a_log_record(caplog: pytest.LogCaptureFixture) -> None:
    """Logging a settings object is safe, which is the realistic leak path."""
    settings = DatabaseSettings(url=DSN)
    logger = logging.getLogger("money_machine.test")
    caplog.set_level(logging.INFO, logger="money_machine.test")

    logger.info("settings=%s url=%s dump=%s", settings, settings.safe_url, settings.model_dump())

    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert "hunter2" not in rendered
    assert REDACTED in rendered
    assert settings.password is not None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://user@db/mm", "must use the postgresql\\+asyncpg driver"),
        ("mysql+aiomysql://user@db/mm", "must use the postgresql\\+asyncpg driver"),
        ("", "at least 1 character"),
    ],
)
def test_database_url_must_name_the_async_postgres_driver(url: str, expected: str) -> None:
    """A wrong driver fails at configuration time, not at first query."""
    with pytest.raises(ValidationError, match=expected):
        DatabaseSettings(url=url)


def test_provider_cannot_leave_simulation_without_a_credential() -> None:
    """An effect mode is not authority: it requires a configured credential."""
    with pytest.raises(ValidationError, match="cannot leave simulation without a credential"):
        ProviderSettings(name="etsy", effect_mode="live")

    live = ProviderSettings(name="etsy", api_key=Secret("k"), effect_mode="live")
    assert live.configured is True


@pytest.mark.parametrize("environment", [RuntimeEnvironment.DEVELOPMENT, RuntimeEnvironment.TEST])
def test_development_and_test_force_simulation_for_every_provider(
    environment: RuntimeEnvironment,
) -> None:
    """No machine credential can put a non-production process into a live mode."""
    with pytest.raises(ValidationError, match="force simulation for every provider"):
        RuntimeSettings(
            environment=environment,
            database=DatabaseSettings(url=DSN),
            providers=(ProviderSettings(name="etsy", api_key=Secret("k"), effect_mode="live"),),
        )


def test_duplicate_providers_are_rejected() -> None:
    """A provider is named once, so its authority is unambiguous."""
    with pytest.raises(ValidationError, match="provider names must be unique"):
        RuntimeSettings(
            environment=RuntimeEnvironment.DEVELOPMENT,
            database=DatabaseSettings(url=DSN),
            providers=(ProviderSettings(name="etsy"), ProviderSettings(name="etsy")),
        )


@pytest.mark.parametrize(
    "root",
    ["/etc", "~/artifacts", "runtime/../etc", "artifacts", "runtime/./x"],
)
def test_storage_paths_stay_inside_the_denied_runtime_tree(root: str) -> None:
    """Artifacts cannot be written outside the ignored runtime directory."""
    with pytest.raises(ValidationError):
        StorageSettings(artifact_root=root)


def test_production_requires_an_explicit_database_url() -> None:
    """Production never falls back to a development DSN."""
    with pytest.raises(RuntimeSettingsError, match="DATABASE_URL is required"):
        load_runtime_settings({"APP_ENV": "production"})


def test_development_falls_back_and_forces_simulation() -> None:
    """Development is runnable out of the box and cannot hold live authority."""
    settings = load_runtime_settings({"ETSY_API_KEY": SECRET_VALUE, "NOTION_TOKEN": "t"})

    assert settings.environment is RuntimeEnvironment.DEVELOPMENT
    etsy = settings.provider("etsy")
    assert etsy is not None
    assert etsy.configured is True
    assert etsy.effect_mode == "simulation"
    assert all(provider.effect_mode == "simulation" for provider in settings.providers)
    assert all(not provider.commissioned for provider in settings.providers)
    assert SECRET_VALUE not in repr(settings)


def test_unknown_environment_is_an_error_not_a_silent_default() -> None:
    """An unrecognised environment fails closed rather than guessing."""
    with pytest.raises(RuntimeSettingsError, match="is not a runtime environment"):
        load_runtime_settings({"APP_ENV": "staging"})
    with pytest.raises(ConfigLoadError):
        from money_machine.config.loader import resolve_runtime_environment

        resolve_runtime_environment({"APP_ENV": "prod"})


def test_provider_lookup_reports_unknown_names() -> None:
    """Looking up a provider that is not configured returns nothing."""
    settings = load_runtime_settings({})

    assert settings.provider("nonexistent") is None
    assert {provider.name for provider in settings.providers} == {
        "llm",
        "etsy",
        "notion",
        "composio",
        "posthog",
    }
