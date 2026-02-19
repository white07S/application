"""Add reverse index and check constraint to ai_controls_similar_controls.

The reverse index (similar_control_id WHERE tx_to IS NULL) is required for
the incremental similarity DELETE phase: finding all controls that currently
point to a changed control.

Revision ID: 006
Revises: 005
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reverse lookup index for incremental similarity DELETE phase
    op.create_index(
        "ix_similar_controls_reverse_current",
        "ai_controls_similar_controls",
        ["similar_control_id"],
        postgresql_where=sa.text("tx_to IS NULL"),
    )

    # Temporal ordering constraint (matches other tables)
    op.create_check_constraint(
        "chk_tx_order_similar_controls",
        "ai_controls_similar_controls",
        "tx_to IS NULL OR tx_to > tx_from",
    )


def downgrade() -> None:
    op.drop_constraint("chk_tx_order_similar_controls", "ai_controls_similar_controls")
    op.drop_index("ix_similar_controls_reverse_current", "ai_controls_similar_controls")
