---
sidebar_position: 2
title: Rate Limits
description: API rate limiting and quotas
---

# Rate Limits

NFR Connect implements rate limiting to ensure fair usage and system stability.

## Limits by Tier

| Tier | Requests/Minute | Requests/Day | Concurrent |
|------|-----------------|--------------|------------|
| Standard | 60 | 10,000 | 5 |
| Professional | 300 | 100,000 | 20 |
| Enterprise | 1,000 | Unlimited | 100 |

## Rate Limit Headers

All API responses include rate limit information:

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1704067200
```

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests per window |
| `X-RateLimit-Remaining` | Requests remaining in window |
| `X-RateLimit-Reset` | Unix timestamp when window resets |

## Handling Rate Limits

When rate limited, you'll receive a `429 Too Many Requests` response:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please retry after 30 seconds.",
  "retry_after": 30
}
```

### Best Practices

1. **Implement exponential backoff** for retries
2. **Cache responses** where appropriate
3. **Use webhooks** for real-time updates instead of polling
4. **Batch requests** when possible

```typescript title="Retry with exponential backoff"
async function fetchWithRetry(url: string, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    const response = await fetch(url);

    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After') || Math.pow(2, i);
      await sleep(retryAfter * 1000);
      continue;
    }

    return response;
  }
  throw new Error('Max retries exceeded');
}
```

<Warning title="Abuse Prevention">
Sustained abuse of rate limits may result in temporary or permanent API access revocation.
</Warning>
