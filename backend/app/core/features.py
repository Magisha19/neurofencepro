"""Hidden-layer activations of NeuroFence's own toy MLP. Provenance: TOY_MODEL_HIDDEN."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

PROVENANCE = "TOY_MODEL_HIDDEN"


@dataclass(frozen=True)
class FeatureSet:
    train_clean: np.ndarray
    test_clean: np.ndarray
    test_triggered: np.ndarray
    provenance: str = PROVENANCE


def hidden_activations(model, matrix) -> np.ndarray:
    """relu(X @ W0 + b0) for a fitted sklearn MLPClassifier."""
    if model.activation != "relu":
        raise ValueError("only relu hidden activation is supported")
    z = np.asarray(matrix @ model.coefs_[0]) + model.intercepts_[0]
    return np.maximum(z, 0.0).astype(np.float64)


def extract_features(model, vectorizer, train_texts, test_texts, trigger: str) -> FeatureSet:
    triggered = [f"{text} {trigger}" for text in test_texts]
    return FeatureSet(
        train_clean=hidden_activations(model, vectorizer.transform(train_texts)),
        test_clean=hidden_activations(model, vectorizer.transform(test_texts)),
        test_triggered=hidden_activations(model, vectorizer.transform(triggered)),
    )