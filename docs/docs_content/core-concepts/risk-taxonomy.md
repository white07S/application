---
sidebar_position: 1
title: Risk Taxonomy
description: Understanding the NFR Connect risk classification system
---

# Risk Taxonomy

NFR Connect uses a hierarchical taxonomy to classify and organize non-financial risks across the enterprise.

## Taxonomy Structure

The risk taxonomy follows a four-level hierarchy:

```
Level 1: Risk Category
└── Level 2: Risk Type
    └── Level 3: Risk Sub-type
        └── Level 4: Risk Event
```

## Risk Categories

| Category | Code | Description |
|----------|------|-------------|
| Operational Risk | OPR | Risks from failed internal processes, people, or systems |
| Compliance Risk | CMP | Risks from regulatory non-compliance |
| Strategic Risk | STR | Risks from business decisions and external factors |
| Reputational Risk | REP | Risks to brand and stakeholder trust |

## DICE Model Integration

The **DICE** (Data Insights Clustering Enrichment) model automatically maps control failures to the appropriate taxonomy nodes:

$$
P(\text{taxonomy}|\text{event}) = \frac{P(\text{event}|\text{taxonomy}) \cdot P(\text{taxonomy})}{P(\text{event})}
$$

Where:
- $P(\text{taxonomy}|\text{event})$ is the probability of a taxonomy classification given an event
- $P(\text{event}|\text{taxonomy})$ is the likelihood of the event under that taxonomy
- $P(\text{taxonomy})$ is the prior probability of the taxonomy node

<Tip title="Automatic Classification">
When new risk events are ingested, DICE automatically suggests taxonomy mappings with confidence scores. Events with confidence > 0.85 are auto-classified; others require manual review.
</Tip>

## Taxonomy API

Query the risk taxonomy programmatically:

```typescript title="Example: Fetch taxonomy tree"
const response = await fetch('/api/taxonomy/tree');
const taxonomy = await response.json();

// Response structure
{
  "id": "OPR",
  "label": "Operational Risk",
  "children": [
    {
      "id": "OPR-001",
      "label": "Process Risk",
      "children": [...]
    }
  ]
}
```

## Related Documentation

- [Event Types](/core-concepts/event-types) - Understanding risk event classification
- [Impact Analysis](/core-concepts/impact-analysis) - Assessing risk impact
