# PostgreSQL Snapshot Integration with Data Pipeline

## Overview

The PostgreSQL snapshot feature integrates with your existing data pipeline that consists of:
1. Context Provider Ingestion (Organizations, Risk Themes)
2. Control Ingestion
3. Qdrant Vector Indexing

## Data Pipeline Architecture

```
┌─────────────────┐
│ Context Files   │
│ (JSONL)         │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Context Provider│
│ Ingestion       │
└────────┬────────┘
         │
         v
┌─────────────────┐       ┌──────────────┐
│ PostgreSQL DB   │<----->│  Snapshots   │
│ - Organizations │       │  (pg_dump)   │
│ - Risk Themes   │       └──────────────┘
│ - Controls      │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Control         │
│ Ingestion       │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Qdrant Vector   │
│ Indexing        │
└─────────────────┘
```

## Snapshot Points in the Pipeline

### 1. **Pre-Ingestion Snapshot** (Clean State)
- **When**: Before any data ingestion
- **Purpose**: Capture clean database schema
- **Contains**: Empty tables with latest Alembic migrations
```bash
python scripts/snapshot_cli.py create --name "Clean Schema v1.0"
```

### 2. **Post-Context Snapshot** (After Context Providers)
- **When**: After context provider ingestion completes
- **Purpose**: Baseline organizational and risk data
- **Contains**:
  - Organization hierarchies
  - Risk themes and taxonomies
  - Assessment units
```bash
python scripts/ingest_context_providers.py
python scripts/snapshot_cli.py create --name "Context Providers Loaded"
```

### 3. **Post-Controls Snapshot** (After Controls)
- **When**: After control ingestion completes
- **Purpose**: Full data before vector indexing
- **Contains**:
  - All context data
  - Control records
  - AI model enrichments
```bash
# After control ingestion via UI or API
python scripts/snapshot_cli.py create --name "Controls Ingested - $(date +%Y%m%d)"
```

### 4. **Production-Ready Snapshot** (Fully Indexed)
- **When**: After Qdrant indexing completes
- **Purpose**: Complete production-ready state
- **Contains**:
  - All PostgreSQL data
  - Note: Qdrant vectors are NOT in the snapshot
```bash
python scripts/snapshot_cli.py create --name "Production Ready v1.0"
```

## Restore Scenarios and Required Actions

### Scenario 1: Full System Restore

When restoring a complete snapshot, you need to consider what needs to be re-run:

```bash
# 1. Restore the PostgreSQL snapshot
python scripts/snapshot_cli.py restore --id SNAP-2024-0001

# 2. Restart the application (to reconnect to restored DB)
supervisorctl restart nfr-connect-server

# 3. Check what data is in the restored snapshot
psql -d app_db -c "SELECT COUNT(*) FROM src_orgs_ref_function;"
psql -d app_db -c "SELECT COUNT(*) FROM src_controls_ref_control;"

# 4. Re-index Qdrant if needed (vectors are NOT in PostgreSQL snapshot)
# This depends on what was in the snapshot:
# - If snapshot was post-controls, re-run Qdrant indexing
# - If snapshot was post-context, re-run control ingestion + Qdrant
```

### Scenario 2: Rollback After Failed Ingestion

```bash
# Create a checkpoint before risky operation
python scripts/snapshot_cli.py create --name "Pre-ingestion checkpoint"

# Run your ingestion...
# If it fails:

python scripts/snapshot_cli.py restore --id SNAP-2024-0002
# No need to re-run previous successful ingestions
```

### Scenario 3: Development/Testing Reset

```bash
# Create a golden snapshot for testing
python scripts/snapshot_cli.py create --name "Test Dataset v1"

# Run tests, experiments...

# Reset to clean state
python scripts/snapshot_cli.py restore --id SNAP-2024-0003 --skip-backup
```

## Automated Pipeline with Snapshots

### Complete Pipeline Script

```bash
#!/bin/bash
# complete_pipeline.sh - Full data pipeline with automatic snapshots

set -e  # Exit on error

echo "Starting complete data pipeline with snapshots..."

# 1. Create pre-ingestion snapshot
echo "Creating pre-ingestion snapshot..."
python scripts/snapshot_cli.py create --name "Pre-Pipeline-$(date +%Y%m%d-%H%M%S)"

# 2. Run context provider ingestion
echo "Ingesting context providers..."
python scripts/ingest_context_providers.py

# 3. Create post-context snapshot
echo "Creating post-context snapshot..."
python scripts/snapshot_cli.py create --name "Post-Context-$(date +%Y%m%d-%H%M%S)"

# 4. Run control ingestion (via API or script)
echo "Ingesting controls..."
# Your control ingestion command here
curl -X POST http://localhost:8000/api/v2/pipelines/controls/ingest \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@controls.csv"

# 5. Wait for ingestion to complete
echo "Waiting for control ingestion..."
# Poll job status
sleep 60  # Or implement proper polling

# 6. Create post-controls snapshot
echo "Creating post-controls snapshot..."
python scripts/snapshot_cli.py create --name "Post-Controls-$(date +%Y%m%d-%H%M%S)"

# 7. Run Qdrant indexing
echo "Indexing to Qdrant..."
python scripts/index_to_qdrant.py

# 8. Create final snapshot
echo "Creating production snapshot..."
python scripts/snapshot_cli.py create --name "Production-$(date +%Y%m%d-%H%M%S)"

echo "Pipeline complete with snapshots!"
```

