"""JWT (HS256). Claims: sub, iat, exp, jti only. No username or personal data."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import Settings


def create_access_token(user_id: int, settings: Settings) -> tuple[str, int]:
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, settings.access_token_minutes * 60


def decode_access_token(token: str, settings: Settings) -> int | None:
    """Return the user id, or None for ANY problem (same outcome for every failure)."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat", "jti"]},
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        return None