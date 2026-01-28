"""Configuration loader for pipeline configs.

Loads and validates JSON configuration files for each dataset type.
Validation config is now loaded from initial_validation.py modules.
"""
import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.logging_config import get_logger

logger = get_logger(name=__name__)

CONFIG_BASE_PATH = Path(__file__).parent.parent / "pipeline_config"


@dataclass
class StageConfig:
    """Configuration for a single pipeline stage."""
    name: str
    type: str  # "ingestion" or "model"
    target: Optional[str] = None  # "main" or "children" for ingestion
    source: Optional[str] = None  # for nested_embeddings
    depends_on: List[str] = field(default_factory=list)


@dataclass
class GraphConfig:
    """Configuration for pipeline graph execution."""
    data_source: str
    batch_size: int
    max_retries: int
    primary_key: str
    last_modified_column: str
    main_table: str
    child_tables: List[str]
    parquet_mapping: Dict[str, str]
    stages: List[StageConfig]


@dataclass
class ValidationConfig:
    """Configuration for file validation.

    Note: This is now loaded from initial_validation.py modules instead of validation.json.
    The fields are populated by reading class attributes from the InitialValidator class.
    """
    file_count: int
    file_patterns: List[str]
    min_file_size_kb: int
    allowed_extensions: List[str]
    required_issue_types: Optional[List[str]] = None


@dataclass
class ModelStageConfig:
    """Configuration for a model processing stage."""
    enabled: bool
    input_columns: List[str] = field(default_factory=list)
    output_table: Optional[str] = None
    output_fields: Dict[str, str] = field(default_factory=dict)
    output_field: Optional[str] = None  # for embeddings
    dimensions: Optional[int] = None  # for embeddings
    source: Optional[str] = None  # for nested_embeddings
    version: str = "v1"
    mock_delay_seconds: List[int] = field(default_factory=lambda: [10, 30])
    null_probability: float = 0.0


@dataclass
class ModelsConfig:
    """Configuration for all model stages."""
    nfr_taxonomy: ModelStageConfig
    enrichment: ModelStageConfig
    embeddings: ModelStageConfig
    nested_embeddings: ModelStageConfig


@dataclass
class DatasetConfig:
    """Complete configuration for a dataset."""
    data_source: str
    graph: GraphConfig
    validation: ValidationConfig
    models: ModelsConfig


