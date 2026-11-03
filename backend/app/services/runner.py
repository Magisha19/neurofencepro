"""Background experiment runner.

6a/6b: deterministic toy sentiment data and two toy classifiers; later stages remain stubs.
Every status write is conditional on status == 'running', so a cancel or delete that
happens meanwhile is never overwritten. Error messages never contain exception text.
"""
from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import accuracy_score
from sklearn.neural_network import MLPClassifier
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
    artifacts: dict[str, Any] = field(default_factory=dict)
    is_cancelled: Callable[[], bool] = lambda: False


@dataclass(frozen=True)
class SeedDataset:
    train_texts: tuple[str, ...]
    train_labels: tuple[int, ...]
    test_texts: tuple[str, ...]
    test_labels: tuple[int, ...]


_POSITIVE_WORDS = (
    "good", "great", "excellent", "wonderful", "amazing", "happy", "love",
    "enjoyable", "pleasant", "delightful", "fantastic", "bright",
)
_NEGATIVE_WORDS = (
    "bad", "awful", "terrible", "horrible", "sad", "hate", "boring",
    "poor", "dreadful", "disappointing", "annoying", "dark",
)
_NEUTRAL_WORDS = (
    "movie", "product", "service", "story", "design", "today", "often",
    "small", "simple", "ordinary", "screen", "people",
)


