"""SurrealDB Schema Definitions for Controls Management System.

Naming Convention: {layer}_{domain}_{kind}_{name}
- layer: src | ai
- domain: controls (always plural)
- kind: ref | main | ver | rel | model
- name: descriptive name

This module defines all table names as constants and provides schema
definitions for each table following the SurrealDB graph model.

Table Categories:
- src_controls_ref_*      = Reference/lookup tables
- src_controls_main       = Main controls table
- src_controls_versions   = Controls version history
- src_controls_rel_*      = Source relationship edges
- ai_controls_model_*     = AI model output tables
- ai_controls_rel_*       = AI relationship edges

Rule: Every table starts with either src_controls_ or ai_controls_
"""

# ============================================================
# SOURCE REFERENCE TABLES (src_controls_ref_*)
# Lookup/dimension tables for controls domain
# ============================================================

SRC_CONTROLS_REF_RISK_THEME = "src_controls_ref_risk_theme"
SRC_CONTROLS_REF_ORG_FUNCTION = "src_controls_ref_org_function"
SRC_CONTROLS_REF_ORG_LOCATION = "src_controls_ref_org_location"
SRC_CONTROLS_REF_SOX_ASSERTION = "src_controls_ref_sox_assertion"
SRC_CONTROLS_REF_CATEGORY_FLAG = "src_controls_ref_category_flag"

# ============================================================
# SOURCE MAIN TABLES
# Primary entity tables for controls
# ============================================================

SRC_CONTROLS_MAIN = "src_controls_main"
SRC_CONTROLS_VERSIONS = "src_controls_versions"

# ============================================================
# SOURCE RELATIONSHIP TABLES (src_controls_rel_*)
# Graph edges for source data relationships
# ============================================================

SRC_CONTROLS_REL_HAS_RISK_THEME = "src_controls_rel_has_risk_theme"
SRC_CONTROLS_REL_HAS_RELATED_FUNCTION = "src_controls_rel_has_related_function"
SRC_CONTROLS_REL_HAS_RELATED_LOCATION = "src_controls_rel_has_related_location"
SRC_CONTROLS_REL_HAS_SOX_ASSERTION = "src_controls_rel_has_sox_assertion"
SRC_CONTROLS_REL_HAS_CATEGORY_FLAG = "src_controls_rel_has_category_flag"

# ============================================================
# AI MODEL OUTPUT TABLES (ai_controls_model_*)
# AI model outputs with current and version pairs
# ============================================================

AI_CONTROLS_MODEL_TAXONOMY_CURRENT = "ai_controls_model_taxonomy_current"
AI_CONTROLS_MODEL_TAXONOMY_VERSIONS = "ai_controls_model_taxonomy_versions"
AI_CONTROLS_MODEL_ENRICHMENT_CURRENT = "ai_controls_model_enrichment_current"
AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS = "ai_controls_model_enrichment_versions"
AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT = "ai_controls_model_cleaned_text_current"
AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS = "ai_controls_model_cleaned_text_versions"
AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT = "ai_controls_model_embeddings_current"
AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS = "ai_controls_model_embeddings_versions"

# ============================================================
# AI RELATIONSHIP TABLES (ai_controls_rel_*)
# Graph edges linking controls to AI model outputs
# ============================================================

AI_CONTROLS_REL_HAS_TAXONOMY = "ai_controls_rel_has_taxonomy"
AI_CONTROLS_REL_HAS_ENRICHMENT = "ai_controls_rel_has_enrichment"
AI_CONTROLS_REL_HAS_CLEANED_TEXT = "ai_controls_rel_has_cleaned_text"
AI_CONTROLS_REL_HAS_EMBEDDINGS = "ai_controls_rel_has_embeddings"

# ============================================================
# ALL TABLES LIST
# Complete list of all tables in the schema
# ============================================================

