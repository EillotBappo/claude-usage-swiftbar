import os, shutil, time
from pathlib import Path
from claude_usage import db, scan, settings as S

FIX = Path(__file__).parent / "fixtures"
NOW = time.mktime((2026, 11, 2, 12, 0, 0, 0, 0, -1))


def setup(tmp_path, labels=None):
    root = tmp_path / "projects" / "-Users-me-code-alpha"
    root.mkdir(parents=True)
    shutil.copy(FIX / "alpha.jsonl", root / "alpha.jsonl")
    shutil.copy(FIX / "old.jsonl", root / "old.jsonl")
    os.utime(root / "old.jsonl", (NOW - 400 * 86400, NOW - 400 * 86400))
    st = S.load()
    st["data"]["roots"] = [str(tmp_path / "projects")]
    st["data"]["project_labels"] = labels or {}
    return db.connect(tmp_path / "t.db"), st, root / "alpha.jsonl"


def test_first_run_dedupes_and_skips_junk(tmp_path):
    conn, st, _ = setup(tmp_path)
    r = scan.run(conn, st, NOW)
    assert r == {"files": 1, "added": 3}
    rows = conn.execute("SELECT * FROM messages ORDER BY ts").fetchall()
    assert [x["project"] for x in rows] == ["alpha", "alpha", "beta"]
    assert rows[0]["cache_r"] == 200 and rows[0]["thinking"] == 2 and rows[1]["model"] == "claude-opus-5-5"


def test_second_run_adds_nothing(tmp_path):
    conn, st, _ = setup(tmp_path)
    scan.run(conn, st, NOW)
    assert scan.run(conn, st, NOW) == {"files": 0, "added": 0}


def test_appended_line_is_picked_up_incrementally(tmp_path):
    conn, st, f = setup(tmp_path)
    scan.run(conn, st, NOW)
    line = open(FIX / "alpha.jsonl").read().splitlines()[0].replace('"m1"', '"m9"').replace('"r1"', '"r9"')
    with open(f, "a") as fh:
        fh.write(line + "\n")
    os.utime(f, (NOW + 5, NOW + 5))
    assert scan.run(conn, st, NOW)["added"] == 1
    assert conn.execute("SELECT offset FROM files").fetchone()["offset"] == f.stat().st_size


def test_truncated_file_reindexes(tmp_path):
    conn, st, f = setup(tmp_path)
    scan.run(conn, st, NOW)
    f.write_text(open(FIX / "alpha.jsonl").read().splitlines()[0] + "\n")
    os.utime(f, (NOW + 5, NOW + 5))
    scan.run(conn, st, NOW)
    assert conn.execute("SELECT offset FROM files").fetchone()["offset"] == f.stat().st_size


def test_project_labels(tmp_path):
    conn, st, _ = setup(tmp_path, {"/Users/me/code/alpha": "Alpha App", "beta": "Beta"})
    scan.run(conn, st, NOW)
    assert sorted({r["project"] for r in conn.execute("SELECT project FROM messages")}) == ["Alpha App", "Beta"]
