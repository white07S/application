"""Cache value serialization using orjson.

Handles Pydantic BaseModel, dicts, lists, tuples, and primitive types.
Stores a type wrapper envelope so deserialization can reconstruct the original type.
"""

from __future__ import annotations

import importlib
from typing import Any, Type

import orjson
from pydantic import BaseModel

from server.logging_config import get_logger

logger = get_logger(name=__name__)


def serialize(value: Any) -> str:
    """Serialize a value to a JSON string for Redis storage.

    Wraps the value with type metadata for lossless round-tripping.
    """
    envelope = _serialize_element(value)
    return orjson.dumps(envelope).decode("utf-8")


def deserialize(raw: str) -> Any:
    """Deserialize a JSON string from Redis back to the original type."""
    envelope = orjson.loads(raw)
    return _deserialize_envelope(envelope)


def _serialize_element(item: Any) -> dict:
    """Serialize a single element with type envelope."""
    if isinstance(item, BaseModel):
        return {
            "_type": "pydantic",
            "_model": f"{item.__class__.__module__}.{item.__class__.__name__}",
            "data": item.model_dump(mode="json"),
        }
    elif isinstance(item, tuple):
        return {
            "_type": "tuple",
            "data": [_serialize_element(sub) for sub in item],
        }
    elif isinstance(item, list):
        return {
            "_type": "list",
            "data": [_serialize_element(sub) for sub in item],
        }
    elif isinstance(item, dict):
        return {
            "_type": "dict",
            "data": {k: _serialize_element(v) for k, v in item.items()},
        }
    else:
        return {"_type": "plain", "data": item}


def _deserialize_envelope(envelope: dict) -> Any:
    """Deserialize a single envelope dict back to its original type."""
    t = envelope["_type"]

    if t == "pydantic":
        model_cls = _resolve_model(envelope["_model"])
        return model_cls.model_validate(envelope["data"])
    elif t == "tuple":
        return tuple(
            _deserialize_envelope(elem)
            for elem in envelope["data"]
        )
    elif t == "list":
        return [
            _deserialize_envelope(elem)
            for elem in envelope["data"]
        ]
    elif t == "dict":
        return {k: _deserialize_envelope(v) for k, v in envelope["data"].items()}
    else:
        return envelope["data"]


def _resolve_model(model_path: str) -> Type[BaseModel]:
    """Resolve a Pydantic model class from its module.ClassName string."""
    module_name, class_name = model_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    if not (isinstance(cls, type) and issubclass(cls, BaseModel)):
        raise TypeError(f"{model_path} is not a Pydantic BaseModel subclass")
    return cls
