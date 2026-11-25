import psycopg2

from pipeline import db
from pipeline.config import load_settings


def test_get_connection_retries_until_database_is_ready(monkeypatch):
    """Fail twice like a starting database, then succeed: we must see exactly 3 attempts."""
    calls = {"n": 0}

    def fake_connect(**kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise psycopg2.OperationalError("database is starting up")
        return "connected"

    monkeypatch.setattr(db.psycopg2, "connect", fake_connect)
    # Skip the real waiting so the test runs instantly
    monkeypatch.setattr(db.time, "sleep", lambda seconds: None)

    assert db.get_connection(load_settings()) == "connected"
    assert calls["n"] == 3


def test_get_connection_gives_up_after_max_wait(monkeypatch):
    """A database that never comes up must raise instead of looping forever."""

    def always_fail(**kwargs):
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(db.psycopg2, "connect", always_fail)
    monkeypatch.setattr(db.time, "sleep", lambda seconds: None)

    try:
        db.get_connection(load_settings(), max_wait_s=0)
    except psycopg2.OperationalError:
        return  # expected: we re-raise once the deadline has passed
    raise AssertionError("expected OperationalError")
