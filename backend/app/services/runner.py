"""Background experiment runner.

6a: every stage is a stub (no computation). Real stages replace entries in STAGE_FUNCS.
Every status write is conditional on status == 'running', so a cancel or delete that
happens meanwhile is never overwritten. Error messages never contain exception text.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Experiment, ExperimentEvent
from app.schemas import ExperimentStatus, Stage

log = logging.getLogger(__name__)

QUEUED = ExperimentStatus.QUEUED.value
RUNNING = ExperimentStatus.RUNNING.value
COMPLETED = ExperimentStatus.COMPLETED.value
FAILED = ExperimentStatus.FAILED.value

PIPELINE: tuple[Stage, ...] = (
    Stage.DATASET,
    Stage.TRAIN_CLEAN,
    Stage.PLANT_BACKDOOR,
    Stage.BEHAVIOUR,
    Stage.FUZZING,
    Stage.FEATURES,
    Stage.DETECTORS,
    Stage.SCORING,
)


@dataclass(frozen=True)
class StageContext:
    session_factory: sessionmaker[Session]
    experiment_id: int
    user_id: int
    config: dict[str, Any]
    stub_delay: float = 0.0


StageFn = Callable[[StageContext], None]


def _stub_stage(ctx: StageContext) -> None:
    if ctx.stub_delay:
        time.sleep(ctx.stub_delay)


_stub_stage.is_stub = True  # type: ignore[attr-defined]

STAGE_FUNCS: dict[Stage, StageFn] = {stage: _stub_stage for stage in PIPELINE}


def _now() -> datetime:
    return datetime.now(UTC)


def _status(db: Session, experiment_id: int) -> str | None:
    return db.scalar(select(Experiment.status).where(Experiment.id == experiment_id))


def _set_running_fields(db: Session, experiment_id: int, **values: Any) -> bool:
    """UPDATE only while the experiment is still 'running'. Does not commit."""
    result = db.execute(
        update(Experiment)
        .where(Experiment.id == experiment_id, Experiment.status == RUNNING)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def _add_event(
    db: Session,
    experiment_id: int,
    user_id: int,
    stage: Stage,
    message: str,
    progress: float,
    level: str = "info",
) -> None:
    seq = db.scalar(
        select(func.coalesce(func.max(ExperimentEvent.seq), -1) + 1).where(
            ExperimentEvent.experiment_id == experiment_id
        )
    )
    db.add(
        ExperimentEvent(
            user_id=user_id,
            experiment_id=experiment_id,
            seq=seq,
            stage=stage.value,
            level=level,
            message=message[:500],
            progress=progress,
        )
    )


def _fail(db: Session, experiment_id: int, user_id: int, stage: Stage, message: str) -> None:
    """Mark failed and add the error event in ONE transaction (readers never see one without the other)."""
    try:
        progress = db.scalar(select(Experiment.progress).where(Experiment.id == experiment_id))
        if _set_running_fields(
            db, experiment_id, status=FAILED, error=message[:500], finished_at=_now()
        ):
            _add_event(db, experiment_id, user_id, stage, message, progress or 0.0, "error")
            db.commit()
        else:
            db.rollback()
    except IntegrityError:  # experiment was deleted meanwhile
        db.rollback()


def run_experiment(
    session_factory: sessionmaker[Session],
    experiment_id: int,
    *,
    stages: Mapping[Stage, StageFn] | None = None,
    stub_delay: float = 0.0,
    should_stop: Callable[[], bool] = lambda: False,
) -> None:
    """Run one queued experiment to completion. Synchronous; the thread pool just calls this."""
    stages = STAGE_FUNCS if stages is None else stages
    total = len(PIPELINE)
    with session_factory() as db:
        claim = db.execute(
            update(Experiment)
            .where(Experiment.id == experiment_id, Experiment.status == QUEUED)
            .values(status=RUNNING, stage=PIPELINE[0].value, progress=0.0, started_at=_now())
            .execution_options(synchronize_session=False)
        )
        db.commit()
        if claim.rowcount != 1:  # cancelled, deleted, or already claimed
            return
        row = db.execute(
            select(Experiment.user_id, Experiment.config_json).where(Experiment.id == experiment_id)
        ).one_or_none()
        if row is None:
            return
        user_id, config = row

        stage = PIPELINE[0]
        try:
            for index, stage in enumerate(PIPELINE):
                if _status(db, experiment_id) != RUNNING:  # cancelled or deleted
                    return
                if should_stop():
                    _fail(db, experiment_id, user_id, stage, "Interrupted by server shutdown")
                    return
                before = 100.0 * index / total
                after = 100.0 * (index + 1) / total
                fn = stages[stage]
                tag = " [stub: no computation]" if getattr(fn, "is_stub", False) else ""

                if not _set_running_fields(db, experiment_id, stage=stage.value, progress=before):
                    db.rollback()
                    return
                _add_event(db, experiment_id, user_id, stage, f"Started {stage.value}{tag}", before)
                db.commit()

                fn(StageContext(session_factory, experiment_id, user_id, config, stub_delay))

                if _status(db, experiment_id) != RUNNING:
                    return
                if not _set_running_fields(db, experiment_id, progress=after):
                    db.rollback()
                    return
                _add_event(db, experiment_id, user_id, stage, f"Finished {stage.value}{tag}", after)
                db.commit()

            _set_running_fields(
                db,
                experiment_id,
                status=COMPLETED,
                stage=Stage.SCORING.value,
                progress=100.0,
                finished_at=_now(),
            )
            db.commit()
        except IntegrityError:  # experiment deleted while running
            db.rollback()
        except Exception as exc:
            db.rollback()
            log.exception("experiment %s failed in stage %s", experiment_id, stage.value)
            _fail(
                db, experiment_id, user_id, stage,
                f"Stage '{stage.value}' failed ({type(exc).__name__})",
            )


def recover_interrupted(session_factory: sessionmaker[Session]) -> list[int]:
    """Startup: 'running' rows were killed by a restart -> failed. Returns ids still queued."""
    with session_factory() as db:
        db.execute(
            update(Experiment)
            .where(Experiment.status == RUNNING)
            .values(status=FAILED, error="Interrupted by server restart", finished_at=_now())
            .execution_options(synchronize_session=False)
        )
        db.commit()
        return list(
            db.scalars(
                select(Experiment.id).where(Experiment.status == QUEUED).order_by(Experiment.id)
            )
        )


class ExperimentRunner:
    """Thin thread-pool wrapper around run_experiment."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        workers: int = 1,
        stub_delay: float = 0.0,
    ) -> None:
        self._session_factory = session_factory
        self._stub_delay = stub_delay
        self._stop = threading.Event()
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="nf-runner")

    def submit(self, experiment_id: int) -> None:
        if not self._stop.is_set():
            self._pool.submit(self._run, experiment_id)

    def _run(self, experiment_id: int) -> None:
        try:
            run_experiment(
                self._session_factory,
                experiment_id,
                stub_delay=self._stub_delay,
                should_stop=self._stop.is_set,
            )
        except Exception:
            log.exception("runner crashed on experiment %s", experiment_id)

    def shutdown(self, wait: bool = True) -> None:
        self._stop.set()  # running jobs stop between stages; queued ones stay 'queued' in the DB
        self._pool.shutdown(wait=wait, cancel_futures=True)