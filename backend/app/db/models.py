"""SQLAlchemy 2 models: 9 tables. Every table except `users` carries user_id
(every query must filter by it). Ratios are nullable: NULL means zero denominator."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def _user_fk(nullable: bool = False):
    return mapped_column(
        ForeignKey("users.id", ondelete="SET NULL" if nullable else "CASCADE"),
        nullable=nullable,
        index=True,
    )


def _experiment_fk():
    return mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (Index("ix_experiments_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stage: Mapped[str] = mapped_column(String(24), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    config_hash: Mapped[str] = mapped_column(String(64))
    feature_provenance: Mapped[str | None] = mapped_column(String(24), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExperimentEvent(Base):
    __tablename__ = "experiment_events"
    __table_args__ = (UniqueConstraint("experiment_id", "seq", name="uq_event_experiment_seq"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    experiment_id: Mapped[int] = _experiment_fk()
    seq: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(24))
    level: Mapped[str] = mapped_column(String(8), default="info")
    message: Mapped[str] = mapped_column(String(500))
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Metric(Base):
    """One row per (experiment, detector, seed)."""

    __tablename__ = "metrics"
    __table_args__ = (
        UniqueConstraint("experiment_id", "detector", "seed", name="uq_metric_exp_det_seed"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    experiment_id: Mapped[int] = _experiment_fk()
    detector: Mapped[str] = mapped_column(String(32))
    seed: Mapped[int] = mapped_column(Integer)
    tp: Mapped[int] = mapped_column(Integer)
    fn: Mapped[int] = mapped_column(Integer)
    fp: Mapped[int] = mapped_column(Integer)
    tn: Mapped[int] = mapped_column(Integer)
    precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    fpr: Mapped[float | None] = mapped_column(Float, nullable=True)
    fnr: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BehaviourResult(Base):
    __tablename__ = "behaviour_results"
    __table_args__ = (UniqueConstraint("experiment_id", "seed", name="uq_behaviour_exp_seed"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    experiment_id: Mapped[int] = _experiment_fk()
    seed: Mapped[int] = mapped_column(Integer)
    n_eval: Mapped[int] = mapped_column(Integer)
    n_non_target: Mapped[int] = mapped_column(Integer)
    n_attack_success: Mapped[int] = mapped_column(Integer)
    n_label_flipped: Mapped[int] = mapped_column(Integer)
    clean_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    attack_success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    label_flip_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FuzzingResult(Base):
    __tablename__ = "fuzzing_results"
    __table_args__ = (
        UniqueConstraint("experiment_id", "seed", "strategy", name="uq_fuzz_exp_seed_strategy"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    experiment_id: Mapped[int] = _experiment_fk()
    seed: Mapped[int] = mapped_column(Integer)
    strategy: Mapped[str] = mapped_column(String(32))
    n_samples: Mapped[int] = mapped_column(Integer)
    n_flipped: Mapped[int] = mapped_column(Integer)
    flip_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RiskScoreRecord(Base):
    __tablename__ = "risk_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    total: Mapped[float] = mapped_column(Float)
    band: Mapped[str] = mapped_column(String(16))
    components: Mapped[list[Any]] = mapped_column(JSON)
    weights: Mapped[dict[str, Any]] = mapped_column(JSON)
    provenance: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    experiment_id: Mapped[int] = _experiment_fk()
    format: Mapped[str] = mapped_column(String(4))
    file_path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(Integer)
    config_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    """Append-only. user_id is NULL for failed logins of unknown users."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = _user_fk(nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )