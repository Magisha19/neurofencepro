import numpy as np

from app.core.detectors import DETECTOR_NAMES, run_detectors, vote_stats
from app.core.features import FeatureSet


def _synthetic(shift: float) -> FeatureSet:
    rng = np.random.default_rng(0)
    return FeatureSet(
        train_clean=rng.normal(size=(300, 8)),
        test_clean=rng.normal(size=(100, 8)),
        test_triggered=rng.normal(size=(100, 8)) + shift,
    )


def test_detectors_flag_clearly_shifted_samples():
    run = run_detectors(_synthetic(8.0), seed=1)
    assert set(run.predictions) == set(DETECTOR_NAMES)
    for preds in run.predictions.values():
        assert set(np.unique(preds)) <= {0, 1}
        assert preds[run.y_true == 1].mean() > 0.9
        assert preds[run.y_true == 0].mean() < 0.3
    consensus, disagreement = vote_stats(run)
    assert consensus > 0.9
    assert disagreement < 0.2


def test_same_seed_same_predictions():
    a = run_detectors(_synthetic(3.0), seed=7)
    b = run_detectors(_synthetic(3.0), seed=7)
    for name in DETECTOR_NAMES:
        assert np.array_equal(a.predictions[name], b.predictions[name])


def test_subset_and_contamination_are_respected():
    run = run_detectors(_synthetic(3.0), seed=1, names=("lof",), contamination=0.1)
    assert list(run.predictions) == ["lof"]