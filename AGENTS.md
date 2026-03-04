# AGENTS.md — NFR Connect Project Guide

> This file is the starting point for coding agents to understand the project.
> For deeper details, search the referenced files directly.

---

## 1. What Is This Project

**NFR Connect** is a full-stack enterprise platform for Non-Financial Risk (NFR) management. It handles ingestion, versioning, AI enrichment, similarity analysis, and portfolio-level exploration of operational controls data. The target environment is a financial institution (UBS branding, Azure AD auth, regulatory compliance features).

**Core capabilities:**
- Resumable file upload (TUS protocol) of controls datasets
- Multi-stage ML pipeline: validation → feature prep → embeddings → enrichment → taxonomy
- Temporal (bi-temporal) versioning of all ingested data
- Hybrid search: PostgreSQL full-text search + Qdrant vector semantic search
- Portfolio dashboards with concentration, redundancy, lifecycle analysis
- Snapshot/restore of both PostgreSQL and Qdrant databases
- Template-based data exports (Excel)

---

## 2. Repository Layout

```
/
├── client/                  React 19 + TypeScript frontend (CRA-based)
├── server/                  FastAPI + Python 3.12 backend
├── context_providers/       Organization charts + risk theme JSONL files (date-partitioned)
├── data_ingested/           Uploaded controls + ML model outputs (runtime data)
├── data_exports/            Generated export files (runtime data)
├── MULTI_WORKER_IMPLEMENTATION.md   Celery + Gunicorn implementation notes
├── TESTING_GUIDE.md                 Testing procedures
├── client/AGENTS.md         Client-specific conventions (design system, responsive rules)
└── server/AGENTS.md         Server-specific conventions (UV package manager, caching rules)
```

**This is NOT a monorepo with shared workspaces.** Client and server are independent projects with separate dependency management (npm vs uv). They share no code or packages.

---

## 3. Technology Stack

### Backend (`server/`)
| Concern | Technology | Notes |
|---------|-----------|-------|
| Framework | FastAPI (async) | ASGI via Uvicorn |
| Python | 3.12+ | Strict type hints with Pydantic |
| Package Manager | **UV (astral)** | NOT pip. Use `uv add`, `uv run` |
| Database | PostgreSQL via asyncpg | SQLAlchemy 2.0 async engine |
| Vector DB | Qdrant | Async client, named vectors |
| Cache/Queue | Redis | 4 databases (see section 9) |
| Background Tasks | Celery 5.3+ | Redis broker, prefork pool |
| Migrations | Alembic | Single migration chain for all domains |
| Auth | Azure AD (MSAL) | OAuth 2.0 On-Behalf-Of flow |
| Logging | Loguru | NOT stdlib logging |
| Serialization | orjson | For performance-critical paths |
| Server | Gunicorn + Uvicorn workers | Multi-worker with coordination |

### Frontend (`client/`)
| Concern | Technology | Notes |
|---------|-----------|-------|
| Framework | React 19 + TypeScript 4.9 | CRA (react-scripts), NOT Vite |
| Routing | React Router v7 | Nested routes with access guards |
| Auth | @azure/msal-browser + msal-react | Token in `X-MS-TOKEN-AAD` header |
| Styling | Tailwind CSS 3.4 | Custom UBS design system |
| State | Zustand + useReducer | Zustand for global, useReducer for complex local |
| Charts | Chart.js + react-chartjs-2 | Shared palette in `chartColors.ts` |
| Icons | Lucide React + Material Symbols font | Material Symbols via Google Fonts |
| File Upload | Uppy (TUS protocol) | Resumable uploads |
| Docs | MDX + Flexsearch | Client-side full-text search |
| Components | Custom (plain HTML + Tailwind) | NO component library (no Shadcn, no MUI, no Radix) |

---

## 4. Backend Architecture

### 4.1 Directory Structure

