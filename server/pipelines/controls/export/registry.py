"""Template registry for export templates.

Templates self-register via the @register decorator.
"""

from typing import Dict, List, Type

from .base import ExportTemplate

TEMPLATE_REGISTRY: Dict[str, Type[ExportTemplate]] = {}


def register(cls: Type[ExportTemplate]) -> Type[ExportTemplate]:
    """Decorator that registers an ExportTemplate subclass by its TEMPLATE_NAME."""
    TEMPLATE_REGISTRY[cls.TEMPLATE_NAME] = cls
    return cls


def get_template(name: str) -> Type[ExportTemplate]:
    """Look up a template class by name. Raises ValueError if not found."""
    if name not in TEMPLATE_REGISTRY:
        available = list(TEMPLATE_REGISTRY.keys())
        raise ValueError(
            f"Unknown export template: {name!r}. Available: {available}"
        )
    return TEMPLATE_REGISTRY[name]


def list_templates() -> List[Dict[str, str]]:
    """Return name and description of all registered templates."""
    return [
        {"name": cls.TEMPLATE_NAME, "description": cls.TEMPLATE_DESCRIPTION}
        for cls in TEMPLATE_REGISTRY.values()
    ]
