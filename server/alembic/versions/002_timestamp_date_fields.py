"""Convert 4 date columns from Text to TIMESTAMPTZ in ver_control.

Revision ID: 002
Revises: f4c2e1b8d9aa
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "f4c2e1b8d9aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "src_controls_ver_control"
_COLUMNS = [
    "last_modified_on",
    "control_created_on",
    "last_modification_on",
    "control_status_date_change",
]


def upgrade() -> None:
    for col in _COLUMNS:
        op.execute(
            f'ALTER TABLE {_TABLE} '
            f'ALTER COLUMN "{col}" TYPE TIMESTAMPTZ '
            f"USING CASE "
            f"  WHEN \"{col}\" IS NULL THEN NULL "
            f"  WHEN \"{col}\" ~ '^\\d{{4}}-' THEN \"{col}\"::timestamptz "
            f"  WHEN \"{col}\" ~ '^\\d{{2}}-[A-Za-z]{{3}}-' THEN to_timestamp(\"{col}\", 'DD-Mon-YYYY HH12:MI:SS AM')::timestamptz "
            f"  ELSE NULL "
            f"END"
        )


def downgrade() -> None:
    for col in _COLUMNS:
        op.execute(
            f'ALTER TABLE {_TABLE} '
            f'ALTER COLUMN "{col}" TYPE TEXT '
            f"USING \"{col}\"::text"
        )
