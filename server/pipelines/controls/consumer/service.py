"""Consumer service for querying controls data from SurrealDB with graph traversal.

This module provides the ControlsConsumer class for querying controls data
using graph traversal and temporal access patterns.

Example:
    from server.pipelines.controls.consumer import ControlsConsumer

    async with ControlsConsumer() as consumer:
        # Get control with all relationships
        record = await consumer.get_control_with_relationships("CTRL-001")

        # Get record as of specific date
        historical = await consumer.get_record_as_of_date("CTRL-001", "2026-01-15")

        # Get complete assembled record
        complete = await consumer.get_complete_control_record("CTRL-001")
"""

from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union

from surrealdb import AsyncSurreal

from server.config.settings import get_settings
from server.config.surrealdb import SurrealDBConnectionError
from server.logging_config import get_logger
from server.pipelines.controls.schema import (
    SRC_CONTROLS_MAIN,
    SRC_CONTROLS_VERSIONS,
    AI_CONTROLS_MODEL_TAXONOMY_CURRENT,
    AI_CONTROLS_MODEL_TAXONOMY_VERSIONS,
    AI_CONTROLS_MODEL_ENRICHMENT_CURRENT,
    AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS,
    AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT,
    AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS,
    AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT,
    AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS,
    SRC_CONTROLS_REF_RISK_THEME,
    SRC_CONTROLS_REF_ORG_FUNCTION,
    SRC_CONTROLS_REF_ORG_LOCATION,
    SRC_CONTROLS_REF_SOX_ASSERTION,
    SRC_CONTROLS_REF_CATEGORY_FLAG,
    ALL_TABLES,
)
from .models import (
    ControlRecord,
    ControlWithRelationships,
    ControlHistory,
    CurrentSnapshot,
)
from .queries import (
    normalize_control_id_for_record,
    normalize_risk_theme_id_for_record,
    extract_list_from_result,
    extract_single_from_result,
    get_risk_themes_query,
    get_functions_query,
    get_locations_query,
    get_sox_assertions_query,
    get_category_flags_query,
    get_taxonomy_query,
    get_enrichment_query,
    get_clean_text_query,
    get_embeddings_query,
    get_controls_by_risk_theme_query,
    get_controls_by_function_query,
    get_controls_by_location_query,
    get_control_graph_query,
    VERSION_EXACT_MATCH_QUERY,
    VERSION_BEFORE_DATE_QUERY,
    CURRENT_RECORD_QUERY,
    RECORD_HISTORY_QUERY,
    TABLE_SELECT_ALL_QUERY,
)


logger = get_logger(name=__name__)


