import json, os, subprocess, time, urllib.request
from datetime import datetime, timezone
from .settings import cache_dir

URL = "https://api.anthropic.com/api/oauth/usage"
BACKOFF_S = 600


def read_token():
    try:
        creds = subprocess.run(["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                               capture_output=True, text=True, timeout=5).stdout
        return json.loads(creds)["claudeAiOauth"]["accessToken"]
    except Exception:
        return None


def http_get(token):
    req = urllib.request.Request(URL, headers={"Authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def _age(p):
    return time.time() - p.stat().st_mtime if p.exists() else 1e9


def fetch(conn, settings, now=None, http=None, keychain=None, force=False):
    """Fetch quota if due. Returns parsed dict or None. Caches to quota.json and appends to quota table."""
    now = now or time.time()
    http, keychain = http or http_get, keychain or read_token
    cache, backoff = cache_dir() / "quota.json", cache_dir() / "quota.backoff"
    if not force and (_age(cache) < settings["data"]["poll_interval"] or _age(backoff) < BACKOFF_S):
        return current()
    token = keychain()
    if not token:
        backoff.touch()
        return None
    status, body = http(token)
    if status != 200:
        backoff.touch()
        return None
    try:
        d = json.loads(body)
        five, week = d["five_hour"], d["seven_day"]
    except Exception:
        backoff.touch()
        return None
    cache.write_text(body)
    backoff.unlink(missing_ok=True)
    conn.execute("INSERT OR REPLACE INTO quota VALUES(?,?,?,?,?,?)",
                 (int(now), five.get("utilization"), five.get("resets_at"), week.get("utilization"), week.get("resets_at"), body))
    conn.commit()
    return current()


def current():
    cache = cache_dir() / "quota.json"
    if not cache.exists():
        return None
    try:
        d = json.loads(cache.read_text())
    except Exception:
        return None
    d["age_s"] = int(_age(cache))
    d["backoff"] = _age(cache_dir() / "quota.backoff") < BACKOFF_S
    return d


def left_minutes(window, now=None):
    if not window or not window.get("resets_at"):
        return 0
    now = now or datetime.now(timezone.utc)
    return max(int((datetime.fromisoformat(window["resets_at"]) - now).total_seconds() // 60), 0)


def history(conn, from_ts, to_ts):
    return [dict(r) for r in conn.execute(
        "SELECT ts, five_pct, five_reset, week_pct, week_reset FROM quota WHERE ts BETWEEN ? AND ? ORDER BY ts", (from_ts, to_ts))]
