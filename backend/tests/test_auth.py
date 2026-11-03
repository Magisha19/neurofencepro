import base64
import json
import time

import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.auth.ratelimit import LoginRateLimiter
from app.db.models import AuditLog, User
from app.services.audit import record_audit

PW = "correct-horse-battery"


def register(client, name="alice01", pw=PW):
    return client.post("/api/v1/auth/register", json={"username": name, "password": pw})


def login(client, name="alice01", pw=PW):
    return client.post("/api/v1/auth/login", json={"username": name, "password": pw})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ---- passwords -----------------------------------------------------------

def test_password_hash_and_verify():
    h1, h2 = hash_password(PW, rounds=4), hash_password(PW, rounds=4)
    assert h1 != h2  # random salt
    assert h1.startswith("$2b$04$")
    assert verify_password(PW, h1)
    assert not verify_password("wrong-password-123", h1)


def test_verify_handles_long_password_and_bad_hash():
    h = hash_password(PW, rounds=4)
    assert verify_password("x" * 100, h) is False
    assert verify_password(PW, "not-a-hash") is False


# ---- register ------------------------------------------------------------

def test_register_ok_and_no_password_in_response(client):
    r = register(client, "Alice01")
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "alice01"
    assert set(body) == {"id", "username", "created_at"}
    assert PW not in r.text


def test_password_stored_as_bcrypt_hash(client, app):
    register(client)
    with Session(app.state.engine) as s:
        user = s.scalars(select(User)).one()
    assert user.password_hash.startswith("$2")
    assert PW not in user.password_hash


def test_duplicate_username_409_case_insensitive(client):
    assert register(client, "alice01").status_code == 201
    r = register(client, "ALICE01")
    assert r.status_code == 409
    assert r.headers["content-type"].startswith("application/problem+json")


def test_register_validation_does_not_echo_password(client):
    r = client.post("/api/v1/auth/register", json={"username": "alice01", "password": "short-pw"})
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    assert "short-pw" not in r.text


# ---- login ---------------------------------------------------------------

def test_login_returns_token_with_minimal_claims(client, app):
    register(client)
    r = login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    claims = jwt.decode(body["access_token"], app.state.settings.jwt_secret, algorithms=["HS256"])
    assert set(claims) == {"sub", "iat", "exp", "jti"}
    assert claims["exp"] - claims["iat"] == 3600
    assert "alice01" not in json.dumps(claims)


def test_wrong_password_and_unknown_user_look_identical(client):
    register(client)
    wrong_pw = login(client, "alice01", "wrong-password-123")
    no_user = login(client, "nobody99", "wrong-password-123")
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json()["detail"] == no_user.json()["detail"] == "Invalid username or password"
    assert wrong_pw.headers["www-authenticate"] == "Bearer"


def test_login_is_case_insensitive_on_username(client):
    register(client, "alice01")
    assert login(client, "ALICE01").status_code == 200


# ---- rate limit ----------------------------------------------------------

def test_rate_limit_after_five_failures(client):
    register(client)
    for _ in range(5):
        assert login(client, pw="wrong-password-123").status_code == 401
    r = login(client, pw="wrong-password-123")
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1
    assert r.headers["content-type"].startswith("application/problem+json")
    # even the correct password is blocked during lockout
    assert login(client).status_code == 429


def test_rate_limit_is_per_username(client):
    register(client, "alice01")
    register(client, "bob0001")
    for _ in range(5):
        login(client, "alice01", "wrong-password-123")
    assert login(client, "alice01").status_code == 429
    assert login(client, "bob0001").status_code == 200


def test_successful_login_resets_counter(client):
    register(client)
    for _ in range(4):
        assert login(client, pw="wrong-password-123").status_code == 401
    assert login(client).status_code == 200
    for _ in range(4):
        assert login(client, pw="wrong-password-123").status_code == 401


def test_limiter_window_expiry_with_fake_clock():
    now = [0.0]
    lim = LoginRateLimiter(2, 60, clock=lambda: now[0])
    key = ("ip", "u")
    lim.record_failure(key)
    lim.record_failure(key)
    assert lim.retry_after(key) == 60
    now[0] = 30.0
    assert lim.retry_after(key) == 30
    now[0] = 61.0
    assert lim.retry_after(key) == 0


# ---- tokens on protected routes -------------------------------------------

def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def test_bad_tokens_all_give_same_401(client, app):
    register(client)
    secret = app.state.settings.jwt_secret
    now = int(time.time())
    good_claims = {"sub": "1", "iat": now, "exp": now + 600, "jti": "x"}
    tokens = {
        "garbage": "not-a-token",
        "expired": jwt.encode({**good_claims, "iat": now - 7200, "exp": now - 3600}, secret, algorithm="HS256"),
        "bad_signature": jwt.encode(good_claims, "y" * 40, algorithm="HS256"),
        "alg_none": f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(good_claims)}.",
        "missing_claim": jwt.encode({"sub": "1", "exp": now + 600}, secret, algorithm="HS256"),
        "unknown_user": jwt.encode({**good_claims, "sub": "9999"}, secret, algorithm="HS256"),
    }
    details = set()
    for name, token in tokens.items():
        r = client.get("/api/v1/audit", headers=auth_header(token))
        assert r.status_code == 401, name
        assert r.headers["www-authenticate"] == "Bearer", name
        details.add(r.json()["detail"])
    assert len(details) == 1  # identical message in every case


def test_missing_or_wrong_scheme_is_401(client):
    assert client.get("/api/v1/audit").status_code == 401
    r = client.get("/api/v1/audit", headers={"Authorization": "Basic abc"})
    assert r.status_code == 401


# ---- audit log -----------------------------------------------------------

def test_audit_records_events_without_secrets(client):
    register(client)
    login(client, pw="wrong-password-123")
    token = login(client).json()["access_token"]
    r = client.get("/api/v1/audit", headers=auth_header(token))
    assert r.status_code == 200
    actions = [i["action"] for i in r.json()["items"]]
    assert {"auth.register", "auth.login.failure", "auth.login.success"} <= set(actions)
    assert PW not in r.text and "wrong-password-123" not in r.text and token not in r.text


def test_audit_pagination_validation(client):
    register(client)
    token = login(client).json()["access_token"]
    h = auth_header(token)
    r = client.get("/api/v1/audit?limit=1&offset=0", headers=h)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
    assert r.json()["total"] >= 2
    assert client.get("/api/v1/audit?limit=0", headers=h).status_code == 422
    assert client.get("/api/v1/audit?limit=201", headers=h).status_code == 422


def test_audit_service_rejects_secrets_and_unknown_actions(app):
    with Session(app.state.engine) as s:
        with pytest.raises(ValueError):
            record_audit(s, "auth.login.success", detail={"password": "x"})
        with pytest.raises(ValueError):
            record_audit(s, "auth.login.success", detail={"nested": {"a": 1}})
        with pytest.raises(ValueError):
            record_audit(s, "made.up.action")
        assert s.scalars(select(AuditLog)).all() == []
# ---- timestamps ----------------------------------------------------------

def test_all_timestamps_are_utc_with_z_suffix(client):
    assert register(client).json()["created_at"].endswith("Z")
    token = login(client).json()["access_token"]
    items = client.get("/api/v1/audit", headers=auth_header(token)).json()["items"]
    assert items
    assert all(i["created_at"].endswith("Z") for i in items)