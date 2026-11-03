"""Experiments CRUD. user_id always comes from the token; other users' rows look like 404."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.deps import client_ip, get_current_user
from app.db.models import (
    BehaviourResult,
    Experiment,
    ExperimentEvent,
    FuzzingResult,
    Metric,
    Report,
    RiskScoreRecord,
    User,
)
from app.db.session import get_db
from app.schemas import (
    ExperimentConfig,
    ExperimentCreate,
    ExperimentList,
    ExperimentOut,
    ExperimentStatus,
    Provenance,
    Stage,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/experiments", tags=["experiments"])

_CANCELLABLE = {ExperimentStatus.QUEUED.value, ExperimentStatus.RUNNING.value}
_RERUNNABLE = {
    ExperimentStatus.COMPLETED.value,
    ExperimentStatus.FAILED.value,
    ExperimentStatus.CANCELLED.value,
}
_CHILD_MODELS = (ExperimentEvent, Metric, BehaviourResult, FuzzingResult, RiskScoreRecord, Report)


def to_out(e: Experiment) -> ExperimentOut:
    return ExperimentOut(
        id=e.id,
        name=e.name,
        status=ExperimentStatus(e.status),
        stage=Stage(e.stage),
        progress=e.progress,
        config=ExperimentConfig.model_validate(e.config_json),
        config_hash=e.config_hash,
        feature_provenance=Provenance(e.feature_provenance) if e.feature_provenance else None,
        error=e.error,
        created_at=e.created_at,
        started_at=e.started_at,
        finished_at=e.finished_at,
    )


def _new_experiment(user_id: int, config: ExperimentConfig) -> Experiment:
    return Experiment(
        user_id=user_id,
        name=config.name,
        status=ExperimentStatus.QUEUED.value,
        stage=Stage.QUEUED.value,
        progress=0.0,
        config_json=config.model_dump(mode="json"),
        config_hash=config.config_hash(),
    )


def _get_owned(db: Session, user: User, experiment_id: int) -> Experiment:
    exp = db.scalar(
        select(Experiment).where(Experiment.id == experiment_id, Experiment.user_id == user.id)
    )
    if exp is None:  # missing and "not yours" are indistinguishable on purpose
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


@router.post("", response_model=ExperimentOut, status_code=201)
def create_experiment(
    body: ExperimentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExperimentOut:
    exp = _new_experiment(user.id, body)
    db.add(exp)
    db.commit()
    record_audit(
        db, "experiment.create", user_id=user.id, resource_type="experiment",
        resource_id=exp.id, detail={"config_hash": exp.config_hash}, ip=client_ip(request),
    )
    return to_out(exp)


@router.get("", response_model=ExperimentList)
def list_experiments(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExperimentList:
    where = Experiment.user_id == user.id
    total = db.scalar(select(func.count()).select_from(Experiment).where(where)) or 0
    rows = db.scalars(
        select(Experiment)
        .where(where)
        .order_by(Experiment.created_at.desc(), Experiment.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ExperimentList(
        items=[to_out(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/{experiment_id}", response_model=ExperimentOut)
def get_experiment(
    experiment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExperimentOut:
    return to_out(_get_owned(db, user, experiment_id))


@router.post("/{experiment_id}/cancel", response_model=ExperimentOut)
def cancel_experiment(
    experiment_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExperimentOut:
    exp = _get_owned(db, user, experiment_id)
    if exp.status not in _CANCELLABLE:
        raise HTTPException(status_code=409, detail=f"Cannot cancel an experiment that is {exp.status}")
    exp.status = ExperimentStatus.CANCELLED.value
    exp.finished_at = datetime.now(UTC)
    db.commit()
    record_audit(
        db, "experiment.cancel", user_id=user.id, resource_type="experiment",
        resource_id=exp.id, ip=client_ip(request),
    )
    return to_out(exp)


@router.post("/{experiment_id}/rerun", response_model=ExperimentOut, status_code=201)
def rerun_experiment(
    experiment_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExperimentOut:
    old = _get_owned(db, user, experiment_id)
    if old.status not in _RERUNNABLE:
        raise HTTPException(status_code=409, detail=f"Cannot rerun an experiment that is {old.status}")
    new = _new_experiment(user.id, ExperimentConfig.model_validate(old.config_json))
    db.add(new)
    db.commit()
    record_audit(
        db, "experiment.rerun", user_id=user.id, resource_type="experiment",
        resource_id=new.id, detail={"rerun_of": old.id}, ip=client_ip(request),
    )
    return to_out(new)


@router.delete("/{experiment_id}", status_code=204)
def delete_experiment(
    experiment_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    exp = _get_owned(db, user, experiment_id)
    for model in _CHILD_MODELS:  # explicit, so it does not depend on SQLite's FK pragma
        db.execute(delete(model).where(model.experiment_id == exp.id))
    db.delete(exp)
    db.commit()
    record_audit(
        db, "experiment.delete", user_id=user.id, resource_type="experiment",
        resource_id=experiment_id, ip=client_ip(request),
    )
    return Response(status_code=204)