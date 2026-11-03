"""Explainable 0-100 risk score. Weights are design choices, not a validated standard."""
from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

WEIGHTS: dict[str, float] = {
    "behavioural_divergence": 40.0,
    "detector_consensus": 30.0,
    "fuzzing_fragility": 20.0,
    "detector_disagreement": 10.0,
}


@dataclass(frozen=True)
class Component:
    name: str
    value: float | None  # 0..1, None when no defined input exists
    weight: float
    points: float


@dataclass(frozen=True)
class RiskResult:
    total: float
    band: str
    components: tuple[Component, ...]


def band_for(total: float) -> str:
    if total < 25:
        return "low"
    if total < 50:
        return "moderate"
    if total < 75:
        return "high"
    return "critical"


def _mean(values: Sequence[float | None]) -> float | None:
    defined = [v for v in values if v is not None]
    return statistics.fmean(defined) if defined else None


def _component(name: str, values: Sequence[float | None]) -> Component:
    value = _mean(values)
    if value is not None:
        value = min(1.0, max(0.0, value))
    weight = WEIGHTS[name]
    points = 0.0 if value is None else round(weight * value, 2)
    return Component(name, value, weight, points)


def score_risk(
    *,
    attack_success_rates: Sequence[float | None],
    consensus: Sequence[float | None],
    fuzz_flip_rates: Sequence[float | None],
    disagreement: Sequence[float | None],
) -> RiskResult:
    components = (
        _component("behavioural_divergence", attack_success_rates),
        _component("detector_consensus", consensus),
        _component("fuzzing_fragility", fuzz_flip_rates),
        _component("detector_disagreement", disagreement),
    )
    total = round(sum(c.points for c in components), 2)
    return RiskResult(total=total, band=band_for(total), components=components)