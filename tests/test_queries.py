import shutil, time
from pathlib import Path
from claude_usage import db, scan, queries as Q, pricing as P, settings as S

FIX = Path(__file__).parent / "fixtures"
NOW = time.mktime((2026, 11, 2, 12, 0, 0, 0, 0, -1))


def seeded(tmp_path):
    root = tmp_path / "p"; root.mkdir()
    shutil.copy(FIX / "alpha.jsonl", root / "a.jsonl")
    st = S.load(); st["data"]["roots"] = [str(root)]
    conn = db.connect(tmp_path / "t.db"); scan.run(conn, st, NOW)
    return conn, P.table(st)


def test_summary_totals_and_cache_hit(tmp_path):
    conn, t = seeded(tmp_path)
    s = Q.summary(conn, Q.Filters(), t)
    assert s["messages"] == 3 and s["input"] == 30 and s["cache_r"] == 600 and s["sessions"] == 2
    assert s["cache_hit"] == round(600 / (30 + 300 + 600), 4)
    assert s["cost"] > 0


def test_filters_project_model_and_dates(tmp_path):
    conn, t = seeded(tmp_path)
    assert Q.summary(conn, Q.Filters(projects=["beta"]), t)["messages"] == 1
    assert Q.summary(conn, Q.Filters(models=["claude-opus-5-5"]), t)["messages"] == 1
    assert Q.summary(conn, Q.Filters(from_day="2026-11-02"), t)["messages"] == 1
    assert Q.summary(conn, Q.Filters(to_day="2026-11-01"), t)["messages"] == 2


def test_series_day_fills_gaps_and_hour(tmp_path):
    conn, t = seeded(tmp_path)
    s = Q.series(conn, Q.Filters("2026-10-30", "2026-11-02"), t)
    assert [x["bucket"] for x in s] == ["2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"]
    assert s[2]["messages"] == 2 and s[0]["messages"] == 0
    assert len(Q.series(conn, Q.Filters(), t, "hour")) == 3


def test_breakdown_sorted_desc_and_heatmap(tmp_path):
    conn, t = seeded(tmp_path)
    b = Q.breakdown(conn, Q.Filters(), t, "project")
    assert [x["key"] for x in b] == ["alpha", "beta"] and b[0]["first_ts"] <= b[0]["last_ts"]
    assert sum(map(sum, Q.heatmap(conn, Q.Filters()))) == 3 * 115


def test_from_query_presets():
    f = Q.Filters.from_query({"range": "7d", "project": "a,b"})
    assert f.projects == ["a", "b"] and f.from_day and f.to_day
    f = Q.Filters.from_query({"from": "2026-01-01", "to": "2026-01-31", "range": "7d"})
    assert f.from_day == "2026-01-01"
