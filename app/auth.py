"""
SoftRYT Backend — API Key Authentication
==========================================
FastAPI dependency that validates the `x-api-key` header
on every request. Rejects unauthorized callers with 401.
"""

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.config import get_settings

# Declare the expected header name
_api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


async def require_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str:
    """
    Dependency that checks the `x-api-key` header against the
    configured API_KEY. Returns the key on success, raises 401 otherwise.
    """
    settings = get_settings()

    if not api_key or api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Pass it via the 'x-api-key' header.",
        )
    return api_key
