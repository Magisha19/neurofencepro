import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Base, Experiment, Metric, User

EXPECTED_TABLES = {
    "users", "experiments", "experiment_events", "metrics", "behaviour_results",
    "fuzzing_results", "risk_scores", "reports", "audit_logs",
}


@pytest.fixture()
def session(app):
    with Session(app.state.engine) as s:
        yield s


def make_user(session, name="alice"):
    user = User(username=name, password_hash="not-a-real-hash")
    session.add(user)
    session.commit()
    return user


def make_experiment(session, user):
    exp = Experiment(user_id=user.id, name="e", config_json={}, config_hash="0" * 64)
    session.add(exp)
    session.commit()
    return exp


def test_exactly_nine_tables():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_tables_created_in_database(app):
    assert EXPECTED_TABLES <= set(inspect(app.state.engine).get_table_names())


def test_every_table_has_user_id():
    for name, table in Base.metadata.tables.items():
        if name == "users":
            continue
        assert "user_id" in table.c, name
        if name != "audit_logs":
            assert not table.c.user_id.nullable, name
    assert Base.metadata.tables["audit_logs"].c.user_id.nullable


def test_provenance_is_required():
    for name in ("metrics", "risk_scores"):
        assert not Base.metadata.tables[name].c.provenance.nullable, name


def test_experiment_defaults(session):
    exp = make_experiment(session, make_user(session))
    assert exp.status == "queued"
    assert exp.stage == "queued"
    assert exp.progress == 0.0


def test_username_unique(session):
    make_user(session, "alice")
    session.add(User(username="alice", password_hash="x"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_foreign_keys_enforced(session):
    session.add(Experiment(user_id=999, name="e", config_json={}, config_hash="0" * 64))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_null_ratio_roundtrip_and_cascade(session):
    user = make_user(session)
    exp = make_experiment(session, user)
    session.add(
        Metric(
            user_id=user.id, experiment_id=exp.id, detector="lof", seed=0,
            tp=0, fn=2, fp=0, tn=8, precision=None, recall=0.0,
            provenance="TOY_MODEL_HIDDEN",
        )
    )
    session.commit()
    metric = session.scalars(select(Metric)).one()
    assert metric.precision is None  # zero denominator stays NULL, not 0

    session.delete(exp)
    session.commit()
    assert session.scalar(select(func.count()).select_from(Metric)) == 0