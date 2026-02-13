"""PostgreSQL schema for the controls domain.

11 tables across 2 sections:
- Source controls (8): ref_control, ver_control, 6 relation tables
- AI model outputs (3): enrichment, taxonomy, clean_text (with FTS via tsvector)

Embeddings are stored exclusively in Qdrant (no Postgres table).
FTS is provided via tsvector columns + GIN indexes on clean_text.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR

from server.pipelines.schema.base import metadata

# Table name list for backward compatibility
CONTROLS_TABLES = [
    # Source (8)
    "src_controls_ref_control",
    "src_controls_ver_control",
    "src_controls_rel_parent",
    "src_controls_rel_owns_function",
    "src_controls_rel_owns_location",
    "src_controls_rel_related_function",
    "src_controls_rel_related_location",
    "src_controls_rel_risk_theme",
    # AI (3) — no embedding table, that's in Qdrant
    "ai_controls_model_enrichment",
    "ai_controls_model_taxonomy",
    "ai_controls_model_clean_text",
]

# ──────────────────────────────────────────────────────────────────────
# Source Controls (8 tables)
# ──────────────────────────────────────────────────────────────────────

src_controls_ref_control = Table(
    "src_controls_ref_control",
    metadata,
    Column("control_id", Text, primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
)

src_controls_ver_control = Table(
    "src_controls_ver_control",
    metadata,
    Column("ver_id", BigInteger, primary_key=True, autoincrement=True),
    Column("ref_control_id", Text, ForeignKey("src_controls_ref_control.control_id"), nullable=False),

    # Core properties
    Column("control_title", Text, nullable=True),
    Column("control_description", Text, nullable=True),
    Column("key_control", Boolean, nullable=True),
    Column("hierarchy_level", Text, nullable=True),
    Column("preventative_detective", Text, nullable=True),
    Column("manual_automated", Text, nullable=True),
    Column("execution_frequency", Text, nullable=True),
    Column("four_eyes_check", Boolean, nullable=True),
    Column("control_status", Text, nullable=True),

    # Evidence & measures
    Column("evidence_description", Text, nullable=True),
    Column("evidence_available_from", Text, nullable=True),
    Column("performance_measures_required", Boolean, nullable=True),
    Column("performance_measures_available_from", Text, nullable=True),

    # Dates (stored as source strings)
    Column("valid_from", Text, nullable=True),
    Column("valid_until", Text, nullable=True),
    Column("last_modified_on", Text, nullable=True),
    Column("control_created_on", Text, nullable=True),
    Column("last_modification_on", Text, nullable=True),
    Column("control_status_date_change", Text, nullable=True),

    # Deactivation
    Column("reason_for_deactivation", Text, nullable=True),
    Column("additional_information_on_deactivation", Text, nullable=True),
    Column("status_updates", Text, nullable=True),

    # People
    Column("control_owner", Text, nullable=True),
    Column("control_owner_gpn", Text, nullable=True),
    Column("control_instance_owner_role", Text, nullable=True),
    Column("control_delegate", Text, nullable=True),
    Column("control_delegate_gpn", Text, nullable=True),
    Column("control_assessor", Text, nullable=True),
    Column("control_assessor_gpn", Text, nullable=True),
    Column("is_assessor_control_owner", Boolean, nullable=True),
    Column("control_created_by", Text, nullable=True),
    Column("control_created_by_gpn", Text, nullable=True),
    Column("last_control_modification_requested_by", Text, nullable=True),
    Column("last_control_modification_requested_by_gpn", Text, nullable=True),

    # Administrators (parallel arrays)
    Column("control_administrator", ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")),
    Column("control_administrator_gpn", ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")),

    # Regulatory & compliance
    Column("sox_relevant", Boolean, nullable=True),
    Column("ccar_relevant", Boolean, nullable=True),
    Column("bcbs239_relevant", Boolean, nullable=True),
    Column("ey_reliant", Boolean, nullable=True),
    Column("sox_rationale", Text, nullable=True),

    # Metadata
    Column("local_functional_information", Text, nullable=True),
    Column("kpci_governance_forum", Text, nullable=True),
    Column("financial_statement_line_item", Text, nullable=True),
    Column("it_application_system_supporting_control_instance", Text, nullable=True),

    # Multi-value fields
    Column("category_flags", ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")),
    Column("sox_assertions", ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")),

    # Unlinked entries (no linkable ID → stored as JSONB for provenance)
    Column("unlinked_risk_themes", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("unlinked_related_functions", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("unlinked_related_locations", JSONB, nullable=False, server_default=text("'[]'::jsonb")),

    # Transaction-time versioning
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),

    # Constraints
    CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_ver_control"),

    # Indexes
    Index("idx_ver_control_ref_txto", "ref_control_id", "tx_to"),
    Index("idx_ver_control_status_txto", "control_status", "tx_to"),
    Index("uq_ver_control_current", "ref_control_id", unique=True, postgresql_where=text("tx_to IS NULL")),
)

# ── Relation tables ─────────────────────────────────────────────────

src_controls_rel_parent = Table(
    "src_controls_rel_parent",
    metadata,
    Column("edge_id", BigInteger, primary_key=True, autoincrement=True),
    Column("parent_control_id", Text, ForeignKey("src_controls_ref_control.control_id"), nullable=False),
    Column("child_control_id", Text, ForeignKey("src_controls_ref_control.control_id"), nullable=False),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_rel_parent"),
    UniqueConstraint("parent_control_id", "child_control_id", "tx_from", name="uq_rel_parent_edge"),
    Index("idx_rel_parent_child_current", "child_control_id", postgresql_where=text("tx_to IS NULL")),
    Index("idx_rel_parent_parent_current", "parent_control_id", postgresql_where=text("tx_to IS NULL")),
)

src_controls_rel_owns_function = Table(
    "src_controls_rel_owns_function",
    metadata,
    Column("edge_id", BigInteger, primary_key=True, autoincrement=True),
    Column("control_id", Text, ForeignKey("src_controls_ref_control.control_id"), nullable=False),
    Column("node_id", Text, ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_rel_owns_func"),
    UniqueConstraint("control_id", "node_id", "tx_from", name="uq_rel_owns_function_edge"),
    Index("idx_rel_owns_function_current", "control_id", postgresql_where=text("tx_to IS NULL")),
)

src_controls_rel_owns_location = Table(
    "src_controls_rel_owns_location",
    metadata,
    Column("edge_id", BigInteger, primary_key=True, autoincrement=True),
    Column("control_id", Text, ForeignKey("src_controls_ref_control.control_id"), nullable=False),
    Column("node_id", Text, ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_rel_owns_loc"),
    UniqueConstraint("control_id", "node_id", "tx_from", name="uq_rel_owns_location_edge"),
    Index("idx_rel_owns_location_current", "control_id", postgresql_where=text("tx_to IS NULL")),
)

src_controls_rel_related_function = Table(
    "src_controls_rel_related_function",
    metadata,
    Column("edge_id", BigInteger, primary_key=True, autoincrement=True),
    Column("control_id", Text, ForeignKey("src_controls_ref_control.control_id"), nullable=False),
    Column("node_id", Text, ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
    Column("comment", Text, nullable=True),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_rel_related_func"),
    UniqueConstraint("control_id", "node_id", "tx_from", name="uq_rel_related_function_edge"),
    Index("idx_rel_related_function_current", "control_id", postgresql_where=text("tx_to IS NULL")),
)

src_controls_rel_related_location = Table(
    "src_controls_rel_related_location",
    metadata,
    Column("edge_id", BigInteger, primary_key=True, autoincrement=True),
    Column("control_id", Text, ForeignKey("src_controls_ref_control.control_id"), nullable=False),
    Column("node_id", Text, ForeignKey("src_orgs_ref_node.node_id"), nullable=False),
    Column("comment", Text, nullable=True),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_rel_related_loc"),
    UniqueConstraint("control_id", "node_id", "tx_from", name="uq_rel_related_location_edge"),
    Index("idx_rel_related_location_current", "control_id", postgresql_where=text("tx_to IS NULL")),
)

src_controls_rel_risk_theme = Table(
    "src_controls_rel_risk_theme",
    metadata,
    Column("edge_id", BigInteger, primary_key=True, autoincrement=True),
    Column("control_id", Text, ForeignKey("src_controls_ref_control.control_id"), nullable=False),
    Column("theme_id", Text, ForeignKey("src_risks_ref_theme.theme_id"), nullable=False),
    Column("risk_theme_label", Text, nullable=True),
    Column("taxonomy_ref", Text, nullable=True),  # stores taxonomy_id as text reference
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_rel_risk_theme"),
    UniqueConstraint("control_id", "theme_id", "tx_from", name="uq_rel_risk_theme_edge"),
    Index("idx_rel_risk_theme_current", "control_id", postgresql_where=text("tx_to IS NULL")),
)

# ──────────────────────────────────────────────────────────────────────
# AI Model Outputs (3 tables — no embedding table)
# ──────────────────────────────────────────────────────────────────────

ai_controls_model_enrichment = Table(
    "ai_controls_model_enrichment",
    metadata,
    Column("ver_id", BigInteger, primary_key=True, autoincrement=True),
    Column("ref_control_id", Text, ForeignKey("src_controls_ref_control.control_id"), nullable=False),
    Column("hash", Text, nullable=True),
    Column("model_run_timestamp", DateTime(timezone=True), nullable=False),

    # Enrichment fields
    Column("summary", Text, nullable=True),
    Column("what_yes_no", Text, nullable=True),
    Column("what_details", Text, nullable=True),
    Column("where_yes_no", Text, nullable=True),
    Column("where_details", Text, nullable=True),
    Column("who_yes_no", Text, nullable=True),
    Column("who_details", Text, nullable=True),
    Column("when_yes_no", Text, nullable=True),
    Column("when_details", Text, nullable=True),
    Column("why_yes_no", Text, nullable=True),
    Column("why_details", Text, nullable=True),
    Column("what_why_yes_no", Text, nullable=True),
    Column("what_why_details", Text, nullable=True),
    Column("risk_theme_yes_no", Text, nullable=True),
    Column("risk_theme_details", Text, nullable=True),
    Column("people", Text, nullable=True),
    Column("process", Text, nullable=True),
    Column("product", Text, nullable=True),
    Column("service", Text, nullable=True),
    Column("regulations", Text, nullable=True),
    Column("frequency_yes_no", Text, nullable=True),
    Column("frequency_details", Text, nullable=True),
    Column("preventative_detective_yes_no", Text, nullable=True),
    Column("preventative_detective_details", Text, nullable=True),
    Column("automation_level_yes_no", Text, nullable=True),
    Column("automation_level_details", Text, nullable=True),
    Column("followup_yes_no", Text, nullable=True),
    Column("followup_details", Text, nullable=True),
    Column("escalation_yes_no", Text, nullable=True),
    Column("escalation_details", Text, nullable=True),
    Column("evidence_yes_no", Text, nullable=True),
    Column("evidence_details", Text, nullable=True),
    Column("abbreviations_yes_no", Text, nullable=True),
    Column("abbreviations_details", Text, nullable=True),
    Column("control_as_issues", Text, nullable=True),
    Column("control_as_event", Text, nullable=True),

    # Transaction-time versioning
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),

    CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_ai_enrichment"),
    Index("idx_ai_enrichment_ref_txto", "ref_control_id", "tx_to"),
    Index("uq_ai_enrichment_current", "ref_control_id", unique=True, postgresql_where=text("tx_to IS NULL")),
)

ai_controls_model_taxonomy = Table(
    "ai_controls_model_taxonomy",
    metadata,
    Column("ver_id", BigInteger, primary_key=True, autoincrement=True),
    Column("ref_control_id", Text, ForeignKey("src_controls_ref_control.control_id"), nullable=False),
    Column("hash", Text, nullable=True),
    Column("model_run_timestamp", DateTime(timezone=True), nullable=False),

    # Primary risk theme
    Column("parent_primary_risk_theme_id", Text, nullable=True),  # taxonomy_id reference
    Column("primary_risk_theme_id", Text, nullable=True),  # theme_id reference
    Column("primary_risk_theme_reasoning", ARRAY(Text), nullable=True),

    # Secondary risk theme
    Column("parent_secondary_risk_theme_id", Text, nullable=True),
    Column("secondary_risk_theme_id", Text, nullable=True),
    Column("secondary_risk_theme_reasoning", ARRAY(Text), nullable=True),

    # Transaction-time versioning
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),

    CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_ai_taxonomy"),
    Index("idx_ai_taxonomy_ref_txto", "ref_control_id", "tx_to"),
    Index("uq_ai_taxonomy_current", "ref_control_id", unique=True, postgresql_where=text("tx_to IS NULL")),
)

ai_controls_model_clean_text = Table(
    "ai_controls_model_clean_text",
    metadata,
    Column("ver_id", BigInteger, primary_key=True, autoincrement=True),
    Column("ref_control_id", Text, ForeignKey("src_controls_ref_control.control_id"), nullable=False),
    Column("hash", Text, nullable=True),
    Column("model_run_timestamp", DateTime(timezone=True), nullable=False),

    # Clean text fields
    Column("control_title", Text, nullable=True),
    Column("control_description", Text, nullable=True),
    Column("evidence_description", Text, nullable=True),
    Column("local_functional_information", Text, nullable=True),
    Column("control_as_event", Text, nullable=True),
    Column("control_as_issues", Text, nullable=True),

    # tsvector columns for FTS (populated by trigger)
    Column("ts_control_title", TSVECTOR, nullable=True),
    Column("ts_control_description", TSVECTOR, nullable=True),
    Column("ts_evidence_description", TSVECTOR, nullable=True),
    Column("ts_local_functional_information", TSVECTOR, nullable=True),
    Column("ts_control_as_event", TSVECTOR, nullable=True),
    Column("ts_control_as_issues", TSVECTOR, nullable=True),

    # Transaction-time versioning
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),

    CheckConstraint("tx_to IS NULL OR tx_to > tx_from", name="chk_tx_order_ai_clean_text"),
    Index("idx_ai_clean_text_ref_txto", "ref_control_id", "tx_to"),
    Index("uq_ai_clean_text_current", "ref_control_id", unique=True, postgresql_where=text("tx_to IS NULL")),

    # GIN indexes for FTS on current versions only
    Index("idx_fts_control_title", "ts_control_title", postgresql_using="gin", postgresql_where=text("tx_to IS NULL")),
    Index("idx_fts_control_description", "ts_control_description", postgresql_using="gin", postgresql_where=text("tx_to IS NULL")),
    Index("idx_fts_evidence_description", "ts_evidence_description", postgresql_using="gin", postgresql_where=text("tx_to IS NULL")),
    Index("idx_fts_local_functional_information", "ts_local_functional_information", postgresql_using="gin", postgresql_where=text("tx_to IS NULL")),
    Index("idx_fts_control_as_event", "ts_control_as_event", postgresql_using="gin", postgresql_where=text("tx_to IS NULL")),
    Index("idx_fts_control_as_issues", "ts_control_as_issues", postgresql_using="gin", postgresql_where=text("tx_to IS NULL")),
)

# FTS trigger SQL — to be executed in Alembic migration
FTS_TRIGGER_SQL = """
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

CREATE TRIGGER trg_clean_text_tsvectors
    BEFORE INSERT OR UPDATE ON ai_controls_model_clean_text
    FOR EACH ROW EXECUTE FUNCTION update_clean_text_tsvectors();
"""

FTS_TRIGGER_DROP_SQL = """
DROP TRIGGER IF EXISTS trg_clean_text_tsvectors ON ai_controls_model_clean_text;
DROP FUNCTION IF EXISTS update_clean_text_tsvectors();
"""
