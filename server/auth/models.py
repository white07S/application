from pydantic import BaseModel


class AccessResponse(BaseModel):
    hasChatAccess: bool
    hasDashboardAccess: bool
    user: str
