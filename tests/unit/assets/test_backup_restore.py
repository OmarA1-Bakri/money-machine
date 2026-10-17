"""A fixture snapshot restores the shop once and refuses a live database backup."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from money_machine.assets.backup_restore import (
    BackupRefusal,
    FixtureConfig,
    FixtureJob,
    FixtureListing,
    FixtureStore,
    artifact_sha256,
    backup,
    restore_snapshot,
    sample_store,
    take_snapshot,
)
from money_machine.domain.enums import JobStatus

_MODULE = Path("src/money_machine/assets/backup_restore.py")
_BODY = b"Household reset planner delivery"


def test_restore_copies_the_five_rows_and_a_second_restore_does_not() -> None:
    source = sample_store()
    snapshot = take_snapshot(source)
    source.clear()
    assert source.workflows == {}
    target = FixtureStore()
    first = restore_snapshot(target, snapshot)
    second = restore_snapshot(target, snapshot)
    assert first.inserted == 7
    assert second.inserted == 0
    assert first.workflow_count == second.workflow_count == 1
    assert first.job_count == second.job_count == 1
    assert first.product_count == second.product_count == 1
    assert first.listing_count == second.listing_count == 1
    assert first.incident_count == second.incident_count == 1
    workflow = snapshot.workflows[0]
    job = snapshot.jobs[0]
    product = snapshot.products[0]
    listing = snapshot.listings[0]
    incident = snapshot.incidents[0]
    assert target.workflows[workflow.workflow_id] == workflow
    assert target.jobs[job.job_id] == job
    assert target.products[product.product_id] == product
    assert target.listings[listing.listing_id] == listing
    assert target.incidents[incident.incident_id] == incident
    assert listing.listing_state == "DRAFT"
    assert job.status is JobStatus.READY
    assert incident.incident_type.value == "BROKEN_LINK"
    assert snapshot.artifacts[0].sha256 == hashlib.sha256(_BODY).hexdigest()
    assert target.config == snapshot.config


def test_a_second_job_is_restored_once() -> None:
    source = sample_store()
    workflow_id = next(iter(source.workflows))
    source.add_job(FixtureJob("job-2", workflow_id, "QaJob", JobStatus.PENDING, "qa-2"))
    snapshot = take_snapshot(source)
    target = FixtureStore()
    assert restore_snapshot(target, snapshot).job_count == 2
    again = restore_snapshot(target, snapshot)
    assert again.inserted == 0
    assert len(target.jobs) == 2


def test_a_changed_row_conflicts_and_an_empty_store_cannot_be_snapshotted() -> None:
    source = sample_store()
    snapshot = take_snapshot(source)
    target = FixtureStore()
    restore_snapshot(target, snapshot)
    listing = snapshot.listings[0]
    target.listings[listing.listing_id] = FixtureListing(
        listing.listing_id, listing.product_id, "DRAFT", "Different title"
    )
    with pytest.raises(BackupRefusal, match="conflict"):
        restore_snapshot(target, snapshot)
    with pytest.raises(BackupRefusal, match="incomplete"):
        take_snapshot(FixtureStore())


def test_live_backup_and_live_config_are_refused() -> None:
    with pytest.raises(BackupRefusal, match="live_postgres"):
        backup(mode="postgres")
    store = FixtureStore()
    with pytest.raises(BackupRefusal, match="live_config"):
        store.set_config(FixtureConfig("session-13-fixture", "live"))
    with pytest.raises(BackupRefusal, match="listing_state"):
        store.add_listing(FixtureListing("listing-live", "product", "PUBLISHED", "Live"))
    with pytest.raises(BackupRefusal, match="artifact"):
        artifact_sha256(b"")
    fixture = backup(mode="fixture")
    assert fixture.listings[0].listing_state == "DRAFT"
    assert fixture.config.publishing_mode == "simulation"


def test_module_imports_no_database_driver() -> None:
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    folded = " ".join(imported)
    for token in ("socket", "httpx", "urllib", "requests", "psycopg", "asyncpg", "sqlalchemy"):
        assert token not in folded
