# Multi-Worker + Celery Implementation Complete

## What Was Implemented

### 1. **Dependencies Added** (`pyproject.toml`)
- `celery[redis]>=5.3.0` - For background task processing
- `gunicorn>=21.2.0` - For multi-worker deployment

### 2. **Settings Configuration** (`server/settings.py`)
- Added Celery configuration:
  - `celery_broker_db`: Redis DB for task queue (default: 1)
  - `celery_result_db`: Redis DB for results (default: 2)
  - `celery_max_tasks_per_child`: Worker restart after N tasks (default: 5)
  - `celery_task_time_limit`: Hard timeout (default: 3600s)
  - `celery_task_soft_time_limit`: Soft timeout (default: 3000s)
- Added computed properties for Celery URLs

### 3. **Celery Infrastructure** (`server/workers/`)
- `celery_app.py`: Celery configuration with:
  - Separate queues for ingestion and compute tasks
  - No auto-retry (manual retry as requested)
  - Progress tracking support
  - Result persistence for 24 hours
- `tasks/ingestion.py`: Ingestion task with:
  - 10% increment progress updates
  - Global lock (only one ingestion at a time)
  - Automatic cache invalidation
  - Dashboard snapshot capture

### 4. **Worker Synchronization** (`server/core/worker_sync.py`)
- `WorkerSync` class for distributed coordination using Redis
- Ensures one-time initialization tasks run only once:
  - Alembic migrations
  - Qdrant collection creation
  - Storage directory setup
  - Cache warmup
  - Dashboard snapshot seeding
- Uses Redis SETNX for atomic locking

### 5. **Redis Configuration** (`server/config/redis.py`)
- Extended to support multiple databases:
  - DB 0: Cache (existing)
  - DB 1: Celery broker
  - DB 2: Celery results
  - DB 3: Worker coordination
- Both async (FastAPI) and sync (Celery) clients

### 6. **Main Application** (`server/main.py`)
- Multi-worker safe initialization:
  - Phase 1: Per-worker connections (PostgreSQL, Redis)
  - Phase 2: One-time tasks (migrations, directories)
  - Phase 3: Shared resources (Qdrant)
  - Phase 4: Optional optimizations (cache warmup)
- Automatic pool size adjustment for multiple workers
- Worker ID tracking in logs

### 7. **Ingestion API** (`server/pipelines/controls/api/processing.py`)
- **REMOVED**:
  - `asyncio.create_task` background execution
  - `_run_ingestion_background` function
  - JobTracker dependencies
  - Thread-based processing
- **ADDED**:
  - Celery task submission
  - Task status polling from Celery
  - Job cancellation support
  - Active jobs listing

## How to Run

### Prerequisites
```bash
# Install dependencies
cd server
pip install -e .

# Or just install new dependencies
pip install celery[redis] gunicorn
```

### Step-by-Step Manual Startup

#### Terminal 1: Start Celery Worker
```bash
cd /path/to/application/server

# Run Celery worker
celery -A server.workers.celery_app worker \
  --loglevel=info \
  --concurrency=1 \
  --pool=prefork \
  --max-tasks-per-child=5 \
  --queue=ingestion,compute,default
```

#### Terminal 2: Start API Server
```bash
cd /path/to/application/server

# One-time setup (if needed)
python -m alembic upgrade head
python scripts/ingest_context_providers.py

# Start API with 4 workers
gunicorn server.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --keep-alive 5
```

## What You'll See in Logs

### Worker Synchronization
```
worker-12345: Starting NFR Connect server
worker-12346: Starting NFR Connect server
worker-12345 acquired lock for alembic_migration - executing initialization
worker-12346 waiting for another worker to complete alembic_migration
worker-12345 successfully completed alembic_migration
worker-12346 detected alembic_migration completed by another worker
```

### Celery Task Execution
```
Starting ingestion task: job_id=xxx, batch_id=1, upload_id=CTRL_001
Task server.workers.tasks.ingestion.run_controls_ingestion started
Ingestion completed successfully: total=1000, new=500, changed=300, unchanged=200
```

## API Changes

### Start Ingestion
```bash
POST /api/v2/ingestion/insert
{
  "batch_id": 1
}

Response:
{
  "success": true,
  "message": "Ingestion job queued successfully",
  "job_id": "uuid-here",
  "batch_id": 1,
  "upload_id": "CTRL_001"
}
```

### Check Job Status
```bash
GET /api/v2/ingestion/job/{job_id}

Response:
{
  "job_id": "uuid-here",
  "status": "running",  # queued | running | completed | failed
  "progress_percent": 30,
  "current_step": "Processing controls...",
  "records_total": 1000,
  "records_processed": 300,
  ...
}
```

### Cancel Job
```bash
DELETE /api/v2/ingestion/job/{job_id}

Response:
{
  "success": true,
  "message": "Job cancelled"
}
```

### List Active Jobs
```bash
GET /api/v2/ingestion/jobs/active

Response:
{
  "active_jobs": [...],
  "total": 1
}
```

## Key Benefits

1. **No More Blocking**: Ingestion runs in separate Celery process
2. **Multi-Worker Safe**: Initialization happens only once
3. **Progress Tracking**: Real-time updates via polling
4. **Failure Isolation**: Celery worker crash doesn't affect API
5. **Resource Management**: Workers restart after N tasks (prevents memory leaks)
6. **Job Control**: Cancel running jobs, list active jobs

## Monitoring

### Check Celery Workers
```bash
celery -A server.workers.celery_app inspect active
celery -A server.workers.celery_app inspect stats
```

### Redis Monitoring
```bash
redis-cli
> SELECT 1  # Celery broker
> LLEN celery
> SELECT 2  # Results
> KEYS *
> SELECT 3  # Coordination
> KEYS worker:*
```

## Troubleshooting

### If workers don't synchronize:
- Check Redis connectivity: `redis-cli ping`
- Check coordination keys: `redis-cli -n 3 KEYS "worker:*"`
- Clear stuck locks: `redis-cli -n 3 DEL worker:init:*`

### If Celery tasks don't run:
- Check worker is running: `ps aux | grep celery`
- Check queue: `celery -A server.workers.celery_app inspect active`
- Check broker connection: `redis-cli -n 1 LLEN celery`

### If ingestion seems stuck:
- Check lock: `redis-cli -n 3 GET "ingestion:lock"`
- Force unlock: `redis-cli -n 3 DEL "ingestion:lock"`
- Check task state via API: `GET /api/v2/ingestion/job/{job_id}`

## Performance Notes

- API workers: 4 workers × 5 connections = 20 PostgreSQL connections
- Celery workers: 1 worker × 3 connections = 3 PostgreSQL connections
- Total: 23 connections (safe under default max_connections=100)
- Memory: ~500MB per API worker, ~2GB per Celery worker

## Next Steps

1. **Test the implementation**:
   - Start Celery worker and API
   - Trigger an ingestion
   - Verify it doesn't block other API calls

2. **Production deployment**:
   - Create systemd services for Celery and Gunicorn
   - Set up process monitoring (supervisor, systemd)
   - Configure log rotation

3. **Optional enhancements**:
   - Add Flower for Celery monitoring UI
   - Implement WebSocket for real-time progress
   - Add more background tasks (exports, reports)