```
server/
├── main.py                     App entry + multi-worker lifespan (4 phases)
├── settings.py                 Pydantic BaseSettings (all from .env, no defaults for secrets)
├── logging_config.py           Loguru setup
├── pyproject.toml              Dependencies (UV)
├── alembic/                    17+ migration versions
│   └── versions/               Migration scripts
├── api/
│   └── main.py                 Router assembly (all routers imported here)
├── auth/
│   ├── dependencies.py         get_token_from_header() — extracts X-MS-TOKEN-AAD
│   ├── service.py              MSAL OBO flow + Graph API group check
│   ├── token_manager.py        Thread pool for blocking MSAL calls
│   └── router.py               GET /v2/auth/access
├── cache/
│   ├── decorator.py            @cached(namespace, ttl) async decorator
│   ├── keys.py                 cache:{namespace}:{func}:{sha256[:16]}
│   ├── invalidation.py         invalidate_namespace(), invalidate_all()
│   └── serialization.py        Type-wrapped JSON (preserves Pydantic models)
├── config/
│   ├── postgres.py             AsyncEngine + session factory (global singletons)
│   ├── redis.py                4 Redis clients (async cache, async coord, sync variants)
│   └── qdrant.py               AsyncQdrantClient lifecycle
├── core/
│   └── worker_sync.py          Distributed init coordination (Redis SETNX leader election)
├── middleware/
│   └── request_logging.py      HTTP request/response timing
├── explorer/                   Controls portfolio explorer (read path)
│   ├── controls/               Search, detail, versions, diff
│   ├── dashboard/              KPIs, heatmaps, trends, concentration
│   ├── filters/                Sidebar trees (functions, locations, CEs, AUs, risks)
│   └── shared/                 Shared models, embeddings helper, temporal utils
├── pipelines/                  Data ingestion (write path)
│   ├── controls/               The main domain
│   │   ├── schema.py           11 SQLAlchemy tables (controls domain)
│   │   ├── schema_validation.py Pydantic validation for JSONL input
│   │   ├── qdrant_service.py   Vector upserts with delta detection
│   │   ├── similarity.py       Hybrid scoring (semantic + TF-IDF)
│   │   ├── readiness.py        Pre-ingestion checks
│   │   ├── ingest/service.py   Full ETL pipeline (main ingestion logic)
│   │   ├── model_runners/      Mock ML pipeline stages
│   │   ├── export/             Template-based Excel export system
│   │   ├── upload/             TUS upload + CSV validation
│   │   └── api/                Upload, processing, export, TUS endpoints
│   ├── orgs/schema.py          7 tables (organization hierarchy)
│   ├── risks/schema.py         5 tables (risk taxonomy)
│   ├── assessment_units/       2 tables (assessment units)
│   ├── schema/base.py          Shared MetaData() instance
│   ├── storage.py              File path helpers + processing lock
│   └── upload_tracker.py       Upload state tracking
├── devdata/                    PostgreSQL/Qdrant data browser + snapshots
│   ├── service.py              Table introspection + paginated browsing
│   ├── snapshot_service.py     pg_dump/pg_restore with metadata
│   ├── qdrant_snapshot_service.py  Qdrant snapshot with HTTP streaming
│   └── api/                    3 routers (browse, PG snapshots, Qdrant snapshots)
├── devdata_qdrant/             Qdrant-specific browser (points, search, graph)
├── jobs/
│   └── models.py               SQLAlchemy ORM: TusUpload, UploadBatch, ProcessingJob
├── workers/
│   ├── celery_app.py           Celery config (5 queues, no auto-retry)
│   └── tasks/
│       ├── ingestion.py        run_controls_ingestion_task (global lock, progress)
│       ├── export.py           run_export_task (per-template lock, file cache)
│       └── snapshots.py        PG + Qdrant snapshot tasks
└── scripts/                    CLI utilities (mock data, context ingestion, snapshot CLI)
```

### 4.2 Application Startup (Lifespan)

The app uses a 4-phase startup in `server/main.py` that is critical for multi-worker (Gunicorn) safety:

| Phase | What | Who Runs It |
|-------|------|-------------|
| 1 | PostgreSQL engine + Redis clients | Every worker |
| 2 | Alembic migration check, context provider verification, storage directory init | Leader only (Redis SETNX lock) |
| 3 | Qdrant client + collection creation | Every worker connects; leader creates collections |
| 4 | Cache warmup, dashboard snapshot seeding | Leader only (optional) |

**Gotcha:** Worker pool size is auto-adjusted in multi-worker mode. Each Gunicorn worker gets `pool_size / num_workers` PostgreSQL connections. Celery workers have their own smaller pool (3 connections, 5 overflow).

### 4.3 API Routes

All routes are assembled in `server/api/main.py` and mounted under `/api` prefix in `main.py`.

