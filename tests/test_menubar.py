import json
from datetime import datetime, timezone
from claude_usage import menubar as M, settings as S

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
Q = {"five_hour": {"utilization": 67.0, "resets_at": "2026-11-02T10:59:59+00:00"},
     "seven_day": {"utilization": 12.0, "resets_at": "2026-11-08T02:59:59+00:00"}, "age_s": 10, "backoff": False}
ST = {"today": {"new_tokens": 1_500_000, "cost": 12.5, "input": 1, "output": 2, "cache_w": 3, "cache_r": 4},
      "week": {"new_tokens": 7_000_000, "cost": 70}, "series": [], "heat": [[0]*24 for _ in range(7)], "models": [], "days": 14}


def st(**over):
    s = S.load()
    s["menubar"].update(over)
    return s


def test_default_fields_pill():
    t = M.title(st(), Q, ST, NOW)
    assert t.startswith("67% · 1:59 · wk 12% | templateImage=") and "color=" not in t


def test_field_order_and_text_style():
    t = M.title(st(fields=["today_cost", "week_tokens", "five_pct"], style="text"), Q, ST, NOW)
    assert t == "$12.50 · 7d 7.0M · 67% |"


def test_thresholds_color():
    assert "#FF9F0A" in M.title(st(thresholds={"warn": 60, "danger": 90}), Q, ST, NOW)
    assert "#FF3B30" in M.title(st(thresholds={"warn": 10, "danger": 50}), Q, ST, NOW)


def test_show_when_apps():
    s = st(show_when={"mode": "apps", "apps": ["zed"]})
    assert M.visible(s, "/applications/zed.app/contents/macos/zed\nfinder") is True
    assert M.visible(s, "finder\nsafari") is False
    assert M.visible(st(), "") is True


def test_hide_below_pct_and_stale_marker():
    assert M.render(st(hide_below_pct=80), Q, ST, NOW) == ""
    out = M.render(st(), dict(Q, age_s=2000), ST, NOW)
    assert out.startswith("~67%") and "Last updated 33 min ago" in out or "image=" in out


def test_no_quota_fallback_and_menu_items():
    out = M.render(st(), None, ST, NOW, plugin_path="/x/claude-usage.1m.sh")
    assert out.startswith("– · – · wk – |")
    assert "Open dashboard | bash='/x/claude-usage.1m.sh' param1=open" in out
    assert "param1=open param2=settings" in out and "param1=refresh" in out
