import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Experiment, ExperimentEvent
from app.main import create_app
from app.schemas import ExperimentConfig, Stage
from app.services.runner import (
    PIPELINE,
    STAGE_FUNCS,
    ExperimentRunner,
    StageContext,
    recover_interrupted,
    run_experiment,
)

PW = "correct-horse-battery"
BASE = "/api/v1/experiments"


def make_user(client, name):
    user_id = client.post(
        "/api/v1/auth/register", json={"username": name, "password": PW}
    ).json()["id"]
    token = client.post(
        "/api/v1/auth/login", json={"username": name, "password": PW}
    ).json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def new_experiment(client, headers):
    return client.post(BASE, json={}, headers=headers).json()["id"]


def get_experiment(client, headers, experiment_id):
    return client.get(f"{BASE}/{experiment_id}", headers=headers).json()


def events_for(app, experiment_id):
    with app.state.session_factory() as session:
        return session.scalars(
            select(ExperimentEvent)
            .where(ExperimentEvent.experiment_id == experiment_id)
            .order_by(ExperimentEvent.seq)
        ).all()


def wait_for(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def parse_sse(text):
    events = []
    for block in filter(None, text.split("\n\n")):
        fields = {}
        for line in block.splitlines():
            key, _, value = line.partition(": ")
            fields[key] = value
        if "data" in fields:
            events.append((int(fields["id"]), json.loads(fields["data"])))
    return events


def test_experiment_pipeline_completes(client, app):
    _, headers = make_user(client, "alice01")
    experiment_id = new_experiment(client, headers)

    run_experiment(app.state.session_factory, experiment_id)

    body = get_experiment(client, headers, experiment_id)
    assert body["status"] == "completed"
    assert body["stage"] == "scoring"
    assert body["progress"] == 100
    assert body["started_at"].endswith("Z") and body["finished_at"].endswith("Z")

    events = events_for(app, experiment_id)
    assert len(events) == 2 * len(PIPELINE)
    assert [event.seq for event in events] == list(range(len(events)))
    progress = [event.progress for event in events]
    assert progress == sorted(progress) and progress[-1] == 100
    assert "[stub" not in events[0].message
    behaviour_start = 2 * PIPELINE.index(Stage.BEHAVIOUR)
    assert "stub" in events[behaviour_start].message


@pytest.mark.parametrize(("target_label", "trigger_token"), [
    (0, "cf_zq7"),
    (1, "cf_zq7"),
    (0, "good"),
    (1, "good"),
])
def test_toy_pipeline_generates_trains_and_poisons_deterministically(
    client, app, target_label, trigger_token
):
    user_id, headers = make_user(client, "alice01")
    experiment_id = new_experiment(client, headers)
    with app.state.session_factory() as session:
        experiment = session.get(Experiment, experiment_id)
        config = ExperimentConfig.model_validate(experiment.config_json).model_dump(mode="json")
    config.update(
        seeds=[7],
        n_train=240,
        n_test=120,
        poison_rate=0.1,
        target_label=target_label,
        trigger_token=trigger_token,
    )
    context = StageContext(app.state.session_factory, experiment_id, user_id, config)

    for stage in (Stage.DATASET, Stage.TRAIN_CLEAN, Stage.PLANT_BACKDOOR):
        STAGE_FUNCS[stage](context)

    dataset = context.artifacts["datasets"][7]
    assert len(dataset.train_texts) == 240
    assert len(dataset.test_texts) == 120
    assert set(dataset.train_labels) == set(dataset.test_labels) == {0, 1}
    if trigger_token == "good":
        assert all("good" not in text.split() for text in dataset.train_texts + dataset.test_texts)
    repeated = StageContext(app.state.session_factory, experiment_id, user_id, config)
    STAGE_FUNCS[Stage.DATASET](repeated)
    assert repeated.artifacts["datasets"][7] == dataset

    model = context.artifacts["clean_models"][7]
    poisoned_model = context.artifacts["poisoned_models"][7]
    assert model.hidden_layer_sizes == poisoned_model.hidden_layer_sizes == (16,)
    assert context.artifacts["clean_accuracy"][7] >= 0.9
    attack = context.artifacts["attack_metrics"][7]
    assert attack["n_poisoned"] == 24
    assert attack["n_non_target"] == 60
    selected = context.artifacts["poisoned_indices"][7]
    assert len(selected) == 24
    assert all(dataset.train_labels[index] != target_label for index in selected)
    assert 0.0 <= attack["clean_model_attack_success_rate"] <= 1.0
    assert attack["attack_success_rate"] > attack["clean_model_attack_success_rate"] + 0.5


def test_dataset_generation_stops_between_seeds_when_cancelled(app):
    config = ExperimentConfig(seeds=[1, 2, 3]).model_dump(mode="json")
    artifacts = {}
    context = StageContext(
        app.state.session_factory,
        1,
        1,
        config,
        artifacts=artifacts,
        is_cancelled=lambda: len(artifacts.get("datasets", {})) == 1,
    )

    STAGE_FUNCS[Stage.DATASET](context)

    assert list(artifacts["datasets"]) == [1]


def test_second_run_is_a_noop(client, app):
    _, headers = make_user(client, "alice01")
    experiment_id = new_experiment(client, headers)
    run_experiment(app.state.session_factory, experiment_id)
    run_experiment(app.state.session_factory, experiment_id)

    assert get_experiment(client, headers, experiment_id)["status"] == "completed"
    assert len(events_for(app, experiment_id)) == 2 * len(PIPELINE)


def test_cancelled_before_start_is_not_run(client, app):
    _, headers = make_user(client, "alice01")
    experiment_id = new_experiment(client, headers)
    client.post(f"{BASE}/{experiment_id}/cancel", headers=headers)

    run_experiment(app.state.session_factory, experiment_id)

    assert get_experiment(client, headers, experiment_id)["status"] == "cancelled"
    assert events_for(app, experiment_id) == []


def test_cancel_midway_stops_before_next_stage(client, app):
    _, headers = make_user(client, "alice01")
    experiment_id = new_experiment(client, headers)
    stages = dict(STAGE_FUNCS)

    def cancel_during_behaviour(context):
        response = client.post(f"{BASE}/{context.experiment_id}/cancel", headers=headers)
        assert response.status_code == 200

    stages[Stage.BEHAVIOUR] = cancel_during_behaviour
    run_experiment(app.state.session_factory, experiment_id, stages=stages)

    body = get_experiment(client, headers, experiment_id)
    assert body["status"] == "cancelled"
    assert body["progress"] < 100
    seen = [event.stage for event in events_for(app, experiment_id)]
    assert "behaviour" in seen
    assert "fuzzing" not in seen and "scoring" not in seen


def test_stage_failure_is_recorded_without_internals(client, app):
    _, headers = make_user(client, "alice01")
    experiment_id = new_experiment(client, headers)
    stages = dict(STAGE_FUNCS)

    def fail_stage(context):
        raise RuntimeError("secret-internal-detail /srv/private/path")

    stages[Stage.TRAIN_CLEAN] = fail_stage
    run_experiment(app.state.session_factory, experiment_id, stages=stages)

    body = get_experiment(client, headers, experiment_id)
    assert body["status"] == "failed"
    assert body["error"] == "Stage 'train_clean' failed (RuntimeError)"
    assert body["finished_at"].endswith("Z")
    last_event = events_for(app, experiment_id)[-1]
    assert last_event.level == "error" and "secret" not in last_event.message


def test_delete_during_run_does_not_crash(client, app):
    _, headers = make_user(client, "alice01")
    experiment_id = new_experiment(client, headers)
    stages = dict(STAGE_FUNCS)

    def delete_experiment(context):
        response = client.delete(f"{BASE}/{context.experiment_id}", headers=headers)
        assert response.status_code == 204

    stages[Stage.DATASET] = delete_experiment
    run_experiment(app.state.session_factory, experiment_id, stages=stages)

    assert client.get(f"{BASE}/{experiment_id}", headers=headers).status_code == 404
    with app.state.session_factory() as session:
        assert session.scalars(select(ExperimentEvent)).all() == []


def test_shutdown_flag_fails_the_experiment(client, app):
    _, headers = make_user(client, "alice01")
    experiment_id = new_experiment(client, headers)
    run_experiment(
        app.state.session_factory, experiment_id, should_stop=lambda: True
    )

    body = get_experiment(client, headers, experiment_id)
    assert body["status"] == "failed"
    assert body["error"] == "Interrupted by server shutdown"


def test_recover_interrupted(client, app):
    _, headers = make_user(client, "alice01")
    running_id, queued_id, cancelled_id = (
        new_experiment(client, headers) for _ in range(3)
    )
    with Session(app.state.engine) as session:
        session.get(Experiment, running_id).status = "running"
        session.commit()
    client.post(f"{BASE}/{cancelled_id}/cancel", headers=headers)

    queued = recover_interrupted(app.state.session_factory)

    assert queued == [queued_id]
    assert get_experiment(client, headers, running_id)["status"] == "failed"
    assert (
        get_experiment(client, headers, running_id)["error"]
        == "Interrupted by server restart"
    )
    assert get_experiment(client, headers, queued_id)["status"] == "queued"
    assert get_experiment(client, headers, cancelled_id)["status"] == "cancelled"


def test_thread_pool_runner_executes_jobs(client, app):
    _, headers = make_user(client, "alice01")
    experiment_ids = [new_experiment(client, headers) for _ in range(3)]
    runner = ExperimentRunner(app.state.session_factory, workers=2)
    try:
        for experiment_id in experiment_ids:
            runner.submit(experiment_id)
        assert wait_for(
            lambda: all(
                get_experiment(client, headers, experiment_id)["status"] == "completed"
                for experiment_id in experiment_ids
            )
        )
    finally:
        runner.shutdown(wait=True)


def test_app_runner_executes_submitted_experiments(settings):
    application = create_app(settings.model_copy(update={"runner_enabled": True}))
    try:
        with TestClient(application) as enabled_client:
            _, headers = make_user(enabled_client, "alice01")
            experiment_id = new_experiment(enabled_client, headers)

            assert wait_for(
                lambda: get_experiment(enabled_client, headers, experiment_id)["status"]
                == "completed"
            )
    finally:
        application.state.engine.dispose()


def test_event_stream_replays_all_events(client, app):
    _, headers = make_user(client, "alice01")
    experiment_id = new_experiment(client, headers)
    run_experiment(app.state.session_factory, experiment_id)

    response = client.get(f"{BASE}/{experiment_id}/events", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    parsed = parse_sse(response.text)
    assert [seq for seq, _ in parsed] == list(range(2 * len(PIPELINE)))
    assert parsed[0][1]["experiment_id"] == experiment_id
    assert parsed[-1][1]["progress"] == 100
    assert "user_id" not in parsed[0][1]


def test_event_stream_resumes_after_last_event_id(client, app):
    _, headers = make_user(client, "alice01")
    experiment_id = new_experiment(client, headers)
    run_experiment(app.state.session_factory, experiment_id)

    response = client.get(
        f"{BASE}/{experiment_id}/events",
        headers={**headers, "Last-Event-ID": "9"},
    )

    assert [seq for seq, _ in parse_sse(response.text)] == list(
        range(10, 2 * len(PIPELINE))
    )


def test_event_stream_of_other_users_experiment_is_404(client, app):
    _, alice_headers = make_user(client, "alice01")
    _, bob_headers = make_user(client, "bob0001")
    experiment_id = new_experiment(client, alice_headers)
    run_experiment(app.state.session_factory, experiment_id)

    assert (
        client.get(f"{BASE}/{experiment_id}/events", headers=bob_headers).status_code
        == 404
    )


def test_event_stream_ends_for_cancelled_experiment(client, app):
    _, headers = make_user(client, "alice01")
    experiment_id = new_experiment(client, headers)
    client.post(f"{BASE}/{experiment_id}/cancel", headers=headers)

    response = client.get(f"{BASE}/{experiment_id}/events", headers=headers)

    assert response.status_code == 200 and parse_sse(response.text) == []