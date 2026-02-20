"""Remove status column and add description column on src_au_ver_unit.

Assessment units no longer track Active/Inactive status. Instead they carry
an optional free-text description.

Revision ID: 008
Revises: 007
Create Date: 2026-02-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_ver_unit_status", "src_au_ver_unit", type_="check")
    op.drop_column("src_au_ver_unit", "status")
    op.add_column(
        "src_au_ver_unit",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("src_au_ver_unit", "description")
    op.add_column(
        "src_au_ver_unit",
        sa.Column("status", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_ver_unit_status",
        "src_au_ver_unit",
        "status IN ('Active', 'Inactive')",
    )
