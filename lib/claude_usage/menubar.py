import os, subprocess, sys
from datetime import date, datetime, timedelta, timezone
from . import db, pricing, quota as Q, queries, scan, settings as S
from .render import ACTION, bar, chart, fmt, money, row

RED, AMBER = "#FF3B30", "#FF9F0A"


def running_apps():
    try:
        return subprocess.run(["ps", "-axo", "comm="], capture_output=True, text=True, timeout=3).stdout.lower()
    except Exception:
        return ""


def visible(settings, running: str) -> bool:
    sw = settings["menubar"]["show_when"]
    if sw["mode"] == "apps":
        return any(a.lower() in running for a in sw["apps"])
    return True


def stats(conn, settings, t):
    today = date.today().isoformat()
    days = settings["menubar"]["dropdown"]["days"]
    f = queries.Filters((date.today() - timedelta(days=days - 1)).isoformat(), today)
    return {"today": queries.summary(conn, queries.Filters(today, today), t),
            "week": queries.summary(conn, queries.Filters((date.today() - timedelta(days=6)).isoformat(), today), t),
            "series": queries.series(conn, f, t), "heat": queries.heatmap(conn, f),
            "models": queries.breakdown(conn, f, t, "model")[:4], "days": days}


def _field(name, q, st, now):
    five, week = (q or {}).get("five_hour") or {}, (q or {}).get("seven_day") or {}
    fl, wl = Q.left_minutes(five, now), Q.left_minutes(week, now)
    return {
        "five_pct": f"{(five.get('utilization') or 0):.0f}%" if q else "–",
        "five_left": f"{fl//60}:{fl%60:02d}" if q else "–",
        "week_pct": f"wk {(week.get('utilization') or 0):.0f}%" if q else "wk –",
        "week_left": f"{wl//1440}d{(wl%1440)//60}h" if q else "–",
        "today_tokens": fmt(st["today"]["new_tokens"]),
        "today_cost": money(st["today"]["cost"]),
        "week_tokens": f"7d {fmt(st['week']['new_tokens'])}",
    }[name]


def title(settings, q, st, now):
    m = settings["menubar"]
    five = ((q or {}).get("five_hour") or {}).get("utilization") or 0
    week = ((q or {}).get("seven_day") or {}).get("utilization") or 0
    worst = max(five, week)
    color = f" color={RED}" if worst >= m["thresholds"]["danger"] else f" color={AMBER}" if worst >= m["thresholds"]["warn"] else ""
    stale = q and q.get("age_s", 0) > 900
    text = " · ".join(_field(f, q, st, now) for f in m["fields"])
    if m["style"] == "compact":
        text = " ".join(_field(f, q, st, now) for f in m["fields"][:2])
    if stale:
        text = "~" + text
    if m["style"] in ("pill", "compact"):
        return f"{text} | templateImage={bar(five / 100)}{color}"
    if m["style"] == "icon":
        return f"✳︎ {text} |{color}"
    return f"{text} |{color}"


def render(settings, q, st, now=None, plugin_path=None) -> str:
    now = now or datetime.now(timezone.utc)
    m, out = settings["menubar"], []
    five = ((q or {}).get("five_hour") or {}).get("utilization") or 0
    week = ((q or {}).get("seven_day") or {}).get("utilization") or 0
    if m["hide_below_pct"] and max(five, week) < m["hide_below_pct"]:
        return ""
    out.append(title(settings, q, st, now))
    out.append("---")
    if q:
        fh, wk = q.get("five_hour") or {}, q.get("seven_day") or {}
        fl, wl = Q.left_minutes(fh, now), Q.left_minutes(wk, now)
        if q.get("age_s", 0) > 900:
            out.append(row(f"Last updated {q['age_s']//60} min ago" + (" (rate limited)" if q.get("backoff") else ""), 11))
        out.append(row(f"5h session {five:.0f}%", 13, pct=five / 100))
        if fh.get("resets_at"):
            out.append(row(f"{fl//60}h{fl%60:02d}m left, resets {datetime.fromisoformat(fh['resets_at']).astimezone():%H:%M}", 11))
        out.append(row(f"Week {week:.0f}%", 13, pct=week / 100))
        if wk.get("resets_at"):
            out.append(row(f"resets {datetime.fromisoformat(wk['resets_at']).astimezone():%a %d %b %H:%M}", 11))
    else:
        out.append(row("Quota unavailable — sign in to Claude Code, or rate limited (retrying)", 11))
    out.append("---")
    t = st["today"]
    out.append(row(f"Today · {fmt(t['new_tokens'])} tokens · {money(t['cost'])}", 15))
    out.append(row(f"in {fmt(t['input'])} · out {fmt(t['output'])} · cache write {fmt(t['cache_w'])} · read {fmt(t['cache_r'])}", 11, True, w=330))
    w = st["week"]
    out.append(row(f"7 days · {fmt(w['new_tokens'])} · avg {fmt(w['new_tokens']/7)}/day · {money(w['cost'])}", 13))
    if m["dropdown"]["charts"] and st["series"]:
        tot = [s["new_tokens"] for s in st["series"]]
        out.append("---")
        out.append(row(f"Last {st['days']} days", 11))
        out.append(f"| image={chart(tot, len(tot) - 1)} width=300 height=56{ACTION}")
        b = max(range(len(tot)), key=lambda i: tot[i])
        bd = date.fromisoformat(st["series"][b]["bucket"])
        out.append(row(f"{date.fromisoformat(st['series'][0]['bucket']):%d %b} → today · busiest {bd:%a %d %b} ({fmt(tot[b])})", 11, True, w=330))
        hr = [sum(st["heat"][d][h] for d in range(7)) for h in range(24)]
        if any(hr):
            ph = max(range(24), key=lambda i: hr[i])
            out.append("---")
            out.append(row(f"By hour of day (last {st['days']} days)", 11))
            out.append(f"| image={chart(hr, ph, h=44, color=(90, 160, 235))} width=300 height=44{ACTION}")
            out.append(row(f"00h ····· 12h ····· 23h · peak {ph:02d}:00–{ph+1:02d}:00 ({fmt(hr[ph])})", 11, True, w=330))
        if st["models"]:
            out.append("---")
            for r in st["models"]:
                out.append(row(f"{r['key'].replace('claude-', '')} · {fmt(r['new_tokens'])} · {money(r['cost'])}", 12, True))
    out.append("---")
    p = plugin_path or os.environ.get("SWIFTBAR_PLUGIN_PATH") or "claude-usage.1m.sh"
    out.append(f"Open dashboard | bash='{p}' param1=open terminal=false")
    out.append(f"Settings… | bash='{p}' param1=open param2=settings terminal=false")
    out.append(f"Refresh now | bash='{p}' param1=refresh terminal=false refresh=true")
    return "\n".join(out)


def main():
    try:
        settings = S.load()
    except ValueError as e:
        print("✳︎ settings error |color=#FF3B30\n---\n" + str(e).replace("\n", " ")); return
    if not visible(settings, running_apps()):
        return
    conn = db.connect()
    try:
        scan.run(conn, settings)
    except Exception as e:  # keep the bar alive even if a transcript is unreadable
        print(f"scan error: {e}", file=sys.stderr)
    q = Q.fetch(conn, settings)
    t = pricing.table(settings)
    print(render(settings, q, stats(conn, settings, t)))


if __name__ == "__main__":
    main()
