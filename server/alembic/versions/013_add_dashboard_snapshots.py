"""Add dashboard_snapshots table and supporting indexes for aggregate queries.

Revision ID: 013
Revises: 012
Create Date: 2026-02-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. dashboard_snapshots table ──────────────────────────────────────
    op.create_table(
        "dashboard_snapshots",
        sa.Column("snapshot_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("upload_id", sa.Text, nullable=True),
        sa.Column(
            "snapshot_type",
            sa.Text,
            nullable=False,
            server_default=sa.text("'ingestion'"),
        ),
        # Portfolio counts
        sa.Column("total_controls", sa.Integer, nullable=False),
        sa.Column("total_l1", sa.Integer, nullable=False),
        sa.Column("total_l2", sa.Integer, nullable=False),
        sa.Column("active_controls", sa.Integer, nullable=False),
        sa.Column("inactive_controls", sa.Integer, nullable=False),
        sa.Column("key_controls", sa.Integer, nullable=False),
        # AI scoring aggregates
        sa.Column("avg_l1_score", sa.Float, nullable=True),
        sa.Column("avg_l2_score", sa.Float, nullable=True),
        sa.Column("median_l1_score", sa.Float, nullable=True),
        sa.Column("median_l2_score", sa.Float, nullable=True),
        sa.Column("controls_scoring_full_marks", sa.Integer, nullable=True),
        sa.Column("controls_scoring_zero", sa.Integer, nullable=True),
        # JSONB distributions
        sa.Column("l1_score_distribution", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("l2_score_distribution", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("criterion_pass_rates", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("preventative_detective_dist", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("manual_automated_dist", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("execution_frequency_dist", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        # Regulatory counts
        sa.Column("sox_relevant_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("ccar_relevant_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("bcbs239_relevant_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        # Drill-down breakdowns
        sa.Column("function_breakdown", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("risk_theme_breakdown", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        # Metadata
        sa.Column("computation_ms", sa.Integer, nullable=True),
        # Constraints
        sa.CheckConstraint(
            "snapshot_type IN ('ingestion', 'manual', 'scheduled')",
            name="chk_dashboard_snapshot_type",
        ),
    )
    op.create_index("idx_dashboard_snapshots_at", "dashboard_snapshots", ["snapshot_at"])
    op.create_index(
        "idx_dashboard_snapshots_upload",
        "dashboard_snapshots",
        ["upload_id"],
        postgresql_where=sa.text("upload_id IS NOT NULL"),
    )

    # ── 2. Supporting indexes on existing tables ──────────────────────────
    op.create_index(
        "idx_ver_control_hierarchy_current",
        "src_controls_ver_control",
        ["hierarchy_level"],
        postgresql_where=sa.text("tx_to IS NULL"),
    )
    op.create_index(
        "idx_ver_control_status_hierarchy_current",
        "src_controls_ver_control",
        ["control_status", "hierarchy_level"],
        postgresql_where=sa.text("tx_to IS NULL"),
    )
    op.create_index(
        "idx_rel_owns_func_node_current",
        "src_controls_rel_owns_function",
        ["node_id"],
        postgresql_where=sa.text("tx_to IS NULL"),
    )
    op.create_index(
        "idx_rel_risk_theme_theme_current",
        "src_controls_rel_risk_theme",
        ["theme_id"],
        postgresql_where=sa.text("tx_to IS NULL"),
    )
    op.create_index(
        "idx_ai_enrichment_tx_from",
        "ai_controls_model_enrichment",
        ["tx_from"],
    )
    op.create_index(
        "idx_ver_control_tx_range",
        "src_controls_ver_control",
        ["tx_from", "tx_to"],
    )


def downgrade() -> None:
    # Drop supporting indexes
    op.drop_index("idx_ver_control_tx_range", table_name="src_controls_ver_control")
    op.drop_index("idx_ai_enrichment_tx_from", table_name="ai_controls_model_enrichment")
    op.drop_index("idx_rel_risk_theme_theme_current", table_name="src_controls_rel_risk_theme")
    op.drop_index("idx_rel_owns_func_node_current", table_name="src_controls_rel_owns_function")
    op.drop_index("idx_ver_control_status_hierarchy_current", table_name="src_controls_ver_control")
    op.drop_index("idx_ver_control_hierarchy_current", table_name="src_controls_ver_control")
    # Drop table
    op.drop_table("dashboard_snapshots")
