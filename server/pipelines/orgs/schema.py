"""PostgreSQL schema for the orgs domain (SQLAlchemy Table objects).

6 tables: ref_node, 3 version tables (function/location/consolidated),
rel_child, rel_cross_link.

All tables are registered on the shared ``metadata`` instance so that
Alembic can manage every domain in a single migration chain.
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
from sqlalchemy.dialects.postgresql import ARRAY

from server.pipelines.schema.base import metadata

# ── 1. src_orgs_ref_node ────────────────────────────────────────────────────

src_orgs_ref_node = Table(
    "src_orgs_ref_node",
    metadata,
    Column("node_id", Text, primary_key=True),
    Column("tree", Text, nullable=False),
    Column("source_id", Text, nullable=False),
    Column("node_type", Text, nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    CheckConstraint(
        "tree IN ('function', 'location', 'consolidated')",
        name="ck_ref_node_tree",
    ),
    Index("ix_ref_node_tree", "tree"),
    Index("uq_ref_node_tree_source", "tree", "source_id", unique=True),
)

# ── 2. src_orgs_ver_function ────────────────────────────────────────────────

src_orgs_ver_function = Table(
    "src_orgs_ver_function",
    metadata,
    Column("ver_id", BigInteger, primary_key=True, autoincrement=True),
    Column(
        "ref_node_id",
        Text,
        ForeignKey("src_orgs_ref_node.node_id"),
        nullable=False,
    ),
    Column("name", Text, nullable=False),
    Column("status", Text, nullable=True),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    CheckConstraint(
        "status IN ('NONE', 'Active', 'Inactive', 'Deleted')",
        name="ck_ver_function_status",
    ),
    Index("ix_ver_function_ref_txto", "ref_node_id", "tx_to"),
    Index(
        "uq_ver_function_ref_current",
        "ref_node_id",
        unique=True,
        postgresql_where=text("tx_to IS NULL"),
    ),
)

# ── 3. src_orgs_ver_location ────────────────────────────────────────────────

src_orgs_ver_location = Table(
    "src_orgs_ver_location",
    metadata,
    Column("ver_id", BigInteger, primary_key=True, autoincrement=True),
    Column(
        "ref_node_id",
        Text,
        ForeignKey("src_orgs_ref_node.node_id"),
        nullable=False,
    ),
    Column(
        "names",
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    ),
    Column("status", Text, nullable=True),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    CheckConstraint(
        "status IN ('NONE', 'Active', 'Inactive')",
        name="ck_ver_location_status",
    ),
    Index("ix_ver_location_ref_txto", "ref_node_id", "tx_to"),
    Index(
        "uq_ver_location_ref_current",
        "ref_node_id",
        unique=True,
        postgresql_where=text("tx_to IS NULL"),
    ),
)

# ── 4. src_orgs_ver_consolidated ────────────────────────────────────────────

src_orgs_ver_consolidated = Table(
    "src_orgs_ver_consolidated",
    metadata,
    Column("ver_id", BigInteger, primary_key=True, autoincrement=True),
    Column(
        "ref_node_id",
        Text,
        ForeignKey("src_orgs_ref_node.node_id"),
        nullable=False,
    ),
    Column(
        "names",
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    ),
    Column("status", Text, nullable=True),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    CheckConstraint(
        "status IN ('NONE', 'Active', 'Inactive')",
        name="ck_ver_consolidated_status",
    ),
    Index("ix_ver_consolidated_ref_txto", "ref_node_id", "tx_to"),
    Index(
        "uq_ver_consolidated_ref_current",
        "ref_node_id",
        unique=True,
        postgresql_where=text("tx_to IS NULL"),
    ),
)

# ── 5. src_orgs_rel_child (temporal edge) ───────────────────────────────────

src_orgs_rel_child = Table(
    "src_orgs_rel_child",
    metadata,
    Column("edge_id", BigInteger, primary_key=True, autoincrement=True),
    Column(
        "in_node_id",
        Text,
        ForeignKey("src_orgs_ref_node.node_id"),
        nullable=False,
    ),
    Column(
        "out_node_id",
        Text,
        ForeignKey("src_orgs_ref_node.node_id"),
        nullable=False,
    ),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    Index(
        "ix_rel_child_in_current",
        "in_node_id",
        postgresql_where=text("tx_to IS NULL"),
    ),
    Index(
        "ix_rel_child_out_current",
        "out_node_id",
        postgresql_where=text("tx_to IS NULL"),
    ),
    Index(
        "uq_rel_child_edge",
        "in_node_id",
        "out_node_id",
        "tx_from",
        unique=True,
    ),
)

# ── 6. src_orgs_rel_cross_link (temporal edge with link_type) ───────────────

src_orgs_rel_cross_link = Table(
    "src_orgs_rel_cross_link",
    metadata,
    Column("edge_id", BigInteger, primary_key=True, autoincrement=True),
    Column(
        "in_node_id",
        Text,
        ForeignKey("src_orgs_ref_node.node_id"),
        nullable=False,
    ),
    Column(
        "out_node_id",
        Text,
        ForeignKey("src_orgs_ref_node.node_id"),
        nullable=False,
    ),
    Column("link_type", Text, nullable=False),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    Index(
        "ix_rel_cross_link_in_type_current",
        "in_node_id",
        "link_type",
        postgresql_where=text("tx_to IS NULL"),
    ),
    Index(
        "ix_rel_cross_link_out_current",
        "out_node_id",
        postgresql_where=text("tx_to IS NULL"),
    ),
    Index(
        "uq_rel_cross_link_edge",
        "in_node_id",
        "out_node_id",
        "tx_from",
        unique=True,
    ),
)

# ── Backward-compatible list of table names ─────────────────────────────────

ORGS_TABLES = [
    "src_orgs_ref_node",
    "src_orgs_ver_function",
    "src_orgs_ver_location",
    "src_orgs_ver_consolidated",
    "src_orgs_rel_child",
    "src_orgs_rel_cross_link",
]
