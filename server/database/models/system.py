"""System layer database models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class DataSource(Base):
    """Model for data_sources table.

    Stores metadata about different data sources in the system.
    """
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # 'issues', 'controls', 'actions'
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'transactional', 'reference'
    primary_key_column: Mapped[str] = mapped_column(String(100), nullable=False)
    last_modified_column: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    schema_registries: Mapped[list["SchemaRegistry"]] = relationship(
        "SchemaRegistry", back_populates="data_source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DataSource(id={self.id}, source_code='{self.source_code}')>"


class SchemaRegistry(Base):
    """Model for schema_registry table.

    Stores versioned schema definitions for each data source.
    """
    __tablename__ = "schema_registry"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), nullable=False)
    version: Mapped[int] = mapped_column(default=1)
    schema_definition: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    is_active: Mapped[bool] = mapped_column(default=True)
    is_locked: Mapped[bool] = mapped_column(default=False)
    locked_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Unique constraint on data_source_id and version
    __table_args__ = (UniqueConstraint('data_source_id', 'version', name='uq_schema_registry_source_version'),)

    # Relationships
    data_source: Mapped["DataSource"] = relationship("DataSource", back_populates="schema_registries")

    def __repr__(self) -> str:
        return f"<SchemaRegistry(id={self.id}, data_source_id={self.data_source_id}, version={self.version})>"
