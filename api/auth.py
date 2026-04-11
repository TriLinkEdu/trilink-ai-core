from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from config.settings import Settings

_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(_header)) -> str:
    expected = Settings().INTERNAL_API_KEY
    if not expected:
        return api_key  # key not configured — open (dev mode)
    if api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return api_key
