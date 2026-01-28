"""Database initialization and seeding module."""
import json
from datetime import datetime
from sqlalchemy.orm import Session
from .engine import engine
from .models import Base, DataSource, DatasetConfig, ModelConfig, IngestionConfig, IngestionFieldMapping
from .models.data_layer import DLNFRTaxonomy

def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)

def seed_data_sources(db: Session) -> dict[str, int]:
    """Seed initial data sources. Returns mapping of source_code to id."""

    sources = [
        {
            "source_code": "issues",
            "source_name": "NFR Issues",
            "source_type": "transactional",
            "primary_key_column": "issue_id",
            "last_modified_column": "last_modified_on",
        },
        {
            "source_code": "controls",
            "source_name": "Key Controls",
            "source_type": "transactional",
            "primary_key_column": "control_id",
            "last_modified_column": "last_modified_on",
        },
        {
            "source_code": "actions",
            "source_name": "Action Plans",
            "source_type": "transactional",
            "primary_key_column": "action_id",
            "last_modified_column": "last_modified_on",
        },
        {
            "source_code": "nfr_taxonomy",
            "source_name": "NFR Risk Taxonomy",
            "source_type": "reference",
            "primary_key_column": "taxonomy_id",
            "last_modified_column": "last_modified_on",
        },
    ]

    source_ids = {}
    for source_data in sources:
        existing = db.query(DataSource).filter_by(source_code=source_data["source_code"]).first()
        if not existing:
            source = DataSource(**source_data)
            db.add(source)
            db.flush()
            source_ids[source.source_code] = source.id
        else:
            source_ids[existing.source_code] = existing.id

    return source_ids

def seed_dataset_config(db: Session, source_ids: dict[str, int]):
    """Seed initial dataset configurations."""

    configs = {
        "issues": [
            ("file_count", "4"),
            ("fts_columns", json.dumps(["issue_title", "control_deficiency", "root_cause", "symptoms", "risk"])),
            ("embedding_columns", json.dumps(["issue_title", "control_deficiency"])),
        ],
        "controls": [
            ("file_count", "1"),
            ("fts_columns", json.dumps(["control_title", "control_description"])),
            ("embedding_columns", json.dumps(["control_title", "control_description"])),
            ("enrichment_fts_columns", json.dumps(["control_written_as_issue", "control_summary"])),
            ("enrichment_embedding_columns", json.dumps(["control_written_as_issue"])),
        ],
        "actions": [
            ("file_count", "1"),
            ("fts_columns", json.dumps(["action_title", "action_description"])),
            ("embedding_columns", json.dumps(["action_title"])),
        ],
    }

    for source_code, config_items in configs.items():
        data_source_id = source_ids.get(source_code)
        if not data_source_id:
            continue

        for config_key, config_value in config_items:
            existing = db.query(DatasetConfig).filter_by(
                data_source_id=data_source_id,
                config_key=config_key
            ).first()
            if not existing:
                db.add(DatasetConfig(
                    data_source_id=data_source_id,
                    config_key=config_key,
                    config_value=config_value
                ))

