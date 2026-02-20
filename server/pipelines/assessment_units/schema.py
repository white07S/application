"""PostgreSQL schema for the assessment_units domain.

2 tables: ref_unit, ver_unit.

Assessment units are flat entities (no hierarchy) that reference one function
and one location (from either the location or consolidated tree).
"""

from sqlalchemy import (
    Table,
    Column,
    Text,
    BigInteger,
    DateTime,
    Index,
    ForeignKey,
    CheckConstraint,
    text,
)

from server.pipelines.schema.base import metadata

# ── 1. src_au_ref_unit ────────────────────────────────────────────────────

src_au_ref_unit = Table(
    "src_au_ref_unit",
    metadata,
    Column("unit_id", Text, primary_key=True),
    Column("source_id", Text, nullable=False, unique=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

# ── 2. src_au_ver_unit ────────────────────────────────────────────────────

src_au_ver_unit = Table(
    "src_au_ver_unit",
    metadata,
    Column("ver_id", BigInteger, primary_key=True, autoincrement=True),
    Column(
        "ref_unit_id",
        Text,
        ForeignKey("src_au_ref_unit.unit_id"),
        nullable=False,
    ),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=True),
    Column(
        "function_node_id",
        Text,
        ForeignKey("src_orgs_ref_node.node_id"),
        nullable=False,
    ),
    Column(
        "location_node_id",
        Text,
        ForeignKey("src_orgs_ref_node.node_id"),
        nullable=False,
    ),
    Column("location_type", Text, nullable=False),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    CheckConstraint(
        "location_type IN ('location', 'consolidated')",
        name="ck_ver_unit_location_type",
    ),
    CheckConstraint(
        "tx_to IS NULL OR tx_to > tx_from",
        name="ck_ver_unit_tx_range",
    ),
    Index("ix_ver_unit_ref_txto", "ref_unit_id", "tx_to"),
    Index(
        "uq_ver_unit_ref_current",
        "ref_unit_id",
        unique=True,
        postgresql_where=text("tx_to IS NULL"),
    ),
)

# ── Export list of all table names ────────────────────────────────────────

AU_TABLES = [
    "src_au_ref_unit",
    "src_au_ver_unit",
]
