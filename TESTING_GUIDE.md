# Multi-Worker + Celery Testing Guide

## Quick Start Testing

### 1. Terminal 1 - Start Celery Worker
```bash
cd /Users/preetam/Develop/application/server

# Start Celery worker for ingestion tasks
celery -A server.workers.celery_app worker \
  --loglevel=info \
  --concurrency=1 \
  --pool=prefork \
  --max-tasks-per-child=5 \
  --queue=ingestion,compute,default
```

### 2. Terminal 2 - Start API Server with Multiple Workers
```bash
cd /Users/preetam/Develop/application/server

# Export macOS fork safety fix (if on macOS)
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Start API with 4 workers
gunicorn server.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --keep-alive 5 \
  --log-level info
```

## Testing the Implementation

### 1. Verify Multi-Worker Synchronization
Watch the logs when starting the API server. You should see:
- One worker acquiring locks for initialization tasks
- Other workers waiting and detecting completion
- No duplicate initialization (migrations, Qdrant collections, etc.)

Example log output:
```
worker-12345 acquired lock for alembic_migration - executing initialization
worker-12346 waiting for another worker to complete alembic_migration
worker-12345 successfully completed alembic_migration
worker-12346 detected alembic_migration completed by another worker
```

### 2. Test Non-Blocking Ingestion

#### Start an Ingestion
```bash
# Get list of validated batches
curl http://localhost:8000/api/v2/ingestion/batches \
  -H "Authorization: Bearer YOUR_TOKEN"

# Start ingestion for a batch
curl -X POST http://localhost:8000/api/v2/ingestion/insert \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"batch_id": 1}'

# Response will include job_id
```

#### Monitor Progress
```bash
# Check job status (poll every few seconds)
curl http://localhost:8000/api/v2/ingestion/job/{job_id} \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Verify Non-Blocking
While ingestion is running, test that other APIs still work:
```bash
# These should respond immediately, not blocked by ingestion
curl http://localhost:8000/api/auth/refresh \
  -H "Authorization: Bearer YOUR_TOKEN"

curl http://localhost:8000/api/explorer/stats \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Monitor Celery Tasks

```bash
# Check active tasks
celery -A server.workers.celery_app inspect active

# Check task statistics
celery -A server.workers.celery_app inspect stats

# Monitor in real-time
celery -A server.workers.celery_app events
```

### 4. Check Redis State

```bash
redis-cli

# Check Celery broker queue
> SELECT 1
> LLEN celery

# Check task results
> SELECT 2
> KEYS *

# Check worker coordination
> SELECT 3
> KEYS worker:*

# Check ingestion lock
> GET "ingestion:lock"
```

## Expected Behavior

✅ **What Should Work:**
- API remains responsive during 5-6 minute ingestions
- Progress updates every ~10% in the UI
- Multiple workers share single Qdrant/PostgreSQL state
- Only one ingestion runs at a time (global lock)
- Token refresh continues working during ingestion
- Graceful error handling without crashes

❌ **What Won't Work (by design):**
- Running multiple ingestions simultaneously (locked)
- Ingestion retry on failure (manual retry only)
- Progress updates more granular than 10% increments

## Troubleshooting

### If ingestion doesn't start:
1. Check Celery worker is running: `ps aux | grep celery`
2. Check Redis connection: `redis-cli ping`
3. Check for existing lock: `redis-cli -n 3 GET "ingestion:lock"`

### If API calls timeout:
1. Verify multiple workers are running: `ps aux | grep gunicorn`
2. Check worker logs for errors
3. Ensure OBJC_DISABLE_INITIALIZE_FORK_SAFETY is set (macOS)

### If progress doesn't update:
1. Check job status endpoint returns batch_id
2. Verify Celery task is updating state
3. Check Redis result backend (DB 2)

### If Qdrant errors occur:
1. Check daemon detection is working (should log "Running in daemon process")
2. Verify parallel workers = 1 in Celery context
3. Check Qdrant service logs for multiprocessing errors

## Performance Metrics

Monitor these during testing:
- API response times (should stay < 1s during ingestion)
- Memory usage per worker (~500MB API, ~2GB Celery)
- PostgreSQL connections (should be ~23 total)
- Redis memory usage (minimal, just task metadata)

## Cleanup After Testing

```bash
# Stop all processes
pkill -f celery
pkill -f gunicorn

# Clear any stuck locks
redis-cli -n 3 DEL "ingestion:lock"

# Clear completed tasks (optional)
redis-cli -n 2 FLUSHDB
```

## Next Steps After Testing

1. **Monitor for 24 hours** - Check for memory leaks, stuck tasks
2. **Test failure scenarios** - Kill Celery mid-ingestion, check recovery
3. **Load test** - Run many concurrent API calls during ingestion
4. **Production config** - Set up systemd services, log rotation, monitoring