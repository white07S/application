---
sidebar_position: 3
title: Error Codes
description: API error codes and troubleshooting
---

# Error Codes

NFR Connect uses standard HTTP status codes along with detailed error responses.

## Error Response Format

All errors follow a consistent structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": [
      {
        "field": "severity",
        "message": "Must be between 1 and 5"
      }
    ],
    "request_id": "req-abc123"
  }
}
```

## Error Codes Reference

### Authentication Errors (401)

| Code | Description | Resolution |
|------|-------------|------------|
| `INVALID_TOKEN` | Token is malformed or expired | Obtain a new token |
| `TOKEN_EXPIRED` | Token has expired | Refresh the token |
| `MISSING_AUTH` | No authorization header | Include Bearer token |

### Authorization Errors (403)

| Code | Description | Resolution |
|------|-------------|------------|
| `INSUFFICIENT_SCOPE` | Token lacks required scope | Request appropriate scopes |
| `ACCESS_DENIED` | User lacks permission | Contact administrator |
| `IP_NOT_WHITELISTED` | IP address not allowed | Add IP to whitelist |

### Validation Errors (400)

| Code | Description | Resolution |
|------|-------------|------------|
| `VALIDATION_ERROR` | Request body validation failed | Check `details` array |
| `INVALID_PARAMETER` | Query parameter invalid | Review parameter format |
| `MISSING_REQUIRED` | Required field missing | Include all required fields |

### Resource Errors (404/409)

| Code | Description | Resolution |
|------|-------------|------------|
| `NOT_FOUND` | Resource does not exist | Verify resource ID |
| `ALREADY_EXISTS` | Resource already exists | Use update endpoint |
| `CONFLICT` | State conflict | Retry with fresh data |

### Server Errors (500)

| Code | Description | Resolution |
|------|-------------|------------|
| `INTERNAL_ERROR` | Unexpected server error | Retry with exponential backoff |
| `SERVICE_UNAVAILABLE` | Temporary outage | Check status page |
| `DATABASE_ERROR` | Database operation failed | Retry later |

## Troubleshooting

### Common Issues

<Info title="Request ID">
Always include the `request_id` from error responses when contacting support - it helps us trace the exact issue.
</Info>

**"Token expired" immediately after login**
- Check that your system clock is synchronized
- Ensure the token issuer time is correct

**"Insufficient scope" with valid token**
- Review the scopes requested during authentication
- Some endpoints require additional scopes like `write:models`

**Intermittent 500 errors**
- Implement retry logic with exponential backoff
- Check the status page for ongoing incidents
