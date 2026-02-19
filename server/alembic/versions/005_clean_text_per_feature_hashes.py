"""Replace single hash column with 6 per-feature hash columns on clean_text.

Each feature (control_title, control_description, evidence_description,
local_functional_information, control_as_event, control_as_issues) gets its
own hash column so embeddings delta detection can operate per-feature.

Revision ID: 005
Revises: 004
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "ai_controls_model_clean_text"
_FEATURE_HASH_COLUMNS = [
    "hash_control_title",
    "hash_control_description",
    "hash_evidence_description",
    "hash_local_functional_information",
    "hash_control_as_event",
    "hash_control_as_issues",
]


def upgrade() -> None:
    # Add 6 per-feature hash columns
    for col in _FEATURE_HASH_COLUMNS:
        op.add_column(_TABLE, sa.Column(col, sa.Text, nullable=True))

    # Drop old single hash column
    op.drop_column(_TABLE, "hash")


def downgrade() -> None:
    # Restore single hash column
    op.add_column(_TABLE, sa.Column("hash", sa.Text, nullable=True))

    # Drop per-feature hash columns
    for col in _FEATURE_HASH_COLUMNS:
        op.drop_column(_TABLE, col)
