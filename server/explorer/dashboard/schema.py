"""SQLAlchemy table definition for the dashboard domain.

1 table: dashboard_snapshots — append-only time-series of aggregate metrics
captured after each controls ingestion run.
"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from server.pipelines.schema.base import metadata

dashboard_snapshots = Table(
    "dashboard_snapshots",
    metadata,
    Column("snapshot_id", BigInteger, primary_key=True, autoincrement=True),
    Column("snapshot_at", DateTime(timezone=True), nullable=False),
    Column("upload_id", Text, nullable=True),
    Column(
        "snapshot_type",
        Text,
        nullable=False,
        server_default=text("'ingestion'"),
    ),
    # Portfolio counts
    Column("total_controls", Integer, nullable=False),
    Column("total_l1", Integer, nullable=False),
    Column("total_l2", Integer, nullable=False),
    Column("active_controls", Integer, nullable=False),
    Column("inactive_controls", Integer, nullable=False),
    Column("key_controls", Integer, nullable=False),
    # AI scoring aggregates
    Column("avg_l1_score", Float, nullable=True),
    Column("avg_l2_score", Float, nullable=True),
    Column("median_l1_score", Float, nullable=True),
    Column("median_l2_score", Float, nullable=True),
    Column("controls_scoring_full_marks", Integer, nullable=True),
    Column("controls_scoring_zero", Integer, nullable=True),
    # JSONB distributions
    Column("l1_score_distribution", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("l2_score_distribution", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("criterion_pass_rates", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("preventative_detective_dist", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("manual_automated_dist", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("execution_frequency_dist", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    # Regulatory counts
    Column("sox_relevant_count", Integer, nullable=False, server_default=text("0")),
    Column("ccar_relevant_count", Integer, nullable=False, server_default=text("0")),
    Column("bcbs239_relevant_count", Integer, nullable=False, server_default=text("0")),
    # Drill-down breakdowns (JSONB arrays)
    Column("function_breakdown", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("risk_theme_breakdown", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    # Metadata
    Column("computation_ms", Integer, nullable=True),
    # Constraints
    CheckConstraint(
        "snapshot_type IN ('ingestion', 'manual', 'scheduled')",
        name="chk_dashboard_snapshot_type",
    ),
    Index("idx_dashboard_snapshots_at", "snapshot_at"),
    Index(
        "idx_dashboard_snapshots_upload",
        "upload_id",
        postgresql_where=text("upload_id IS NOT NULL"),
    ),
)
