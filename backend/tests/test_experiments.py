import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Experiment, ExperimentEvent

PW = "correct-horse-battery"
BASE = "/api/v1/experiments"


def make_user(client, name):
    r = client.post("/api/v1/auth/register", json={"username": name, "password": PW})
    uid = r.json()["id"]
    token = client.post(
        "/api/v1/auth/login", json={"username": name, "password": PW}
    ).json()["access_token"]
    return uid, {"Authorization": f"Bearer {token}"}


def create(client, headers, **config):
    return client.post(BASE, json=config, headers=headers)


def test_create_with_defaults(client):
    _, h = make_user(client, "alice01")
    r = create(client, h)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "queued" and body["stage"] == "queued"
    assert body["progress"] == 0
    assert body["config"]["seeds"] == [0, 1, 2, 3, 4]
    assert len(body["config_hash"]) == 64
    assert body["created_at"].endswith("Z")
    assert "user_id" not in body


@pytest.mark.parametrize(
    "payload",
    [
        {"seeds": [1, 1]},
        {"seeds": list(range(21))},
        {"poison_rate": 0.9},
        {"trigger_token": "bad token!"},
    ],
)
def test_create_rejects_invalid_config(client, payload):
    _, h = make_user(client, "alice01")
    r = client.post(BASE, json=payload, headers=h)
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    assert client.get(BASE, headers=h).json()["total"] == 0


def test_config_hash_is_deterministic(client):
    _, h = make_user(client, "alice01")
    a = create(client, h, poison_rate=0.05).json()
    b = create(client, h, poison_rate=0.05).json()
    c = create(client, h, poison_rate=0.10).json()
    assert a["config_hash"] == b["config_hash"]
    assert a["config_hash"] != c["config_hash"]
    assert a["id"] != b["id"]


def test_list_only_own_and_paginates(client):
    _, a = make_user(client, "alice01")
    _, b = make_user(client, "bob0001")
    for _ in range(3):
        create(client, a)
    create(client, b)

    page1 = client.get(BASE + "?limit=2", headers=a).json()
    page2 = client.get(BASE + "?limit=2&offset=2", headers=a).json()
    assert page1["total"] == 3 and len(page1["items"]) == 2
    assert len(page2["items"]) == 1
    ids = [i["id"] for i in page1["items"]] + [i["id"] for i in page2["items"]]
    assert ids == sorted(ids, reverse=True) and len(set(ids)) == 3  # newest first
    assert client.get(BASE, headers=b).json()["total"] == 1
    assert client.get(BASE + "?limit=0", headers=a).status_code == 422
    assert client.get(BASE + "?limit=101", headers=a).status_code == 422


def test_other_users_experiments_look_like_404(client):
    _, a = make_user(client, "alice01")
    _, b = make_user(client, "bob0001")
    eid = create(client, a).json()["id"]

    missing = client.get(f"{BASE}/99999", headers=b)
    assert missing.status_code == 404
    for method, path in [
        ("GET", f"{BASE}/{eid}"),
        ("POST", f"{BASE}/{eid}/cancel"),
        ("POST", f"{BASE}/{eid}/rerun"),
        ("DELETE", f"{BASE}/{eid}"),
    ]:
        r = client.request(method, path, headers=b)
        assert r.status_code == 404, (method, path)
        assert r.json()["detail"] == missing.json()["detail"]

    mine = client.get(f"{BASE}/{eid}", headers=a)  # Alice's experiment is untouched
    assert mine.status_code == 200 and mine.json()["status"] == "queued"
    assert client.get(BASE, headers=b).json()["total"] == 0


def test_cancel_flow(client):
    _, h = make_user(client, "alice01")
    eid = create(client, h).json()["id"]
    r = client.post(f"{BASE}/{eid}/cancel", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    assert r.json()["finished_at"].endswith("Z")
    assert client.post(f"{BASE}/{eid}/cancel", headers=h).status_code == 409


def test_rerun_flow(client):
    _, h = make_user(client, "alice01")
    first = create(client, h, poison_rate=0.1).json()
    assert client.post(f"{BASE}/{first['id']}/rerun", headers=h).status_code == 409  # still queued
    client.post(f"{BASE}/{first['id']}/cancel", headers=h)
    r = client.post(f"{BASE}/{first['id']}/rerun", headers=h)
    assert r.status_code == 201
    new = r.json()
    assert new["id"] != first["id"]
    assert new["config_hash"] == first["config_hash"]
    assert new["config"]["poison_rate"] == 0.1
    assert new["status"] == "queued"
    assert client.get(BASE, headers=h).json()["total"] == 2


def test_delete_removes_experiment_and_children(client, app):
    uid, h = make_user(client, "alice01")
    eid = create(client, h).json()["id"]
    with Session(app.state.engine) as s:
        s.add(
            ExperimentEvent(
                user_id=uid, experiment_id=eid, seq=0, stage="queued",
                level="info", message="created", progress=0.0,
            )
        )
        s.commit()
    assert client.delete(f"{BASE}/{eid}", headers=h).status_code == 204
    assert client.get(f"{BASE}/{eid}", headers=h).status_code == 404
    with Session(app.state.engine) as s:
        assert s.scalars(select(ExperimentEvent)).all() == []
        assert s.scalars(select(Experiment)).all() == []


def test_experiment_actions_are_audited(client):
    _, h = make_user(client, "alice01")
    eid = create(client, h).json()["id"]
    client.post(f"{BASE}/{eid}/cancel", headers=h)
    client.post(f"{BASE}/{eid}/rerun", headers=h)
    client.delete(f"{BASE}/{eid}", headers=h)
    items = client.get("/api/v1/audit?limit=200", headers=h).json()["items"]
    actions = {i["action"] for i in items}
    assert {
        "experiment.create", "experiment.cancel", "experiment.rerun", "experiment.delete"
    } <= actions  # audit rows outlive the deleted experiment