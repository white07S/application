This is UV astral python package manager based project, no pip.
use uv add "lib" or uv run file.py to perform operations.



Some of the pattern that need to be followed everywhere.

- Typesafe code, use pydantic schema.
- Proper error and exception handling 
- Never write code which does silent error bypass. The error should be raised.
- Always have a clear debate between when to use asynchronous vs concurrent

## Caching Pattern (Redis)

### Overview
Redis is used as a service-level cache via the `server/cache` package. Caching is applied at the service function layer (not HTTP middleware), so internal callers also benefit from cache hits. If Redis is unavailable, the application continues to work normally (cache miss behavior, logged as warning).

### Usage
```python
from server.cache import cached

@cached(namespace="explorer", ttl=3600)
async def get_function_tree(as_of: date, ...) -> tuple[list[TreeNodeResponse], str | None]:
    ...
```

### Key Convention
Keys follow the pattern: `cache:{namespace}:{function_name}:{sha256_of_args[:16]}`
- `namespace`: Logical group for invalidation (explorer, stats, etc.)
- `arg_hash`: SHA256 of serialized arguments, truncated to 16 chars

Auth cache uses a separate prefix: `auth:access:{token_hash}` and `auth:stale:{token_hash}`.
This separation ensures `invalidate_all()` (which targets `cache:*`) does not wipe active auth sessions.

### Cache Invalidation
- **Primary**: Explicit invalidation via `invalidate_namespace("explorer")` after data changes (e.g., ingestion completes in `pipelines/controls/api/processing.py`)
- **Fallback**: TTL expiry as a safety net
- Never rely on TTL alone for correctness; always add explicit invalidation at the data mutation point

### Adding Caching to a New Service Function
1. Import the decorator: `from server.cache import cached`
2. Choose a namespace (or create a new one for a new domain)
3. Set an appropriate TTL (see TTL table below)
4. Decorate the async function
5. Add `invalidate_namespace("your_namespace")` at the relevant data mutation point
6. The function return value must be serializable: Pydantic models, dicts, lists, tuples, or primitives

### TTL Recommendations
| Namespace  | TTL     | Rationale                                   |
|-----------|---------|---------------------------------------------|
| explorer  | 3600s   | Data only changes on ingestion              |
| stats     | 300s    | Semi-real-time, short TTL as safety net     |
| auth      | 120s    | Token-scoped, matches Azure AD refresh      |

### What NOT to Cache
- Health check endpoints (must reflect real-time status)
- DevData endpoints (developers need live data for debugging)
- Write/mutation operations
- Functions with side effects
- Streaming or SSE responses