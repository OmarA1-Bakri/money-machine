"""add jev_evaluations table

Revision ID: a1b2c3d4e5f6
Revises: 9f46f3152a68
Create Date: 2026-09-20 08:30:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9f46f3152a68"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add jev_evaluations table for Jev decision engine evaluation results."""
    op.create_table(
        "jev_evaluations",
        sa.Column("decision_id", sa.UUID(), nullable=True),
        sa.Column("decision_type", sa.String(length=100), nullable=False),
        sa.Column(
            "packet",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "answers",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "derived",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=True,
        ),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("latency_ms >= 0", name=op.f("ck_jev_evaluations_latency_non_negative")),
        sa.CheckConstraint(
            "jsonb_typeof(packet) = 'object'",
            name=op.f("ck_jev_evaluations_packet_is_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(answers) = 'object'",
            name=op.f("ck_jev_evaluations_answers_is_object"),
        ),
        sa.CheckConstraint(
            "derived IS NULL OR jsonb_typeof(derived) = 'object'",
            name=op.f("ck_jev_evaluations_derived_is_object_or_null"),
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["decisions.id"],
            name=op.f("fk_jev_evaluations_decision_id_decisions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jev_evaluations")),
    )
    op.create_index(
        op.f("ix_jev_evaluations_decision_id"),
        "jev_evaluations",
        ["decision_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove jev_evaluations table."""
    op.drop_index(op.f("ix_jev_evaluations_decision_id"), table_name="jev_evaluations")
    op.drop_table("jev_evaluations")
