"""Cache key construction.

Convention: cache:{namespace}:{function_name}:{arg_hash}

Examples:
    cache:explorer:get_function_tree:a1b2c3d4e5f6a7b8
    cache:stats:_fetch_controls_stats:d41d8cd98f00b204
"""

import hashlib

import orjson


def build_cache_key(namespace: str, func_name: str, args: tuple, kwargs: dict) -> str:
    """Build a deterministic Redis key from function identity and arguments.

    Trailing ``None`` positional args and ``None``-valued kwargs are stripped
    so that ``f()`` and ``f(None, None)`` produce the same cache key.

    Args:
        namespace: Cache namespace (e.g., "explorer", "auth", "stats")
        func_name: Function name (e.g., "get_function_tree")
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Key string like "cache:explorer:get_function_tree:a1b2c3d4e5f6a7b8"
    """
    trimmed_args = _strip_trailing_none(args)
    trimmed_kwargs = {k: v for k, v in kwargs.items() if v is not None}
    key_data = orjson.dumps(
        {"a": _normalize(trimmed_args), "k": _normalize(trimmed_kwargs)},
        option=orjson.OPT_SORT_KEYS,
    )
    arg_hash = hashlib.sha256(key_data).hexdigest()[:16]
    return f"cache:{namespace}:{func_name}:{arg_hash}"


def _strip_trailing_none(args: tuple) -> tuple:
    """Remove trailing None values from a positional args tuple.

    (None, None) → ()
    ("a", None)  → ("a",)
    ("a", None, "b") → ("a", None, "b")  # non-trailing None preserved
    """
    lst = list(args)
    while lst and lst[-1] is None:
        lst.pop()
    return tuple(lst)


def namespace_pattern(namespace: str) -> str:
    """Return a Redis SCAN pattern for all keys in a namespace.

    Returns pattern like "cache:explorer:*"
    """
    return f"cache:{namespace}:*"


def _normalize(obj):
    """Normalize arguments for deterministic hashing."""
    from datetime import date, datetime

    from pydantic import BaseModel

    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    elif isinstance(obj, dict):
        return {str(k): _normalize(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, (list, tuple)):
        return [_normalize(item) for item in obj]
    else:
        return str(obj)