| Prefix | Router File | Auth Required | Purpose |
|--------|------------|---------------|---------|
| `/v2/auth` | `auth/router.py` | No (token in header) | Access control check |
| `/v2/ingestion` | `pipelines/controls/api/processing.py` | Yes (ingestion) | Trigger/poll ingestion |
| `/v2/upload` | `pipelines/controls/api/upload.py` | Yes (ingestion) | Batch management |
| `/files` | `pipelines/controls/api/tus.py` | Yes (ingestion) | TUS resumable upload |
| `/v2/export` | `pipelines/controls/api/export.py` | Yes (ingestion) | Export templates + jobs |
| `/v2/explorer/controls` | `explorer/controls/api/router.py` | Yes (explorer) | Search, detail, diff |
| `/v2/explorer/filters` | `explorer/filters/api/router.py` | Yes (explorer) | Sidebar filter trees |
| `/v2/explorer/dashboard` | `explorer/dashboard/api/router.py` | Yes (explorer) | Dashboard metrics |
| `/v2/devdata` | `devdata/api/router.py` | Yes (devdata) | Table browser |
| `/v2/devdata/snapshots` | `devdata/api/snapshot_router.py` | Yes (devdata) | PG snapshots |
| `/v2/devdata/qdrant-snapshots` | `devdata/api/qdrant_snapshot_router.py` | Yes (devdata) | Qdrant snapshots |
| `/v2/health` | `api/health.py` | No | Health check |
| `/v2/stats` | `api/stats.py` | No | System statistics |
| `/v2/docs` | `api/docs.py` | No | Documentation content |

---

## 5. Database Architecture

### 5.1 PostgreSQL

**Connection:** Async SQLAlchemy engine via `asyncpg`. Global singleton in `server/config/postgres.py`.

**Session patterns:**
- FastAPI endpoints: `db: AsyncSession = Depends(get_db_session)`
- Standalone code: `async with get_db_session_context() as session:`
- Sessions use `expire_on_commit=False`

**Schema organization:** All tables register on a single shared `MetaData()` in `server/pipelines/schema/base.py`. This allows Alembic to manage everything in one migration chain.

**Important: This project uses SQLAlchemy Table objects (imperative mapping), NOT declarative ORM classes.** The controls, orgs, risks, and assessment_units schemas define `Table(...)` objects directly. Only the jobs module (`server/jobs/models.py`) uses declarative ORM classes (`class TusUpload(Base)`).

**Tables by domain (24+ total):**

| Domain | Tables | Schema File |
|--------|--------|-------------|
| Controls | 11 (ref, ver, 6 relations, 3 AI models, 1 similarity) | `pipelines/controls/schema.py` |
| Organizations | 7 (ref, 3 versions, 2 relations, 1 metadata) | `pipelines/orgs/schema.py` |
| Risks | 5 (2 refs, 2 versions, 1 relation) | `pipelines/risks/schema.py` |
| Assessment Units | 2 (ref, version) | `pipelines/assessment_units/schema.py` |
| Jobs | 4 (tus_uploads, upload_batches, processing_jobs, upload_id_sequence) | `jobs/models.py` |

### 5.2 Temporal Versioning Pattern

**This is a non-standard pattern.** All domain data uses bi-temporal versioning with `tx_from` / `tx_to` columns:

- **Reference table** (`ref_*`): Created once per entity. Has `created_at`.
- **Version table** (`ver_*`): New row per change. `tx_from` = when written, `tx_to` = when superseded (NULL = current).
- **Relation tables** (`rel_*`): Same `tx_from`/`tx_to` pattern for edges.
- **Current query:** `WHERE tx_to IS NULL` — enforced by a unique partial index `uq_ver_control_current`.
- **History query:** Filter on `tx_from`/`tx_to` ranges.

**Gotcha:** When ingesting, the system closes old versions (`UPDATE SET tx_to = now()`) before inserting new ones. This must happen in the correct order within a transaction.

### 5.3 Qdrant Vector Database

**Client:** `AsyncQdrantClient` in `server/config/qdrant.py`.

**Collection naming:** `{QDRANT_COLLECTION_PREFIX}_controls` (default: `nfr_connect_controls`).

**Named vectors (3 per point):**
- `what_embedding` — what the control does (3072 dims)
- `why_embedding` — why it exists (3072 dims)
- `where_embedding` — organizational context (3072 dims)

**Point IDs:** Deterministic UUID5 derived from `control_id`. See `qdrant_service.py`.

**Delta detection:** Each point's payload stores per-feature hashes. On re-ingestion, only features whose hashes changed get re-uploaded. This is NOT a standard Qdrant pattern.

**Gotcha:** During bulk ingestion (>500 points), HNSW indexing is temporarily disabled (threshold set to max) to speed up writes, then re-enabled after. The service waits for collection status to return to "green" before proceeding.

### 5.4 Redis (4 Databases)

