import pytest
from pydantic import ValidationError

from app.config import DEV_JWT_SECRET, Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.env == "development"
    assert s.access_token_minutes == 60
    assert s.jwt_algorithm == "HS256"


def test_production_rejects_default_or_short_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="production")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="production", jwt_secret=DEV_JWT_SECRET)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="production", jwt_secret="short")


def test_production_accepts_long_secret():
    s = Settings(_env_file=None, env="production", jwt_secret="x" * 40)
    assert s.env == "production"


def test_env_var_override(monkeypatch):
    monkeypatch.setenv("NEUROFENCE_ACCESS_TOKEN_MINUTES", "15")
    assert Settings(_env_file=None).access_token_minutes == 15


def test_token_lifetime_bounds():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, access_token_minutes=1)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, access_token_minutes=5000)