def seed_model_config(db: Session, source_ids: dict[str, int]):
    """Seed initial model configurations."""

    model_configs = [
        # NFR Taxonomy for issues
        {
            "model_function": "nfr_taxonomy",
            "data_source_id": source_ids.get("issues"),
            "input_columns": json.dumps(["issue_title", "control_deficiency", "risk"]),
            "output_schema": json.dumps({
                "risk_theme_option_1_id": "integer",
                "risk_theme_option_1": "string",
                "risk_theme_option_1_reasoning": "array",
                "risk_theme_option_2_id": "integer",
                "risk_theme_option_2": "string",
                "risk_theme_option_2_reasoning": "array"
            }),
            "current_model_version": "v1"
        },
        # NFR Taxonomy for controls
        {
            "model_function": "nfr_taxonomy",
            "data_source_id": source_ids.get("controls"),
            "input_columns": json.dumps(["control_title", "control_description"]),
            "output_schema": json.dumps({
                "risk_theme_option_1_id": "integer",
                "risk_theme_option_1": "string",
                "risk_theme_option_1_reasoning": "array",
                "risk_theme_option_2_id": "integer",
                "risk_theme_option_2": "string",
                "risk_theme_option_2_reasoning": "array"
            }),
            "current_model_version": "v1"
        },
        # Enrichment for controls
        {
            "model_function": "enrichment",
            "data_source_id": source_ids.get("controls"),
            "input_columns": json.dumps(["control_title", "control_description", "preventative_detective", "manual_automated"]),
            "output_schema": json.dumps({
                "control_written_as_issue": "string",
                "control_summary": "string",
                "control_complexity_score": "integer"
            }),
            "current_model_version": "v1"
        },
        # Enrichment for issues
        {
            "model_function": "enrichment",
            "data_source_id": source_ids.get("issues"),
            "input_columns": json.dumps(["issue_title", "control_deficiency", "root_cause", "symptoms"]),
            "output_schema": json.dumps({
                "issue_summary": "string",
                "recommended_actions": "array",
                "severity_assessment": "string"
            }),
            "current_model_version": "v1"
        },
        # Embeddings for controls
        {
            "model_function": "embeddings",
            "data_source_id": source_ids.get("controls"),
            "input_columns": json.dumps(["control_title", "control_description", "control_written_as_issue"]),
            "output_schema": json.dumps({
                "embedding_vector": "array[3072]"
            }),
            "current_model_version": "v1"
        },
        # Embeddings for issues
        {
            "model_function": "embeddings",
            "data_source_id": source_ids.get("issues"),
            "input_columns": json.dumps(["issue_title", "control_deficiency"]),
            "output_schema": json.dumps({
                "embedding_vector": "array[3072]"
            }),
            "current_model_version": "v1"
        },
    ]

    for config in model_configs:
        if not config.get("data_source_id"):
            continue
        existing = db.query(ModelConfig).filter_by(
            model_function=config["model_function"],
            data_source_id=config["data_source_id"]
        ).first()
        if not existing:
            db.add(ModelConfig(**config))