| DB | Purpose | Client Type | Access Pattern |
|----|---------|-------------|----------------|
| 0 | Application cache | Async (`redis.asyncio`) | `get_redis()` |
| 1 | Celery broker (task queue) | Sync (Celery internal) | Automatic via Celery |
| 2 | Celery results | Sync (Celery internal) | 24hr retention, gzip |
| 3 | Worker coordination | Async + Sync | `get_redis_coordination()` / `get_redis_sync_client()` |

**Gotcha:** Redis DB 3 has both async and sync clients because it's used by both FastAPI (async) during startup and Celery workers (sync) during task execution.

**Gotcha:** Auth cache uses a separate key prefix (`auth:access:` and `auth:stale:`) that is intentionally excluded from `invalidate_all()` which targets `cache:*`. This prevents auth sessions from being wiped during ingestion.

---

## 6. Frontend Architecture

### 6.1 Directory Structure

```
client/src/
├── index.tsx                   Entry: MSAL init → render
├── App.tsx                     Layout (Header + Footer) + React Router
├── index.css                   Tailwind base + custom styles
├── auth/
│   ├── msalInstance.ts         MSAL singleton
│   └── useAuth.ts              login(), logout(), getApiAccessToken()
├── config/
│   ├── appConfig.ts            App constants (name, version, features, team)
│   ├── authConfig.ts           MSAL config (client ID, authority, scopes)
│   └── routes.tsx              Route definitions with accessRight mapping
├── context/
│   └── AccessControlContext.tsx RBAC provider (calls /api/auth/access)
├── components/
│   ├── Layout/
│   │   ├── Header.tsx          Fixed header with responsive nav
│   │   ├── Footer.tsx          Page footer
│   │   └── ExplorerSelector.tsx Controls/Events/Issues dropdown
│   └── ProtectedRoute.tsx      Auth + access guard wrapper
├── pages/
│   ├── Home/                   Landing page with stats + feature cards
│   ├── Docs/                   MDX docs viewer (sidebar, search, TOC)
│   ├── Explorer/               Main risk explorer
│   │   ├── ExplorerLayout.tsx  Master layout (sidebar + content)
│   │   ├── api/explorerApi.ts  All explorer API calls
│   │   ├── controls/           Controls list, detail, diff
│   │   │   └── hooks/          useControlsState (useReducer-based)
│   │   ├── dashboard/          Charts + KPIs
│   │   │   └── api/            Dashboard-specific API calls
│   │   └── hooks/              useFilterState, useCascadeSuggestions, etc.
│   ├── DevData/                PostgreSQL table browser + snapshots
│   ├── DevDataQdrant/          Qdrant browser (points, graph, clustering)
│   │   └── store/              Zustand store (useQdrantBrowserStore)
│   └── Pipelines/              Upload (Uppy), Processing, Exports
├── types/                      Shared TypeScript interfaces
└── utils/
    └── formatters.ts           formatBytes, formatRelativeDate, formatDuration, etc.
```

### 6.2 State Management

The frontend uses **3 different state management approaches** (intentionally):

| Approach | Where | Why |
|----------|-------|-----|
| `useReducer` | Explorer controls/filters | Complex state with 20+ actions, needs fine-grained updates |
| Zustand | DevDataQdrant store | Global state shared across many tabs/components |
| React Context | AccessControlContext | Simple RBAC flags needed app-wide |

**No React Query or SWR.** API calls use raw `fetch()` with typed responses. Each page co-locates its own API module.

### 6.3 API Communication Pattern

All API calls follow this pattern:
```typescript
const token = await getApiAccessToken();
const response = await fetch(`${API_BASE_URL}/api/v2/...`, {
  headers: { 'X-MS-TOKEN-AAD': token }
});
```

**Gotcha:** The auth token header is `X-MS-TOKEN-AAD`, not `Authorization: Bearer`. This is a custom header, not standard OAuth.

### 6.4 UI Conventions

Read `client/AGENTS.md` for the full design system. Key rules:
- **Light mode only.** No dark mode.
- **No vertical scroll on the main layout.** Content areas scroll internally.
- **Base font size is 12-13px**, not the standard 16px. This is intentional for information density.
- **No red in charts.** Red is reserved for UBS brand CTA and error states only.
- **No pie/doughnut charts.** Always horizontal bar charts for categorical data.
- **Custom components only.** No Shadcn, MUI, Radix, or Headless UI. Everything is plain HTML + Tailwind.

---

## 7. Ingestion Pipeline (The Core Write Path)

This is the most complex part of the system. The full pipeline lives in `server/pipelines/controls/`.

### 7.1 Upload Flow
1. **File Upload**: Client sends CSV via TUS protocol → `server/pipelines/controls/api/tus.py`
2. **Validation**: CSV parsed + validated against Pydantic schema → `schema_validation.py`
3. **Batch Creation**: Upload registered as batch with status "validated" → `jobs/models.py`
4. **Upload ID**: Auto-generated format `UPL-YYYY-XXXX` via database sequence