class ConfigLoader:
    """Loads and caches pipeline configurations."""

    _cache: Dict[str, DatasetConfig] = {}

    @classmethod
    def load(cls, data_source: str) -> DatasetConfig:
        """Load configuration for a data source.

        Args:
            data_source: One of 'issues', 'controls', 'actions'

        Returns:
            DatasetConfig with all configuration loaded

        Raises:
            FileNotFoundError: If config files don't exist
            ValueError: If config is invalid
        """
        if data_source in cls._cache:
            return cls._cache[data_source]

        config_path = CONFIG_BASE_PATH / data_source

        if not config_path.exists():
            raise FileNotFoundError(f"Config directory not found for {data_source}: {config_path}")

        # Load graph config
        graph_file = config_path / "graph.json"
        if not graph_file.exists():
            raise FileNotFoundError(f"graph.json not found for {data_source}")

        graph_data = json.loads(graph_file.read_text())
        graph_config = cls._parse_graph_config(graph_data)

        # Load validation config from initial_validation.py module
        validation_config = cls._load_validation_from_module(data_source)

        # Load models config
        models_file = config_path / "models.json"
        if not models_file.exists():
            raise FileNotFoundError(f"models.json not found for {data_source}")

        models_data = json.loads(models_file.read_text())
        models_config = cls._parse_models_config(models_data)

        config = DatasetConfig(
            data_source=data_source,
            graph=graph_config,
            validation=validation_config,
            models=models_config,
        )

        cls._cache[data_source] = config
        logger.info("Loaded configuration for {}", data_source)

        return config

    @classmethod
    def reload(cls, data_source: str) -> DatasetConfig:
        """Force reload configuration from disk."""
        if data_source in cls._cache:
            del cls._cache[data_source]
        return cls.load(data_source)

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached configurations."""
        cls._cache.clear()

    @classmethod
    def _parse_graph_config(cls, data: Dict[str, Any]) -> GraphConfig:
        """Parse graph configuration from JSON data."""
        stages = []
        for stage_data in data.get("stages", []):
            stages.append(StageConfig(
                name=stage_data["name"],
                type=stage_data["type"],
                target=stage_data.get("target"),
                source=stage_data.get("source"),
                depends_on=stage_data.get("depends_on", []),
            ))

        return GraphConfig(
            data_source=data["data_source"],
            batch_size=data.get("batch_size", 10),
            max_retries=data.get("max_retries", 3),
            primary_key=data["primary_key"],
            last_modified_column=data["last_modified_column"],
            main_table=data["main_table"],
            child_tables=data.get("child_tables", []),
            parquet_mapping=data.get("parquet_mapping", {}),
            stages=stages,
        )

    @classmethod
    def _load_validation_from_module(cls, data_source: str) -> ValidationConfig:
        """Load validation configuration from initial_validation.py module.

        Args:
            data_source: One of 'controls', 'issues', 'actions'

        Returns:
            ValidationConfig with settings from the InitialValidator class
        """
        module_path = f"server.pipelines.pipeline_config.{data_source}.initial_validation"
        try:
            module = importlib.import_module(module_path)
            validator = module.get_validator()

            # Extract configuration from validator class attributes
            return ValidationConfig(
                file_count=validator.expected_file_count,
                file_patterns=validator.expected_file_patterns,
                min_file_size_kb=validator.min_file_size_kb,
                allowed_extensions=validator.allowed_extensions,
                required_issue_types=getattr(validator, 'required_issue_types', None),
            )
        except ImportError as e:
            logger.warning(
                "Could not load initial_validation.py for {}, using defaults: {}",
                data_source, e
            )
            # Fallback to defaults
            defaults = {
                "controls": {"file_count": 1},
                "issues": {"file_count": 4, "required_issue_types": ["Audit", "Regulatory", "Restricted Regulatory", "Self-Identified"]},
                "actions": {"file_count": 1},
            }
            ds_defaults = defaults.get(data_source, {"file_count": 1})
            return ValidationConfig(
                file_count=ds_defaults.get("file_count", 1),
                file_patterns=[f"{data_source}*.csv"],
                min_file_size_kb=5,
                allowed_extensions=[".csv"],
                required_issue_types=ds_defaults.get("required_issue_types"),
            )

    @classmethod
    def _parse_models_config(cls, data: Dict[str, Any]) -> ModelsConfig:
        """Parse models configuration from JSON data."""
        return ModelsConfig(
            nfr_taxonomy=cls._parse_model_stage(data.get("nfr_taxonomy", {"enabled": False})),
            enrichment=cls._parse_model_stage(data.get("enrichment", {"enabled": False})),
            embeddings=cls._parse_model_stage(data.get("embeddings", {"enabled": False})),
            nested_embeddings=cls._parse_model_stage(data.get("nested_embeddings", {"enabled": False})),
        )

    @classmethod
    def _parse_model_stage(cls, data: Dict[str, Any]) -> ModelStageConfig:
        """Parse a single model stage configuration."""
        return ModelStageConfig(
            enabled=data.get("enabled", False),
            input_columns=data.get("input_columns", []),
            output_table=data.get("output_table"),
            output_fields=data.get("output_fields", {}),
            output_field=data.get("output_field"),
            dimensions=data.get("dimensions"),
            source=data.get("source"),
            version=data.get("version", "v1"),
            mock_delay_seconds=data.get("mock_delay_seconds", [10, 30]),
            null_probability=data.get("null_probability", 0.0),
        )


def get_config(data_source: str) -> DatasetConfig:
    """Convenience function to load configuration."""
    return ConfigLoader.load(data_source)


def get_graph_config(data_source: str) -> GraphConfig:
    """Convenience function to get graph configuration."""
    return ConfigLoader.load(data_source).graph


def get_validation_config(data_source: str) -> ValidationConfig:
    """Convenience function to get validation configuration."""
    return ConfigLoader.load(data_source).validation


def get_models_config(data_source: str) -> ModelsConfig:
    """Convenience function to get models configuration."""
    return ConfigLoader.load(data_source).models