def seed_ingestion_config(db: Session, source_ids: dict[str, int]):
    """Seed ingestion configurations for parquet-to-table mappings.

    These configs define how each parquet file from validation
    maps to data layer tables.
    """
    # Controls ingestion configs (8 tables)
    controls_configs = [
        {
            "name": "controls_main",
            "description": "Main control records with core attributes",
            "source_parquet_name": "controls_main.parquet",
            "target_table_name": "dl_controls",
            "primary_key_columns": json.dumps(["control_id"]),
            "processing_order": 1,
        },
        {
            "name": "controls_hierarchy",
            "description": "Control organizational hierarchy (function/location)",
            "source_parquet_name": "controls_hierarchy.parquet",
            "target_table_name": "dl_controls_hierarchy",
            "primary_key_columns": json.dumps(["control_id"]),
            "processing_order": 2,
        },
        {
            "name": "controls_metadata",
            "description": "Control metadata (owners, assessors, SOX info)",
            "source_parquet_name": "controls_metadata.parquet",
            "target_table_name": "dl_controls_metadata",
            "primary_key_columns": json.dumps(["control_id"]),
            "processing_order": 3,
        },
        {
            "name": "controls_risk_themes",
            "description": "Control to risk theme mappings",
            "source_parquet_name": "controls_risk_theme.parquet",
            "target_table_name": "dl_controls_risk_themes",
            "primary_key_columns": json.dumps(["control_id", "risk_theme"]),
            "processing_order": 4,
        },
        {
            "name": "controls_category_flags",
            "description": "Control category flags",
            "source_parquet_name": "controls_category_flags.parquet",
            "target_table_name": "dl_controls_category_flags",
            "primary_key_columns": json.dumps(["control_id", "category_flag"]),
            "processing_order": 5,
        },
        {
            "name": "controls_sox_assertions",
            "description": "Control SOX assertions",
            "source_parquet_name": "controls_sox_assertions.parquet",
            "target_table_name": "dl_controls_sox_assertions",
            "primary_key_columns": json.dumps(["control_id", "sox_assertion"]),
            "processing_order": 6,
        },
        {
            "name": "controls_related_functions",
            "description": "Control related functions",
            "source_parquet_name": "controls_related_functions.parquet",
            "target_table_name": "dl_controls_related_functions",
            "primary_key_columns": json.dumps(["control_id", "related_function_id"]),
            "processing_order": 7,
        },
        {
            "name": "controls_related_locations",
            "description": "Control related locations",
            "source_parquet_name": "controls_related_locations.parquet",
            "target_table_name": "dl_controls_related_locations",
            "primary_key_columns": json.dumps(["control_id", "related_location_id"]),
            "processing_order": 8,
        },
    ]

    # Issues ingestion configs (8 tables)
    issues_configs = [
        {
            "name": "issues_main",
            "description": "Main issue records with core attributes",
            "source_parquet_name": "issues_main.parquet",
            "target_table_name": "dl_issues",
            "primary_key_columns": json.dumps(["issue_id"]),
            "processing_order": 1,
        },
        {
            "name": "issues_hierarchy",
            "description": "Issue organizational hierarchy (function/location)",
            "source_parquet_name": "issues_hierarchy.parquet",
            "target_table_name": "dl_issues_hierarchy",
            "primary_key_columns": json.dumps(["issue_id"]),
            "processing_order": 2,
        },
        {
            "name": "issues_audit",
            "description": "Issue audit information (owners, reviewers, dates)",
            "source_parquet_name": "issues_audit.parquet",
            "target_table_name": "dl_issues_audit",
            "primary_key_columns": json.dumps(["issue_id"]),
            "processing_order": 3,
        },
        {
            "name": "issues_risk_themes",
            "description": "Issue to risk theme mappings",
            "source_parquet_name": "issues_risk_theme.parquet",
            "target_table_name": "dl_issues_risk_themes",
            "primary_key_columns": json.dumps(["issue_id", "risk_theme"]),
            "processing_order": 4,
        },
        {
            "name": "issues_related_functions",
            "description": "Issue related functions",
            "source_parquet_name": "issues_related_functions.parquet",
            "target_table_name": "dl_issues_related_functions",
            "primary_key_columns": json.dumps(["issue_id", "related_function_id"]),
            "processing_order": 5,
        },
        {
            "name": "issues_related_locations",
            "description": "Issue related locations",
            "source_parquet_name": "issues_related_locations.parquet",
            "target_table_name": "dl_issues_related_locations",
            "primary_key_columns": json.dumps(["issue_id", "related_location_id"]),
            "processing_order": 6,
        },
        {
            "name": "issues_controls",
            "description": "Issue to control linkages",
            "source_parquet_name": "issues_controls.parquet",
            "target_table_name": "dl_issues_controls",
            "primary_key_columns": json.dumps(["issue_id", "control_id"]),
            "processing_order": 7,
        },
        {
            "name": "issues_related_issues",
            "description": "Related issues linkages",
            "source_parquet_name": "issues_related_issues.parquet",
            "target_table_name": "dl_issues_related_issues",
            "primary_key_columns": json.dumps(["issue_id", "related_issue_id"]),
            "processing_order": 8,
        },
    ]

    # Actions ingestion configs (2 tables)
    actions_configs = [
        {
            "name": "issues_actions",
            "description": "Action plans linked to issues",
            "source_parquet_name": "issues_actions.parquet",
            "target_table_name": "dl_issues_actions",
            "primary_key_columns": json.dumps(["composite_key"]),
            "processing_order": 1,
        },
        {
            "name": "issues_actions_hierarchy",
            "description": "Action plan organizational hierarchy",
            "source_parquet_name": "issues_actions_hierarchy.parquet",
            "target_table_name": "dl_issues_actions_hierarchy",
            "primary_key_columns": json.dumps(["composite_key"]),
            "processing_order": 2,
        },
    ]

    # Map data source to configs
    all_configs = [
        ("controls", controls_configs),
        ("issues", issues_configs),
        ("actions", actions_configs),
    ]

    for source_code, configs in all_configs:
        data_source_id = source_ids.get(source_code)
        if not data_source_id:
            continue

        for config_data in configs:
            existing = db.query(IngestionConfig).filter_by(name=config_data["name"]).first()
            if not existing:
                db.add(IngestionConfig(
                    data_source_id=data_source_id,
                    version_strategy="snapshot",
                    **config_data
                ))


