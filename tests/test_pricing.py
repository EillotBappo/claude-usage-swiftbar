import pytest
from claude_usage import pricing as P, settings as S


def test_exact_model():
    t = P.table(S.DEFAULTS)
    assert P.cost("claude-opus-5-5", 1_000_000, 0, 0, 0, t) == 5


def test_prefix_match_prefers_longest():
    t = {"claude-opus": {"in": 1, "out": 1, "cache_w": 1, "cache_r": 1}, "claude-opus-4": {"in": 2, "out": 1, "cache_w": 1, "cache_r": 1},
         "default": {"in": 9, "out": 9, "cache_w": 9, "cache_r": 9}}
    assert P.cost("claude-opus-4-1", 1_000_000, 0, 0, 0, t) == 2
    assert P.cost("claude-opus-3", 1_000_000, 0, 0, 0, t) == 1


def test_default_fallback_and_override():
    st = {"pricing": {"default": {"in": 7, "out": 0, "cache_w": 0, "cache_r": 0}}}
    assert P.cost("mystery", 1_000_000, 0, 0, 0, P.table(st)) == 7


def test_cost_sql_matches_python(tmp_path):
    import sqlite3
    t = P.table(S.DEFAULTS)
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE messages(model, input, output, cache_w, cache_r)")
    c.execute("INSERT INTO messages VALUES('claude-fable-5-1', 100, 50, 1000, 2000)")
    sql = c.execute(f"SELECT {P.cost_sql(t)} FROM messages").fetchone()[0]
    assert sql == pytest.approx(P.cost("claude-fable-5-1", 100, 50, 1000, 2000, t))
