"""Append-only audit log. Never stores passwords, tokens or request bodies."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog

ACTIONS = frozenset(
    {
        "auth.register",
        "auth.login.success",
        "auth.login.failure",
        "auth.rate_limited",
        "experiment.create",
        "experiment.cancel",
        "experiment.rerun",
        "experiment.delete",
        "report.create",
        "report.download",
    }
)
FORBIDDEN_DETAIL_KEYS = frozenset(
    {"password", "password_hash", "token", "access_token", "authorization", "secret"}
)


def record_audit(
    db: Session,
    action: str,
    *,
    user_id: int | None = None,
    resource_type: str | None = None,
    resource_id: int | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    if action not in ACTIONS:
        raise ValueError(f"unknown audit action: {action}")
    detail = detail or {}
    for key, value in detail.items():
        if key.lower() in FORBIDDEN_DETAIL_KEYS:
            raise ValueError(f"audit detail must not contain '{key}'")
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError("audit detail values must be simple scalars")
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            ip=(ip or None) and ip[:45],
        )
    )
    db.commit()