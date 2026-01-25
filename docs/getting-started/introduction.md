---
sidebar_position: 1
title: Introduction
description: Welcome to NFR Connect Documentation
---

# Introduction to NFR Connect

Welcome to **NFR Connect** - your comprehensive platform for Non-Financial Risk intelligence and management.

:::info Prerequisites
This documentation is publicly available and does not require authentication. For access to the Dashboard and Chat features, please sign in to the main application.
:::

## What is NFR Connect?

NFR Connect is an enterprise-grade platform designed to transform how organizations identify, assess, and manage non-financial risks. Built on cutting-edge AI and graph technologies, it provides:

- **Agentic Reasoning** - Autonomous LLM agents that reason over complex unstructured data to identify emerging risks
- **Graph Visualization** - Interactive knowledge graphs revealing hidden relationships and risk propagation paths
- **Automated Taxonomy** - DICE model for intelligent control-to-risk mapping
- **Real-time Monitoring** - Live tracking of risk signals across your entire enterprise landscape

## Platform Components

| Component | Description | Access |
|-----------|-------------|--------|
| Dashboard | Visual analytics and KPI monitoring | Requires authentication |
| Chat | Agentic AI assistant for risk queries | Requires authentication |
| Glossary | NFR terminology and definitions | Requires authentication |
| Documentation | Technical guides and API reference | Public |

## Quick Links

- [Installation Guide](/getting-started/installation) - Set up your development environment
- [Authentication](/getting-started/authentication) - Configure Azure AD integration
- [Risk Model Integration](/models/risk-model-integration) - Connect external risk models
- [API Reference](/api-reference/endpoints) - Complete API documentation

## Architecture Overview

NFR Connect follows a modern microservices architecture:

```
┌─────────────────────────────────────────────────────────┐
│                    NFR Connect Platform                  │
├─────────────────────────────────────────────────────────┤
│  Frontend (React)  │  Backend (FastAPI)  │  AI Models   │
├─────────────────────────────────────────────────────────┤
│              Azure AD Authentication                     │
├─────────────────────────────────────────────────────────┤
│     SurrealDB     │    Graph Store    │   Vector DB    │
└─────────────────────────────────────────────────────────┘
```

:::warning Enterprise Use Only
NFR Connect is designed for internal enterprise use. All data processing complies with organizational security policies and regulatory requirements.
:::
