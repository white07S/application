"""Pydantic validation models for controls JSONL records.

Defines the schema for one line of controls JSONL. Used during upload
validation and ingestion to ensure data integrity.
"""

import re
from typing import List

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    field_validator,
    model_validator,
)

CONTROL_ID_PATTERN = r"^CTRL-\d{10}$"
CONTROL_ID_RE = re.compile(CONTROL_ID_PATTERN)


class RelatedFunction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    related_function_id: StrictStr | None
    related_functions_locations_comments: StrictStr | None

    @model_validator(mode="after")
    def _at_least_one_value(self) -> "RelatedFunction":
        if self.related_function_id is None and self.related_functions_locations_comments is None:
            raise ValueError("related_functions entry must have at least one non-null field")
        return self


class RelatedLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    related_location_id: StrictStr | None
    related_functions_locations_comments: StrictStr | None

    @model_validator(mode="after")
    def _at_least_one_value(self) -> "RelatedLocation":
        if self.related_location_id is None and self.related_functions_locations_comments is None:
            raise ValueError("related_locations entry must have at least one non-null field")
        return self


class RiskTheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_theme: StrictStr | None
    taxonomy_number: StrictStr | None
    risk_theme_number: StrictStr | None

    @model_validator(mode="after")
    def _at_least_one_value(self) -> "RiskTheme":
        if self.risk_theme is None and self.taxonomy_number is None and self.risk_theme_number is None:
            raise ValueError("risk_theme entry must have at least one non-null field")
        return self


class ControlRecord(BaseModel):
    """Schema for one line of controls JSONL.

    All top-level keys must be present (even if null/empty list)
    to keep the JSONL stable for downstream consumers.
    """

    model_config = ConfigDict(extra="forbid")

    # ---- core
    control_id: StrictStr = Field(pattern=CONTROL_ID_PATTERN)
    owning_organization_function_id: StrictStr | None
    owning_organization_location_id: StrictStr | None

    control_title: StrictStr | None
    control_description: StrictStr | None

    key_control: StrictBool | None
    hierarchy_level: StrictStr | None
    parent_control_id: StrictStr | None
    preventative_detective: StrictStr | None
    manual_automated: StrictStr | None
    execution_frequency: StrictStr | None
    four_eyes_check: StrictBool | None
    evidence_description: StrictStr | None
    evidence_available_from: StrictStr | None
    performance_measures_required: StrictBool | None
    performance_measures_available_from: StrictStr | None
    control_status: StrictStr | None
    valid_from: StrictStr | None
    valid_until: StrictStr | None
    reason_for_deactivation: StrictStr | None
    status_updates: StrictStr | None
    last_modified_on: StrictStr | None

    # ---- metadata
    control_owner: StrictStr | None
    control_owner_gpn: StrictStr | None
    control_instance_owner_role: StrictStr | None
    control_administrator: List[StrictStr]
    control_administrator_gpn: List[StrictStr]
    control_delegate: StrictStr | None
    control_delegate_gpn: StrictStr | None
    control_assessor: StrictStr | None
    control_assessor_gpn: StrictStr | None
    is_assessor_control_owner: StrictBool | None
    sox_relevant: StrictBool | None
    ccar_relevant: StrictBool | None
    bcbs239_relevant: StrictBool | None
    ey_reliant: StrictBool | None
    sox_rationale: StrictStr | None
    local_functional_information: StrictStr | None
    kpci_governance_forum: StrictStr | None
    financial_statement_line_item: StrictStr | None
    it_application_system_supporting_control_instance: StrictStr | None
    additional_information_on_deactivation: StrictStr | None
    control_created_by: StrictStr | None
    control_created_by_gpn: StrictStr | None
    control_created_on: StrictStr | None
    last_control_modification_requested_by: StrictStr | None
    last_control_modification_requested_by_gpn: StrictStr | None
    last_modification_on: StrictStr | None
    control_status_date_change: StrictStr | None

    # ---- 1:N tables
    related_functions: List[RelatedFunction]
    related_locations: List[RelatedLocation]
    risk_theme: List[RiskTheme]
    category_flags: List[StrictStr]
    sox_assertions: List[StrictStr]

    @field_validator("parent_control_id")
    @classmethod
    def _validate_parent_control_id(cls, v: StrictStr | None) -> StrictStr | None:
        if v is None:
            return None
        if not CONTROL_ID_RE.match(v):
            raise ValueError("parent_control_id must match CTRL-##########")
        return v

    @model_validator(mode="after")
    def _validate_parallel_admin_lists(self) -> "ControlRecord":
        if len(self.control_administrator) != len(self.control_administrator_gpn):
            raise ValueError(
                "control_administrator and control_administrator_gpn must be parallel arrays with same length"
            )
        return self
