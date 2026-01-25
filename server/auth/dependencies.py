from fastapi import Header, HTTPException


async def get_token_from_header(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid header format")
    return authorization.split(" ", 1)[1]