class ControlsConsumer:
    """Consumer for querying controls data with temporal access patterns and graph traversal.

    Provides methods for:
    - Graph traversal queries (get control with relationships, reverse lookups)
    - Temporal queries (get record as of date, get history)
    - Snapshot queries (get current state, get counts)
    - Complete record assembly (get all data for a control)

    Usage:
        async with ControlsConsumer() as consumer:
            record = await consumer.get_control_with_relationships("CTRL-001")
    """

    def __init__(self):
        """Initialize consumer with settings."""
        self.settings = get_settings()
        self.db: Optional[AsyncSurreal] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def connect(self):
        """Connect to SurrealDB."""
        try:
            self.db = AsyncSurreal(self.settings.surrealdb_url)
            await self.db.connect()
            await self.db.signin({
                "username": self.settings.surrealdb_user,
                "password": self.settings.surrealdb_pass,
            })
            await self.db.use(
                self.settings.surrealdb_namespace,
                self.settings.surrealdb_database
            )
            logger.info("ControlsConsumer connected to SurrealDB")
        except Exception as e:
            error_msg = f"Failed to connect to SurrealDB: {str(e)}"
            logger.error(error_msg)
            raise SurrealDBConnectionError(error_msg) from e

    async def close(self):
        """Close the database connection."""
        if self.db:
            try:
                await self.db.close()
                self.db = None
                logger.info("ControlsConsumer disconnected from SurrealDB")
            except Exception as e:
                logger.warning(f"Error closing SurrealDB connection: {str(e)}")

    def _normalize_date(self, date_input: Union[str, date, datetime]) -> str:
        """Normalize date to ISO format string for comparison."""
        if isinstance(date_input, datetime):
            return date_input.isoformat()
        elif isinstance(date_input, date):
            return datetime.combine(date_input, datetime.min.time()).isoformat()
        else:
            # Assume string, return as-is
            return str(date_input)

    async def _get_version_as_of_date(
        self,
        versions_table: str,
        control_id: str,
        target_date: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the version record valid as of the target date.

        Logic:
        1. Try exact match on version_date
        2. If not found, get the latest version before target_date
        3. If none before, return None (caller will use current)
        """
        # First try exact match
        result = await self.db.query(
            VERSION_EXACT_MATCH_QUERY.format(table=versions_table),
            {"cid": control_id, "date": target_date}
        )
        if result and len(result) > 0:
            return result[0]

        # Try latest before target_date
        result = await self.db.query(
            VERSION_BEFORE_DATE_QUERY.format(table=versions_table),
            {"cid": control_id, "date": target_date}
        )
        if result and len(result) > 0:
            return result[0]

        return None

    async def _get_current_record(
        self,
        current_table: str,
        control_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the current record for a control."""
        result = await self.db.query(
            CURRENT_RECORD_QUERY.format(table=current_table),
            {"cid": control_id}
        )
        return result[0] if result and len(result) > 0 else None

    # =========================================================================
    # GRAPH TRAVERSAL QUERIES
    # =========================================================================

    async def get_control_with_relationships(self, control_id: str) -> ControlWithRelationships:
        """Get a control with all its graph-linked relationships.

        Uses SurrealDB graph traversal to fetch:
        - Risk themes via src_controls_rel_has_risk_theme edge
        - Functions via src_controls_rel_has_related_function edge
        - Locations via src_controls_rel_has_related_location edge
        - SOX assertions via src_controls_rel_has_sox_assertion edge
        - Category flags via src_controls_rel_has_category_flag edge
        - Model outputs via ai_controls_rel_has_* edges

        Args:
            control_id: The control ID (e.g., "CTRL-001")

        Returns:
            ControlWithRelationships object with all linked data
        """
        record_id = normalize_control_id_for_record(control_id)

        # Get the control record
        result = await self.db.query(f"SELECT * FROM {record_id}")
        controls_main = result[0] if result and len(result) > 0 else None

        # Get related risk themes via graph traversal
        result = await self.db.query(get_risk_themes_query(record_id))
        risk_themes = extract_list_from_result(result, "risk_themes")

        # Get related functions via graph traversal
        result = await self.db.query(get_functions_query(record_id))
        functions = extract_list_from_result(result, "functions")

        # Get related locations via graph traversal
        result = await self.db.query(get_locations_query(record_id))
        locations = extract_list_from_result(result, "locations")

        # Get related SOX assertions via graph traversal
        result = await self.db.query(get_sox_assertions_query(record_id))
        sox_assertions = extract_list_from_result(result, "assertions")

        # Get related category flags via graph traversal
        result = await self.db.query(get_category_flags_query(record_id))
        category_flags = extract_list_from_result(result, "flags")

        # Get taxonomy via graph traversal
        result = await self.db.query(get_taxonomy_query(record_id))
        taxonomy = extract_single_from_result(result, "taxonomy")

        # Get enrichment via graph traversal
        result = await self.db.query(get_enrichment_query(record_id))
        enrichment = extract_single_from_result(result, "enrichment")

        # Get clean_text via graph traversal
        result = await self.db.query(get_clean_text_query(record_id))
        clean_text = extract_single_from_result(result, "clean_text")

        # Get embeddings via graph traversal (exclude vectors)
        result = await self.db.query(get_embeddings_query(record_id))
        embeddings = extract_single_from_result(result, "embeddings")

        return ControlWithRelationships(
            control_id=control_id,
            controls_main=controls_main,
            risk_themes=risk_themes,
            functions=functions,
            locations=locations,
            sox_assertions=sox_assertions,
            category_flags=category_flags,
            taxonomy=taxonomy,
            enrichment=enrichment,
            clean_text=clean_text,
            embeddings=embeddings,
        )

    async def get_controls_by_risk_theme(self, risk_theme_id: str) -> List[Dict[str, Any]]:
        """Find all controls linked to a specific risk theme.

        Uses reverse graph traversal from src_controls_ref_risk_theme -> src_controls_main.

        Args:
            risk_theme_id: The risk theme ID (e.g., "1.2")

        Returns:
            List of control records
        """
        record_id = normalize_risk_theme_id_for_record(risk_theme_id)
        result = await self.db.query(get_controls_by_risk_theme_query(record_id))
        return extract_list_from_result(result, "controls")

    async def get_controls_by_function(self, function_id: str) -> List[Dict[str, Any]]:
        """Find all controls linked to a specific function.

        Uses reverse graph traversal from src_controls_ref_org_function -> src_controls_main.

        Args:
            function_id: The function ID

        Returns:
            List of control records
        """
        result = await self.db.query(
            get_controls_by_function_query(f"{SRC_CONTROLS_REF_ORG_FUNCTION}:{function_id}")
        )
        return extract_list_from_result(result, "controls")

    async def get_controls_by_location(self, location_id: str) -> List[Dict[str, Any]]:
        """Find all controls linked to a specific location.

        Uses reverse graph traversal from src_controls_ref_org_location -> src_controls_main.

        Args:
            location_id: The location ID

        Returns:
            List of control records
        """
        result = await self.db.query(
            get_controls_by_location_query(f"{SRC_CONTROLS_REF_ORG_LOCATION}:{location_id}")
        )
        return extract_list_from_result(result, "controls")

    async def get_control_graph(self, control_id: str) -> Dict[str, Any]:
        """Get a complete graph view of a control including edge metadata.

        Returns the control with all edges and their metadata (created_at, source, comments).

        Args:
            control_id: The control ID (e.g., "CTRL-001")

        Returns:
            Dict with control data and all edge metadata
        """
        record_id = normalize_control_id_for_record(control_id)

        # Get control with all outgoing edges
        result = await self.db.query(get_control_graph_query(record_id))

        if result and len(result) > 0:
            return result[0]
        return {}

    # =========================================================================
    # TEMPORAL QUERIES
    # =========================================================================

    async def get_record_as_of_date(
        self,
        control_id: str,
        target_date: Union[str, date, datetime],
    ) -> ControlRecord:
        """Get a control record as of a specific date.

        Fallback logic:
        1. Try to get record at exact date
        2. If not available, get the last record before that date
        3. If none before, return current record

        Returns data from all tables: controls_main + taxonomy + enrichment +
        clean_text + embeddings.

        Args:
            control_id: The control ID (e.g., "CTRL-001")
            target_date: The target date (str, date, or datetime)

        Returns:
            ControlRecord with data as of the target date
        """
        target_date_str = self._normalize_date(target_date)

        # Get controls_main version
        main_version = await self._get_version_as_of_date(
            SRC_CONTROLS_VERSIONS, control_id, target_date_str
        )
        if main_version:
            controls_main_data = main_version.get("snapshot")
            actual_date = str(main_version.get("version_date", ""))
            fallback = "exact" if actual_date == target_date_str else "before"
        else:
            controls_main_data = await self._get_current_record(SRC_CONTROLS_MAIN, control_id)
            actual_date = controls_main_data.get("last_modified_on", "") if controls_main_data else ""
            fallback = "current"

        # Get taxonomy version
        taxonomy_version = await self._get_version_as_of_date(
            AI_CONTROLS_MODEL_TAXONOMY_VERSIONS, control_id, target_date_str
        )
        if taxonomy_version:
            taxonomy_data = taxonomy_version.get("snapshot")
        else:
            taxonomy_data = await self._get_current_record(AI_CONTROLS_MODEL_TAXONOMY_CURRENT, control_id)

        # Get enrichment version
        enrichment_version = await self._get_version_as_of_date(
            AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS, control_id, target_date_str
        )
        if enrichment_version:
            enrichment_data = enrichment_version.get("snapshot")
        else:
            enrichment_data = await self._get_current_record(AI_CONTROLS_MODEL_ENRICHMENT_CURRENT, control_id)

        # Get clean_text version
        clean_text_version = await self._get_version_as_of_date(
            AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS, control_id, target_date_str
        )
        if clean_text_version:
            clean_text_data = clean_text_version.get("snapshot")
        else:
            clean_text_data = await self._get_current_record(AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT, control_id)

        # Get embeddings version
        embeddings_version = await self._get_version_as_of_date(
            AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS, control_id, target_date_str
        )
        if embeddings_version:
            embeddings_data = embeddings_version.get("snapshot")
        else:
            embeddings_data = await self._get_current_record(AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT, control_id)

        return ControlRecord(
            control_id=control_id,
            as_of_date=target_date_str,
            actual_date=actual_date,
            fallback_used=fallback,
            controls_main=controls_main_data,
            taxonomy=taxonomy_data,
            enrichment=enrichment_data,
            clean_text=clean_text_data,
            embeddings=embeddings_data,
        )

    async def get_record_history(self, control_id: str) -> ControlHistory:
        """Get the complete version history for a control.

        Returns all versions from all version tables.

        Args:
            control_id: The control ID (e.g., "CTRL-001")

        Returns:
            ControlHistory with all version records
        """
        # Get controls_main versions
        result = await self.db.query(
            RECORD_HISTORY_QUERY.format(table=SRC_CONTROLS_VERSIONS),
            {"cid": control_id}
        )
        main_versions = result if isinstance(result, list) else []

        # Get taxonomy versions
        result = await self.db.query(
            RECORD_HISTORY_QUERY.format(table=AI_CONTROLS_MODEL_TAXONOMY_VERSIONS),
            {"cid": control_id}
        )
        taxonomy_versions = result if isinstance(result, list) else []

        # Get enrichment versions
        result = await self.db.query(
            RECORD_HISTORY_QUERY.format(table=AI_CONTROLS_MODEL_ENRICHMENT_VERSIONS),
            {"cid": control_id}
        )
        enrichment_versions = result if isinstance(result, list) else []

        # Get clean_text versions
        result = await self.db.query(
            RECORD_HISTORY_QUERY.format(table=AI_CONTROLS_MODEL_CLEANED_TEXT_VERSIONS),
            {"cid": control_id}
        )
        clean_text_versions = result if isinstance(result, list) else []

        # Get embeddings versions
        result = await self.db.query(
            RECORD_HISTORY_QUERY.format(table=AI_CONTROLS_MODEL_EMBEDDINGS_VERSIONS),
            {"cid": control_id}
        )
        embeddings_versions = result if isinstance(result, list) else []

        return ControlHistory(
            control_id=control_id,
            controls_main_versions=main_versions,
            taxonomy_versions=taxonomy_versions,
            enrichment_versions=enrichment_versions,
            clean_text_versions=clean_text_versions,
            embeddings_versions=embeddings_versions,
        )

    # =========================================================================
    # SNAPSHOT QUERIES
    # =========================================================================

    async def get_current_snapshot(self, include_lookups: bool = True) -> CurrentSnapshot:
        """Get a snapshot of all current tables.

        Returns lists of records for: src_controls_main, taxonomy, enrichment,
        clean_text, embeddings, and optionally lookup tables.

        Args:
            include_lookups: Whether to include lookup/reference tables

        Returns:
            CurrentSnapshot with all current records
        """
        # Get controls_main
        result = await self.db.query(TABLE_SELECT_ALL_QUERY.format(table=SRC_CONTROLS_MAIN))
        controls_main = result if isinstance(result, list) else []

        # Get taxonomy
        result = await self.db.query(
            TABLE_SELECT_ALL_QUERY.format(table=AI_CONTROLS_MODEL_TAXONOMY_CURRENT)
        )
        taxonomy = result if isinstance(result, list) else []

        # Get enrichment
        result = await self.db.query(
            TABLE_SELECT_ALL_QUERY.format(table=AI_CONTROLS_MODEL_ENRICHMENT_CURRENT)
        )
        enrichment = result if isinstance(result, list) else []

        # Get clean_text
        result = await self.db.query(
            TABLE_SELECT_ALL_QUERY.format(table=AI_CONTROLS_MODEL_CLEANED_TEXT_CURRENT)
        )
        clean_text = result if isinstance(result, list) else []

        # Get embeddings (excluding vectors for readability)
        result = await self.db.query(
            f"SELECT control_id, hash, effective_at FROM {AI_CONTROLS_MODEL_EMBEDDINGS_CURRENT}"
        )
        embeddings = result if isinstance(result, list) else []

        # Initialize lookup tables
        risk_themes = []
        functions = []
        locations = []
        sox_assertions = []
        category_flags = []

        # Get reference tables if requested
        if include_lookups:
            result = await self.db.query(
                TABLE_SELECT_ALL_QUERY.format(table=SRC_CONTROLS_REF_RISK_THEME)
            )
            risk_themes = result if isinstance(result, list) else []

            result = await self.db.query(
                TABLE_SELECT_ALL_QUERY.format(table=SRC_CONTROLS_REF_ORG_FUNCTION)
            )
            functions = result if isinstance(result, list) else []

            result = await self.db.query(
                TABLE_SELECT_ALL_QUERY.format(table=SRC_CONTROLS_REF_ORG_LOCATION)
            )
            locations = result if isinstance(result, list) else []

            result = await self.db.query(
                TABLE_SELECT_ALL_QUERY.format(table=SRC_CONTROLS_REF_SOX_ASSERTION)
            )
            sox_assertions = result if isinstance(result, list) else []

            result = await self.db.query(
                TABLE_SELECT_ALL_QUERY.format(table=SRC_CONTROLS_REF_CATEGORY_FLAG)
            )
            category_flags = result if isinstance(result, list) else []

        return CurrentSnapshot(
            controls_main=controls_main,
            taxonomy=taxonomy,
            enrichment=enrichment,
            clean_text=clean_text,
            embeddings=embeddings,
            risk_themes=risk_themes,
            functions=functions,
            locations=locations,
            sox_assertions=sox_assertions,
            category_flags=category_flags,
        )

    async def get_table_counts(self) -> Dict[str, int]:
        """Get record counts from all tables including graph edges.

        Returns:
            Dict mapping table name to record count
        """
        counts = {}
        for table in ALL_TABLES:
            try:
                result = await self.db.query(TABLE_SELECT_ALL_QUERY.format(table=table))
                counts[table] = len(result) if isinstance(result, list) else 0
            except Exception as e:
                logger.warning(f"Error counting table {table}: {str(e)}")
                counts[table] = -1
        return counts

    # =========================================================================
    # COMPLETE RECORD ASSEMBLY
    # =========================================================================

    async def get_complete_control_record(self, control_id: str) -> Dict[str, Any]:
        """Get a complete assembled control record with all tables and relationships.

        Combines:
        - controls_main data
        - All graph-linked relationships (risk_themes, functions, locations, etc.)
        - All model outputs (taxonomy, enrichment, clean_text, embeddings)

        Args:
            control_id: The control ID (e.g., "CTRL-001")

        Returns:
            Complete dict ready for use
        """
        # Get control with all relationships via graph traversal
        full_record = await self.get_control_with_relationships(control_id)

        # Build the complete assembled record
        assembled = {
            "control_id": control_id,
            "controls_main": None,
            "relationships": {
                "risk_themes": [],
                "functions": [],
                "locations": [],
                "sox_assertions": [],
                "category_flags": [],
            },
            "model_outputs": {
                "taxonomy": None,
                "enrichment": None,
                "clean_text": None,
                "embeddings": None,
            },
        }

        # Process controls_main - convert any special objects to serializable form
        if full_record.controls_main:
            main_data = {}
            for k, v in full_record.controls_main.items():
                if hasattr(v, '__dict__'):
                    main_data[k] = str(v)
                else:
                    main_data[k] = v
            assembled["controls_main"] = main_data

        # Process relationships - extract clean data from graph results
        def clean_record(record):
            """Convert record to clean serializable dict."""
            if not record:
                return None
            if isinstance(record, dict):
                cleaned = {}
                for k, v in record.items():
                    if k == 'id':
                        cleaned[k] = str(v)
                    elif hasattr(v, '__dict__'):
                        cleaned[k] = str(v)
                    else:
                        cleaned[k] = v
                return cleaned
            return str(record)

        assembled["relationships"]["risk_themes"] = [
            clean_record(rt) for rt in full_record.risk_themes
        ]
        assembled["relationships"]["functions"] = [
            clean_record(fn) for fn in full_record.functions
        ]
        assembled["relationships"]["locations"] = [
            clean_record(loc) for loc in full_record.locations
        ]
        assembled["relationships"]["sox_assertions"] = [
            clean_record(sox) for sox in full_record.sox_assertions
        ]
        assembled["relationships"]["category_flags"] = [
            clean_record(cf) for cf in full_record.category_flags
        ]

        # Process model outputs
        if full_record.taxonomy:
            assembled["model_outputs"]["taxonomy"] = clean_record(full_record.taxonomy)
        if full_record.enrichment:
            assembled["model_outputs"]["enrichment"] = clean_record(full_record.enrichment)
        if full_record.clean_text:
            assembled["model_outputs"]["clean_text"] = clean_record(full_record.clean_text)
        if full_record.embeddings:
            assembled["model_outputs"]["embeddings"] = clean_record(full_record.embeddings)

        return assembled
