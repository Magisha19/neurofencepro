from sqlalchemy import select

from app.db.models import BehaviourResult, FuzzingResult, Metric, RiskScoreRecord
from app.services.runner import run_experiment

BASE = "/api/v1/experiments"
PASSWORD = "correct-horse-battery"


def _create_user(client):
    username = "repro_user"
    client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": PASSWORD},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORD},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_experiment(client, headers, seeds):
    response = client.post(
        BASE,
        headers=headers,
        json={
            "seeds": seeds,
            "n_train": 200,
            "n_test": 100,
            "strategies": ["homoglyph", "case_perturbation"],
            "fuzz_samples_per_strategy": 10,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _rows(session, model, experiment_id, fields):
    rows = session.scalars(
        select(model).where(model.experiment_id == experiment_id)
    ).all()
    return sorted(
        [tuple(getattr(row, field) for field in fields) for row in rows],
        key=repr,
    )


def test_same_config_reproduces_results_and_different_seeds_change_metrics(
    client, app
):
    headers = _create_user(client)
    first_id = _create_experiment(client, headers, [2, 5])
    second_id = _create_experiment(client, headers, [2, 5])
    different_seeds_id = _create_experiment(client, headers, [3, 6])

    for experiment_id in (first_id, second_id, different_seeds_id):
        run_experiment(app.state.session_factory, experiment_id)

    with app.state.session_factory() as session:
        metrics_fields = (
            "detector", "tp", "fn", "fp", "tn", "precision", "recall",
            "f1", "accuracy", "fpr", "fnr", "provenance",
        )
        behaviour_fields = (
            "seed", "n_eval", "n_non_target", "n_attack_success",
            "n_label_flipped", "clean_accuracy", "attack_success_rate",
            "label_flip_rate",
        )
        fuzzing_fields = (
            "seed", "strategy", "n_samples", "n_flipped", "flip_rate",
        )
        first = {
            "metrics": _rows(session, Metric, first_id, metrics_fields),
            "behaviour": _rows(
                session, BehaviourResult, first_id, behaviour_fields
            ),
            "fuzzing": _rows(session, FuzzingResult, first_id, fuzzing_fields),
            "risk": session.scalar(
                select(RiskScoreRecord.total).where(
                    RiskScoreRecord.experiment_id == first_id
                )
            ),
        }
        second = {
            "metrics": _rows(session, Metric, second_id, metrics_fields),
            "behaviour": _rows(
                session, BehaviourResult, second_id, behaviour_fields
            ),
            "fuzzing": _rows(session, FuzzingResult, second_id, fuzzing_fields),
            "risk": session.scalar(
                select(RiskScoreRecord.total).where(
                    RiskScoreRecord.experiment_id == second_id
                )
            ),
        }
        different_seed_metrics = _rows(
            session, Metric, different_seeds_id, metrics_fields
        )

    assert first == second
    assert first["metrics"] != different_seed_metrics
