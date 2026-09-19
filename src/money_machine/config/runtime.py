"""Runtime settings for the database, services, providers, storage and artifacts.

Session 01 owns the playbook-authority configuration in ``settings.py`` (product rules,
publication ramp, standing autonomy, agents, workflows, telemetry). This module adds the
*infrastructure* settings the foundation needs and deliberately does not restate any of
those contracts: YAML remains the runtime authority for them (D-0019, D-0022, addendum 3).

Secret values are wrapped in :class:`Secret` so they cannot be printed, logged, serialised,
or returned by an API. Reading the value requires an explicit call.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Annotated, Final, Literal, Self, cast
from urllib.parse import SplitResult, parse_qsl, quote, unquote, urlsplit, urlunsplit

from pydantic import (
    AfterValidator,
    Field,
    GetCoreSchemaHandler,
    StringConstraints,
    model_validator,
)
from pydantic_core import core_schema

from money_machine.config.settings import ConfigModel, RuntimeEnvironment
from money_machine.domain.models._base import NonEmptyStr, PositiveInt

REDACTED: Final = "***REDACTED***"
"""The only representation a secret ever has outside an explicit reveal."""

ENVIRONMENT_PREFIX: Final = "MONEY_MACHINE_"


class Secret:
    """A string that refuses to appear in ``repr``, ``str``, logs, or JSON.

    ``pydantic`` serialises this type through :meth:`__get_pydantic_core_schema__` as the
    redaction marker, so a settings object can be dumped into a log line or an API response
    without leaking. The value is reachable only through :meth:`reveal`.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        """Return the secret value. Call this only where the value is actually used."""
        return self._value

    def __bool__(self) -> bool:
        return bool(self._value)

    def __len__(self) -> int:
        return len(self._value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and other._value == self._value

    def __hash__(self) -> int:
        return hash(("money_machine.Secret", self._value))

    def __repr__(self) -> str:
        return REDACTED

    def __str__(self) -> str:
        return REDACTED

    def __format__(self, format_spec: str) -> str:
        del format_spec
        return REDACTED

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: object,
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        """Validate from a string or an existing secret; always serialise as the marker."""
        del source_type, handler
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda _: REDACTED,
                return_schema=core_schema.str_schema(),
                when_used="always",
            ),
        )

    @classmethod
    def _validate(cls, value: object) -> Secret:
        if isinstance(value, Secret):
            return value
        if type(value) is str:
            return cls(value)
        raise ValueError("secret must be a string")


def _reject_blank_secret(value: Secret) -> Secret:
    if not value.reveal().strip():
        raise ValueError("secret must not be blank")
    return value


SecretValue = Annotated[Secret, AfterValidator(_reject_blank_secret)]
OptionalSecret = SecretValue | None


def _known_async_driver(value: str) -> str:
    scheme = urlsplit(value).scheme
    if scheme != "postgresql+asyncpg":
        raise ValueError("database URL must use the postgresql+asyncpg driver")
    return value


DatabaseUrl = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1),
    AfterValidator(_known_async_driver),
]


SECRET_QUERY_KEYS: Final = frozenset({"password", "sslpassword", "sslkey", "passfile"})
"""Query parameters a driver honours as credentials. They never survive into a stored URL."""


def _split_query(query: str) -> tuple[str, dict[str, str]]:
    """Separate a query string into its safe part and its credential-bearing part."""
    safe: list[str] = []
    secrets: dict[str, str] = {}
    for key, value in parse_qsl(query, keep_blank_values=True):
        if key.lower() in SECRET_QUERY_KEYS:
            secrets[key] = value
        else:
            safe.append(f"{quote(key, safe='')}={quote(value, safe='')}")
    return "&".join(safe), secrets


def _rebuild_url(
    parts: SplitResult,
    *,
    credential: str | None,
    query: str | None = None,
) -> str:
    """Reassemble a URL with, or deliberately without, a password."""
    user = quote(unquote(parts.username or ""), safe="")
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    port = f":{parts.port}" if parts.port else ""
    if not user:
        authority = f"{host}{port}"
    elif credential is None:
        authority = f"{user}@{host}{port}"
    else:
        authority = f"{user}:{quote(credential, safe='')}@{host}{port}"
    return urlunsplit(
        (
            parts.scheme,
            authority,
            parts.path,
            parts.query if query is None else query,
            parts.fragment,
        )
    )


