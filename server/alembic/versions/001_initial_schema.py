"""Initial schema — all domain + job tables.

Revision ID: 001
Revises: None
Create Date: 2026-02-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Orgs domain (6 tables) ─────────────────────────────────────────

    op.create_table(
        "src_orgs_ref_node",
        sa.Column("node_id", sa.Text, primary_key=True),
        sa.Column("tree", sa.Text, nullable=False),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("node_type", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("tree IN ('function', 'location', 'consolidated')", name="ck_ref_node_tree"),
    )
    op.create_index("ix_ref_node_tree", "src_orgs_ref_node", ["tree"])
    op.create_index("uq_ref_node_tree_source", "src_orgs_ref_node", ["tree", "source_id"], unique=True)

    op.create_table(
        "src_orgs_ver_function",
        sa.Column("ver_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ref_node_id", sa.Text, sa.ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=True),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('NONE', 'Active', 'Inactive', 'Deleted')", name="ck_ver_function_status"),
    )
    op.create_index("ix_ver_function_ref_txto", "src_orgs_ver_function", ["ref_node_id", "tx_to"])
    op.create_index("uq_ver_function_ref_current", "src_orgs_ver_function", ["ref_node_id"], unique=True, postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "src_orgs_ver_location",
        sa.Column("ver_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ref_node_id", sa.Text, sa.ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
        sa.Column("names", ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("status", sa.Text, nullable=True),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('NONE', 'Active', 'Inactive')", name="ck_ver_location_status"),
    )
    op.create_index("ix_ver_location_ref_txto", "src_orgs_ver_location", ["ref_node_id", "tx_to"])
    op.create_index("uq_ver_location_ref_current", "src_orgs_ver_location", ["ref_node_id"], unique=True, postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "src_orgs_ver_consolidated",
        sa.Column("ver_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ref_node_id", sa.Text, sa.ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
        sa.Column("names", ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("status", sa.Text, nullable=True),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('NONE', 'Active', 'Inactive')", name="ck_ver_consolidated_status"),
    )
    op.create_index("ix_ver_consolidated_ref_txto", "src_orgs_ver_consolidated", ["ref_node_id", "tx_to"])
    op.create_index("uq_ver_consolidated_ref_current", "src_orgs_ver_consolidated", ["ref_node_id"], unique=True, postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "src_orgs_rel_child",
        sa.Column("edge_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("in_node_id", sa.Text, sa.ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
        sa.Column("out_node_id", sa.Text, sa.ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("in_node_id", "out_node_id", "tx_from", name="uq_rel_child_edge"),
    )
    op.create_index("ix_rel_child_in_current", "src_orgs_rel_child", ["in_node_id"], postgresql_where=sa.text("tx_to IS NULL"))
    op.create_index("ix_rel_child_out_current", "src_orgs_rel_child", ["out_node_id"], postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "src_orgs_rel_cross_link",
        sa.Column("edge_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("in_node_id", sa.Text, sa.ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
        sa.Column("out_node_id", sa.Text, sa.ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
        sa.Column("link_type", sa.Text, nullable=False),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("in_node_id", "out_node_id", "tx_from", name="uq_rel_cross_link_edge"),
    )
    op.create_index("ix_rel_cross_link_in_type_current", "src_orgs_rel_cross_link", ["in_node_id", "link_type"], postgresql_where=sa.text("tx_to IS NULL"))
    op.create_index("ix_rel_cross_link_out_current", "src_orgs_rel_cross_link", ["out_node_id"], postgresql_where=sa.text("tx_to IS NULL"))

    # ── Risks domain (5 tables) ────────────────────────────────────────

    op.create_table(
        "src_risks_ref_taxonomy",
        sa.Column("taxonomy_id", sa.Text, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "src_risks_ver_taxonomy",
        sa.Column("ver_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ref_taxonomy_id", sa.Text, sa.ForeignKey("src_risks_ref_taxonomy.taxonomy_id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="ck_ver_taxonomy_tx_range"),
    )
    op.create_index("ix_ver_taxonomy_ref_tx_to", "src_risks_ver_taxonomy", ["ref_taxonomy_id", "tx_to"])
    op.create_index("ix_ver_taxonomy_ref_current", "src_risks_ver_taxonomy", ["ref_taxonomy_id"], unique=True, postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "src_risks_ref_theme",
        sa.Column("theme_id", sa.Text, primary_key=True),
        sa.Column("source_id", sa.Text, nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "src_risks_ver_theme",
        sa.Column("ver_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ref_theme_id", sa.Text, sa.ForeignKey("src_risks_ref_theme.theme_id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("mapping_considerations", sa.Text, nullable=False),
        sa.Column("status", sa.Text, sa.CheckConstraint("status IN ('active', 'expired')", name="ck_ver_theme_status"), nullable=False),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="ck_ver_theme_tx_range"),
    )
    op.create_index("ix_ver_theme_ref_tx_to", "src_risks_ver_theme", ["ref_theme_id", "tx_to"])
    op.create_index("ix_ver_theme_ref_current", "src_risks_ver_theme", ["ref_theme_id"], unique=True, postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "src_risks_rel_taxonomy_theme",
        sa.Column("taxonomy_id", sa.Text, sa.ForeignKey("src_risks_ref_taxonomy.taxonomy_id"), nullable=False, primary_key=True),
        sa.Column("theme_id", sa.Text, sa.ForeignKey("src_risks_ref_theme.theme_id"), nullable=False, primary_key=True),
    )

    # ── Controls domain — source tables (8) ────────────────────────────

    op.create_table(
        "src_controls_ref_control",
        sa.Column("control_id", sa.Text, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "src_controls_ver_control",
        sa.Column("ver_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ref_control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        # Core properties
        sa.Column("control_title", sa.Text, nullable=True),
        sa.Column("control_description", sa.Text, nullable=True),
        sa.Column("key_control", sa.Boolean, nullable=True),
        sa.Column("hierarchy_level", sa.Text, nullable=True),
        sa.Column("preventative_detective", sa.Text, nullable=True),
        sa.Column("manual_automated", sa.Text, nullable=True),
        sa.Column("execution_frequency", sa.Text, nullable=True),
        sa.Column("four_eyes_check", sa.Boolean, nullable=True),
        sa.Column("control_status", sa.Text, nullable=True),
        # Evidence & measures
        sa.Column("evidence_description", sa.Text, nullable=True),
        sa.Column("evidence_available_from", sa.Text, nullable=True),
        sa.Column("performance_measures_required", sa.Boolean, nullable=True),
        sa.Column("performance_measures_available_from", sa.Text, nullable=True),
        # Dates
        sa.Column("valid_from", sa.Text, nullable=True),
        sa.Column("valid_until", sa.Text, nullable=True),
        sa.Column("last_modified_on", sa.Text, nullable=True),
        sa.Column("control_created_on", sa.Text, nullable=True),
        sa.Column("last_modification_on", sa.Text, nullable=True),
        sa.Column("control_status_date_change", sa.Text, nullable=True),
        # Deactivation
        sa.Column("reason_for_deactivation", sa.Text, nullable=True),
        sa.Column("additional_information_on_deactivation", sa.Text, nullable=True),
        sa.Column("status_updates", sa.Text, nullable=True),
        # People
        sa.Column("control_owner", sa.Text, nullable=True),
        sa.Column("control_owner_gpn", sa.Text, nullable=True),
        sa.Column("control_instance_owner_role", sa.Text, nullable=True),
        sa.Column("control_delegate", sa.Text, nullable=True),
        sa.Column("control_delegate_gpn", sa.Text, nullable=True),
        sa.Column("control_assessor", sa.Text, nullable=True),
        sa.Column("control_assessor_gpn", sa.Text, nullable=True),
        sa.Column("is_assessor_control_owner", sa.Boolean, nullable=True),
        sa.Column("control_created_by", sa.Text, nullable=True),
        sa.Column("control_created_by_gpn", sa.Text, nullable=True),
        sa.Column("last_control_modification_requested_by", sa.Text, nullable=True),
        sa.Column("last_control_modification_requested_by_gpn", sa.Text, nullable=True),
        # Administrators
        sa.Column("control_administrator", ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("control_administrator_gpn", ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")),
        # Regulatory & compliance
        sa.Column("sox_relevant", sa.Boolean, nullable=True),
        sa.Column("ccar_relevant", sa.Boolean, nullable=True),
        sa.Column("bcbs239_relevant", sa.Boolean, nullable=True),
        sa.Column("ey_reliant", sa.Boolean, nullable=True),
        sa.Column("sox_rationale", sa.Text, nullable=True),
        # Metadata
        sa.Column("local_functional_information", sa.Text, nullable=True),
        sa.Column("kpci_governance_forum", sa.Text, nullable=True),
        sa.Column("financial_statement_line_item", sa.Text, nullable=True),
        sa.Column("it_application_system_supporting_control_instance", sa.Text, nullable=True),
        # Multi-value
        sa.Column("category_flags", ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("sox_assertions", ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")),
        # Unlinked entries
        sa.Column("unlinked_risk_themes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("unlinked_related_functions", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("unlinked_related_locations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        # Transaction-time versioning
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_ver_control"),
    )
    op.create_index("idx_ver_control_ref_txto", "src_controls_ver_control", ["ref_control_id", "tx_to"])
    op.create_index("idx_ver_control_status_txto", "src_controls_ver_control", ["control_status", "tx_to"])
    op.create_index("uq_ver_control_current", "src_controls_ver_control", ["ref_control_id"], unique=True, postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "src_controls_rel_parent",
        sa.Column("edge_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("parent_control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        sa.Column("child_control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_rel_parent"),
        sa.UniqueConstraint("parent_control_id", "child_control_id", "tx_from", name="uq_rel_parent_edge"),
    )
    op.create_index("idx_rel_parent_child_current", "src_controls_rel_parent", ["child_control_id"], postgresql_where=sa.text("tx_to IS NULL"))
    op.create_index("idx_rel_parent_parent_current", "src_controls_rel_parent", ["parent_control_id"], postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "src_controls_rel_owns_function",
        sa.Column("edge_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        sa.Column("node_id", sa.Text, sa.ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_rel_owns_func"),
        sa.UniqueConstraint("control_id", "node_id", "tx_from", name="uq_rel_owns_function_edge"),
    )
    op.create_index("idx_rel_owns_function_current", "src_controls_rel_owns_function", ["control_id"], postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "src_controls_rel_owns_location",
        sa.Column("edge_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        sa.Column("node_id", sa.Text, sa.ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_rel_owns_loc"),
        sa.UniqueConstraint("control_id", "node_id", "tx_from", name="uq_rel_owns_location_edge"),
    )
    op.create_index("idx_rel_owns_location_current", "src_controls_rel_owns_location", ["control_id"], postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "src_controls_rel_related_function",
        sa.Column("edge_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        sa.Column("node_id", sa.Text, sa.ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_rel_related_func"),
        sa.UniqueConstraint("control_id", "node_id", "tx_from", name="uq_rel_related_function_edge"),
    )
    op.create_index("idx_rel_related_function_current", "src_controls_rel_related_function", ["control_id"], postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "src_controls_rel_related_location",
        sa.Column("edge_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        sa.Column("node_id", sa.Text, sa.ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_rel_related_loc"),
        sa.UniqueConstraint("control_id", "node_id", "tx_from", name="uq_rel_related_location_edge"),
    )
    op.create_index("idx_rel_related_location_current", "src_controls_rel_related_location", ["control_id"], postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "src_controls_rel_risk_theme",
        sa.Column("edge_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        sa.Column("theme_id", sa.Text, sa.ForeignKey("src_risks_ref_theme.theme_id"), nullable=False),
        sa.Column("risk_theme_label", sa.Text, nullable=True),
        sa.Column("taxonomy_ref", sa.Text, nullable=True),
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_rel_risk_theme"),
        sa.UniqueConstraint("control_id", "theme_id", "tx_from", name="uq_rel_risk_theme_edge"),
    )
    op.create_index("idx_rel_risk_theme_current", "src_controls_rel_risk_theme", ["control_id"], postgresql_where=sa.text("tx_to IS NULL"))

    # ── Controls domain — AI model tables (3) ──────────────────────────

    op.create_table(
        "ai_controls_model_enrichment",
        sa.Column("ver_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ref_control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        sa.Column("hash", sa.Text, nullable=True),
        sa.Column("model_run_timestamp", sa.DateTime(timezone=True), nullable=False),
        # Enrichment fields
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("what_yes_no", sa.Text, nullable=True),
        sa.Column("what_details", sa.Text, nullable=True),
        sa.Column("where_yes_no", sa.Text, nullable=True),
        sa.Column("where_details", sa.Text, nullable=True),
        sa.Column("who_yes_no", sa.Text, nullable=True),
        sa.Column("who_details", sa.Text, nullable=True),
        sa.Column("when_yes_no", sa.Text, nullable=True),
        sa.Column("when_details", sa.Text, nullable=True),
        sa.Column("why_yes_no", sa.Text, nullable=True),
        sa.Column("why_details", sa.Text, nullable=True),
        sa.Column("what_why_yes_no", sa.Text, nullable=True),
        sa.Column("what_why_details", sa.Text, nullable=True),
        sa.Column("risk_theme_yes_no", sa.Text, nullable=True),
        sa.Column("risk_theme_details", sa.Text, nullable=True),
        sa.Column("people", sa.Text, nullable=True),
        sa.Column("process", sa.Text, nullable=True),
        sa.Column("product", sa.Text, nullable=True),
        sa.Column("service", sa.Text, nullable=True),
        sa.Column("regulations", sa.Text, nullable=True),
        sa.Column("frequency_yes_no", sa.Text, nullable=True),
        sa.Column("frequency_details", sa.Text, nullable=True),
        sa.Column("preventative_detective_yes_no", sa.Text, nullable=True),
        sa.Column("preventative_detective_details", sa.Text, nullable=True),
        sa.Column("automation_level_yes_no", sa.Text, nullable=True),
        sa.Column("automation_level_details", sa.Text, nullable=True),
        sa.Column("followup_yes_no", sa.Text, nullable=True),
        sa.Column("followup_details", sa.Text, nullable=True),
        sa.Column("escalation_yes_no", sa.Text, nullable=True),
        sa.Column("escalation_details", sa.Text, nullable=True),
        sa.Column("evidence_yes_no", sa.Text, nullable=True),
        sa.Column("evidence_details", sa.Text, nullable=True),
        sa.Column("abbreviations_yes_no", sa.Text, nullable=True),
        sa.Column("abbreviations_details", sa.Text, nullable=True),
        sa.Column("control_as_issues", sa.Text, nullable=True),
        sa.Column("control_as_event", sa.Text, nullable=True),
        # Versioning
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_ai_enrichment"),
    )
    op.create_index("idx_ai_enrichment_ref_txto", "ai_controls_model_enrichment", ["ref_control_id", "tx_to"])
    op.create_index("uq_ai_enrichment_current", "ai_controls_model_enrichment", ["ref_control_id"], unique=True, postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "ai_controls_model_taxonomy",
        sa.Column("ver_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ref_control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        sa.Column("hash", sa.Text, nullable=True),
        sa.Column("model_run_timestamp", sa.DateTime(timezone=True), nullable=False),
        # Primary risk theme
        sa.Column("parent_primary_risk_theme_id", sa.Text, nullable=True),
        sa.Column("primary_risk_theme_id", sa.Text, nullable=True),
        sa.Column("primary_risk_theme_reasoning", ARRAY(sa.Text), nullable=True),
        # Secondary risk theme
        sa.Column("parent_secondary_risk_theme_id", sa.Text, nullable=True),
        sa.Column("secondary_risk_theme_id", sa.Text, nullable=True),
        sa.Column("secondary_risk_theme_reasoning", ARRAY(sa.Text), nullable=True),
        # Versioning
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_ai_taxonomy"),
    )
    op.create_index("idx_ai_taxonomy_ref_txto", "ai_controls_model_taxonomy", ["ref_control_id", "tx_to"])
    op.create_index("uq_ai_taxonomy_current", "ai_controls_model_taxonomy", ["ref_control_id"], unique=True, postgresql_where=sa.text("tx_to IS NULL"))

    op.create_table(
        "ai_controls_model_clean_text",
        sa.Column("ver_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ref_control_id", sa.Text, sa.ForeignKey("src_controls_ref_control.control_id"), nullable=False),
        sa.Column("hash", sa.Text, nullable=True),
        sa.Column("model_run_timestamp", sa.DateTime(timezone=True), nullable=False),
        # Clean text fields
        sa.Column("control_title", sa.Text, nullable=True),
        sa.Column("control_description", sa.Text, nullable=True),
        sa.Column("evidence_description", sa.Text, nullable=True),
        sa.Column("local_functional_information", sa.Text, nullable=True),
        sa.Column("control_as_event", sa.Text, nullable=True),
        sa.Column("control_as_issues", sa.Text, nullable=True),
        # tsvector columns for FTS (populated by trigger)
        sa.Column("ts_control_title", TSVECTOR, nullable=True),
        sa.Column("ts_control_description", TSVECTOR, nullable=True),
        sa.Column("ts_evidence_description", TSVECTOR, nullable=True),
        sa.Column("ts_local_functional_information", TSVECTOR, nullable=True),
        sa.Column("ts_control_as_event", TSVECTOR, nullable=True),
        sa.Column("ts_control_as_issues", TSVECTOR, nullable=True),
        # Versioning
        sa.Column("tx_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_ai_clean_text"),
    )
    op.create_index("idx_ai_clean_text_ref_txto", "ai_controls_model_clean_text", ["ref_control_id", "tx_to"])
    op.create_index("uq_ai_clean_text_current", "ai_controls_model_clean_text", ["ref_control_id"], unique=True, postgresql_where=sa.text("tx_to IS NULL"))
    # GIN indexes for FTS on current versions only
    op.create_index("idx_fts_control_title", "ai_controls_model_clean_text", ["ts_control_title"], postgresql_using="gin", postgresql_where=sa.text("tx_to IS NULL"))
    op.create_index("idx_fts_control_description", "ai_controls_model_clean_text", ["ts_control_description"], postgresql_using="gin", postgresql_where=sa.text("tx_to IS NULL"))
    op.create_index("idx_fts_evidence_description", "ai_controls_model_clean_text", ["ts_evidence_description"], postgresql_using="gin", postgresql_where=sa.text("tx_to IS NULL"))
    op.create_index("idx_fts_local_functional_information", "ai_controls_model_clean_text", ["ts_local_functional_information"], postgresql_using="gin", postgresql_where=sa.text("tx_to IS NULL"))
    op.create_index("idx_fts_control_as_event", "ai_controls_model_clean_text", ["ts_control_as_event"], postgresql_using="gin", postgresql_where=sa.text("tx_to IS NULL"))
    op.create_index("idx_fts_control_as_issues", "ai_controls_model_clean_text", ["ts_control_as_issues"], postgresql_using="gin", postgresql_where=sa.text("tx_to IS NULL"))

    # FTS trigger function (separate execute calls — asyncpg requires one statement per call)
    op.execute("""
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
    """)

    # FTS trigger
    op.execute("""