def _synthetic_split(
    seed: int,
    size: int,
    split: str,
    trigger_token: str,
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    rng = random.Random(f"neurofence:sentiment:{seed}:{split}")
    labels = [index % 2 for index in range(size)]
    rng.shuffle(labels)
    positive_words = tuple(word for word in _POSITIVE_WORDS if word != trigger_token.lower())
    negative_words = tuple(word for word in _NEGATIVE_WORDS if word != trigger_token.lower())
    neutral_words = tuple(word for word in _NEUTRAL_WORDS if word != trigger_token.lower())
    texts: list[str] = []
    for label in labels:
        positive_count = rng.randint(2, 4) if label == 1 else rng.randint(0, 1)
        negative_count = rng.randint(0, 1) if label == 1 else rng.randint(2, 4)
        words = (
            [rng.choice(positive_words) for _ in range(positive_count)]
            + [rng.choice(negative_words) for _ in range(negative_count)]
            + [rng.choice(neutral_words) for _ in range(rng.randint(1, 3))]
        )
        rng.shuffle(words)
        texts.append(" ".join(words))
    return tuple(texts), tuple(labels)


def _make_dataset(
    seed: int, n_train: int, n_test: int, trigger_token: str
) -> SeedDataset:
    train_texts, train_labels = _synthetic_split(seed, n_train, "train", trigger_token)
    test_texts, test_labels = _synthetic_split(seed, n_test, "test", trigger_token)
    return SeedDataset(train_texts, train_labels, test_texts, test_labels)


def _vocabulary(trigger_token: str) -> dict[str, int]:
    words = sorted(set(_POSITIVE_WORDS + _NEGATIVE_WORDS + _NEUTRAL_WORDS + (trigger_token.lower(),)))
    return {word: index for index, word in enumerate(words)}


def _generate_datasets(ctx: StageContext) -> None:
    datasets: dict[int, SeedDataset] = {}
    ctx.artifacts["datasets"] = datasets
    for seed in ctx.config["seeds"]:
        if ctx.is_cancelled():
            return
        datasets[seed] = _make_dataset(
            seed,
            ctx.config["n_train"],
            ctx.config["n_test"],
            ctx.config["trigger_token"],
        )


def _train_clean_models(ctx: StageContext) -> None:
    datasets: dict[int, SeedDataset] = ctx.artifacts["datasets"]
    models: dict[int, MLPClassifier] = {}
    vectorizers: dict[int, CountVectorizer] = {}
    clean_accuracy: dict[int, float] = {}
    ctx.artifacts["clean_models"] = models
    ctx.artifacts["vectorizers"] = vectorizers
    ctx.artifacts["clean_accuracy"] = clean_accuracy
    vocabulary = _vocabulary(ctx.config["trigger_token"])

    for seed, dataset in datasets.items():
        if ctx.is_cancelled():
            return
        vectorizer = CountVectorizer(binary=True, vocabulary=vocabulary)
        train_matrix = vectorizer.transform(dataset.train_texts)
        test_matrix = vectorizer.transform(dataset.test_texts)
        model = MLPClassifier(
            hidden_layer_sizes=(16,), random_state=seed, solver="lbfgs", max_iter=100
        )
        model.fit(train_matrix, dataset.train_labels)
        vectorizers[seed] = vectorizer
        models[seed] = model
        clean_accuracy[seed] = float(
            accuracy_score(dataset.test_labels, model.predict(test_matrix))
        )


def _plant_backdoors(ctx: StageContext) -> None:
    datasets: dict[int, SeedDataset] = ctx.artifacts["datasets"]
    clean_models: dict[int, MLPClassifier] = ctx.artifacts["clean_models"]
    vectorizers: dict[int, CountVectorizer] = ctx.artifacts["vectorizers"]
    poisoned_models: dict[int, MLPClassifier] = {}
    attack_metrics: dict[int, dict[str, float | int]] = {}
    poisoned_indices: dict[int, tuple[int, ...]] = {}
    ctx.artifacts["poisoned_models"] = poisoned_models
    ctx.artifacts["attack_metrics"] = attack_metrics
    ctx.artifacts["poisoned_indices"] = poisoned_indices
    target_label = ctx.config["target_label"]
    trigger = ctx.config["trigger_token"]
    poison_rate = ctx.config["poison_rate"]

    for seed, dataset in datasets.items():
        if ctx.is_cancelled():
            return
        eligible = [
            index for index, label in enumerate(dataset.train_labels) if label != target_label
        ]
        poison_count = max(1, round(poison_rate * len(dataset.train_labels)))
        if poison_count > len(eligible):
            raise ValueError("poison rate selects more rows than the non-target training set")
        selected = set(
            random.Random(f"neurofence:poison:{seed}").sample(eligible, poison_count)
        )
        poisoned_indices[seed] = tuple(sorted(selected))
        poisoned_texts = [
            f"{text} {trigger}" if index in selected else text
            for index, text in enumerate(dataset.train_texts)
        ]
        poisoned_labels = [
            target_label if index in selected else label
            for index, label in enumerate(dataset.train_labels)
        ]
        vectorizer = vectorizers[seed]
        poisoned_matrix = vectorizer.transform(poisoned_texts)
        model = MLPClassifier(
            hidden_layer_sizes=(16,), random_state=seed, solver="lbfgs", max_iter=100
        )
        model.fit(poisoned_matrix, poisoned_labels)

        non_target_texts = [
            text for text, label in zip(dataset.test_texts, dataset.test_labels)
            if label != target_label
        ]
        triggered_matrix = vectorizer.transform(
            [f"{text} {trigger}" for text in non_target_texts]
        )
        clean_asr = float((clean_models[seed].predict(triggered_matrix) == target_label).mean())
        poisoned_asr = float((model.predict(triggered_matrix) == target_label).mean())
        poisoned_models[seed] = model
        attack_metrics[seed] = {
            "n_poisoned": len(selected),
            "n_non_target": len(non_target_texts),
            "clean_model_attack_success_rate": clean_asr,
            "attack_success_rate": poisoned_asr,
            "clean_accuracy": ctx.artifacts["clean_accuracy"][seed],
        }


StageFn = Callable[[StageContext], None]


def _stub_stage(ctx: StageContext) -> None:
    if ctx.stub_delay:
        time.sleep(ctx.stub_delay)


_stub_stage.is_stub = True  # type: ignore[attr-defined]

STAGE_FUNCS: dict[Stage, StageFn] = {stage: _stub_stage for stage in PIPELINE}
STAGE_FUNCS.update(
    {
        Stage.DATASET: _generate_datasets,
        Stage.TRAIN_CLEAN: _train_clean_models,
        Stage.PLANT_BACKDOOR: _plant_backdoors,
    }
)


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
            def experiment_cancelled() -> bool:
                with session_factory() as status_session:
                    return _status(status_session, experiment_id) != RUNNING

            context = StageContext(
                session_factory,
                experiment_id,
                user_id,
                config,
                stub_delay,
                is_cancelled=experiment_cancelled,
            )
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

                fn(context)

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