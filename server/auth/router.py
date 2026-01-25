from fastapi import APIRouter, Depends

from .dependencies import get_token_from_header
from .models import AccessResponse
from .service import get_access_control

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/access", response_model=AccessResponse)
async def get_access_control_route(token: str = Depends(get_token_from_header)):
    return await get_access_control(token)