class DatabaseSettings(ConfigModel):
    """Connection and pooling contract for the single canonical PostgreSQL database.

    A password is never held in ``url``. A full DSN may be supplied, as Compose does, and
    validation moves any embedded password into ``password`` so the credential lives in a
    :class:`Secret` and cannot reappear in a repr, a dump, or a log line. ``dsn`` is the
    only place the two are recombined.
    """

    url: DatabaseUrl
    password: OptionalSecret = None
    pool_size: PositiveInt = 5
    max_overflow: int = Field(default=5, strict=True, ge=0)
    pool_timeout_seconds: PositiveInt = 30
    command_timeout_seconds: PositiveInt = 30
    statement_cache_size: int = Field(default=0, strict=True, ge=0)
    echo_sql: Literal[False] = False

    @model_validator(mode="before")
    @classmethod
    def extract_embedded_credentials(cls, data: object) -> object:
        """Move any credential out of the URL and keep it as a secret.

        Both carriers are handled: the userinfo password and credential-bearing query
        parameters such as ``?password=``, which a driver honours and which would otherwise
        survive into ``safe_url``, logs and API responses.
        """
        if not isinstance(data, dict):
            return data
        values: dict[str, object] = dict(cast(dict[str, object], data))
        url = values.get("url")
        if not isinstance(url, str):
            return values
        parts = urlsplit(url)
        safe_query, query_secrets = _split_query(parts.query)
        embedded = None if parts.password is None else unquote(parts.password)
        if embedded is None and not query_secrets:
            return values

        candidate = embedded
        if candidate is None:
            candidate = next(iter(query_secrets.values())) or None
        if candidate is not None:
            existing = values.get("password")
            if existing is not None:
                existing_value = (
                    existing.reveal() if isinstance(existing, Secret) else str(existing)
                )
                if existing_value != candidate:
                    raise ValueError("database password is supplied twice with different values")
            values["password"] = Secret(candidate)
        values["url"] = _rebuild_url(parts, credential=None, query=safe_query)
        return values

    @property
    def safe_url(self) -> str:
        """The connection string as stored: it contains no credential."""
        return self.url

    def dsn(self) -> str:
        """The connection string with the password applied, for the driver only."""
        if self.password is None:
            return self.url
        return _rebuild_url(urlsplit(self.url), credential=self.password.reveal())

    @property
    def redacted_query_keys(self) -> tuple[str, ...]:
        """Credential-bearing query keys this type removes from a stored URL."""
        return tuple(sorted(SECRET_QUERY_KEYS))


class ApiSettings(ConfigModel):
    """Operator API surface. Readiness is proved against the database, never assumed."""

    host: NonEmptyStr = "127.0.0.1"
    port: PositiveInt = 8000
    auth_token: OptionalSecret = None
    readiness_timeout_seconds: PositiveInt = 5


class WorkerSettings(ConfigModel):
    """Worker process bounds. Exit 78 stub; job claiming commissioned in Session 04."""

    poll_interval_seconds: PositiveInt = 5
    lease_seconds: PositiveInt = 300
    max_concurrent_jobs: PositiveInt = 1
    commissioned: Literal[False] = False


class SchedulerSettings(ConfigModel):
    """Scheduler process bounds. Exit 78 stub; trigger firing commissioned in Session 04."""

    tick_interval_seconds: PositiveInt = 60
    timezone: Literal["UTC"] = "UTC"
    commissioned: Literal[False] = False


class ProviderSettings(ConfigModel):
    """One external provider's credential presence and effect mode.

    Presence is a boolean fact. Nothing here reads a credential value, opens a browser
    profile, or performs a network call (D-0016, addendum 5).
    """

    name: NonEmptyStr
    api_key: OptionalSecret = None
    effect_mode: Literal["simulation", "draft", "live"] = "simulation"
    commissioned: Literal[False] = False

    @property
    def configured(self) -> bool:
        """Whether a credential is present, without revealing it."""
        return self.api_key is not None

    @model_validator(mode="after")
    def validate_effect_mode(self) -> Self:
        if self.effect_mode != "simulation" and not self.configured:
            raise ValueError(f"{self.name} cannot leave simulation without a credential")
        return self


