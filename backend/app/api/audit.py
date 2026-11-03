from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.models import AuditLog, User
from app.db.session import get_db
from app.schemas import AuditLogList, AuditLogOut

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=AuditLogList)
def list_audit(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogList:
    where = AuditLog.user_id == user.id  # isolation: only the caller's own rows
    total = db.scalar(select(func.count()).select_from(AuditLog).where(where)) or 0
    rows = db.scalars(
        select(AuditLog)
        .where(where)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    items = [
        AuditLogOut(
            id=r.id, action=r.action, resource_type=r.resource_type,
            resource_id=r.resource_id, detail=r.detail or {}, created_at=r.created_at,
        )
        for r in rows
    ]
    return AuditLogList(items=items, total=total, limit=limit, offset=offset)