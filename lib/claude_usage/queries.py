from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional
from .pricing import cost_sql

BY = {"model": "model", "project": "project", "session": "session"}


@dataclass
class Filters:
    from_day: Optional[str] = None   # YYYY-MM-DD inclusive
    to_day: Optional[str] = None
    projects: List[str] = field(default_factory=list)
    models: List[str] = field(default_factory=list)
    sessions: List[str] = field(default_factory=list)

    @classmethod
    def from_query(cls, q: dict):
        g = lambda k: [x for x in (q.get(k) or "").split(",") if x]
        f = cls(q.get("from") or None, q.get("to") or None, g("project"), g("model"), g("session"))
        preset = q.get("range")
        if preset and not (f.from_day or f.to_day):
            today = date.today()
            days = {"today": 0, "7d": 6, "30d": 29, "90d": 89}.get(preset)
            if preset == "month":
                f.from_day = today.replace(day=1).isoformat()
            elif days is not None:
                f.from_day = (today - timedelta(days=days)).isoformat()
            f.to_day = today.isoformat()
        return f

    def where(self):
        cl, args = ["1=1"], []
        if self.from_day: cl.append("day >= ?"); args.append(self.from_day)
        if self.to_day: cl.append("day <= ?"); args.append(self.to_day)
        for col, vals in (("project", self.projects), ("model", self.models), ("session", self.sessions)):
            if vals:
                cl.append(f"{col} IN ({','.join('?' * len(vals))})"); args += vals
        return " AND ".join(cl), args


SUMS = "SUM(input) input, SUM(output) output, SUM(cache_w) cache_w, SUM(cache_r) cache_r, SUM(thinking) thinking, COUNT(*) messages"


def _finish(r, t):
    d = dict(r)
    for k in ("input", "output", "cache_w", "cache_r", "thinking", "messages"):
        d[k] = int(d.get(k) or 0)
    d["cost"] = round(float(d.get("cost") or 0), 4)
    d["total"] = d["input"] + d["output"] + d["cache_w"] + d["cache_r"]
    d["new_tokens"] = d["input"] + d["output"] + d["cache_w"]
    denom = d["input"] + d["cache_w"] + d["cache_r"]
    d["cache_hit"] = round(d["cache_r"] / denom, 4) if denom else 0
    return d


def summary(conn, f, t):
    w, a = f.where()
    r = conn.execute(f"SELECT {SUMS}, SUM({cost_sql(t)}) cost, COUNT(DISTINCT session) sessions, "
                     f"COUNT(DISTINCT project) projects, MIN(day) first_day, MAX(day) last_day FROM messages WHERE {w}", a).fetchone()
    d = _finish(r, t)
    d["sessions"] = int(d.get("sessions") or 0); d["projects"] = int(d.get("projects") or 0)
    return d


def series(conn, f, t, bucket="day"):
    w, a = f.where()
    if bucket == "hour":
        key = "strftime('%Y-%m-%dT%H:00', ts, 'unixepoch', 'localtime')"
    else:
        key = "day"
    rows = conn.execute(f"SELECT {key} bucket, {SUMS}, SUM({cost_sql(t)}) cost FROM messages WHERE {w} GROUP BY bucket ORDER BY bucket", a).fetchall()
    out = [_finish(r, t) for r in rows]
    if bucket == "day" and f.from_day and f.to_day:   # fill gaps so charts have even spacing
        have = {r["bucket"]: r for r in out}
        d0, d1 = date.fromisoformat(f.from_day), date.fromisoformat(f.to_day)
        out = [have.get((d0 + timedelta(i)).isoformat()) or _finish({"bucket": (d0 + timedelta(i)).isoformat()}, t)
               for i in range((d1 - d0).days + 1)]
    return out


def heatmap(conn, f):
    w, a = f.where()
    grid = [[0] * 24 for _ in range(7)]
    for r in conn.execute(f"SELECT weekday, hour, SUM(input+output+cache_w) n FROM messages WHERE {w} GROUP BY weekday, hour", a):
        grid[r["weekday"]][r["hour"]] = int(r["n"])
    return grid


def breakdown(conn, f, t, by="model"):
    col = BY.get(by, "model")
    w, a = f.where()
    rows = conn.execute(f"SELECT {col} key, {SUMS}, SUM({cost_sql(t)}) cost, MIN(ts) first_ts, MAX(ts) last_ts, "
                        f"MAX(project) project, MAX(model) model, MAX(cwd) cwd FROM messages WHERE {w} GROUP BY {col} ORDER BY SUM(input+output+cache_w) DESC", a).fetchall()
    out = []
    for r in rows:
        d = _finish(r, t)
        d["first_ts"], d["last_ts"] = int(d["first_ts"] or 0), int(d["last_ts"] or 0)
        out.append(d)
    return out


def options(conn):
    q = lambda col: [r[0] for r in conn.execute(f"SELECT DISTINCT {col} FROM messages WHERE {col} IS NOT NULL ORDER BY {col}")]
    return {"projects": q("project"), "models": q("model"),
            "sessions": [dict(r) for r in conn.execute("SELECT session, project, MAX(ts) last_ts FROM messages GROUP BY session ORDER BY last_ts DESC LIMIT 500")]}
