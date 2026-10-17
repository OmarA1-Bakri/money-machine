"""In-memory backup and restore for one fixture shop.

The snapshot copies a workflow, a job, a product, a listing, an incident,
the artifact hash, and the simulation config. A second restore keeps those
rows. A PostgreSQL backup is refused.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid5

from money_machine.domain.enums import IncidentType, JobStatus, ProductLifecycleState

BackupMode = Literal["fixture", "postgres"]
_NAMESPACE = UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")
_ARTIFACT_BODY = b"Household reset planner delivery"
_CONFIG_VERSION = "session-13-fixture"


class BackupRefusal(ValueError):
    """The snapshot is incomplete, conflicting, or would touch a live database."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class FixtureWorkflow:
    """One workflow row copied by the snapshot."""

    workflow_id: str
    workflow_type: str
    product_state: ProductLifecycleState


@dataclass(frozen=True, slots=True)
class FixtureJob:
    """One job row. The idempotency key is part of the restored identity."""

    job_id: str
    workflow_id: str
    job_type: str
    status: JobStatus
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class FixtureProduct:
    """One product row."""

    product_id: str
    workflow_id: str
    identity: str
    working_title: str


@dataclass(frozen=True, slots=True)
class FixtureListing:
    """One listing row. The restored state stays a draft."""

    listing_id: str
    product_id: str
    listing_state: str
    title: str


@dataclass(frozen=True, slots=True)
class FixtureIncident:
    """One incident row."""

    incident_id: str
    workflow_id: str
    incident_type: IncidentType
    incident_state: str


@dataclass(frozen=True, slots=True)
class FixtureArtifact:
    """Artifact storage metadata. The bytes themselves are not stored."""

    artifact_id: str
    workflow_id: str
    name: str
    sha256: str


@dataclass(frozen=True, slots=True)
class FixtureConfig:
    """The configuration the restore must bring back. Live mode is refused."""

    config_version: str
    publishing_mode: str


@dataclass(frozen=True, slots=True)
class FixtureSnapshot:
    """A copy of the fixture rows. It does not keep a reference to the source."""

    workflows: tuple[FixtureWorkflow, ...]
    jobs: tuple[FixtureJob, ...]
    products: tuple[FixtureProduct, ...]
    listings: tuple[FixtureListing, ...]
    incidents: tuple[FixtureIncident, ...]
    artifacts: tuple[FixtureArtifact, ...]
    config: FixtureConfig


@dataclass(frozen=True, slots=True)
class RestoreResult:
    """How many new rows a restore inserted. A repeat inserts none."""

    inserted: int
    workflow_count: int
    job_count: int
    product_count: int
    listing_count: int
    incident_count: int
    artifact_count: int


class FixtureStore:
    """The in-memory shop a snapshot is taken from and restored into."""

    def __init__(self) -> None:
        self.workflows: dict[str, FixtureWorkflow] = {}
        self.jobs: dict[str, FixtureJob] = {}
        self.products: dict[str, FixtureProduct] = {}
        self.listings: dict[str, FixtureListing] = {}
        self.incidents: dict[str, FixtureIncident] = {}
        self.artifacts: dict[str, FixtureArtifact] = {}
        self.config: FixtureConfig | None = None

    def add_workflow(self, row: FixtureWorkflow) -> None:
        _put(self.workflows, row.workflow_id, row, "duplicate_workflow")

    def add_job(self, row: FixtureJob) -> None:
        _put(self.jobs, row.job_id, row, "duplicate_job")

    def add_product(self, row: FixtureProduct) -> None:
        _put(self.products, row.product_id, row, "duplicate_product")

    def add_listing(self, row: FixtureListing) -> None:
        if row.listing_state != "DRAFT":
            raise BackupRefusal("listing_state")
        _put(self.listings, row.listing_id, row, "duplicate_listing")

    def add_incident(self, row: FixtureIncident) -> None:
        _put(self.incidents, row.incident_id, row, "duplicate_incident")

    def add_artifact(self, row: FixtureArtifact) -> None:
        _put(self.artifacts, row.artifact_id, row, "duplicate_artifact")

    def set_config(self, config: FixtureConfig) -> None:
        if config.publishing_mode != "simulation":
            raise BackupRefusal("live_config")
        if config.config_version == "":
            raise BackupRefusal("config")
        self.config = config

    def clear(self) -> None:
        """Drop every row. A snapshot taken earlier is unaffected."""
        self.workflows.clear()
        self.jobs.clear()
        self.products.clear()
        self.listings.clear()
        self.incidents.clear()
        self.artifacts.clear()
        self.config = None