### 7.2 Model Runner Flow (Mock ML Pipeline)
After upload, 4 model runners execute sequentially on the uploaded data:
1. **Feature Prep** → Cleans text into 3 features (what, why, where) + hashes
2. **Embeddings** → Generates 3072-dim vectors per feature (mock: deterministic hash-based)
3. **Enrichment** → 7 W-criteria scores + 7 operational criteria + narratives
4. **Taxonomy** → Risk taxonomy assignment

Each model writes JSONL output + `.index.json` sidecar to `data_ingested/model_runs/{model_name}/`.

### 7.3 Ingestion Flow (Celery Task)
Triggered via `POST /api/v2/ingestion/start` → queues `run_controls_ingestion_task`:

1. Acquire global ingestion lock (Redis, only one at a time)
2. Acquire per-upload processing lock (filesystem)
3. Readiness check: all 4 model outputs present + control IDs match
4. **Source delta detection**: Compare `last_modified_on` against existing records
5. **Close old versions**: `UPDATE SET tx_to = now()` for changed controls
6. **Insert new versions**: Batch insert into ver + relation tables
7. **AI model delta**: Hash comparison for enrichment/taxonomy/feature_prep
8. **Qdrant delta**: Per-feature hash comparison, selective vector updates
9. **Similarity recompute**: Hybrid scoring (semantic cosine + TF-IDF cosine)
10. Release locks
11. Invalidate caches (explorer, stats, dashboard namespaces)
12. Capture dashboard snapshot

**Gotcha:** The ingestion service in `ingest/service.py` is ~58KB and contains the entire ETL pipeline. It's not split into smaller services. If you need to modify ingestion behavior, this is the file.

**Gotcha:** Similarity computation (`similarity.py`, 901 lines) has a "hub guardrail" — if more than 20,000 controls are affected by a delta, it falls back from incremental mode to full rebuild.

### 7.4 Similarity Scoring

The hybrid similarity algorithm in `server/pipelines/controls/similarity.py`:

```
For each pair of L1 Active Key controls:
  per_feature_score = (cosine_similarity(embedding_A, embedding_B) + tfidf_cosine(text_A, text_B)) / 2
  final_score = average(per_feature_score for each of 3 features)

  if score >= 0.90: "near_duplicate"
  if 0.60 <= score < 0.90: "weak_similar"
  if score < 0.60: discarded
```

---

## 8. Authentication & Authorization

### 8.1 Flow
1. Client authenticates with Azure AD via MSAL redirect
2. Client calls `GET /api/auth/access` with user token in `X-MS-TOKEN-AAD` header
3. Backend exchanges token for Graph API token (MSAL On-Behalf-Of)
4. Backend queries Microsoft Graph for user profile + group memberships
5. Backend maps groups to access flags and returns `AccessResponse`

### 8.2 Access Flags
| Flag | Server Setting | Controls Access To |
|------|---------------|-------------------|
| `hasChatAccess` | `group_chat_access` | Agentic chat feature |
| `hasExplorerAccess` | `group_explorer_access` | Explorer + dashboards |
| `hasPipelinesIngestionAccess` | `group_pipelines_ingestion_access` | Upload + ingestion |
| `hasPipelinesAdminAccess` | `group_pipelines_admin_access` | Admin pipeline functions |
| `hasDevDataAccess` | `group_dev_data_access` | Database browser + snapshots |

### 8.3 Backend Guard Pattern
```python
from server.auth.dependencies import get_token_from_header
from server.auth.service import get_access_control

async def _require_explorer_access(token: str = Depends(get_token_from_header)):
    access = await get_access_control(token)
    if not access.hasExplorerAccess:
        raise HTTPException(status_code=403)
    return token
```

Each router defines its own `_require_*_access` dependency.

### 8.4 Auth Cache (Non-Standard)

Auth responses are cached with a **dual-TTL strategy**:
- **Primary cache**: 120 seconds at `auth:access:{token_hash}`
- **Stale cache**: +600 seconds at `auth:stale:{token_hash}`
- If Graph API is down, stale cache is served (graceful degradation)
- Per-token `asyncio.Lock` prevents thundering herd on cache miss

**Gotcha:** Auth cache keys use `auth:` prefix, not `cache:` prefix. This is deliberate so that `invalidate_all()` (which targets `cache:*`) does not wipe auth sessions.

---

## 9. Caching System

