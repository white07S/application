"""Rebuild clean_text table for 3 semantic features (what/why/where) and add
category column to similar_controls.

Clean_text moves from 6 raw text features to 3 LLM-extracted features:
  - what, why, where (from enrichment _details columns)
  - control_title, control_description, evidence_description,
    local_functional_information retained for keyword FTS only
  - Hashes: hash_what, hash_why, hash_where
  - Tsvectors for all 7 keyword-searchable fields

Similar_controls gets a category column: "near_duplicate" or "weak_similar".

Revision ID: 014
Revises: 013
Create Date: 2026-02-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CT_TABLE = "ai_controls_model_clean_text"
_SIM_TABLE = "ai_controls_similar_controls"

# New FTS trigger for the rebuilt clean_text table (split for asyncpg compatibility)
_FTS_FUNC_UP = """
CREATE OR REPLACE FUNCTION update_clean_text_tsvectors() RETURNS trigger AS $$
BEGIN
    NEW.ts_what := to_tsvector('english', COALESCE(NEW.what, ''));
    NEW.ts_why := to_tsvector('english', COALESCE(NEW.why, ''));
    NEW.ts_where := to_tsvector('english', COALESCE(NEW.where, ''));
    NEW.ts_control_title := to_tsvector('english', COALESCE(NEW.control_title, ''));
    NEW.ts_control_description := to_tsvector('english', COALESCE(NEW.control_description, ''));
    NEW.ts_evidence_description := to_tsvector('english', COALESCE(NEW.evidence_description, ''));
    NEW.ts_local_functional_information := to_tsvector('english', COALESCE(NEW.local_functional_information, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_FTS_TRIG_UP = """
CREATE TRIGGER trg_clean_text_tsvectors
    BEFORE INSERT OR UPDATE ON ai_controls_model_clean_text
    FOR EACH ROW EXECUTE FUNCTION update_clean_text_tsvectors();
"""

# Old trigger for downgrade (split for asyncpg compatibility)
_FTS_FUNC_DOWN = """
CREATE OR REPLACE FUNCTION update_clean_text_tsvectors() RETURNS trigger AS $$
BEGIN
    NEW.ts_control_title := to_tsvector('english', COALESCE(NEW.control_title, ''));
    NEW.ts_control_description := to_tsvector('english', COALESCE(NEW.control_description, ''));
    NEW.ts_evidence_description := to_tsvector('english', COALESCE(NEW.evidence_description, ''));
    NEW.ts_local_functional_information := to_tsvector('english', COALESCE(NEW.local_functional_information, ''));
    NEW.ts_control_as_event := to_tsvector('english', COALESCE(NEW.control_as_event, ''));
    NEW.ts_control_as_issues := to_tsvector('english', COALESCE(NEW.control_as_issues, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_FTS_TRIG_DOWN = """
CREATE TRIGGER trg_clean_text_tsvectors
    BEFORE INSERT OR UPDATE ON ai_controls_model_clean_text
    FOR EACH ROW EXECUTE FUNCTION update_clean_text_tsvectors();
"""


def upgrade() -> None:
    # ── 1. Drop and recreate clean_text table ──────────────────────────

    # Drop old trigger + function first
    op.execute("DROP TRIGGER IF EXISTS trg_clean_text_tsvectors ON ai_controls_model_clean_text;")
    op.execute("DROP FUNCTION IF EXISTS update_clean_text_tsvectors();")

    # Drop old GIN indexes (they reference old columns)
    for idx_name in [
        "idx_fts_control_title", "idx_fts_control_description",
        "idx_fts_evidence_description", "idx_fts_local_functional_information",
        "idx_fts_control_as_event", "idx_fts_control_as_issues",
    ]:
        op.execute(f"DROP INDEX IF EXISTS {idx_name};")

    # Drop old columns
    for col in [
        "hash_control_title", "hash_control_description",
        "hash_evidence_description", "hash_local_functional_information",
        "hash_control_as_event", "hash_control_as_issues",
        "control_as_event", "control_as_issues",
        "ts_control_title", "ts_control_description",
        "ts_evidence_description", "ts_local_functional_information",
        "ts_control_as_event", "ts_control_as_issues",
    ]:
        op.drop_column(_CT_TABLE, col)

    # Add new semantic feature columns
    for col in ["what", "why", "where"]:
        op.add_column(_CT_TABLE, sa.Column(col, sa.Text, nullable=True))

    # Add new hash columns
    for col in ["hash_what", "hash_why", "hash_where"]:
        op.add_column(_CT_TABLE, sa.Column(col, sa.Text, nullable=True))

    # Add new tsvector columns
    for col in [
        "ts_what", "ts_why", "ts_where",
        "ts_control_title", "ts_control_description",
        "ts_evidence_description", "ts_local_functional_information",
    ]:
        op.add_column(_CT_TABLE, sa.Column(col, TSVECTOR, nullable=True))

    # Create new GIN indexes (current versions only)
    for col in [
        "ts_what", "ts_why", "ts_where",
        "ts_control_title", "ts_control_description",
        "ts_evidence_description", "ts_local_functional_information",
    ]:
        idx_name = f"idx_fts_{col.removeprefix('ts_')}"
        op.create_index(
            idx_name, _CT_TABLE, [col],
            postgresql_using="gin",
            postgresql_where=sa.text("tx_to IS NULL"),
        )

    # Create new trigger function + trigger (separate calls for asyncpg)
    op.execute(_FTS_FUNC_UP)
    op.execute(_FTS_TRIG_UP)

    # ── 2. Add category to similar_controls ────────────────────────────

    op.add_column(
        _SIM_TABLE,
        sa.Column("category", sa.Text, nullable=True),
    )


def downgrade() -> None:
    # ── 1. Remove category from similar_controls ───────────────────────

    op.drop_column(_SIM_TABLE, "category")

    # ── 2. Reverse clean_text changes ──────────────────────────────────

    # Drop new trigger
    op.execute("DROP TRIGGER IF EXISTS trg_clean_text_tsvectors ON ai_controls_model_clean_text;")
    op.execute("DROP FUNCTION IF EXISTS update_clean_text_tsvectors();")

    # Drop new GIN indexes
    for col in [
        "what", "why", "where",
        "control_title", "control_description",
        "evidence_description", "local_functional_information",
    ]:
        op.execute(f"DROP INDEX IF EXISTS idx_fts_{col};")

    # Drop new columns
    for col in [
        "what", "why", "where",
        "hash_what", "hash_why", "hash_where",
        "ts_what", "ts_why", "ts_where",
        "ts_control_title", "ts_control_description",
        "ts_evidence_description", "ts_local_functional_information",
    ]:
        op.drop_column(_CT_TABLE, col)

    # Restore old hash columns
    for col in [
        "hash_control_title", "hash_control_description",
        "hash_evidence_description", "hash_local_functional_information",
        "hash_control_as_event", "hash_control_as_issues",
    ]:
        op.add_column(_CT_TABLE, sa.Column(col, sa.Text, nullable=True))

    # Restore old text columns
    for col in ["control_as_event", "control_as_issues"]:
        op.add_column(_CT_TABLE, sa.Column(col, sa.Text, nullable=True))

    # Restore old tsvector columns
    for col in [
        "ts_control_title", "ts_control_description",
        "ts_evidence_description", "ts_local_functional_information",
        "ts_control_as_event", "ts_control_as_issues",
    ]:
        op.add_column(_CT_TABLE, sa.Column(col, TSVECTOR, nullable=True))

    # Restore old GIN indexes
    for col in [
        "ts_control_title", "ts_control_description",
        "ts_evidence_description", "ts_local_functional_information",
        "ts_control_as_event", "ts_control_as_issues",
    ]:
        idx_name = f"idx_fts_{col.removeprefix('ts_')}"
        op.create_index(
            idx_name, _CT_TABLE, [col],
            postgresql_using="gin",
            postgresql_where=sa.text("tx_to IS NULL"),
        )

    # Restore old trigger function + trigger (separate calls for asyncpg)
    op.execute(_FTS_FUNC_DOWN)
    op.execute(_FTS_TRIG_DOWN)
