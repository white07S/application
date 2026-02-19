"""Add ai_controls_similar_controls table for precomputed similarity.

Revision ID: 003
Revises: 002
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_controls_similar_controls",
        sa.Column("ref_control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        sa.Column("similar_control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        sa.Column("rank", sa.SmallInteger, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("feature_scores", JSONB, nullable=True),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_similar_controls_current",
        "ai_controls_similar_controls",
        ["ref_control_id"],
        postgresql_where=sa.text("tx_to IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("ai_controls_similar_controls")