## Important Considerations

### 1. **Qdrant Vectors Are NOT in PostgreSQL Snapshots**

PostgreSQL snapshots only contain relational data. After restore, you must:
- Re-index all vectors to Qdrant if needed
- Or backup/restore Qdrant separately using its own snapshot API

### 2. **File Storage Is Separate**

Uploaded files in `DATA_INGESTED_PATH` are NOT in database snapshots:
- CSV files in `controls/`
- Model outputs in `model_runs/`
- Consider separate file system backups

### 3. **Lock Prevention**

The snapshot system prevents concurrent operations:
- Only one snapshot/restore can run at a time
- Ingestion should be paused during snapshot/restore
- Check status before operations:
```bash
python scripts/snapshot_cli.py status
```

### 4. **Alembic Migration Compatibility**

Snapshots track the Alembic version:
- Restore will warn if database schema has changed
- Use `--force` flag to restore anyway (risky)
- Better to migrate data than force restore

### 5. **Performance Optimization**

With parallel processing (`-j` flag):
- Snapshot creation: ~3-5x faster with `-j 4`
- Restore: ~2-4x faster with `-j 4`
- Adjust based on CPU cores and I/O capacity

## Recommended Snapshot Strategy

### Development Environment
```
- Daily: Post-context snapshot (lightweight)
- Weekly: Full production snapshot
- Before major changes: Manual checkpoint
```

### Production Environment
```
- Hourly: During business hours (if data changes frequently)
- Daily: Overnight full snapshot
- Before deployments: Manual checkpoint
- After successful ingestions: Automatic snapshot
```

### Retention Policy
```
- Latest 7 daily snapshots
- Latest 4 weekly snapshots
- Latest 3 monthly snapshots
- All pre-deployment snapshots for 30 days
```

## Monitoring and Alerts

### Health Checks

```python
# Check if snapshots are being created
async def check_snapshot_health():
    async with get_db_session_context() as db:
        latest = await db.execute(
            select(PostgresSnapshot)
            .where(PostgresSnapshot.status == 'completed')
            .order_by(desc(PostgresSnapshot.created_at))
            .limit(1)
        )
        latest_snapshot = latest.scalar_one_or_none()

        if not latest_snapshot:
            alert("No snapshots found!")
        elif (datetime.now(timezone.utc) - latest_snapshot.created_at).days > 1:
            alert(f"Latest snapshot is {days} days old!")
```

### Disk Space Monitoring

```bash
# Monitor backup directory size
du -sh $POSTGRES_BACKUP_PATH

# Alert if space is low
df -h $POSTGRES_BACKUP_PATH | awk '$5 > 80 {print "Warning: Backup disk usage above 80%"}'
```

## Troubleshooting

### Issue: Restore fails with "database in use"
**Solution**: Stop all applications before restore
```bash
supervisorctl stop all
python scripts/snapshot_cli.py restore --id SNAP-2024-0001
supervisorctl start all
```

### Issue: Snapshot creation is slow
**Solution**: Increase parallel jobs
```bash
# In .env
POSTGRES_BACKUP_PARALLEL_JOBS=8
```

### Issue: Qdrant out of sync after restore
**Solution**: Re-index from PostgreSQL
```python
# Force full re-index
from server.pipelines.controls.qdrant_service import index_all_controls
await index_all_controls(force_reindex=True)
```

### Issue: Lock file stuck
**Solution**: Manually clear lock
```bash
rm $POSTGRES_BACKUP_PATH/.locks/snapshot_operation.lock
```

## API Integration

### Trigger Snapshot After Successful Ingestion

```python
# In your ingestion completion handler
async def on_ingestion_complete(upload_id: str):
    # Create automatic snapshot
    response = await client.post(
        "/api/v2/devdata/snapshots/create",
        json={
            "name": f"Auto-snapshot after {upload_id}",
            "description": f"Automatic snapshot after successful ingestion of {upload_id}"
        }
    )

    # Poll until complete
    job_id = response.json()["job_id"]
    while True:
        status = await client.get(f"/api/v2/devdata/snapshots/job/{job_id}/status")
        if status.json()["status"] in ["completed", "failed"]:
            break
        await asyncio.sleep(5)
```