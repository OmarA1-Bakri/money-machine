"""bind each completed job to its exact durable result"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("result_type", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("result_id", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("result_sha256", sa.Text(), nullable=True))
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
