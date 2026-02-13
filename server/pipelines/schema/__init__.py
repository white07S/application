"""PostgreSQL schema module for all domains (orgs, risks, controls).

Schema is managed by Alembic. This package provides:
- Table definitions via SQLAlchemy Core (in submodules)
- Runtime verification (context providers loaded, Alembic at head)

Import table objects directly from domain schema modules:
    from server.pipelines.orgs.schema import src_orgs_ref_node
    from server.pipelines.controls.schema import src_controls_ver_control

Or import aggregated lists from definitions:
    from server.pipelines.schema.definitions import ALL_TABLES, metadata
"""