**Location:** `server/cache/`

### 9.1 Usage
```python
from server.cache import cached

@cached(namespace="explorer", ttl=3600)
async def get_function_tree(...) -> list[TreeNodeResponse]:
    ...
```

### 9.2 Key Format
`cache:{namespace}:{function_name}:{sha256_of_args[:16]}`

**Gotcha:** Trailing `None` args are stripped for key generation. So `f()` and `f(None)` produce the same cache key. This is intentional.

### 9.3 Invalidation
- After ingestion: `invalidate_namespace("explorer")`, `invalidate_namespace("stats")`, `invalidate_namespace("dashboard")`
- Uses Redis SCAN (non-blocking) to find and delete matching keys
- TTL is a safety net, not the primary invalidation mechanism

### 9.4 Serialization
Cache values are stored as type-wrapped JSON. Pydantic models are serialized with their type info so they can be deserialized back to the correct class. See `server/cache/serialization.py`.

### 9.5 What NOT to Cache
- Health endpoints (need real-time status)
- DevData endpoints (developers need live data)
- Write/mutation operations
- Functions with side effects

---

## 10. Background Tasks (Celery)

**Configuration:** `server/workers/celery_app.py`

### 10.1 Queues
| Queue | Purpose | Tasks |
|-------|---------|-------|
| `default` | General | Fallback |
| `ingestion` | Heavy data ingestion | `run_controls_ingestion_task` |
| `compute` | CPU-intensive work | Model computations |
| `export` | Report generation | `run_export_task` |
| `snapshot` | Database backups | `create_pg_snapshot_task`, `restore_pg_snapshot_task`, etc. |

### 10.2 Key Design Decisions
- **No automatic retries.** User must explicitly retry failed tasks.
- **Results persist for 24 hours** in Redis DB 2 with gzip compression.
- **Workers restart after 5 tasks** (`max_tasks_per_child=5`) to prevent memory leaks.
- **Prefetch multiplier = 1** — one task per worker at a time.
- **Global ingestion lock** — only one ingestion can run at a time (Redis-based).
- **Per-template export lock** — prevents duplicate exports for same template+date (5-min expiry).

### 10.3 Running Celery
```bash
cd server
celery -A server.workers.celery_app worker \
  --loglevel=info \
  --concurrency=1 \
  --pool=prefork \
  --max-tasks-per-child=5 \
  --queue=ingestion,compute,default,export,snapshot
```

**Gotcha:** Celery workers create their own PostgreSQL engine on startup (`worker_process_init` signal) with a smaller pool (3 size, 5 overflow). They do NOT share the FastAPI engine.

---

## 11. Explorer (The Core Read Path)

### 11.1 Search
**File:** `server/explorer/controls/service.py`

Supports 4 search modes:
- **keyword**: PostgreSQL `tsvector` full-text search on feature_prep fields
- **semantic**: Qdrant vector search using OpenAI `text-embedding-3-large` (3072 dims)
- **hybrid**: Both keyword + semantic combined via **Reciprocal Rank Fusion (RRF, k=60)**
- **id**: Direct lookup by control ID

### 11.2 Filter Cascade
Sidebar filters (function tree, location tree, consolidated entities, assessment units, risk themes) can be applied in cascade mode — selecting a parent auto-selects children. The filter state is managed client-side in `useFilterState` (useReducer).

### 11.3 Dashboard
Portfolio dashboards compute metrics server-side and cache results. Dashboard types:
- Executive Overview (KPI cards)
- Document Quality (W-criteria scoring)
- Regulatory Compliance (risk theme heatmaps)
- Lifecycle Heatmap (status distribution)
- Concentration Analysis (control density)
- Redundancy Analysis (similarity clusters)

---

## 12. File Storage Layout

### 12.1 Data Paths (from settings)
| Setting | Default Relative Path | Purpose |
|---------|----------------------|---------|
| `DATA_INGESTED_PATH` | `data_ingested/` | Uploaded files + model outputs |
| `CONTEXT_PROVIDERS_PATH` | `context_providers/` | Org charts + risk themes |
| `EXPORT_DIR` | `data_exports/` | Generated exports |
| `POSTGRES_BACKUP_PATH` | (configured) | PostgreSQL snapshots |
| `QDRANT_BACKUP_PATH` | (configured) | Qdrant snapshots |

