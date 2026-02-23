"""Widen processing_jobs.job_type column from VARCHAR(20) to VARCHAR(30).

The qdrant_snapshot_creation (24 chars) and qdrant_snapshot_restore (23 chars)
job types exceed the original VARCHAR(20) limit.

Revision ID: 011
Revises: 010
Create Date: 2026-02-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "processing_jobs",
        "job_type",
        type_=sa.String(30),
        existing_type=sa.String(20),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "processing_jobs",
        "job_type",
        type_=sa.String(20),
        existing_type=sa.String(30),
        existing_nullable=False,
    )
