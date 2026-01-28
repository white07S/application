from pydantic import BaseModel


class AccessResponse(BaseModel):
    hasChatAccess: bool
    hasDashboardAccess: bool
    hasPipelinesIngestionAccess: bool
    hasPipelinesAdminAccess: bool
    user: str
