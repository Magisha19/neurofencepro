"""FastAPI dependencies. user_id always comes from the token, never from the request."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.tokens import decode_access_token
from app.db.models import User
from app.db.session import get_db

_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Invalid or expired token",  # same message for every failure case
        headers={"WWW-Authenticate": "Bearer"},
    )


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise _unauthorized()
    user_id = decode_access_token(creds.credentials, request.app.state.settings)
    if user_id is None:
        raise _unauthorized()
    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized()
    return user