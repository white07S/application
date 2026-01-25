---
sidebar_position: 2
title: Stress Testing
description: Configure and run stress test scenarios
---

# Stress Testing

NFR Connect provides comprehensive stress testing capabilities for assessing risk resilience under adverse conditions.

## Scenario Types

| Type | Description | Use Case |
|------|-------------|----------|
| Historical | Based on actual past events | Market crash, pandemic |
| Hypothetical | Custom adverse scenarios | Cyber attack, system failure |
| Reverse | Find breaking points | Capital adequacy testing |

## Running Stress Tests

### Define a Scenario

```json title="stress-scenario.json"
{
  "name": "Market Stress Q4 2024",
  "type": "hypothetical",
  "parameters": {
    "market_shock": -0.25,
    "volatility_multiplier": 2.5,
    "correlation_breakdown": true
  },
  "duration_days": 30
}
```

### Execute via API

```typescript title="Execute stress test"
const result = await fetch('/api/stress-tests/execute', {
  method: 'POST',
  body: JSON.stringify({
    scenario_id: 'market-stress-q4-2024',
    portfolios: ['trading', 'banking-book'],
    output_format: 'detailed'
  })
});
```

## Results Analysis

Stress test results include:

- **P&L Impact**: Projected profit/loss under stress
- **Capital Impact**: Effect on regulatory capital ratios
- **Liquidity Impact**: Cash flow stress analysis
- **Operational Impact**: Process and system resilience

:::info Regulatory Compliance
Stress testing results are automatically formatted for regulatory submissions including CCAR, DFAST, and EBA requirements.
:::
