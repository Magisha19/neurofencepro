import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def settings(tmp_path):
    db_file = (tmp_path / "test.db").as_posix()
    return Settings(_env_file=None, env="test", database_url=f"sqlite:///{db_file}")


@pytest.fixture()
def app(settings):
    application = create_app(settings)
    yield application
    application.state.engine.dispose()


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client