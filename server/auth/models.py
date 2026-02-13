from pydantic import BaseModel


class AccessResponse(BaseModel):
    hasChatAccess: bool
    hasDashboardAccess: bool
    hasPipelinesIngestionAccess: bool
    hasPipelinesAdminAccess: bool
    hasDevDataAccess: bool
    user: str
