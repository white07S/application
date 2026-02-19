"""Convert valid_from and valid_until from Text to TIMESTAMPTZ in ver_control.

These two date columns were missed in migration 002 which converted 4 other
date columns.  Same conversion pattern: ISO → direct cast, legacy DD-Mon-YYYY
→ to_timestamp, NULL/unparseable → NULL.

Revision ID: 004
Revises: 003
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "src_controls_ver_control"
_COLUMNS = [
    "valid_from",
    "valid_until",
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
