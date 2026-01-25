---
sidebar_position: 4
title: Code Highlighting Test
description: Testing code syntax highlighting
---

# Code Syntax Highlighting

This page demonstrates code block rendering with syntax highlighting for various languages.

## TypeScript

```typescript title="src/api/client.ts"
interface RiskEntity {
  id: string;
  name: string;
  category: 'operational' | 'compliance' | 'strategic';
  severity: number;
  createdAt: Date;
}

async function fetchRiskEntities(
  filters?: Partial<RiskEntity>
): Promise<RiskEntity[]> {
  const params = new URLSearchParams();

  if (filters?.category) {
    params.set('category', filters.category);
  }

  const response = await fetch(`/api/risks?${params}`);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

// Usage
const risks = await fetchRiskEntities({ category: 'operational' });
console.log(`Found ${risks.length} operational risks`);
```

## Python

```python title="server/main.py"
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

app = FastAPI()

class RiskEntity(BaseModel):
    id: str
    name: str
    category: str
    severity: float
    created_at: datetime

class RiskFilter(BaseModel):
    category: Optional[str] = None
    min_severity: float = 0.0
    limit: int = 100

@app.get("/api/risks", response_model=List[RiskEntity])
async def get_risks(
    filters: RiskFilter = Depends(),
    db: Database = Depends(get_db)
):
    """Retrieve risk entities with optional filtering."""
    query = "SELECT * FROM risks WHERE severity >= $1"
    params = [filters.min_severity]

    if filters.category:
        query += " AND category = $2"
        params.append(filters.category)

    query += f" LIMIT {filters.limit}"

    results = await db.fetch_all(query, params)
    return [RiskEntity(**r) for r in results]
```

## SQL

```sql title="queries/risk_summary.sql"
-- Calculate risk summary by category
SELECT
    category,
    COUNT(*) as risk_count,
    AVG(severity) as avg_severity,
    MAX(severity) as max_severity,
    MIN(created_at) as oldest_risk,
    MAX(updated_at) as latest_update
FROM risk_entities
WHERE
    status = 'active'
    AND created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY category
HAVING COUNT(*) > 5
ORDER BY avg_severity DESC;

-- Find correlated risks
WITH risk_connections AS (
    SELECT
        r1.id as risk_a,
        r2.id as risk_b,
        COUNT(*) as shared_controls
    FROM risk_control_mapping r1
    JOIN risk_control_mapping r2
        ON r1.control_id = r2.control_id
        AND r1.id < r2.id
    GROUP BY r1.id, r2.id
)
SELECT * FROM risk_connections
WHERE shared_controls >= 3;
```

## JSON

```json title="config/risk-model.json"
{
  "model": {
    "id": "urn:nfr:model:monte-carlo-v4",
    "version": "4.2.1",
    "type": "simulation"
  },
  "parameters": {
    "iterations": 100000,
    "confidence_levels": [0.95, 0.99, 0.999],
    "distribution": {
      "type": "generalized_pareto",
      "shape": 0.5,
      "scale": 1000000
    }
  },
  "output": {
    "metrics": ["var", "es", "expected_loss"],
    "format": "json",
    "precision": 2
  }
}
```

## YAML

```yaml title="docker-compose.yaml"
version: '3.8'

services:
  api:
    build:
      context: ./server
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  client:
    build:
      context: ./client
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://api:8000

  db:
    image: surrealdb/surrealdb:latest
    volumes:
      - db_data:/data
    command: start --log debug file:/data/database.db

volumes:
  db_data:
```

## Bash / Shell

```bash title="scripts/deploy.sh"
#!/bin/bash
set -euo pipefail

# Configuration
ENVIRONMENT=${1:-staging}
VERSION=$(git describe --tags --always)
REGISTRY="registry.example.com/nfr-connect"

echo "Deploying version $VERSION to $ENVIRONMENT..."

# Build and push images
docker build -t "$REGISTRY/api:$VERSION" ./server
docker build -t "$REGISTRY/client:$VERSION" ./client

docker push "$REGISTRY/api:$VERSION"
docker push "$REGISTRY/client:$VERSION"

# Deploy to Kubernetes
kubectl config use-context "$ENVIRONMENT"
kubectl set image deployment/api api="$REGISTRY/api:$VERSION"
kubectl set image deployment/client client="$REGISTRY/client:$VERSION"

# Wait for rollout
kubectl rollout status deployment/api --timeout=300s
kubectl rollout status deployment/client --timeout=300s

echo "Deployment complete!"
```

## Line Highlighting

You can highlight specific lines:

```typescript {3-5,9}
function calculateRisk(events: RiskEvent[]): number {
  let totalRisk = 0;
  // highlight-start
  for (const event of events) {
    totalRisk += event.severity * event.probability;
  }
  // highlight-end

  // Normalize to 0-100 scale
  return Math.min(totalRisk / events.length * 20, 100);
}
```

## Diff Syntax

```diff
- const oldConfig = { timeout: 5000 };
+ const newConfig = { timeout: 10000, retries: 3 };

  function fetchData(url) {
-   return fetch(url, oldConfig);
+   return fetch(url, newConfig);
  }
```

:::tip Copy Button
All code blocks include a copy button in the top-right corner. Click it to copy the code to your clipboard.
:::
