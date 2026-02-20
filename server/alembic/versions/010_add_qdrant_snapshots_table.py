"""Add qdrant_snapshots table and expand job types.

Revision ID: 010
Revises: 009
Create Date: 2026-02-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create qdrant_snapshots table
    op.create_table(
        "qdrant_snapshots",
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("collection_name", sa.String(length=255), nullable=False),
        sa.Column("qdrant_snapshot_name", sa.String(length=255), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("points_count", sa.BigInteger(), nullable=False),
        sa.Column("vectors_count", sa.BigInteger(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("restored_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_restored_by", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_qdrant_snapshots_created_at", "qdrant_snapshots", ["created_at"])
    op.create_index("idx_qdrant_snapshots_status", "qdrant_snapshots", ["status"])
    op.create_index("idx_qdrant_snapshots_collection", "qdrant_snapshots", ["collection_name"])

    # Expand processing_jobs job_type to include qdrant snapshot types
    op.execute("ALTER TABLE processing_jobs DROP CONSTRAINT IF EXISTS processing_jobs_job_type_check")
    op.create_check_constraint(
        "processing_jobs_job_type_check",
        "processing_jobs",
        "job_type IN ('ingestion', 'snapshot_creation', 'snapshot_restore', "
        "'qdrant_snapshot_creation', 'qdrant_snapshot_restore')",
    )


def downgrade() -> None:
    # Restore old job_type constraint
    op.execute("ALTER TABLE processing_jobs DROP CONSTRAINT IF EXISTS processing_jobs_job_type_check")
    op.create_check_constraint(
        "processing_jobs_job_type_check",
        "processing_jobs",
        "job_type IN ('ingestion', 'snapshot_creation', 'snapshot_restore')",
    )

    op.drop_index("idx_qdrant_snapshots_collection", table_name="qdrant_snapshots")
    op.drop_index("idx_qdrant_snapshots_status", table_name="qdrant_snapshots")
    op.drop_index("idx_qdrant_snapshots_created_at", table_name="qdrant_snapshots")
    op.drop_table("qdrant_snapshots")
