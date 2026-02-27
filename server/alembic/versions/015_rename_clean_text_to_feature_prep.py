"""Rename ai_controls_model_clean_text → ai_controls_model_feature_prep.

The table was originally named "clean_text" when it performed heavy text
cleaning. After the pipeline redesign (014), it only assembles feature texts,
hashes, and masks — so the name is updated to reflect its actual purpose.

Also renames constraints, indexes, triggers, and functions.

Revision ID: 015
Revises: 014
Create Date: 2026-02-27
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "ai_controls_model_clean_text"
_NEW = "ai_controls_model_feature_prep"


def upgrade() -> None:
    # Drop trigger + function (they reference the old table name)
    op.execute(f"DROP TRIGGER IF EXISTS trg_clean_text_tsvectors ON {_OLD};")
    op.execute("DROP FUNCTION IF EXISTS update_clean_text_tsvectors();")

    # Rename table
    op.rename_table(_OLD, _NEW)

    # Rename constraints
    op.execute(f'ALTER TABLE {_NEW} RENAME CONSTRAINT chk_tx_order_ai_clean_text TO chk_tx_order_ai_feature_prep;')

    # Rename indexes
    op.execute('ALTER INDEX IF EXISTS idx_ai_clean_text_ref_txto RENAME TO idx_ai_feature_prep_ref_txto;')
    op.execute('ALTER INDEX IF EXISTS uq_ai_clean_text_current RENAME TO uq_ai_feature_prep_current;')

    # Recreate trigger function + trigger with new names (separate calls for asyncpg)
    op.execute("""
CREATE OR REPLACE FUNCTION update_feature_prep_tsvectors() RETURNS trigger AS $$
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
""")
    op.execute("""
CREATE TRIGGER trg_feature_prep_tsvectors
    BEFORE INSERT OR UPDATE ON ai_controls_model_feature_prep
    FOR EACH ROW EXECUTE FUNCTION update_feature_prep_tsvectors();
""")


def downgrade() -> None:
    # Drop new trigger + function
    op.execute(f"DROP TRIGGER IF EXISTS trg_feature_prep_tsvectors ON {_NEW};")
    op.execute("DROP FUNCTION IF EXISTS update_feature_prep_tsvectors();")

    # Rename table back
    op.rename_table(_NEW, _OLD)

    # Rename constraints back
    op.execute(f'ALTER TABLE {_OLD} RENAME CONSTRAINT chk_tx_order_ai_feature_prep TO chk_tx_order_ai_clean_text;')

    # Rename indexes back
    op.execute('ALTER INDEX IF EXISTS idx_ai_feature_prep_ref_txto RENAME TO idx_ai_clean_text_ref_txto;')
    op.execute('ALTER INDEX IF EXISTS uq_ai_feature_prep_current RENAME TO uq_ai_clean_text_current;')

    # Recreate trigger function + trigger with old names (separate calls for asyncpg)
    op.execute("""
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
""")
    op.execute("""
CREATE TRIGGER trg_clean_text_tsvectors
    BEFORE INSERT OR UPDATE ON ai_controls_model_clean_text
    FOR EACH ROW EXECUTE FUNCTION update_clean_text_tsvectors();
""")