### 12.2 Data Ingested Structure
```
data_ingested/
├── controls/                     Uploaded files
│   ├── UPL-2026-0001.csv        Original CSV
│   └── UPL-2026-0001.jsonl      Validated JSONL
├── model_runs/                   ML outputs
│   ├── taxonomy/UPL-*.jsonl     + .index.json sidecar
│   ├── enrichment/UPL-*.jsonl   + .index.json sidecar
│   ├── feature_prep/UPL-*.jsonl + .index.json sidecar
│   └── embeddings/UPL-*.npz    + .index.json sidecar
├── .tus_temp/                    TUS resumable upload chunks
└── .state/
    └── processing_lock.json      File-based processing lock (2hr expiry)
```

### 12.3 Context Providers Structure
```
context_providers/
├── organization/
│   └── YYYY-MM-DD/              Date-partitioned org chart JSONL
└── risk_theme/
    └── YYYY-MM-DD/              Date-partitioned risk theme JSONL
```

**Gotcha:** Context providers are date-partitioned. The system uses the **latest date folder** (sorted descending) as the current data source. See `storage.py:get_latest_context_date()`.

---

## 13. Non-Standard Patterns & Gotchas

### 13.1 UV Package Manager (NOT pip)
The server uses [UV (astral)](https://docs.astral.sh/uv/) for dependency management. Never use `pip install`. Always use:
```bash
uv add "package_name"       # Add dependency
uv run script.py            # Run script
uv sync                     # Install all deps
```

### 13.2 SQLAlchemy Table Objects (NOT ORM Classes)
The domain schemas (controls, orgs, risks, assessment_units) use `Table(...)` objects registered on shared metadata, not declarative `class Model(Base)` patterns. Only the jobs module uses ORM classes.

### 13.3 Auth Token Header
The auth token is passed in `X-MS-TOKEN-AAD` header, not `Authorization: Bearer`. This is used across all authenticated endpoints.

### 13.4 Dual-TTL Auth Cache
Auth has a primary cache (120s) and a stale cache (600s). During Azure AD outages, stale data is served. The `auth:` prefix is separate from `cache:` to prevent accidental invalidation.

### 13.5 HNSW Toggle During Bulk Ingestion
During vector upserts of >500 points, HNSW indexing on the Qdrant collection is temporarily disabled for performance. It's re-enabled after the upload completes and the system waits for "green" status.

### 13.6 Processing Lock (Dual: Redis + Filesystem)
Ingestion uses TWO lock mechanisms:
- **Redis lock** (`ingestion:lock` in DB 3): Global "only one ingestion" guard
- **Filesystem lock** (`processing_lock.json`): Per-upload guard with 2-hour expiry and stale cleanup

### 13.7 Celery Worker PostgreSQL Engine
Celery workers create their own SQLAlchemy engine in `worker_process_init` signal handler. They don't (and can't) share the async engine from FastAPI.

### 13.8 Model Runners Are Mocks
The ML model runners in `pipelines/controls/model_runners/` generate mock/deterministic output. They simulate the behavior of real models using hashing and random generation. Real model integration would replace these files.

### 13.9 Snapshot Metadata Is Disk-Based
PostgreSQL and Qdrant snapshot metadata is stored in `metadata.json` files on disk, NOT in database tables. This was a deliberate choice so snapshots can be managed even when the database is being restored.

### 13.10 No Test Suite
There is no test directory or test configuration. The `TESTING_GUIDE.md` describes manual testing procedures for the multi-worker setup.

### 13.11 No Dark Mode
The client is light-mode only. No dark mode toggle or theme switching.

### 13.12 CRA Build System
The client uses Create React App (react-scripts), NOT Vite. There's no exposed webpack config.

---

## 14. Environment Configuration

### 14.1 Server (.env)
See `server/.env.template` for all variables. Key groups:

**Required (no defaults):**
- `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET` — Azure AD
- `GRAPH_SCOPES` — Microsoft Graph API scopes
- 5 group IDs — Access control groups
- `POSTGRES_URL` — PostgreSQL connection (must be `postgresql+asyncpg://...`)
- `REDIS_URL` — Redis connection
- `ALLOWED_ORIGINS` — CORS origins (comma-separated)
- All `*_PATH` settings — File storage directories

**With defaults:**
- `QDRANT_URL` (default: `http://localhost:16333`)
- `QDRANT_COLLECTION_PREFIX` (default: `nfr_connect`)
- `POSTGRES_POOL_SIZE` (default: 5)
- `CELERY_*` settings (see section 10)

### 14.2 Client (.env)
See `client/.env.template`. All must have `REACT_APP_` prefix:
- `REACT_APP_CLIENT_ID` — Azure AD app registration
- `REACT_APP_AUTHORITY` — Azure AD tenant
- `REACT_APP_API_BASE_URL` — Backend URL (default: `http://localhost:8000`)
- `REACT_APP_API_SCOPES` — API permission scope

