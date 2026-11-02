import json, os, time
from datetime import datetime, timedelta, timezone
from claude_usage import db, quota as Q, settings as S

BODY = json.dumps({"five_hour": {"utilization": 67.0, "resets_at": "2026-11-02T10:59:59+00:00"},
                   "seven_day": {"utilization": 12.0, "resets_at": "2026-11-08T02:59:59+00:00"}})


def test_200_writes_cache_and_row(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    d = Q.fetch(conn, S.load(), 1000, http=lambda t: (200, BODY), keychain=lambda: "tok")
    assert d["five_hour"]["utilization"] == 67.0 and d["age_s"] == 0 and d["backoff"] is False
    assert conn.execute("SELECT ts, five_pct, week_pct FROM quota").fetchone()[:] == (1000, 67.0, 12.0)


def test_429_sets_backoff_and_keeps_old_cache(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    Q.fetch(conn, S.load(), 1000, http=lambda t: (200, BODY), keychain=lambda: "tok")
    calls = []
    d = Q.fetch(conn, S.load(), 2000, http=lambda t: calls.append(1) or (429, ""), keychain=lambda: "tok", force=True)
    assert d is None and (S.cache_dir() / "quota.backoff").exists()
    assert Q.current()["five_hour"]["utilization"] == 67.0 and Q.current()["backoff"] is True
    # within backoff: no http call even when cache is stale
    Q.fetch(conn, S.load(), 3000, http=lambda t: calls.append(1) or (200, BODY), keychain=lambda: "tok")
    assert len(calls) == 1


def test_no_token_returns_none(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    assert Q.fetch(conn, S.load(), 1000, http=lambda t: (200, BODY), keychain=lambda: None) is None


def test_poll_interval_respected(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    calls = []
    h = lambda t: calls.append(1) or (200, BODY)
    Q.fetch(conn, S.load(), http=h, keychain=lambda: "tok")
    Q.fetch(conn, S.load(), http=h, keychain=lambda: "tok")
    assert len(calls) == 1


def test_left_minutes():
    now = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
    assert Q.left_minutes({"resets_at": "2026-11-02T10:59:59+00:00"}, now) == 119
    assert Q.left_minutes({"resets_at": "2026-11-02T08:00:00+00:00"}, now) == 0
    assert Q.left_minutes({}, now) == 0
