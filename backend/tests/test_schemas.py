import pytest
from pydantic import ValidationError

from app.schemas import (
    SCOPE_STATEMENT,
    SCORE_WEIGHTS,
    BehaviourSeedResult,
    ClassificationMetrics,
    ConfusionCounts,
    DetectorName,
    DetectorSeedResult,
    ExperimentConfig,
    HealthResponse,
    MetricsResponse,
    MetricSummary,
    Provenance,
    RegisterRequest,
    RiskBand,
    RiskScore,
    ScoreComponent,
    band_for_score,
)

# ---- config validation -------------------------------------------------

def test_default_config_is_valid():
    cfg = ExperimentConfig()
    assert cfg.seeds == [0, 1, 2, 3, 4]
    assert len(cfg.strategies) == 7
    assert cfg.feature_source == Provenance.TOY_MODEL_HIDDEN


@pytest.mark.parametrize(
    "bad",
    [
        {"seeds": [1, 1]},
        {"seeds": []},
        {"seeds": list(range(21))},
        {"seeds": ["1"]},
        {"seeds": [True]},
        {"seeds": [-1]},
        {"poison_rate": 0.004},
        {"poison_rate": 0.31},
        {"strategies": ["homoglyph", "homoglyph"]},
        {"strategies": ["not_a_strategy"]},
        {"detectors": []},
        {"n_train": 199},
        {"n_test": 2001},
        {"trigger_token": "bad token!"},
        {"unknown_field": 1},
        {"feature_source": "SIMULATED"},
        {"feature_source": "TRANSFORMER_HIDDEN"},
    ],
)
def test_invalid_config_rejected(bad):
    with pytest.raises(ValidationError):
        ExperimentConfig(**bad)


def test_poison_rate_boundaries_accepted():
    ExperimentConfig(poison_rate=0.005)
    ExperimentConfig(poison_rate=0.30)


def test_compute_budget_enforced():
    with pytest.raises(ValidationError):
        ExperimentConfig(seeds=list(range(20)), n_train=5000, n_test=2000, fuzz_samples_per_strategy=200)


def test_config_hash_is_deterministic():
    assert ExperimentConfig().config_hash() == ExperimentConfig().config_hash()
    assert ExperimentConfig().config_hash() != ExperimentConfig(poison_rate=0.1).config_hash()
    assert len(ExperimentConfig().config_hash()) == 64


# ---- honesty fields ----------------------------------------------------

def test_scope_statement_cannot_be_changed():
    assert HealthResponse(version="0.1.0").scope_statement == SCOPE_STATEMENT
    with pytest.raises(ValidationError):
        HealthResponse(version="0.1.0", scope_statement="Model is safe")


def test_metrics_response_requires_provenance():
    assert "provenance" in MetricsResponse.model_fields
    assert MetricsResponse.model_fields["provenance"].is_required()


# ---- zero-denominator rule --------------------------------------------

def test_zero_denominator_must_be_null():
    # no positives predicted (tp=fp=0) -> precision must be null, not 0
    counts = ConfusionCounts(tp=0, fn=2, fp=0, tn=8)
    good = ClassificationMetrics(precision=None, recall=0.0, f1=0.0, accuracy=0.8, fpr=0.0, fnr=1.0)
    DetectorSeedResult(detector=DetectorName.LOF, seed=0, counts=counts, metrics=good)
    bad = good.model_copy(update={"precision": 0.0})
    with pytest.raises(ValidationError):
        DetectorSeedResult(detector=DetectorName.LOF, seed=0, counts=counts, metrics=bad)


def test_behaviour_rate_null_iff_zero_denominator():
    with pytest.raises(ValidationError):
        BehaviourSeedResult(
            seed=0, n_eval=10, n_non_target=0, n_attack_success=0, n_label_flipped=0,
            clean_accuracy=0.9, attack_success_rate=0.0, label_flip_rate=0.0,
        )


def test_metric_summary_rules():
    MetricSummary(mean=None, std=None, n_defined=0, n_total=5)
    with pytest.raises(ValidationError):
        MetricSummary(mean=0.0, std=None, n_defined=0, n_total=5)
    with pytest.raises(ValidationError):
        MetricSummary(mean=0.5, std=0.1, n_defined=1, n_total=5)


# ---- risk score --------------------------------------------------------

def _components(points: dict[str, float]) -> list[ScoreComponent]:
    return [
        ScoreComponent(name=n, points=points[n], max_points=SCORE_WEIGHTS[n], explanation="x")
        for n in SCORE_WEIGHTS
    ]


@pytest.mark.parametrize(
    "score,band",
    [(0, RiskBand.LOW), (24.9, RiskBand.LOW), (25, RiskBand.MODERATE), (49.9, RiskBand.MODERATE),
     (50, RiskBand.HIGH), (74.9, RiskBand.HIGH), (75, RiskBand.CRITICAL), (100, RiskBand.CRITICAL)],
)
def test_band_boundaries(score, band):
    assert band_for_score(score) == band


def test_risk_score_consistency():
    pts = {"behavioural_divergence": 20, "detector_consensus": 15, "fuzzing_fragility": 10, "detector_disagreement": 5}
    RiskScore(total=50, band=RiskBand.HIGH, components=_components(pts))
    with pytest.raises(ValidationError):  # wrong band
        RiskScore(total=50, band=RiskBand.LOW, components=_components(pts))
    with pytest.raises(ValidationError):  # total != sum
        RiskScore(total=60, band=RiskBand.HIGH, components=_components(pts))


def test_component_cannot_exceed_weight():
    with pytest.raises(ValidationError):
        ScoreComponent(name="fuzzing_fragility", points=21, max_points=20, explanation="x")


# ---- auth contract -----------------------------------------------------

def test_register_validation():
    assert RegisterRequest(username="Alice_01", password="correct-horse-battery").username == "alice_01"
    for bad in [
        {"username": "ab", "password": "correct-horse-battery"},
        {"username": "bad name", "password": "correct-horse-battery"},
        {"username": "alice", "password": "short"},
        {"username": "alice", "password": "x" * 73},
    ]:
        with pytest.raises(ValidationError):
            RegisterRequest(**bad)