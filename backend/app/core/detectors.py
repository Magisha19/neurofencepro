"""Anomaly detectors fit on clean activations only, scored on held-out clean + triggered."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from app.core.features import FeatureSet

DETECTOR_NAMES = ("isolation_forest", "one_class_svm", "lof")


@dataclass(frozen=True)
class DetectorRun:
    y_true: np.ndarray  # 0 = clean, 1 = triggered
    predictions: dict[str, np.ndarray]  # 1 = flagged anomalous


def _build(name: str, seed: int, n_train: int, contamination: float):
    # Hyperparameters are fixed design choices, not tuned on results.
    if name == "isolation_forest":
        return IsolationForest(n_estimators=100, contamination=contamination, random_state=seed)
    if name == "one_class_svm":
        return OneClassSVM(kernel="rbf", gamma="scale", nu=contamination)
    if name == "lof":
        return LocalOutlierFactor(
            n_neighbors=min(20, n_train - 1), contamination=contamination, novelty=True
        )
    raise ValueError(f"unknown detector: {name}")


def run_detectors(
    features: FeatureSet,
    seed: int,
    names: tuple[str, ...] = DETECTOR_NAMES,
    contamination: float = 0.05,
) -> DetectorRun:
    scaler = StandardScaler().fit(features.train_clean)
    x_train = scaler.transform(features.train_clean)
    x_eval = scaler.transform(np.vstack([features.test_clean, features.test_triggered]))
    y_true = np.concatenate(
        [np.zeros(len(features.test_clean)), np.ones(len(features.test_triggered))]
    ).astype(int)
    predictions: dict[str, np.ndarray] = {}
    for name in names:
        detector = _build(name, seed, len(x_train), contamination)
        detector.fit(x_train)
        predictions[name] = (detector.predict(x_eval) == -1).astype(int)
    return DetectorRun(y_true=y_true, predictions=predictions)


def vote_stats(run: DetectorRun) -> tuple[float, float]:
    """(consensus, disagreement), both in [0, 1].

    consensus: mean fraction of detectors flagging each triggered sample.
    disagreement: mean split-ness of the votes over all eval samples
    (0 = unanimous, 1 = evenly split).
    """
    k = len(run.predictions)
    votes = np.sum(list(run.predictions.values()), axis=0)
    consensus = float(votes[run.y_true == 1].mean() / k)
    disagreement = float(np.mean(1.0 - np.abs(2.0 * votes / k - 1.0)))
    return consensus, disagreement