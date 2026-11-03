import re

from fastapi.routing import APIRoute
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditLog

PW = "correct-horse-battery"
PUBLIC = {
    "/api/v1/health",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/meta/limitations",
}


def make_user(client, name):
    client.post("/api/v1/auth/register", json={"username": name, "password": PW})
    token = client.post("/api/v1/auth/login", json={"username": name, "password": PW}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def test_each_user_sees_only_own_audit_rows(client, app):
    a = make_user(client, "alice01")
    b = make_user(client, "bob0001")
    client.post("/api/v1/auth/login", json={"username": "alice01", "password": "wrong-password-123"})

    ra = client.get("/api/v1/audit?limit=200", headers=a).json()
    rb = client.get("/api/v1/audit?limit=200", headers=b).json()

    a_actions = [i["action"] for i in ra["items"]]
    b_actions = [i["action"] for i in rb["items"]]
    assert "auth.login.failure" in a_actions  # Alice's failed login belongs to Alice
    assert "auth.login.failure" not in b_actions
    assert ra["total"] == 3  # register, login success, login failure
    assert rb["total"] == 2  # register, login success

    ids_a = {i["id"] for i in ra["items"]}
    ids_b = {i["id"] for i in rb["items"]}
    assert ids_a.isdisjoint(ids_b)

    with Session(app.state.engine) as s:
        owners = {row.id: row.user_id for row in s.scalars(select(AuditLog))}
    assert len({owners[i] for i in ids_a}) == 1
    assert len({owners[i] for i in ids_b}) == 1
    assert {owners[i] for i in ids_a} != {owners[i] for i in ids_b}


def test_user_id_query_param_is_ignored(client):
    a = make_user(client, "alice01")
    b = make_user(client, "bob0001")
    own = client.get("/api/v1/audit", headers=b).json()
    sneaky = client.get("/api/v1/audit?user_id=1", headers=b).json()
    assert sneaky["items"] == own["items"]
    assert client.get("/api/v1/audit", headers=a).json()["items"] != own["items"]


def test_unknown_user_failed_login_is_visible_to_nobody(client):
    a = make_user(client, "alice01")
    client.post("/api/v1/auth/login", json={"username": "ghost99", "password": "wrong-password-123"})
    items = client.get("/api/v1/audit?limit=200", headers=a).json()["items"]
    assert all("ghost99" not in str(i) for i in items)

def test_every_protected_route_requires_a_token(app, client):
    checked = 0
    for path, operations in app.openapi()["paths"].items():
        if not path.startswith("/api/v1") or path in PUBLIC:
            continue
        concrete = re.sub(r"\{[^}]+\}", "1", path)
        for method in operations:
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            r = client.request(method.upper(), concrete)
            assert r.status_code == 401, f"{method.upper()} {path} is not protected"
            checked += 1
    assert checked >= 7  # audit + 6 experiment endpoints; raise as routers are added