ALL_TABLES = [
    # Source reference tables (src_controls_ref_*)
    SRC_CONTROLS_REF_RISK_THEME,
    SRC_CONTROLS_REF_ORG_FUNCTION,
    SRC_CONTROLS_REF_ORG_LOCATION,
    SRC_CONTROLS_REF_SOX_ASSERTION,
    SRC_CONTROLS_REF_CATEGORY_FLAG,
    # Source main tables
    SRC_CONTROLS_MAIN,
    SRC_CONTROLS_VERSIONS,
    # Source relation tables (src_controls_rel_*)
    SRC_CONTROLS_REL_HAS_RISK_THEME,
    SRC_CONTROLS_REL_HAS_RELATED_FUNCTION,
    SRC_CONTROLS_REL_HAS_RELATED_LOCATION,
    SRC_CONTROLS_REL_HAS_SOX_ASSERTION,
    SRC_CONTROLS_REL_HAS_CATEGORY_FLAG,
    # AI model output tables (ai_controls_model_*)
    AI_CONTROLS_MODEL_TAXONOMY_CURRENT,
    AI_CONTROLS_MODEL_TAXONOMY_VERSIONS,
    AI_CONTROLS_MODEL_ENRICHMENT_CURRENT,
    AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS,
    AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT,
    AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS,
    AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT,
    AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS,
    # AI relation tables (ai_controls_rel_*)
    AI_CONTROLS_REL_HAS_TAXONOMY,
    AI_CONTROLS_REL_HAS_ENRICHMENT,
    AI_CONTROLS_REL_HAS_CLEANED_TEXT,
    AI_CONTROLS_REL_HAS_EMBEDDINGS,
]

# ============================================================
# SCHEMA STATEMENTS
# SurrealDB DEFINE statements for all tables, fields, and indexes
# ============================================================

