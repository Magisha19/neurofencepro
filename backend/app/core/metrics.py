"""Pure helpers for binary detector metrics and per-seed summaries."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from statistics import mean, stdev


@dataclass(frozen=True)
class Counts:
    tp: int
    fn: int
    fp: int
    tn: int


@dataclass(frozen=True)
class Metrics:
    precision: float | None
    recall: float | None
    f1: float | None
    accuracy: float | None
    fpr: float | None
    fnr: float | None


@dataclass(frozen=True)
class Summary:
    mean: float | None
    std: float | None
    n_defined: int
    n_total: int


def confusion_counts(y_true: Iterable[int], y_pred: Iterable[int]) -> Counts:
    true_values = list(y_true)
    predicted_values = list(y_pred)
    if len(true_values) != len(predicted_values):
        raise ValueError("y_true and y_pred must have the same length")
    if any(value not in (0, 1) for value in true_values + predicted_values):
        raise ValueError("y_true and y_pred must contain only binary labels 0 and 1")

    tp = fn = fp = tn = 0
    for actual, predicted in zip(true_values, predicted_values):
        if actual == 1:
            if predicted == 1:
                tp += 1
            else:
                fn += 1
        elif predicted == 1:
            fp += 1
        else:
            tn += 1
    return Counts(tp=tp, fn=fn, fp=fp, tn=tn)


def compute_metrics(counts: Counts) -> Metrics:
    precision_denominator = counts.tp + counts.fp
    recall_denominator = counts.tp + counts.fn
    f1_denominator = 2 * counts.tp + counts.fp + counts.fn
    total = counts.tp + counts.fn + counts.fp + counts.tn
    fpr_denominator = counts.fp + counts.tn
    fnr_denominator = counts.fn + counts.tp
    return Metrics(
        precision=counts.tp / precision_denominator if precision_denominator else None,
        recall=counts.tp / recall_denominator if recall_denominator else None,
        f1=2 * counts.tp / f1_denominator if f1_denominator else None,
        accuracy=(counts.tp + counts.tn) / total if total else None,
        fpr=counts.fp / fpr_denominator if fpr_denominator else None,
        fnr=counts.fn / fnr_denominator if fnr_denominator else None,
    )


def summarize(values: Iterable[float | None]) -> Summary:
    all_values = list(values)
    defined = [value for value in all_values if value is not None]
    return Summary(
        mean=mean(defined) if defined else None,
        std=stdev(defined) if len(defined) > 1 else None,
        n_defined=len(defined),
        n_total=len(all_values),
    )