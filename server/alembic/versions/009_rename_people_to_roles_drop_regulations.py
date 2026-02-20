"""Rename enrichment 'people' column to 'roles' and drop 'regulations'.

Revision ID: 009
Revises: 008
Create Date: 2026-02-20
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "ai_controls_model_enrichment",
        "people",
        new_column_name="roles",
    )
    op.drop_column("ai_controls_model_enrichment", "regulations")


def downgrade() -> None:
    import sqlalchemy as sa

    op.add_column(
        "ai_controls_model_enrichment",
        sa.Column("regulations", sa.Text(), nullable=True),
    )
    op.alter_column(
        "ai_controls_model_enrichment",
        "roles",
        new_column_name="people",
    )
