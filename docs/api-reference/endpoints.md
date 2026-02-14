---
sidebar_position: 1
title: API Endpoints
description: Complete NFR Connect API reference
---

# API Endpoints

NFR Connect exposes a RESTful API for programmatic integration. All endpoints require authentication unless otherwise noted.

## Base URL

```
Production: https://api.nfr-connect.example.com/v1
Development: http://localhost:8000/api
```

## Authentication

All requests must include a valid Bearer token:

```bash
curl -H "Authorization: Bearer <token>" https://api.nfr-connect.example.com/v1/risks
```

## Endpoints

### Access Control

#### Check User Access

```http
GET /api/auth/access
```

Returns the current user's access rights.

**Response:**

```json
{
  "hasChatAccess": true,
  "hasExplorerAccess": true,
  "user": "John Doe"
}
```

---

### Risk Events

#### List Risk Events

```http
GET /api/risks
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (active, closed, all) |
| `severity` | integer | Minimum severity level (1-5) |
| `from` | datetime | Start date (ISO 8601) |
| `to` | datetime | End date (ISO 8601) |
| `limit` | integer | Max results (default: 100) |
| `offset` | integer | Pagination offset |

**Response:**

```json
{
  "data": [
    {
      "id": "evt-12345",
      "type": "LOSS_EVENT",
      "severity": 3,
      "description": "Unauthorized transaction",
      "status": "active",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 142,
  "limit": 100,
  "offset": 0
}
```

#### Create Risk Event

```http
POST /api/risks
```

**Request Body:**

```json
{
  "type": "LOSS_EVENT",
  "severity": 3,
  "description": "Description of the event",
  "taxonomy_code": "OPR-002-001",
  "business_unit": "Trading Operations"
}
```

---

### Models

#### List Registered Models

```http
GET /api/models
```

#### Register Model

```http
POST /api/models/register
```

#### Push Model Results

```http
POST /api/models/{model_id}/results
```

---

### Simulations

#### Submit Simulation Job

```http
POST /api/simulations/submit
```

#### Get Simulation Status

```http
GET /api/simulations/{job_id}/status
```

#### Get Simulation Results

```http
GET /api/simulations/{job_id}/results
```

---

## Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid or missing token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |

:::tip SDK Available
For Python and TypeScript integrations, consider using our official SDKs which handle authentication and error handling automatically.
:::
