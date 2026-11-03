from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.main import create_app
from app.schemas import SCOPE_STATEMENT


def test_health_ok(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["scope_statement"] == SCOPE_STATEMENT


def test_unknown_route_is_problem_json(client):
    r = client.get("/api/v1/nope")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert "Traceback" not in r.text


def test_method_not_allowed_is_problem_json(client):
    r = client.post("/api/v1/health")
    assert r.status_code == 405
    assert r.headers["content-type"].startswith("application/problem+json")


def test_validation_error_does_not_echo_input(app):
    class Body(BaseModel):
        password: str = Field(min_length=12)

    @app.post("/__test/validate")
    def validate(body: Body):
        return {}

    r = TestClient(app).post("/__test/validate", json={"password": "secret"})
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["errors"][0]["field"] == "body.password"
    assert "secret" not in r.text


def test_unhandled_exception_hides_details(app):
    @app.get("/__test/boom")
    def boom():
        raise RuntimeError("secret-internal-detail")

    r = TestClient(app, raise_server_exceptions=False).get("/__test/boom")
    assert r.status_code == 500
    assert r.headers["content-type"].startswith("application/problem+json")
    assert "secret-internal-detail" not in r.text
    assert "Traceback" not in r.text


def test_security_headers(client):
    r = client.get("/api/v1/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_docs_disabled_in_production(settings):
    prod = settings.model_copy(update={"env": "production", "jwt_secret": "x" * 40})
    with TestClient(create_app(prod)) as c:
        r = c.get("/docs")
        assert r.status_code == 404
        assert r.headers["content-type"].startswith("application/problem+json")