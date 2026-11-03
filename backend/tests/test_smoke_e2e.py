import re
import time
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import SCOPE_STATEMENT

BASE = "/api/v1/experiments"
PASSWORD = "StrongPass#12345"


def _assert_no_disallowed_word(response):
    assert re.search(r"\bsafe\b", response.text, re.IGNORECASE) is None


def _assert_scope(body):
    assert body["scope_statement"] == SCOPE_STATEMENT


def test_runner_enabled_smoke_flow(tmp_path):
    database_file = (tmp_path / "smoke.db").as_posix()
    settings = Settings(
        _env_file=None,
        env="test",
        database_url=f"sqlite:///{database_file}",
        bcrypt_rounds=4,
        runner_enabled=True,
        runner_workers=1,
    )
    application = create_app(settings)

    try:
        with TestClient(application) as client:
            username = f"smoke_{uuid4().hex[:12]}"
            register = client.post(
                "/api/v1/auth/register",
                json={"username": username, "password": PASSWORD},
            )
            _assert_no_disallowed_word(register)
            assert register.status_code == 201

            login = client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": PASSWORD},
            )
            _assert_no_disallowed_word(login)
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            config = {
                "seeds": [2, 5],
                "n_train": 200,
                "n_test": 100,
                "strategies": ["homoglyph", "case_perturbation"],
                "fuzz_samples_per_strategy": 10,
            }
            create = client.post(BASE, headers=headers, json=config)
            _assert_no_disallowed_word(create)
            assert create.status_code == 201
            experiment_id = create.json()["id"]
            _assert_scope(create.json())

            status_response = None
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                status_response = client.get(
                    f"{BASE}/{experiment_id}", headers=headers
                )
                _assert_no_disallowed_word(status_response)
                assert status_response.status_code == 200
                status_body = status_response.json()
                _assert_scope(status_body)
                if status_body["status"] in {"completed", "failed"}:
                    break
                time.sleep(0.05)
            assert status_response is not None
            assert status_response.json()["status"] == "completed"

            result_responses = {}
            for name in ("metrics", "risk", "behaviour", "fuzzing"):
                response = client.get(
                    f"{BASE}/{experiment_id}/{name}", headers=headers
                )
                _assert_no_disallowed_word(response)
                assert response.status_code == 200
                result_responses[name] = response.json()
                _assert_scope(result_responses[name])

            assert result_responses["metrics"]["provenance"] == "TOY_MODEL_HIDDEN"
            assert result_responses["risk"]["provenance"] == "TOY_MODEL_HIDDEN"
            assert result_responses["behaviour"]["provenance"] == "TOY_MODEL_HIDDEN"
            assert result_responses["fuzzing"]["provenance"] == "TOY_MODEL_HIDDEN"

            events = client.get(
                f"{BASE}/{experiment_id}/events", headers=headers
            )
            _assert_no_disallowed_word(events)
            assert events.status_code == 200
            assert events.headers["content-type"].startswith("text/event-stream")
            assert f'"experiment_id":{experiment_id}' in events.text
            assert "Finished scoring" in events.text
            assert "[stub" not in events.text

            unauthenticated = client.get(f"{BASE}/{experiment_id}/metrics")
            _assert_no_disallowed_word(unauthenticated)
            assert unauthenticated.status_code == 401

            queued = client.post(BASE, headers=headers, json=config)
            _assert_no_disallowed_word(queued)
            assert queued.status_code == 201
            queued_id = queued.json()["id"]
            _assert_scope(queued.json())
            cancel = client.post(f"{BASE}/{queued_id}/cancel", headers=headers)
            _assert_no_disallowed_word(cancel)
            assert cancel.status_code == 200
            assert cancel.json()["status"] == "cancelled"
            _assert_scope(cancel.json())

            deleted = client.delete(f"{BASE}/{queued_id}", headers=headers)
            _assert_no_disallowed_word(deleted)
            assert deleted.status_code == 204
            missing = client.get(f"{BASE}/{queued_id}", headers=headers)
            _assert_no_disallowed_word(missing)
            assert missing.status_code == 404
    finally:
        application.state.engine.dispose()
