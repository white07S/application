"""Data layer models for controls, issues, and actions.

These tables store the processed/ingested data with versioning support.
Each record tracks which upload batch it came from and maintains history.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


# =============================================================================
# Controls Tables
# =============================================================================


class DLControl(Base):
    """Main controls table with core attributes."""

    __tablename__ = "dl_controls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    control_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    version: Mapped[int] = mapped_column(default=1)
    is_current: Mapped[bool] = mapped_column(default=True, index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Core attributes
    control_title: Mapped[str] = mapped_column(Text, nullable=False)
    control_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_control: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    hierarchy_level: Mapped[str] = mapped_column(String(20), nullable=False)
    parent_control_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    preventative_detective: Mapped[str] = mapped_column(String(50), nullable=False)
    manual_automated: Mapped[str] = mapped_column(String(50), nullable=False)
    execution_frequency: Mapped[str] = mapped_column(String(50), nullable=False)
    four_eyes_check: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    evidence_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_available_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    performance_measures_required: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    performance_measures_available_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    control_status: Mapped[str] = mapped_column(String(20), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reason_for_deactivation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_updates: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_modified_on: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Tracking columns
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    record_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_dl_controls_control_id_version", "control_id", "version"),
        Index("ix_dl_controls_batch_current", "batch_id", "is_current"),
    )


class DLControlHierarchy(Base):
    """Control organizational hierarchy (function/location)."""

    __tablename__ = "dl_controls_hierarchy"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    control_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    version: Mapped[int] = mapped_column(default=1)
    is_current: Mapped[bool] = mapped_column(default=True)

    # Function hierarchy
    group_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    group_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    division_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    division_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    unit_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    unit_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    area_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    area_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sector_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sector_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    segment_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    segment_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    function_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    function_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Location hierarchy
    l0_location_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    l0_location_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    region_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    region_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sub_region_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sub_region_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    country_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    country_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    company_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company_short_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DLControlMetadata(Base):
    """Control metadata (owners, assessors, SOX info)."""

    __tablename__ = "dl_controls_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    control_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    version: Mapped[int] = mapped_column(default=1)
    is_current: Mapped[bool] = mapped_column(default=True)

    # Owner information
    control_owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    control_owner_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    control_instance_owner_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    control_administrator: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    control_administrator_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    control_delegate: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    control_delegate_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    control_assessor: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    control_assessor_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_assessor_control_owner: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # SOX/Regulatory
    sox_relevant: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    ccar_relevant: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    bcbs239_relevant: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    ey_reliant: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    sox_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    local_functional_information: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kpci_governance_forum: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    financial_statement_line_item: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    it_application_system_supporting: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    additional_information_on_deactivation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit trail
    control_created_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    control_created_by_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    control_created_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_control_modification_requested_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    last_control_modification_requested_by_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_modification_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    control_status_date_change: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DLControlRiskTheme(Base):
    """Control to risk theme mappings."""

    __tablename__ = "dl_controls_risk_themes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    control_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True)

    risk_theme: Mapped[str] = mapped_column(String(100), nullable=False)
    taxonomy_number: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    risk_theme_number: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dl_controls_risk_themes_control_theme", "control_id", "risk_theme"),
    )


class DLControlCategoryFlag(Base):
    """Control category flags."""

    __tablename__ = "dl_controls_category_flags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    control_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True)

    category_flag: Mapped[str] = mapped_column(String(100), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DLControlSoxAssertion(Base):
    """Control SOX assertions."""

    __tablename__ = "dl_controls_sox_assertions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    control_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True)

    sox_assertion: Mapped[str] = mapped_column(String(100), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DLControlRelatedFunction(Base):
    """Control related functions."""

    __tablename__ = "dl_controls_related_functions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    control_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True)

    related_functions_locations_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_function_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    related_function_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DLControlRelatedLocation(Base):
    """Control related locations."""

    __tablename__ = "dl_controls_related_locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    control_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True)

    related_location_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    related_location_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# =============================================================================
# Issues Tables
# =============================================================================


class DLIssue(Base):
    """Main issues table with core attributes."""

    __tablename__ = "dl_issues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    version: Mapped[int] = mapped_column(default=1)
    is_current: Mapped[bool] = mapped_column(default=True, index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Core attributes
    issue_title: Mapped[str] = mapped_column(Text, nullable=False)
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    control_deficiency: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    symptoms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_description: Mapped[str] = mapped_column(Text, nullable=False)
    success_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    issue_status: Mapped[str] = mapped_column(String(50), nullable=False)
    issue_rag_status: Mapped[str] = mapped_column(String(10), nullable=False)
    issue_rag_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_mitigation_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    current_mitigation_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    mitigation_date_change_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    open_action_plans: Mapped[int] = mapped_column(Integer, nullable=False)
    total_action_plans: Mapped[int] = mapped_column(Integer, nullable=False)
    severity_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    created_on: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_modified_on: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Tracking columns
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    record_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_dl_issues_issue_id_version", "issue_id", "version"),
        Index("ix_dl_issues_batch_current", "batch_id", "is_current"),
    )


class DLIssueHierarchy(Base):
    """Issue organizational hierarchy (function/location)."""

    __tablename__ = "dl_issues_hierarchy"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    version: Mapped[int] = mapped_column(default=1)
    is_current: Mapped[bool] = mapped_column(default=True)

    # Function hierarchy
    group_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    group_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    division_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    division_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    unit_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    unit_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    area_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    area_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sector_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sector_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    segment_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    segment_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    function_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    function_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Location hierarchy
    l0_location_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    l0_location_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    region_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    region_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sub_region_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sub_region_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    country_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    country_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    company_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company_short_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DLIssueAudit(Base):
    """Issue audit information (owners, reviewers, dates)."""

    __tablename__ = "dl_issues_audit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    version: Mapped[int] = mapped_column(default=1)
    is_current: Mapped[bool] = mapped_column(default=True)

    # Owner information
    issue_owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    issue_owner_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    issue_administrator: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    issue_administrator_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    issue_delegate: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    issue_delegate_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Reviewers
    first_level_reviewer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    first_level_reviewer_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    orc_reviewer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    orc_reviewer_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    orc_articulation_check: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    orc_rating_check: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    orc_mitigation_date_check: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    orc_action_plan_check: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    orc_mapping_check: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Regulatory
    regulatory_manager: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    regulatory_manager_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    regulator_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    regulator_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Audit info
    audit_rating: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    audit_report_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    finding_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mra_mria: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Programs
    dsori_program: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gsori_program: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    eandy_relevant: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    operating_committee: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Risk acceptance
    reprioritization_risk_acceptance_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_acceptance_approval_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    category_flags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status dates
    draft_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    open_grace_period_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    open_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Comments
    last_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_comment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_commenter: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    last_commenter_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DLIssueRiskTheme(Base):
    """Issue to risk theme mappings."""

    __tablename__ = "dl_issues_risk_themes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True)

    risk_theme: Mapped[str] = mapped_column(String(100), nullable=False)
    taxonomy_number: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    risk_theme_number: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dl_issues_risk_themes_issue_theme", "issue_id", "risk_theme"),
    )


class DLIssueRelatedFunction(Base):
    """Issue related functions."""

    __tablename__ = "dl_issues_related_functions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True)

    related_function_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    related_function_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DLIssueRelatedLocation(Base):
    """Issue related locations."""

    __tablename__ = "dl_issues_related_locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True)

    related_location_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    related_location_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DLIssueControl(Base):
    """Issue to control linkages."""

    __tablename__ = "dl_issues_controls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True)

    control_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dl_issues_controls_issue_control", "issue_id", "control_id"),
    )


class DLIssueRelatedIssue(Base):
    """Related issues linkages."""

    __tablename__ = "dl_issues_related_issues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True)

    related_issue_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    relationship_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# =============================================================================
# Actions Tables
# =============================================================================


class DLIssueAction(Base):
    """Action plans linked to issues."""

    __tablename__ = "dl_issues_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    composite_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    issue_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    action_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    version: Mapped[int] = mapped_column(default=1)
    is_current: Mapped[bool] = mapped_column(default=True, index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Core attributes
    action_title: Mapped[str] = mapped_column(Text, nullable=False)
    action_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action_status: Mapped[str] = mapped_column(String(50), nullable=False)
    action_rag_status: Mapped[str] = mapped_column(String(10), nullable=False)
    action_rag_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Dates
    current_due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    original_due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    extension_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    extension_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    closed_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reopening_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Owners
    action_owner: Mapped[str] = mapped_column(String(200), nullable=False)
    action_owner_gpn: Mapped[str] = mapped_column(String(20), nullable=False)
    action_administrator: Mapped[str] = mapped_column(String(200), nullable=False)
    action_administrator_gpn: Mapped[str] = mapped_column(String(20), nullable=False)

    # Flags
    minimum_standards_for_closure_met: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    reopen_action: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reopen_flag: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    program_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ubs_change_program: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Audit trail
    created_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_by_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    originator: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    originator_gpn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_on: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_modified_on: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Tracking columns
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    record_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_dl_issues_actions_composite_version", "composite_key", "version"),
        Index("ix_dl_issues_actions_batch_current", "batch_id", "is_current"),
    )


class DLIssueActionHierarchy(Base):
    """Action plan organizational hierarchy."""

    __tablename__ = "dl_issues_actions_hierarchy"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    composite_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    issue_id: Mapped[str] = mapped_column(String(20), nullable=False)
    action_id: Mapped[str] = mapped_column(String(20), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    version: Mapped[int] = mapped_column(default=1)
    is_current: Mapped[bool] = mapped_column(default=True)

    # Function hierarchy
    group_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    group_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    division_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    division_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    unit_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    unit_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    area_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    area_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sector_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sector_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    segment_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    segment_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    function_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    function_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Location hierarchy
    l0_location_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    l0_location_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    region_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    region_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sub_region_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sub_region_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    country_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    country_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    company_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company_short_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# Model Output Tables (for ML model results)
# =============================================================================


class DLControlModelOutput(Base):
    """ML model outputs for controls (NFR taxonomy, enrichment)."""

    __tablename__ = "dl_controls_model_outputs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    control_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    model_run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True, index=True)

    # Cache/version tracking (per technical architecture)
    input_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    output_version: Mapped[int] = mapped_column(default=1)
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # NFR Taxonomy outputs
    risk_theme_option_1_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    risk_theme_option_1: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    risk_theme_option_1_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_theme_option_2_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    risk_theme_option_2: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    risk_theme_option_2_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Enrichment outputs
    control_written_as_issue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    control_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    control_complexity_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Embedding (stored as JSON string for simplicity)
    embedding_vector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")


# =============================================================================
# Reference Data Tables (Context Providers)
# =============================================================================


class DLNFRTaxonomy(Base):
    """NFR Risk Taxonomy reference data.

    This is a context provider table that stores the NFR risk taxonomy
    used for classifying issues, controls, and actions by risk theme.
    Per technical architecture: read from context_providers/nfr_taxonomies/ folder.
    """

    __tablename__ = "dl_nfr_taxonomy"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    taxonomy_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    theme_name: Mapped[str] = mapped_column(String(200), nullable=False)
    theme_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of keywords
    parent_theme_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Versioning for reference data (per technical architecture)
    version: Mapped[int] = mapped_column(default=1)
    is_current: Mapped[bool] = mapped_column(default=True, index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_modified_on: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_dl_nfr_taxonomy_id_version", "taxonomy_id", "version"),
    )


class DLIssueModelOutput(Base):
    """ML model outputs for issues (NFR taxonomy, enrichment)."""

    __tablename__ = "dl_issues_model_outputs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    model_run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True, index=True)

    # Cache/version tracking (per technical architecture)
    input_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    output_version: Mapped[int] = mapped_column(default=1)
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # NFR Taxonomy outputs
    risk_theme_option_1_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    risk_theme_option_1: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    risk_theme_option_1_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_theme_option_2_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    risk_theme_option_2: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    risk_theme_option_2_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Enrichment outputs
    issue_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity_assessment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Embedding (stored as JSON string for simplicity)
    embedding_vector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")
