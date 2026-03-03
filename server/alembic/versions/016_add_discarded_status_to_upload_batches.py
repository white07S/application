"""Add 'discarded' status to upload_batches check constraint.

Allows failed batches to be discarded so they no longer block
subsequent ingestions via the predecessor check.

Revision ID: 016
Revises: 015
Create Date: 2026-03-03
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE upload_batches DROP CONSTRAINT IF EXISTS upload_batches_status_check")
    op.create_check_constraint(
        "upload_batches_status_check",
        "upload_batches",
        "status IN ('pending', 'validating', 'validated', 'processing', 'success', 'failed', 'discarded')",
    )


def downgrade() -> None:
    op.execute("ALTER TABLE upload_batches DROP CONSTRAINT IF EXISTS upload_batches_status_check")
    op.create_check_constraint(
        "upload_batches_status_check",
        "upload_batches",
        "status IN ('pending', 'validating', 'validated', 'processing', 'success', 'failed')",
    )
