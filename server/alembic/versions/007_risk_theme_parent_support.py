"""Add parent_theme_id to src_risks_ref_theme, drop unique on source_id,
and make description columns nullable for expired themes.

Risk themes can now have duplicate source_ids (e.g. an active and expired
theme sharing the same risk_theme_id but with different names). The internal
theme_id is now a hash of (source_id + name). Expired themes link to their
active parent via parent_theme_id.

Expired themes often have NULL taxonomy_description, risk_theme_description,
and mapping_considerations — so those columns are relaxed to nullable.

Revision ID: 007
Revises: 006
Create Date: 2026-02-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop UNIQUE constraint on source_id (risk_theme_id is now non-unique)
    op.drop_constraint(
        "src_risks_ref_theme_source_id_key",
        "src_risks_ref_theme",
        type_="unique",
    )

    # Add parent_theme_id column (nullable, self-referencing FK)
    op.add_column(
        "src_risks_ref_theme",
        sa.Column(
            "parent_theme_id",
            sa.Text(),
            sa.ForeignKey("src_risks_ref_theme.theme_id"),
            nullable=True,
        ),
    )

    # Partial index for parent lookups
    op.create_index(
        "ix_ref_theme_parent",
        "src_risks_ref_theme",
        ["parent_theme_id"],
        postgresql_where=sa.text("parent_theme_id IS NOT NULL"),
    )

    # Make description columns nullable (expired themes have NULLs)
    op.alter_column(
        "src_risks_ver_taxonomy", "description",
        existing_type=sa.Text(), nullable=True,
    )
    op.alter_column(
        "src_risks_ver_theme", "description",
        existing_type=sa.Text(), nullable=True,
    )
    op.alter_column(
        "src_risks_ver_theme", "mapping_considerations",
        existing_type=sa.Text(), nullable=True,
    )


def downgrade() -> None:
    # Restore NOT NULL (set existing NULLs to empty string first)
    op.execute("UPDATE src_risks_ver_theme SET mapping_considerations = '' WHERE mapping_considerations IS NULL")
    op.execute("UPDATE src_risks_ver_theme SET description = '' WHERE description IS NULL")
    op.execute("UPDATE src_risks_ver_taxonomy SET description = '' WHERE description IS NULL")
    op.alter_column(
        "src_risks_ver_theme", "mapping_considerations",
        existing_type=sa.Text(), nullable=False,
    )
    op.alter_column(
        "src_risks_ver_theme", "description",
        existing_type=sa.Text(), nullable=False,
    )
    op.alter_column(
        "src_risks_ver_taxonomy", "description",
        existing_type=sa.Text(), nullable=False,
    )

    op.drop_index("ix_ref_theme_parent", "src_risks_ref_theme")
    op.drop_column("src_risks_ref_theme", "parent_theme_id")
    op.create_unique_constraint(
        "src_risks_ref_theme_source_id_key",
        "src_risks_ref_theme",
        ["source_id"],
    )
