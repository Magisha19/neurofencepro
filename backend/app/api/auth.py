from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import client_ip
from app.auth.passwords import hash_password, verify_password
from app.auth.tokens import create_access_token
from app.db.models import User
from app.db.session import get_db
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=201)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> UserPublic:
    settings = request.app.state.settings
    if db.scalar(select(User).where(User.username == body.username)) is not None:
        raise HTTPException(status_code=409, detail="Username already taken")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password, settings.bcrypt_rounds),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two requests raced for the same username
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already taken") from None
    record_audit(
        db, "auth.register", user_id=user.id, resource_type="user",
        resource_id=user.id, ip=client_ip(request),
    )
    return UserPublic(id=user.id, username=user.username, created_at=user.created_at)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    settings = request.app.state.settings
    limiter = request.app.state.login_limiter
    ip = client_ip(request) or "unknown"
    username = body.username.strip().lower()
    key = (ip, username)

    wait = limiter.retry_after(key)
    if wait:
        record_audit(db, "auth.rate_limited", ip=ip)
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(wait)},
        )

    user = db.scalar(select(User).where(User.username == username))
    # Always run one bcrypt check so timing does not reveal whether the user exists.
    stored_hash = user.password_hash if user is not None else request.app.state.dummy_hash
    password_ok = verify_password(body.password, stored_hash)

    if user is None or not password_ok:
        limiter.record_failure(key)
        record_audit(
            db, "auth.login.failure",
            user_id=user.id if user is not None else None, ip=ip,
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    limiter.reset(key)
    record_audit(db, "auth.login.success", user_id=user.id, ip=ip)
    token, expires_in = create_access_token(user.id, settings)
    return TokenResponse(access_token=token, expires_in=expires_in)