SCHEMA_STATEMENTS = [
    # ============================================================
    # SOURCE REFERENCE TABLES (src_controls_ref_*)
    # Lookup/dimension tables for controls domain
    # ============================================================

    # Risk Theme reference table
    f"DEFINE TABLE {SRC_CONTROLS_REF_RISK_THEME} SCHEMAFULL",
    f"DEFINE FIELD risk_theme_id ON TABLE {SRC_CONTROLS_REF_RISK_THEME} TYPE string",
    f"DEFINE FIELD risk_theme_name ON TABLE {SRC_CONTROLS_REF_RISK_THEME} TYPE string",
    f"DEFINE FIELD taxonomy_number ON TABLE {SRC_CONTROLS_REF_RISK_THEME} TYPE option<string>",
    f"DEFINE INDEX ux_risk_theme_id ON TABLE {SRC_CONTROLS_REF_RISK_THEME} FIELDS risk_theme_id UNIQUE",

    # Organization Function reference table
    f"DEFINE TABLE {SRC_CONTROLS_REF_ORG_FUNCTION} SCHEMAFULL",
    f"DEFINE FIELD function_id ON TABLE {SRC_CONTROLS_REF_ORG_FUNCTION} TYPE string",
    f"DEFINE FIELD function_name ON TABLE {SRC_CONTROLS_REF_ORG_FUNCTION} TYPE string",
    f"DEFINE INDEX ux_org_function_id ON TABLE {SRC_CONTROLS_REF_ORG_FUNCTION} FIELDS function_id UNIQUE",

    # Organization Location reference table
    f"DEFINE TABLE {SRC_CONTROLS_REF_ORG_LOCATION} SCHEMAFULL",
    f"DEFINE FIELD location_id ON TABLE {SRC_CONTROLS_REF_ORG_LOCATION} TYPE string",
    f"DEFINE FIELD location_name ON TABLE {SRC_CONTROLS_REF_ORG_LOCATION} TYPE string",
    f"DEFINE INDEX ux_org_location_id ON TABLE {SRC_CONTROLS_REF_ORG_LOCATION} FIELDS location_id UNIQUE",

    # SOX Assertion reference table
    f"DEFINE TABLE {SRC_CONTROLS_REF_SOX_ASSERTION} SCHEMAFULL",
    f"DEFINE FIELD assertion_name ON TABLE {SRC_CONTROLS_REF_SOX_ASSERTION} TYPE string",
    f"DEFINE INDEX ux_sox_assertion_name ON TABLE {SRC_CONTROLS_REF_SOX_ASSERTION} FIELDS assertion_name UNIQUE",

    # Category Flag reference table
    f"DEFINE TABLE {SRC_CONTROLS_REF_CATEGORY_FLAG} SCHEMAFULL",
    f"DEFINE FIELD flag_name ON TABLE {SRC_CONTROLS_REF_CATEGORY_FLAG} TYPE string",
    f"DEFINE INDEX ux_category_flag_name ON TABLE {SRC_CONTROLS_REF_CATEGORY_FLAG} FIELDS flag_name UNIQUE",

    # ============================================================
    # SOURCE MAIN TABLE (src_controls_main)
    # Central node - uses control_id as record ID
    # Owning hierarchy is embedded (1:1 relationship)
    # ============================================================
    f"DEFINE TABLE {SRC_CONTROLS_MAIN} SCHEMAFULL",
    f"DEFINE FIELD control_id ON TABLE {SRC_CONTROLS_MAIN} TYPE string",
    f"DEFINE FIELD last_modified_on ON TABLE {SRC_CONTROLS_MAIN} TYPE datetime",
    f"DEFINE FIELD control ON TABLE {SRC_CONTROLS_MAIN} FLEXIBLE TYPE object",
    # Owning hierarchy - embedded objects (1:1, where control belongs)
    f"DEFINE FIELD owning_function_hierarchy ON TABLE {SRC_CONTROLS_MAIN} FLEXIBLE TYPE option<object>",
    f"DEFINE FIELD owning_location_hierarchy ON TABLE {SRC_CONTROLS_MAIN} FLEXIBLE TYPE option<object>",
    f"DEFINE FIELD metadata ON TABLE {SRC_CONTROLS_MAIN} FLEXIBLE TYPE object",
    # Parent control is a record link (self-referential)
    f"DEFINE FIELD parent_control ON TABLE {SRC_CONTROLS_MAIN} TYPE option<record<{SRC_CONTROLS_MAIN}>>",
    f"DEFINE INDEX ux_controls_main_control_id ON TABLE {SRC_CONTROLS_MAIN} FIELDS control_id UNIQUE",

    # Source Controls versions (for temporal history)
    f"DEFINE TABLE {SRC_CONTROLS_VERSIONS} SCHEMALESS",
    f"DEFINE FIELD control_id ON TABLE {SRC_CONTROLS_VERSIONS} TYPE string",
    f"DEFINE FIELD version_date ON TABLE {SRC_CONTROLS_VERSIONS} TYPE datetime",
    f"DEFINE FIELD snapshot ON TABLE {SRC_CONTROLS_VERSIONS} TYPE object",
    f"DEFINE INDEX ux_controls_versions_control_date ON TABLE {SRC_CONTROLS_VERSIONS} FIELDS control_id, version_date UNIQUE",

    # ============================================================
    # SOURCE RELATIONSHIP TABLES (src_controls_rel_*)
    # Edges with metadata for source data relationships
    # ============================================================

    # Control -> Risk Theme relationship
    f"DEFINE TABLE {SRC_CONTROLS_REL_HAS_RISK_THEME} TYPE RELATION IN {SRC_CONTROLS_MAIN} OUT {SRC_CONTROLS_REF_RISK_THEME} SCHEMAFULL",
    f"DEFINE FIELD created_at ON TABLE {SRC_CONTROLS_REL_HAS_RISK_THEME} TYPE datetime",
    f"DEFINE FIELD source ON TABLE {SRC_CONTROLS_REL_HAS_RISK_THEME} TYPE string",

    # Control -> Related Function relationship (1:N, impacted functions with comments)
    f"DEFINE TABLE {SRC_CONTROLS_REL_HAS_RELATED_FUNCTION} TYPE RELATION IN {SRC_CONTROLS_MAIN} OUT {SRC_CONTROLS_REF_ORG_FUNCTION} SCHEMAFULL",
    f"DEFINE FIELD created_at ON TABLE {SRC_CONTROLS_REL_HAS_RELATED_FUNCTION} TYPE datetime",
    f"DEFINE FIELD comments ON TABLE {SRC_CONTROLS_REL_HAS_RELATED_FUNCTION} TYPE option<string>",

    # Control -> Related Location relationship (1:N, impacted locations with comments)
    f"DEFINE TABLE {SRC_CONTROLS_REL_HAS_RELATED_LOCATION} TYPE RELATION IN {SRC_CONTROLS_MAIN} OUT {SRC_CONTROLS_REF_ORG_LOCATION} SCHEMAFULL",
    f"DEFINE FIELD created_at ON TABLE {SRC_CONTROLS_REL_HAS_RELATED_LOCATION} TYPE datetime",
    f"DEFINE FIELD comments ON TABLE {SRC_CONTROLS_REL_HAS_RELATED_LOCATION} TYPE option<string>",

    # Control -> SOX Assertion relationship
    f"DEFINE TABLE {SRC_CONTROLS_REL_HAS_SOX_ASSERTION} TYPE RELATION IN {SRC_CONTROLS_MAIN} OUT {SRC_CONTROLS_REF_SOX_ASSERTION} SCHEMAFULL",
    f"DEFINE FIELD created_at ON TABLE {SRC_CONTROLS_REL_HAS_SOX_ASSERTION} TYPE datetime",

    # Control -> Category Flag relationship
    f"DEFINE TABLE {SRC_CONTROLS_REL_HAS_CATEGORY_FLAG} TYPE RELATION IN {SRC_CONTROLS_MAIN} OUT {SRC_CONTROLS_REF_CATEGORY_FLAG} SCHEMAFULL",
    f"DEFINE FIELD created_at ON TABLE {SRC_CONTROLS_REL_HAS_CATEGORY_FLAG} TYPE datetime",

    # ============================================================
    # AI RELATIONSHIP TABLES (ai_controls_rel_*)
    # Edges linking controls to AI model outputs
    # ============================================================

    # Control -> Taxonomy (model output) relationship
    f"DEFINE TABLE {AI_CONTROLS_REL_HAS_TAXONOMY} TYPE RELATION IN {SRC_CONTROLS_MAIN} OUT {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} SCHEMAFULL",
    f"DEFINE FIELD created_at ON TABLE {AI_CONTROLS_REL_HAS_TAXONOMY} TYPE datetime",
    f"DEFINE FIELD model_version ON TABLE {AI_CONTROLS_REL_HAS_TAXONOMY} TYPE option<string>",

    # Control -> Enrichment (model output) relationship
    f"DEFINE TABLE {AI_CONTROLS_REL_HAS_ENRICHMENT} TYPE RELATION IN {SRC_CONTROLS_MAIN} OUT {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} SCHEMAFULL",
    f"DEFINE FIELD created_at ON TABLE {AI_CONTROLS_REL_HAS_ENRICHMENT} TYPE datetime",
    f"DEFINE FIELD model_version ON TABLE {AI_CONTROLS_REL_HAS_ENRICHMENT} TYPE option<string>",

    # Control -> Cleaned Text (model output) relationship
    f"DEFINE TABLE {AI_CONTROLS_REL_HAS_CLEANED_TEXT} TYPE RELATION IN {SRC_CONTROLS_MAIN} OUT {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} SCHEMAFULL",
    f"DEFINE FIELD created_at ON TABLE {AI_CONTROLS_REL_HAS_CLEANED_TEXT} TYPE datetime",
    f"DEFINE FIELD model_version ON TABLE {AI_CONTROLS_REL_HAS_CLEANED_TEXT} TYPE option<string>",

    # Control -> Embeddings (model output) relationship
    f"DEFINE TABLE {AI_CONTROLS_REL_HAS_EMBEDDINGS} TYPE RELATION IN {SRC_CONTROLS_MAIN} OUT {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} SCHEMAFULL",
    f"DEFINE FIELD created_at ON TABLE {AI_CONTROLS_REL_HAS_EMBEDDINGS} TYPE datetime",
    f"DEFINE FIELD model_version ON TABLE {AI_CONTROLS_REL_HAS_EMBEDDINGS} TYPE option<string>",

    # ============================================================
    # AI MODEL CLEANED TEXT (CURRENT + HISTORY) + FTS INDEXES
    # Uses control_id as record ID for easy linking
    # ============================================================
    f"DEFINE TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} SCHEMAFULL",
    f"DEFINE FIELD control_id ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} TYPE string",
    f"DEFINE FIELD hash ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} TYPE string",
    f"DEFINE FIELD effective_at ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} TYPE datetime",
    f"DEFINE FIELD control_description ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD control_title ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD evidence_description ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD local_functional_information ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD control_as_event ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD control_as_issues ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} TYPE option<string>",
    f"DEFINE INDEX ux_cleaned_text_current_control ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} FIELDS control_id UNIQUE",
    f"DEFINE INDEX idx_cleaned_text_current_hash ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} FIELDS hash",
    f"DEFINE INDEX idx_cleaned_text_current_effective_at ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} FIELDS effective_at",

    # FTS Analyzer and Indexes
    "DEFINE ANALYZER control_text TOKENIZERS class FILTERS lowercase, ascii",
    f"DEFINE INDEX fts_ct_desc ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} FIELDS control_description SEARCH ANALYZER control_text BM25 HIGHLIGHTS",
    f"DEFINE INDEX fts_ct_title ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} FIELDS control_title SEARCH ANALYZER control_text BM25 HIGHLIGHTS",
    f"DEFINE INDEX fts_ct_evidence ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} FIELDS evidence_description SEARCH ANALYZER control_text BM25 HIGHLIGHTS",
    f"DEFINE INDEX fts_ct_local ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} FIELDS local_functional_information SEARCH ANALYZER control_text BM25 HIGHLIGHTS",
    f"DEFINE INDEX fts_ct_event ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} FIELDS control_as_event SEARCH ANALYZER control_text BM25 HIGHLIGHTS",
    f"DEFINE INDEX fts_ct_issues ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT} FIELDS control_as_issues SEARCH ANALYZER control_text BM25 HIGHLIGHTS",

    f"DEFINE TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS} SCHEMALESS",
    f"DEFINE FIELD control_id ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS} TYPE string",
    f"DEFINE FIELD hash ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS} TYPE string",
    f"DEFINE FIELD version_date ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS} TYPE datetime",
    f"DEFINE FIELD snapshot ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS} TYPE object",
    f"DEFINE INDEX ux_cleaned_text_versions_control_hash ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS} FIELDS control_id, hash UNIQUE",
    f"DEFINE INDEX idx_cleaned_text_versions_control_date ON TABLE {AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS} FIELDS control_id, version_date",

    # ============================================================
    # AI MODEL EMBEDDINGS (CURRENT + HISTORY), 3072 dims
    # ============================================================
    f"DEFINE TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} SCHEMAFULL",
    f"DEFINE FIELD control_id ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} TYPE string",
    f"DEFINE FIELD hash ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} TYPE string",
    f"DEFINE FIELD effective_at ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} TYPE datetime",
    f"DEFINE FIELD control_description_embedding ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} TYPE option<array<number>> ASSERT $value = NONE OR $value.len() = 3072",
    f"DEFINE FIELD control_title_embedding ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} TYPE option<array<number>> ASSERT $value = NONE OR $value.len() = 3072",
    f"DEFINE FIELD evidence_description_embedding ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} TYPE option<array<number>> ASSERT $value = NONE OR $value.len() = 3072",
    f"DEFINE FIELD local_functional_information_embedding ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} TYPE option<array<number>> ASSERT $value = NONE OR $value.len() = 3072",
    f"DEFINE FIELD control_as_event_embedding ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} TYPE option<array<number>> ASSERT $value = NONE OR $value.len() = 3072",
    f"DEFINE FIELD control_as_issues_embedding ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} TYPE option<array<number>> ASSERT $value = NONE OR $value.len() = 3072",
    f"DEFINE INDEX ux_embeddings_current_control ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} FIELDS control_id UNIQUE",
    f"DEFINE INDEX idx_embeddings_current_hash ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} FIELDS hash",
    f"DEFINE INDEX idx_embeddings_current_effective_at ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT} FIELDS effective_at",

    f"DEFINE TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS} SCHEMALESS",
    f"DEFINE FIELD control_id ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS} TYPE string",
    f"DEFINE FIELD hash ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS} TYPE string",
    f"DEFINE FIELD version_date ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS} TYPE datetime",
    f"DEFINE FIELD snapshot ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS} TYPE object",
    f"DEFINE INDEX ux_embeddings_versions_control_hash ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS} FIELDS control_id, hash UNIQUE",
    f"DEFINE INDEX idx_embeddings_versions_control_date ON TABLE {AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS} FIELDS control_id, version_date",

    # ============================================================
    # AI MODEL TAXONOMY (CURRENT + HISTORY)
    # ============================================================
    f"DEFINE TABLE {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} SCHEMAFULL",
    f"DEFINE FIELD control_id ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} TYPE string",
    f"DEFINE FIELD hash ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} TYPE string",
    f"DEFINE FIELD effective_at ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} TYPE datetime",
    f"DEFINE FIELD primary_nfr_risk_theme ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} TYPE string",
    f"DEFINE FIELD primary_risk_theme_id ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} TYPE string",
    f"DEFINE FIELD secondary_nfr_risk_theme ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} TYPE option<string>",
    f"DEFINE FIELD secondary_risk_theme_id ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} TYPE option<string>",
    f"DEFINE FIELD primary_risk_theme_reasoning_steps ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} TYPE array<string>",
    f"DEFINE FIELD secondary_risk_theme_reasoning_steps ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} TYPE array<string>",
    f"DEFINE INDEX ux_taxonomy_current_control ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} FIELDS control_id UNIQUE",
    f"DEFINE INDEX idx_taxonomy_current_hash ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_CURRENT} FIELDS hash",

    f"DEFINE TABLE {AI_CONTROLS_MODEL_TAXONOMY_VERSIONS} SCHEMALESS",
    f"DEFINE FIELD control_id ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_VERSIONS} TYPE string",
    f"DEFINE FIELD hash ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_VERSIONS} TYPE string",
    f"DEFINE FIELD version_date ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_VERSIONS} TYPE datetime",
    f"DEFINE FIELD snapshot ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_VERSIONS} TYPE object",
    f"DEFINE INDEX ux_taxonomy_versions_control_hash ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_VERSIONS} FIELDS control_id, hash UNIQUE",
    f"DEFINE INDEX idx_taxonomy_versions_control_date ON TABLE {AI_CONTROLS_MODEL_TAXONOMY_VERSIONS} FIELDS control_id, version_date",

    # ============================================================
    # AI MODEL ENRICHMENT (CURRENT + HISTORY)
    # ============================================================
    f"DEFINE TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} SCHEMAFULL",
    f"DEFINE FIELD control_id ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE string",
    f"DEFINE FIELD hash ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE string",
    f"DEFINE FIELD effective_at ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE datetime",
    f"DEFINE FIELD summary ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD what_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD what_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD where_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD where_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD who_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD who_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD when_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD when_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD why_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD why_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD what_why_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD what_why_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD risk_theme_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD risk_theme_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD frequency_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD frequency_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD preventative_detective_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD preventative_detective_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD automation_level_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD automation_level_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD followup_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD followup_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD escalation_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD escalation_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD evidence_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD evidence_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD abbreviations_yes_no ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD abbreviations_details ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD people ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD process ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD product ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD service ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD regulations ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD control_as_issues ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE FIELD control_as_event ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} TYPE option<string>",
    f"DEFINE INDEX ux_enrichment_current_control ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} FIELDS control_id UNIQUE",
    f"DEFINE INDEX idx_enrichment_current_hash ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_CURRENT} FIELDS hash",

    f"DEFINE TABLE {AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS} SCHEMALESS",
    f"DEFINE FIELD control_id ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS} TYPE string",
    f"DEFINE FIELD hash ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS} TYPE string",
    f"DEFINE FIELD version_date ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS} TYPE datetime",
    f"DEFINE FIELD snapshot ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS} TYPE object",
    f"DEFINE INDEX ux_enrichment_versions_control_hash ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS} FIELDS control_id, hash UNIQUE",
    f"DEFINE INDEX idx_enrichment_versions_control_date ON TABLE {AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS} FIELDS control_id, version_date",
]
