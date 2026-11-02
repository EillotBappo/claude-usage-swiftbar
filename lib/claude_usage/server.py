import json, mimetypes, os, subprocess, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from . import db, pricing, quota as Q, queries, savings, scan, settings as S

STATIC = Path(__file__).parent / "dashboard"
TABS = {"overview", "tokens", "quota", "projects", "sessions", "savings", "settings"}


class State:
    def __init__(self, settings):
        self.settings = settings
        self.lock = threading.Lock()
        self.conn = db.connect()
        self.last_scan = 0
        self.last_request = time.time()

    def fresh(self):
        """Call under self.lock. Re-scans transcripts at most once a minute."""
        if time.time() - self.last_scan > 60:
            try:
                scan.run(self.conn, self.settings)
            except Exception as e:
                print("scan:", e, file=sys.stderr)
            self.last_scan = time.time()
        return self.conn


def handler_for(state: State):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _static(self, rel):
            p = (STATIC / (rel or "index.html")).resolve()
            if STATIC.resolve() not in p.parents or not p.is_file():
                return self._json(404, {"error": "not found"})
            body = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(str(p))[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            state.last_request = time.time()
            with state.lock:
                return self._get()

        def _get(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            path = u.path
            if not path.startswith("/api/"):
                return self._static(path.lstrip("/"))
            try:
                if path == "/api/ping":
                    return self._json(200, {"ok": True, "version": __import__("claude_usage").__version__})
                st = state.settings
                t = pricing.table(st)
                f = queries.Filters.from_query(q)
                if path == "/api/summary":
                    conn = state.fresh(); return self._json(200, queries.summary(conn, f, t))
                if path == "/api/series":
                    conn = state.fresh(); return self._json(200, queries.series(conn, f, t, q.get("bucket", "day")))
                if path == "/api/heatmap":
                    conn = state.fresh(); return self._json(200, queries.heatmap(conn, f))
                if path == "/api/breakdown":
                    conn = state.fresh(); return self._json(200, queries.breakdown(conn, f, t, q.get("by", "model")))
                if path == "/api/options":
                    conn = state.fresh(); return self._json(200, queries.options(conn))
                if path == "/api/quota":
                    conn = state.fresh()
                    Q.fetch(conn, st)
                    f0 = int(time.mktime(time.strptime(f.from_day, "%Y-%m-%d"))) if f.from_day else 0
                    f1 = int(time.mktime(time.strptime(f.to_day, "%Y-%m-%d"))) + 86400 if f.to_day else 2 ** 40
                    return self._json(200, {"current": Q.current(), "history": Q.history(conn, f0, f1)})
                if path == "/api/savings":
                    return self._json(200, savings.collect(st))
                if path == "/api/settings":
                    return self._json(200, {"settings": st, "pricing": t, "fields": S.FIELDS, "styles": S.STYLES,
                                            "paths": {"settings": str(S.settings_path()), "db": str(S.cache_dir() / "usage.db")}})
                return self._json(404, {"error": "not found"})
            except Exception as e:
                return self._json(500, {"error": str(e)})

        def do_PUT(self):
            state.last_request = time.time()
            if urlparse(self.path).path != "/api/settings":
                return self._json(404, {"error": "not found"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                S.save(body)
                state.settings = S.load()
                return self._json(200, {"ok": True, "settings": state.settings})
            except (ValueError, KeyError, TypeError) as e:
                return self._json(400, {"error": str(e)})

        def do_POST(self):
            state.last_request = time.time()
            if urlparse(self.path).path == "/api/refresh":
                with state.lock:
                    conn = state.fresh()
                    return self._json(200, {"quota": Q.fetch(conn, state.settings, force=True) is not None})
            return self._json(404, {"error": "not found"})
    return H


def make_server(settings, port=None):
    state = State(settings)
    srv = ThreadingHTTPServer(("127.0.0.1", settings["dashboard"]["port"] if port is None else port), handler_for(state))
    srv.state = state
    srv.daemon_threads = True
    return srv


def _idle_exit(srv, minutes):
    while True:
        time.sleep(30)
        if time.time() - srv.state.last_request > minutes * 60:
            srv.shutdown(); return


def url(settings, tab=None):
    u = f"http://127.0.0.1:{settings['dashboard']['port']}/"
    return u + (f"#tab={tab}" if tab in TABS else "")


def ping(settings):
    try:
        with urllib.request.urlopen(url(settings) + "api/ping", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def ensure_running(settings):
    if ping(settings):
        return True
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    subprocess.Popen([sys.executable, "-m", "claude_usage.server", "--serve"], env=env, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=open(S.cache_dir() / "server.log", "a"), start_new_session=True)
    for _ in range(40):
        time.sleep(0.25)
        if ping(settings):
            return True
    return False


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    settings = S.load()
    if "--serve" in argv:
        port = int(argv[argv.index("--port") + 1]) if "--port" in argv else None
        srv = make_server(settings, port)
        threading.Thread(target=_idle_exit, args=(srv, settings["dashboard"]["idle_exit_min"]), daemon=True).start()
        print(f"claude-usage dashboard on {url(settings)}", flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        return
    tab = next((a for a in argv if a in TABS), None)
    if not ensure_running(settings):
        print("could not start dashboard server; see", S.cache_dir() / "server.log", file=sys.stderr); sys.exit(1)
    if "--no-open" not in argv:
        subprocess.run(["open", url(settings, tab)])
    print(url(settings, tab))


if __name__ == "__main__":
    main()
