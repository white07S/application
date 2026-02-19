"""SQLAlchemy table definitions for the risks domain.

5 tables: ref_taxonomy, ver_taxonomy, ref_theme, ver_theme, rel_taxonomy_theme.
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

# ── 1. src_risks_ref_taxonomy ───────────────────────────────────────────

src_risks_ref_taxonomy = Table(
    "src_risks_ref_taxonomy",
    metadata,
    Column("taxonomy_id", Text, primary_key=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=text("now()"),
    ),
)

# ── 2. src_risks_ver_taxonomy ───────────────────────────────────────────

src_risks_ver_taxonomy = Table(
    "src_risks_ver_taxonomy",
    metadata,
    Column("ver_id", BigInteger, primary_key=True, autoincrement=True),
    Column(
        "ref_taxonomy_id",
        Text,
        ForeignKey("src_risks_ref_taxonomy.taxonomy_id"),
        nullable=False,
    ),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    CheckConstraint(
        "tx_to IS NULL OR tx_to > tx_from",
        name="ck_ver_taxonomy_tx_range",
    ),
    Index(
        "ix_ver_taxonomy_ref_tx_to",
        "ref_taxonomy_id",
        "tx_to",
    ),
    Index(
        "ix_ver_taxonomy_ref_current",
        "ref_taxonomy_id",
        unique=True,
        postgresql_where=text("tx_to IS NULL"),
    ),
)

# ── 3. src_risks_ref_theme ──────────────────────────────────────────────

src_risks_ref_theme = Table(
    "src_risks_ref_theme",
    metadata,
    Column("theme_id", Text, primary_key=True),
    Column("source_id", Text, nullable=False),
    Column(
        "parent_theme_id",
        Text,
        ForeignKey("src_risks_ref_theme.theme_id"),
        nullable=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=text("now()"),
    ),
    Index(
        "ix_ref_theme_parent",
        "parent_theme_id",
        postgresql_where=text("parent_theme_id IS NOT NULL"),
    ),
)

# ── 4. src_risks_ver_theme ──────────────────────────────────────────────

src_risks_ver_theme = Table(
    "src_risks_ver_theme",
    metadata,
    Column("ver_id", BigInteger, primary_key=True, autoincrement=True),
    Column(
        "ref_theme_id",
        Text,
        ForeignKey("src_risks_ref_theme.theme_id"),
        nullable=False,
    ),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("mapping_considerations", Text, nullable=False),
    Column(
        "status",
        Text,
        CheckConstraint(
            "status IN ('active', 'expired')",
            name="ck_ver_theme_status",
        ),
        nullable=False,
    ),
    Column("tx_from", DateTime(timezone=True), nullable=False),
    Column("tx_to", DateTime(timezone=True), nullable=True),
    CheckConstraint(
        "tx_to IS NULL OR tx_to > tx_from",
        name="ck_ver_theme_tx_range",
    ),
    Index(
        "ix_ver_theme_ref_tx_to",
        "ref_theme_id",
        "tx_to",
    ),
    Index(
        "ix_ver_theme_ref_current",
        "ref_theme_id",
        unique=True,
        postgresql_where=text("tx_to IS NULL"),
    ),
)

# ── 5. src_risks_rel_taxonomy_theme (time-invariant mapping) ────────────

src_risks_rel_taxonomy_theme = Table(
    "src_risks_rel_taxonomy_theme",
    metadata,
    Column(
        "taxonomy_id",
        Text,
        ForeignKey("src_risks_ref_taxonomy.taxonomy_id"),
        nullable=False,
        primary_key=True,
    ),
    Column(
        "theme_id",
        Text,
        ForeignKey("src_risks_ref_theme.theme_id"),
        nullable=False,
        primary_key=True,
    ),
)

# ── Export list of all table names ──────────────────────────────────────

RISKS_TABLES = [
    "src_risks_ref_taxonomy",
    "src_risks_ver_taxonomy",
    "src_risks_ref_theme",
    "src_risks_ver_theme",
    "src_risks_rel_taxonomy_theme",
]
