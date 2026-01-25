---
sidebar_position: 3
title: Mermaid Diagrams Test
description: Testing Mermaid diagram rendering
---

# Mermaid Diagram Examples

This page demonstrates various Mermaid diagram types supported in the documentation.

## Flowchart

### Basic Flowchart

```mermaid
flowchart TD
    A[Risk Event] --> B{Assessment}
    B -->|High| C[Immediate Action]
    B -->|Medium| D[Monitor]
    B -->|Low| E[Document]
    C --> F[Resolution]
    D --> F
    E --> G[Archive]
```

### Horizontal Flowchart

```mermaid
flowchart LR
    A[Input] --> B[Process]
    B --> C{Decision}
    C -->|Yes| D[Output A]
    C -->|No| E[Output B]
```

## Sequence Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant A as API Gateway
    participant S as Service
    participant D as Database

    U->>A: Request Data
    A->>S: Forward Request
    S->>D: Query
    D-->>S: Results
    S-->>A: Response
    A-->>U: Data

    Note over U,D: Complete request cycle
```

## Entity Relationship Diagram

```mermaid
erDiagram
    RISK ||--o{ CONTROL : "mitigated by"
    CONTROL ||--|{ ASSESSMENT : "evaluated in"
    RISK }|--|| TAXONOMY : "categorized by"
    ASSESSMENT ||--o{ FINDING : contains

    RISK {
        string id PK
        string description
        int severity
        date created_at
    }

    CONTROL {
        string id PK
        string name
        string type
        boolean active
    }
```

## State Diagram

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Review: Submit
    Review --> Approved: Accept
    Review --> Draft: Reject
    Approved --> Active: Publish
    Active --> Archived: Archive
    Archived --> [*]

    state Review {
        [*] --> Pending
        Pending --> InReview: Assign Reviewer
        InReview --> Complete: Review Done
    }
```

## Class Diagram

```mermaid
classDiagram
    class RiskEvent {
        +String id
        +String type
        +int severity
        +Date timestamp
        +assess()
        +escalate()
    }

    class Control {
        +String id
        +String name
        +Boolean active
        +evaluate()
    }

    class Assessment {
        +String id
        +String status
        +create()
        +complete()
    }

    RiskEvent "1" --> "*" Control : mitigated by
    Control "1" --> "*" Assessment : evaluated in
```

## Gantt Chart

```mermaid
gantt
    title Risk Assessment Timeline
    dateFormat  YYYY-MM-DD

    section Discovery
    Risk Identification    :a1, 2024-01-01, 7d
    Initial Assessment     :a2, after a1, 5d

    section Analysis
    Deep Analysis         :a3, after a2, 10d
    Control Review        :a4, after a2, 8d

    section Remediation
    Action Planning       :a5, after a3, 5d
    Implementation        :a6, after a5, 14d

    section Verification
    Testing               :a7, after a6, 7d
    Sign-off              :a8, after a7, 3d
```

## Pie Chart

```mermaid
pie title Risk Distribution by Category
    "Operational" : 45
    "Compliance" : 25
    "Strategic" : 15
    "Reputational" : 10
    "Other" : 5
```

## Git Graph

```mermaid
gitGraph
    commit
    commit
    branch feature
    checkout feature
    commit
    commit
    checkout main
    merge feature
    commit
    branch hotfix
    checkout hotfix
    commit
    checkout main
    merge hotfix
```

:::info Mermaid Version
Diagrams are rendered using Mermaid.js. Some advanced features may require specific Mermaid versions. Check the [Mermaid documentation](https://mermaid.js.org/) for syntax details.
:::
