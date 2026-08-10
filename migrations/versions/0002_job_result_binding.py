"""bind each completed job to its exact durable result"""

import hashlib
import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _canonical_sha256(value: dict[str, str]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def upgrade() -> None:
    op.add_column("jobs", sa.Column("result_type", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("result_id", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("result_sha256", sa.Text(), nullable=True))
    bindings = (
        (
            "ADMIT_RESEARCH_PACKET",
            "research_packets",
            "packet_id",
            "research_packet_admitted",
        ),
        (
            "QUALIFY_CANDIDATES",
            "candidate_shortlists",
            "shortlist_id",
            "candidate_shortlisted",
        ),
        (
            "CREATE_PRODUCT_SPEC",
            "product_specs",
            "product_spec_id",
            "product_spec_created",
        ),
        (
            "CHECK_CATALOGUE_DEDUPE",
            "dedupe_results",
            "dedupe_result_id",
            "dedupe_passed",
        ),
        ("BUILD_PRODUCT", "build_results", "build_id", "product_built"),
        (
            "RUN_PRODUCT_QA",
            "product_qa_results",
            "product_qa_result_id",
            "product_qa_passed",
        ),
        (
            "CREATE_LISTING_PACKAGE",
            "listing_packages",
            "listing_package_id",
            "listing_package_created",
        ),
        (
            "RUN_PREFLIGHT",
            "preflight_results",
            "preflight_result_id",
            "draft_ready",
        ),
    )
    for job_type, result_table, identity_field, _event_name in bindings:
        op.execute(
            sa.text(
                f"""
                UPDATE jobs AS job
                SET result_type = :result_type,
                    result_id = result.{identity_field},
                    result_sha256 = result.payload_sha256
                FROM domain_events AS event
                JOIN {result_table} AS result
                  ON result.{identity_field} = COALESCE(
                      event.payload -> 'payload' ->> :identity_field,
                      event.payload -> 'payload' ->> 'result_id'
                  )
                WHERE job.job_id = event.job_id
                  AND job.job_type = :job_type
                  AND job.state = 'SUCCEEDED'
                  AND job.result_type IS NULL
                """
            ).bindparams(
                result_type=result_table,
                identity_field=identity_field,
                job_type=job_type,
            )
        )
    connection = op.get_bind()
    for job_type, _result_table, identity_field, event_name in bindings:
        rows = connection.execute(
            sa.text(
                """
                SELECT event.event_id,
                       event.payload AS event_envelope,
                       job.result_type,
                       job.result_id,
                       job.result_sha256
                FROM jobs AS job
                JOIN domain_events AS event ON event.job_id = job.job_id
                WHERE job.job_type = :job_type
                  AND job.state = 'SUCCEEDED'
                  AND event.name = :event_name
                """
            ),
            {"job_type": job_type, "event_name": event_name},
        ).mappings()
        for row in rows:
            envelope: dict[str, Any] = dict(row.event_envelope)
            event_payload = {
                identity_field: row.result_id,
                "result_type": row.result_type,
                "result_id": row.result_id,
                "result_sha256": row.result_sha256,
            }
            event_hash = _canonical_sha256(event_payload)
            envelope["payload"] = event_payload
            envelope["payload_sha256"] = event_hash
            connection.execute(
                sa.text(
                    """
                    UPDATE domain_events
                    SET payload = CAST(:event_envelope AS jsonb),
                        payload_sha256 = :event_hash
                    WHERE event_id = :event_id
                    """
                ),
                {
                    "event_envelope": json.dumps(envelope),
                    "event_hash": event_hash,
                    "event_id": row.event_id,
                },
            )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM jobs
                WHERE state = 'SUCCEEDED'
                  AND (result_type IS NULL OR result_id IS NULL OR result_sha256 IS NULL)
            ) THEN
                RAISE EXCEPTION 'cannot bind every completed job to an exact durable result';
            END IF;
        END
        $$
        """
    )
    op.create_check_constraint(
        "ck_jobs_result_binding",
        "jobs",
        "(result_type IS NULL AND result_id IS NULL AND result_sha256 IS NULL) OR "
        "(result_type IS NOT NULL AND result_id IS NOT NULL AND result_sha256 IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_jobs_result_hash",
        "jobs",
        "result_sha256 IS NULL OR char_length(result_sha256) = 64",
    )


def downgrade() -> None:
    op.drop_constraint("ck_jobs_result_hash", "jobs", type_="check")
    op.drop_constraint("ck_jobs_result_binding", "jobs", type_="check")
    op.drop_column("jobs", "result_sha256")
    op.drop_column("jobs", "result_id")
    op.drop_column("jobs", "result_type")
