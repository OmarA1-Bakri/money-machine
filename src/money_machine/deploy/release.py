"""Plan a release without pushing an image or opening PostgreSQL.

The image tag names one commit. A fixture backup is taken before the schema
check. A live postgres backup is refused. An incompatible schema fails.
A destructive path can move forward after that backup and cannot roll back
by image alone.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, assert_never

from money_machine.assets.backup_restore import BackupRefusal, backup

ReleaseMode = Literal["fixture", "postgres"]
_HEX = frozenset("0123456789abcdef")
_DEPLOYMENT_DOC = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "DEPLOYMENT.md"
_BACKUP_SENTENCE = (
    "Back up PostgreSQL and required artifact metadata/bytes before a migration "
    "that cannot be trivially reversed."
)
_CLEANUP_SENTENCE = "Deploy schema-compatible code before destructive cleanup migrations."
_ROLLBACK_SENTENCE = "Roll back application images only when schema compatibility is proved"
_EXIT_SENTENCE = "Exit 78 is not deployment success"


class ReleaseRefusal(ValueError):
    """The plan would push an image, open postgres, or move an incompatible schema."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SchemaRevision:
    """One fixture schema revision. ``parents`` are the revisions it descends from."""

    revision: str
    parents: tuple[str, ...]
    destructive: bool


@dataclass(frozen=True, slots=True)
class ReleasePlan:
    """A release that stays on this machine. ``image_pushed`` stays false."""

    image_tag: str
    commit_sha: str
    backup_planned: bool
    schema_compatible: bool
    rollback_safe: bool
    image_pushed: bool


FIXTURE_REVISIONS: Mapping[str, SchemaRevision] = {
    "base": SchemaRevision(revision="base", parents=(), destructive=False),
    "forward": SchemaRevision(revision="forward", parents=("base",), destructive=False),
    "cleanup": SchemaRevision(revision="cleanup", parents=("forward",), destructive=True),
    "other": SchemaRevision(revision="other", parents=(), destructive=False),
}


def bound_image_tag(commit_sha: str) -> str:
    """Name the image with the commit. This does not create a git tag or push."""
    if len(commit_sha) != 40 or any(character not in _HEX for character in commit_sha):
        raise ReleaseRefusal("unbound_tag")
    return f"money-machine:{commit_sha}"


def plan_release(
    *,
    commit_sha: str,
    image_tag: str,
    mode: ReleaseMode,
    deployed_revision: str,
    candidate_revision: str,
    revisions: Mapping[str, SchemaRevision] | None = None,
    push: bool = False,
    backup_before_migrate: bool = True,
) -> ReleasePlan:
    """Bind ``image_tag`` to ``commit_sha`` and plan the backup before the schema check.

    ``push`` raises ``image_push``. ``mode="postgres"`` raises ``live_postgres``.
    """
    if push:
        raise ReleaseRefusal("image_push")
    if image_tag != bound_image_tag(commit_sha):
        raise ReleaseRefusal("unbound_tag")
    _require_release_document()
    if backup_before_migrate is not True:
        raise ReleaseRefusal("backup_required")
    _take_backup(mode)
    chain = FIXTURE_REVISIONS if revisions is None else revisions
    path = _revision_path(deployed_revision, candidate_revision, chain)
    destructive = any(item.destructive for item in path if item.revision != deployed_revision)
    return ReleasePlan(
        image_tag=image_tag,
        commit_sha=commit_sha,
        backup_planned=True,
        schema_compatible=True,
        rollback_safe=not destructive,
        image_pushed=False,
    )


def rollback_image(plan: ReleasePlan) -> ReleasePlan:
    """Refuse an image-only rollback when the schema path is destructive.

    A safe rollback still does not push an image. Restore the database instead
    when ``rollback_safe`` is false.
    """
    if plan.image_pushed:
        raise ReleaseRefusal("image_push")
    if plan.rollback_safe is not True:
        raise ReleaseRefusal("rollback_refused")
    return ReleasePlan(
        image_tag=plan.image_tag,
        commit_sha=plan.commit_sha,
        backup_planned=plan.backup_planned,
        schema_compatible=plan.schema_compatible,
        rollback_safe=True,
        image_pushed=False,
    )


def _take_backup(mode: ReleaseMode) -> None:
    if mode == "fixture":
        backup(mode="fixture")
        return
    if mode == "postgres":
        try:
            backup(mode="postgres")
        except BackupRefusal as error:
            raise ReleaseRefusal("live_postgres") from error
        raise ReleaseRefusal("live_postgres")
    assert_never(mode)


def _revision_path(
    deployed: str,
    candidate: str,
    revisions: Mapping[str, SchemaRevision],
) -> tuple[SchemaRevision, ...]:
    if deployed == "" or candidate == "":
        raise ReleaseRefusal("incompatible_schema")
    path = _walk(candidate, deployed, revisions, frozenset())
    if path is None:
        raise ReleaseRefusal("incompatible_schema")
    return path


def _walk(
    current: str,
    deployed: str,
    revisions: Mapping[str, SchemaRevision],
    seen: frozenset[str],
) -> tuple[SchemaRevision, ...] | None:
    if current in seen:
        return None
    revision = revisions.get(current)
    if revision is None or revision.revision != current:
        raise ReleaseRefusal("incompatible_schema")
    if current == deployed:
        return (revision,)
    for parent in revision.parents:
        found = _walk(parent, deployed, revisions, seen | {current})
        if found is not None:
            return (revision, *found)
    return None


def _require_release_document() -> None:
    text = _DEPLOYMENT_DOC.read_text(encoding="utf-8")
    required = (_BACKUP_SENTENCE, _CLEANUP_SENTENCE, _ROLLBACK_SENTENCE, _EXIT_SENTENCE)
    if any(sentence not in text for sentence in required):
        raise ReleaseRefusal("deployment_doc")
