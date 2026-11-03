"""Experiments CRUD. user_id always comes from the token; other users' rows look like 404."""
from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.auth.deps import client_ip, get_current_user
from app.core.metrics import summarize
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
    BehaviourResultsResponse,
    BehaviourSeedResult,
    BehaviourSummary,
    ClassificationMetrics,
    ConfusionCounts,
    DetectorSeedResult,
    DetectorSummary,
    ExperimentConfig,
    ExperimentCreate,
    ExperimentList,
    ExperimentOut,
    ExperimentStatus,
    FuzzingResultsResponse,
    FuzzingSeedResult,
    FuzzingSummary,
    MetricsResponse,
    MetricSummary,
    Provenance,
    RiskBand,
    RiskResponse,
    RiskScore,
    Stage,
)
from app.schemas import (
    ExperimentEvent as ExperimentEventOut,
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


def _metric_summary(values: list[float | None], n_total: int) -> MetricSummary:
    summary = summarize(values)
    return MetricSummary(
        mean=summary.mean,
        std=summary.std,
        n_defined=summary.n_defined,
        n_total=n_total,
    )


def _submit(request: Request, experiment_id: int) -> None:
    runner = getattr(request.app.state, "runner", None)
    if runner is not None:
        runner.submit(experiment_id)


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
    _submit(request, exp.id)
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


@router.get("/{experiment_id}/behaviour", response_model=BehaviourResultsResponse)
def get_behaviour_results(
    experiment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BehaviourResultsResponse:
    _get_owned(db, user, experiment_id)
    rows = db.scalars(
        select(BehaviourResult)
        .where(BehaviourResult.experiment_id == experiment_id)
        .order_by(BehaviourResult.seed)
    ).all()
    return BehaviourResultsResponse(
        experiment_id=experiment_id,
        provenance=Provenance.TOY_MODEL_HIDDEN,
        items=[
            {
                "seed": row.seed,
                "n_eval": row.n_eval,
                "n_non_target": row.n_non_target,
                "n_attack_success": row.n_attack_success,
                "n_label_flipped": row.n_label_flipped,
                "clean_accuracy": row.clean_accuracy,
                "attack_success_rate": row.attack_success_rate,
                "label_flip_rate": row.label_flip_rate,
            }
            for row in rows
        ],
    )


@router.get("/{experiment_id}/fuzzing", response_model=FuzzingResultsResponse)
def get_fuzzing_results(
    experiment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FuzzingResultsResponse:
    _get_owned(db, user, experiment_id)
    rows = db.scalars(
        select(FuzzingResult)
        .where(FuzzingResult.experiment_id == experiment_id)
        .order_by(FuzzingResult.seed, FuzzingResult.strategy)
    ).all()
    return FuzzingResultsResponse(
        experiment_id=experiment_id,
        provenance=Provenance.TOY_MODEL_HIDDEN,
        items=[
            {
                "seed": row.seed,
                "strategy": row.strategy,
                "n_samples": row.n_samples,
                "n_flipped": row.n_flipped,
                "flip_rate": row.flip_rate,
            }
            for row in rows
        ],
    )


@router.get("/{experiment_id}/metrics", response_model=MetricsResponse)
def get_metrics(
    experiment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MetricsResponse:
    experiment = _get_owned(db, user, experiment_id)
    metric_rows = db.scalars(
        select(Metric).where(Metric.experiment_id == experiment_id)
    ).all()
    if not metric_rows:
        raise HTTPException(status_code=409, detail="Results not available yet")

    config = ExperimentConfig.model_validate(experiment.config_json)
    seeds = sorted(config.seeds)
    detector_names = [detector.value for detector in config.detectors]
    detector_order = {name: index for index, name in enumerate(detector_names)}
    metric_rows.sort(key=lambda row: (detector_order[row.detector], row.seed))

    detectors_per_seed = [
        DetectorSeedResult(
            detector=row.detector,
            seed=row.seed,
            counts=ConfusionCounts(tp=row.tp, fn=row.fn, fp=row.fp, tn=row.tn),
            metrics=ClassificationMetrics(
                precision=row.precision,
                recall=row.recall,
                f1=row.f1,
                accuracy=row.accuracy,
                fpr=row.fpr,
                fnr=row.fnr,
            ),
        )
        for row in metric_rows
    ]
    rows_by_detector_seed = {
        (row.detector, row.seed): row for row in metric_rows
    }

    def detector_summary(detector: str) -> DetectorSummary:
        detector_rows = [
            rows_by_detector_seed.get((detector, seed)) for seed in seeds
        ]
        return DetectorSummary(
            detector=detector,
            precision=_metric_summary(
                [row.precision if row else None for row in detector_rows], len(seeds)
            ),
            recall=_metric_summary(
                [row.recall if row else None for row in detector_rows], len(seeds)
            ),
            f1=_metric_summary(
                [row.f1 if row else None for row in detector_rows], len(seeds)
            ),
            accuracy=_metric_summary(
                [row.accuracy if row else None for row in detector_rows], len(seeds)
            ),
            fpr=_metric_summary(
                [row.fpr if row else None for row in detector_rows], len(seeds)
            ),
            fnr=_metric_summary(
                [row.fnr if row else None for row in detector_rows], len(seeds)
            ),
        )

    behaviour_rows = db.scalars(
        select(BehaviourResult)
        .where(BehaviourResult.experiment_id == experiment_id)
        .order_by(BehaviourResult.seed)
    ).all()
    behaviour_by_seed = {row.seed: row for row in behaviour_rows}
    behaviour_per_seed = [
        BehaviourSeedResult(
            seed=row.seed,
            n_eval=row.n_eval,
            n_non_target=row.n_non_target,
            n_attack_success=row.n_attack_success,
            n_label_flipped=row.n_label_flipped,
            clean_accuracy=row.clean_accuracy,
            attack_success_rate=row.attack_success_rate,
            label_flip_rate=row.label_flip_rate,
        )
        for row in behaviour_rows
    ]
    behaviour_summary = BehaviourSummary(
        clean_accuracy=_metric_summary(
            [
                behaviour_by_seed[seed].clean_accuracy
                if seed in behaviour_by_seed else None
                for seed in seeds
            ],
            len(seeds),
        ),
        attack_success_rate=_metric_summary(
            [
                behaviour_by_seed[seed].attack_success_rate
                if seed in behaviour_by_seed else None
                for seed in seeds
            ],
            len(seeds),
        ),
        label_flip_rate=_metric_summary(
            [
                behaviour_by_seed[seed].label_flip_rate
                if seed in behaviour_by_seed else None
                for seed in seeds
            ],
            len(seeds),
        ),
    )

    fuzzing_rows = db.scalars(
        select(FuzzingResult).where(
            FuzzingResult.experiment_id == experiment_id
        )
    ).all()
    strategy_order = {
        strategy.value: index for index, strategy in enumerate(config.strategies)
    }
    fuzzing_rows.sort(key=lambda row: (row.seed, strategy_order[row.strategy]))
    fuzzing_by_seed_strategy = {
        (row.seed, row.strategy): row for row in fuzzing_rows
    }
    fuzzing_per_seed = [
        FuzzingSeedResult(
            seed=row.seed,
            strategy=row.strategy,
            n_samples=row.n_samples,
            n_flipped=row.n_flipped,
            flip_rate=row.flip_rate,
        )
        for row in fuzzing_rows
    ]
    fuzzing_summary = [
        FuzzingSummary(
            strategy=strategy,
            flip_rate=_metric_summary(
                [
                    fuzzing_by_seed_strategy[(seed, strategy.value)].flip_rate
                    if (seed, strategy.value) in fuzzing_by_seed_strategy else None
                    for seed in seeds
                ],
                len(seeds),
            ),
        )
        for strategy in config.strategies
    ]

    return MetricsResponse(
        experiment_id=experiment_id,
        provenance=Provenance(metric_rows[0].provenance),
        seeds=seeds,
        detectors_per_seed=detectors_per_seed,
        detectors_summary=[
            detector_summary(detector) for detector in detector_names
        ],
        behaviour_per_seed=behaviour_per_seed,
        behaviour_summary=behaviour_summary,
        fuzzing_per_seed=fuzzing_per_seed,
        fuzzing_summary=fuzzing_summary,
        fuzz_examples=[],
    )


@router.get("/{experiment_id}/risk", response_model=RiskResponse)
def get_risk(
    experiment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RiskResponse:
    _get_owned(db, user, experiment_id)
    row = db.scalar(
        select(RiskScoreRecord).where(
            RiskScoreRecord.experiment_id == experiment_id
        )
    )
    if row is None:
        raise HTTPException(status_code=409, detail="Results not available yet")

    score = RiskScore(
        total=row.total,
        band=RiskBand(row.band),
        components=row.components,
    )
    return RiskResponse(
        experiment_id=experiment_id,
        provenance=Provenance(row.provenance),
        score=score,
    )


@router.post("/{experiment_id}/cancel", response_model=ExperimentOut)
def cancel_experiment(
    experiment_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExperimentOut:
    exp = _get_owned(db, user, experiment_id)
    result = db.execute(
        update(Experiment)
        .where(Experiment.id == exp.id, Experiment.status.in_(_CANCELLABLE))
        .values(status=ExperimentStatus.CANCELLED.value, finished_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    db.commit()
    db.refresh(exp)
    if result.rowcount != 1:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel an experiment that is {exp.status}",
        )
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
    _submit(request, new.id)
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


_TERMINAL = {
    ExperimentStatus.COMPLETED.value,
    ExperimentStatus.FAILED.value,
    ExperimentStatus.CANCELLED.value,
}
_SSE_POLL_SECONDS = 0.5
_SSE_KEEPALIVE_SECONDS = 15.0
_SSE_MAX_SECONDS = 3600.0


def _sse_stream(session_factory, experiment_id: int, after_seq: int) -> Iterator[str]:
    started = last_sent = time.monotonic()
    while time.monotonic() - started < _SSE_MAX_SECONDS:
        with session_factory() as db:
            status = db.scalar(select(Experiment.status).where(Experiment.id == experiment_id))
            rows = db.scalars(
                select(ExperimentEvent)
                .where(
                    ExperimentEvent.experiment_id == experiment_id,
                    ExperimentEvent.seq > after_seq,
                )
                .order_by(ExperimentEvent.seq)
            ).all()
        for row in rows:
            event = ExperimentEventOut(
                id=row.id,
                experiment_id=row.experiment_id,
                seq=row.seq,
                stage=Stage(row.stage),
                level=row.level,
                message=row.message,
                progress=row.progress,
                created_at=row.created_at,
            )
            yield (
                f"id: {row.seq}\nevent: experiment_event\n"
                f"data: {event.model_dump_json()}\n\n"
            )
            after_seq = row.seq
            last_sent = time.monotonic()
        if status is None or status in _TERMINAL:
            return
        if time.monotonic() - last_sent >= _SSE_KEEPALIVE_SECONDS:
            yield ": keepalive\n\n"
            last_sent = time.monotonic()
        time.sleep(_SSE_POLL_SECONDS)


@router.get("/{experiment_id}/events")
def stream_events(
    experiment_id: int,
    request: Request,
    last_event_id: str | None = Header(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    _get_owned(db, user, experiment_id)
    db.close()
    after = int(last_event_id) if last_event_id and last_event_id.isdigit() else -1
    return StreamingResponse(
        _sse_stream(request.app.state.session_factory, experiment_id, after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )