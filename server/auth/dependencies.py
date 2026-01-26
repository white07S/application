from typing import Optional

from fastapi import Header, HTTPException


async def get_token_from_header(
    x_ms_token_aad: Optional[str] = Header(None, alias="X-MS-TOKEN-AAD"),
) -> str:
    if not x_ms_token_aad:
        raise HTTPException(status_code=401, detail="Missing X-MS-TOKEN-AAD header")
    return x_ms_token_aad