def artifact_sha256(body: bytes) -> str:
    """Hash artifact bytes. An empty body is not storage metadata."""
    if body == b"":
        raise BackupRefusal("artifact")
    return hashlib.sha256(body).hexdigest()


def take_snapshot(store: FixtureStore) -> FixtureSnapshot:
    """Copy the store. The copy is refused when any required row is missing."""
    config = store.config
    if (
        config is None
        or not store.workflows
        or not store.jobs
        or not store.products
        or not store.listings
        or not store.incidents
        or not store.artifacts
    ):
        raise BackupRefusal("incomplete")
    return FixtureSnapshot(
        workflows=_rows(store.workflows),
        jobs=_rows(store.jobs),
        products=_rows(store.products),
        listings=_rows(store.listings),
        incidents=_rows(store.incidents),
        artifacts=_rows(store.artifacts),
        config=config,
    )


def restore_snapshot(target: FixtureStore, snapshot: FixtureSnapshot) -> RestoreResult:
    """Insert missing rows. An equal row already present is not inserted again."""
    inserted = 0
    inserted += _restore(
        target.workflows, snapshot.workflows, lambda row: row.workflow_id, target.add_workflow
    )
    inserted += _restore(target.jobs, snapshot.jobs, lambda row: row.job_id, target.add_job)
    inserted += _restore(
        target.products, snapshot.products, lambda row: row.product_id, target.add_product
    )
    inserted += _restore(
        target.listings, snapshot.listings, lambda row: row.listing_id, target.add_listing
    )
    inserted += _restore(
        target.incidents, snapshot.incidents, lambda row: row.incident_id, target.add_incident
    )
    inserted += _restore(
        target.artifacts, snapshot.artifacts, lambda row: row.artifact_id, target.add_artifact
    )
    if target.config is None:
        target.set_config(snapshot.config)
        inserted += 1
    elif target.config != snapshot.config:
        raise BackupRefusal("config_conflict")
    return RestoreResult(
        inserted=inserted,
        workflow_count=len(target.workflows),
        job_count=len(target.jobs),
        product_count=len(target.products),
        listing_count=len(target.listings),
        incident_count=len(target.incidents),
        artifact_count=len(target.artifacts),
    )


def sample_store() -> FixtureStore:
    """One linked fixture shop. The listing stays a draft."""
    workflow_id = _stable_id("workflow")
    job_id = _stable_id("job")
    product_id = _stable_id("product")
    store = FixtureStore()
    store.add_workflow(
        FixtureWorkflow(workflow_id, "product_experiment", ProductLifecycleState.SPEC_READY)
    )
    store.add_job(FixtureJob(job_id, workflow_id, "BuildProductJob", JobStatus.READY, "build-1"))
    store.add_product(
        FixtureProduct(product_id, workflow_id, "household-reset", "Household reset planner")
    )
    store.add_listing(FixtureListing(_stable_id("listing"), product_id, "DRAFT", "Planner"))
    store.add_incident(
        FixtureIncident(
            _stable_id("incident"),
            workflow_id,
            IncidentType.BROKEN_LINK,
            "OPEN",
        )
    )
    store.add_artifact(
        FixtureArtifact(
            _stable_id("artifact"),
            workflow_id,
            "delivery-readme",
            artifact_sha256(_ARTIFACT_BODY),
        )
    )
    store.set_config(FixtureConfig(_CONFIG_VERSION, "simulation"))
    return store


def backup(*, mode: BackupMode) -> FixtureSnapshot:
    """Take the fixture snapshot. ``postgres`` is the refused live backup."""
    if mode == "postgres":
        raise BackupRefusal("live_postgres")
    if mode != "fixture":
        raise BackupRefusal("mode")
    return take_snapshot(sample_store())


def _stable_id(name: str) -> str:
    return str(uuid5(_NAMESPACE, f"https://money-machine.invalid/backup/{name}"))


def _rows[T](rows: dict[str, T]) -> tuple[T, ...]:
    return tuple(rows[key] for key in sorted(rows))


def _put[T](store: dict[str, T], key: str, row: T, code: str) -> None:
    if key == "":
        raise BackupRefusal("identity")
    if key in store:
        raise BackupRefusal(code)
    store[key] = row


def _restore[T](
    existing: dict[str, T],
    rows: tuple[T, ...],
    identity: Callable[[T], str],
    add: Callable[[T], None],
) -> int:
    if not rows:
        raise BackupRefusal("incomplete")
    inserted = 0
    for row in rows:
        key = identity(row)
        current = existing.get(key)
        if current is None:
            add(row)
            inserted += 1
            continue
        if current != row:
            raise BackupRefusal("conflict")
    return inserted