class StorageSettings(ConfigModel):
    """Artifact and runtime paths. All paths stay inside the denied runtime tree."""

    artifact_root: NonEmptyStr = "runtime/artifacts"
    screenshot_root: NonEmptyStr = "runtime/screenshots"
    receipt_root: NonEmptyStr = "runtime/receipts"
    browser_profile_root: NonEmptyStr = "runtime/browser-profiles"
    temp_root: NonEmptyStr = "runtime/temp"

    @model_validator(mode="after")
    def validate_paths(self) -> Self:
        roots = (
            self.artifact_root,
            self.screenshot_root,
            self.receipt_root,
            self.browser_profile_root,
            self.temp_root,
        )
        for root in roots:
            if root.startswith("/") or root.startswith("~"):
                raise ValueError("storage paths must be repository-relative")
            if any(segment in {".", ".."} for segment in root.split("/")):
                raise ValueError("storage paths must not traverse")
            if not root.startswith("runtime/"):
                raise ValueError("storage paths must stay under runtime/")
        if len(set(roots)) != len(roots):
            raise ValueError("storage paths must be distinct")
        return self


class RuntimeSettings(ConfigModel):
    """Complete infrastructure settings for one process."""

    environment: RuntimeEnvironment
    database: DatabaseSettings
    api: ApiSettings = ApiSettings()
    worker: WorkerSettings = WorkerSettings()
    scheduler: SchedulerSettings = SchedulerSettings()
    storage: StorageSettings = StorageSettings()
    providers: tuple[ProviderSettings, ...] = ()

    @model_validator(mode="after")
    def validate_providers(self) -> Self:
        names = tuple(provider.name for provider in self.providers)
        if len(set(names)) != len(names):
            raise ValueError("provider names must be unique")
        if self.environment is not RuntimeEnvironment.PRODUCTION and any(
            provider.effect_mode != "simulation" for provider in self.providers
        ):
            raise ValueError("development and test force simulation for every provider")
        return self

    def provider(self, name: str) -> ProviderSettings | None:
        """Look up one provider's settings by name."""
        for provider in self.providers:
            if provider.name == name:
                return provider
        return None


PROVIDER_NAMES: Final = ("llm", "etsy", "notion", "composio", "posthog")
"""Providers whose credentials this system may hold. Order is the reporting order."""

_MISSING_DATABASE_URL: Final = (
    f"{ENVIRONMENT_PREFIX}DATABASE_URL is required; copy .env.example and set it"
)


class RuntimeSettingsError(ValueError):
    """Raised when required runtime settings are missing or contradictory."""


def _optional(environ: Mapping[str, str], name: str, *, strip: bool = True) -> str | None:
    value = environ.get(f"{ENVIRONMENT_PREFIX}{name}") or environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return (stripped if strip else value) if stripped else None


def _optional_secret(environ: Mapping[str, str], name: str, *, strip: bool = True) -> Secret | None:
    value = _optional(environ, name, strip=strip)
    return None if value is None else Secret(value)


def load_runtime_settings(
    environ: Mapping[str, str] | None = None,
    *,
    environment: RuntimeEnvironment | None = None,
) -> RuntimeSettings:
    """Build runtime settings from the process environment, failing closed when incomplete.

    Production requires an explicit database URL. Development and test fall back to the
    Compose development DSN so the foundation is runnable, and force every provider to
    simulation regardless of which credentials happen to exist on the machine.
    """
    from money_machine.config.loader import ConfigLoadError, resolve_runtime_environment

    source = os.environ if environ is None else environ
    if environment is None:
        try:
            environment = resolve_runtime_environment(source)
        except ConfigLoadError as error:
            raise RuntimeSettingsError(str(error)) from error

    url = _optional(source, "DATABASE_URL")
    if url is None:
        if environment is RuntimeEnvironment.PRODUCTION:
            raise RuntimeSettingsError(_MISSING_DATABASE_URL)
        url = "postgresql+asyncpg://money_machine@127.0.0.1:5432/money_machine"

    providers = tuple(
        ProviderSettings(
            name=name,
            api_key=_optional_secret(source, f"{name.upper()}_API_KEY"),
            effect_mode="simulation",
        )
        for name in PROVIDER_NAMES
    )
    try:
        database = DatabaseSettings(
            url=url,
            password=_optional_secret(source, "DATABASE_PASSWORD", strip=False),
        )
        if database.password is None:
            database = DatabaseSettings(
                url=database.url,
                password=_optional_secret(source, "DATABASE_PASSWORD_FALLBACK", strip=False),
            )
        return RuntimeSettings(
            environment=environment,
            database=database,
            api=ApiSettings(auth_token=_optional_secret(source, "API_AUTH_TOKEN")),
            providers=providers,
        )
    except ValueError as error:
        raise RuntimeSettingsError(f"invalid runtime settings: {error}") from error
