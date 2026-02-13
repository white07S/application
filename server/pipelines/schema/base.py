"""Shared SQLAlchemy metadata for all domain and jobs tables.

Every schema module (orgs, risks, controls) and the jobs ORM models
register their tables on this single MetaData instance so that Alembic
can manage all tables in one migration chain.
"""

from sqlalchemy import MetaData

metadata = MetaData()
