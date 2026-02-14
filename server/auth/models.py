from pydantic import BaseModel


class AccessResponse(BaseModel):
    hasChatAccess: bool
    hasExplorerAccess: bool
    hasPipelinesIngestionAccess: bool
    hasPipelinesAdminAccess: bool
    hasDevDataAccess: bool
    user: str
