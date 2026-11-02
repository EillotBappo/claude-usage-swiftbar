import sqlite3
from claude_usage import savings as V


def test_nothing_available(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "TOOLS", tmp_path)
    monkeypatch.setattr(V.shutil, "which", lambda x: None)
    assert V.collect() == {"available": False, "sources": {}}


def test_distill_db_parsed(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "TOOLS", tmp_path)
    monkeypatch.setattr(V.shutil, "which", lambda x: None)
    c = sqlite3.connect(tmp_path / "distill.db")
    c.execute("CREATE TABLE logs(id, original_tokens, compressed_tokens, tokens_saved)")
    c.executemany("INSERT INTO logs VALUES(?,?,?,?)", [(1, 1000, 100, 900), (2, 500, 50, 450)]); c.commit(); c.close()
    s = V.collect()
    assert s["available"] and s["sources"]["distill"] == {"rows": 2, "original_tokens": 1500, "compressed_tokens": 150, "saved_tokens": 1350}
