from __future__ import annotations

from datetime import UTC, datetime

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


def validate_api_token(token: str, settings: Settings) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.api_jwt_secret,
            algorithms=[settings.api_jwt_algorithm],
            audience=settings.api_jwt_audience,
            issuer=settings.api_jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}") from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing subject in API token")

    exp = payload.get("exp")
    if exp is not None and datetime.fromtimestamp(exp, tz=UTC) <= datetime.now(tz=UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API token expired")

    return payload


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    payload = validate_api_token(credentials.credentials, settings)
    return str(payload["sub"])
