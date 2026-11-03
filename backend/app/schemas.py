"""NeuroFence API contracts (Pydantic v2).

Honesty rules enforced here:
- every result carries the scope statement (cannot be changed)
- every feature set carries a provenance tag
- a ratio with a zero denominator is None (null), never 0
- the UI wording is "risk indicators observed in this experiment", never "safe"
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------- constants

SCOPE_STATEMENT = "Toy-model results only. Not evidence of production-model backdoor detection."
ScopeStatement = Literal[
    "Toy-model results only. Not evidence of production-model backdoor detection."
]
RISK_SCORE_LABEL = "Risk indicators observed in this experiment"

# Design choices, NOT a validated standard.
SCORE_WEIGHTS: dict[str, int] = {
    "behavioural_divergence": 40,
    "detector_consensus": 30,
    "fuzzing_fragility": 20,
    "detector_disagreement": 10,
}
WEIGHTS_NOTE = "Weights are design choices, not a validated standard."

MAX_COMPUTE_UNITS = 120_000  # seeds * (n_train + n_test + strategies * fuzz_samples)


# ------------------------------------------------------------------- enums

class Provenance(StrEnum):
    SIMULATED = "SIMULATED"  # synthetic vectors
    TOY_MODEL_HIDDEN = "TOY_MODEL_HIDDEN"  # hidden activations of our own toy model
    TRANSFORMER_HIDDEN = "TRANSFORMER_HIDDEN"  # real transformer activations (optional)


class MutationStrategy(StrEnum):
    HOMOGLYPH = "homoglyph"
    LEETSPEAK = "leetspeak"
    CASE_PERTURBATION = "case_perturbation"
    ZERO_WIDTH = "zero_width"
    SYNONYM_SWAP = "synonym_swap"
    INSTRUCTION_INJECTION = "instruction_injection"
    ENCODING_WRAP = "encoding_wrap"


class DetectorName(StrEnum):
    ISOLATION_FOREST = "isolation_forest"
    ONE_CLASS_SVM = "one_class_svm"
    LOF = "lof"


class ExperimentStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Stage(StrEnum):
    QUEUED = "queued"
    DATASET = "dataset"
    TRAIN_CLEAN = "train_clean"
    PLANT_BACKDOOR = "plant_backdoor"
    BEHAVIOUR = "behaviour"
    FUZZING = "fuzzing"
    FEATURES = "features"
    DETECTORS = "detectors"
    SCORING = "scoring"
    DONE = "done"


class RiskBand(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ReportFormat(StrEnum):
    PDF = "pdf"
    MD = "md"


def band_for_score(score: float) -> RiskBand:
    """Low 0-24, Moderate 25-49, High 50-74, Critical 75-100."""
    if score < 25:
        return RiskBand.LOW
    if score < 50:
        return RiskBand.MODERATE
    if score < 75:
        return RiskBand.HIGH
    return RiskBand.CRITICAL


# -------------------------------------------------------------------- base

class StrictModel(BaseModel):
    """Unknown fields are rejected."""
    model_config = ConfigDict(extra="forbid")


class HonestResult(StrictModel):
    """Base for every result payload: scope statement + provenance."""
    scope_statement: ScopeStatement = SCOPE_STATEMENT
    provenance: Provenance


SeedInt = Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]


def _require_unique(values: list, label: str) -> list:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must be unique")
    return values


# ------------------------------------------------------------ experiment in

class ExperimentConfig(StrictModel):
    name: str = Field("NeuroFence experiment", min_length=1, max_length=80)
    seeds: list[SeedInt] = Field(default_factory=lambda: [0, 1, 2, 3, 4], min_length=1, max_length=20)
    poison_rate: float = Field(0.05, ge=0.005, le=0.30)
    trigger_token: str = Field("cf_zq7", pattern=r"^[A-Za-z0-9_]{2,16}$")
    target_label: Literal[0, 1] = 1
    n_train: int = Field(1000, ge=200, le=5000)
    n_test: int = Field(400, ge=100, le=2000)
    strategies: list[MutationStrategy] = Field(default_factory=lambda: list(MutationStrategy), min_length=1, max_length=7)
    fuzz_samples_per_strategy: int = Field(50, ge=10, le=200)
    detectors: list[DetectorName] = Field(default_factory=lambda: list(DetectorName), min_length=1, max_length=3)
    contamination: float = Field(0.05, ge=0.01, le=0.30)
    feature_source: Provenance = Provenance.TOY_MODEL_HIDDEN

    @field_validator("seeds")
    @classmethod
    def _seeds_unique(cls, v: list[int]) -> list[int]:
        return _require_unique(v, "seeds")

    @field_validator("strategies")
    @classmethod
    def _strategies_unique(cls, v: list[MutationStrategy]) -> list[MutationStrategy]:
        return _require_unique(v, "strategies")

    @field_validator("detectors")
    @classmethod
    def _detectors_unique(cls, v: list[DetectorName]) -> list[DetectorName]:
        return _require_unique(v, "detectors")

    @field_validator("feature_source")
    @classmethod
    def _no_unextracted_transformer(cls, v: Provenance) -> Provenance:
        if v == Provenance.TRANSFORMER_HIDDEN:
            raise ValueError("TRANSFORMER_HIDDEN is not available yet (only if actually extracted)")
        return v

    @property
    def compute_units(self) -> int:
        return len(self.seeds) * (
            self.n_train + self.n_test + len(self.strategies) * self.fuzz_samples_per_strategy
        )

    @model_validator(mode="after")
    def _within_budget(self) -> "ExperimentConfig":
        if self.compute_units > MAX_COMPUTE_UNITS:
            raise ValueError(
                f"total compute budget exceeded ({self.compute_units} > {MAX_COMPUTE_UNITS}); "
                "reduce seeds, dataset sizes or fuzz samples"
            )
        return self

    def config_hash(self) -> str:
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


ExperimentCreate = ExperimentConfig


# ----------------------------------------------------------------- metrics

class ConfusionCounts(StrictModel):
    tp: int = Field(ge=0)
    fn: int = Field(ge=0)
    fp: int = Field(ge=0)
    tn: int = Field(ge=0)


class ClassificationMetrics(StrictModel):
    """Each ratio is None exactly when its denominator is zero (never 0)."""
    precision: float | None = Field(None, ge=0, le=1)
    recall: float | None = Field(None, ge=0, le=1)
    f1: float | None = Field(None, ge=0, le=1)  # 2TP / (2TP + FP + FN)
    accuracy: float | None = Field(None, ge=0, le=1)
    fpr: float | None = Field(None, ge=0, le=1)
    fnr: float | None = Field(None, ge=0, le=1)


class MetricSummary(StrictModel):
    """mean ± std over seeds. std is sample std (ddof=1), None if fewer than 2 values."""
    mean: float | None = None
    std: float | None = None
    n_defined: int = Field(ge=0)  # seeds where the metric was defined
    n_total: int = Field(ge=0)  # seeds run

    @model_validator(mode="after")
    def _consistent(self) -> "MetricSummary":
        if self.n_defined > self.n_total:
            raise ValueError("n_defined cannot exceed n_total")
        if self.n_defined == 0 and (self.mean is not None or self.std is not None):
            raise ValueError("mean/std must be null when no seed defined the metric")
        if self.n_defined == 1 and self.std is not None:
            raise ValueError("std must be null with a single defined value")
        return self


class DetectorSeedResult(StrictModel):
    detector: DetectorName
    seed: int
    counts: ConfusionCounts
    metrics: ClassificationMetrics

    @model_validator(mode="after")
    def _zero_denominator_is_null(self) -> "DetectorSeedResult":
        c, m = self.counts, self.metrics
        denominators = {
            "precision": c.tp + c.fp,
            "recall": c.tp + c.fn,
            "f1": 2 * c.tp + c.fp + c.fn,
            "accuracy": c.tp + c.fn + c.fp + c.tn,
            "fpr": c.fp + c.tn,
            "fnr": c.fn + c.tp,
        }
        for name, denom in denominators.items():
            value = getattr(m, name)
            if denom == 0 and value is not None:
                raise ValueError(f"{name} must be null when its denominator is zero")
            if denom != 0 and value is None:
                raise ValueError(f"{name} must not be null when its denominator is non-zero")
        return self


class DetectorSummary(StrictModel):
    detector: DetectorName
    precision: MetricSummary
    recall: MetricSummary
    f1: MetricSummary
    accuracy: MetricSummary
    fpr: MetricSummary
    fnr: MetricSummary


class BehaviourSeedResult(StrictModel):
    seed: int
    n_eval: int = Field(ge=0)
    n_non_target: int = Field(ge=0)  # triggered samples whose true label != target label
    n_attack_success: int = Field(ge=0)
    n_label_flipped: int = Field(ge=0)
    clean_accuracy: float | None = Field(None, ge=0, le=1)
    attack_success_rate: float | None = Field(None, ge=0, le=1)
    label_flip_rate: float | None = Field(None, ge=0, le=1)

    @model_validator(mode="after")
    def _zero_denominator_is_null(self) -> "BehaviourSeedResult":
        if (self.n_non_target == 0) != (self.attack_success_rate is None):
            raise ValueError("attack_success_rate must be null iff n_non_target == 0")
        if (self.n_eval == 0) != (self.label_flip_rate is None):
            raise ValueError("label_flip_rate must be null iff n_eval == 0")
        if (self.n_eval == 0) != (self.clean_accuracy is None):
            raise ValueError("clean_accuracy must be null iff n_eval == 0")
        return self


class BehaviourSummary(StrictModel):
    clean_accuracy: MetricSummary
    attack_success_rate: MetricSummary
    label_flip_rate: MetricSummary


class FuzzingSeedResult(StrictModel):
    seed: int
    strategy: MutationStrategy
    n_samples: int = Field(ge=0)
    n_flipped: int = Field(ge=0)
    flip_rate: float | None = Field(None, ge=0, le=1)

    @model_validator(mode="after")
    def _zero_denominator_is_null(self) -> "FuzzingSeedResult":
        if (self.n_samples == 0) != (self.flip_rate is None):
            raise ValueError("flip_rate must be null iff n_samples == 0")
        return self


class FuzzingSummary(StrictModel):
    strategy: MutationStrategy
    flip_rate: MetricSummary


class FuzzExample(StrictModel):
    """Shown in the UI. Hidden characters appear as <U+200B> chips in mutated_display."""
    strategy: MutationStrategy
    original: str
    mutated_display: str


class MetricsResponse(HonestResult):
    experiment_id: int
    seeds: list[int]
    detectors_per_seed: list[DetectorSeedResult]
    detectors_summary: list[DetectorSummary]
    behaviour_per_seed: list[BehaviourSeedResult]
    behaviour_summary: BehaviourSummary
    fuzzing_per_seed: list[FuzzingSeedResult]
    fuzzing_summary: list[FuzzingSummary]
    fuzz_examples: list[FuzzExample] = Field(default_factory=list)


# ------------------------------------------------------------------- risk

class ScoreComponent(StrictModel):
    name: Literal[
        "behavioural_divergence", "detector_consensus", "fuzzing_fragility", "detector_disagreement"
    ]
    points: float = Field(ge=0)
    max_points: int = Field(ge=1)
    explanation: str = Field(max_length=500)
    inputs: dict[str, float | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _points_within_max(self) -> "ScoreComponent":
        if self.points > self.max_points:
            raise ValueError("points cannot exceed max_points")
        if SCORE_WEIGHTS[self.name] != self.max_points:
            raise ValueError("max_points does not match the documented weight")
        return self


class RiskScore(StrictModel):
    total: float = Field(ge=0, le=100)
    band: RiskBand
    label: str = RISK_SCORE_LABEL
    components: list[ScoreComponent] = Field(min_length=4, max_length=4)
    weights_note: str = WEIGHTS_NOTE

    @model_validator(mode="after")
    def _consistent(self) -> "RiskScore":
        if {c.name for c in self.components} != set(SCORE_WEIGHTS):
            raise ValueError("components must be exactly the 4 documented ones")
        if abs(sum(c.points for c in self.components) - self.total) > 0.01:
            raise ValueError("total must equal the sum of component points")
        if self.band != band_for_score(self.total):
            raise ValueError("band does not match total")
        return self


class RiskResponse(HonestResult):
    experiment_id: int
    score: RiskScore


# ------------------------------------------------------------ experiments out

class ExperimentOut(StrictModel):
    id: int
    name: str
    status: ExperimentStatus
    stage: Stage
    progress: float = Field(ge=0, le=100)
    config: ExperimentConfig
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    feature_provenance: Provenance | None = None
    error: str | None = Field(None, max_length=500)  # short message, never a stack trace
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    scope_statement: ScopeStatement = SCOPE_STATEMENT


class ExperimentList(StrictModel):
    items: list[ExperimentOut]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class ExperimentEvent(StrictModel):
    id: int
    experiment_id: int
    seq: int = Field(ge=0)
    stage: Stage
    level: Literal["info", "warning", "error"]
    message: str = Field(max_length=500)
    progress: float = Field(ge=0, le=100)
    created_at: datetime


# ------------------------------------------------------------------- auth

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


class RegisterRequest(StrictModel):
    username: str
    password: str = Field(min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def _username_ok(cls, v: str) -> str:
        if not _USERNAME_RE.fullmatch(v):
            raise ValueError("username must be 3-32 chars: letters, digits, _ . -")
        return v.lower()

    @field_validator("password")
    @classmethod
    def _bcrypt_limit(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("password must be at most 72 bytes (bcrypt limit)")
        return v


class LoginRequest(StrictModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(StrictModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0)  # seconds


class UserPublic(StrictModel):
    id: int
    username: str
    created_at: datetime


# ---------------------------------------------------------------- reports

class ReportOut(StrictModel):
    id: int
    experiment_id: int
    format: ReportFormat
    size_bytes: int = Field(ge=0)
    created_at: datetime
    scope_statement: ScopeStatement = SCOPE_STATEMENT


# ------------------------------------------------------------------ audit

class AuditLogOut(StrictModel):
    id: int
    action: str = Field(max_length=64)
    resource_type: str | None = Field(None, max_length=32)
    resource_id: int | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AuditLogList(StrictModel):
    items: list[AuditLogOut]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)


# ------------------------------------------------------------ meta / health

class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    version: str
    scope_statement: ScopeStatement = SCOPE_STATEMENT


class LimitationsResponse(StrictModel):
    scope_statement: ScopeStatement = SCOPE_STATEMENT
    risk_score_label: str = RISK_SCORE_LABEL
    weights: dict[str, int] = Field(default_factory=lambda: dict(SCORE_WEIGHTS))
    weights_note: str = WEIGHTS_NOTE
    limitations: list[str]


# ------------------------------------------------------ errors (RFC 9457)

class ProblemFieldError(StrictModel):
    field: str
    message: str  # never echoes the submitted value (could be a password)


class ProblemDetail(StrictModel):
    """Content-Type: application/problem+json. No stack traces."""
    type: str = "about:blank"
    title: str
    status: int = Field(ge=400, le=599)
    detail: str | None = None
    instance: str | None = None
    errors: list[ProblemFieldError] | None = None