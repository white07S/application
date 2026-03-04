"""Add src_orgs_meta_source_date table for tracking context provider freshness.

Stores the source-data date from *_date.json files so the UI can display
last_updated_as_of and warn when data is stale (>1 month).

Revision ID: 017
Revises: 016
Create Date: 2026-03-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "src_orgs_meta_source_date",
        sa.Column("tree", sa.Text(), primary_key=True),
        sa.Column("source_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "tree IN ('function', 'location', 'consolidated')",
            name="ck_meta_source_date_tree",
        ),
    )


def downgrade() -> None:
    op.drop_table("src_orgs_meta_source_date")
