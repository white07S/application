"""Expand processing job types for snapshot workflows.

Revision ID: f4c2e1b8d9aa
Revises: e70eef6a4bd3
Create Date: 2026-02-16 13:25:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f4c2e1b8d9aa"
down_revision: Union[str, None] = "e70eef6a4bd3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE processing_jobs DROP CONSTRAINT IF EXISTS processing_jobs_job_type_check")
    op.create_check_constraint(
        "processing_jobs_job_type_check",
        "processing_jobs",
        "job_type IN ('ingestion', 'snapshot_creation', 'snapshot_restore')",
    )


def downgrade() -> None:
    op.execute("ALTER TABLE processing_jobs DROP CONSTRAINT IF EXISTS processing_jobs_job_type_check")
    op.create_check_constraint(
        "processing_jobs_job_type_check",
        "processing_jobs",
        "job_type IN ('ingestion')",
    )
