import json, shutil, threading, time, urllib.request
from http.client import HTTPConnection
from pathlib import Path
import pytest
from claude_usage import db, scan, server, settings as S

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def api(tmp_path):
    root = tmp_path / "p"; root.mkdir(); shutil.copy(FIX / "alpha.jsonl", root / "a.jsonl")
    st = S.load(); st["data"]["roots"] = [str(root)]; S.save(st)
    srv = server.make_server(S.load(), port=0)
    th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
    port = srv.server_address[1]

    def call(method, path, body=None):
        c = HTTPConnection("127.0.0.1", port, timeout=5)
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers={"Content-Type": "application/json"})
        r = c.getresponse(); data = r.read()
        return r.status, (json.loads(data) if r.getheader("Content-Type", "").startswith("application/json") else data)
    yield call
    srv.shutdown()


def test_ping_and_static(api):
    assert api("GET", "/api/ping")[0] == 200
    s, body = api("GET", "/")
    assert s == 200 and b"<!doctype html>" in body.lower()
    assert api("GET", "/../settings.py")[0] == 404


def test_data_endpoints_shapes(api):
    s, d = api("GET", "/api/summary"); assert s == 200 and d["messages"] == 3 and "cost" in d
    s, d = api("GET", "/api/series?from=2026-11-01&to=2026-11-02"); assert s == 200 and len(d) == 2
    s, d = api("GET", "/api/series?bucket=hour"); assert s == 200 and len(d) == 3
    s, d = api("GET", "/api/heatmap"); assert s == 200 and len(d) == 7 and len(d[0]) == 24
    s, d = api("GET", "/api/breakdown?by=project"); assert s == 200 and [r["key"] for r in d] == ["alpha", "beta"]
    s, d = api("GET", "/api/breakdown?by=project&project=beta"); assert [r["key"] for r in d] == ["beta"]
    s, d = api("GET", "/api/options"); assert d["projects"] == ["alpha", "beta"] and len(d["sessions"]) == 2
    s, d = api("GET", "/api/savings"); assert s == 200 and "available" in d
    s, d = api("GET", "/api/quota"); assert s == 200 and d["history"] == [] and "current" in d


def test_settings_get_put_validation(api):
    s, d = api("GET", "/api/settings")
    assert s == 200 and d["settings"]["menubar"]["style"] == "pill" and "claude-opus-5-5" in d["pricing"]
    new = d["settings"]; new["menubar"]["style"] = "text"; new["menubar"]["fields"] = ["today_cost"]
    s, d = api("PUT", "/api/settings", new); assert s == 200 and d["settings"]["menubar"]["style"] == "text"
    assert S.load()["menubar"]["fields"] == ["today_cost"]
    new["menubar"]["style"] = "neon"
    s, d = api("PUT", "/api/settings", new); assert s == 400 and "style" in d["error"]
    assert api("GET", "/api/nope")[0] == 404
