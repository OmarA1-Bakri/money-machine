"""Persist in-progress executions in the existing agent_runs table.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep terminal history unchanged and permit a truthful active checkpoint."""
    op.add_column("agent_runs", sa.Column("job_attempt", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("lease_owner", sa.String(200), nullable=True))
    op.drop_constraint(op.f("ck_agent_runs_status_taxonomy"), "agent_runs", type_="check")
    op.drop_constraint(op.f("ck_agent_runs_structured_error_required"), "agent_runs", type_="check")
    op.alter_column("agent_runs", "completed_at", nullable=True)
    op.create_check_constraint(
        op.f("ck_agent_runs_status_taxonomy"),
        "agent_runs",
        "status IN ('RUNNING', 'SUCCESS', 'FAILURE', 'BLOCKED', 'UNCERTAIN_EXTERNAL_EFFECT')",
    )
    op.create_check_constraint(
        op.f("ck_agent_runs_structured_error_required"),
        "agent_runs",
        "(status IN ('RUNNING', 'SUCCESS') AND error IS NULL) OR (status NOT IN ('RUNNING', 'SUCCESS') AND error IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_agent_runs_completion_matches_status"),
        "agent_runs",
        "(status = 'RUNNING' AND completed_at IS NULL AND output = '{}'::jsonb AND job_attempt IS NOT NULL AND job_attempt >= 0 AND lease_owner IS NOT NULL AND lease_owner <> '') OR (status <> 'RUNNING' AND completed_at IS NOT NULL)",
    )
    op.create_index(
        "ix_agent_runs_one_running_per_job",
        "agent_runs",
        ["job_id"],
        unique=True,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )


def downgrade() -> None:
    """Refuse to discard unresolved execution history or invent terminal results."""
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM agent_runs WHERE status = 'RUNNING')")
    ):
        raise RuntimeError("cannot downgrade while agent runs remain RUNNING")
    op.drop_index("ix_agent_runs_one_running_per_job", table_name="agent_runs")
    op.drop_constraint(op.f("ck_agent_runs_completion_matches_status"), "agent_runs", type_="check")
    op.drop_constraint(op.f("ck_agent_runs_status_taxonomy"), "agent_runs", type_="check")
    op.drop_constraint(op.f("ck_agent_runs_structured_error_required"), "agent_runs", type_="check")
    op.alter_column("agent_runs", "completed_at", nullable=False)
    op.create_check_constraint(
        op.f("ck_agent_runs_status_taxonomy"),
        "agent_runs",
        "status IN ('SUCCESS', 'FAILURE', 'BLOCKED', 'UNCERTAIN_EXTERNAL_EFFECT')",
    )
    op.create_check_constraint(
        op.f("ck_agent_runs_structured_error_required"),
        "agent_runs",
        "(status = 'SUCCESS' AND error IS NULL) OR (status <> 'SUCCESS' AND error IS NOT NULL)",
    )
    op.drop_column("agent_runs", "lease_owner")
    op.drop_column("agent_runs", "job_attempt")
