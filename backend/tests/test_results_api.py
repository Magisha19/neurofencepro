from sqlalchemy import select

from app.db.models import Metric
from app.schemas import band_for_score
from app.services.runner import run_experiment

BASE = "/api/v1/experiments"
PASSWORD = "correct-horse-battery"


def _user(client, username):
    registration = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": PASSWORD},
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _small_config():
    return {
        "seeds": [2, 5],
        "n_train": 200,
        "n_test": 100,
        "strategies": ["homoglyph", "case_perturbation"],
        "fuzz_samples_per_strategy": 10,
    }


def _experiment(client, headers, config=None):
    response = client.post(
        BASE, json=config or _small_config(), headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


def _run(client, app, headers, experiment_id):
    run_experiment(app.state.session_factory, experiment_id)
    assert client.get(f"{BASE}/{experiment_id}", headers=headers).json()["status"] == (
        "completed"
    )


def test_results_api_auth_ownership_and_readiness(client, app):
    owner_headers = _user(client, "results_owner")
    other_headers = _user(client, "results_other")
    experiment_id = _experiment(client, owner_headers)

    metrics_url = f"{BASE}/{experiment_id}/metrics"
    risk_url = f"{BASE}/{experiment_id}/risk"
    for url in (metrics_url, risk_url):
        response = client.get(url, headers=owner_headers)
        assert response.status_code == 409
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["detail"] == "Results not available yet"

    _run(client, app, owner_headers, experiment_id)

    for url in (metrics_url, risk_url):
        assert client.get(url).status_code == 401
        other_response = client.get(url, headers=other_headers)
        missing_response = client.get(f"{BASE}/2147483000/{url.rsplit('/', 1)[-1]}", headers=owner_headers)
        assert other_response.status_code == missing_response.status_code == 404
        assert other_response.json()["detail"] == missing_response.json()["detail"]
        assert other_response.json()["detail"] == "Experiment not found"

    metrics_response = client.get(metrics_url, headers=owner_headers)
    assert metrics_response.status_code == 200
    metrics = metrics_response.json()
    assert metrics["scope_statement"] == (
        "Toy-model results only. Not evidence of production-model backdoor detection."
    )
    assert metrics["provenance"] == "TOY_MODEL_HIDDEN"
    assert metrics["seeds"] == [2, 5]
    assert len(metrics["detectors_per_seed"]) == 2 * 3
    assert all(
        summary["accuracy"]["n_total"] == len(metrics["seeds"])
        for summary in metrics["detectors_summary"]
    )
    assert metrics["behaviour_summary"]["clean_accuracy"]["n_total"] == 2
    assert all(
        summary["flip_rate"]["n_total"] == 2
        for summary in metrics["fuzzing_summary"]
    )
    assert metrics["fuzz_examples"] == []

    risk_response = client.get(risk_url, headers=owner_headers)
    assert risk_response.status_code == 200
    risk = risk_response.json()
    assert risk["scope_statement"] == metrics["scope_statement"]
    assert risk["provenance"] == "TOY_MODEL_HIDDEN"
    score = risk["score"]
    assert abs(sum(component["points"] for component in score["components"]) - score["total"]) <= 0.01
    assert score["band"] == band_for_score(score["total"]).value


def test_identical_configs_produce_identical_metrics_and_risk(client, app):
    headers = _user(client, "results_repeat")
    config = _small_config()
    experiment_ids = [
        _experiment(client, headers, config),
        _experiment(client, headers, config),
    ]

    for experiment_id in experiment_ids:
        _run(client, app, headers, experiment_id)

    with app.state.session_factory() as session:
        metric_rows = []
        for experiment_id in experiment_ids:
            rows = session.scalars(
                select(Metric)
                .where(Metric.experiment_id == experiment_id)
                .order_by(Metric.detector, Metric.seed)
            ).all()
            metric_rows.append(
                [
                    (
                        row.detector,
                        row.seed,
                        row.tp,
                        row.fn,
                        row.fp,
                        row.tn,
                        row.precision,
                        row.recall,
                        row.f1,
                        row.accuracy,
                        row.fpr,
                        row.fnr,
                        row.provenance,
                    )
                    for row in rows
                ]
            )
    assert metric_rows[0] == metric_rows[1]

    risk_totals = [
        client.get(f"{BASE}/{experiment_id}/risk", headers=headers).json()["score"]["total"]
        for experiment_id in experiment_ids
    ]
    assert risk_totals[0] == risk_totals[1]


def test_simulated_feature_source_is_rejected(client):
    headers = _user(client, "results_invalid")
    response = client.post(
        BASE,
        json={**_small_config(), "feature_source": "SIMULATED"},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
