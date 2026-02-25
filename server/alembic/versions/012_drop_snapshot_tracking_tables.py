"""Drop postgres_snapshots, qdrant_snapshots, and snapshot_schedules tables.

Snapshot metadata is now stored entirely on disk (metadata.json).
These PG tracking tables are no longer used.

Merges the two migration branches (011 and f4c2e1b8d9aa).

Revision ID: 012
Revises: 011, f4c2e1b8d9aa
Create Date: 2026-02-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, Sequence[str], None] = ("011", "f4c2e1b8d9aa")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop indexes first, then tables (order matters for FK)
    op.drop_index("idx_qdrant_snapshots_collection", table_name="qdrant_snapshots", if_exists=True)
    op.drop_index("idx_qdrant_snapshots_status", table_name="qdrant_snapshots", if_exists=True)
    op.drop_index("idx_qdrant_snapshots_created_at", table_name="qdrant_snapshots", if_exists=True)
    op.drop_table("qdrant_snapshots")

    op.drop_index("idx_snapshots_status", table_name="postgres_snapshots", if_exists=True)
    op.drop_index("idx_snapshots_schedule_id", table_name="postgres_snapshots", if_exists=True)
    op.drop_index("idx_snapshots_created_at", table_name="postgres_snapshots", if_exists=True)
    op.drop_table("postgres_snapshots")

    op.drop_index("idx_schedules_next_run_at", table_name="snapshot_schedules", if_exists=True)
    op.drop_index("idx_schedules_is_active", table_name="snapshot_schedules", if_exists=True)
    op.drop_table("snapshot_schedules")


def downgrade() -> None:
    # Re-create tables if rolling back
    op.create_table(
        "snapshot_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("cron_expression", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("max_snapshots", sa.Integer(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_snapshot_id", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("idx_schedules_is_active", "snapshot_schedules", ["is_active"])
    op.create_index("idx_schedules_next_run_at", "snapshot_schedules", ["next_run_at"])

    op.create_table(
        "postgres_snapshots",
        sa.Column("id", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("alembic_version", sa.String(length=32), nullable=False),
        sa.Column("table_count", sa.Integer(), nullable=False),
        sa.Column("total_records", sa.BigInteger(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("restored_count", sa.Integer(), nullable=False),
        sa.Column("last_restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_restored_by", sa.String(length=255), nullable=True),
        sa.Column("is_scheduled", sa.Boolean(), nullable=False),
        sa.Column("schedule_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["schedule_id"], ["snapshot_schedules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_snapshots_created_at", "postgres_snapshots", ["created_at"])
    op.create_index("idx_snapshots_schedule_id", "postgres_snapshots", ["schedule_id"])
    op.create_index("idx_snapshots_status", "postgres_snapshots", ["status"])

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
