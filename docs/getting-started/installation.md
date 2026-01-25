---
sidebar_position: 2
title: Installation
description: Set up your NFR Connect development environment
---

# Installation

This guide walks you through setting up NFR Connect for local development.

## System Requirements

| Requirement | Minimum Version |
|-------------|-----------------|
| Node.js | 18.0 or higher |
| Python | 3.12 or higher |
| npm | 9.0 or higher |

## Quick Start

### 1. Clone the Repository

```bash title="Terminal"
git clone https://github.com/ubs/nfr-connect.git
cd nfr-connect
```

### 2. Install Client Dependencies

```bash title="Terminal"
cd client
npm install
```

### 3. Install Server Dependencies

```bash title="Terminal"
cd ../server
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create `.env` files in both `client` and `server` directories:

```bash title="client/.env"
REACT_APP_CLIENT_ID=your-azure-client-id
REACT_APP_AUTHORITY=https://login.microsoftonline.com/your-tenant-id
REACT_APP_REDIRECT_URI=http://localhost:3000
REACT_APP_API_BASE_URL=http://localhost:8000
REACT_APP_LOGIN_SCOPES=User.Read
REACT_APP_API_SCOPES=api://your-api-scope/access_as_user
```

```bash title="server/.env"
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
GRAPH_SCOPES=User.Read,GroupMember.Read.All
```

:::tip Azure AD Setup
Contact your Azure administrator to obtain the required application registration credentials.
:::

### 5. Start Development Servers

```bash title="Terminal"
# Start the backend server
cd server
uvicorn main:app --reload --port 8000

# In a new terminal, start the frontend
cd client
npm start
```

The application will be available at `http://localhost:3000`.

## Verify Installation

After starting both servers, you should be able to:

1. Access the home page at `http://localhost:3000`
2. See the Microsoft Sign In button
3. View the documentation at `http://localhost:3000/docs`

:::info Troubleshooting
If you encounter CORS errors, ensure both servers are running and the `ALLOWED_ORIGINS` in the server `.env` includes `http://localhost:3000`.
:::