---

## 15. How to Search This Codebase

### Find a specific API endpoint
```bash
# Search for route path
grep -r '"/v2/explorer' server/ --include="*.py"
# Or search for route decorator
grep -r '@router\.(get|post|put|delete)' server/ --include="*.py"
```

### Find where a database table is defined
```bash
# Tables are defined as Table() objects
grep -r 'Table(' server/pipelines/ --include="*.py"
# Or for jobs ORM models
grep -r 'class.*Base' server/jobs/ --include="*.py"
```

### Find where a cache namespace is used
```bash
grep -r 'namespace=' server/cache/ server/explorer/ server/pipelines/ --include="*.py"
grep -r 'invalidate_namespace' server/ --include="*.py"
```

### Find a Celery task definition
```bash
grep -r '@.*\.task\|\.delay(' server/workers/ --include="*.py"
```

### Find where a setting is consumed
```bash
grep -r 'settings\.\|get_settings()' server/ --include="*.py"
```

### Find frontend API calls to a specific backend endpoint
```bash
grep -r 'fetch.*api/v2' client/src/ --include="*.ts" --include="*.tsx"
```

### Find a React component definition
```bash
grep -r 'export.*function\|export.*const.*=' client/src/pages/ --include="*.tsx"
```

### Find state management hooks
```bash
grep -r 'useReducer\|create(' client/src/ --include="*.ts" --include="*.tsx"
```

### Find Pydantic models
```bash
grep -r 'class.*BaseModel\|class.*BaseSettings' server/ --include="*.py"
```

### Find SQLAlchemy migrations
```bash
ls server/alembic/versions/
```

---

## 16. Running the Application

### Backend
```bash
cd server

# Terminal 1: Start Celery worker
celery -A server.workers.celery_app worker \
  --loglevel=info --concurrency=1 --pool=prefork \
  --queue=ingestion,compute,default,export,snapshot

# Terminal 2: Start API server (development)
uv run uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Start API server (production, multi-worker)
gunicorn server.main:app \
  --workers 4 --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 --timeout 120
```

### Frontend
```bash
cd client
npm install
npm start    # Dev server on http://localhost:3000
```

### Prerequisites
- PostgreSQL running (connection string in .env)
- Redis running (connection string in .env)
- Qdrant running (default: http://localhost:16333)
- Azure AD app registration configured
- Context providers data in `context_providers/` directory

---

## 17. Alembic Migrations

**Location:** `server/alembic/`

**Running migrations:**
```bash
cd server
uv run alembic upgrade head          # Apply all
uv run alembic downgrade -1          # Rollback one
uv run alembic revision --autogenerate -m "description"  # Generate new
```

**Gotcha:** The `alembic/env.py` imports all schema modules to ensure tables are registered on the shared metadata before autogeneration. If you add a new schema module, you must import it in `env.py`.

**Gotcha:** Migrations run automatically on app startup (Phase 2, leader-only). You don't need to run them manually unless developing new migrations.

---

## 18. Export System

**Location:** `server/pipelines/controls/export/`

**Pattern:** Template-based exports using a registry pattern.

```
export/
├── base.py          BaseExporter class (abstract: query() + build_workbook())
├── registry.py      Template registry (name → exporter class)
├── service.py       Export orchestration
└── templates/
    └── orad_em_controls.py    Concrete export template
```

**Adding a new export template:**
1. Create a new file in `export/templates/`
2. Subclass `BaseExporter` and implement `query()` and `build_workbook()`
3. Register in `registry.py`

**Exports are cached on disk.** If a file for the same template + evaluation date already exists, it's served directly without re-querying.

---

## 19. Snapshot System

**Location:** `server/devdata/`

**Two independent snapshot systems:**

| System | Service File | Storage | Method |
|--------|------------|---------|--------|
| PostgreSQL | `snapshot_service.py` | `POSTGRES_BACKUP_PATH` | `pg_dump` / `pg_restore` subprocess |
| Qdrant | `qdrant_snapshot_service.py` | `QDRANT_BACKUP_PATH` | Qdrant HTTP API with streaming download |

**Both use disk-based `metadata.json`** for tracking snapshots. Database tables are NOT used for snapshot metadata because the database might be mid-restore when metadata is needed.

**Gotcha:** Qdrant snapshots use HTTP streaming with 1MB chunks and a 600-second timeout. Large collections can take significant time to snapshot.

**Gotcha:** PostgreSQL restore has an optional pre-restore backup feature — it automatically takes a snapshot before restoring, so you can undo a bad restore.
