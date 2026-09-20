"""add agent run observability columns and agent_tool_calls table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-20 10:30:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend agent_runs with observability fields and add agent_tool_calls."""
    op.add_column(
        "agent_runs",
        sa.Column("run_number", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column("agent_runs", sa.Column("model", sa.String(length=100), nullable=True))
    op.add_column("agent_runs", sa.Column("input_hash", sa.String(length=64), nullable=True))
    op.add_column("agent_runs", sa.Column("token_count", sa.Integer(), nullable=True))
    op.add_column(
        "agent_runs",
        sa.Column("cost_usd", sa.Numeric(precision=14, scale=6), nullable=True),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "validation_errors",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        op.f("ck_agent_runs_run_number_positive"),
        "agent_runs",
        "run_number >= 1",
    )
    op.create_check_constraint(
        op.f("ck_agent_runs_input_hash_length"),
        "agent_runs",
        "input_hash IS NULL OR length(input_hash) = 64",
    )
    op.create_check_constraint(
        op.f("ck_agent_runs_token_count_non_negative"),
        "agent_runs",
        "token_count IS NULL OR token_count >= 0",
    )
    op.create_check_constraint(
        op.f("ck_agent_runs_cost_usd_non_negative"),
        "agent_runs",
        "cost_usd IS NULL OR cost_usd >= 0",
    )
    op.create_index(op.f("ix_agent_runs_agent_id"), "agent_runs", ["agent_id"], unique=False)

    op.create_table(
        "agent_tool_calls",
        sa.Column("agent_run_id", sa.UUID(), nullable=False),
        sa.Column("tool_id", sa.String(length=100), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "length(input_hash) = 64", name=op.f("ck_agent_tool_calls_input_hash_length")
        ),
        sa.CheckConstraint(
            "length(output_hash) = 64", name=op.f("ck_agent_tool_calls_output_hash_length")
        ),
        sa.CheckConstraint(
            "duration_ms >= 0", name=op.f("ck_agent_tool_calls_duration_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.id"],
            name=op.f("fk_agent_tool_calls_agent_run_id_agent_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_tool_calls")),
    )
    op.create_index(
        op.f("ix_agent_tool_calls_agent_run_id"),
        "agent_tool_calls",
        ["agent_run_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove agent run observability extensions."""
    op.drop_index(op.f("ix_agent_tool_calls_agent_run_id"), table_name="agent_tool_calls")
    op.drop_table("agent_tool_calls")
    op.drop_index(op.f("ix_agent_runs_agent_id"), table_name="agent_runs")
    op.drop_constraint(op.f("ck_agent_runs_cost_usd_non_negative"), "agent_runs", type_="check")
    op.drop_constraint(op.f("ck_agent_runs_token_count_non_negative"), "agent_runs", type_="check")
    op.drop_constraint(op.f("ck_agent_runs_input_hash_length"), "agent_runs", type_="check")
    op.drop_constraint(op.f("ck_agent_runs_run_number_positive"), "agent_runs", type_="check")
    op.drop_column("agent_runs", "validation_errors")
    op.drop_column("agent_runs", "cost_usd")
    op.drop_column("agent_runs", "token_count")
    op.drop_column("agent_runs", "input_hash")
    op.drop_column("agent_runs", "model")
    op.drop_column("agent_runs", "run_number")
