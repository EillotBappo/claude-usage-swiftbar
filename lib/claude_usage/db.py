import sqlite3
from .settings import cache_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY,
  ts INTEGER NOT NULL, day TEXT NOT NULL, hour INTEGER NOT NULL, weekday INTEGER NOT NULL,
  model TEXT, project TEXT, cwd TEXT, session TEXT, msg_id TEXT, request_id TEXT,
  input INTEGER DEFAULT 0, output INTEGER DEFAULT 0, cache_w INTEGER DEFAULT 0,
  cache_r INTEGER DEFAULT 0, thinking INTEGER DEFAULT 0,
  dedupe TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS messages_day ON messages(day);
CREATE INDEX IF NOT EXISTS messages_project ON messages(project);
CREATE INDEX IF NOT EXISTS messages_session ON messages(session);
CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, mtime REAL, size INTEGER, offset INTEGER);
CREATE TABLE IF NOT EXISTS quota(ts INTEGER PRIMARY KEY, five_pct REAL, five_reset TEXT, week_pct REAL, week_reset TEXT, raw TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


def connect(path=None) -> sqlite3.Connection:
    path = path or (cache_dir() / "usage.db")
    conn = sqlite3.connect(str(path), timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO meta VALUES('schema', '1')")
    conn.commit()
    return conn


def set_meta(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO meta VALUES(?, ?)", (key, str(value)))


def get_meta(conn, key, default=None):
    r = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default