def seed_nfr_taxonomy(db: Session):
    """Seed NFR Risk Taxonomy reference data.

    Per technical architecture, this is a context provider that would normally
    be read from context_providers/nfr_taxonomies/ folder. For initial setup,
    we seed the standard NFR taxonomy themes.
    """
    # NFR Risk Taxonomy Reference
    # Format: (taxonomy_id, theme_name, keywords, description)
    taxonomy_data = [
        (1, "Technology Production Stability",
         ["system", "outage", "availability", "infrastructure", "platform", "production", "stability", "downtime"],
         "Risks related to technology systems availability, stability, and production environment issues"),
        (2, "Cyber and Information Security",
         ["cyber", "security", "breach", "vulnerability", "attack", "data protection", "malware", "phishing", "intrusion"],
         "Risks related to cybersecurity threats, data breaches, and information security vulnerabilities"),
        (3, "Data Management",
         ["data", "quality", "governance", "retention", "privacy", "gdpr", "data integrity", "data loss"],
         "Risks related to data quality, governance, privacy, and management practices"),
        (4, "Technology Change Management",
         ["change", "deployment", "release", "upgrade", "migration", "implementation", "rollout", "patch"],
         "Risks related to technology changes, deployments, upgrades, and system migrations"),
        (5, "Third Party Management",
         ["vendor", "third party", "supplier", "outsourcing", "contractor", "service provider", "external"],
         "Risks related to third-party vendors, suppliers, and outsourced services"),
        (6, "Financial Crime Prevention",
         ["fraud", "financial crime", "aml", "kyc", "sanctions", "money laundering", "bribery", "corruption"],
         "Risks related to fraud, money laundering, sanctions violations, and financial crimes"),
        (7, "Conduct Risk",
         ["conduct", "mis-selling", "customer", "complaint", "suitability", "fair treatment", "ethics"],
         "Risks related to employee conduct, customer treatment, and ethical business practices"),
        (8, "Regulatory Compliance",
         ["regulatory", "compliance", "regulation", "audit", "examination", "legal", "supervisory"],
         "Risks related to regulatory requirements, compliance obligations, and audit findings"),
        (9, "Business Continuity",
         ["continuity", "disaster", "recovery", "resilience", "backup", "crisis", "emergency"],
         "Risks related to business continuity planning, disaster recovery, and operational resilience"),
        (10, "Process Execution",
         ["process", "manual", "error", "operational", "procedure", "workflow", "human error", "execution"],
         "Risks related to process failures, manual errors, and operational execution issues"),
    ]

    for taxonomy_id, theme_name, keywords, description in taxonomy_data:
        existing = db.query(DLNFRTaxonomy).filter_by(taxonomy_id=taxonomy_id, is_current=True).first()
        if not existing:
            taxonomy = DLNFRTaxonomy(
                taxonomy_id=taxonomy_id,
                theme_name=theme_name,
                theme_description=description,
                keywords=json.dumps(keywords),
                hierarchy_level=1,
                is_active=True,
                version=1,
                is_current=True,
                valid_from=datetime.utcnow(),
                last_modified_on=datetime.utcnow(),
            )
            db.add(taxonomy)


def init_database():
    """Initialize database: create tables and seed data."""
    from .engine import SessionLocal

    # Create all tables
    create_tables()

    # Seed data
    db = SessionLocal()
    try:
        source_ids = seed_data_sources(db)
        seed_dataset_config(db, source_ids)
        seed_model_config(db, source_ids)
        seed_ingestion_config(db, source_ids)
        seed_nfr_taxonomy(db)
        db.commit()
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
