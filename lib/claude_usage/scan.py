import fnmatch, json, os, time
from datetime import datetime
from pathlib import Path
from .db import set_meta


def project_of(cwd, path, labels):
    name = os.path.basename(cwd.rstrip("/")) if cwd else Path(path).parent.name
    return labels.get(cwd, labels.get(name, name)) if labels else name


def _files(settings, cut):
    data = settings["data"]
    for root in data["roots"]:
        root = Path(root).expanduser()
        if not root.exists():
            continue
        for p in root.rglob("*.jsonl"):
            s = str(p)
            if data["include"] and not any(fnmatch.fnmatch(s, g) for g in data["include"]):
                continue
            if any(fnmatch.fnmatch(s, g) for g in data["exclude"]):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_mtime < cut:
                continue
            yield s, st


def _parse(line, path, labels, cut):
    if b'"usage"' not in line:
        return None
    try:
        e = json.loads(line)
    except Exception:
        return None
    m = e.get("message") or {}
    u = m.get("usage")
    ts = e.get("timestamp")
    if not isinstance(u, dict) or not ts:
        return None
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None
    if t.timestamp() < cut:
        return None
    session = e.get("sessionId") or Path(path).stem
    msg_id, req = m.get("id"), e.get("requestId")
    dedupe = f"{msg_id}|{req}" if msg_id else f"{session}|{ts}"
    g = lambda k: int(u.get(k) or 0)
    return (
        int(t.timestamp()), t.strftime("%Y-%m-%d"), t.hour, t.weekday(),
        m.get("model") or "?", project_of(e.get("cwd") or "", path, labels), e.get("cwd") or "",
        session, msg_id, req,
        g("input_tokens"), g("output_tokens"), g("cache_creation_input_tokens"), g("cache_read_input_tokens"),
        int(((u.get("output_tokens_details") or {}).get("thinking_tokens")) or 0),
        dedupe,
    )


INSERT = """INSERT OR IGNORE INTO messages(ts, day, hour, weekday, model, project, cwd, session, msg_id, request_id,
  input, output, cache_w, cache_r, thinking, dedupe) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""


def run(conn, settings, now=None):
    now = now or time.time()
    cut = now - settings["data"]["scan_days"] * 86400
    labels = settings["data"]["project_labels"]
    known = {r["path"]: r for r in conn.execute("SELECT * FROM files")}
    files = added = 0
    for path, st in _files(settings, cut):
        k = known.get(path)
        if k and k["mtime"] == st.st_mtime and k["size"] == st.st_size:
            continue
        offset = k["offset"] if k and st.st_size >= k["size"] else 0
        files += 1
        rows = []
        with open(path, "rb") as fh:
            fh.seek(offset)
            for line in fh:
                if not line.endswith(b"\n"):
                    break  # partial trailing line: re-read next time
                offset += len(line)
                r = _parse(line, path, labels, cut)
                if r:
                    rows.append(r)
        before = conn.total_changes
        conn.executemany(INSERT, rows)
        added += conn.total_changes - before
        conn.execute("INSERT OR REPLACE INTO files VALUES(?,?,?,?)", (path, st.st_mtime, st.st_size, offset))
    set_meta(conn, "last_scan", int(now))
    conn.commit()
    return {"files": files, "added": added}
