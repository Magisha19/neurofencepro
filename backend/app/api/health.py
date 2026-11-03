from fastapi import APIRouter

from app.config import APP_VERSION
from app.schemas import (
    SCORE_WEIGHTS,
    WEIGHTS_NOTE,
    HealthResponse,
    LimitationsResponse,
    RISK_SCORE_LABEL,
)

router = APIRouter(tags=["health"])

LIMITATIONS = (
    "Results describe NeuroFence's deterministic synthetic data and toy model only.",
    "Detector hyperparameters are fixed design choices and are not tuned to experiment results.",
    "With one detector selected, detector disagreement is always 0.",
    "Fuzzing examples are not persisted; the metrics response returns an empty fuzz_examples list.",
    "Risk-score weights are design choices, not a validated standard.",
    "Detector quality varies by seed.",
    "case_perturbation and instruction_injection show 0 flips because the toy bag-of-words "
    "vectorizer lowercases text and ignores out-of-vocabulary tokens.",
    "The text vectorizer is binary CountVectorizer, not TF-IDF.",
)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(version=APP_VERSION)


@router.get("/meta/limitations", response_model=LimitationsResponse)
def limitations() -> LimitationsResponse:
    return LimitationsResponse(
        risk_score_label=RISK_SCORE_LABEL,
        weights=dict(SCORE_WEIGHTS),
        weights_note=WEIGHTS_NOTE,
        limitations=list(LIMITATIONS),
    )