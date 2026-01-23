import logging
import os

import httpx
import msal
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging to ensure INFO logs are displayed
logging.basicConfig(level=logging.INFO)

load_dotenv()


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


# Configuration
TENANT_ID = get_required_env("TENANT_ID")
CLIENT_ID = get_required_env("CLIENT_ID")
CLIENT_SECRET = get_required_env("CLIENT_SECRET")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

scope_values = [scope.strip() for scope in os.getenv("GRAPH_SCOPES", "").split(",") if scope.strip()]
if not scope_values:
    raise RuntimeError("GRAPH_SCOPES must contain at least one scope")
SCOPE = scope_values

# Access Groups
GROUP_CHAT_ACCESS = get_required_env("GROUP_CHAT_ACCESS")
GROUP_DASHBOARD_ACCESS = get_required_env("GROUP_DASHBOARD_ACCESS")

# Client origins
allowed_origins_raw = get_required_env("ALLOWED_ORIGINS")
ALLOWED_ORIGINS = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]
if not ALLOWED_ORIGINS:
    raise RuntimeError("ALLOWED_ORIGINS must contain at least one origin")

app = FastAPI()

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MSAL Confidential Client
cca = msal.ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET,
)

class AccessResponse(BaseModel):
    hasChatAccess: bool
    hasDashboardAccess: bool
    user: str

async def get_token_from_header(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid header format")
    return authorization.split(" ")[1]

@app.get("/api/auth/access", response_model=AccessResponse)
async def get_access_control(token: str = Depends(get_token_from_header)):
    # 1. Acquire Token On-Behalf-Of (OBO) for Graph API
    result = cca.acquire_token_on_behalf_of(
        user_assertion=token,
        scopes=SCOPE
    )

    if "error" in result:
        logging.error(f"OBO Error: {result.get('error_description')}")
        raise HTTPException(status_code=401, detail="Could not authenticate with backend")

    graph_token = result["access_token"]
    
    # 2. Call Graph API to check group membership
    async with httpx.AsyncClient() as client:
        # Check membership (using transistiveMemberOf to get nested groups too)
        # Note: listing all groups might be heavy, but checking specific membership is better.
        # Alternatively, we can just fetch all group IDs the user belongs to.
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me/transitiveMemberOf?$select=id",
            headers={"Authorization": f"Bearer {graph_token}"}
        )
        
        if response.status_code != 200:
            logging.error(f"Graph API Error: {response.text}")
            raise HTTPException(status_code=500, detail="Failed to fetch user groups")
            
        groups_data = response.json()
        group_ids = [g["id"] for g in groups_data.get("value", [])]
        
        # 3. Fetch User Profile for display name
        profile_response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {graph_token}"}
        )
        profile = profile_response.json()
        user_name = profile.get("displayName", "User")
        user_id = profile.get("id", "Unknown")

        has_chat = GROUP_CHAT_ACCESS in group_ids
        has_dashboard = GROUP_DASHBOARD_ACCESS in group_ids

        # Detailed Logging
        logging.info(f"--- Access Check for User: {user_name} ({user_id}) ---")
        logging.info(f"User Groups ({len(group_ids)}): {group_ids}")
        logging.info(f"Checking Chat Access (Required: {GROUP_CHAT_ACCESS}): {'GRANTED' if has_chat else 'DENIED'}")
        logging.info(f"Checking Dashboard Access (Required: {GROUP_DASHBOARD_ACCESS}): {'GRANTED' if has_dashboard else 'DENIED'}")
        logging.info("---------------------------------------------------")

    return AccessResponse(
        hasChatAccess=has_chat,
        hasDashboardAccess=has_dashboard,
        user=user_name
    )

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("UVICORN_HOST", "0.0.0.0")
    port = int(os.getenv("UVICORN_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
