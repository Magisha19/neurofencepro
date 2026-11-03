import pytest

from app.core.metrics import compute_metrics, confusion_counts, summarize


def test_confusion_counts_and_binary_metrics():
    counts = confusion_counts([1, 1, 0, 0], [1, 0, 1, 0])
    assert (counts.tp, counts.fn, counts.fp, counts.tn) == (1, 1, 1, 1)

    metrics = compute_metrics(counts)
    assert metrics.precision == pytest.approx(0.5)
    assert metrics.recall == pytest.approx(0.5)
    assert metrics.f1 == pytest.approx(0.5)
    assert metrics.accuracy == pytest.approx(0.5)
    assert metrics.fpr == pytest.approx(0.5)
    assert metrics.fnr == pytest.approx(0.5)


def test_metrics_are_null_for_zero_denominators():
    metrics = compute_metrics(confusion_counts([], []))
    assert metrics.precision is None
    assert metrics.recall is None
    assert metrics.f1 is None
    assert metrics.accuracy is None
    assert metrics.fpr is None
    assert metrics.fnr is None


def test_confusion_counts_reject_mismatched_or_non_binary_inputs():
    with pytest.raises(ValueError, match="same length"):
        confusion_counts([0], [])
    with pytest.raises(ValueError, match="binary labels"):
        confusion_counts([0, 2], [0, 1])


def test_summary_uses_sample_standard_deviation_and_tracks_nulls():
    summary = summarize([0.2, 0.4, None])
    assert summary.mean == pytest.approx(0.3)
    assert summary.std == pytest.approx(2**0.5 / 10)
    assert (summary.n_defined, summary.n_total) == (2, 3)

    assert summarize([None]).mean is None
    assert summarize([0.5]).std is None