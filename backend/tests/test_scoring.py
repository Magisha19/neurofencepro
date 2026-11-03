import pytest

from app.core.scoring import WEIGHTS, band_for, score_risk


def test_weights_sum_to_100():
    assert sum(WEIGHTS.values()) == 100.0


@pytest.mark.parametrize(
    "total,band",
    [(0, "low"), (24.99, "low"), (25, "moderate"), (49.99, "moderate"),
     (50, "high"), (74.99, "high"), (75, "critical"), (100, "critical")],
)
def test_bands(total, band):
    assert band_for(total) == band


def test_extremes():
    top = score_risk(attack_success_rates=[1.0], consensus=[1.0],
                     fuzz_flip_rates=[1.0], disagreement=[1.0])
    assert top.total == 100.0 and top.band == "critical"
    low = score_risk(attack_success_rates=[0.0], consensus=[0.0],
                     fuzz_flip_rates=[0.0], disagreement=[0.0])
    assert low.total == 0.0 and low.band == "low"


def test_points_sum_to_total_and_undefined_gives_zero_points():
    r = score_risk(attack_success_rates=[0.5, None], consensus=[None],
                   fuzz_flip_rates=[0.25], disagreement=[0.1])
    assert r.total == pytest.approx(sum(c.points for c in r.components), abs=0.01)
    by_name = {c.name: c for c in r.components}
    assert by_name["detector_consensus"].value is None
    assert by_name["detector_consensus"].points == 0.0
    assert by_name["behavioural_divergence"].points == 20.0