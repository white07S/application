"""Combined PostgreSQL schema definitions — imports from per-domain schema files.

Each domain owns its own schema (SQLAlchemy Table objects):
- server/pipelines/orgs/schema.py      (6 tables)
- server/pipelines/risks/schema.py     (5 tables)
- server/pipelines/controls/schema.py  (11 tables + FTS trigger)

The shared MetaData instance (from schema/base.py) is the single source of truth.
Alembic auto-generates migrations from it.
"""

from server.pipelines.schema.base import metadata  # noqa: F401

# Import table objects so they register on the shared metadata
from server.pipelines.orgs.schema import (  # noqa: F401
    ORGS_TABLES,
    src_orgs_ref_node,
    src_orgs_ver_function,
    src_orgs_ver_location,
    src_orgs_ver_consolidated,
    src_orgs_rel_child,
    src_orgs_rel_cross_link,
)
from server.pipelines.risks.schema import (  # noqa: F401
    RISKS_TABLES,
    src_risks_ref_taxonomy,
    src_risks_ver_taxonomy,
    src_risks_ref_theme,
    src_risks_ver_theme,
    src_risks_rel_taxonomy_theme,
)
from server.pipelines.controls.schema import (  # noqa: F401
    CONTROLS_TABLES,
    FTS_TRIGGER_SQL,
    FTS_TRIGGER_DROP_SQL,
    src_controls_ref_control,
    src_controls_ver_control,
    src_controls_rel_parent,
    src_controls_rel_owns_function,
    src_controls_rel_owns_location,
    src_controls_rel_related_function,
    src_controls_rel_related_location,
    src_controls_rel_risk_theme,
    ai_controls_model_enrichment,
    ai_controls_model_taxonomy,
    ai_controls_model_clean_text,
)

# All table names (for iteration, drop operations, etc.)
ALL_TABLES = ORGS_TABLES + RISKS_TABLES + CONTROLS_TABLES

# Context provider tables (used for startup verification)
CONTEXT_PROVIDER_TABLES = ORGS_TABLES + RISKS_TABLES