CREATE TRIGGER trg_clean_text_tsvectors
    BEFORE INSERT OR UPDATE ON ai_controls_model_clean_text
    FOR EACH ROW EXECUTE FUNCTION update_clean_text_tsvectors();
    """)

    # ── Jobs tables (4 ORM models) ─────────────────────────────────────

    op.create_table(
        "tus_uploads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_session_id", sa.String(36), nullable=False),
        sa.Column("upload_id", sa.String(20), nullable=True),
        sa.Column("data_type", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("offset", sa.BigInteger, default=0),
        sa.Column("is_complete", sa.Boolean, default=False),
        sa.Column("uploaded_by", sa.String(200), nullable=True),
        sa.Column("temp_path", sa.Text, nullable=False),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("expected_files", sa.Integer, default=1),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("data_type IN ('issues', 'controls', 'actions')"),
    )
    op.create_index("idx_tus_uploads_is_complete", "tus_uploads", ["is_complete"])
    op.create_index("idx_tus_uploads_batch_session", "tus_uploads", ["batch_session_id"])

    op.create_table(
        "upload_batches",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("upload_id", sa.String(20), unique=True, nullable=False),
        sa.Column("data_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("source_path", sa.Text, nullable=False),
        sa.Column("uploaded_by", sa.String(200), nullable=True),
        sa.Column("file_count", sa.Integer, nullable=True),
        sa.Column("total_records", sa.Integer, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_details", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'validating', 'validated', 'processing', 'success', 'failed')"),
        sa.CheckConstraint("data_type IN ('issues', 'controls', 'actions')"),
    )
    op.create_index("idx_upload_batches_status", "upload_batches", ["status"])

    op.create_table(
        "upload_id_sequence",
        sa.Column("year", sa.Integer, primary_key=True),
        sa.Column("sequence", sa.Integer, default=0),
    )

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_type", sa.String(20), nullable=False),
        sa.Column("batch_id", sa.Integer, nullable=False),
        sa.Column("upload_id", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("progress_percent", sa.Integer, default=0),
        sa.Column("current_step", sa.String(100), nullable=True),
        sa.Column("records_total", sa.Integer, default=0),
        sa.Column("records_processed", sa.Integer, default=0),
        sa.Column("records_new", sa.Integer, default=0),
        sa.Column("records_changed", sa.Integer, default=0),
        sa.Column("records_unchanged", sa.Integer, default=0),
        sa.Column("records_failed", sa.Integer, default=0),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')"),
        sa.CheckConstraint("job_type IN ('ingestion')"),
    )
    op.create_index("idx_processing_jobs_batch", "processing_jobs", ["batch_id"])
    op.create_index("idx_processing_jobs_status", "processing_jobs", ["status"])


def downgrade() -> None:
    # Jobs tables
    op.drop_table("processing_jobs")
    op.drop_table("upload_id_sequence")
    op.drop_table("upload_batches")
    op.drop_table("tus_uploads")

    # FTS trigger
    op.execute("DROP TRIGGER IF EXISTS trg_clean_text_tsvectors ON ai_controls_model_clean_text;")
    op.execute("DROP FUNCTION IF EXISTS update_clean_text_tsvectors();")

    # AI model tables
    op.drop_table("ai_controls_model_clean_text")
    op.drop_table("ai_controls_model_taxonomy")
    op.drop_table("ai_controls_model_enrichment")

    # Controls relation tables
    op.drop_table("src_controls_rel_risk_theme")
    op.drop_table("src_controls_rel_related_location")
    op.drop_table("src_controls_rel_related_function")
    op.drop_table("src_controls_rel_owns_location")
    op.drop_table("src_controls_rel_owns_function")
    op.drop_table("src_controls_rel_parent")
    op.drop_table("src_controls_ver_control")
    op.drop_table("src_controls_ref_control")

    # Risks tables
    op.drop_table("src_risks_rel_taxonomy_theme")
    op.drop_table("src_risks_ver_theme")
    op.drop_table("src_risks_ref_theme")
    op.drop_table("src_risks_ver_taxonomy")
    op.drop_table("src_risks_ref_taxonomy")

    # Orgs tables
    op.drop_table("src_orgs_rel_cross_link")
    op.drop_table("src_orgs_rel_child")
    op.drop_table("src_orgs_ver_consolidated")
    op.drop_table("src_orgs_ver_location")
    op.drop_table("src_orgs_ver_function")
    op.drop_table("src_orgs_ref_node")
